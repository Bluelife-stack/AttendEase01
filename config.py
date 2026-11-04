"""
config.py — AttendEase configuration loader.
Reads from environment variables (.env) with safe defaults.
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:5000/auth/google/callback",
)


def load_environment(env_file=None):
    """Load this project's environment file without overriding process settings."""
    return load_dotenv(
        dotenv_path=env_file or os.path.join(BASE_DIR, ".env"),
        override=False,
    )


load_environment()


class Config:
    # Security
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = GOOGLE_REDIRECT_URI
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "").strip()

    # Database — supports SQLite locally and PostgreSQL on Render via DATABASE_URL
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("postgres://"):
        # Render uses postgres://, SQLAlchemy needs postgresql://
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'attendease.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    SQLALCHEMY_ECHO = False

    # Application settings
    APP_NAME = os.environ.get("APP_NAME", "AttendEase")
    ATTENDANCE_THRESHOLD = float(os.environ.get("ATTENDANCE_THRESHOLD", "75.0"))
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # WTForms CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600


class DevelopmentConfig(Config):
    FLASK_DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    FLASK_DEBUG = False
    WTF_CSRF_ENABLED = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
