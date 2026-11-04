"""app/routes/subjects.py — Subject CRUD routes."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Subject, AttendanceSession

subjects_bp = Blueprint("subjects", __name__)


def _validate_subject(data, subject_id=None):
    errors = []
    code = data.get("subject_code", "").strip().upper()
    name = data.get("subject_name", "").strip()

    if not code:
        errors.append("Subject code is required.")
    elif len(code) > 20:
        errors.append("Subject code must be at most 20 characters.")
    else:
        existing = Subject.query.filter_by(subject_code=code).first()
        if existing and existing.id != subject_id:
            errors.append(f"Subject code '{code}' is already in use.")

    if not name:
        errors.append("Subject name is required.")
    elif len(name) > 120:
        errors.append("Subject name must be at most 120 characters.")

    return errors


@subjects_bp.route("/")
def list_subjects():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "active")

    query = Subject.query
    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Subject.subject_name.ilike(like), Subject.subject_code.ilike(like))
        )

    subjects = query.order_by(Subject.subject_code).all()
    return render_template(
        "subjects/list.html",
        subjects=subjects,
        search=search,
        status_filter=status_filter,
    )


@subjects_bp.route("/add", methods=["GET", "POST"])
def add_subject():
    if request.method == "POST":
        data = request.form
        errors = _validate_subject(data)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("subjects/form.html", subject=None, form_data=data)

        subject = Subject(
            subject_code=data["subject_code"].strip().upper(),
            subject_name=data["subject_name"].strip(),
            class_section=data.get("class_section", "").strip(),
            faculty=data.get("faculty", "").strip(),
            is_active=True,
        )
        db.session.add(subject)
        db.session.commit()
        flash(f"Subject '{subject.subject_name}' added successfully.", "success")
        return redirect(url_for("subjects.list_subjects"))

    return render_template("subjects/form.html", subject=None, form_data={})


@subjects_bp.route("/<int:subject_id>/edit", methods=["GET", "POST"])
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if request.method == "POST":
        data = request.form
        errors = _validate_subject(data, subject_id=subject_id)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("subjects/form.html", subject=subject, form_data=data)

        subject.subject_code = data["subject_code"].strip().upper()
        subject.subject_name = data["subject_name"].strip()
        subject.class_section = data.get("class_section", "").strip()
        subject.faculty = data.get("faculty", "").strip()
        db.session.commit()
        flash(f"Subject '{subject.subject_name}' updated.", "success")
        return redirect(url_for("subjects.list_subjects"))

    return render_template("subjects/form.html", subject=subject, form_data=subject.to_dict())


@subjects_bp.route("/<int:subject_id>")
def view_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    recent_sessions = (
        AttendanceSession.query.filter_by(subject_id=subject_id)
        .order_by(AttendanceSession.session_date.desc())
        .limit(10).all()
    )
    total_sessions = AttendanceSession.query.filter_by(subject_id=subject_id).count()
    return render_template(
        "subjects/detail.html",
        subject=subject,
        recent_sessions=recent_sessions,
        total_sessions=total_sessions,
    )


@subjects_bp.route("/<int:subject_id>/deactivate", methods=["POST"])
def deactivate_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    subject.is_active = False
    db.session.commit()
    flash(f"Subject '{subject.subject_name}' deactivated.", "warning")
    return redirect(url_for("subjects.list_subjects"))


@subjects_bp.route("/<int:subject_id>/reactivate", methods=["POST"])
def reactivate_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    subject.is_active = True
    db.session.commit()
    flash(f"Subject '{subject.subject_name}' reactivated.", "success")
    return redirect(url_for("subjects.list_subjects"))
