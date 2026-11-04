"""
app/routes/reports.py — Multi-Format Reporting, Analysis & Chart Generation Routes.
Supports CSV, Excel (.xlsx), Executive PDF (.pdf), Structured JSON, and Print formats.
Scoped per customer/user for multi-tenant data isolation.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, make_response, flash, redirect, url_for, jsonify
from flask_login import current_user
from app.models import Employee, AppSettings
from app.services.analytics_service import (
    get_employee_attendance_summary,
    get_monthly_attendance_summary,
    get_department_attendance_summary,
    generate_all_visualizations,
    get_charts_dir
)
from app.services.report_service import (
    generate_employee_summary_csv,
    generate_monthly_summary_csv,
    generate_department_summary_csv,
    generate_excel_report,
    generate_pdf_report,
)

reports_bp = Blueprint("reports", __name__)


def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@reports_bp.route("")
@reports_bp.route("/")
def index():
    user_id = current_user.id if current_user.is_authenticated else None
    report_type = request.args.get("type", "employee")
    dept = request.args.get("department", "").strip()
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    settings = AppSettings.get_settings(user_id=user_id)
    threshold = settings.attendance_threshold

    dept_q = Employee.query.with_entities(Employee.department).distinct()
    if user_id is not None:
        dept_q = dept_q.filter(Employee.user_id == user_id)
    departments = sorted(set(e.department for e in dept_q.all() if e.department))

    employee_rows = []
    monthly_rows = []
    department_rows = []

    if report_type == "employee":
        employee_rows = get_employee_attendance_summary(
            department=dept, start_date=date_from, end_date=date_to, threshold=threshold, user_id=user_id
        )
    elif report_type == "monthly":
        monthly_rows = get_monthly_attendance_summary(user_id=user_id)
    elif report_type == "department":
        department_rows = get_department_attendance_summary(user_id=user_id)

    return render_template(
        "reports/index.html",
        report_type=report_type,
        departments=departments,
        dept=dept,
        date_from=request.args.get("date_from", ""),
        date_to=request.args.get("date_to", ""),
        employee_rows=employee_rows,
        monthly_rows=monthly_rows,
        department_rows=department_rows,
        threshold=threshold,
    )


@reports_bp.route("/charts")
def view_charts():
    charts_dir = get_charts_dir()
    charts_exist = (
        (charts_dir / "monthly_attendance_summary.png").exists() and
        (charts_dir / "department_absenteeism_comparison.png").exists() and
        (charts_dir / "employee_attendance_percentage.png").exists()
    )

    return render_template("reports/charts.html", charts_exist=charts_exist)


@reports_bp.route("/charts/generate", methods=["POST"])
def generate_charts_action():
    user_id = current_user.id if current_user.is_authenticated else None
    settings = AppSettings.get_settings(user_id=user_id)
    try:
        generate_all_visualizations(user_id=user_id, threshold=settings.attendance_threshold)
        flash("Successfully generated all 3 Matplotlib analytics charts!", "success")
    except Exception as e:
        flash(f"Failed to generate charts: {str(e)}", "error")
    return redirect(url_for("reports.view_charts"))


# ==========================================================
# MULTI-FORMAT EXPORT ROUTES
# ==========================================================

@reports_bp.route("/export/csv")
@reports_bp.route("/export-csv")
def export_csv():
    """Format 1: Standard Comma-Separated Values (CSV)."""
    user_id = current_user.id if current_user.is_authenticated else None
    report_type = request.args.get("type", "employee")
    dept = request.args.get("department", "").strip()
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    if report_type == "monthly":
        csv_bytes = generate_monthly_summary_csv(user_id=user_id)
        filename = "monthly_attendance_report.csv"
    elif report_type == "department":
        csv_bytes = generate_department_summary_csv(user_id=user_id)
        filename = "department_attendance_summary.csv"
    else:
        csv_bytes = generate_employee_summary_csv(department=dept, start_date=date_from, end_date=date_to, user_id=user_id)
        filename = "employee_attendance_report.csv"

    response = make_response(csv_bytes)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@reports_bp.route("/export/excel")
@reports_bp.route("/export-excel")
def export_excel():
    """Format 2: Styled Microsoft Excel Spreadsheet (.xlsx)."""
    user_id = current_user.id if current_user.is_authenticated else None
    report_type = request.args.get("type", "employee")
    dept = request.args.get("department", "").strip()
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    excel_bytes = generate_excel_report(
        report_type=report_type,
        department=dept,
        start_date=date_from,
        end_date=date_to,
        user_id=user_id
    )
    filename = f"{report_type}_attendance_report.xlsx"

    response = make_response(excel_bytes)
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@reports_bp.route("/export/pdf")
@reports_bp.route("/export-pdf")
def export_pdf():
    """Format 3: Executive PDF Audit Document (.pdf) via ReportLab."""
    user_id = current_user.id if current_user.is_authenticated else None
    report_type = request.args.get("type", "employee")
    dept = request.args.get("department", "").strip()
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    pdf_bytes = generate_pdf_report(
        report_type=report_type,
        department=dept,
        start_date=date_from,
        end_date=date_to,
        user_id=user_id
    )
    filename = f"{report_type}_attendance_report.pdf"

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@reports_bp.route("/export/json")
@reports_bp.route("/export-json")
def export_json():
    """Format 4: Structured JSON Data Export (.json)."""
    user_id = current_user.id if current_user.is_authenticated else None
    report_type = request.args.get("type", "employee")
    dept = request.args.get("department", "").strip()
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    settings = AppSettings.get_settings(user_id=user_id)
    threshold = settings.attendance_threshold

    if report_type == "monthly":
        data = get_monthly_attendance_summary(user_id=user_id)
    elif report_type == "department":
        data = get_department_attendance_summary(user_id=user_id)
    else:
        data = get_employee_attendance_summary(
            department=dept, start_date=date_from, end_date=date_to, threshold=threshold, user_id=user_id
        )

    as_download = request.args.get("download", "1") == "1"
    response = jsonify({
        "institution": settings.institution_name,
        "report_type": report_type,
        "academic_year": settings.academic_year,
        "attendance_threshold": threshold,
        "generated_at": datetime.utcnow().isoformat(),
        "total_records": len(data),
        "data": data
    })
    if as_download:
        response.headers["Content-Disposition"] = f"attachment; filename={report_type}_attendance_report.json"
    return response


@reports_bp.route("/print")
def print_report():
    """Format 5: Clean, print-ready document view with automatic print preview."""
    user_id = current_user.id if current_user.is_authenticated else None
    report_type = request.args.get("type", "employee")
    dept = request.args.get("department", "").strip()
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    settings = AppSettings.get_settings(user_id=user_id)
    threshold = settings.attendance_threshold

    employee_rows = []
    monthly_rows = []
    department_rows = []

    if report_type == "employee":
        employee_rows = get_employee_attendance_summary(
            department=dept, start_date=date_from, end_date=date_to, threshold=threshold, user_id=user_id
        )
    elif report_type == "monthly":
        monthly_rows = get_monthly_attendance_summary(user_id=user_id)
    elif report_type == "department":
        department_rows = get_department_attendance_summary(user_id=user_id)

    return render_template(
        "reports/print.html",
        report_type=report_type,
        dept=dept,
        date_from=request.args.get("date_from", ""),
        date_to=request.args.get("date_to", ""),
        employee_rows=employee_rows,
        monthly_rows=monthly_rows,
        department_rows=department_rows,
        threshold=threshold,
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
    )
