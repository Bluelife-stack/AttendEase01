"""
app/routes/attendance.py — Attendance Recording & History Routes.
Scoped per customer/user for multi-tenant data isolation.
"""
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from app import db
from app.models import Employee, Attendance
from app.services.attendance_service import record_daily_roster, record_single_attendance, delete_attendance

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.route("/mark", methods=["GET", "POST"])
def mark_attendance():
    user_id = current_user.id if current_user.is_authenticated else None

    dept_q = Employee.query.with_entities(Employee.department).distinct()
    if user_id is not None:
        dept_q = dept_q.filter(Employee.user_id == user_id)
    departments = sorted(set(e.department for e in dept_q.all() if e.department))

    today_str = date.today().isoformat()
    selected_dept = request.args.get("department", "") or request.form.get("department", "")
    selected_date_str = request.args.get("attendance_date", "") or request.form.get("attendance_date", "") or today_str

    try:
        att_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        att_date = date.today()
        selected_date_str = att_date.isoformat()

    query = Employee.query.filter_by(is_active=True)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    if selected_dept:
        query = query.filter_by(department=selected_dept)
    employees = query.order_by(Employee.employee_code).all()

    # Fetch existing attendance on that date to prefill radio buttons
    exist_q = Attendance.query.join(Employee).filter(Attendance.attendance_date == att_date)
    if user_id is not None:
        exist_q = exist_q.filter(Employee.user_id == user_id)
    existing_records = {r.employee_id: r.status for r in exist_q.all()}

    if request.method == "POST":
        records = []
        for emp in employees:
            status_val = request.form.get(f"status_{emp.employee_id}", "Present")
            if status_val not in Attendance.VALID_STATUSES:
                status_val = "Present"
            records.append({
                "employee_id": emp.employee_id,
                "status": status_val
            })

        ok, msg, count = record_daily_roster(att_date, records)
        if ok:
            flash(msg, "success")
            return redirect(url_for("attendance.history", date_from=selected_date_str, date_to=selected_date_str))
        else:
            flash(msg, "error")

    return render_template(
        "attendance/mark.html",
        departments=departments,
        selected_dept=selected_dept,
        selected_date=selected_date_str,
        employees=employees,
        existing_records=existing_records,
    )


@attendance_bp.route("/history")
def history():
    user_id = current_user.id if current_user.is_authenticated else None
    dept_filter = request.args.get("department", "").strip()
    status_filter = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = request.args.get("page", 1, type=int)

    query = Attendance.query.join(Employee)
    if user_id is not None:
        query = query.filter(Employee.user_id == user_id)

    if dept_filter:
        query = query.filter(Employee.department == dept_filter)
    if status_filter:
        query = query.filter(Attendance.status == status_filter)
    if date_from:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(Attendance.attendance_date >= d_from)
        except ValueError:
            pass
    if date_to:
        try:
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(Attendance.attendance_date <= d_to)
        except ValueError:
            pass

    pagination = query.order_by(
        Attendance.attendance_date.desc(), Employee.employee_code.asc()
    ).paginate(page=page, per_page=25, error_out=False)

    dept_q = Employee.query.with_entities(Employee.department).distinct()
    if user_id is not None:
        dept_q = dept_q.filter(Employee.user_id == user_id)
    departments = sorted(set(e.department for e in dept_q.all() if e.department))

    return render_template(
        "attendance/history.html",
        pagination=pagination,
        records=pagination.items,
        departments=departments,
        dept_filter=dept_filter,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


@attendance_bp.route("/<int:attendance_id>/edit", methods=["GET", "POST"])
def edit_record(attendance_id):
    user_id = current_user.id if current_user.is_authenticated else None
    rec = Attendance.query.get_or_404(attendance_id)
    if user_id is not None and rec.employee.user_id is not None and rec.employee.user_id != user_id:
        abort(404)

    if request.method == "POST":
        new_status = request.form.get("status", rec.status)
        if new_status in Attendance.VALID_STATUSES:
            rec.status = new_status
            db.session.commit()
            flash(f"Updated attendance for {rec.employee.employee_name} on {rec.attendance_date} to {new_status}.", "success")
            return redirect(url_for("attendance.history"))
        else:
            flash(f"Invalid status '{new_status}'.", "error")

    return render_template("attendance/edit.html", record=rec)


@attendance_bp.route("/<int:attendance_id>/delete", methods=["POST"])
def delete_record(attendance_id):
    user_id = current_user.id if current_user.is_authenticated else None
    rec = Attendance.query.get_or_404(attendance_id)
    if user_id is not None and rec.employee.user_id is not None and rec.employee.user_id != user_id:
        abort(404)

    ok, msg = delete_attendance(attendance_id)
    if ok:
        flash(msg, "warning")
    else:
        flash(msg, "error")
    return redirect(url_for("attendance.history"))
