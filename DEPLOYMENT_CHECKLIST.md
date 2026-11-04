# Submission / Deployment Checklist

- [ ] GitHub repository contains `run.py`, `app/`, `config.py`, `requirements.txt`, `Procfile`, `seed.py`, `tests/`, and documentation at repository root.
- [ ] No `.env`, passwords, database dumps, `.git/` folder, `.venv/`, `__pycache__/`, or `.pytest_cache/` committed.
- [ ] GitHub Actions or local test run completes successfully (`python -m pytest tests -v`).
- [ ] Render Web Service uses `pip install -r requirements.txt` and `gunicorn run:app`.
- [ ] Render environment includes `FLASK_ENV=production`, a unique `SECRET_KEY`, and PostgreSQL `DATABASE_URL`.
- [ ] Database initialized with `flask --app run.py init-db`.
- [ ] `/health` returns healthy status and database connected.
- [ ] Log in, create an employee, record attendance, and open reports to smoke-test the deployed app.
- [ ] If using the demo seed, only run it against a new/disposable database because the current script drops existing tables.
- [ ] Replace demo credentials or remove demo users before sharing a public production instance.

- [ ] Before applying database schema migrations, take a database backup. Run `flask --app run.py init-db` to create missing tables and apply pending migrations.
