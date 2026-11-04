"""
app/models.py — Data Models with User Authentication & Institutional Customization.

Models:
  1. User (Login, Registration, Roles, Password Hashing)
  2. Employee (Faculty & Employee records with department, designation, email)
  3. Attendance (Daily logs with Present, Absent, Leave, Holiday, notes)
  4. AppSettings (Institutional settings: University/School/Corporate adaptability)
"""
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    """
    User accounts for authenticated access (Faculty coordinators, Administrators, HR).
    Includes secure password hashing and role management.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), default="Administrator", nullable=False)  # Administrator, Coordinator, HR Manager
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str):
        """Hashes and stores password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies candidate password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Department(db.Model):
    """Institution-owned department directory used by faculty forms and imports."""
    __tablename__ = "departments"
    __table_args__ = (
        db.UniqueConstraint("user_id", "code", name="uq_user_department_code"),
        db.UniqueConstraint("user_id", "name", name="uq_user_department_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Department {self.code} - {self.name}>"


class Employee(db.Model):
    """
    Employee / Faculty entity. Adaptable for university faculty, school teachers, or corporate staff.
    Table: employees
    Fields: employee_id, user_id, employee_code, employee_name, department, designation, email, phone
    """
    __tablename__ = "employees"
    __table_args__ = (
        db.UniqueConstraint("user_id", "employee_code", name="uq_user_employee_code"),
    )

    employee_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    employee_code = db.Column(db.String(20), nullable=True, index=True)
    employee_name = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(80), nullable=True, index=True)
    designation = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("employees", cascade="all, delete-orphan", lazy="dynamic"))

    # Relationships
    attendance_records = db.relationship(
        "Attendance",
        back_populates="employee",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="Attendance.attendance_date.desc()"
    )

    def __repr__(self):
        return f"<Employee {self.employee_code} - {self.employee_name} ({self.department})>"

    def to_dict(self):
        return {
            "employee_id": self.employee_id,
            "employee_code": self.employee_code,
            "employee_name": self.employee_name,
            "department": self.department,
            "designation": self.designation,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
        }


class Student(db.Model):
    """
    Student model retained for legacy student-attendance modules and alternate academic flows.
    Keeps the schema minimal but compatible with the student CRUD routes already present in the codebase.
    """
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    class_section = db.Column(db.String(30), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "roll_number": self.roll_number,
            "full_name": self.full_name,
            "class_section": self.class_section,
            "email": self.email,
            "is_active": self.is_active,
        }


class Subject(db.Model):
    """
    Subject model kept for legacy subject management routes and academic reporting views.
    """
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    subject_name = db.Column(db.String(120), nullable=False)
    class_section = db.Column(db.String(30), nullable=True, index=True)
    faculty = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sessions = db.relationship(
        "AttendanceSession",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="AttendanceSession.session_date.desc()"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "subject_code": self.subject_code,
            "subject_name": self.subject_name,
            "class_section": self.class_section,
            "faculty": self.faculty,
            "is_active": self.is_active,
        }


class AttendanceSession(db.Model):
    """AttendanceSession used by subject-based attendance utilities."""
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    session_date = db.Column(db.Date, nullable=False, index=True)
    topic = db.Column(db.String(160), nullable=True)
    class_section = db.Column(db.String(30), nullable=True, index=True)
    faculty = db.Column(db.String(120), nullable=True)
    total_students = db.Column(db.Integer, default=0, nullable=False)
    present_count = db.Column(db.Integer, default=0, nullable=False)
    absent_count = db.Column(db.Integer, default=0, nullable=False)
    notes = db.Column(db.String(255), nullable=True, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    subject = db.relationship("Subject", back_populates="sessions")


class Attendance(db.Model):
    """
    Daily attendance log for an employee or faculty member.
    Table: attendance
    Fields: attendance_id, employee_id, attendance_date, status, notes, recorded_at

    Supported Statuses:
      - Present: Active duty / lecture presence.
      - Absent: Unapproved absence on working day.
      - Leave: Approved medical, casual, or duty leave.
      - Holiday: Official institution/company holiday (excluded from working days denominator).

    Constraints:
      - Unique constraint on (employee_id, attendance_date) blocks duplicate records.
      - Check constraint restricts valid statuses.
    """
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("employee_id", "attendance_date", name="uq_employee_date"),
        db.CheckConstraint("status IN ('Present', 'Absent', 'Leave', 'Holiday')", name="ck_attendance_status"),
    )

    VALID_STATUSES = ("Present", "Absent", "Leave", "Holiday")

    attendance_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.String(255), nullable=True, default="")
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    employee = db.relationship("Employee", back_populates="attendance_records")

    def __repr__(self):
        return f"<Attendance id={self.attendance_id} emp={self.employee_id} date={self.attendance_date} status={self.status}>"

    def to_dict(self):
        return {
            "attendance_id": self.attendance_id,
            "employee_id": self.employee_id,
            "employee_code": self.employee.employee_code if self.employee else None,
            "employee_name": self.employee.employee_name if self.employee else None,
            "department": self.employee.department if self.employee else None,
            "attendance_date": self.attendance_date.isoformat(),
            "status": self.status,
            "notes": self.notes or "",
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


class AppSettings(db.Model):
    """
    Institutional configuration settings.
    Allows complete customization for Universities, Colleges, Schools, Corporate Offices, and Research Institutes.
    Scoped per user/customer so each account maintains their own unique settings.
    """
    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    app_name = db.Column(db.String(120), default="StaffPulse — Employee & Faculty Attendance System", nullable=False)
    institution_name = db.Column(db.String(200), default="Mohan Babu University (MBU)", nullable=False)
    institution_type = db.Column(db.String(80), default="University / College", nullable=False)
    employee_label_singular = db.Column(db.String(60), default="Faculty / Employee", nullable=False)
    employee_label_plural = db.Column(db.String(60), default="Faculty & Staff", nullable=False)
    department_label = db.Column(db.String(60), default="Department / School", nullable=False)
    id_code_label = db.Column(db.String(60), default="Faculty / Employee ID", nullable=False)
    attendance_threshold = db.Column(db.Float, default=75.0, nullable=False)
    academic_year = db.Column(db.String(40), default="2026-2027", nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("settings_record", uselist=False))

    @classmethod
    def get_settings(cls, user_id=None):
        if user_id:
            s = cls.query.filter_by(user_id=user_id).first()
            if s is None:
                # Inherit default template or create custom for this customer
                s = cls(user_id=user_id)
                db.session.add(s)
                db.session.commit()
            return s
        s = cls.query.filter_by(user_id=None).first() or cls.query.first()
        if s is None:
            s = cls()
            db.session.add(s)
            db.session.commit()
        return s
