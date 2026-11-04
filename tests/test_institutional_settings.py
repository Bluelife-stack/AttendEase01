"""
tests/test_institutional_settings.py — Tests for Institutional Adaptability & Terminology Configuration.
Verifies that settings can be changed between University, School, Corporate, and Research models.
"""
import pytest
from app import db
from app.models import AppSettings


def test_default_institutional_settings(app):
    """Test default institutional settings initialization."""
    with app.app_context():
        settings = AppSettings.get_settings()
        assert settings.institution_name is not None
        assert settings.attendance_threshold == 75.0
        assert settings.employee_label_singular is not None
        assert settings.employee_label_plural is not None


def test_update_institutional_settings(client, app):
    """Test updating settings to an institutional model (e.g. University vs Corporate)."""
    response = client.post("/settings/", data={
        "app_name": "UniAttend — Faculty Attendance Portal",
        "institution_name": "Mohan Babu University",
        "institution_type": "University / College",
        "employee_label_singular": "Faculty Member",
        "employee_label_plural": "Faculty & Staff",
        "department_label": "School / Department",
        "id_code_label": "Faculty ID",
        "academic_year": "2026-2027",
        "attendance_threshold": "80.0",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Institutional configuration and terminology updated successfully" in response.data

    with app.app_context():
        settings = AppSettings.get_settings()
        assert settings.institution_name == "Mohan Babu University"
        assert settings.attendance_threshold == 80.0
        assert settings.employee_label_plural == "Faculty & Staff"
        assert settings.department_label == "School / Department"
