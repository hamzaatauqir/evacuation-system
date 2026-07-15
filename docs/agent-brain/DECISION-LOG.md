# Decision Log — Embassy Portal

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
