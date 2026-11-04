"""
app/routes/auth.py — Authentication Blueprint.
Provides Sign In (Login), Sign Up (Register), Logout, and Show/Hide Password functionality.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask import current_app
from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from werkzeug.security import generate_password_hash
import os
from app import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


def _create_user_settings(user):
    """Create the same isolated institution defaults for password and Google sign-up."""
    from app.models import AppSettings

    faculty_role = "Faculty" in user.role or "Department" in user.role
    return AppSettings(
        user_id=user.id,
        app_name=f"{user.full_name}'s Attendance Portal",
        institution_name=f"{user.full_name}'s Organization",
        institution_type="University / College" if faculty_role else "Corporate Enterprise",
        employee_label_singular="Faculty Member" if faculty_role else "Employee",
        employee_label_plural="Faculty & Staff" if faculty_role else "Employees",
        department_label="School / Department" if faculty_role else "Department",
        id_code_label="Faculty ID" if faculty_role else "Employee ID",
        attendance_threshold=75.0,
        academic_year="2026-2027",
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Sign In interface for existing users."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()  # username or email
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        if not identifier or not password:
            flash("Please enter both username/email and your password.", "error")
            return render_template("auth/login.html", identifier=identifier)

        # Allow logging in with either username or email
        user = User.query.filter(
            db.or_(User.username == identifier, User.email == identifier.lower())
        ).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials. Please verify your username and password.", "error")
            return render_template("auth/login.html", identifier=identifier)

        if not user.is_active:
            flash("Your account has been deactivated. Please contact the administrator.", "warning")
            return render_template("auth/login.html", identifier=identifier)

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.full_name}!", "success")

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html", identifier="")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Sign Up interface for new users / coordinators / administrators."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "Faculty Coordinator").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not username:
            errors.append("Username is required.")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        elif User.query.filter_by(username=username).first():
            errors.append(f"Username '{username}' is already taken.")

        if not email:
            errors.append("Email address is required.")
        elif "@" not in email:
            errors.append("Please enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append(f"Email '{email}' is already registered.")

        if not password:
            errors.append("Password is required.")
        elif len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        elif password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template(
                "auth/register.html",
                form_data={"full_name": full_name, "username": username, "email": email, "role": role}
            )

        # Create the account and its initial settings together.
        new_user = User(
            full_name=full_name,
            username=username,
            email=email,
            role=role,
            is_active=True
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        db.session.add(_create_user_settings(new_user))
        db.session.commit()

        login_user(new_user)
        flash(f"Account created successfully! Logged in as {new_user.full_name} ({new_user.role}).", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html", form_data={})


@auth_bp.route("/logout")
def logout():
    """Logs out the current user."""
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/google")
def google_login():
    """Start the Google OpenID Connect authorization flow."""
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        flash(
            "Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in "
            "the project .env file, then restart the app.",
            "error",
        )
        return redirect(url_for("auth.login"))

    try:
        oauth = current_app.extensions.get("oauth")
        google = oauth.create_client("google") if oauth else None
        if google is None:
            raise RuntimeError("Google OAuth client was not initialized")
        return google.authorize_redirect(current_app.config["GOOGLE_REDIRECT_URI"])
    except Exception as exc:
        current_app.logger.error("Google OAuth authorization could not start (%s)", type(exc).__name__)
        flash("Google sign-in could not be started. Check the OAuth configuration and try again.", "error")
        return redirect(url_for("auth.login"))


@auth_bp.route("/google/callback")
def google_callback():
    """Verify Google's identity response and sign in an existing account or create one."""
    oauth = current_app.extensions.get("oauth")
    google = oauth.create_client("google") if oauth else None
    if google is None:
        flash("Google sign-in is not configured. Set the OAuth credentials and restart the app.", "error")
        return redirect(url_for("auth.login"))

    try:
        token = google.authorize_access_token()
        info = token.get("userinfo") or google.userinfo()
        email = (info.get("email") or "").strip().lower()
        if not email or info.get("email_verified") is not True:
            flash("Google did not provide a verified email address.", "error")
            return redirect(url_for("auth.login"))
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user is None:
            base = (email.split("@")[0] or "user")[:70]
            username = base
            suffix = 1
            while User.query.filter_by(username=username).first():
                username = f"{base}{suffix}"
                suffix += 1
            full_name = (info.get("name") or base).strip()[:120]
            user = User(
                full_name=full_name,
                username=username,
                email=email,
                role="Faculty Coordinator",
                is_active=True,
                password_hash=generate_password_hash(os.urandom(32).hex()),
            )
            db.session.add(user)
            db.session.flush()
            db.session.add(_create_user_settings(user))
            db.session.commit()
        if not user.is_active:
            flash("Your account is deactivated. Contact the administrator.", "warning")
            return redirect(url_for("auth.login"))
        login_user(user)
        flash(f"Welcome, {user.full_name}.", "success")
        return redirect(url_for("main.dashboard"))
    except MismatchingStateError:
        db.session.rollback()
        flash("Google sign-in could not be verified because the OAuth state was invalid. Please try again.", "error")
        return redirect(url_for("auth.login"))
    except OAuthError as exc:
        db.session.rollback()
        current_app.logger.error("Google OAuth callback failed (%s)", type(exc).__name__)
        flash("Google sign-in could not be verified. Please try again or use email and password.", "error")
        return redirect(url_for("auth.login"))
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("Google OAuth callback failed unexpectedly (%s)", type(exc).__name__)
        flash("Google sign-in failed. Please try again or use email and password.", "error")
        return redirect(url_for("auth.login"))
