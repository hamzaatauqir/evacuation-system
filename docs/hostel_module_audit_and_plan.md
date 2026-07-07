# Hostel / Nurse Accommodation Partner Module — Phase 0 Audit & Implementation Plan

Date: 2026-07-07 · Target: `server.py` (51,986 lines) + new `app/domains/hostel/` package
Scope: AJA Care hostel partner system (assignment, agreements, partner login) + safe additive modularization.

---

## 1. Audit Findings

### 1.1 Nurse data model (what we link to)

- **`nurse_registrations`** (CREATE at `server.py:1379`) is the canonical nurse identity table.
  Identity fields: `reference_id` (`NUR-#####`), `full_name`, `passport_number`, `civil_id` (CPR),
  `cnic`, `mobile`/`mobile_full`, `email`. No `gender`/`nationality` columns (code checks defensively).
  Already carries AJA-adjacent flags: `aja_care_resident` (line 1623), `current_hostel`, `room_number`, `vendor_name`.
- **`gl_applications`** (`server.py:296`) links via integer `nurse_id` → `nurse_registrations.id` and freezes
  identity into `*_snapshot` columns. Ref format `GL-{year}-{seq:06d}` from the race-safe `gl_ref_counter`
  table (`_gl_next_ref_no`, line 10283) — the pattern to copy for new references.
- **Cross-domain join convention (newest subsystems):** integer `nurse_registration_id` FK
  (`nh_nurse_account:687`, `facility_roster:2169`, `gl_applications:299`), optionally with denormalized
  `nurse_reference` / `passport_number` text copies (facility_roster pattern). New hostel tables follow this.
- **AJA Care today is a string, not an entity:** `FACILITY_VENDOR_DEFAULT = 'AJA Care'` (`server.py:5385`)
  on `facility_roster.vendor_name`, plus the `aja_care_resident` flag. There is **no partner table, no
  partner account model** anywhere.
- **AJA reconciliation** (`/admin/aja-reconciliation`, page 35549; APIs 35954–35983, 39254–39271) is a
  phone-call work-queue view over `facility_roster LEFT JOIN nurse_registrations` — read/update of
  `reconciliation_*` columns. It does not manage tenancy or documents. We leave it untouched.
- **Existing admin nurse search** to reuse as a model: `GET /api/admin/nurses/registrations`
  (handler 36068–36217) searches 11 fields (`reference_id, full_name, passport_number, cnic, civil_id,
  mobile, email, batch_number, hospital, facility_name, vendor_name`) with `UPPER(...) LIKE` + pagination.

### 1.2 Auth & roles

- Staff auth: `users` table (`server.py:998`), free-text `role` column, **unsalted SHA-256** password hash
  (`hash_pw`, line 3394). In-memory `SESSIONS` dict (line 111), cookie `session`, `create_session` (24355),
  `require_auth` (35069) → `can_access_admin_route` (5573) / `can_access_api_route` (5628).
- **Critical finding:** every authenticated staff role gets a default access floor —
  `_staff_base_path_allowed` returns True for *any* role (`server.py:5619, 5661–5663`), granting
  `/staff/my-cases` + related APIs. A `HOSTEL_PARTNER` role placed in the `users` table would inherit this
  floor and require invasive changes to deny it.
- Nurse portal auth is a **second, separate mechanism**: PBKDF2 helpers
  (`_nurse_hash_password_pbkdf2:5310`, `_nurse_verify_password_pbkdf2:5318`), session marker stored on the
  nurse row, no cookie, no `SESSIONS` entry. Precedent: adding an isolated login population is an accepted
  pattern in this codebase.
- No vendor/partner/hostel login exists. `/hostel*`, `/partner*`, `/api/hostel*` namespaces are free
  (verified against `tests/route_inventory.txt`).

**Decision:** hostel partner users get their **own table + own session store + own cookie
(`hostel_session`) + own guard**, never entering staff `SESSIONS`/RBAC. Staff auth is not modified.
Partner passwords use the existing PBKDF2 helpers (better than staff SHA-256).

### 1.3 Uploads / downloads

- Shared multipart parser: `extract_multipart_upload(body, content_type, field_names)` (`server.py:34297`) —
  returns first file part; extra text fields parsed inline by callers (pattern at 40679–40692).
- Storage convention: `RENDER_DISK('/data')` if present else `PROJECT_ROOT` (lines 114–120); stored names =
  `timestamp_tokenhex_sanitizedname` (`server.py:28660`); sanitizer `re.sub(r'[^A-Za-z0-9._-]+','_',name)`.
- Download convention: **DB-driven paths** (client supplies row id only → traversal-safe by design), manual
  headers with `Content-Disposition` inline/attachment toggle, header-injection guard
  `re.sub(r'[\r\n"]+','_',name)` (37541), no-cache header block for sensitive docs (37420–37422),
  audit row on permission denial (37501).
- Gaps to close in the new module: only a global 50 MB body cap (`MAX_REQUEST_BODY_BYTES:166`), extension
  **OR** magic-byte check (either passes). New module enforces per-file cap (10 MB), extension **AND**
  magic-byte agreement (PDF/JPG/PNG), and logs every partner download.

### 1.4 Routing / page patterns

- `Handler` at 34736; `do_GET` 35154; `do_POST` 38600; both are `if/elif` chains ending in a 404 `else`
  (38596). New routes appended just before the final `else` cannot shadow anything.
- Newest admin-page pattern (copy this): `require_auth` → role-set check →
  `render_template_with_context('templates/x.html', {'USER_NAME':…})` with inline fallback
  (`/admin/aja-reconciliation` block, 35549–35555). Templates use `__PLACEHOLDER__` substitution, link
  `/static/css/cwa-admin.css`, vanilla-JS `fetch`.
- API convention: `api_*(data, user)` dict-in/dict-out with `{'success': bool}`, handler does
  `json.loads(body)` + `send_json(result, 200 if success else 400)`.
- Smoke baseline: `tests/smoke/routes.py` (read-only; any 5xx fails; unauthenticated admin routes expect
  302). `tests/route_inventory.txt` is the frozen route baseline — additions only.
- Nav insertion points: `MAIN_APP` sidebar (~47648), `_nurse_accommodation_admin_sidebar` (42736),
  `templates/admin_community_welfare.html` sidebar.
- Modularization state: `app/` + `app/core/` are empty stubs (Phase 0). The modularization audit
  (`server_modularization_audit.md`) prescribes: additive extraction, `server.py` stays sole entrypoint,
  domain modules with no HTTP coupling where possible, no framework/ORM, no URL changes.

### 1.5 Security risks identified → mitigations

| Risk | Mitigation in design |
|---|---|
| Partner inherits staff access floor | Separate session store/cookie/guard; partner never in staff RBAC |
| Partner sees other partners' nurses | `partner_id` always read from session, never from request |
| Unrelated document download | Download checks: partner session → agreement → assignment → session partner_id → `visible_to_partner` → status ACTIVE |
| Path traversal | DB-driven stored names (client sends row id only), whitelist-sanitized filenames |
| Malicious upload | Admin-only upload; extension AND magic bytes; 10 MB cap; random stored names |
| Cancelled agreements lost | Status change only, file + row retained; append-only `hostel_audit` |
| Partner brute force | Per-IP+username lockout (5 fails / 300 s) mirroring staff `LOGIN_ATTEMPTS` |
| Staff session hitting partner APIs (or vice versa) | Different cookie names; each guard only accepts its own store |

---

## 2. Patch Plan (exact changes)

### 2.1 New package `app/domains/hostel/` (all logic lives here)

```
app/domains/__init__.py          (new, empty)
app/domains/hostel/__init__.py   re-exports: configure, ensure_schema, handle_get, handle_post, matches_path
app/domains/hostel/core.py       injected deps (get_db, multipart parser, pbkdf2 fns, data root), constants, ref generator
app/domains/hostel/schema.py     ensure_schema(db) — additive CREATE TABLE IF NOT EXISTS + seed AJA Care
app/domains/hostel/audit.py      write_audit(...) → hostel_audit (append-only)
app/domains/hostel/auth.py       partner sessions (own dict + lock), login/logout, lockout, require_partner
app/domains/hostel/service.py    nurse search, assignment lifecycle, exports (pure logic, dict-in/dict-out)
app/domains/hostel/documents.py  upload validation/storage, permission-checked download resolution
app/domains/hostel/admin_api.py  staff-facing api functions
app/domains/hostel/partner_api.py partner-facing api functions
app/domains/hostel/routes.py     HTTP dispatch: handle_get/handle_post(handler, path, …)
templates/admin_hostel_accommodation.html   admin UI (search / assign / agreements / audit)
templates/hostel_login.html                 partner login
templates/hostel_dashboard.html             partner dashboard
tests/smoke/hostel_module.py                read-only gate checks (routes.py style)
tests/smoke/hostel_workflow.py              localhost-only E2E workflow test
```

### 2.2 `server.py` edits (additive, ~40 lines total)

1. Top of file: `from app.domains import hostel as hostel_module` (pure import, no side effects).
2. After PBKDF2/multipart helpers exist (before `Handler`): one `hostel_module.configure(...)` call
   injecting `get_db`, `extract_multipart_upload`, `_nurse_hash_password_pbkdf2`,
   `_nurse_verify_password_pbkdf2`, data-root path, `FACILITY_VENDOR_DEFAULT`.
3. `init_db()`: one guarded `hostel_module.ensure_schema(db)` call (try/except + warning print, same as
   other domain bootstrappers — a hostel schema error must not block boot).
4. `do_GET`: one `elif hostel_module.matches_path(path): hostel_module.handle_get(self, path, params)`
   placed immediately before the final 404 `else` (cannot shadow existing routes).
5. `do_POST`: same, before its fallback.
6. RBAC (2 additive lines): `/admin/hostel-accommodation` added to community-desk page set (5600–5613)
   and `/api/admin/hostel/` to community-desk API prefixes (5648–5660). Full-admin roles pass already.
7. Nav: one link in `_nurse_accommodation_admin_sidebar`, one button in `MAIN_APP` sidebar, one link in
   `templates/admin_community_welfare.html`.

No existing route, table, or function is modified or moved. Route inventory diff = additions only.

### 2.3 DB schema additions (idempotent `CREATE TABLE IF NOT EXISTS`)

- **`hostel_partners`** — id, partner_code UNIQUE, partner_name, display_name, contact_person, email,
  phone, address, status (ACTIVE/SUSPENDED/ARCHIVED), can_mark_arrival INT DEFAULT 1, notes,
  created_at, updated_at. Seed row: AJA Care (`AJA_CARE`).
- **`hostel_partner_users`** — id, partner_id → hostel_partners, username UNIQUE, full_name, email,
  password_hash + password_salt (PBKDF2), role DEFAULT 'HOSTEL_PARTNER', status (ACTIVE/DISABLED),
  last_login_at, created_by, created_at, updated_at.
- **`hostel_assignments`** — id, assignment_ref UNIQUE (`HST-{year}-{seq:05d}` via hostel_ref_counter),
  nurse_registration_id → nurse_registrations, gl_application_id NULL, partner_id → hostel_partners,
  denormalized nurse_name/passport_number/nurse_reference, hostel_name, room_number, bed_number,
  assigned_date, expected_arrival_date, actual_arrival_date,
  status (ASSIGNED/ARRIVED/ACTIVE_TENANT/LEFT_HOSTEL/CANCELLED),
  notes (internal), note_for_partner, partner_note, acknowledged_at, acknowledged_by,
  assigned_by, cancelled_by, cancelled_at, cancellation_reason, created_at, updated_at.
  Code-enforced: one non-cancelled assignment per (nurse, partner).
- **`hostel_agreements`** — id, assignment_id → hostel_assignments, nurse_registration_id, partner_id,
  document_type (ACCOMMODATION_AGREEMENT/CANCELLATION/REPLACEMENT/OTHER), file_name (original),
  stored_name (generated), mime_type, file_size, status (ACTIVE/CANCELLED/REPLACED/ARCHIVED),
  visible_to_partner INT DEFAULT 1, uploaded_by, uploaded_at, cancelled_by, cancelled_at,
  cancellation_reason, replaced_by_document_id, created_at, updated_at.
- **`hostel_audit`** — append-only: id, entity_type, entity_id, partner_id, nurse_registration_id,
  actor_type (STAFF/PARTNER/SYSTEM), actor, event_type, old_value, new_value, note, ip, created_at.
- **`hostel_ref_counter`** — year PK, next_seq (gl_ref_counter pattern).

Files: `hostel_agreement_uploads/` under `/data` on Render, project root locally (existing convention;
already added to `.gitignore` and covered by the whole-file DB/disk backup).

### 2.4 New routes

Staff (existing staff session; full admins + community_desk):
```
GET  /admin/hostel-accommodation            admin page
GET  /api/admin/hostel/partners             list partners (+ users; admin sees usernames/status)
POST /api/admin/hostel/partners/save        create/update partner (admin only)
POST /api/admin/hostel/partner-users/save   create partner login / reset password / disable (admin only)
GET  /api/admin/hostel/nurse-search         search nurses + GL status + current assignment
GET  /api/admin/hostel/assignments          list, filters + pagination
GET  /api/admin/hostel/assignments/detail   one assignment + agreements + audit timeline
POST /api/admin/hostel/assignments/create   assign nurse(s) — single or bulk nurse_ids
POST /api/admin/hostel/assignments/update   room/bed/dates, mark arrived/active/left, cancel w/ reason
POST /api/admin/hostel/agreements/upload    multipart PDF/JPG/PNG, ≤10 MB
GET  /api/admin/hostel/agreements/file      view/download (staff)
POST /api/admin/hostel/agreements/update    cancel / archive / toggle partner visibility / replace
GET  /api/admin/hostel/export.csv           current tenant list CSV
GET  /api/admin/hostel/audit                audit timeline (filterable)
```

Partner (own `hostel_session` cookie; partner_id always from session):
```
GET  /hostel/login                          login page (public)
POST /api/hostel/login                      authenticate (lockout: 5 fails / 300 s)
POST /api/hostel/logout
GET  /hostel/dashboard                      dashboard page (redirects to /hostel/login when signed out)
GET  /api/hostel/summary                    KPIs: expected today, active tenants, pending acknowledgement
GET  /api/hostel/nurses                     assigned nurses only (scoped)
GET  /api/hostel/nurses/detail              one assignment (scoped) + visible agreements
GET  /api/hostel/agreements/file            download — scoped + visible_to_partner + ACTIVE only; logged
POST /api/hostel/acknowledge                acknowledge an assignment
POST /api/hostel/note                       partner note visible to Embassy
POST /api/hostel/mark-arrival               record actual arrival (if partner.can_mark_arrival)
GET  /api/hostel/export.csv                 assigned list CSV (scoped)
```

### 2.5 Audit events (all → `hostel_audit`)

partner_created, partner_user_created, partner_user_password_reset, partner_user_status_changed,
assignment_created, assignment_updated, assignment_status_changed, assignment_cancelled,
agreement_uploaded, agreement_cancelled, agreement_replaced, agreement_archived, agreement_visibility_changed,
agreement_viewed_by_partner, agreement_downloaded_by_partner, agreement_downloaded_by_staff,
partner_login_success, partner_login_failed, partner_login_locked, partner_logout,
assignment_acknowledged, partner_note_added, arrival_marked_by_partner, partner_access_denied.

## 3. Test Plan

1. `python3 -m py_compile server.py` + all `app/domains/hostel/*.py`.
2. Existing suite unchanged-green: `python3 tests/smoke/routes.py http://localhost:8080` (`Failed: 0`, `5xx: 0`).
3. New `tests/smoke/hostel_module.py` (read-only): admin page 302 gate, partner login page 200,
   partner APIs 401 without session, admin hostel APIs 302 without session.
4. New `tests/smoke/hostel_workflow.py` (refuses non-localhost): admin login → create partner user →
   search nurse → assign → upload agreement → partner login → sees exactly own nurses → downloads
   agreement → staff cancels agreement → partner no longer sees it → audit rows exist for each step →
   partner cannot fetch another partner's agreement (403/404) → partner cannot call `/api/admin/*` (302/403).
5. Route inventory: regenerate and diff — additions only.
6. Manual spot checks: homepage, tracking, nurse login, GL admin page, AJA reconciliation, accommodation
   list, fee routes untouched (no code paths modified).

## 4. Rollback Plan

- Local git baseline commit `addafd7` (repo initialized 2026-07-07 with data/uploads ignored):
  `git checkout addafd7 -- server.py && rm -rf app/domains/hostel` reverts everything.
- All schema changes are additive `CREATE TABLE IF NOT EXISTS` — reverting the code leaves inert tables;
  no destructive migration to undo. Uploaded agreement files live in a dedicated directory that can be
  archived or left in place.
- On Render: standard "Rollback to previous deploy". `hostel_module.ensure_schema` is wrapped in
  try/except so even a schema failure cannot block boot.

## 5. Explicitly Out of Scope (unchanged)

Backup/OneDrive, email worker, PDF/OCR pipeline, fee routes, staff auth/session logic, TOTP 2FA,
nurse portal flows, GL workflow, AJA reconciliation, React SPA, `init_db()` existing content,
all existing routes and tables.
