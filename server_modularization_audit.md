# Embassy Community Welfare Portal — Modularization Audit

**System:** Pakistan Embassy Kuwait — Community Welfare & Operations Portal
**Audit target:** `server.py` (Python stdlib HTTP server + SQLite), live on Render
**Auditor brief:** stability-first; gradual extraction; no rewrites
**Audit date:** 2026-05-05

---

## Executive Summary

The portal is a working, production-grade government operations system implemented as a single-file Python stdlib monolith. It is currently 44,973 lines, 784 top-level definitions, with one `Handler` class spanning 7,518 lines. It serves 16 distinct functional domains over ~316 route branches, against 63 SQLite tables, with four background threads, OCR/PDF rendering, OneDrive backup, an email worker queue, and per-thread DB connections.

The system is mature in *behavior* — the workflows are real, the data is real, the users are real Embassy staff and applicants — but immature in *structure*. Risk concentrates in three places: (a) the giant `Handler` class that mixes routing, auth, validation, business logic, and HTML rendering; (b) the embedded HTML/JS strings (39 page-sized constants) that hide UI changes from any IDE search; (c) the global mutable session dictionary that pins state to one process, blocking horizontal scale.

**Maturity assessment.** Behavior: 4/5. Structure: 1/5. Operational stability: 4/5 (the WAL pragma, locks, and email worker are well-considered). Test coverage: 0/5 (none observed in tree). Onboarding for a new engineer: 1/5 — finding any feature requires `grep`, then reading 200–500 contiguous lines of mixed concerns.

**Biggest architectural risk.** Not the size — government portals routinely run as monoliths. The risk is the *coupling between routing, business logic, and HTML* inside one class, combined with in-process session state. A second admin replica (for HA or zero-downtime deploy) cannot be added without sharing sessions; a single bad route change can crash the entire operations surface; a single template change can require editing inside a 7,518-line class. The `init_db()` function alone is 2,065 lines and creates schema for every domain at startup — a single SQLite-level mistake there freezes the whole portal.

**Safest path forward.** Surgical, additive modularization: introduce an `app/` package alongside `server.py`, leave `server.py` as the one and only routing entrypoint, and extract one domain at a time as a *pure-Python module with no HTTP coupling*. The Handler keeps calling the now-relocated functions. No URL changes, no auth changes, no DB schema changes, no deployment changes for at least the first three phases.

**Estimated effort.** 12–16 engineering weeks at one developer focused half-time, in 8 phases of 1–2 weeks each. Stability dividends start arriving after Phase 2 (audit & email plumbing extraction).

**Recommended cadence.** One module per phase. One PR per phase, merged behind a Render deploy. Smoke test the same 12 critical workflows after every merge. No phase begins until the prior phase has been live for at least one full business day on Render.

**What NOT to do.** Don't migrate to Flask/FastAPI/Django. Don't add an ORM. Don't redesign the schema. Don't try to extract the giant `Handler` class first — extract its dependencies first, then thin it out by delegation. Don't change the OneDrive backup, email worker, or `start_email_worker` startup sequence in early phases. Don't touch `init_db()` until at least Phase 5.

---

## Current Architecture Assessment

### Code shape (measured)

| Metric | Value |
|---|---|
| Total lines | 44,973 |
| Top-level `def`/`class` | 784 |
| Routes (do_GET + do_POST branches) | ~316 (265 under `/api/...`) |
| `Handler` class size | 7,518 lines (~17% of file) |
| `init_db()` size | 2,065 lines |
| Largest UI generator (`iraq_public_form_page_with_flag`) | 5,751 lines |
| `cwa_module_page()` | 1,767 lines |
| `nurse_simple_page()` | 594 lines |
| Inline HTML page constants (`*_PAGE = """..."""`) | 39 |
| `self.send_html` / `self.send_json` call sites | 720 |
| `db.execute` / `executescript` / `executemany` call sites | 1,093 |
| SQLite tables created in this file | 63 |
| Threading locks | 5 (`SESSIONS_LOCK`, `_DB_WAL_LOCK`, `MONTHLY_WELFARE_CHECKIN_LOCK`, `_NH_SCHEMA_LOCK`, `_NO_SCHEMA_LOCK`) |
| Global mutable dicts | 2 (`SESSIONS`, `LOGIN_ATTEMPTS`) |
| Background threads | 4 (email worker, OneDrive async upload, auto-backup scheduler, monthly welfare check-in scheduler) |
| External tools wired in | PyMuPDF (`fitz`), pdftotext, pytesseract, pdf2image, smtplib, MS Graph (OneDrive) |

### Domains observed (16 functional clusters)

The codebase has already accreted natural domain prefixes — useful signal that an organic structure exists; it just isn't expressed in the file system. By call-site count and table count:

| Domain | Tables (incl.) | Route prefix(es) | Notes |
|---|---|---|---|
| Auth & sessions | `users` | `/login`, `/logout`, `/api/login` | `SESSIONS` dict + `LOGIN_ATTEMPTS` lockout map |
| Iraq KSA transit | `iraq_*`, `evacuees`, `mofa_batches`, `approval_upload*`, `iraq_public_submissions` | `/api/iraq*`, `/iraq-*`, `/print/*` | Largest functional surface; PDF + email-heavy |
| Note Verbal | `note_verbal_*`, `nv_release_log` | `/api/admin/note-verbal*`, `/note-verbal-file` | Tied to MOFA/Iraq |
| Embassy letter generation | (uses many) | `/admin/.../letter`, `/print/*` | PyMuPDF + OCR |
| Fee collection | `fee_collections`, `fee_distributions`, `cwa_advance_ledger`, `office_expenses` | `/api/fee*`, `/api/admin/fee*`, `/fee-collector` | Money + timed ledgers, sensitive |
| Welfare cases | `welfare_cases`, `welfare_case_actions`, `welfare_auto_routing_rules` | `/api/admin/welfare*` | Auto-routing logic |
| Legal / OPF | `legal_case_*` | `/legal-opf*`, `/api/admin/legal-cases*` | |
| Death cases | `death_case_*` | `/death-cases*`, `/api/admin/death-cases*` | |
| Nurses (registration, login, complaints, leave notice, accommodation, MTON) | `nurse_registrations`, `nurse_complaints`, `nurse_complaint_actions`, `nurse_accommodation_requests`, `nurse_leave_notices`, `nurse_activity_log` | `/nurses/*`, `/api/nurses/*` | Public + nurse-portal auth |
| Nurse Housing (`nh_*`) — AJA arrival batches | `nh_arrival_batch`, `nh_nurse_account`, `nh_audit`, `nh_settings` | `/api/admin/nurses/pending-accounts`, `/arrival-batches`, etc. | Recently added, well-prefixed |
| Grading Letter (`gl_*`) | `gl_applications`, `gl_audit`, `gl_grading_scale*`, `gl_gpa_conversion*`, `gl_settings`, `gl_ref_counter` | `/api/nurses/grading-letter*`, `/api/admin/gl/*` | Recently added, well-prefixed |
| MOH Onboarding (this audit's prior patch) | `nurse_onboarding_*` | `/api/nurses/onboarding/*`, `/api/admin/nurses/onboarding/*` | Newly added, well-prefixed |
| Facility roster / occupancy | `facility_roster*`, `alternative_facilities` | `/admin/facility-roster*` | Big legacy admin pages, vendor reconciliation |
| Ambassador Pulse | (read-only across cases) | `/api/admin/ambassador-pulse-export.csv` | Cross-domain read |
| SITREP & dashboards | (cross-domain reads) | `/admin/dashboard`, `/admin/community-welfare`, etc. | |
| Public tracking & feedback | `public_feedback_messages`, plus shared reads | `/api/public/track*`, `/community-feedback` | |
| Charter / cargo / travel-interest forms | `charter_interest`, `cargo_interest`, `family_group`, `family_members` | `/api/charter*`, `/travel-interest`, `/register` | |
| Backup, OneDrive, email worker, scheduling | `audit_log`, `notification_log` | (no public route; runs in background) | Critical infrastructure |

The observation worth flagging: every recent feature (`gl_`, `nh_`, `nurse_onboarding_*`) is *already* prefixed and lives in clean blocks. The codebase has been getting more disciplined over time. Modularization is therefore extractive (move what is already cohesive) rather than reconstructive.

### State, threading & concurrency

- **`SESSIONS` (line ~83) and `LOGIN_ATTEMPTS` (line ~19014)** are in-process Python dicts. They survive process lifetime only. Restarting the server invalidates every active session. A second replica cannot share them.
- **5 threading locks**, each guarding a separate concern. The locking is tight and conservative — a positive signal that whoever wrote this code understood concurrency.
- **`get_db()`** opens a new SQLite connection per request (with `PRAGMA busy_timeout=30000` and WAL mode applied once at startup via `_apply_wal_once()`). This is the right pattern for `ThreadingHTTPServer` + SQLite, but every domain re-opens its own connection inside `try/finally db.close()` boilerplate that is duplicated ~150+ times.
- **Background threads**: `_email_worker_loop` (email queue drain), `auto_backup_scheduler` (daily backup + OneDrive), `monthly_welfare_checkin_scheduler_loop`, and ad-hoc `_onedrive_upload_async` per-backup. Each is a daemon thread started at module import or `start_email_worker()` time. None of them have explicit shutdown handling beyond daemon flag; this is acceptable for Render's signal-based termination but can be improved later.

### HTML & template strategy

39 `*_PAGE = """..."""` constants embed full HTML documents in Python string literals, several with inline `<script>` blocks. The largest single string (`iraq_public_form_page_with_flag`) is 5,751 lines — a complete page generator that mixes Python f-string interpolation with HTML and JS. There is also a `templates/` directory with `render_template_with_context` calls (16), so a template path exists; it's just not used uniformly.

This is the highest-friction part of the codebase to modify. A typo in a script tag inside an embedded string can pass `py_compile` cleanly and only break at runtime in a specific user's browser.

### Database

63 tables, all created via `CREATE TABLE IF NOT EXISTS` inside `init_db()` (or its sub-functions like `_init_grading_letter_db`, `_nh_ensure_schema`, `_nurse_onboarding_ensure_schema`). Migrations are idempotent column-adds via `ALTER TABLE ... ADD COLUMN` wrapped in `try/except OperationalError`. This is a pragmatic, additive migration pattern that has clearly served the project well — keep it. Do not introduce a migration framework; do not introduce SQLAlchemy.

### Strengths

- Idempotent migrations, additively applied.
- WAL mode with `busy_timeout=30000` — robust against concurrent reads.
- Per-thread DB connections, properly closed in `finally` blocks.
- Good separation of *data* concerns from each domain via prefixed function names (`_gl_`, `_nh_`, `nh_`, etc.).
- Audit tables exist for sensitive domains (welfare cases, nurse activity, GL, NH).
- Email is queued via `_enqueue_email_job` and drained by a worker — never inline.
- Backups are automated with OneDrive secondary destination.
- Auth is gated centrally via `require_auth` + `can_access_api_route` / `can_access_admin_route`.

### Weaknesses

- One 7,518-line `Handler` class containing 316 route branches.
- 39 inline HTML pages, including a 5,751-line page generator.
- No unit tests, no integration tests, no smoke-test script in repo.
- Sessions are in-process dicts — single replica only.
- `init_db()` creates *all* schema at startup; a single bad CREATE/ALTER can prevent boot.
- Domain logic and HTTP handling are intermixed inside many `api_*` functions (e.g., they read `data` directly from request payload and respond with `status_code` keys consumed by the Handler).
- Several functions exceed 200 lines; the single biggest are render/page generators that should be templates.

---

## Critical Risks

Ranked by potential blast radius if disturbed.

1. **`init_db()` (2,065 lines).** Touches every table. A migration error here prevents process boot. **Treat as untouchable until Phase 5+** with explicit per-domain extraction guarded by manual DB verification.
2. **`SESSIONS` global dict.** Any change to session storage invalidates active staff sessions. Modify only with announced maintenance window, and only after introducing a session interface (Phase 6+).
3. **`Handler.do_GET` / `do_POST` branch trees.** A single misplaced `elif` or duplicate `path ==` bug silently shadows real routes. Refactor must preserve order or use explicit per-route registration.
4. **PDF generation (PyMuPDF + OCR fallback chain).** Used by Iraq letters, embassy letters, grading letters. Library version drift on Render has historically been a cause of regressions. **Pin versions** before any extraction.
5. **Email worker (`_email_worker_loop`).** A single unhandled exception inside the worker thread silently kills delivery of a queued letter. Currently uses `try/except` around `_send_email_smtp`, which is correct — preserve it.
6. **Backup scheduler + OneDrive.** Critical infrastructure. Don't touch in early phases. Rate of file change here is low; risk-of-break is high.
7. **Fee collection routes.** Money + audit. Highest sensitivity to behavioral drift. Touch only after Phase 4 with explicit acceptance tests.
8. **Auth gates `can_access_api_route` / `can_access_admin_route` / `require_auth`.** Path-prefix-based authorization. A renamed prefix during extraction can silently grant or remove access.
9. **`approval_uploads/`, `note_verbal_uploads/`, `generated_letters/`, `letter_templates/`.** On-disk file artifacts. Their paths are baked into route handlers and DB rows. Path changes during extraction must be opt-in via env config, with backwards-compatible reads.
10. **Render deployment script (`build.sh` + `Aptfile`).** Any new module top-level imports introduced during extraction must remain installable on Render's standard buildpack. New `Aptfile` entries trigger longer build times.

---

## Module Mapping (proposed `app/` package)

This is a target shape, not a destination to reach in one sprint. The path from monolith to this layout takes the full 8-phase plan.

```
NEw Update/                       # repo root (unchanged)
├── server.py                     # remains the one entrypoint; thinning over time
├── app/                          # NEW: pure-Python package, no top-level side effects
│   ├── __init__.py
│   ├── core/                     # cross-cutting infrastructure
│   │   ├── db.py                 # get_db, _apply_wal_once, _table_columns
│   │   ├── auth.py               # SESSIONS interface, require_auth, RBAC checks
│   │   ├── audit.py              # audit_log helpers (shared)
│   │   ├── email.py              # _enqueue_email_job, _email_worker_loop, templates render
│   │   ├── backup.py             # do_backup, OneDrive helpers, prune_local_backups
│   │   ├── pdf.py                # PyMuPDF + Type1 fallback PDF builder
│   │   ├── ocr.py                # pdftotext + pytesseract fallbacks
│   │   ├── settings.py           # _get_setting, _load_email_config
│   │   └── http.py               # send_json/send_html helpers, body parsing, multipart
│   ├── domains/
│   │   ├── nurses/               # registration, login, complaints, leave-notice, MTON
│   │   ├── housing/              # nh_* (arrival batches, sidecar accounts)
│   │   ├── grading_letter/       # gl_*
│   │   ├── onboarding/           # nurse_onboarding_*
│   │   ├── facility/             # facility_roster, occupancy, vendor reconciliation
│   │   ├── iraq/                 # iraq_*, public submissions, MOFA dispatches
│   │   ├── note_verbal/          # nv_*, links, releases
│   │   ├── fee/                  # fee_collections, distributions, advance ledger
│   │   ├── welfare/              # welfare_cases, auto-routing
│   │   ├── legal/                # legal_case_*
│   │   ├── death/                # death_case_*
│   │   ├── public/               # tracking, feedback, charter/cargo/travel-interest
│   │   ├── ambassador_pulse/     # cross-domain CSV exports
│   │   ├── sitrep/               # SITREP editor + dashboards
│   │   └── letters/              # embassy letter HTML/PDF generators (cross-domain)
│   └── routing/
│       ├── __init__.py
│       ├── registry.py           # explicit (method, path) → handler mapping
│       └── adapters.py           # path-pattern matching, regex routes (e.g. /admin/gl/<id>)
├── templates/                    # existing; expand
├── static/                       # existing; expand
├── letter_templates/             # existing
├── generated_letters/            # existing
└── tests/                        # NEW: smoke tests + per-domain pytest
    ├── smoke/
    │   └── routes.py             # hits every public route, asserts 200/302/404 unchanged
    └── domains/
        └── ...
```

The two-letter convention to keep:

- **`app/core/*`** = no domain knowledge, no DB schema ownership.
- **`app/domains/<x>/`** = owns its tables, helpers, route handlers, and one `urls.py` exposing `(method, path) → callable`.
- **`server.py`** = imports route registries, owns the `Handler` class, owns process startup, owns the background thread launches. Eventually, but not in early phases.

---

## Dependency Analysis (where the wires cross)

Hot dependencies you must respect during extraction.

| Caller | Depends on | Direction of risk |
|---|---|---|
| Every domain handler | `get_db`, `require_auth`, `send_json`, `send_html` | Extract `core/` first; everything else imports it. |
| Iraq, Note Verbal, Embassy Letter generation | PyMuPDF, OCR fallback, `letter_templates/`, file paths | Pin library versions; file paths via env; isolate one extraction at a time. |
| Email worker | DB notification_log + smtp config + every domain's `_queue_*_email` | Worker should pull rows by job kind; keep job kind strings stable. |
| Auth gates | Path-prefix matching | Any URL rename ripples here. Don't rename URLs during extraction. |
| Ambassador Pulse export | Reads from welfare, legal, death, fee, nurses | Touch last; depends on every domain's stability. |
| `init_db()` | Every domain's CREATE TABLE | Split into per-domain `ensure_schema()` like `_nh_ensure_schema` and `_nurse_onboarding_ensure_schema` already do. |
| Static `/static/...` serving | File path resolution inside Handler | Keep server.py the static server until last. |
| Backup scheduler | Snapshots `evacuation.db` whole-file | Don't change DB filename or path. |

The most dangerous *invisible* coupling is the email worker's job-kind strings (`registration`, `iraq_public_submitted`, `mofa_sent`, `route_clarification`, etc.). Each `_queue_*_email` writes a job with a fixed kind, which the worker dispatches on. **Treat job-kind strings as a public contract** — never rename, only add new ones.

---

## Recommended Modular Structure (target)

Same as Module Mapping above. Two design choices worth calling out:

**1. Domain modules export "ports", not Flask blueprints.**
```python
# app/domains/grading_letter/urls.py
from .api import nurse_summary, nurse_submit, admin_list, admin_detail

ROUTES = [
    ("GET",  "/api/nurses/grading-letter",          nurse_summary),
    ("POST", "/api/nurses/grading-letter/submit",   nurse_submit),
    ("GET",  "/api/admin/gl/list",                  admin_list),
    ("GET",  re.compile(r"^/api/admin/gl/detail$"), admin_detail),
    # ...
]
```

`server.py` reads `ROUTES` from each domain and dispatches in `do_GET` / `do_POST`. No web framework, no decorators, no magic. Pure data, easy to grep.

**2. Schema ownership stays with the domain.**
Each domain exposes `ensure_schema(db)`. `server.py`'s `init_db()` becomes a *list of calls* — exactly the pattern `_nh_ensure_schema` and `_init_grading_letter_db` already use. The 2,065-line `init_db()` shrinks to a few hundred lines by Phase 5.

---

## Safe Extraction Order

Risk-banded, in execution sequence. *Do not jump levels.*

### LOW risk (start here)

1. **`app/core/`** (Phase 1) — pure helpers with no domain logic and no behavior change. `_apply_wal_once`, `get_db`, `esc`, `send_json` body, `_table_columns`, `_get_setting`. **Why low risk:** these have no business decisions, no auth, and no schema work. They have tons of callers, but the callers don't care which file the function lives in.
2. **Audit log helpers** (Phase 2) — `audit_log` writers are append-only, idempotent, and already abstracted in newer domains (`_gl_write_audit`, `_nh_write_audit`, `_nurse_onboarding_write_audit`). Consolidate into `app/core/audit.py`.
3. **Email plumbing** (Phase 2) — `_enqueue_email_job`, `_send_email_smtp`, `_load_email_templates`, `_render_email_template`, `_email_worker_loop`. **Why low risk:** moves code, not behavior. Keep job-kind strings stable.

### MEDIUM risk

4. **MOH Onboarding domain** (Phase 3) — newest, smallest, fully prefixed `nurse_onboarding_*`. Acts as a proving ground for the extraction pattern. **Why medium:** new module, easy to test, but proves that the extraction pattern actually works end-to-end with auth and routing.
5. **Grading Letter domain** (Phase 3 or 4) — well-prefixed `gl_*`, has its own audit table, has its own ensure_schema. Larger surface than onboarding but same shape.
6. **Nurse Housing (AJA / arrival batches)** (Phase 4) — already prefixed `nh_*`. Extracted after Grading Letter because nurse-portal auth gating is shared.
7. **Public tracking + feedback + charter/cargo/travel-interest** (Phase 4) — public-facing, low data sensitivity, well-bounded forms.

### HIGH risk

8. **Nurses domain (registration, login, complaints, leave notice, accommodation, MTON)** (Phase 5) — *Touches identity* and is depended on by Housing/Grading/Onboarding. Extract only after those have been live for ≥1 week as modules. Requires careful auth handling.
9. **Welfare cases + auto-routing rules** (Phase 5) — has business rules (`welfare_auto_routing_rules`) that are runtime-editable. Verify rule evaluation doesn't change.
10. **Legal / Death cases** (Phase 6) — case workflows with admin actions and dispatched emails. Lower volume than nurses but higher per-case sensitivity (vital records).
11. **Facility roster / occupancy** (Phase 6) — large legacy admin pages with embedded JS. Move HTML to `templates/` first; only then extract handlers.
12. **Ambassador Pulse export + SITREP + dashboards** (Phase 7) — these are cross-domain readers. They go last so all the underlying domains are already stable as modules.

### CRITICAL — DO NOT TOUCH EARLY

13. **Auth & sessions (`SESSIONS`, `LOGIN_ATTEMPTS`, `require_auth`, RBAC matrices)** — fundamental. Any change here can lock out staff. Extract only after Phase 6, and only with a planned maintenance window. Any session-storage swap (e.g., to SQLite-backed sessions) needs an additional two-deploy migration: first dual-write, then cut over.
14. **Iraq KSA Transit + MOFA Note Verbal + Embassy Letter generation + Approval uploads** (Phase 7–8) — the largest, most coupled, most PDF/OCR-dependent surface. The single function `iraq_public_form_page_with_flag` is 5,751 lines. Extract HTML/JS to templates *first*, then extract Python handlers, then extract PDF builders.
15. **Fee collection + CWA advance ledger + Office expenses** (Phase 8) — money. Extract last with explicit before/after totals reconciliation in a one-shot script.
16. **`init_db()` consolidation** (Phase 5–8 incremental) — instead of a "big extraction," delete each domain's CREATE TABLE block from `init_db()` *only when* that domain's `ensure_schema(db)` is wired up and confirmed to run on cold start.
17. **Backup scheduler + OneDrive integration** — leave alone until Phase 8 minimum. The risk/reward is poor.

### Why these orderings

- **Newest code first** because it's the most prefixed, the most cohesive, and the team's mental model of it is the freshest.
- **Cross-domain readers last** (Pulse, SITREP) because their bug surface depends on every domain they touch.
- **Auth in the middle, with care** because changing it forces every prior extraction to re-prove its access checks.
- **Money last** because reconciliation requires explicit before/after totals.

---

## First Extraction Candidate (Phase 1 — `app/core/`)

The recommended *first* extraction is **the database connection helper and a small set of pure helpers**. Reason: zero behavior change, zero auth interaction, hundreds of callers — proves the pattern by moving non-controversial code.

### Target files

```
app/__init__.py                 # empty
app/core/__init__.py            # empty
app/core/db.py
app/core/text.py                # esc(), _table_columns(), trivial string utils
```

### What moves into `app/core/db.py`

- `get_db()` (line ~141)
- `_apply_wal_once()` (line ~120)
- `_DB_WAL_APPLIED`, `_DB_WAL_LOCK`
- `DB_PATH`, `RENDER_DISK`, `BACKUP_DIR`, `LOCAL_BACKUP_KEEP_COUNT`
- `_table_columns(db, table_name)` (line ~4392)

### What stays in `server.py` (Phase 1)

```python
# server.py — top
from app.core import db as _db
from app.core import text as _text

# Compatibility shim — preserve exact module-level names so existing call sites work.
get_db = _db.get_db
_apply_wal_once = _db._apply_wal_once
_table_columns = _db._table_columns
DB_PATH = _db.DB_PATH
BACKUP_DIR = _db.BACKUP_DIR
esc = _text.esc
```

This shim is the heart of the strategy. The other 783 functions still call `get_db()` from `server.py` — they don't know or care it's now a re-export.

### Dependencies to isolate

- `Path`, `os`, `sqlite3`, `threading` — pure stdlib, fine.
- `RENDER_DISK` resolution depends on whether `/data` exists. Move the resolution into `app/core/db.py`; return the resolved `DB_PATH` and `BACKUP_DIR` constants.

### Risks

- **Import order.** If `server.py` initializes constants from `app.core.db` *after* a function defined earlier already references the old constants, the constants are stale. Mitigation: do the imports at the top of `server.py`, before any `def`.
- **WAL pragma double-apply.** Already guarded by `_DB_WAL_APPLIED` + lock. Moving the guard moves with the code; safe.
- **Logging differences.** If the moved code prints with `flush=True`, keep that; Render captures stdout for live tail.

### Compatibility precautions

- Add a `from app.core import db` import at the very top of `server.py`.
- Keep the bare names (`get_db`, `_table_columns`, `DB_PATH`) re-exported at module top level.
- Do *not* rename anything in this phase. Renames are Phase 9+.

### Expected file structure after Phase 1

```
NEw Update/
├── server.py                     # 1 import block + compat shims at top, otherwise unchanged
├── app/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── db.py                 # ~50 lines extracted
│       └── text.py               # ~30 lines extracted
└── ... (everything else unchanged)
```

### Phase 1 testing checklist

- `python3 -m py_compile server.py` exits 0.
- `python3 -m py_compile app/core/db.py app/core/text.py` exits 0.
- Boot the app on Render staging branch.
- Hit each of these routes (manual or via the smoke test script described in Stability section):
  - `GET /health` → 200 OK
  - `GET /login` → 200 OK
  - Admin login → 302 to admin home
  - `GET /admin/community-welfare` → 200
  - `GET /admin/nurses` → 200
  - `GET /admin/legal-cases` → 200
  - `GET /admin/death-cases` → 200
  - `GET /admin/welfare-cases` → 200
  - `GET /api/admin/nurses/summary` → JSON with `success: true`
  - `GET /api/admin/gl/list` (admin role) → JSON
  - `GET /api/admin/ambassador-pulse-export.csv?days=7` → CSV file
  - Nurse login + nurse portal load → 200
  - One nurse complaint submission round-trip → 200
- Verify `evacuation.db` file size unchanged after a fresh boot (no schema regression).
- Tail Render logs for 10 minutes; confirm no `[DB] WAL apply warning` regressions.

---

## Compatibility Layer Strategy

The whole strategy is: **`server.py` remains the only routing entrypoint forever, until we decide otherwise**.

### Pattern 1 — re-export shim (Phase 1–3)

```python
# server.py top
from app.core.db import get_db, _apply_wal_once, _table_columns, DB_PATH, BACKUP_DIR
from app.core.text import esc
```

Existing call sites compile and run unchanged.

### Pattern 2 — domain handler delegation (Phase 3+)

```python
# app/domains/grading_letter/api.py
def api_gl_nurse_summary(data): ...
def api_gl_nurse_submit(data): ...

# server.py
from app.domains.grading_letter import api as _gl_api
api_gl_nurse_summary = _gl_api.api_gl_nurse_summary
api_gl_nurse_submit  = _gl_api.api_gl_nurse_submit
```

Handler branches in `do_GET`/`do_POST` continue calling `api_gl_nurse_summary(data)` — they don't know it's been moved.

### Pattern 3 — explicit route registry (Phase 5+)

When extracting a domain whose route count is large enough that branch-deletion in `Handler` is desirable, introduce the route registry:

```python
# app/routing/registry.py
ROUTES_GET  = []   # list of (path_or_pattern, callable, role_check_fn)
ROUTES_POST = []

def register(method, path, fn, role_check=None):
    target = ROUTES_GET if method == "GET" else ROUTES_POST
    target.append((path, fn, role_check))

# app/domains/grading_letter/urls.py
from app.routing.registry import register
from .api import api_gl_nurse_summary, api_gl_nurse_submit
register("GET",  "/api/nurses/grading-letter", api_gl_nurse_summary)
register("POST", "/api/nurses/grading-letter/submit", api_gl_nurse_submit)

# server.py do_GET (excerpt)
for path_or_pat, fn, role_check in ROUTES_GET:
    matched = (path == path_or_pat) if isinstance(path_or_pat, str) else path_or_pat.match(path)
    if matched:
        if role_check and not role_check(self):
            self.send_json({'success': False, 'error': 'Unauthorized'}, 403)
            return
        body = fn(params)
        self.send_json(body, 200 if body.get('success') else 400)
        return
# ... fallback to existing elif tree for not-yet-extracted routes
```

The registry is *additive* — old `elif` branches stay until the domain is fully migrated. The Handler shrinks one extraction at a time.

### Pattern 4 — schema delegation (Phase 5+)

```python
# app/domains/grading_letter/schema.py
def ensure_schema(db): ...   # was _init_grading_letter_db

# server.py init_db()
def init_db():
    db = get_db()
    db.executescript("""... base tables only ...""")
    from app.domains.grading_letter.schema import ensure_schema as gl_ensure
    from app.domains.housing.schema import ensure_schema as nh_ensure
    from app.domains.onboarding.schema import ensure_schema as no_ensure
    gl_ensure(db); nh_ensure(db); no_ensure(db)
    # ...
```

This pattern *already exists* (`_init_grading_letter_db`, `_nh_ensure_schema`, `_nurse_onboarding_ensure_schema`). Phase 5 systematizes it.

### Pattern 5 — feature flag escape hatch

Every extraction phase ships behind a feature flag (env var) that, when set false, falls back to the legacy in-`server.py` code path. The flags can be deleted phase-by-phase once stable on Render.

```python
USE_APP_CORE_DB = os.environ.get('USE_APP_CORE_DB', '1') == '1'
if USE_APP_CORE_DB:
    from app.core.db import get_db
else:
    def get_db(): ...   # legacy inline copy retained
```

Use this *only* on extractions that change behavior risk; pure code moves don't need a flag.

---

## Stability & Testing Strategy

### Smoke test (write this first, before any extraction)

`tests/smoke/routes.py` — pure stdlib, no pytest required. Hits ~30 critical routes via `urllib.request` against a running server, prints `OK`/`FAIL` per route.

```python
# tests/smoke/routes.py
import urllib.request, sys
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080'
ROUTES = [
    ('GET', '/health', 200),
    ('GET', '/login',  200),
    ('GET', '/api/public/track?ref=DEMO', None),  # any 2xx/4xx is fine, 5xx fails
    ('GET', '/admin/community-welfare', (302, 200)),
    # ... up to ~30 critical routes
]
def hit(method, path, expect):
    req = urllib.request.Request(BASE + path, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    ok = (expect is None) or (code == expect if isinstance(expect, int) else code in expect)
    print(f"{'OK ' if ok else 'FAIL'} {method:5} {path} -> {code}")
    return ok
ok = all(hit(*r) for r in ROUTES)
sys.exit(0 if ok else 1)
```

Run after every phase: `python3 tests/smoke/routes.py http://localhost:8080`.

### Route inventory & before/after diff

Generate the inventory once, store it in `tests/route_inventory.txt`:

```bash
grep -oE "(elif path ==|elif path in)\s+['\(].*?['\)]" server.py | sort -u > tests/route_inventory.txt
```

After every extraction, regenerate and `diff` against the baseline. The diff should show *only* additions of new routes you intended; never removals or reorderings.

### Per-phase rollout protocol

1. Cut a feature branch named `phase-N-extract-<module>`.
2. Implement the extraction. `server.py` keeps re-exports.
3. Run `python3 -m py_compile server.py`, `python3 -m py_compile app/...`.
4. Boot locally; run `tests/smoke/routes.py`.
5. Open PR; reviewer's checklist: "Does the route inventory diff show only additions?" "Do all four background threads still start?" "Does `init_db()` still call all schema bootstrappers?"
6. Merge to `main`.
7. Render auto-deploys; tail logs for 10 minutes.
8. Run smoke test against production URL.
9. Wait at least one full business day before starting the next phase.

### Rollback

- Render's "Rollback to previous deploy" is the primary rollback. Test it once before Phase 1 by deploying a no-op commit and rolling back.
- Backups already exist (`do_backup`) and rotate (`prune_local_backups`). Verify a backup is taken right before each phase deploys; `do_backup(reason=f'pre-phase-{N}')`.
- Maintain an explicit "kill switch" by deleting `app/` and reverting the import shim — `server.py` should be runnable standalone.

### Git workflow

- Trunk-based with short branches (≤1 phase per branch).
- Mandatory `git diff --check` (whitespace lint) before merge.
- Tag each merged phase: `phase-1-core-db`, `phase-2-email-audit`, etc. Render's pin-deploy can target tags directly for emergency rollback.

### Database backup before each phase

`do_backup` already exists. Add a one-liner to the deploy script: `python3 -c "import server; server.do_backup('pre-phase-N')"`. Store the backup name in the PR description.

### Deployment verification

After Render reports "deploy live":
- Health probe: `GET /health` returns `OK`.
- Smoke test: `python3 tests/smoke/routes.py https://...`.
- Tail Render logs: no `[GradingLetter] migration failed`, no `[NurseHousing] migration failed`, no Python tracebacks.
- Run a single end-to-end nurse portal login as a test user. Then a single admin login.

---

## Technical Debt Scorecard

| Dimension | Score (1–5) | Why |
|---|---|---|
| Maintainability | 1 / 5 | Finding a feature requires `grep`; reading any handler requires reading 200–500 lines of mixed concerns; `Handler` class is 7,518 lines. |
| Stability (production behavior) | 4 / 5 | The portal works, has live users, has WAL + locks + idempotent migrations + backups. Few crashes; recent additions are well-prefixed. |
| Scalability | 1 / 5 | In-process `SESSIONS` dict prevents horizontal scale. SQLite single-file DB is fine for current load but caps growth. Email worker is single-thread. |
| Modularity | 1 / 5 | Single file, single class. Recent additions (`gl_*`, `nh_*`, `nurse_onboarding_*`) show modularity is *possible* — just not yet done at file-system level. |
| Deployment risk | 2 / 5 | One bad change can topple the whole portal because nothing isolates blast radius. Render rollback exists but is a blunt instrument. No staging mirror noted. |
| Onboarding difficulty (new engineer) | 1 / 5 | A new dev must read tens of thousands of lines to find any specific behavior. Function naming is good; file structure isn't. |
| Testing maturity | 0 / 5 | No tests in tree. No smoke script. No CI. |
| Observability | 2 / 5 | `print(..., flush=True)` to Render stdout. No structured logging, no trace IDs, no per-route metrics. |
| Documentation | 2 / 5 | Top-of-file docstring, `HealthWorkers_Welfare_Oversight_Blueprint.md`, recent design docs (grading letter, AJA, MOH). No API reference. |
| Security posture | 3 / 5 | Auth gating exists, login lockouts, password hashing, file path normalization, secrets via env. No CSRF tokens visible; PDF/OCR external tools could be a vector. |

**Overall:** behavior 4, structure 1.

---

## Final Recommendations

### Do these in order

1. **Pin dependency versions** in `requirements.txt` (PyMuPDF, Pillow, etc.) before any extraction. A library version drift on Render is the silent killer of OCR/PDF flows.
2. **Write the smoke test script** (`tests/smoke/routes.py`). Land it on `main` before Phase 1.
3. **Generate the route inventory** baseline and commit it to `tests/route_inventory.txt`.
4. **Phase 1 — Core DB & text helpers** (1 week). The proving-ground extraction.
5. **Phase 2 — Audit + email + backup helpers** into `app/core/` (1–2 weeks). After this lands, the most-touched cross-domain helpers are isolated.
6. **Phase 3 — Onboarding domain** (1 week). Smallest, newest, fully prefixed. Validates the domain-extraction pattern.
7. **Phase 4 — Grading letter + Nurse Housing domains** (2 weeks). Same pattern, larger surface.
8. **Phase 5 — Nurses domain + per-domain `ensure_schema()` consolidation** (2 weeks). Auth-adjacent; requires care.
9. **Phase 6 — Welfare cases + legal + death** (2 weeks).
10. **Phase 7 — Iraq KSA Transit + Note Verbal + Embassy Letters** (2–3 weeks). Largest, most PDF-heavy. Extract HTML to `templates/` first.
11. **Phase 8 — Facility roster, Ambassador Pulse, SITREP, Public forms, Fee collection** (2 weeks). Cross-domain readers and money.
12. **Stop here for at least one quarter.** Let the structure settle. Re-evaluate before considering session-store changes or framework migration.

### Don't do these

- **No framework migration** (Flask, FastAPI, Django). The stdlib server is fine; switching adds risk for marginal gain.
- **No ORM** (SQLAlchemy, etc.). Direct SQL via `db.execute(...)` is auditable and idempotent. The migration pattern (`ALTER TABLE ... ADD COLUMN` in try/except) is well-suited to SQLite and would fight an ORM.
- **No big-bang refactor.** Every extraction must be reversible by reverting one PR.
- **No URL changes.** Auth gates are path-prefix-based. URL renames cascade.
- **No sessions storage swap until Phase 6+.** Keep `SESSIONS` in-process for now.
- **No deletion of inline HTML constants until templates exist.** Move HTML to `templates/` *first*, then delete the constant.
- **No test framework introduction in Phase 1.** A standalone smoke script is enough; pytest can come later.
- **No new background threads.** The four existing ones are already a stretch for a stdlib server. Use the existing email worker queue for any deferred work.

### Acceptance criteria for "phased modularization complete"

- `server.py` ≤ 5,000 lines, none of it route handlers.
- All 63 tables created via per-domain `ensure_schema()` calls.
- One `tests/smoke/routes.py` covering ≥ 40 critical routes, runnable in CI.
- Zero embedded HTML page constants (all moved to `templates/`).
- The `Handler` class shrinks from 7,518 lines to ≤ 800 lines (routing + auth + body parsing only).
- A new engineer can locate any feature within 60 seconds via the file system.
- Render's deploy script unchanged.

### Commit cadence

One PR per phase. PR title: `phase-N: extract <module>`. PR body must include: (a) the route inventory diff, (b) the smoke test output, (c) the pre-phase backup name, (d) a one-line rollback instruction.

---

## Appendix A — Extraction template

When extracting domain `X`:

```
app/domains/<x>/
├── __init__.py
├── schema.py        # ensure_schema(db) — was _x_ensure_schema in server.py
├── helpers.py       # _x_clean_text, _x_*_normalize, etc. (private)
├── service.py       # business logic, no HTTP, no print, no send_json
├── api.py           # api_<x>_* functions (HTTP-aware: take dict in, return dict out)
├── csv_export.py    # if applicable, export functions returning (bytes, fname, err)
├── urls.py          # ROUTES list of (method, path, callable, role_check)
└── templates/       # if applicable, HTML extracted from server.py constants
```

Order of operations *inside* one phase:

1. Create the package skeleton with empty modules.
2. Move `_x_*` helpers to `helpers.py`. Re-export from `server.py`.
3. Move schema to `schema.py`. Replace `_x_ensure_schema` body in `server.py` with a delegate call.
4. Move `api_x_*` to `api.py`. Re-export in `server.py`.
5. Move HTML page constants to `templates/`. Update `cwa_module_page`/`render_template` callers.
6. Add `urls.py` registry; switch `do_GET`/`do_POST` branches to use registry; delete the old `elif`.
7. Smoke test, route-inventory diff, deploy.

---

## Appendix B — Files most likely to need extraction first

These functions/blocks are the highest-leverage extraction targets and are mentioned by line ranges to guide the first reviewer reading `server.py`:

| Function | Approx. line | Domain | Why move first |
|---|---|---|---|
| `get_db` | 141 | core | Hundreds of callers; pure stdlib; safe extraction. |
| `_apply_wal_once` | 120 | core | Single global, lock already in place. |
| `_table_columns` | 4392 | core | Tiny, pure helper. |
| `_enqueue_email_job` | 2869 | core | Email queue contract — shared by every domain. |
| `_email_worker_loop` | 3903 | core | Background thread; isolate to test in future. |
| `_init_grading_letter_db` | 251 | grading_letter | Already a self-contained schema bootstrapper. |
| `_nh_ensure_schema` | 315 | housing | Already idempotent. |
| `_nurse_onboarding_ensure_schema` | (added in this audit's prior patch) | onboarding | Already structured for extraction. |
| `_gl_*` family | ~9000–11800 | grading_letter | Block of ~120 functions, well-prefixed. |
| `nh_*` family | ~5800–6100 | housing | Already well-prefixed. |

---

## Appendix C — One-line description of each phase

| Phase | Length | Outcome |
|---|---|---|
| 1 | 1 wk | `app/core/db.py`, `app/core/text.py`. Re-exports in `server.py`. Smoke test green. |
| 2 | 1–2 wk | `app/core/audit.py`, `app/core/email.py`, `app/core/settings.py`. |
| 3 | 1 wk | `app/domains/onboarding/`. First domain extraction. |
| 4 | 2 wk | `app/domains/grading_letter/`, `app/domains/housing/`. |
| 5 | 2 wk | `app/domains/nurses/`. `init_db()` thinned via per-domain `ensure_schema()`. |
| 6 | 2 wk | `app/domains/welfare/`, `app/domains/legal/`, `app/domains/death/`. |
| 7 | 2–3 wk | `app/domains/iraq/`, `app/domains/note_verbal/`, `app/domains/letters/`. Templates extracted. |
| 8 | 2 wk | `app/domains/facility/`, `app/domains/ambassador_pulse/`, `app/domains/sitrep/`, `app/domains/public/`, `app/domains/fee/`. |

Total: ≈ 13–17 weeks of focused work, comfortably parallelizable across one to two engineers.

---

*End of audit.*
