"""
tests/test_analytics_and_reports.py — Tests for Pandas, NumPy, and Matplotlib Pipelines.
"""
from datetime import date
from pathlib import Path
from app import db
from app.models import Employee, Attendance
from app.services.analytics_service import (
    get_employee_attendance_summary,
    get_monthly_attendance_summary,
    get_department_attendance_summary,
    generate_all_visualizations,
    get_charts_dir
)
from app.services.report_service import (
    generate_employee_summary_csv,
    generate_excel_report,
    generate_pdf_report
)


def test_employee_attendance_summary_and_threshold(app):
    with app.app_context():
        # High attendee (100%)
        e1 = Employee(employee_code="AN01", employee_name="High Attendee", department="Engineering", is_active=True)
        # Defaulter (25%)
        e2 = Employee(employee_code="AN02", employee_name="Defaulter", department="Engineering", is_active=True)
        db.session.add_all([e1, e2])
        db.session.commit()

        # 4 dates
        for i in range(4):
            d = date(2026, 10, i + 1)
            # e1 Present on all 4
            db.session.add(Attendance(employee_id=e1.employee_id, attendance_date=d, status="Present"))
            # e2 Present on 1, Absent on 3
            st = "Present" if i == 0 else "Absent"
            db.session.add(Attendance(employee_id=e2.employee_id, attendance_date=d, status=st))
        db.session.commit()

        summary = get_employee_attendance_summary(threshold=75.0)
        s_map = {item["employee_code"]: item for item in summary}

        assert s_map["AN01"]["attendance_percentage"] == 100.0
        assert s_map["AN01"]["below_threshold"] is False

        assert s_map["AN02"]["attendance_percentage"] == 25.0
        assert s_map["AN02"]["below_threshold"] is True
        assert s_map["AN02"]["absenteeism_rate"] == 75.0


def test_monthly_attendance_summary_pandas(app):
    with app.app_context():
        e1 = Employee(employee_code="MO01", employee_name="Month Test", department="Finance", is_active=True)
        db.session.add(e1)
        db.session.commit()

        # Sep record
        db.session.add(Attendance(employee_id=e1.employee_id, attendance_date=date(2026, 9, 20), status="Present"))
        # Oct record
        db.session.add(Attendance(employee_id=e1.employee_id, attendance_date=date(2026, 10, 5), status="Absent"))
        db.session.commit()

        m_summary = get_monthly_attendance_summary()
        months = [m["month"] for m in m_summary]
        assert "2026-09" in months
        assert "2026-10" in months


def test_department_attendance_summary_pandas(app):
    with app.app_context():
        e1 = Employee(employee_code="DP01", employee_name="Dept Test 1", department="HR", is_active=True)
        e2 = Employee(employee_code="DP02", employee_name="Dept Test 2", department="Sales", is_active=True)
        db.session.add_all([e1, e2])
        db.session.commit()

        d = date(2026, 10, 10)
        db.session.add(Attendance(employee_id=e1.employee_id, attendance_date=d, status="Present"))
        db.session.add(Attendance(employee_id=e2.employee_id, attendance_date=d, status="Absent"))
        db.session.commit()

        d_summary = get_department_attendance_summary()
        dept_names = [d["department"] for d in d_summary]
        assert "HR" in dept_names
        assert "Sales" in dept_names


def test_generate_all_matplotlib_charts(app):
    with app.app_context():
        e = Employee(employee_code="CH01", employee_name="Chart User", department="IT", is_active=True)
        db.session.add(e)
        db.session.commit()
        db.session.add(Attendance(employee_id=e.employee_id, attendance_date=date(2026, 10, 1), status="Present"))
        db.session.commit()

        charts = generate_all_visualizations()
        assert Path(charts["monthly_chart"]).exists()
        assert Path(charts["department_chart"]).exists()
        assert Path(charts["employee_chart"]).exists()


def test_csv_export_formatting(app):
    csv_bytes = generate_employee_summary_csv()
    csv_str = csv_bytes.decode("utf-8")
    assert "Employee Code,Employee Name,Department,Present Days,Absent Days" in csv_str


def test_excel_export_formatting(app):
    with app.app_context():
        xlsx_bytes = generate_excel_report(report_type="employee")
        assert len(xlsx_bytes) > 0
        # Check ZIP / XLSX magic header PK\x03\x04
        assert xlsx_bytes.startswith(b"PK\x03\x04")


def test_pdf_export_formatting(app):
    with app.app_context():
        pdf_bytes = generate_pdf_report(report_type="employee")
        assert len(pdf_bytes) > 0
        # Check PDF magic header %PDF
        assert pdf_bytes.startswith(b"%PDF")


def test_export_endpoints(client):
    # CSV route
    r_csv = client.get("/reports/export/csv?type=employee")
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.content_type

    # Excel route
    r_xlsx = client.get("/reports/export/excel?type=employee")
    assert r_xlsx.status_code == 200
    assert "spreadsheetml" in r_xlsx.content_type

    # PDF route
    r_pdf = client.get("/reports/export/pdf?type=employee")
    assert r_pdf.status_code == 200
    assert "application/pdf" in r_pdf.content_type

    # JSON route
    r_json = client.get("/reports/export/json?type=employee")
    assert r_json.status_code == 200
    assert "application/json" in r_json.content_type
    assert "data" in r_json.json

    # Print route
    r_print = client.get("/reports/print?type=employee")
    assert r_print.status_code == 200
    assert "window.print()" in r_print.text

