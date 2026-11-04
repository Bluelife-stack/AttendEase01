"""
tests/test_multi_tenancy.py — Automated tests for Customer Data Isolation.
Verifies that every customer sees their own unique data, preserves existing data,
and prevents data leakage between different user accounts.
"""
import pytest
from app import db
from app.models import User, Employee, Attendance, AppSettings


def test_unique_data_per_customer_and_data_preservation(client, app):
    """
    Test scenario:
      1. Customer A registers and adds employees.
      2. Customer B registers with a different email and adds their own employee.
      3. Customer B only sees Customer B's records.
      4. Customer A logs back in: Customer A's records are completely preserved.
      5. Customer A and B maintain separate, independent institutional settings.
    """
    # 1. Register Customer A
    client.post("/auth/register", data={
        "full_name": "Dr. Alice Adams",
        "username": "customer_a",
        "email": "alice@university_a.edu",
        "role": "Administrator",
        "password": "PasswordA123!",
        "confirm_password": "PasswordA123!"
    }, follow_redirects=True)

    # Customer A customizes institutional settings
    client.post("/settings/", data={
        "app_name": "University A Attendance System",
        "institution_name": "University Alpha",
        "institution_type": "University / College",
        "employee_label_singular": "Professor",
        "employee_label_plural": "Faculty Members",
        "department_label": "School",
        "id_code_label": "Prof Code",
        "academic_year": "2026-2027",
        "attendance_threshold": "75.0"
    }, follow_redirects=True)

    client.post("/employees/departments", data={
        "name": "School of Computing",
        "code": "COMP",
    }, follow_redirects=True)

    # Customer A adds an employee
    res_add_a = client.post("/employees/add", data={
        "employee_code": "FAC_A01",
        "employee_name": "Dr. Alan Turing",
        "department": "School of Computing"
    }, follow_redirects=True)
    assert res_add_a.status_code == 200
    assert b"FAC_A01" in res_add_a.data
    assert b"Dr. Alan Turing" in res_add_a.data

    # Customer A logs out
    client.get("/auth/logout", follow_redirects=True)

    # 2. Register Customer B (Different University / School)
    client.post("/auth/register", data={
        "full_name": "Principal Bob Baker",
        "username": "customer_b",
        "email": "bob@school_b.edu",
        "role": "HR / Staff Supervisor",
        "password": "PasswordB123!",
        "confirm_password": "PasswordB123!"
    }, follow_redirects=True)

    # Customer B customizes institutional settings
    client.post("/settings/", data={
        "app_name": "School B Staff Portal",
        "institution_name": "Baker High School",
        "institution_type": "School / K-12",
        "employee_label_singular": "Teacher",
        "employee_label_plural": "Teachers & Staff",
        "department_label": "Wing",
        "id_code_label": "Teacher ID",
        "academic_year": "2026-2027",
        "attendance_threshold": "85.0"
    }, follow_redirects=True)

    client.post("/employees/departments", data={
        "name": "Science Wing",
        "code": "SCI",
    }, follow_redirects=True)

    # Verify Customer B's employee list does NOT show Customer A's employee
    res_list_b = client.get("/employees/")
    assert b"Dr. Alan Turing" not in res_list_b.data
    assert b"FAC_A01" not in res_list_b.data

    # Customer B adds their own employee
    res_add_b = client.post("/employees/add", data={
        "employee_code": "TCH_B01",
        "employee_name": "Grace Hopper",
        "department": "Science Wing"
    }, follow_redirects=True)
    assert res_add_b.status_code == 200
    assert b"TCH_B01" in res_add_b.data
    assert b"Grace Hopper" in res_add_b.data
    assert b"Dr. Alan Turing" not in res_add_b.data

    # Customer B logs out
    client.get("/auth/logout", follow_redirects=True)

    # 3. Customer A logs back in: Verify Customer A's data is 100% PRESERVED
    client.post("/auth/login", data={
        "identifier": "customer_a",
        "password": "PasswordA123!"
    }, follow_redirects=True)

    res_list_a = client.get("/employees/")
    assert b"Dr. Alan Turing" in res_list_a.data
    assert b"FAC_A01" in res_list_a.data
    # Customer A must NOT see Customer B's employee
    assert b"Grace Hopper" not in res_list_a.data
    assert b"TCH_B01" not in res_list_a.data

    # Verify settings isolation: Customer A's settings remain "University Alpha"
    with app.app_context():
        user_a = User.query.filter_by(username="customer_a").first()
        user_b = User.query.filter_by(username="customer_b").first()

        settings_a = AppSettings.get_settings(user_id=user_a.id)
        settings_b = AppSettings.get_settings(user_id=user_b.id)

        assert settings_a.institution_name == "University Alpha"
        assert settings_a.attendance_threshold == 75.0

        assert settings_b.institution_name == "Baker High School"
        assert settings_b.attendance_threshold == 85.0
