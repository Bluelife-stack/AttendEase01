"""
app/services/analytics_service.py — Data Analytics, Grouped Summaries & Matplotlib Visualizations.

Leverages:
  - Pandas for tabular aggregation, pivot tables, and monthly grouping
  - NumPy for vectorized percentage and absenteeism rate calculations with zero-division handling
  - Matplotlib (headless 'Agg' backend) for generating persistent PNG charts:
      1. monthly_attendance_summary.png
      2. department_absenteeism_comparison.png
      3. employee_attendance_percentage.png
"""
import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app import db
from app.models import Employee, Attendance, AppSettings


def get_charts_dir() -> Path:
    """Returns the static charts directory inside the Flask app."""
    base_dir = Path(__file__).resolve().parent.parent
    charts_dir = base_dir / "static" / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    return charts_dir


def get_outputs_charts_dir() -> Path:
    """Returns the project-level outputs/charts directory."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    charts_dir = base_dir / "outputs" / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    return charts_dir


# ==========================================================
# DATA INGESTION INTO PANDAS DATAFRAME
# ==========================================================

def load_attendance_dataframe(department: str = None, start_date=None, end_date=None, user_id: int = None) -> pd.DataFrame:
    """
    Extracts joined Employee and Attendance records via SQLAlchemy ORM into a Pandas DataFrame.
    Uses LEFT JOIN so employees with zero recorded days are still represented.
    Scopes by user_id for multi-tenant data isolation.
    """
    query = (
        db.session.query(
            Employee.employee_id,
            Employee.employee_code,
            Employee.employee_name,
            Employee.department,
            Employee.is_active,
            Attendance.attendance_id,
            Attendance.attendance_date,
            Attendance.status
        )
        .outerjoin(Attendance, Employee.employee_id == Attendance.employee_id)
        .filter(Employee.is_active == True)
    )

    if user_id is not None:
        query = query.filter(Employee.user_id == user_id)
    if department:
        query = query.filter(Employee.department == department)
    if start_date:
        query = query.filter(db.or_(Attendance.attendance_date >= start_date, Attendance.attendance_date == None))
    if end_date:
        query = query.filter(db.or_(Attendance.attendance_date <= end_date, Attendance.attendance_date == None))

    records = query.all()
    if not records:
        return pd.DataFrame(columns=[
            "employee_id", "employee_code", "employee_name", "department",
            "is_active", "attendance_id", "attendance_date", "status", "year_month"
        ])

    data = []
    for r in records:
        ym = r.attendance_date.strftime("%Y-%m") if r.attendance_date else None
        data.append({
            "employee_id": r.employee_id,
            "employee_code": r.employee_code,
            "employee_name": r.employee_name,
            "department": r.department,
            "is_active": r.is_active,
            "attendance_id": r.attendance_id,
            "attendance_date": r.attendance_date,
            "status": r.status,
            "year_month": ym
        })

    return pd.DataFrame(data)


# ==========================================================
# NUMPY VECTORIZED CALCULATION ROUTINES
# ==========================================================

def calculate_attendance_percentage(present_days: int | float, absent_days: int | float, leave_days: int | float) -> float:
    """
    Computes Attendance Percentage using NumPy scalar math.
    Standard academic/enterprise formula:
      Working Days = Present + Absent + Leave
      Attendance % = (Present / Working Days) * 100
    Holidays are excluded from the working days denominator.
    Returns 0.0 cleanly on zero working days without ZeroDivisionError.
    """
    working_days = float(present_days + absent_days + leave_days)
    if working_days <= 0:
        return 0.0
    return float(np.round((float(present_days) / working_days) * 100.0, 2))


def calculate_absenteeism_rate(absent_days: int | float, present_days: int | float, leave_days: int | float) -> float:
    """
    Computes Absenteeism Rate using NumPy scalar math.
    Standard formula:
      Working Days = Present + Absent + Leave
      Absenteeism Rate % = (Absent / Working Days) * 100
    """
    working_days = float(present_days + absent_days + leave_days)
    if working_days <= 0:
        return 0.0
    return float(np.round((float(absent_days) / working_days) * 100.0, 2))


# ==========================================================
# AGGREGATION SUMMARIES (Pandas GroupBy & Pivots)
# ==========================================================

def get_employee_attendance_summary(department: str = None, start_date=None, end_date=None, threshold: float = 75.0, user_id: int = None) -> list[dict]:
    """
    Generates employee-level attendance breakdown, total working days, and percentages.
    """
    df = load_attendance_dataframe(department=department, start_date=start_date, end_date=end_date, user_id=user_id)
    if df.empty:
        return []

    emp_meta = df[["employee_id", "employee_code", "employee_name", "department"]].drop_duplicates().set_index("employee_id")

    att_df = df[df["attendance_id"].notnull()]
    if att_df.empty:
        pivot = pd.DataFrame(0, index=emp_meta.index, columns=["Present", "Absent", "Leave", "Holiday"])
    else:
        pivot = att_df.groupby(["employee_id", "status"]).size().unstack(fill_value=0)
        for st in ["Present", "Absent", "Leave", "Holiday"]:
            if st not in pivot.columns:
                pivot[st] = 0

    pivot = pivot.reindex(emp_meta.index, fill_value=0)

    summary = []
    for emp_id, row in pivot.iterrows():
        meta = emp_meta.loc[emp_id]
        p = int(row.get("Present", 0))
        a = int(row.get("Absent", 0))
        l = int(row.get("Leave", 0))
        h = int(row.get("Holiday", 0))
        employee_code = None if pd.isna(meta["employee_code"]) else meta["employee_code"]
        employee_name = None if pd.isna(meta["employee_name"]) else meta["employee_name"]
        department_name = None if pd.isna(meta["department"]) else meta["department"]

        working_days = p + a + l
        total_days = working_days + h
        pct = calculate_attendance_percentage(p, a, l)
        abs_rate = calculate_absenteeism_rate(a, p, l)

        summary.append({
            "employee_id": int(emp_id),
            "employee_code": employee_code,
            "employee_name": employee_name,
            "department": department_name,
            "present_count": p,
            "absent_count": a,
            "leave_count": l,
            "holiday_count": h,
            "total_working_days": working_days,
            "total_recorded_days": total_days,
            "attendance_percentage": pct,
            "absenteeism_rate": abs_rate,
            "below_threshold": (pct < threshold if working_days > 0 else True),
            "status_compliance": "Meets Policy" if pct >= threshold else "Defaulter (<75%)"
        })

    summary.sort(key=lambda x: (x["employee_code"] or "", (x["employee_name"] or "").casefold()))
    return summary


def get_monthly_attendance_summary(user_id: int = None) -> list[dict]:
    """
    Generates monthly attendance summary grouped by year_month using Pandas.
    """
    df = load_attendance_dataframe(user_id=user_id)
    att_df = df[df["attendance_id"].notnull() & df["year_month"].notnull()]
    if att_df.empty:
        return []

    month_counts = att_df.groupby(["year_month", "status"]).size().unstack(fill_value=0)
    for st in ["Present", "Absent", "Leave", "Holiday"]:
        if st not in month_counts.columns:
            month_counts[st] = 0

    reports = []
    for ym, row in month_counts.iterrows():
        p = int(row["Present"])
        a = int(row["Absent"])
        l = int(row["Leave"])
        h = int(row["Holiday"])
        working_days = p + a + l
        total_days = working_days + h
        pct = calculate_attendance_percentage(p, a, l)
        abs_rate = calculate_absenteeism_rate(a, p, l)

        reports.append({
            "month": ym,
            "present_count": p,
            "absent_count": a,
            "leave_count": l,
            "holiday_count": h,
            "total_working_days": working_days,
            "total_recorded_days": total_days,
            "attendance_percentage": pct,
            "absenteeism_rate": abs_rate
        })

    reports.sort(key=lambda x: x["month"])
    return reports


def get_department_attendance_summary(user_id: int = None) -> list[dict]:
    """
    Generates department-wise attendance and absenteeism comparison using Pandas.
    """
    df = load_attendance_dataframe(user_id=user_id)
    if df.empty:
        return []

    df = df.copy()
    df["department"] = df["department"].fillna("Unassigned").astype(str)
    departments = sorted(df["department"].unique())
    att_df = df[df["attendance_id"].notnull()]

    dept_summary = []
    for dept in departments:
        dept_emps = df[df["department"] == dept]["employee_id"].nunique()
        dept_att = att_df[att_df["department"] == dept]

        if dept_att.empty:
            p = a = l = h = 0
        else:
            counts = dept_att["status"].value_counts().to_dict()
            p = int(counts.get("Present", 0))
            a = int(counts.get("Absent", 0))
            l = int(counts.get("Leave", 0))
            h = int(counts.get("Holiday", 0))

        working_days = p + a + l
        total_days = working_days + h
        pct = calculate_attendance_percentage(p, a, l)
        abs_rate = calculate_absenteeism_rate(a, p, l)

        dept_summary.append({
            "department": dept,
            "total_employees": int(dept_emps),
            "present_count": p,
            "absent_count": a,
            "leave_count": l,
            "holiday_count": h,
            "total_working_days": working_days,
            "total_recorded_days": total_days,
            "attendance_percentage": pct,
            "absenteeism_rate": abs_rate
        })

    return dept_summary


def dashboard_kpis(user_id: int = None, threshold: float = 75.0) -> dict:
    """Calculates top-level KPI metrics for the executive dashboard scoped by customer."""
    emp_query = Employee.query.filter_by(is_active=True)
    if user_id is not None:
        emp_query = emp_query.filter_by(user_id=user_id)
    total_employees = emp_query.count()

    dept_query = db.session.query(Employee.department).distinct().filter(Employee.is_active == True)
    if user_id is not None:
        dept_query = dept_query.filter(Employee.user_id == user_id)
    departments = [d[0] for d in dept_query.all()]

    att_query = Attendance.query.join(Employee)
    if user_id is not None:
        att_query = att_query.filter(Employee.user_id == user_id)
    total_records = att_query.count()

    p_count = att_query.filter(Attendance.status == "Present").count()
    a_count = att_query.filter(Attendance.status == "Absent").count()
    l_count = att_query.filter(Attendance.status == "Leave").count()
    overall_pct = calculate_attendance_percentage(p_count, a_count, l_count)
    overall_abs = calculate_absenteeism_rate(a_count, p_count, l_count)

    emp_summary = get_employee_attendance_summary(user_id=user_id, threshold=threshold)
    defaulters = [e for e in emp_summary if e["below_threshold"]]

    # Recent 5 dates of attendance activity
    recent_dates_q = db.session.query(Attendance.attendance_date).join(Employee)
    if user_id is not None:
        recent_dates_q = recent_dates_q.filter(Employee.user_id == user_id)
    recent_dates = (
        recent_dates_q
        .distinct()
        .order_by(Attendance.attendance_date.desc())
        .limit(5)
        .all()
    )
    recent_activity = []
    for (d_val,) in recent_dates:
        recs_q = Attendance.query.join(Employee).filter(Attendance.attendance_date == d_val)
        if user_id is not None:
            recs_q = recs_q.filter(Employee.user_id == user_id)
        recs = recs_q.all()
        p = sum(1 for r in recs if r.status == "Present")
        a = sum(1 for r in recs if r.status == "Absent")
        l = sum(1 for r in recs if r.status == "Leave")
        h = sum(1 for r in recs if r.status == "Holiday")
        recent_activity.append({
            "date": d_val,
            "total": len(recs),
            "present": p,
            "absent": a,
            "leave": l,
            "holiday": h,
            "percentage": calculate_attendance_percentage(p, a, l)
        })

    return {
        "total_employees": total_employees,
        "departments_count": len(departments),
        "departments_list": departments,
        "total_records": total_records,
        "overall_percentage": overall_pct,
        "overall_absenteeism": overall_abs,
        "defaulters_count": len(defaulters),
        "defaulters": defaulters,
        "recent_activity": recent_activity
    }


# ==========================================================
# MATPLOTLIB CHART GENERATION PIPELINE
# ==========================================================

def generate_monthly_attendance_chart(user_id: int = None) -> str:
    """Chart 1: Grouped bar chart of monthly status breakdown."""
    monthly_data = get_monthly_attendance_summary(user_id=user_id)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)

    if not monthly_data:
        ax.text(0.5, 0.5, "No Attendance Records Found", ha="center", va="center", fontsize=14, color="#697586")
        ax.set_title("Monthly Attendance Status Summary (No Data)")
    else:
        months = [m["month"] for m in monthly_data]
        p = [m["present_count"] for m in monthly_data]
        a = [m["absent_count"] for m in monthly_data]
        l = [m["leave_count"] for m in monthly_data]
        h = [m["holiday_count"] for m in monthly_data]

        x = np.arange(len(months))
        width = 0.2

        ax.bar(x - 1.5 * width, p, width, label="Present", color="#1E7E34", edgecolor="black", linewidth=0.5)
        ax.bar(x - 0.5 * width, a, width, label="Absent", color="#B93A45", edgecolor="black", linewidth=0.5)
        ax.bar(x + 0.5 * width, l, width, label="Leave", color="#B7791F", edgecolor="black", linewidth=0.5)
        ax.bar(x + 1.5 * width, h, width, label="Holiday", color="#2563EB", edgecolor="black", linewidth=0.5)

        ax.set_xlabel("Month (Year-Month)", fontweight="bold", fontsize=10, labelpad=8)
        ax.set_ylabel("Recorded Days", fontweight="bold", fontsize=10, labelpad=8)
        ax.set_title("Monthly Attendance Status Summary", fontweight="bold", fontsize=12, pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(months, fontsize=9)
        ax.legend(frameon=True, fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    file_suffix = f"_{user_id}.png" if user_id else ".png"
    static_file = get_charts_dir() / f"monthly_attendance_summary{file_suffix}"
    output_file = get_outputs_charts_dir() / f"monthly_attendance_summary{file_suffix}"
    plt.savefig(static_file)
    plt.savefig(output_file)

    # Always also maintain default name for primary/admin view
    default_static = get_charts_dir() / "monthly_attendance_summary.png"
    if str(static_file) != str(default_static):
        plt.savefig(default_static)

    plt.close()
    return str(static_file)


def generate_department_absenteeism_chart(user_id: int = None) -> str:
    """Chart 2: Department-wise Absenteeism Rate Comparison."""
    dept_data = get_department_attendance_summary(user_id=user_id)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)

    if not dept_data:
        ax.text(0.5, 0.5, "No Department Attendance Data", ha="center", va="center", fontsize=14, color="#697586")
        ax.set_title("Department Absenteeism Comparison (No Data)")
    else:
        depts = [d["department"] for d in dept_data]
        abs_rates = [d["absenteeism_rate"] for d in dept_data]
        x = np.arange(len(depts))
        colors = ["#B93A45" if r > 15.0 else "#B7791F" if r > 7.0 else "#1E7E34" for r in abs_rates]

        bars = ax.bar(x, abs_rates, width=0.45, color=colors, edgecolor="black", linewidth=0.5)
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.1f}%",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center", va="bottom",
                fontsize=9, fontweight="bold"
            )

        ax.axhline(y=10.0, color="#64748B", linestyle=":", linewidth=1.2, label="10% Tolerance Threshold")
        ax.set_xlabel("Department", fontweight="bold", fontsize=10, labelpad=8)
        ax.set_ylabel("Absenteeism Rate (%)", fontweight="bold", fontsize=10, labelpad=8)
        ax.set_title("Department-wise Absenteeism Rate Comparison", fontweight="bold", fontsize=12, pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(depts, fontsize=9)
        ax.set_ylim(0, max(abs_rates + [25]) + 10)
        ax.legend(frameon=True, fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    file_suffix = f"_{user_id}.png" if user_id else ".png"
    static_file = get_charts_dir() / f"department_absenteeism_comparison{file_suffix}"
    output_file = get_outputs_charts_dir() / f"department_absenteeism_comparison{file_suffix}"
    plt.savefig(static_file)
    plt.savefig(output_file)

    default_static = get_charts_dir() / "department_absenteeism_comparison.png"
    if str(static_file) != str(default_static):
        plt.savefig(default_static)

    plt.close()
    return str(static_file)


def generate_employee_attendance_chart(user_id: int = None, threshold: float = 75.0) -> str:
    """Chart 3: Horizontal bar chart of employee attendance percentage vs benchmark."""
    emp_data = get_employee_attendance_summary(user_id=user_id, threshold=threshold)
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)

    if not emp_data:
        ax.text(0.5, 0.5, "No Personnel Attendance Data", ha="center", va="center", fontsize=14, color="#697586")
        ax.set_title("Attendance Percentage (No Data)")
    else:
        labels = [f"{e['employee_name']} ({e['employee_code']})" for e in emp_data]
        pcts = [e["attendance_percentage"] for e in emp_data]
        y = np.arange(len(labels))
        colors = ["#1E7E34" if p >= threshold else "#B93A45" for p in pcts]

        bars = ax.barh(y, pcts, height=0.55, color=colors, edgecolor="black", linewidth=0.5)
        for bar in bars:
            width = bar.get_width()
            ax.annotate(
                f"{width:.1f}%",
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(4, 0),
                textcoords="offset points",
                ha="left", va="center",
                fontsize=8, fontweight="bold"
            )

        ax.axvline(x=threshold, color="#B93A45", linestyle="--", linewidth=1.5, label=f"{threshold}% Benchmark")
        ax.set_xlabel("Attendance Percentage (%)", fontweight="bold", fontsize=10, labelpad=8)
        ax.set_ylabel("Personnel (Name & Code)", fontweight="bold", fontsize=10, labelpad=8)
        ax.set_title("Attendance Percentage vs Benchmark", fontweight="bold", fontsize=12, pad=12)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlim(0, 115)
        ax.legend(loc="lower right", frameon=True, fontsize=9)
        ax.grid(axis="x", linestyle="--", alpha=0.5)

    plt.tight_layout()
    file_suffix = f"_{user_id}.png" if user_id else ".png"
    static_file = get_charts_dir() / f"employee_attendance_percentage{file_suffix}"
    output_file = get_outputs_charts_dir() / f"employee_attendance_percentage{file_suffix}"
    plt.savefig(static_file)
    plt.savefig(output_file)

    default_static = get_charts_dir() / "employee_attendance_percentage.png"
    if str(static_file) != str(default_static):
        plt.savefig(default_static)

    plt.close()
    return str(static_file)


def generate_all_visualizations(user_id: int = None, threshold: float = 75.0) -> dict:
    """Generates all 3 required charts and persists them to disk."""
    c1 = generate_monthly_attendance_chart(user_id=user_id)
    c2 = generate_department_absenteeism_chart(user_id=user_id)
    c3 = generate_employee_attendance_chart(user_id=user_id, threshold=threshold)
    return {
        "monthly_chart": c1,
        "department_chart": c2,
        "employee_chart": c3
    }
