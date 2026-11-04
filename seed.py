"""
seed.py — Demonstration Data Seeder for Employee & Faculty Attendance Analysis System.

Creates:
  - Default administrative and faculty coordinator accounts (with hashed passwords)
  - Customizable institutional settings (Mohan Babu University defaults, easily switchable to School/Corporate)
  - 25 faculty and employee records across 5 academic/corporate departments
  - 20 historical attendance dates (working days & institutional holidays)
  - Realistic distribution of Present, Absent, Leave, and Holiday statuses
  - Guaranteed presence of defaulter staff (<75%) to demonstrate policy alerts
  - Automatically invokes Matplotlib to generate the 3 required analytical charts!
"""
import os
from datetime import date, timedelta
from app import create_app, db
from app.models import Employee, Attendance, AppSettings, User
from app.services.analytics_service import generate_all_visualizations


STAFF_DATA = [
    # School of Computer Science & Engineering
    ("FAC101", "Dr. Aarav Sharma", "School of Computer Science", "Professor", "a.sharma@mbu.edu"),
    ("FAC102", "Dr. Aditi Rao", "School of Computer Science", "Associate Professor", "a.rao@mbu.edu"),
    ("FAC103", "Prof. Ananya Verma", "School of Computer Science", "Assistant Professor", "a.verma@mbu.edu"),
    ("FAC104", "Prof. Arjun Nair", "School of Computer Science", "Assistant Professor", "a.nair@mbu.edu"),
    ("FAC105", "Dev Patel", "School of Computer Science", "Technical Assistant", "d.patel@mbu.edu"),         # Defaulter (~30%)
    ("FAC106", "Diya Sengupta", "School of Computer Science", "Research Associate", "d.sengupta@mbu.edu"),
    
    # Department of Electronics & Communication
    ("FAC107", "Dr. Ishaan Kulkarni", "Electronics & Communication", "Professor & Head", "i.kulkarni@mbu.edu"),
    ("FAC108", "Prof. Kavya Menon", "Electronics & Communication", "Associate Professor", "k.menon@mbu.edu"),
    ("FAC109", "Madhav Joshi", "Electronics & Communication", "Lab Instructor", "m.joshi@mbu.edu"),         # Borderline (~70%)
    ("FAC110", "Dr. Meera Iyer", "Electronics & Communication", "Professor", "m.iyer@mbu.edu"),
    
    # Department of Mechanical & Aerospace
    ("FAC111", "Dr. Nikhil Reddy", "Mechanical & Aerospace", "Professor & Dean", "n.reddy@mbu.edu"),
    ("FAC112", "Prof. Pooja Hegde", "Mechanical & Aerospace", "Assistant Professor", "p.hegde@mbu.edu"),
    ("FAC113", "Dr. Pranav Deshmukh", "Mechanical & Aerospace", "Associate Professor", "p.deshmukh@mbu.edu"),
    ("FAC114", "Rhea Pillai", "Mechanical & Aerospace", "Senior Research Fellow", "r.pillai@mbu.edu"),
    
    # School of Management Studies & Commerce
    ("FAC115", "Dr. Rohan Bhatt", "Management Studies", "Professor", "r.bhatt@mbu.edu"),
    ("FAC116", "Prof. Saanvi Mehra", "Management Studies", "Associate Professor", "s.mehra@mbu.edu"),
    ("FAC117", "Dr. Samar Sen", "Management Studies", "Professor", "s.sen@mbu.edu"),
    ("FAC118", "Prof. Shreya Das", "Management Studies", "Assistant Professor", "s.das@mbu.edu"),
    ("FAC119", "Siddharth Bose", "Management Studies", "Administrative Officer", "s.bose@mbu.edu"),
    ("FAC120", "Tanvi Agarwal", "Management Studies", "Academic Coordinator", "t.agarwal@mbu.edu"),
    
    # Department of Sciences & Humanities
    ("FAC121", "Dr. Varun Chopra", "Sciences & Humanities", "Professor of Physics", "v.chopra@mbu.edu"),
    ("FAC122", "Dr. Vidya Balan", "Sciences & Humanities", "Professor of Mathematics", "v.balan@mbu.edu"),
    ("FAC123", "Dr. Vikram Malhotra", "Sciences & Humanities", "Associate Professor", "v.malhotra@mbu.edu"),
    ("FAC124", "Yash Singhal", "Sciences & Humanities", "Laboratory Superintendent", "y.singhal@mbu.edu"),   # Defaulter (~40%)
    ("FAC125", "Dr. Zoya Khan", "Sciences & Humanities", "Assistant Professor", "z.khan@mbu.edu"),
]


def _require_empty_database():
    if any((
        User.query.first(),
        Employee.query.first(),
        Attendance.query.first(),
        AppSettings.query.first(),
    )):
        raise RuntimeError(
            "Refusing to seed a database that already contains customer data. "
            "Use a separate, empty database for demo data."
        )


def seed_database():
    app = create_app()
    with app.app_context():
        db.create_all()
        _require_empty_database()

        # 1. Seed Default User Accounts
        admin = User(
            username="admin",
            email="admin@mbu.edu",
            full_name="Dr. Ramesh Babu",
            role="Administrator",
            is_active=True
        )
        admin.set_password("admin123")
        db.session.add(admin)

        coord = User(
            username="coordinator",
            email="coordinator@mbu.edu",
            full_name="Prof. Sneha Rao",
            role="Faculty Coordinator",
            is_active=True
        )
        coord.set_password("coord123")
        db.session.add(coord)

        db.session.commit()
        print("Verified/Created default accounts: 'admin' (admin123) and 'coordinator' (coord123).")

        # 2. Initialize Institutional Settings for Admin and Coordinator
        settings = AppSettings(
            user_id=admin.id,
            app_name="StaffPulse — Faculty & Employee Attendance System",
            institution_name="Mohan Babu University (MBU)",
            institution_type="University / College",
            employee_label_singular="Faculty Member",
            employee_label_plural="Faculty & Staff",
            department_label="School / Department",
            id_code_label="Faculty ID",
            academic_year="2026-2027",
            attendance_threshold=75.0
        )
        db.session.add(settings)

        # Default global fallback settings
        global_settings = AppSettings(
            user_id=None,
            app_name="StaffPulse — Faculty & Employee Attendance System",
            institution_name="Mohan Babu University (MBU)",
            institution_type="University / College",
            employee_label_singular="Faculty Member",
            employee_label_plural="Faculty & Staff",
            department_label="School / Department",
            id_code_label="Faculty ID",
            academic_year="2026-2027",
            attendance_threshold=75.0
        )
        db.session.add(global_settings)
        db.session.commit()

        # 3. Seed Faculty & Staff Members for Admin (Preserved Account)
        emp_map = {}
        for code, name, dept, desig, email in STAFF_DATA:
            emp = Employee(
                user_id=admin.id,
                employee_code=code,
                employee_name=name,
                department=dept,
                designation=desig,
                email=email,
                is_active=True
            )
            db.session.add(emp)
            db.session.flush()
            emp_map[code] = emp

        db.session.commit()
        print(f"Verified/Seeded {len(emp_map)} staff members across 5 schools/departments.")

        # 4. Seed 20 historical attendance dates across Oct 2026
        # Includes 18 working days and 2 official institutional holidays
        start_date = date(2026, 10, 1)
        attendance_dates = []
        cur = start_date
        while len(attendance_dates) < 20:
            if cur.weekday() < 5:  # Monday to Friday
                attendance_dates.append(cur)
            cur += timedelta(days=1)

        holiday_dates = {attendance_dates[1], attendance_dates[14]}  # 2 Official Institutional Holidays
        records_created = 0

        for d_idx, att_date in enumerate(attendance_dates):
            is_institutional_holiday = (att_date in holiday_dates)

            for code, emp in emp_map.items():
                existing = Attendance.query.filter_by(employee_id=emp.employee_id, attendance_date=att_date).first()
                if existing:
                    continue

                if is_institutional_holiday:
                    status = "Holiday"
                else:
                    # Realistic variance
                    if code == "FAC105":
                        # Dev Patel: Chronic absentee (absent ~70% of days)
                        status = "Absent" if (d_idx % 3 != 0) else "Present"
                    elif code == "FAC124":
                        # Yash Singhal: High absenteeism (~60% absent)
                        status = "Absent" if (d_idx % 2 == 0) else "Present"
                    elif code == "FAC109":
                        # Madhav Joshi: Borderline (~70% attendance)
                        if d_idx in (2, 6, 10, 16):
                            status = "Absent"
                        elif d_idx == 8:
                            status = "Leave"
                        else:
                            status = "Present"
                    elif code in ("FAC103", "FAC118"):
                        # Approved academic leave instances
                        status = "Leave" if d_idx in (4, 11) else "Present"
                    else:
                        # Regular attendance (occasional casual leave or absence)
                        if d_idx == 7 and code == "FAC112":
                            status = "Leave"
                        elif d_idx == 12 and code == "FAC121":
                            status = "Absent"
                        else:
                            status = "Present"

                rec = Attendance(
                    employee_id=emp.employee_id,
                    attendance_date=att_date,
                    status=status
                )
                db.session.add(rec)
                records_created += 1

        db.session.commit()
        print(f"Created {records_created} daily attendance records.")

        # 5. Generate all 3 Matplotlib charts automatically
        print("Generating Matplotlib analytical charts...")
        charts = generate_all_visualizations()
        print("Charts generated successfully:")
        for k, p in charts.items():
            print(f"  - {k}: {p}")

        print("Database successfully seeded & analytics charts rendered!")


if __name__ == "__main__":
    seed_database()
