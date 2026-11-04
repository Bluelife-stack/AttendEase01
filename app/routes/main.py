"""
app/routes/main.py — Executive Dashboard Route for Employee Attendance Analysis System.
Scoped per customer/user for multi-tenant data isolation.
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.services.analytics_service import (
    dashboard_kpis, get_charts_dir, get_monthly_attendance_summary,
    get_department_attendance_summary,
)
from app.models import AppSettings

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def landing():
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main_bp.route("/dashboard")
def dashboard():
    user_id = current_user.id if current_user.is_authenticated else None
    settings = AppSettings.get_settings(user_id=user_id)
    threshold = settings.attendance_threshold
    kpis = dashboard_kpis(user_id=user_id, threshold=threshold)

    # Verify if chart files exist
    charts_dir = get_charts_dir()
    charts_exist = (
        (charts_dir / "monthly_attendance_summary.png").exists() and
        (charts_dir / "department_absenteeism_comparison.png").exists() and
        (charts_dir / "employee_attendance_percentage.png").exists()
    )

    return render_template(
        "dashboard.html",
        kpis=kpis,
        threshold=threshold,
        charts_exist=charts_exist,
        monthly_summary=get_monthly_attendance_summary(user_id=user_id),
        department_summary=get_department_attendance_summary(user_id=user_id),
    )


@main_bp.route("/help")
@login_required
def help_desk():
    return render_template("help.html")
