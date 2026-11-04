# AttendEase — Alternative UI Redesign Master Prompt

You are a senior product designer and Flask engineer. Create an alternative visual design for this existing AttendEase application using the supplied visual references: a premium minimalist SaaS dashboard, warm white surfaces, subtle mint gradients, rounded cards, dark pill-shaped primary actions, restrained green status colors, and clean typography.

## Non-negotiable: preserve the application
- First inspect the complete repository, route map, templates, models, migrations/database setup, JavaScript, and CSS.
- Treat the current project as the source of truth. This is a presentation redesign, not a rewrite.
- Preserve every existing route, endpoint name, form method/action, input name, CSRF token, permission check, session behavior, database model/relationship, calculation, import/export workflow, and JavaScript interaction.
- Do not replace real data with demo data, remove sections, rename routes, or change business logic.
- Do not expose `.env` secrets or commit credentials.
- Prefer additive/reusable CSS and small template changes. Avoid unnecessary dependencies.

## Visual direction
- Use a warm off-white page canvas with extremely subtle peach and pale-mint ambient gradients.
- Use white cards with generous spacing, 18–24px radii, delicate borders, and restrained shadows.
- Use a white/light sidebar with dark charcoal active navigation pills and understated icons.
- Use near-black charcoal primary buttons with white text; light outlined secondary buttons; restrained green success states; muted amber/red for warnings/errors.
- Use readable modern typography, clear hierarchy, consistent spacing, accessible contrast, visible focus states, and polished hover states.
- Tables should have quiet headers, comfortable row height, subtle dividers, and rounded status pills.
- Forms should have soft neutral fields, clear labels, consistent validation and focus rings.
- Do not copy unrelated sales/product names or numbers from the reference images. Apply only their visual language to AttendEase's actual content.

## Apply consistently
Redesign every existing page, including login/register, landing, dashboard, departments, faculty/staff list/detail/forms, bulk import and import preview, attendance marking/history/edit/session detail, reports/charts/print, settings, and error pages. Keep all existing menu items and their order. Make desktop, tablet, and mobile layouts usable; do not hide essential actions on small screens.

## Dashboard
Retain the existing real KPIs, attendance calculations, reports, and charts. Improve their visual hierarchy and card layout without fabricating data or changing calculations.

## Quality gates
1. Compare route maps before and after; no existing route may disappear.
2. Check every template for valid Jinja syntax.
3. Run the project's existing automated tests and report exact results.
4. Test login/logout, registration, navigation, department CRUD, faculty CRUD, import preview/confirm, attendance workflows, reports, settings, and exports where test credentials/data permit.
5. Inspect browser console and Flask logs; fix errors introduced by the redesign.
6. Verify responsive behavior at desktop, tablet, and phone widths.
7. Report any checks that could not be run. Never claim untested functionality is verified.

## Deliverables
- Complete runnable project, not a screenshot or static prototype.
- Exact list of changed files and explanation of UI-only changes.
- Test report with passed/failed/not-run status.
- A ZIP archive excluding `.git`, virtual environments, caches, local databases containing user data, and `.env` secrets.

The result must remain AttendEase: same sections, same behavior, same backend, with a coherent premium soft-mint SaaS appearance.
