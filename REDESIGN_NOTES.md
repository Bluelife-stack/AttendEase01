# AttendEase PRO visual edition

## Design direction
- Swiss-style layout and typography for legibility.
- Selective frosted-glass surfaces for navigation and large panels; forms and tables retain high-contrast solid surfaces.
- Compact top navigation dock instead of the persistent left sidebar. Existing Flask endpoint names and page workflows are retained.
- Graphite controls, restrained emerald/mint accents, muted supporting colours, rounded cards and low-contrast borders.
- Responsive layouts and reduced-motion support.

## Functional changes
- Replaced the basic landing page with a matching product landing page. Preview values are placeholders and clearly labelled illustrative; no fabricated customer KPI is presented as real.
- Added a monthly attendance trend on the dashboard. Its values come from `get_monthly_attendance_summary` for the signed-in account and support metric and date-range selection without a third-party chart dependency.
- Added a Help Desk self-service page and optional `SUPPORT_EMAIL` environment setting.

## Safety and scope
- Existing attendance, employee, department, report, import, authentication, OAuth and database service code was retained except for passing the monthly summary to the dashboard.
- The SQLite database included in the source archive is preserved in this output.
- `.env` was deliberately excluded from the distributable ZIP. Configure credentials from `.env.example`.
- Existing code uses per-user account scoping; institution-level shared memberships are not implemented by this visual edition.

## Validation
- Python AST syntax and Jinja template compilation checked.
- Browser visual QA and full pytest suite require installing `requirements.txt` and running the application in the target environment. They are not claimed as completed here.
