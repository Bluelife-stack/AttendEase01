"""
app/routes/settings.py — Institutional / Enterprise Adaptability & Settings.
Allows dynamic customization across Universities, Colleges, Schools, Corporate Offices, and Research Institutes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import AppSettings

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("")
@settings_bp.route("/", methods=["GET", "POST"])
def index():
    user_id = current_user.id if current_user.is_authenticated else None
    settings = AppSettings.get_settings(user_id=user_id)
    if request.method == "POST":
        app_name = request.form.get("app_name", "").strip()
        institution_name = request.form.get("institution_name", "").strip()
        institution_type = request.form.get("institution_type", "University / College").strip()
        emp_label_singular = request.form.get("employee_label_singular", "Faculty / Employee").strip()
        emp_label_plural = request.form.get("employee_label_plural", "Faculty & Staff").strip()
        dept_label = request.form.get("department_label", "Department / School").strip()
        id_code_label = request.form.get("id_code_label", "Faculty / Employee ID").strip()
        academic_year = request.form.get("academic_year", "2026-2027").strip()
        threshold_val = request.form.get("attendance_threshold", "75.0").strip()

        errors = []
        if not app_name:
            errors.append("System application title is required.")
        if not institution_name:
            errors.append("Institution / University name is required.")
        if not emp_label_plural:
            errors.append("Personnel label (plural) is required.")
        if not dept_label:
            errors.append("Department label is required.")

        try:
            threshold = float(threshold_val)
            if not (0.0 <= threshold <= 100.0):
                errors.append("Attendance threshold must be between 0% and 100%.")
        except ValueError:
            errors.append("Attendance threshold must be a valid number.")
            threshold = 75.0

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            settings.app_name = app_name
            settings.institution_name = institution_name
            settings.institution_type = institution_type
            settings.employee_label_singular = emp_label_singular
            settings.employee_label_plural = emp_label_plural
            settings.department_label = dept_label
            settings.id_code_label = id_code_label
            settings.academic_year = academic_year
            settings.attendance_threshold = threshold
            db.session.commit()
            flash("Institutional configuration and terminology updated successfully!", "success")
            return redirect(url_for("settings.index"))

    return render_template("settings/index.html", settings=settings)
