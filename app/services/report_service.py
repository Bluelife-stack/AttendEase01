"""
app/services/report_service.py — Multi-Format Professional Report Generation.
Supports:
  1. CSV Export (.csv)
  2. Microsoft Excel Styled Workbook (.xlsx)
  3. Executive PDF Document with Institutional Letterhead (.pdf)
  4. Structured JSON Export (.json)
"""
import csv
import io
from datetime import datetime, date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models import Student, Subject, AttendanceSession, AppSettings
from app.services.analytics_service import (
    get_employee_attendance_summary,
    get_monthly_attendance_summary,
    get_department_attendance_summary,
)


def student_detail_report(student_id: int) -> dict:
    """Return a safe empty summary for legacy student-detail views."""
    student = Student.query.get(student_id)
    if student is None:
        return {
            "student": None,
            "detail": [],
            "total_sessions": 0,
            "total_present": 0,
            "overall_pct": None,
        }

    return {
        "student": student,
        "detail": [],
        "total_sessions": AttendanceSession.query.count() if AttendanceSession.query else 0,
        "total_present": 0,
        "overall_pct": None,
    }


def subject_detail_report(subject_id: int) -> dict:
    """Return a safe empty summary for legacy subject-detail views."""
    subject = Subject.query.get(subject_id)
    if subject is None:
        return {"subject": None, "sessions": [], "total_sessions": 0}

    sessions = AttendanceSession.query.filter_by(subject_id=subject_id).order_by(AttendanceSession.session_date.desc()).all()
    return {
        "subject": subject,
        "sessions": sessions,
        "total_sessions": len(sessions),
    }


# ==========================================================
# 1. CSV EXPORT IMPLEMENTATION
# ==========================================================

def generate_employee_summary_csv(department: str = None, start_date=None, end_date=None, user_id: int = None) -> bytes:
    """Generates standard CSV export for Employee Attendance Summary."""
    rows = get_employee_attendance_summary(department=department, start_date=start_date, end_date=end_date, user_id=user_id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Employee Code", "Employee Name", "Department",
        "Present Days", "Absent Days", "Leave Days", "Holiday Days",
        "Total Working Days", "Total Recorded Days",
        "Attendance %", "Absenteeism Rate %", "Compliance Status"
    ])

    for r in rows:
        writer.writerow([
            r["employee_code"],
            r["employee_name"],
            r["department"],
            r["present_count"],
            r["absent_count"],
            r["leave_count"],
            r["holiday_count"],
            r["total_working_days"],
            r["total_recorded_days"],
            f"{r['attendance_percentage']}%",
            f"{r['absenteeism_rate']}%",
            r["status_compliance"],
        ])

    return output.getvalue().encode("utf-8")


def generate_monthly_summary_csv(user_id: int = None) -> bytes:
    """Generates CSV export for Monthly Attendance Summary."""
    rows = get_monthly_attendance_summary(user_id=user_id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Month (Year-Month)", "Present Days", "Absent Days", "Leave Days", "Holiday Days",
        "Total Working Days", "Total Recorded Days", "Attendance %", "Absenteeism Rate %"
    ])

    for r in rows:
        writer.writerow([
            r["month"],
            r["present_count"],
            r["absent_count"],
            r["leave_count"],
            r["holiday_count"],
            r["total_working_days"],
            r["total_recorded_days"],
            f"{r['attendance_percentage']}%",
            f"{r['absenteeism_rate']}%",
        ])

    return output.getvalue().encode("utf-8")


def generate_department_summary_csv(user_id: int = None) -> bytes:
    """Generates CSV export for Department Attendance Summary."""
    rows = get_department_attendance_summary(user_id=user_id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Department", "Total Employees", "Present Days", "Absent Days", "Leave Days", "Holiday Days",
        "Total Working Days", "Total Recorded Days", "Attendance %", "Absenteeism Rate %"
    ])

    for r in rows:
        writer.writerow([
            r["department"],
            r["total_employees"],
            r["present_count"],
            r["absent_count"],
            r["leave_count"],
            r["holiday_count"],
            r["total_working_days"],
            r["total_recorded_days"],
            f"{r['attendance_percentage']}%",
            f"{r['absenteeism_rate']}%",
        ])

    return output.getvalue().encode("utf-8")


# ==========================================================
# 2. MICROSOFT EXCEL (.XLSX) STYLED WORKBOOK GENERATION
# ==========================================================

def generate_excel_report(report_type: str = "employee", department: str = None, start_date=None, end_date=None, user_id: int = None) -> bytes:
    """
    Generates a professionally styled Microsoft Excel spreadsheet (.xlsx).
    Includes institutional branding banner, metadata summary, formatted tables,
    and threshold alert color-coding.
    """
    wb = openpyxl.Workbook()
    ws = wb.active

    settings = AppSettings.get_settings(user_id=user_id)
    institution_name = settings.institution_name if settings else "Mohan Babu University (MBU)"
    threshold = settings.attendance_threshold if settings else 75.0
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")

    # Styling Palettes (Professional Academic Ink / Navy)
    title_font = Font(name="Calibri", size=16, bold=True, color="101B2B")
    subtitle_font = Font(name="Calibri", size=10, italic=True, color="697586")
    meta_font = Font(name="Calibri", size=10, color="202B38")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10, color="202B38")
    bold_data_font = Font(name="Calibri", size=10, bold=True, color="202B38")
    alert_font = Font(name="Calibri", size=10, bold=True, color="991B1B")

    header_fill = PatternFill(start_color="17263C", end_color="17263C", fill_type="solid")
    meta_fill = PatternFill(start_color="F0F4F8", end_color="F0F4F8", fill_type="solid")
    alert_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    alt_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="E2E6E8"),
        right=Side(style="thin", color="E2E6E8"),
        top=Side(style="thin", color="E2E6E8"),
        bottom=Side(style="thin", color="E2E6E8"),
    )

    # 1. Organization Header Block
    ws.merge_cells("A1:G1")
    ws["A1"] = institution_name
    ws["A1"].font = title_font

    ws.merge_cells("A2:G2")
    ws["A2"] = f"Official Attendance Analysis & Compliance Audit Report — Generated: {now_str}"
    ws["A2"].font = subtitle_font

    # 2. Metadata Box
    ws["A4"] = "Report Type:"
    ws["B4"] = report_type.capitalize() + " Summary"
    ws["A5"] = "Attendance Benchmark:"
    ws["B5"] = f"{threshold}% Minimum Compliance"
    ws["A4"].font = bold_data_font
    ws["B4"].font = data_font
    ws["A5"].font = bold_data_font
    ws["B5"].font = data_font

    start_row = 7

    # 3. Data Tables based on Report Type
    if report_type == "monthly":
        ws.title = "Monthly Summary"
        headers = [
            "Month (Year-Month)", "Present Days", "Absent Days", "Leave Days",
            "Institutional Holidays", "Total Working Days", "Total Recorded Days",
            "Attendance %", "Absenteeism Rate %"
        ]
        rows_data = get_monthly_attendance_summary(user_id=user_id)
        
        # Write headers
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=start_row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for r_idx, r in enumerate(rows_data, start_row + 1):
            values = [
                r["month"], r["present_count"], r["absent_count"], r["leave_count"],
                r["holiday_count"], r["total_working_days"], r["total_recorded_days"],
                f"{r['attendance_percentage']}%", f"{r['absenteeism_rate']}%"
            ]
            fill = alt_fill if r_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(values, 1):
                c = ws.cell(row=r_idx, column=col_idx, value=val)
                c.font = data_font
                c.fill = fill
                c.border = thin_border
                c.alignment = Alignment(horizontal="center" if col_idx > 1 else "left")

    elif report_type == "department":
        ws.title = "Department Summary"
        headers = [
            "Department / School", "Total Personnel", "Present Days", "Absent Days",
            "Leave Days", "Holidays", "Total Working Days", "Attendance %", "Absenteeism Rate %"
        ]
        rows_data = get_department_attendance_summary(user_id=user_id)
        
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=start_row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for r_idx, r in enumerate(rows_data, start_row + 1):
            values = [
                r["department"], r["total_employees"], r["present_count"], r["absent_count"],
                r["leave_count"], r["holiday_count"], r["total_working_days"],
                f"{r['attendance_percentage']}%", f"{r['absenteeism_rate']}%"
            ]
            fill = alt_fill if r_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(values, 1):
                c = ws.cell(row=r_idx, column=col_idx, value=val)
                c.font = data_font
                c.fill = fill
                c.border = thin_border
                c.alignment = Alignment(horizontal="center" if col_idx > 1 else "left")

    else:
        # Default: Employee-level report
        ws.title = "Personnel Roster Summary"
        headers = [
            "Personnel Code", "Full Name", "Department / School",
            "Present", "Absent", "Leave", "Holidays",
            "Working Days", "Attendance %", "Absenteeism %", "Compliance Status"
        ]
        rows_data = get_employee_attendance_summary(
            department=department, start_date=start_date, end_date=end_date, threshold=threshold, user_id=user_id
        )

        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=start_row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for r_idx, r in enumerate(rows_data, start_row + 1):
            is_defaulter = r["below_threshold"]
            values = [
                r["employee_code"], r["employee_name"], r["department"],
                r["present_count"], r["absent_count"], r["leave_count"], r["holiday_count"],
                r["total_working_days"], f"{r['attendance_percentage']}%",
                f"{r['absenteeism_rate']}%", r["status_compliance"]
            ]
            
            row_fill = alert_fill if is_defaulter else (alt_fill if r_idx % 2 == 0 else PatternFill(fill_type=None))
            row_font = alert_font if is_defaulter else data_font

            for col_idx, val in enumerate(values, 1):
                c = ws.cell(row=r_idx, column=col_idx, value=val)
                c.font = row_font
                c.fill = row_fill
                c.border = thin_border
                c.alignment = Alignment(horizontal="center" if col_idx not in (1, 2, 3) else "left")

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row < start_row:
                continue
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ==========================================================
# 3. EXECUTIVE PDF DOCUMENT WITH INSTITUTIONAL LETTERHEAD
# ==========================================================

def generate_pdf_report(report_type: str = "employee", department: str = None, start_date=None, end_date=None, user_id: int = None) -> bytes:
    """
    Generates an executive, print-ready PDF audit document with institutional letterhead,
    summary tables, and clean typography via ReportLab.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    settings = AppSettings.get_settings(user_id=user_id)
    institution_name = settings.institution_name if settings else "Mohan Babu University (MBU)"
    threshold = settings.attendance_threshold if settings else 75.0
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InstTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#101B2B"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "InstSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#697586"),
        spaceAfter=14,
    )
    meta_style = ParagraphStyle(
        "InstMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#17263C"),
    )
    cell_style = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
    )

    elements = []

    # Letterhead & Title
    elements.append(Paragraph(institution_name, title_style))
    elements.append(Paragraph(f"Attendance & Compliance Analysis Report | Report View: {report_type.capitalize()} | Generated: {now_str}", subtitle_style))
    elements.append(Paragraph(f"Policy Benchmark Threshold: <b>{threshold}%</b> Minimum Attendance", meta_style))
    elements.append(Spacer(1, 14))

    # Build Table
    if report_type == "monthly":
        headers = ["Month", "Present", "Absent", "Leave", "Holidays", "Working Days", "Recorded", "Attendance %", "Absenteeism %"]
        data = [[Paragraph(f"<b>{h}</b>", cell_bold) for h in headers]]
        rows = get_monthly_attendance_summary(user_id=user_id)
        for r in rows:
            data.append([
                Paragraph(r["month"], cell_bold),
                Paragraph(str(r["present_count"]), cell_style),
                Paragraph(str(r["absent_count"]), cell_style),
                Paragraph(str(r["leave_count"]), cell_style),
                Paragraph(str(r["holiday_count"]), cell_style),
                Paragraph(str(r["total_working_days"]), cell_bold),
                Paragraph(str(r["total_recorded_days"]), cell_style),
                Paragraph(f"{r['attendance_percentage']}%", cell_bold),
                Paragraph(f"{r['absenteeism_rate']}%", cell_style),
            ])
        col_widths = [100, 65, 65, 65, 65, 90, 80, 95, 95]

    elif report_type == "department":
        headers = ["Department / School", "Staff", "Present", "Absent", "Leave", "Holidays", "Working Days", "Attendance %", "Absenteeism %"]
        data = [[Paragraph(f"<b>{h}</b>", cell_bold) for h in headers]]
        rows = get_department_attendance_summary(user_id=user_id)
        for r in rows:
            data.append([
                Paragraph(r["department"], cell_bold),
                Paragraph(str(r["total_employees"]), cell_style),
                Paragraph(str(r["present_count"]), cell_style),
                Paragraph(str(r["absent_count"]), cell_style),
                Paragraph(str(r["leave_count"]), cell_style),
                Paragraph(str(r["holiday_count"]), cell_style),
                Paragraph(str(r["total_working_days"]), cell_bold),
                Paragraph(f"{r['attendance_percentage']}%", cell_bold),
                Paragraph(f"{r['absenteeism_rate']}%", cell_style),
            ])
        col_widths = [180, 50, 60, 60, 60, 60, 80, 85, 85]

    else:
        # Default: Personnel level
        headers = ["Code", "Full Name", "Department / School", "Present", "Absent", "Leave", "Work Days", "Attendance %", "Compliance"]
        data = [[Paragraph(f"<b>{h}</b>", cell_bold) for h in headers]]
        rows = get_employee_attendance_summary(
            department=department, start_date=start_date, end_date=end_date, threshold=threshold, user_id=user_id
        )
        for r in rows:
            is_defaulter = r["below_threshold"]
            pct_text = f"<font color='{'#991B1B' if is_defaulter else '#166534'}'><b>{r['attendance_percentage']}%</b></font>"
            status_text = f"<font color='{'#991B1B' if is_defaulter else '#166534'}'>{r['status_compliance']}</font>"
            data.append([
                Paragraph(r["employee_code"] or "", cell_bold),
                Paragraph(r["employee_name"] or "", cell_style),
                Paragraph(r["department"] or "", cell_style),
                Paragraph(str(r["present_count"]), cell_style),
                Paragraph(str(r["absent_count"]), cell_style),
                Paragraph(str(r["leave_count"]), cell_style),
                Paragraph(str(r["total_working_days"]), cell_bold),
                Paragraph(pct_text, cell_style),
                Paragraph(status_text, cell_style),
            ])
        col_widths = [65, 140, 160, 50, 50, 50, 65, 75, 80]

    # ReportLab Table Styling
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17263C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E6E8")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)

    doc.build(elements)
    return buf.getvalue()
