"""Tests for intelligent, review-before-save faculty roster imports."""
from io import BytesIO
from datetime import date

import pandas as pd
import pytest
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from werkzeug.datastructures import FileStorage

from app import db
from app.models import Attendance, Department, Employee, User
from app.routes.employees import (
    _match_department,
    _normalize_pdf_preview,
    _prepare_import_frame,
    _read_import_file,
)


def _register_import_user(client, app):
    response = client.post("/auth/register", data={
        "full_name": "Import Coordinator",
        "username": "import_coordinator",
        "email": "import.coordinator@example.edu",
        "role": "Faculty Coordinator",
        "password": "ImportPassword123",
        "confirm_password": "ImportPassword123",
    })
    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(username="import_coordinator").one()
        db.session.add_all([
            Department(user_id=user.id, name="Computer Science", code="CSE"),
            Department(user_id=user.id, name="Mathematics", code="MATH"),
        ])
        db.session.commit()


def test_header_detection_skips_preamble_and_matches_aliases():
    frame = pd.DataFrame([
        ["Mohan Babu University Faculty Roster", "", "", ""],
        ["Faculty ID No.", "Faculty Member Name", "School", "Email ID"],
        ["FAC-2", "Zara Rao", "Computer Science", "zara@example.edu"],
    ])

    prepared, mapping = _prepare_import_frame(frame)

    assert prepared.attrs["source_header_row"] == 1
    assert prepared.attrs["detected_columns"]["employee_code"]["confidence"] == "high"
    assert mapping == {
        "employee_code": "Faculty ID No.",
        "employee_name": "Faculty Member Name",
        "department": "School",
        "email": "Email ID",
    }
    assert prepared.iloc[0][mapping["employee_code"]] == "FAC-2"


def test_header_detection_rejects_files_without_any_confident_field():
    frame = pd.DataFrame([
        ["Faculty ID", "Employee ID", "Unrecognized"],
        ["FAC-1", "EMP-1", "Asha Rao"],
    ])

    with pytest.raises(ValueError, match="Could not confidently identify any faculty fields"):
        _prepare_import_frame(frame)


def test_pdf_import_joins_wrapped_words_in_table_cells():
    pdf_buffer = BytesIO()
    cell_style = ParagraphStyle("import-cell", fontName="Helvetica", fontSize=8, leading=9)
    source_rows = [
        ["Faculty ID", "Faculty Name", "Department", "Designation", "Email", "Phone"],
        ["FAC-01", "Asha Rao", "Computer<br/>Science", "Assistant<br/>Professor", "asha@example.edu", "900000000<br/>1"],
        ["FAC-02", "Ravi Kumar", "Electronics<br/>and Commu<br/>nication", "Associate<br/>Professor", "ravi@example.edu", "900000000<br/>2"],
        ["FAC-03", "Mina Das", "Mechanical<br/>Engineeri<br/>ng", "Assistant<br/>Professor", "mina@example.edu", "900000000<br/>3"],
    ]
    table_rows = [
        [Paragraph(value, cell_style) for value in row]
        for row in source_rows
    ]
    table = Table(table_rows, colWidths=[55, 75, 75, 70, 100, 65], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    SimpleDocTemplate(pdf_buffer, pagesize=letter).build([table])

    pdf_buffer.seek(0)
    frame, mapping = _read_import_file(FileStorage(
        stream=pdf_buffer,
        filename="wrapped-faculty.pdf",
    ))

    assert frame.iloc[0][mapping["department"]] == "Computer Science"
    assert frame.iloc[1][mapping["department"]] == "Electronics and Communication"
    assert frame.iloc[2][mapping["department"]] == "Mechanical Engineering"
    assert frame.iloc[0][mapping["designation"]] == "Assistant Professor"
    assert frame.iloc[0][mapping["phone"]] == "9000000001"
    assert frame.attrs["detected_columns"]["department"]["confidence"] == "high"


def test_saved_pdf_preview_normalizes_split_fields():
    preview = {
        "filename": "faculty.pdf",
        "detected_columns": {
            "department": {"column": "Departm\nent", "confidence": "review"},
        },
        "rows": [{
            "department": "Compute\nr Science",
            "department_source": "Compute\nr Science",
        }],
    }

    normalized = _normalize_pdf_preview(preview)

    assert normalized["detected_columns"]["department"]["column"] == "Department"
    assert normalized["rows"][0]["department"] == "Computer Science"
    assert normalized["rows"][0]["department_source"] == "Computer Science"


def test_department_code_matches_long_department_name_by_initials():
    department = Department(
        name="Department of Computer Science and Engineering",
        code="CSE",
    )

    match, reason = _match_department("C.S.E.", [department])

    assert match is department
    assert reason == "Exact name/code match"
    match, reason = _match_department("Computer Sci. Engg.", [department])
    assert match is department
    assert reason == "Exact name/code match"


def test_import_preview_sorts_rows_and_confirm_saves_only_after_review(client, app):
    _register_import_user(client, app)
    roster = (
        "Mohan Babu University Faculty Roster,,,,\n"
        "Faculty ID No.,Faculty Member Name,School,Email ID,Contact Number\n"
        "FAC-2,Zara Rao,Computer Science,zara@example.edu,9000000002\n"
        "FAC-1,Asha Rao,Computer Science,asha@example.edu,9000000001\n"
    )
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(roster.encode("utf-8")), "faculty.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Detected 2 faculty records: 2 ready and 0 with data-integrity errors" in response.data
    assert b"Employee Code from Faculty ID No." in response.data
    assert response.data.index(b"Asha Rao") < response.data.index(b"Zara Rao")
    assert b"<td>3</td>" in response.data
    with app.app_context():
        assert Employee.query.count() == 0

    response = client.post("/employees/import/confirm", data={})

    assert response.status_code == 302
    with app.app_context():
        employees = Employee.query.order_by(Employee.employee_code).all()
        assert [employee.employee_code for employee in employees] == ["FAC-1", "FAC-2"]
        assert [employee.employee_name for employee in employees] == ["Asha Rao", "Zara Rao"]
        assert all(employee.department == "Computer Science" for employee in employees)


def test_excel_import_keeps_all_available_fields(client, app):
    _register_import_user(client, app)
    workbook = BytesIO()
    pd.DataFrame([{
        "Faculty ID": "XLS-1",
        "Faculty Name": "Meera Shah",
        "Department": "Computer Science",
        "Designation": "Lecturer",
        "Email": "meera@example.edu",
        "Phone": "9000000011",
    }]).to_excel(workbook, index=False)
    workbook.seek(0)

    response = client.post(
        "/employees/import",
        data={"file": (workbook, "faculty.xlsx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Meera Shah" in response.data
    assert client.post("/employees/import/confirm", data={}).status_code == 302
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="XLS-1").one()
        assert employee.employee_name == "Meera Shah"
        assert employee.department == "Computer Science"
        assert employee.designation == "Lecturer"
        assert employee.email == "meera@example.edu"
        assert employee.phone == "9000000011"


def test_import_accepts_missing_email_phone_and_unmatched_department(client, app):
    _register_import_user(client, app)
    roster = (
        "Faculty ID,Faculty Name,Department,Designation,Email,Phone\n"
        "FAC-NEW,Initial Name,New Bio Sciences,,,\n"
    )
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(roster.encode("utf-8")), "faculty.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"1 record(s) have non-blocking missing-information warnings" in response.data
    assert b"Approve adding this department" not in response.data
    with app.app_context():
        assert Employee.query.count() == 0
        assert Department.query.count() == 2

    response = client.post("/employees/import/confirm", data={})

    assert response.status_code == 302
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="FAC-NEW").one()
        assert employee.employee_name == "Initial Name"
        assert employee.department is None
        assert employee.email is None
        assert employee.designation is None
        assert employee.phone is None
        assert Department.query.count() == 2


def test_import_accepts_name_and_available_details_without_id_or_department(client, app):
    _register_import_user(client, app)
    roster = (
        "Faculty Name,Designation,Phone\n"
        "Asha Rao,Assistant Professor,9000000001\n"
    )
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(roster.encode("utf-8")), "faculty.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Detected 1 faculty records" in response.data
    assert b"Faculty ID is missing" in response.data
    assert b"Department is missing" in response.data
    response = client.post("/employees/import/confirm", data={})

    assert response.status_code == 302
    with app.app_context():
        employee = Employee.query.filter_by(employee_name="Asha Rao").one()
        assert employee.employee_code is None
        assert employee.department is None
        assert employee.designation == "Assistant Professor"
        assert employee.phone == "9000000001"
        assert employee.email is None


def test_import_skips_entirely_empty_rows_and_reports_warning(client, app):
    _register_import_user(client, app)
    roster = (
        "Faculty ID,Faculty Name,Department,Designation,Email,Phone\n"
        ",,,,,\n"
        "FAC-1,Asha Rao,,,,\n"
    )
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(roster.encode("utf-8")), "faculty.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"1 entirely empty row" in response.data
    assert b"Detected 1 faculty records" in response.data
    response = client.post("/employees/import/confirm", data={})
    assert response.status_code == 302
    with app.app_context():
        assert Employee.query.count() == 1
        assert Employee.query.one().employee_name == "Asha Rao"


def test_imported_incomplete_faculty_can_be_completed_later_and_take_attendance(client, app):
    _register_import_user(client, app)
    roster = "Faculty Name,Phone\nRavi Kumar,9000000002\n"
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(roster.encode("utf-8")), "faculty.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert client.post("/employees/import/confirm", data={}).status_code == 302

    with app.app_context():
        employee = Employee.query.filter_by(employee_name="Ravi Kumar").one()
        employee_id = employee.employee_id

    edit_response = client.post(f"/employees/{employee_id}/edit", data={
        "employee_code": "FAC-RK",
        "employee_name": "Ravi Kumar",
        "department": "Computer Science",
        "designation": "Professor",
        "email": "ravi@example.edu",
        "phone": "9000000002",
    })
    assert edit_response.status_code == 302
    with app.app_context():
        employee = db.session.get(Employee, employee_id)
        assert employee.employee_code == "FAC-RK"
        assert employee.department == "Computer Science"
        assert employee.email == "ravi@example.edu"
        assert employee.designation == "Professor"
        from app.services.attendance_service import record_single_attendance
        ok, _, record = record_single_attendance(employee_id, date(2026, 11, 4), "Present")
        assert ok is True
        assert record.employee_id == employee_id


def test_department_management_remains_available(client, app):
    _register_import_user(client, app)
    response = client.post("/employees/departments", data={
        "name": "Biotechnology",
        "code": "BIO",
        "description": "Life sciences",
    })
    assert response.status_code == 302
    with app.app_context():
        department = Department.query.filter_by(name="Biotechnology").one()
        assert department.code == "BIO"
        assert department.is_active is True


def test_incomplete_faculty_remains_supported_by_analytics_and_exports(client, app):
    _register_import_user(client, app)
    with app.app_context():
        user = User.query.filter_by(username="import_coordinator").one()
        db.session.add_all([
            Employee(user_id=user.id, employee_name="Name Only"),
            Employee(user_id=user.id, employee_code="FAC-2", employee_name="Complete Faculty"),
        ])
        db.session.commit()

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert b"Unassigned" in dashboard_response.data

    for path in (
        "/reports/",
        "/reports/export/csv?type=employee",
        "/reports/export/excel?type=employee",
        "/reports/export/pdf?type=employee",
        "/reports/export/json?type=employee&download=0",
        "/reports/print?type=employee",
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_import_keeps_existing_duplicate_id_approval(client, app):
    _register_import_user(client, app)
    with app.app_context():
        user = User.query.filter_by(username="import_coordinator").one()
        db.session.add(Employee(
            user_id=user.id,
            employee_code="FAC-DUP",
            employee_name="Existing Faculty",
        ))
        db.session.commit()
    roster = "Faculty ID,Faculty Name\nFAC-DUP,Updated Name\n"
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(roster.encode("utf-8")), "faculty.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Approve updating existing profile" in response.data

    response = client.post("/employees/import/confirm", data={})
    assert response.status_code == 200
    with app.app_context():
        assert Employee.query.filter_by(employee_code="FAC-DUP").one().employee_name == "Existing Faculty"


def test_import_explains_empty_department_directory(client, app):
    _register_import_user(client, app)
    with app.app_context():
        Department.query.delete()
        db.session.commit()

    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(b"Faculty ID,Faculty Name,Department\nFAC-1,Asha Rao,Computer Science\n"), "faculty.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"No departments are in your directory yet" in response.data


def test_existing_profile_update_requires_approval_and_preserves_attendance(client, app):
    _register_import_user(client, app)
    with app.app_context():
        user = User.query.filter_by(username="import_coordinator").one()
        employee = Employee(
            user_id=user.id,
            employee_code="FAC-EXIST",
            employee_name="Original Faculty",
            department="Computer Science",
        )
        db.session.add(employee)
        db.session.flush()
        employee_id = employee.employee_id
        db.session.add(Attendance(
            employee_id=employee_id,
            attendance_date=date(2026, 10, 1),
            status="Present",
        ))
        db.session.commit()

    roster = "Faculty ID,Faculty Name,Department\nFAC-EXIST,Updated Faculty,CSE\n"
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(roster.encode("utf-8")), "faculty.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Approve updating existing profile" in response.data
    update = {
        "employee_code_0": "FAC-EXIST",
        "employee_name_0": "Updated Faculty",
        "department_0": "CSE",
        "email_0": "",
        "designation_0": "Faculty Member",
        "phone_0": "",
        "department_code_0": "",
    }

    response = client.post("/employees/import/confirm", data=update)
    assert response.status_code == 200
    with app.app_context():
        employee = db.session.get(Employee, employee_id)
        assert employee.employee_name == "Original Faculty"
        assert Attendance.query.filter_by(employee_id=employee_id).count() == 1

    update["update_existing_0"] = "1"
    response = client.post("/employees/import/confirm", data=update)

    assert response.status_code == 302
    with app.app_context():
        employee = db.session.get(Employee, employee_id)
        attendance = Attendance.query.filter_by(employee_id=employee_id).one()
        assert employee.employee_name == "Updated Faculty"
        assert employee.department == "Computer Science"
        assert attendance.status == "Present"
        assert attendance.attendance_date == date(2026, 10, 1)


def test_import_without_confident_headers_reports_action(client, app):
    _register_import_user(client, app)
    response = client.post(
        "/employees/import",
        data={"file": (BytesIO(b"no,recognizable,roster,headers\n1,2,3,4\n"), "bad.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Could not confidently identify any faculty fields" in response.data
