"""app/routes/students.py — Student CRUD routes."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import Student
from app.services.report_service import student_detail_report

students_bp = Blueprint("students", __name__)


def _validate_student(data, student_id=None):
    """Validate student form data. Returns list of errors."""
    errors = []
    roll = data.get("roll_number", "").strip()
    name = data.get("full_name", "").strip()
    section = data.get("class_section", "").strip()
    email = data.get("email", "").strip()

    if not roll:
        errors.append("Roll number is required.")
    elif len(roll) > 20:
        errors.append("Roll number must be at most 20 characters.")
    else:
        existing = Student.query.filter_by(roll_number=roll).first()
        if existing and existing.id != student_id:
            errors.append(f"Roll number '{roll}' is already in use.")

    if not name:
        errors.append("Full name is required.")
    elif len(name) > 120:
        errors.append("Full name must be at most 120 characters.")

    if not section:
        errors.append("Class/Section is required.")

    if email and "@" not in email:
        errors.append("Email address is not valid.")

    return errors


@students_bp.route("/")
def list_students():
    search = request.args.get("q", "").strip()
    section_filter = request.args.get("section", "").strip()
    status_filter = request.args.get("status", "active")

    query = Student.query
    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Student.full_name.ilike(like), Student.roll_number.ilike(like))
        )
    if section_filter:
        query = query.filter_by(class_section=section_filter)

    students = query.order_by(Student.roll_number).all()

    # Sections for filter dropdown
    sections = sorted(set(
        s.class_section for s in Student.query.with_entities(Student.class_section).distinct() if s.class_section
    ))

    return render_template(
        "students/list.html",
        students=students,
        search=search,
        section_filter=section_filter,
        status_filter=status_filter,
        sections=sections,
    )


@students_bp.route("/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        data = request.form
        errors = _validate_student(data)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("students/form.html", student=None, form_data=data)

        student = Student(
            roll_number=data["roll_number"].strip(),
            full_name=data["full_name"].strip(),
            class_section=data["class_section"].strip(),
            email=data.get("email", "").strip() or None,
            is_active=True,
        )
        db.session.add(student)
        db.session.commit()
        flash(f"Student '{student.full_name}' added successfully.", "success")
        return redirect(url_for("students.list_students"))

    return render_template("students/form.html", student=None, form_data={})


@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == "POST":
        data = request.form
        errors = _validate_student(data, student_id=student_id)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("students/form.html", student=student, form_data=data)

        student.roll_number = data["roll_number"].strip()
        student.full_name = data["full_name"].strip()
        student.class_section = data["class_section"].strip()
        student.email = data.get("email", "").strip() or None
        db.session.commit()
        flash(f"Student '{student.full_name}' updated.", "success")
        return redirect(url_for("students.view_student", student_id=student_id))

    return render_template("students/form.html", student=student, form_data=student.to_dict())


@students_bp.route("/<int:student_id>")
def view_student(student_id):
    student = Student.query.get_or_404(student_id)
    detail = student_detail_report(student_id)
    return render_template("students/detail.html", student=student, detail=detail)


@students_bp.route("/<int:student_id>/deactivate", methods=["POST"])
def deactivate_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.is_active = False
    db.session.commit()
    flash(f"Student '{student.full_name}' has been deactivated. Attendance history is preserved.", "warning")
    return redirect(url_for("students.list_students"))


@students_bp.route("/<int:student_id>/reactivate", methods=["POST"])
def reactivate_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.is_active = True
    db.session.commit()
    flash(f"Student '{student.full_name}' has been reactivated.", "success")
    return redirect(url_for("students.list_students"))
