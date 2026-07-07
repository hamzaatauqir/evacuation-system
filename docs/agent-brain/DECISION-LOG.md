# Decision Log — Embassy Portal

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
