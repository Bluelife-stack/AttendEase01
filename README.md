# Employee & Faculty Attendance Analysis System (AttendEase)

A Flask web application for managing employee/faculty records, recording daily attendance, calculating attendance percentages, and generating reports and charts with Pandas, NumPy, and Matplotlib.

## Features

- User registration and login with hashed passwords
- Employee/faculty record management
- Daily attendance with Present, Absent, Leave, and Holiday statuses
- Database constraint to prevent duplicate attendance for the same employee and date
- Attendance percentage and absenteeism analytics
- Reports, chart visualizations, and configurable institutional labels
- SQLite for local development; PostgreSQL supported for deployment

## Technology stack

- **Frontend:** HTML, CSS, JavaScript, Jinja templates
- **Backend:** Python, Flask, Flask-Login, Flask-WTF
- **Database:** SQLAlchemy; SQLite locally and PostgreSQL for hosted deployment
- **Analysis/visualization:** Pandas, NumPy, Matplotlib
- **Deployment:** Gunicorn; Render-compatible

## Run locally (Windows PowerShell)

Use Python 3.11 or 3.12.

```powershell
cd attendease
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app run.py init-db
python run.py
```

Open http://127.0.0.1:5000.

On macOS/Linux, create and activate the virtual environment with `python3 -m venv .venv` and `source .venv/bin/activate`; then install requirements and run the same Flask commands.

### Optional demo data

`seed.py` populates sample employees, attendance records, and charts. It refuses to seed a database that already contains users, employees, attendance, or settings; use a separate, empty local database for demo data. It does not delete existing tables or data. For a fresh local demo database, run:

```powershell
python seed.py
```

The demo accounts created by the seed script are `admin` / `admin123` and `coordinator` / `coord123`. They are public demonstration credentials: change/delete them and never use them for a real deployment.

## Tests

```powershell
python -m pytest tests -v
```

Run the tests in your own environment before submission. Test results have not been certified as passing as part of this packaging step.

## Deploy to Render

1. Push the contents of this folder (the files inside `attendease`, not the outer ZIP folder) to your GitHub repository.
2. In Render, create a **PostgreSQL** database. Copy its **Internal Database URL** for a web service in the same Render region.
3. Create a **Web Service** and connect the GitHub repository.
4. Set the service root directory to `.` if the repository root contains `run.py`, `app/`, and `requirements.txt`.
5. Use these settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn run:app`
6. Add environment variables in Render:
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` = a long, randomly generated secret value (do not commit it)
   - `DATABASE_URL` = the PostgreSQL Internal Database URL
   - `ATTENDANCE_THRESHOLD` = `75.0`
7. After the first deployment, open the Render Shell for the web service and initialize the database:

   ```bash
   flask --app run.py init-db
   ```

8. If you want sample data, run `python seed.py` only against a brand-new, empty database. It will refuse to run if customer data already exists.
9. Open `https://YOUR-SERVICE.onrender.com/health` and confirm the response reports `"status":"healthy"` and `"database":"connected"`.

**Persistence:** Do not rely on the local SQLite file on a hosted service. Use PostgreSQL for persistent records. Keep `SECRET_KEY` and database credentials in Render environment variables, never in GitHub.

## Repository hygiene

`.gitignore` excludes virtual environments, Python caches, test artifacts, local databases, and `.env` secrets. Commit `.env.example`, but never commit `.env`.


## Added department directory and bulk faculty import

- Open **Departments** from the sidebar to create department names and codes.
- Add faculty from the directory; department is selected from the department list.
- Use **Bulk Import** to upload `.xlsx`, `.xls`, `.csv`, `.pdf`, `.docx`, `.txt`, or `.rtf` files (8 MB maximum). Faculty ID, name, department, designation, email, and phone are optional on import; empty rows are skipped, and unmatched departments are left unassigned. Missing details can be completed later from the faculty edit page.
- The importer scans the first 15 rows for faculty ID and name headers, recognizes common header aliases and reordered columns, matches department names/codes and common long-form/initialism variants, and sorts the review preview by department and name. Approximate header matches are marked for review; ambiguous required columns are rejected instead of guessed.
- Edit extracted faculty fields directly in the review preview before confirming. Duplicate IDs require explicit approval to update the existing profile; its linked attendance history is preserved. Data-integrity errors block the import, while missing-field warnings do not.
- Existing department names/codes are matched against the department directory. Unmatched departments are imported as unassigned; manage departments separately when needed.
- PDF, Word, and text files must contain selectable text in a clear table-like layout with a header row. Scanned/image-only PDFs are not OCR processed; convert them to searchable text or use Excel/CSV. PowerPoint is not supported.
- PDF table cells that wrap words across lines are normalized during import. Departments still need to exist in the account's directory or be explicitly approved for creation in the review step.
- Google sign-in and Google account registration use the same **Continue with Google** flow. A verified Google email signs in an existing account or creates a new account automatically. Configure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` (local) or the hosting environment (Render). In Google Cloud Console, enable the Google Identity / OAuth consent configuration, create an OAuth Client ID for a Web application, and add these Authorized redirect URIs exactly:
  - `http://127.0.0.1:5000/auth/google/callback` (local)
  - `https://YOUR-DOMAIN/auth/google/callback` (deployed)
  Restart the Flask server after setting credentials. Without real credentials and the exact redirect URI, Google authentication cannot complete.

### Database schema updates

Back up the database before applying schema changes. `init-db` creates missing tables and applies pending migrations:

```bash
flask --app run.py init-db
```

For an existing deployment, this migration makes faculty ID, name, department, and designation nullable. It uses an Alembic batch migration that preserves employee rows, indexes, and linked attendance history.

## AttendEase PRO visual edition

This version includes a unified landing page and application theme combining a restrained glass surface treatment, rounded enterprise cards, a compact top navigation dock, and an interactive monthly attendance trend rendered from the signed-in account's saved attendance summaries. The landing-page dashboard artwork is explicitly illustrative; it does not display invented customer metrics.

The Help Desk is available from the application top bar. Configure `SUPPORT_EMAIL` in `.env` or the hosting environment to enable direct email contact. If it is not configured, the Help Desk displays self-service guidance and tells users to contact their institution's administrator.

### Environment and security

- This ZIP intentionally does **not** include `.env` because it may contain OAuth client secrets. Copy `.env.example` to `.env` and enter your own credentials locally.
- `.env.example` contains placeholders only. Create OAuth credentials in your own Google Cloud project, use the configured local callback URI, and never put real credentials in the example file. If a client secret was previously shared or committed, revoke it and create a replacement before use.
- Do not commit `.env`, local database files, uploaded customer data, or generated private exports to GitHub.
- The included SQLite database is retained to preserve the data present in the source ZIP. Back it up before migration or deployment. For a public repository, keep the database out of Git and transfer it securely to the deployment database.

### Tenant model limitation to verify before production

The current source scopes faculty, departments, and settings by **user account ID**. It does not yet implement the previously discussed institution entity with multiple user memberships sharing one institution workspace. The existing account-level isolation tests should not be interpreted as proof of shared institution-level tenancy or role-based institution membership. Do not advertise shared multi-user institution workspaces until that architecture and its migration are implemented and tested.
