"""
tests/test_calculations.py — Formula Precision & Working Day Treatment Tests.
"""
from app.services.analytics_service import (
    calculate_attendance_percentage,
    calculate_absenteeism_rate
)


def test_attendance_percentage_formulas():
    # 15 Present, 5 Absent, 0 Leave = 15/20 = 75.0%
    assert calculate_attendance_percentage(present_days=15, absent_days=5, leave_days=0) == 75.0

    # 14 Present, 6 Absent, 0 Leave = 14/20 = 70.0%
    assert calculate_attendance_percentage(present_days=14, absent_days=6, leave_days=0) == 70.0

    # 18 Present, 2 Absent, 0 Leave = 18/20 = 90.0%
    assert calculate_attendance_percentage(present_days=18, absent_days=2, leave_days=0) == 90.0

    # Zero working days = 0.0% safely (never ZeroDivisionError, NaN, or Inf)
    assert calculate_attendance_percentage(present_days=0, absent_days=0, leave_days=0) == 0.0


def test_leave_day_treatment():
    """
    Leave counts in the working days denominator (approved absence on a working day).
    Present=8, Absent=0, Leave=2 -> Total Working Days = 10.
    Attendance % = 8 / 10 * 100 = 80.0%
    """
    pct = calculate_attendance_percentage(present_days=8, absent_days=0, leave_days=2)
    assert pct == 80.0


def test_absenteeism_rate_formulas():
    # 2 Absent, 8 Present, 0 Leave -> 2/10 = 20.0%
    assert calculate_absenteeism_rate(absent_days=2, present_days=8, leave_days=0) == 20.0

    # 0 Absent, 10 Present, 0 Leave -> 0.0%
    assert calculate_absenteeism_rate(absent_days=0, present_days=10, leave_days=0) == 0.0

    # Zero working days = 0.0%
    assert calculate_absenteeism_rate(absent_days=0, present_days=0, leave_days=0) == 0.0
