"""
tests/test_attendance.py — Automated tests for attendance recording and duplicate prevention.
"""
from datetime import date
from sqlalchemy.exc import IntegrityError
import pytest
from app import db
from app.models import Attendance, Employee
from app.services.attendance_service import record_single_attendance, record_daily_roster


def test_record_single_attendance(app, sample_data):
    with app.app_context():
        e3_id = sample_data["e3_id"]
        ok, msg, rec = record_single_attendance(e3_id, date(2026, 10, 5), "Present")
        assert ok is True
        assert rec is not None
        assert rec.status == "Present"


def test_prevent_duplicate_attendance_constraint(app, sample_data):
    """
    Verifies that the database UNIQUE(employee_id, attendance_date) constraint
    actively prevents duplicate entries for the same employee and date.
    """
    with app.app_context():
        e1_id = sample_data["e1_id"]
        d = date(2026, 10, 1)

        # Attempt raw insert of a duplicate record
        dup_rec = Attendance(employee_id=e1_id, attendance_date=d, status="Absent")
        db.session.add(dup_rec)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_update_existing_attendance_on_subsequent_record(app, sample_data):
    """
    Verifies that the service updates the existing record when attendance is re-submitted
    for an employee on the same date.
    """
    with app.app_context():
        e1_id = sample_data["e1_id"]
        d = date(2026, 10, 1)

        # e1 already has Present on 2026-10-01 in sample_data
        ok, msg, rec = record_single_attendance(e1_id, d, "Leave")
        assert ok is True
        assert rec.status == "Leave"

        # Check in DB
        recs = Attendance.query.filter_by(employee_id=e1_id, attendance_date=d).all()
        assert len(recs) == 1
        assert recs[0].status == "Leave"


def test_reject_invalid_attendance_status(app, sample_data):
    with app.app_context():
        e1_id = sample_data["e1_id"]
        ok, msg, rec = record_single_attendance(e1_id, date(2026, 10, 10), "InvalidStatus")
        assert ok is False
        assert "Must be one of" in msg


def test_batch_roster_recording(app, sample_data):
    with app.app_context():
        d = date(2026, 10, 15)
        records = [
            {"employee_id": sample_data["e1_id"], "status": "Present"},
            {"employee_id": sample_data["e2_id"], "status": "Leave"},
            {"employee_id": sample_data["e3_id"], "status": "Holiday"},
        ]
        ok, msg, count = record_daily_roster(d, records)
        assert ok is True
        assert count == 3

        recs = Attendance.query.filter_by(attendance_date=d).all()
        assert len(recs) == 3
        status_map = {r.employee_id: r.status for r in recs}
        assert status_map[sample_data["e1_id"]] == "Present"
        assert status_map[sample_data["e2_id"]] == "Leave"
        assert status_map[sample_data["e3_id"]] == "Holiday"
