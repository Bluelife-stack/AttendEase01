"""
app/routes/employees.py — Employee Management Routes.
CRUD operations, search, department filtering, and non-destructive deactivation.
Scoped per customer/user for multi-tenant data isolation.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session, current_app
from flask_login import current_user
from app import db
import pandas as pd
import io
import re
import json
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from app.models import Employee, Attendance, Department
from app.services.analytics_service import calculate_attendance_percentage, calculate_absenteeism_rate

employees_bp = Blueprint("employees", __name__)


def _validate_employee(data, employee_id=None, user_id=None):
    errors = []
    code = data.get("employee_code", "").strip().upper() or None
    name = data.get("employee_name", "").strip()
    dept = data.get("department", "").strip()

    if code and len(code) > 20:
        errors.append("Employee code must be at most 20 characters.")
    elif code:
        q = Employee.query.filter_by(employee_code=code)
        if user_id is not None:
            q = q.filter_by(user_id=user_id)
        existing = q.first()
        if existing and existing.employee_id != employee_id:
            errors.append(f"Identifier code '{code}' is already registered in your institution.")

    if name and len(name) > 120:
        errors.append("Employee name must be at most 120 characters.")

    if dept:
        # A submitted value must come from this account's active department list.
        # Existing legacy department names remain valid when editing old records.
        dept_query = _owned_department_query(user_id).filter(Department.name.ilike(dept))
        selected_department = dept_query.first()
        legacy_value = False
        if employee_id is not None:
            current_employee = db.session.get(Employee, employee_id)
            legacy_value = bool(
                current_employee
                and current_employee.department
                and current_employee.department.lower() == dept.lower()
            )
        if not selected_department and not legacy_value:
            errors.append("Select a department from the department directory. Add it first if it is missing.")
        elif selected_department and not selected_department.is_active and not legacy_value:
            errors.append("This department is inactive. Reactivate it before assigning new faculty.")

    if not any((
        code,
        name,
        dept,
        data.get("designation", "").strip(),
        data.get("email", "").strip(),
        data.get("phone", "").strip(),
    )):
        errors.append("Enter at least one faculty detail.")
    if len(data.get("designation", "").strip()) > 80:
        errors.append("Designation must be at most 80 characters.")
    if len(data.get("email", "").strip()) > 120:
        errors.append("Email must be at most 120 characters.")
    if len(data.get("phone", "").strip()) > 30:
        errors.append("Phone must be at most 30 characters.")

    return errors


@employees_bp.route("")
@employees_bp.route("/")
def list_employees():
    user_id = current_user.id if current_user.is_authenticated else None
    search = request.args.get("q", "").strip()
    dept_filter = request.args.get("department", "").strip()
    status_filter = request.args.get("status", "active")

    query = Employee.query
    if user_id is not None:
        query = query.filter_by(user_id=user_id)

    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Employee.employee_name.ilike(like), Employee.employee_code.ilike(like))
        )
    if dept_filter:
        query = query.filter_by(department=dept_filter)

    employees = query.order_by(Employee.employee_code).all()

    # Use the department directory so newly created departments appear even
    # before the first faculty member is assigned to them. Include legacy names.
    directory_names = [d.name for d in _owned_department_query(user_id).order_by(Department.name).all()]
    legacy_q = Employee.query.with_entities(Employee.department).distinct()
    if user_id is not None:
        legacy_q = legacy_q.filter(Employee.user_id == user_id)
    departments = sorted(set(directory_names + [r.department for r in legacy_q.all() if r.department]), key=str.lower)

    return render_template(
        "employees/list.html",
        employees=employees,
        departments=departments,
        search=search,
        dept_filter=dept_filter,
        status_filter=status_filter,
    )


@employees_bp.route("/add", methods=["GET", "POST"])
def add_employee():
    user_id = current_user.id if current_user.is_authenticated else None
    if request.method == "POST":
        data = request.form
        errors = _validate_employee(data, user_id=user_id)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("employees/form.html", employee=None, form_data=data, departments=_owned_department_query(user_id).filter_by(is_active=True).all())

        emp = Employee(
            user_id=user_id,
            employee_code=data.get("employee_code", "").strip().upper() or None,
            employee_name=data.get("employee_name", "").strip() or None,
            department=data.get("department", "").strip() or None,
            designation=data.get("designation", "").strip() or None,
            email=data.get("email", "").strip() or None,
            phone=data.get("phone", "").strip() or None,
            is_active=True,
        )
        db.session.add(emp)
        db.session.commit()
        flash("Faculty/staff record added successfully.", "success")
        return redirect(url_for("employees.list_employees"))

    return render_template("employees/form.html", employee=None, form_data={}, departments=_owned_department_query(user_id).filter_by(is_active=True).all())


@employees_bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
def edit_employee(employee_id):
    user_id = current_user.id if current_user.is_authenticated else None
    emp = Employee.query.get_or_404(employee_id)
    if user_id is not None and emp.user_id is not None and emp.user_id != user_id:
        abort(404)

    if request.method == "POST":
        data = request.form
        errors = _validate_employee(data, employee_id=employee_id, user_id=user_id)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("employees/form.html", employee=emp, form_data=data, departments=_owned_department_query(user_id).filter_by(is_active=True).all())

        emp.employee_code = data.get("employee_code", "").strip().upper() or None
        emp.employee_name = data.get("employee_name", "").strip() or None
        emp.department = data.get("department", "").strip() or None
        emp.designation = data.get("designation", "").strip() or None
        emp.email = data.get("email", "").strip() or None
        emp.phone = data.get("phone", "").strip() or None
        db.session.commit()
        flash("Faculty/staff details updated.", "success")
        return redirect(url_for("employees.view_employee", employee_id=emp.employee_id))

    return render_template("employees/form.html", employee=emp, form_data=emp.to_dict(), departments=_owned_department_query(user_id).filter_by(is_active=True).all())


@employees_bp.route("/<int:employee_id>")
def view_employee(employee_id):
    user_id = current_user.id if current_user.is_authenticated else None
    emp = Employee.query.get_or_404(employee_id)
    if user_id is not None and emp.user_id is not None and emp.user_id != user_id:
        abort(404)

    records = Attendance.query.filter_by(employee_id=employee_id).order_by(Attendance.attendance_date.desc()).all()

    p = sum(1 for r in records if r.status == "Present")
    a = sum(1 for r in records if r.status == "Absent")
    l = sum(1 for r in records if r.status == "Leave")
    h = sum(1 for r in records if r.status == "Holiday")

    working_days = p + a + l
    total_days = working_days + h

    att_pct = calculate_attendance_percentage(p, a, l)
    abs_rate = calculate_absenteeism_rate(a, p, l)

    return render_template(
        "employees/detail.html",
        employee=emp,
        records=records,
        present_count=p,
        absent_count=a,
        leave_count=l,
        holiday_count=h,
        working_days=working_days,
        total_days=total_days,
        attendance_percentage=att_pct,
        absenteeism_rate=abs_rate,
    )


@employees_bp.route("/<int:employee_id>/deactivate", methods=["POST"])
def deactivate_employee(employee_id):
    user_id = current_user.id if current_user.is_authenticated else None
    emp = Employee.query.get_or_404(employee_id)
    if user_id is not None and emp.user_id is not None and emp.user_id != user_id:
        abort(404)

    emp.is_active = False
    db.session.commit()
    flash(f"Record for '{emp.employee_name}' has been deactivated. Historical records preserved.", "warning")
    return redirect(url_for("employees.list_employees"))


@employees_bp.route("/<int:employee_id>/reactivate", methods=["POST"])
def reactivate_employee(employee_id):
    user_id = current_user.id if current_user.is_authenticated else None
    emp = Employee.query.get_or_404(employee_id)
    if user_id is not None and emp.user_id is not None and emp.user_id != user_id:
        abort(404)

    emp.is_active = True
    db.session.commit()
    flash(f"Record for '{emp.employee_name}' has been reactivated.", "success")
    return redirect(url_for("employees.list_employees"))


# ---------------------------------------------------------------------------
# Department directory
# ---------------------------------------------------------------------------
def _owned_department_query(user_id):
    query = Department.query
    return query.filter_by(user_id=user_id) if user_id is not None else query.filter_by(user_id=None)


@employees_bp.route("/departments", methods=["GET", "POST"])
def departments():
    user_id = current_user.id if current_user.is_authenticated else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        description = request.form.get("description", "").strip()
        if not name or not code:
            flash("Department name and code are required.", "error")
        elif len(name) > 80 or len(code) > 20:
            flash("Department name or code is too long.", "error")
        elif _owned_department_query(user_id).filter(
            db.or_(Department.name.ilike(name), Department.code.ilike(code))
        ).first():
            flash("A department with that name or code already exists.", "error")
        else:
            db.session.add(Department(user_id=user_id, name=name, code=code, description=description))
            db.session.commit()
            flash(f"Department '{name}' added successfully.", "success")
            return redirect(url_for("employees.departments"))

    rows = _owned_department_query(user_id).order_by(Department.name.asc()).all()
    return render_template("employees/departments.html", departments=rows)


@employees_bp.route("/departments/<int:department_id>/toggle", methods=["POST"])
def toggle_department(department_id):
    user_id = current_user.id if current_user.is_authenticated else None
    department = _owned_department_query(user_id).filter_by(id=department_id).first_or_404()
    department.is_active = not department.is_active
    db.session.commit()
    flash("Department status updated.", "success")
    return redirect(url_for("employees.departments"))


# ---------------------------------------------------------------------------
# Bulk faculty import: upload -> preview/validate -> explicit confirmation.
# Supported formats: .xlsx, .xls, .csv. No AI is used to invent missing data.
# ---------------------------------------------------------------------------
IMPORT_COLUMNS = {
    "employee_code": (
        "employee code", "employee id", "employee id no", "employee number",
        "faculty code", "faculty id", "faculty id no", "staff id", "staff code",
        "staff number", "personnel id", "identifier", "id", "code",
    ),
    "employee_name": (
        "employee name", "faculty name", "staff name", "faculty member name",
        "full name", "name",
    ),
    "department": ("department", "department name", "department school", "dept", "school"),
    "email": ("email", "email address", "email id", "mail", "mail id"),
    "designation": ("designation", "job title", "position", "role", "title"),
    "phone": ("phone", "mobile", "mobile number", "contact", "contact number", "phone number"),
}


def _normalise_header(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _department_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _expanded_department_name(value):
    replacements = {
        "comp": "computer", "comps": "computer",
        "sci": "science", "engg": "engineering", "engr": "engineering",
        "tech": "technology", "math": "mathematics",
        "dept": "department",
    }
    ignored = {"and", "of", "the", "department", "dept", "school", "faculty", "college", "university"}
    words = _normalise_header(value).split()
    words = [replacements.get(word, word) for word in words]
    return "".join(word for word in words if word not in ignored)


def _department_acronyms(value):
    words = _normalise_header(value).split()
    ignored = {"and", "of", "the", "department", "dept", "school", "faculty", "college", "university"}
    words = [word for word in words if word not in ignored]
    if not words:
        return set()
    acronyms = {"".join(word[0] for word in words)}
    if len(words) > 2:
        acronyms.add("".join(word[0] for word in words[:2] + words[-1:]))
    return acronyms


def _match_department(value, departments):
    """Resolve exact names/codes or unambiguous initialisms; never fuzzy-auto-assign."""
    key = _department_key(value)
    if not key:
        return None, None
    expanded_key = _expanded_department_name(value)
    for department in departments:
        if key in {_department_key(department.name), _department_key(department.code)} or (
            expanded_key and expanded_key == _expanded_department_name(department.name)
        ):
            return department, "Exact name/code match"

    matches = [
        department for department in departments
        if key in _department_acronyms(department.name)
    ]
    if len(matches) == 1:
        return matches[0], f"Initials match {matches[0].name}"
    return None, None


def _suggest_department_code(value):
    words = _normalise_header(value).split()
    ignored = {"and", "of", "the", "department", "dept", "school", "faculty", "college", "university"}
    initials = "".join(word[0] for word in words if word not in ignored)
    if len(initials) >= 2:
        return initials[:20].upper()
    return re.sub(r"[^A-Za-z0-9]", "", str(value or ""))[:4].upper()


def _match_import_headers(values):
    """Map recognized headers to fields, rejecting ambiguous fuzzy matches."""
    candidates = {}
    for column_index, value in enumerate(values):
        header = _normalise_header(value)
        if not header:
            continue
        scores = {
            field: max(
                SequenceMatcher(None, header, _normalise_header(alias)).ratio()
                for alias in aliases
            )
            for field, aliases in IMPORT_COLUMNS.items()
        }
        field, score = max(scores.items(), key=lambda item: item[1])
        if score == 1 or (score >= 0.88 and len(header) >= 5):
            candidates.setdefault(field, []).append((score, column_index))

    mapping = {}
    confidence = {}
    for field, matches in candidates.items():
        matches.sort(reverse=True)
        if len(matches) == 1 or matches[0][0] > matches[1][0]:
            mapping[field] = matches[0][1]
            confidence[field] = "high" if matches[0][0] == 1 else "review"
    return mapping, confidence


def _prepare_import_frame(frame):
    """Find a recognizable header row, including when a file has a title/preamble."""
    if frame.empty:
        raise ValueError("No data rows were found in the uploaded file.")

    best = None
    for row_index in range(min(len(frame), 15)):
        values = frame.iloc[row_index].tolist()
        mapping, confidence = _match_import_headers(values)
        if not mapping:
            continue
        score = sum(1 for field in mapping if field in IMPORT_COLUMNS)
        if best is None or score > best[0]:
            best = (score, row_index, values, mapping, confidence)
    if best is None:
        raise ValueError(
            "Could not confidently identify any faculty fields. "
            "Add recognizable headers such as Faculty Name, Faculty ID, Department, Email, or Phone."
        )

    _, header_row, headers, column_mapping, confidence = best
    frame = frame.iloc[header_row + 1:].copy().reset_index(drop=True)
    if frame.empty:
        raise ValueError("The detected header has no faculty rows beneath it.")
    frame.columns = [str(value or "").strip() for value in headers]
    mapping = {field: frame.columns[index] for field, index in column_mapping.items()}
    frame.attrs["source_header_row"] = header_row
    frame.attrs["detected_columns"] = {
        field: {"column": mapping[field], "confidence": confidence[field]}
        for field in mapping
    }
    return frame, mapping


def _text_to_frame(text):
    """Turn extracted document text into a table using common delimiters/layouts."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("No selectable text was found. Scanned/image-only PDFs need OCR before import.")

    # Prefer explicit delimiters first; otherwise use aligned columns (2+ spaces).
    for delimiter in ("\t", "|", ";", ","):
        candidate = [line for line in lines if delimiter in line]
        if len(candidate) >= 2:
            try:
                frame = pd.read_csv(
                    io.StringIO("\n".join(candidate)), sep=delimiter, dtype=str,
                    engine="python", header=None,
                ).fillna("")
                if len(frame.columns) >= 2:
                    return frame
            except Exception:
                pass
    candidate = [line for line in lines if re.split(r"\s{2,}", line)]
    split_rows = [re.split(r"\s{2,}", line.strip()) for line in candidate]
    split_rows = [row for row in split_rows if len(row) >= 2]
    if len(split_rows) >= 2:
        width = max(len(row) for row in split_rows)
        split_rows = [row + [""] * (width - len(row)) for row in split_rows]
        return pd.DataFrame(split_rows).fillna("")
    raise ValueError("Could not detect a table. Make sure the document contains a clear header row and one faculty record per row.")


def _normalize_pdf_cell(value):
    """Repair words split across PDF table lines without joining separate words."""
    fragments = [
        re.sub(r"\s+", " ", fragment).strip()
        for fragment in str(value or "").replace("\r", "\n").split("\n")
    ]
    fragments = [fragment for fragment in fragments if fragment]
    if not fragments:
        return ""

    line_starters = {"and", "of", "the", "for", "in", "to", "with", "on", "at", "by", "or"}
    result = fragments[0]
    for fragment in fragments[1:]:
        first_word = fragment.split(" ", 1)[0].casefold()
        joins_previous = (
            result[-1].isdigit() and fragment[0].isdigit()
        ) or (
            result[-1].isalnum()
            and fragment[0].islower()
            and first_word not in line_starters
        )
        result += ("" if joins_previous else " ") + fragment
    return result


def _normalize_pdf_preview(preview):
    """Repair older saved previews generated before wrapped PDF cells were normalized."""
    if not preview.get("filename", "").lower().endswith(".pdf"):
        return preview

    for detection in preview.get("detected_columns", {}).values():
        detection["column"] = _normalize_pdf_cell(detection.get("column", ""))
    for row in preview.get("rows", []):
        for field in (
            "employee_code", "employee_name", "department", "department_source",
            "email", "designation", "phone",
        ):
            row[field] = _normalize_pdf_cell(row.get(field, ""))
    return preview


def _read_import_file(file_storage):
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if not raw:
        raise ValueError("The uploaded file is empty.")
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("File exceeds the 8 MB upload limit.")
    if filename.endswith(".csv"):
        frame = pd.read_csv(io.BytesIO(raw), dtype=str, encoding="utf-8-sig", header=None).fillna("")
    elif filename.endswith((".xlsx", ".xls")):
        frame = pd.read_excel(io.BytesIO(raw), dtype=str, header=None).fillna("")
    elif filename.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                table_rows = []
                for page in pdf.pages:
                    for table in (page.extract_tables() or []):
                        table_rows.extend(table)
                if table_rows and len(table_rows) >= 2:
                    frame = pd.DataFrame([
                        [_normalize_pdf_cell(cell) for cell in row]
                        for row in table_rows
                    ]).fillna("")
                else:
                    extracted = "\n".join(page.extract_text() or "" for page in pdf.pages)
                    frame = _text_to_frame(extracted).fillna("")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not read this PDF: {exc}") from exc
    elif filename.endswith(".docx"):
        try:
            from docx import Document
            document = Document(io.BytesIO(raw))
            if document.tables:
                table = document.tables[0]
                matrix = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                if len(matrix) < 2:
                    raise ValueError("The Word document table needs a header and at least one data row.")
                frame = pd.DataFrame(matrix).fillna("")
            else:
                frame = _text_to_frame("\n".join(p.text for p in document.paragraphs)).fillna("")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not read this Word document: {exc}") from exc
    elif filename.endswith((".txt", ".rtf")):
        text = raw.decode("utf-8-sig", errors="replace")
        if filename.endswith(".rtf"):
            text = re.sub(r"\\'[0-9a-fA-F]{2}|\\[a-zA-Z]+-?\d* ?|[{}]", " ", text)
        frame = _text_to_frame(text).fillna("")
    else:
        raise ValueError("Supported formats: Excel (.xlsx, .xls), CSV (.csv), PDF (.pdf), Word (.docx), and text (.txt/.rtf). PowerPoint is not supported.")
    frame, mapping = _prepare_import_frame(frame)
    return frame, mapping


def _render_import_preview(preview, token):
    preview = _normalize_pdf_preview(preview)
    rows = preview.get("rows", [])
    user_id = preview.get("user_id")
    departments = _owned_department_query(user_id).filter_by(
        is_active=True
    ).order_by(Department.name.asc()).all()
    return render_template(
        "employees/import_preview.html",
        rows=rows,
        filename=preview.get("filename", "Roster"),
        departments=departments,
        detected_columns=preview.get("detected_columns", {}),
        ready_count=sum(not row.get("errors") for row in rows),
        error_count=sum(bool(row.get("errors")) for row in rows),
        warning_count=sum(bool(row.get("warnings")) for row in rows),
        skipped_empty_rows=preview.get("skipped_empty_rows", []),
        token=token,
    )


@employees_bp.route("/import", methods=["GET", "POST"])
def import_employees():
    user_id = current_user.id if current_user.is_authenticated else None
    if request.method == "POST":
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            flash("Choose a supported faculty data file to upload.", "error")
            return redirect(url_for("employees.import_employees"))
        try:
            frame, mapping = _read_import_file(uploaded)
            rows = []
            active_departments = _owned_department_query(user_id).filter_by(is_active=True).order_by(Department.name.asc()).all()
            existing_codes = {
                e.employee_code.upper()
                for e in Employee.query.filter_by(user_id=user_id).all()
                if e.employee_code
            }
            seen_codes = set()
            skipped_empty_rows = []
            source_header_row = frame.attrs.get("source_header_row", 0)
            detected_columns = frame.attrs.get("detected_columns", {})
            for index, record in frame.iterrows():
                row_number = int(source_header_row) + int(index) + 2
                code = str(record.get(mapping.get("employee_code"), "") or "").strip().upper()
                name = str(record.get(mapping.get("employee_name"), "") or "").strip()
                dept_col = mapping.get("department")
                dept = str(record.get(dept_col, "") or "").strip() if dept_col else ""
                email = str(record.get(mapping.get("email"), "") or "").strip() if mapping.get("email") else ""
                designation = str(record.get(mapping.get("designation"), "") or "").strip() if mapping.get("designation") else ""
                phone = str(record.get(mapping.get("phone"), "") or "").strip() if mapping.get("phone") else ""
                values = {
                    "employee_code": code,
                    "employee_name": name,
                    "department": dept,
                    "designation": designation,
                    "email": email,
                    "phone": phone,
                }
                if not any(values.values()):
                    skipped_empty_rows.append(row_number)
                    continue

                matched_department, match_reason = _match_department(dept, active_departments)
                row_errors = []
                row_warnings = []
                for field, label in (
                    ("employee_code", "Faculty ID"),
                    ("employee_name", "Faculty name"),
                    ("department", "Department"),
                    ("designation", "Designation"),
                    ("email", "Email"),
                    ("phone", "Phone"),
                ):
                    if not values[field]:
                        row_warnings.append(f"{label} is missing and can be added later")
                if code and len(code) > 20:
                    row_errors.append("Faculty/employee ID must be at most 20 characters")
                if name and len(name) > 120:
                    row_errors.append("Faculty/staff name must be at most 120 characters")
                if designation and len(designation) > 80:
                    row_errors.append("Designation must be at most 80 characters")
                if email and len(email) > 120:
                    row_errors.append("Email must be at most 120 characters")
                if phone and len(phone) > 30:
                    row_errors.append("Phone must be at most 30 characters")
                if code and code in seen_codes:
                    row_errors.append("Duplicate ID within uploaded file")
                if code and code in existing_codes:
                    row_errors.append("ID already exists; edit it or approve updating the existing profile")
                if dept and not matched_department:
                    row_warnings.append("Department was not matched; it will be left unassigned unless changed to an existing department")
                if code:
                    seen_codes.add(code)
                rows.append({
                    "row": row_number, "employee_code": code, "employee_name": name,
                    "department": matched_department.name if matched_department else dept,
                    "department_source": dept,
                    "department_match": match_reason or "",
                    "existing_employee": code in existing_codes,
                    "update_existing_approved": False,
                    "email": email, "designation": designation,
                    "phone": phone, "errors": row_errors, "warnings": row_warnings,
                })
            rows.sort(key=lambda row: (
                (row["department"] or "").casefold(),
                (row["employee_name"] or "").casefold(),
                row["row"],
            ))
            token = uuid.uuid4().hex
            preview_dir = Path(current_app.instance_path) / "import_previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_path = preview_dir / f"{token}.json"
            preview_path.write_text(json.dumps({
                "user_id": user_id, "filename": uploaded.filename,
                "rows": rows, "detected_columns": detected_columns,
                "skipped_empty_rows": skipped_empty_rows,
            }), encoding="utf-8")
            session["faculty_import_token"] = token
            preview = {
                "user_id": user_id, "filename": uploaded.filename,
                "rows": rows, "detected_columns": detected_columns,
                "skipped_empty_rows": skipped_empty_rows,
            }
            return _render_import_preview(preview, token)
        except Exception as exc:
            db.session.rollback()
            flash(f"Import could not be prepared: {exc}", "error")
            return redirect(url_for("employees.import_employees"))

    return render_template("employees/import.html")


@employees_bp.route("/import/confirm", methods=["POST"])
def confirm_employee_import():
    user_id = current_user.id if current_user.is_authenticated else None
    token = session.get("faculty_import_token")
    if not token or not re.fullmatch(r"[a-f0-9]{32}", token):
        flash("Your import preview expired. Please upload the file again.", "error")
        return redirect(url_for("employees.import_employees"))
    preview_path = Path(current_app.instance_path) / "import_previews" / f"{token}.json"
    if not preview_path.is_file():
        flash("Your import preview expired. Please upload the file again.", "error")
        session.pop("faculty_import_token", None)
        return redirect(url_for("employees.import_employees"))
    try:
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        session.pop("faculty_import_token", None)
        flash("The import preview is damaged or expired. Please upload the file again.", "error")
        return redirect(url_for("employees.import_employees"))
    if preview.get("user_id") != user_id:
        abort(403)
    preview = _normalize_pdf_preview(preview)
    rows = preview.get("rows", [])
    if not rows:
        session.pop("faculty_import_token", None)
        preview_path.unlink(missing_ok=True)
        flash("No faculty records were imported because every data row was empty.", "warning")
        return redirect(url_for("employees.import_employees"))
    for index, row in enumerate(rows):
        for field in ("employee_code", "employee_name", "department", "email", "designation", "phone"):
            key = f"{field}_{index}"
            if key in request.form:
                row[field] = request.form.get(key, "").strip()
            if preview.get("filename", "").lower().endswith(".pdf"):
                row[field] = _normalize_pdf_cell(row.get(field, ""))
        row["employee_code"] = row.get("employee_code", "").upper()
        row["department_code"] = request.form.get(f"department_code_{index}", "").strip().upper()
        row["create_department_approved"] = request.form.get(f"create_department_{index}") == "1"
        row["update_existing_approved"] = request.form.get(f"update_existing_{index}") == "1"
        row["errors"] = []

    active_departments = _owned_department_query(user_id).filter_by(is_active=True).all()
    existing_employees = {
        employee.employee_code.upper(): employee
        for employee in Employee.query.filter_by(user_id=user_id).all()
        if employee.employee_code
    }

    seen_codes = set()
    for index, row in enumerate(rows):
        code = row.get("employee_code", "").strip().upper()
        name = row.get("employee_name", "").strip()
        department_name = row.get("department", "").strip()
        row["warnings"] = []
        if not code:
            row["employee_code"] = None
        elif len(code) > 20:
            row["errors"].append("Faculty/employee ID must be at most 20 characters")
        elif code in seen_codes:
            row["errors"].append("ID is duplicated within this uploaded file")
        elif code in existing_employees:
            row["existing_employee"] = True
            if not row["update_existing_approved"]:
                row["errors"].append(
                    "ID already exists; edit it or approve updating this existing profile"
                )
        else:
            row["existing_employee"] = False
        if code:
            seen_codes.add(code)
        if name and len(name) > 120:
            row["errors"].append("Name must be at most 120 characters")
        if department_name:
            matched_department, match_reason = _match_department(department_name, active_departments)
            if matched_department:
                row["department"] = matched_department.name
                row["department_match"] = match_reason
            else:
                row["department"] = None
                row["department_match"] = "Unmatched department left unassigned"
                row["warnings"].append("Department was not matched and was left unassigned")
        else:
            row["department"] = None
        row["employee_name"] = name or None
        row["designation"] = row.get("designation", "").strip() or None
        row["email"] = row.get("email", "").strip() or None
        row["phone"] = row.get("phone", "").strip() or None
        if not name:
            row["warnings"].append("Faculty name is missing and can be added later")
        if not department_name:
            row["warnings"].append("Department is missing and can be added later")
        for field, label in (
            ("employee_code", "Faculty ID"),
            ("designation", "Designation"),
            ("email", "Email"),
            ("phone", "Phone"),
        ):
            if not row.get(field):
                row["warnings"].append(f"{label} is missing and can be added later")
        if len(row.get("email") or "") > 120:
            row["errors"].append("Email must be at most 120 characters")
        if len(row.get("designation") or "") > 80:
            row["errors"].append("Designation must be at most 80 characters")
        if len(row.get("phone") or "") > 30:
            row["errors"].append("Phone must be at most 30 characters")

    if any(row["errors"] for row in rows):
        preview["rows"] = rows
        preview_path.write_text(json.dumps(preview), encoding="utf-8")
        flash("Review the highlighted rows. Nothing has been saved yet.", "error")
        return _render_import_preview(preview, token)

    try:
        updated = 0
        imported = 0
        for row in rows:
            values = {
                "employee_name": row.get("employee_name") or None,
                "department": row.get("department") or None,
                "email": row.get("email") or None,
                "designation": row.get("designation") or None,
                "phone": row.get("phone") or None,
            }
            employee_code = (row.get("employee_code") or "").strip().upper() or None
            existing_employee = existing_employees.get(employee_code) if employee_code else None
            if existing_employee:
                existing_employee.employee_name = values["employee_name"]
                existing_employee.department = values["department"]
                existing_employee.email = values["email"]
                existing_employee.designation = values["designation"]
                existing_employee.phone = values["phone"]
                updated += 1
            else:
                db.session.add(Employee(
                    user_id=user_id,
                    employee_code=employee_code,
                    **values,
                    is_active=True,
                ))
                imported += 1
        db.session.commit()
        session.pop("faculty_import_token", None)
        preview_path.unlink(missing_ok=True)
        flash(
            f"Import complete: added {imported} faculty/staff records and updated "
            f"{updated} approved existing profiles. Attendance history was preserved.",
            "success",
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Faculty import confirmation failed")
        flash("Import failed and no records were saved. Review duplicate IDs and department codes.", "error")
    return redirect(url_for("employees.list_employees"))
