# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pakistan Embassy Kuwait — Community Welfare Portal ("cwakuwait"). A single-file Python HTTP server (`server.py`, ~52,000 lines) backed by SQLite, serving both Jinja-style HTML templates and a React/TypeScript SPA. Deployed on Render.com.

**Default local login:** `admin` / `embassy2026`

## Running the Application

```bash
# Start the backend (port 8080)
python3 server.py

# Frontend dev server (hot-reload, proxied to backend on :8080)
cd community-welfare-ui && npm run dev
```

The backend auto-detects `community-welfare-ui/dist/` and serves the built React app. In production, the React SPA is served from the same origin as the backend.

## Backend Commands

```bash
# Syntax check (run before any commit touching server.py)
python3 -m py_compile server.py

# Install Python dependencies (local dev)
pip install -r requirements.txt

# macOS: install PDF tools for OCR
brew install poppler tesseract
```

## Frontend Commands

```bash
cd community-welfare-ui

# Install
npm ci

# Dev server
npm run dev

# Production build (output: community-welfare-ui/dist/)
npm run build

# Lint
npm run lint

# Seasonal campaign smoke test
npm run smoke:campaign
```

## Testing

```bash
# Full smoke suite (requires server running on :8080)
python3 tests/smoke/routes.py http://localhost:8080

# Individual smoke scripts (run same way)
python3 tests/smoke/fee_collector_expense_ledger_access.py http://localhost:8080
python3 tests/smoke/grading_letter_pdf_layout.py http://localhost:8080
python3 tests/smoke/nurse_service_access.py http://localhost:8080

# Hostel partner module (AJA Care)
python3 tests/smoke/hostel_module.py http://localhost:8080     # read-only gates
python3 tests/smoke/hostel_workflow.py http://localhost:8080   # E2E, localhost only, MUTATES local DB
```

Known issue: `grading_letter_pdf_layout.py` fails with `KeyError: 'relation_text'` — pre-existing
test-script bug (reproduces on pre-hostel baseline), unrelated to server code.

All smoke tests are read-only stdlib HTTP checks. A successful run prints `Failed: 0` and `5xx failures: 0`.

## Build (Render.com)

`build.sh` is the Render build command. It installs `tesseract-ocr`, `poppler-utils`, Python packages, then builds the React SPA. Requires Node.js 20.19+.

## Architecture

### Backend (`server.py`)

A single-file `http.server.BaseHTTPRequestHandler` subclass (`Handler`, defined at line ~34656). Everything lives in this one file: DB schema migrations, PDF generation, OCR, email, OneDrive backup, TOTP 2FA, session management, and all HTTP route handlers.

**Key structural patterns:**
- `init_db()` — runs on startup, applies SQLite schema migrations in-place (additive only, never destructive)
- `get_db()` — returns a per-request SQLite connection (WAL mode)
- `require_auth(role?)` — auth guard; redirects unauthenticated requests to `/login`
- `can_access_api_route(role, path)` / `can_access_admin_route(role, path)` — RBAC checks
- `_HeavyJobGuard` — mutex protecting OCR/PDF rasterization paths on Render's 512 MB instance
- Routes are matched with `if path == '...'` / `elif path.startswith('...')` chains inside `do_GET` and `do_POST`

**Storage layout:**
- Local dev: `evacuation.db`, `backups/`, `approval_uploads/`, `note_verbal_uploads/` in project root
- Render production: same paths under `/data/` (persistent disk)

**PDF pipeline (MOFA approval letters):** tries (1) pypdf text layer → (2) `pdftotext` CLI → (3) raster OCR (Pillow + pytesseract + pdf2image). PyMuPDF handles Note Verbal PDF rendering.

### Frontend (`community-welfare-ui/`)

React 19 + TypeScript + Vite, with React Router v7. No state management library. API calls go through `src/lib/api.ts` which resolves base URLs from `VITE_API_BASE_URL` / `VITE_BACKEND_PORTAL_URL` env vars (falls back to same-origin in production).

**Route split:** Most admin pages are server-rendered HTML templates. The React SPA handles only the Community Welfare section and Nurses sub-system. The set `COMMUNITY_WELFARE_UI_REACT_ROUTES` in `server.py` controls which paths the backend hands off to `index.html`.

**`PublicRouteForwarder`** — component that intercepts KSA Transit alias paths (`/register`, `/ksa-transit`, `/transit-visa`, etc.) and redirects to the backend portal URL.

**`src/lib/seasonalCampaigns.ts`** — date-window logic for temporary UI campaigns (e.g. International Nurses Day). Update the `INTERNATIONAL_NURSES_DAY_CAMPAIGN_*` constants here to change campaign dates for future years.

### TOTP 2FA (`totp_auth.py`)

Dormant Phase 0 implementation. The module is imported optionally; if import fails, 2FA is silently disabled. **Do not modify auth flow or session logic** without re-running the full smoke suite — the 2FA routes (`/api/auth/2fa/*`, `create_session`, `upgrade_session_after_2fa`) are load-bearing.

## Feature Flags

| Flag | Default | Control |
|------|---------|---------|
| `ROUTE_REVIEW_ENABLED` | `False` | Hardcoded in `server.py:60` |
| `FEATURE_GRADING_LETTER` | `True` | Hardcoded |
| `FEATURE_NURSE_HOUSING` | `True` | `FEATURE_NURSE_HOUSING` env var |
| `FEATURE_NURSE_ONBOARDING` | `True` | `FEATURE_NURSE_ONBOARDING` env var |
| `FEATURE_NURSE_ACCOMMODATION_ADMIN` | `True` | `FEATURE_NURSE_ACCOMMODATION_ADMIN` env var |

Set env var to `0`, `false`, `no`, or `off` to disable.

## Key Env Vars

| Variable | Purpose |
|----------|---------|
| `PORT` | HTTP port (default `8080`) |
| `PUBLIC_SITE_URL` | Canonical public URL (default `https://cwakuwait.com`) |
| `ONEDRIVE_CLIENT_ID`, `ONEDRIVE_CLIENT_SECRET`, `ONEDRIVE_REFRESH_TOKEN` | OneDrive backup (Render) |
| `VITE_API_BASE_URL` | Frontend: backend API base (production: leave empty for same-origin) |
| `VITE_BACKEND_PORTAL_URL` | Frontend: backend portal URL for KSA Transit redirects |

## Modularization Status

The codebase is at **Phase 0** of a planned modularization. `app/core/` exists as an empty package stub. **Do not move functions out of `server.py`** until Phase 1 is explicitly started. `tests/route_inventory.txt` is the frozen route baseline — every route listed there must continue to exist after any refactor.

**Exception — `app/domains/hostel/` (added 2026-07-07):** the Hostel / Nurse Accommodation Partner module (AJA Care) was built directly as a domain module rather than inside `server.py`. It is additive-only: `server.py` imports it guarded (`HOSTEL_MODULE`), injects helpers via `hostel.configure(...)`, calls `hostel.ensure_schema(db)` from `init_db()`, and forwards `/admin/hostel-accommodation`, `/hostel/*`, `/api/hostel/*`, `/api/admin/hostel/*` to `hostel.handle_get/handle_post` from the tail of the `do_GET`/`do_POST` chains. Partner logins live in `hostel_partner_users` (PBKDF2) with their own `hostel_session` cookie and in-memory session store — deliberately separate from staff `SESSIONS` (staff RBAC gives every `users`-table role a `/staff/my-cases` access floor, so partners must never be staff users). Tables: `hostel_partners`, `hostel_partner_users`, `hostel_assignments`, `hostel_agreements`, `hostel_audit` (append-only), `hostel_ref_counter`. Agreement files: `hostel_agreement_uploads/` (under `/data` on Render). See `docs/hostel_module_audit_and_plan.md`.
