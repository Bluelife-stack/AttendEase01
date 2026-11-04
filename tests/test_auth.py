"""
tests/test_auth.py — Unit and integration tests for Authentication and Authorization.
Tests User Registration, Login (via username/email), Password Hashing, and Session Logout.
"""
import pytest
from types import SimpleNamespace

from authlib.integrations.flask_client import OAuth

from app import create_app, db
from app.models import AppSettings, User
from config import GOOGLE_REDIRECT_URI, load_environment


def test_user_password_hashing(app):
    """Test that passwords are automatically hashed with salted Werkzeug security."""
    with app.app_context():
        user = User(username="prof_john", email="john@mbu.edu", full_name="Prof. John Doe", role="Faculty Coordinator")
        user.set_password("SecurePass123!")
        db.session.add(user)
        db.session.commit()

        # Plain text password should NEVER be stored
        assert user.password_hash != "SecurePass123!"
        assert user.check_password("SecurePass123!") is True
        assert user.check_password("WrongPassword") is False


def test_user_registration_success(client, app):
    """Test successful user registration through the web interface."""
    response = client.post("/auth/register", data={
        "full_name": "Dr. Sarah Connor",
        "username": "sconnor",
        "email": "s.connor@mbu.edu",
        "role": "Faculty Coordinator",
        "password": "Password456!",
        "confirm_password": "Password456!",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Account created successfully" in response.data or b"sconnor" in response.data

    with app.app_context():
        user = User.query.filter_by(username="sconnor").first()
        assert user is not None
        assert user.full_name == "Dr. Sarah Connor"
        assert user.role == "Faculty Coordinator"
        assert user.check_password("Password456!") is True


def test_user_registration_mismatched_passwords(client, app):
    """Test that registration rejects mismatched password confirmation."""
    response = client.post("/auth/register", data={
        "full_name": "Dr. Sarah Connor",
        "username": "sconnor_test",
        "email": "test@mbu.edu",
        "role": "Faculty Coordinator",
        "password": "Password456!",
        "confirm_password": "DifferentPassword!",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Passwords do not match" in response.data


def test_login_success_with_username_and_email(client, app):
    """Test logging in with username and logging in with email."""
    with app.app_context():
        user = User(username="coordinator1", email="coord1@mbu.edu", full_name="Coordinator One", role="Faculty Coordinator")
        user.set_password("MyPassword789")
        db.session.add(user)
        db.session.commit()

    # 1. Login with username
    res1 = client.post("/auth/login", data={
        "identifier": "coordinator1",
        "password": "MyPassword789"
    }, follow_redirects=True)
    assert res1.status_code == 200
    assert b"Welcome back" in res1.data

    # Logout
    client.get("/auth/logout", follow_redirects=True)

    # 2. Login with email
    res2 = client.post("/auth/login", data={
        "identifier": "coord1@mbu.edu",
        "password": "MyPassword789"
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Welcome back" in res2.data


def test_login_invalid_credentials(client, app):
    """Test that invalid passwords or usernames return an error flash."""
    response = client.post("/auth/login", data={
        "identifier": "nonexistent_user",
        "password": "wrong_password"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Invalid credentials" in response.data


def test_google_oauth_environment_loading(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GOOGLE_CLIENT_ID=test-client-id\n"
        "GOOGLE_CLIENT_SECRET=test-client-secret\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    assert load_environment(env_file)
    configured_app = create_app("testing")

    assert configured_app.config["GOOGLE_CLIENT_ID"] == "test-client-id"
    assert configured_app.config["GOOGLE_CLIENT_SECRET"] == "test-client-secret"
    assert configured_app.config["GOOGLE_REDIRECT_URI"] == GOOGLE_REDIRECT_URI


def test_google_missing_credentials_are_reported(client, app):
    app.config["GOOGLE_CLIENT_ID"] = None
    app.config["GOOGLE_CLIENT_SECRET"] = None

    login_response = client.get("/auth/login")
    register_response = client.get("/auth/register")

    assert b"Continue with Google" in login_response.data
    assert b"Sign up with Google" in register_response.data
    assert b"add your Google OAuth client ID and secret" in login_response.data
    assert b"add your Google OAuth client ID and secret" in register_response.data

    response = client.get("/auth/google", follow_redirects=True)
    assert response.status_code == 200
    assert b"Google sign-in is not configured" in response.data


def _configure_test_google(app):
    oauth = OAuth(app)
    app.extensions["oauth"] = oauth
    oauth.register(
        name="google",
        client_id="test-client-id",
        client_secret="test-client-secret",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        access_token_url="https://oauth2.googleapis.com/token",
        client_kwargs={"scope": "openid email profile"},
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
    return oauth


def test_google_authorization_redirect_and_state(client, app):
    _configure_test_google(app)

    response = client.get("/auth/google")
    assert response.status_code == 302
    location = response.headers["Location"]
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["redirect_uri"] == [GOOGLE_REDIRECT_URI]
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["test-client-id"]
    assert query.get("state", [""])[0]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]


def test_google_callback_rejects_invalid_state(client, app):
    _configure_test_google(app)

    start = client.get("/auth/google")
    assert start.status_code == 302
    response = client.get(
        "/auth/google/callback?state=invalid-state&code=test-code",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"OAuth state was invalid" in response.data


def test_google_callback_logs_in_existing_user(client, app, monkeypatch):
    with app.app_context():
        user = User(
            username="existing_google",
            email="existing@mbu.edu",
            full_name="Existing User",
            role="Faculty Coordinator",
        )
        user.set_password("ExistingPassword123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    google = SimpleNamespace(
        authorize_access_token=lambda: {
            "userinfo": {
                "email": "EXISTING@MBU.EDU",
                "email_verified": True,
                "name": "Google Profile Name",
            }
        }
    )
    monkeypatch.setitem(app.extensions, "oauth", SimpleNamespace(create_client=lambda name: google))

    response = client.get("/auth/google/callback?state=mocked&code=mocked", follow_redirects=True)

    assert response.status_code == 200
    assert b"Welcome, Existing User." in response.data
    with client.session_transaction() as session:
        assert session.get("_user_id") == str(user_id)
    with app.app_context():
        assert User.query.count() == 1


def test_google_callback_registers_new_user_with_institution_settings(client, app, monkeypatch):
    google = SimpleNamespace(
        authorize_access_token=lambda: {
            "userinfo": {
                "email": "new.faculty@mbu.edu",
                "email_verified": True,
                "name": "New Faculty",
            }
        }
    )
    monkeypatch.setitem(app.extensions, "oauth", SimpleNamespace(create_client=lambda name: google))

    response = client.get("/auth/google/callback?state=mocked&code=mocked", follow_redirects=True)

    assert response.status_code == 200
    assert b"Welcome, New Faculty." in response.data
    with app.app_context():
        user = User.query.filter_by(email="new.faculty@mbu.edu").one()
        settings = AppSettings.query.filter_by(user_id=user.id).one()
        assert user.username == "new.faculty"
        assert user.role == "Faculty Coordinator"
        assert user.check_password("not-the-generated-password") is False
        assert settings.institution_name == "New Faculty's Organization"
        assert settings.institution_type == "University / College"
