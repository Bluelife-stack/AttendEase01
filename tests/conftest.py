"""
tests/conftest.py — Pytest Fixtures for Employee Attendance Analysis System.
"""
import pytest
from datetime import date
from app import create_app, db
from app.models import Employee, Attendance, AppSettings


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        AppSettings.get_settings()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_data(app):
    """Seed test employees and attendance."""
    with app.app_context():
        e1 = Employee(employee_code="TEST01", employee_name="Alice Smith", department="Engineering", is_active=True)
        e2 = Employee(employee_code="TEST02", employee_name="Bob Jones", department="Engineering", is_active=True)
        e3 = Employee(employee_code="TEST03", employee_name="Charlie Brown", department="Marketing", is_active=True)

        db.session.add_all([e1, e2, e3])
        db.session.commit()

        # Seed 2 attendance records
        a1 = Attendance(employee_id=e1.employee_id, attendance_date=date(2026, 10, 1), status="Present")
        a2 = Attendance(employee_id=e2.employee_id, attendance_date=date(2026, 10, 1), status="Absent")
        db.session.add_all([a1, a2])
        db.session.commit()

        return {
            "e1_id": e1.employee_id,
            "e2_id": e2.employee_id,
            "e3_id": e3.employee_id,
        }
