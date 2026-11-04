"""
run.py — Main WSGI Entry Point for Employee Attendance Analysis System.
"""
import os
from dotenv import load_dotenv

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR, ".env"), override=False)

from app import create_app, db

app = create_app(os.environ.get("FLASK_ENV", "development"))


@app.cli.command("init-db")
def init_db_command():
    """Create missing tables and apply pending schema migrations."""
    from flask_migrate import upgrade

    with app.app_context():
        db.create_all()
        upgrade()
        print("Database tables created successfully.")


@app.cli.command("seed-data")
def seed_data_command():
    """Populate database with demonstration data and render charts."""
    import seed
    seed.seed_database()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    reloader = os.environ.get("FLASK_USE_RELOADER", "0") == "1"
    print(f"Starting Employee Attendance Analysis System on http://127.0.0.1:{port} (debug={debug}, reloader={reloader})")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=reloader)
