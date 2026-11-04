"""
app/services/attendance_service.py — Core Attendance Recording & Validation Service.

Enforces acceptance criteria:
  - Daily attendance recording
  - Duplicate attendance entries for the same employee and date are prevented or cleanly handled
  - Atomic transactions for multi-record operations
  - Strict validation of allowed statuses: Present, Absent, Leave, Holiday
"""
from datetime import date
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Employee, Attendance


VALID_STATUSES = ("Present", "Absent", "Leave", "Holiday")


def record_single_attendance(employee_id: int, attendance_date: date, status: str) -> tuple[bool, str, Attendance | None]:
    """
    Records or updates attendance for one employee on a given date.
    Returns: (success: bool, message: str, attendance: Attendance | None)
    """
    employee = Employee.query.filter_by(employee_id=employee_id, is_active=True).first()
    if not employee:
        return False, f"Active employee with ID {employee_id} not found.", None

    if status not in VALID_STATUSES:
        return False, f"Invalid status '{status}'. Must be one of {VALID_STATUSES}.", None

    try:
        # Check for existing record
        existing = Attendance.query.filter_by(
            employee_id=employee_id, attendance_date=attendance_date
        ).first()

        if existing:
            existing.status = status
            db.session.commit()
            return True, f"Attendance updated to '{status}' for {employee.employee_name} on {attendance_date}.", existing

        # Create new record
        new_record = Attendance(
            employee_id=employee_id,
            attendance_date=attendance_date,
            status=status
        )
        db.session.add(new_record)
        db.session.commit()
        return True, f"Attendance recorded as '{status}' for {employee.employee_name} on {attendance_date}.", new_record

    except IntegrityError as ie:
        db.session.rollback()
        return False, f"Integrity error: Duplicate record or constraint violation on {attendance_date}.", None
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}", None


def record_daily_roster(attendance_date: date, records: list[dict]) -> tuple[bool, str, int]:
    """
    Atomically saves daily attendance for a batch of employees on attendance_date.
    records: list of dicts with {"employee_id": int, "status": str}
    
    Returns: (success: bool, message: str, count: int)
    """
    if not records:
        return False, "No employee records submitted.", 0

    # Ensure all statuses are valid
    for r in records:
        if r.get("status") not in VALID_STATUSES:
            return False, f"Invalid status '{r.get('status')}'. Allowed: {VALID_STATUSES}", 0

    emp_ids = [r["employee_id"] for r in records]
    if len(set(emp_ids)) != len(emp_ids):
        return False, "Duplicate employee IDs in submission batch.", 0

    try:
        updated_or_created = 0
        for r in records:
            emp_id = r["employee_id"]
            stat = r["status"]

            existing = Attendance.query.filter_by(
                employee_id=emp_id, attendance_date=attendance_date
            ).first()

            if existing:
                existing.status = stat
            else:
                new_rec = Attendance(
                    employee_id=emp_id,
                    attendance_date=attendance_date,
                    status=stat
                )
                db.session.add(new_rec)
            updated_or_created += 1

        db.session.commit()
        return True, f"Successfully recorded attendance for {updated_or_created} employees on {attendance_date}.", updated_or_created

    except Exception as e:
        db.session.rollback()
        return False, f"Transaction error while saving roster: {str(e)}", 0


def delete_attendance(attendance_id: int) -> tuple[bool, str]:
    """Deletes an attendance log entry."""
    rec = Attendance.query.get(attendance_id)
    if not rec:
        return False, "Attendance record not found."
    try:
        db.session.delete(rec)
        db.session.commit()
        return True, "Attendance record deleted."
    except Exception as e:
        db.session.rollback()
        return False, f"Failed to delete record: {str(e)}"
