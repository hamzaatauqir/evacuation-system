# Current State Snapshot — Embassy Portal

Updated: 2026-07-12

- **New (2026-07-12, uncommitted):** `app/domains/ads/` — Website Advertisements
  module (admin-managed homepage popup + banner). Admin page
  `/admin/advertisements` (strictly `admin` role); APIs
  `/api/admin/advertisements[/detail|/audit|/save|/status|/duplicate|/upload-image]`;
  public image route `/ads/media/*`; payload embedded into `cwa_home.html` as
  `window.CWA_ADS`, rendered by `static/js/site-ads.js`. Tables
  `website_advertisements` + `website_ad_audit` (append-only). Images in
  `ad_uploads/` (`/data` on Render), backed up by `backup_onedrive.sh` Step 3b.
  Kill-switch `FEATURE_ADVERTISEMENTS=0`. Tests: `tests/smoke/ads_module.py`
  (24), `tests/smoke/ads_workflow.py` (88, localhost E2E, Pillow needed for the
  image-accept suite), `tests/smoke/site_ads_logic.mjs` (26). See DECISION-LOG
  2026-07-12 entry.

- `server.py` ~52k lines, stdlib HTTP + SQLite, Phase 0 modularization baseline
  (smoke suite + frozen `tests/route_inventory.txt`).
- **New:** `app/domains/hostel/` — Hostel / Nurse Accommodation Partner module
  (AJA Care). Admin page `/admin/hostel-accommodation`; partner portal
  `/hostel/login` + `/hostel/dashboard`; APIs `/api/admin/hostel/*` (staff) and
  `/api/hostel/*` (partner, own `hostel_session` cookie). Tables `hostel_*` (6),
  files in `hostel_agreement_uploads/`. Docs: `docs/hostel_module_audit_and_plan.md`.
- Verification state (2026-07-07): `py_compile` clean; `tests/smoke/routes.py`
  49/49; `tests/smoke/hostel_module.py` 21/21; `tests/smoke/hostel_workflow.py`
  39/39 (localhost E2E); route inventory intact (0 missing).
- Local git repo initialized 2026-07-07 (baseline `addafd7`); production data,
  uploads, node_modules are gitignored. Hostel work staged but **not committed** —
  commit pending user review.
- Test artifacts in local dev DB: partner login `hostel-smoke-partner`
  (AJA Care), cancelled smoke assignments on nurse #3 — created by
  `hostel_workflow.py`, safe to leave or delete.
