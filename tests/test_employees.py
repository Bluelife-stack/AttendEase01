"""
tests/test_employees.py — Automated tests for employee management.
"""
from app import db
from app.models import Department, Employee, Attendance
from datetime import date


def test_add_valid_employee(client, app):
    with app.app_context():
        db.session.add(Department(name="Finance", code="FIN"))
        db.session.commit()
    res = client.post("/employees/add", data={
        "employee_code": "EMP999",
        "employee_name": "Test Employee",
        "department": "Finance"
    }, follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        emp = Employee.query.filter_by(employee_code="EMP999").first()
        assert emp is not None
        assert emp.employee_name == "Test Employee"
        assert emp.department == "Finance"


def test_reject_duplicate_employee_code(client, sample_data, app):
    # TEST01 already exists
    res = client.post("/employees/add", data={
        "employee_code": "TEST01",
        "employee_name": "Duplicate Person",
        "department": "Engineering"
    }, follow_redirects=True)
    assert b"already registered" in res.data


def test_employee_create_requires_some_information_but_fields_are_optional(client, app):
    res = client.post("/employees/add", data={
        "employee_code": "",
        "employee_name": "",
        "department": ""
    }, follow_redirects=True)
    assert b"Enter at least one faculty detail" in res.data
    with app.app_context():
        assert Employee.query.count() == 0


def test_employee_can_be_created_with_only_name(client, app):
    res = client.post("/employees/add", data={
        "employee_code": "",
        "employee_name": "Asha Rao",
        "department": "",
        "designation": "",
        "email": "",
        "phone": "",
    })
    assert res.status_code == 302
    with app.app_context():
        employee = Employee.query.filter_by(employee_name="Asha Rao").one()
        assert employee.employee_code is None
        assert employee.department is None
        assert employee.designation is None


def test_edit_employee(client, sample_data, app):
    e1_id = sample_data["e1_id"]
    with app.app_context():
        db.session.add(Department(name="Research & Development", code="RND"))
        db.session.commit()
    res = client.post(f"/employees/{e1_id}/edit", data={
        "employee_code": "TEST01",
        "employee_name": "Alice Smith Updated",
        "department": "Research & Development"
    }, follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        emp = db.session.get(Employee, e1_id)
        assert emp.employee_name == "Alice Smith Updated"
        assert emp.department == "Research & Development"


def test_edit_employee_can_save_optional_fields_as_null(client, sample_data, app):
    e1_id = sample_data["e1_id"]
    response = client.post(f"/employees/{e1_id}/edit", data={
        "employee_code": "",
        "employee_name": "Alice Smith",
        "department": "",
        "designation": "",
        "email": "",
        "phone": "",
    })
    assert response.status_code == 302
    with app.app_context():
        employee = db.session.get(Employee, e1_id)
        assert employee.employee_code is None
        assert employee.department is None
        assert employee.designation is None


def test_soft_deactivation_preserves_attendance(client, sample_data, app):
    e1_id = sample_data["e1_id"]
    res = client.post(f"/employees/{e1_id}/deactivate", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        emp = db.session.get(Employee, e1_id)
        assert emp.is_active is False
        # Historical attendance records remain intact
        recs = Attendance.query.filter_by(employee_id=e1_id).all()
        assert len(recs) == 1
        assert recs[0].status == "Present"
