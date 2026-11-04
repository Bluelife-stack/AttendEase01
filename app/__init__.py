"""
app/__init__.py — Application Factory with Flask-Login & Institutional Terminology Injection.
"""
import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()


def create_app(config_name: str = None):
    from config import config_map, load_environment

    load_environment()

    app = Flask(__name__, instance_relative_config=True)

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")
    cfg = config_map.get(config_name, config_map["default"])
    if config_name == "production" and not os.environ.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY must be set in the environment for production. "
            "Configure it in your hosting provider's environment variables."
        )
    app.config.from_object(cfg)
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", app.config.get("GOOGLE_CLIENT_ID"))
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get(
        "GOOGLE_CLIENT_SECRET", app.config.get("GOOGLE_CLIENT_SECRET")
    )
    app.config["GOOGLE_REDIRECT_URI"] = os.environ.get(
        "GOOGLE_REDIRECT_URI",
        app.config["GOOGLE_REDIRECT_URI"],
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = config_name == "production"

    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from authlib.integrations.flask_client import OAuth

    oauth = OAuth(app)
    if app.config["GOOGLE_CLIENT_ID"] and app.config["GOOGLE_CLIENT_SECRET"]:
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
            redirect_uri=app.config["GOOGLE_REDIRECT_URI"],
        )
    app.extensions["oauth"] = oauth

    # Configure Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to access this section."
    login_manager.login_message_category = "info"

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.employees import employees_bp
    from app.routes.attendance import attendance_bp
    from app.routes.reports import reports_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(employees_bp, url_prefix="/employees")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(settings_bp, url_prefix="/settings")

    # Health check route
    @app.route("/health")
    def health():
        from flask import jsonify
        try:
            db.session.execute(db.text("SELECT 1"))
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {e}"
        return jsonify({
            "status": "healthy",
            "project": "Employee & Faculty Attendance Analysis System",
            "database": db_status
        })

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    # Global context processor for university / institution dynamic customization
    @app.context_processor
    def inject_institutional_context():
        from flask_login import current_user
        from app.models import AppSettings
        user_id = current_user.id if (current_user and current_user.is_authenticated) else None
        settings = AppSettings.get_settings(user_id=user_id)
        return {
            "config_settings": settings,
            "app_name": settings.app_name if settings else "StaffPulse Attendance",
            "institution_name": settings.institution_name if settings else "Mohan Babu University (MBU)",
            "institution_type": settings.institution_type if settings else "University / College",
            "emp_label_singular": settings.employee_label_singular if settings else "Faculty / Employee",
            "emp_label_plural": settings.employee_label_plural if settings else "Faculty & Staff",
            "dept_label": settings.department_label if settings else "Department / School",
            "id_code_label": settings.id_code_label if settings else "Faculty / Employee ID",
            "threshold": settings.attendance_threshold if settings else 75.0,
            "academic_year": settings.academic_year if settings else "2026-2027",
            "current_year": 2026,
            "google_auth_enabled": bool(app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET")),
            "support_email": app.config.get("SUPPORT_EMAIL", ""),
        }

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app
