# Decision Log — Embassy Portal

## 2026-08-10 — Embassy Forms Library (staff-managed public downloads)

- **Domain module, not monolith:** all logic in `app/domains/forms/`
  (core/schema/storage/audit/service/routes), mirroring `ads`. `server.py` got
  ~90 additive lines (guarded import, `FEATURE_FORMS_LIBRARY` flag, `configure()`,
  `ensure_schema()` in `init_db()`, GET/POST dispatch tails, `FORMS_URL` +
  homepage fragments in `public_route_context`, `render_main_app_html`).
- **PDF only (owner decision).** DOC/DOCX deliberately unsupported: DOCX is a
  ZIP container so content validation is far weaker, many citizens cannot open
  it on a phone, and the Embassy wants a fixed non-editable document.
- **Nothing is ever hard-deleted (owner decision).** `ARCHIVED` is terminal but
  reversible; there is no delete route and no delete function. Superseded files
  stay on disk and gain an `embassy_form_versions` row, so a mistaken
  "Replace File" is recoverable. A genuine erasure is a deliberate `sqlite3`
  action in the Render shell, not a button.
- **Two public surfaces, deliberately different prefixes:**
  `/api/public/forms` is JSON under `/api/` so `_cors_headers_if_api()` applies
  the CORS allowlist automatically; `/forms/download/<id>` is NOT under `/api/`
  because file responses carry no CORS headers and must be reached by top-level
  navigation (a plain `<a href>`), never `fetch()`. Same reasoning as
  `/ads/media/*`. Both React and the backend template use anchors.
- **Public download URL is stable across replacement** — `/forms/download/<id>`
  never changes, so printed/bookmarked links survive a new revision. That is why
  the download cache is `max-age=300`, NOT the `immutable` used for ad media
  (whose URL carries a unique generated name).
- **Downloads are always `Content-Disposition: attachment`**, so a crafted PDF
  never renders inside the Embassy's own origin. PDFs are NOT scanned for
  `/JavaScript` or `/OpenAction`: real government forms are frequently fillable
  AcroForms whose field validation is JavaScript, so that check would reject
  legitimate documents. Transport-level mitigation instead.
- **Own byte-exact multipart reader** (`storage.extract_upload`). The shared
  `server.py:extract_multipart_upload` ends with `rest.rstrip(b'\r\n')`, which
  strips *every* trailing CR/LF rather than the single delimiter CRLF — any file
  ending in a newline (most PDFs, `%%EOF\n`) is silently truncated. Harmless for
  the OCR paths that use it; unacceptable when the file is re-served and a
  digital signature would break. **The shared helper was deliberately left
  alone** — it is load-bearing for Iraq/MOFA, hostel and ads uploads.
- **Roles enforced in-handler, not by route RBAC.** `FULL_SYSTEM_ROLES` contains
  admin, operator AND operator_special, so `can_access_admin_route()` admits all
  three. `MANAGE_ROLES = {admin, operator}` (upload/edit/replace/publish/reorder);
  `ADMIN_ROLES = {admin}` (archive/restore, categories, audit trail).
  `operator_special` is excluded — the dashboard already hides every
  `[data-cwa-nav]` button from it.
- **Categories are data, not an enum** (`embassy_form_categories`, seeded with 7
  rows). The brief requires staff to run the library without a developer; a
  hard-coded list fails on the first new consular category. Re-seeding only ever
  inserts a missing slug, so an admin rename is never reverted on restart.
- **XSS:** the public page injects one JSON payload and builds its DOM with
  `textContent` only; React renders staff text as text nodes. Staff-entered
  content is never placed in an HTML token — `render_template_with_context()`
  escapes nothing.
- **Audit:** dedicated append-only `embassy_form_audit` (matching every recent
  module), plus ONE summary row in the global `audit_log` for publish and
  archive only. Public downloads are counted (`download_count`) but never
  individually logged — that would be a high-volume table of IP-adjacent data
  with no operational value.
- **Storage:** `/data/embassy_forms/` via the standard
  `RENDER_DISK if exists else PROJECT_ROOT` fallback. NOT `/var/data` — that path
  does not exist in this deployment (it survives only as a generic example in
  `TOTP_2FA_Implementation_Plan.md`).
- **Kill-switch:** `FEATURE_FORMS_LIBRARY=0` → all routes 404, nav hidden, and the
  homepage card/nav links vanish. The card is injected from `server.py` via
  `__FORMS_CARD__` / `__FORMS_NAV_LINK__` / `__FORMS_MOBILE_LINK__` rather than
  hard-coded in `cwa_home.html`, precisely so the flag removes it cleanly instead
  of leaving a link to a 404.
- **Fixed while here:** `/dashboard` rendered `MAIN_APP` without substituting
  `__ADS_NAV_BUTTON__`, so that literal string was visible in the sidebar. Both
  render sites now go through `render_main_app_html()`.
- Verified 2026-08-10: `py_compile` clean; `routes.py` 70/70 (16 new CHECKS);
  `forms_module.py` 107/107; `forms_workflow.py` 89/89 (localhost E2E);
  `ads_module` 37, `ads_public_api` 43, `ads_workflow` 77, `hostel_module` 21 —
  all identical to a stashed pre-change baseline; frontend `typecheck` 11 errors
  (all pre-existing in `AdminNursesAccommodationPage.tsx`, unchanged), `build`
  green, `lint` clean, `npm run smoke` 5/5 suites green. Flag-off boot verified
  forms-free; upload → restart → download verified byte-identical.
- Route inventory NOT appended (matches hostel/ads precedent — the baseline is a
  no-deletion safety net; all 408 literal entries still resolve).
- **NOT deployed, NOT committed.** Deploy order when approved: backend first,
  then push the frontend to BOTH `embassy-portal-new-update` and
  `community-welfare-ui-update` (cwakuwait.com deploys from the latter only).
  `backup_onedrive.sh` still needs a Step 3c for `/data/embassy_forms` — the
  script is gitignored and lives on the server.

## 2026-07-12 — Website Advertisements module (homepage popup + banner)

- **Domain module, not monolith:** all logic in `app/domains/ads/` (core/schema/
  audit/media/service/routes), mirroring the hostel pattern; `server.py` got 62
  additive lines (guarded import, `FEATURE_ADVERTISEMENTS` env flag, `configure()`,
  `ensure_schema()` in `init_db()`, GET/POST dispatch tails, homepage payload hook
  in `render_public_home`, `__ADS_NAV_BUTTON__` in `MAIN_APP`).
- **Strictly admin-role only** (owner decision): every management page/API does an
  in-handler `role == 'admin'` check on top of `require_auth()` — operator/
  operator_special are 403'd despite route-level RBAC admitting them.
- **Statuses:** stored DRAFT/ACTIVE/PAUSED/ARCHIVED; SCHEDULED/EXPIRED derived at
  read time from `starts_at`/`ends_at` (UTC strings) — no background job, expiry
  cannot be missed. Archived rows can only be duplicated, never reactivated/edited.
- **content_version** (integer) bumps only on public-facing changes (incl. image
  uploads); browser dismissal keys are `cwa_ad_dismissed:<id>:<version>` (popup)
  and `cwa_ad_banner_dismissed:<id>:<version>` — a republished version re-shows.
- **XSS strategy:** the homepage renderer escapes nothing, so admin content is
  NEVER put in HTML tokens; one JSON payload (`ensure_ascii` + `<`→`<`) is
  injected as `window.CWA_ADS` and `static/js/site-ads.js` builds DOM with
  `textContent` only. URL validator allows only https:// or internal `/` paths.
- **Images:** JPEG/PNG/WebP only (SVG rejected), extension AND magic must agree,
  Pillow header-first dimension check (≤4000×4000, ≥400px wide, ≤16MP) before full
  decode; global `PIL.Image.MAX_IMAGE_PIXELS` deliberately untouched (OCR). Files
  live in `ad_uploads/` (`/data` on Render), generated names only in DB, additive
  replacement, no deletion in v1. `/ads/media/<name>` serves publicly with
  `Cache-Control: immutable` (names are unique per upload).
- **Single-active-per-placement:** activation 409s with a conflict list; explicit
  `confirm_conflict` pauses the other ad (audited `conflict_paused`). Optimistic
  locking via `expected_updated_at` (409 on stale save) — first such convention
  in the portal.
- **Timezone:** admins enter/view Asia/Kuwait (fixed UTC+3, no DST); one shared
  converter in `ads/core.py`; DB stores UTC strings comparable to
  `CURRENT_TIMESTAMP`.
- **Backup:** `backup_onedrive.sh` Step 3b additively tars + uploads `ad_uploads/`
  (all failures WARN-only; DB backup unaffected). In-process `do_backup()` untouched.
- **Kill-switch:** `FEATURE_ADVERTISEMENTS=0` → routes 404, nav hidden, homepage
  payload `null`; data and images preserved.
- Verified 2026-07-12: `py_compile` clean; `routes.py` 54/54 (5 new CHECKS);
  `ads_module.py` 24/24; `ads_workflow.py` 88/88 (localhost E2E, needs
  Pillow-enabled interpreter for the image-accept suite — stock macOS python
  lacks PIL and the suite SKIPs); `site_ads_logic.mjs` 26/26; `hostel_module.py`
  still green; flag-off boot verified ad-free. Interactive a11y (focus trap,
  Escape, restore) is manual-checklist — no browser automation in the test stack.
- Test artifacts left in local DB (like hostel): users `ads-smoke-operator`/
  `ads-smoke-opspecial`, archived `ADS-SMOKE*` ads, images in `ad_uploads/`.
- Route inventory NOT appended (matches hostel precedent — the baseline is a
  no-deletion safety net; new-module routes get smoke CHECKS instead).

## 2026-07-07 — Hostel / Nurse Accommodation Partner module (AJA Care)

- **Separate partner auth, not a staff role.** Staff RBAC (`can_access_admin_route`
  line ~5619) grants every authenticated `users`-table role a `/staff/my-cases` access
  floor. A `HOSTEL_PARTNER` role in `users` would inherit it. Decision: partner logins
  live in `hostel_partner_users` with PBKDF2 hashing (reusing `_nurse_hash_password_pbkdf2`),
  their own in-memory session dict and `hostel_session` cookie. Staff and partner
  sessions are mutually invalid on each other's endpoints (verified by E2E test).
- **Domain module, not more monolith.** All logic in `app/domains/hostel/`
  (core/schema/audit/auth/service/documents/partner_api/routes); `server.py` got only
  ~50 additive lines: guarded import, `configure()` injection, `ensure_schema()` in
  `init_db()`, one dispatch `elif` at the tail of `do_GET` and of `do_POST` (cannot
  shadow existing routes), 2 RBAC lines for community_desk, 3 nav links.
- **partner_id always from session**, never from request payloads. Downloads check
  ownership + `visible_to_partner` + status ACTIVE; all denials return the same 404
  message and are audited (`partner_access_denied`).
- **Uploads stricter than portal norm:** extension AND magic bytes must agree
  (PDF/JPG/PNG), 10 MB cap (portal norm is extension-OR-magic, 50 MB global only).
- **Cancellation is status-only** — file and row are kept for audit; `hostel_audit`
  is append-only.
- **AJA Care seeded** as `hostel_partners.partner_code = 'AJA_CARE'`; existing
  `FACILITY_VENDOR_DEFAULT = 'AJA Care'` string usage and AJA reconciliation left
  untouched (they serve a different workflow: phone reconciliation over facility_roster).
- **Git initialized locally** (was not a repo) with data/uploads ignored; baseline
  commit `addafd7` is the rollback point.
- Pre-existing, unrelated: `tests/smoke/grading_letter_pdf_layout.py` fails with
  `KeyError: 'relation_text'` on baseline too (test-script bug, not server).
