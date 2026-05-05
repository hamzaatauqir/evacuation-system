# Grading Letter Workflow — System Design

Embassy of Pakistan, Kuwait — Community Welfare Portal
Author: design pass for Raza Ali, 2026-05-05

---

## 1. Recommended Workflow

States and allowed transitions:

- **Draft** *(optional, can be deferred to v2)* → **Submitted** when the nurse clicks Submit.
- **Submitted** → **Under Review** as soon as an admin opens the record (auto on first view, or manually).
- **Under Review** → **Correction Required** when admin sends it back with notes.
- **Correction Required** → **Submitted** when the nurse re-submits with fixes.
- **Under Review** → **Approved** after admin confirms data and computed grade.
- **Approved** → **Letter Generated** when admin clicks *Generate Letter*; system creates docx (and optional PDF) and attaches it to the record.
- **Letter Generated** → **Issued** when admin marks the letter as physically/digitally delivered.
- Any non-terminal state → **Rejected** or **Cancelled** (terminal, append-only).

Two key invariants:

1. After **Approved**, the data row is locked. Edits require an explicit *Reopen* that returns the record to **Under Review** and writes an audit entry.
2. After **Issued**, the row and the generated file are immutable. Reissue creates a *new* application referencing the prior reference number (e.g., `REISSUE-OF: GL-2026-0123`).

This guarantees no silent rewrite of an officially issued letter.

---

## 2. Nurse-Side Form Layout

**Tab title:** Grading Letter (new tab inside the nurse dashboard, beside Complaints)

**Header card — read-only, auto-filled from nurse profile:** Name, Father Name, Passport No., CNIC, Civil ID, Mobile, Email. Caption: "If any of these are wrong, update your profile first."

**Section A — Qualification**

- Qualification Type (dropdown, required): BSN Nursing 4 Years; Post RN BSN; General Nursing Diploma; Nursing Diploma; Midwifery / Additional Course; Other (text becomes required).
- Degree Title as printed on certificate (text, required, defaults from qualification but editable so it matches the certificate exactly).
- Student / Roll No. (text, required).
- College / Institute (text, required).
- University / Affiliating Body (text, required).
- Year of Passing (dropdown, required).

**Section B — Grading Mode** (radio, exactly one)

- Marks (Total + Obtained)
- Percentage (direct)
- GPA out of 4.00

Conditional fields:

- If **Marks**: Total Marks (> 0), Obtained Marks (≥ 0, ≤ Total).
- If **Percentage**: Percentage (0–100, up to 2 decimals).
- If **GPA**: GPA Obtained (0.00–4.00, max **fixed and locked at 4.00**).

**Live preview** (read-only, computed): Computed Percentage, Provisional Grade Label. Caption: "Final grade is verified by Embassy admin before letter is issued. The label here is provisional."

**Section C — Supporting Documents**: Degree/Diploma scan (required); Final transcript / mark sheet (required); Passport bio page (auto-attached if on profile); Optional: equivalence certificate or university conversion table.

**Section D — Declaration**: Checkbox "I confirm the information and uploaded documents are true. I understand the Embassy issues this letter without liability." Submit button disabled until valid + checkbox.

**If a request already exists in a non-terminal state**, the form is read-only and shows a status banner (reference number, last update, admin notes if any). A *Cancel Request* button is available for **Submitted** and **Correction Required** only.

---

## 3. Admin-Side Review Layout

**Backend tab:** Community Welfare → *Nurse Grading Letters*

**List view** with top filters (status, qualification, date range, search by passport / name / reference):

| Ref No. | Nurse Name | Passport | Qualification | Mode | Computed % | Grade | Status | Submitted | Actions |

Bulk actions: *Export CSV*, *Mark batch as Under Review*.

**Detail view — three columns**

*Left — Identity & Qualification:* identity card from nurse profile; document previews (click to view full).

*Middle — Editable computed data (admin only):* mode (admin can switch with confirmation if nurse picked the wrong one); Total / Obtained / Percentage / GPA; Computed Percentage (auto, but admin can override — toggling override reveals a required *Override Reason* textarea); Grade Label (auto from active scale, override-able with required reason); live letter preview pane.

*Right — Workflow & Audit:* status pill + transition buttons (*Request Correction*, *Approve*, *Reject*, *Generate Letter*, *Mark Issued*); correction notes textarea (sent back to nurse); audit log (every field change, override, and status transition with actor and timestamp); internal admin notes (not shown to nurse).

*Approve* runs a confirmation dialog showing the final letter text the system will print. After Approve, the data row is locked; *Reopen* returns to Under Review and writes audit.

---

## 4. Database / Table Design

All new tables prefixed `gl_` to avoid collisions in the existing monolith. SQLite-friendly types.

**`gl_applications`**
- `id` INTEGER PK
- `ref_no` TEXT UNIQUE — e.g. `GL-2026-000123`
- `nurse_id` INTEGER FK → `nurses(id)`
- `qualification_code` TEXT — `BSN4`, `POSTRN_BSN`, `GND`, `ND`, `MIDWIFERY`, `OTHER`
- `qualification_other` TEXT NULL
- `degree_title`, `student_no`, `institute`, `university` TEXT
- `year_of_passing` INTEGER
- `mode` TEXT — `MARKS`, `PERCENT`, `GPA`
- `total_marks`, `obtained_marks`, `entered_percentage`, `entered_gpa` REAL NULL
- `computed_percentage` REAL — what the system calculated
- `final_percentage` REAL — what prints on the letter; equals `computed_percentage` unless admin overrides
- `final_grade_label` TEXT — looked up from active scale; admin-override-able
- `override_reason` TEXT NULL
- `relation_override` TEXT NULL — `D/o` or `S/o`, falls back to gender-based default
- `scale_version_id` INTEGER FK → `gl_grading_scale(id)` — frozen at approve time
- `status` TEXT — see workflow
- `correction_notes`, `internal_notes` TEXT NULL
- `letter_path`, `letter_pdf_path` TEXT NULL
- `created_at`, `updated_at`, `submitted_at`, `approved_at`, `generated_at`, `issued_at`

**`gl_documents`** — `id`, `application_id` FK, `doc_type`, `original_name`, `storage_path`, `sha256`, `uploaded_at`.

**`gl_audit`** — append-only — `id`, `application_id` FK, `actor_role` (NURSE/ADMIN), `actor_id`, `event_type`, `field_name`, `old_value`, `new_value`, `note`, `created_at`. Application code never UPDATEs or DELETEs this table.

**`gl_grading_scale`** — `id`, `name`, `is_active`, `created_at`, `created_by`. Versioned (deactivated, not deleted).

**`gl_grading_scale_band`** — `id`, `scale_id` FK, `min_pct`, `max_pct`, `label`. Bands must be contiguous, no overlap.

**`gl_gpa_conversion`** — `id`, `name`, `is_active`, `method` (`LINEAR` | `TABLE`), `created_at`, `created_by`.

**`gl_gpa_conversion_band`** *(used when `method=TABLE`)* — `id`, `conv_id` FK, `min_gpa`, `max_gpa`, `percent`.

**`gl_settings`** — single-row key/value: `rounding_dp` (default 2), `allow_parallel_applications` (0/1, default 0), `letter_template_path`, `ref_no_pattern`.

**`gl_ref_counter`** — `year` PK, `next_seq` — for the per-year `GL-2026-000123` counter, accessed under `BEGIN IMMEDIATE`.

Indexes: `nurse_id`, `status`, `ref_no`, `submitted_at`.

---

## 5. Grading Calculation Method

**Step 1 — compute percentage from input mode**

- `MARKS`: `pct = round((obtained / total) * 100, rounding_dp)`
- `PERCENT`: `pct = round(entered_percentage, rounding_dp)`
- `GPA`: `pct = round(gpa_to_percent(entered_gpa, active_conversion), rounding_dp)`

**Step 2 — derive grade label from the active scale**

Pick the band where `min_pct ≤ pct ≤ max_pct`. Bands are contiguous and must cover 0–100. If no band matches (out of range or scale misconfigured), label = "Pending Admin Review" and the record is flagged for **Correction Required**.

**Step 3 — admin override**

Admin can override `final_percentage` and/or `final_grade_label`. Both overrides require a reason logged to the audit table. The letter always prints from `final_*`, never from `computed_*` or the raw `entered_*` fields.

---

## 6. GPA out of 4.00 Conversion Approach

Pakistani universities don't share a single GPA→% formula, so the system supports two methods:

**LINEAR** *(default for v1)*
- `pct = (gpa / 4.00) * 100`
- 3.65 → 91.25% (matches the existing sample letter exactly)
- Pro: deterministic, transparent, consistent with letters Embassy already issues manually.
- Con: doesn't match HEC tables at the high end.

**TABLE** *(admin-curated, v2)*
- Admin defines GPA bands (e.g., 3.71–4.00 → "Exceptional" with a representative percent).
- System picks the band's percent or interpolates linearly within the band.

**Recommendation for v1:** ship LINEAR active, with admin per-record override. Add TABLE in v2 once the Embassy formally chooses a canonical mapping. The 91.25% sample letter is exactly LINEAR output from 3.65/4.00, so v1 produces identical results to current manual practice.

GPA cap is enforced at three layers: form (locked at 4.00), server validation (raise on > 4.00), and DB CHECK constraint.

---

## 7. Midwifery / Additional Qualification Handling

**One application = one credential = one letter.** Combining a BSN and a Midwifery diploma on a single letter creates ambiguous percentages and is reputationally risky.

If a nurse needs grading for both BSN and Midwifery, that is two applications, two reference numbers, two letters.

Interaction with the repeat rule: when a previous application is in a terminal state (Issued, Rejected, Cancelled), the new one is allowed automatically. If the previous one is still active and the nurse genuinely needs a parallel application for a *different* qualification, admin can either flip `allow_parallel_applications` globally or grant a per-nurse permit (one-shot, consumed on use). A nurse can never have two active applications for the same qualification code, even with a permit.

The "Other" category is a free-text fallback (e.g., "Cardiac Care Certificate"); admin should review the spelling carefully before approving since it prints verbatim.

---

## 8. Repeat Application Rules

Status buckets:

- **Active (blocks new):** Submitted, Under Review, Correction Required, Approved, Letter Generated.
- **Terminal (allows new):** Issued, Rejected, Cancelled.
- **Draft:** at most one per nurse; submitting converts the existing draft.

If a nurse has an active application: the tab shows the status banner, no Apply button.
If terminal or none: the Apply form is shown.

Override path: `gl_settings.allow_parallel_applications=1` globally, or a per-nurse permit row for a different qualification only. The constraint "no two active for the same qualification code" is non-overridable.

---

## 9. Letter Generation Process

**Template:** `letter_templates/grading_letter_v1.docx` with placeholders `{{ref_no}}`, `{{date}}`, `{{name}}`, `{{relation}}`, `{{father_name}}`, `{{passport_no}}`, `{{degree_title}}`, `{{student_no}}`, `{{institute}}`, `{{university}}`, `{{year}}`, `{{percentage}}`, `{{grade}}`.

**Generation flow:**

1. Admin clicks *Generate Letter* on an Approved application.
2. Server loads the template, replaces placeholders using `final_*` columns + nurse profile.
3. Saves to `generated_letters/{ref_no}.docx`.
4. Sets `letter_path`, transitions to **Letter Generated**, writes audit.
5. Optional: convert to PDF via headless `soffice` if the existing portal already does so for other letter types — reuse that helper.
6. Admin downloads, prints, signs/stamps physically, then clicks *Mark Issued*.

**Re-generation:** allowed only while still in **Letter Generated**. Each regeneration overwrites the file but stores the prior file's SHA-256 hash in the audit row. Once **Issued**, the file is read-only on disk (chmod 0444) and the route returns the existing file.

`relation` defaults to `D/o` if `nurse.gender = F`, `S/o` otherwise; admin can override per record via `relation_override`.

---

## 10. Admin Controls / Settings Needed

**Settings → Grading Letter** page in the admin tab:

*Grading scale.* View active scale; edit bands; save as a new version (versioned, never destructive). Default seed (admin must confirm before going live): 80–100 Excellent, 70–79.99 Very Good, 60–69.99 Good, 50–59.99 Pass, 0–49.99 Fail. The sample letter's "Excellent at 91.25%" fits this seed; the Embassy should explicitly accept the seed or replace it before any issue.

*GPA conversion.* Method toggle (LINEAR | TABLE). If TABLE, edit bands.

*Qualifications list.* CRUD for the dropdown + display labels printed in the letter.

*Letter template.* Upload a new docx; system validates required placeholders are present; preview render with sample data.

*Other.* Rounding decimal places (default 2). Allow parallel applications (default off). Email notification toggles for Submitted/Approved/Issued (v2). Reference number pattern (default `GL-{year}-{6}`).

*Roles.* Existing Community Welfare Admin acts; an optional second role *Grading Letter Reviewer* can be added later.

---

## 11. Risks and Safeguards

**Risks**

- Wrong grade label printed on official letter (e.g., 85% printed as Excellent when Embassy meant Exceptional) → reputational and legal exposure.
- GPA→% mismatch across universities.
- Forged or doctored degree scans.
- Nurses race to apply repeatedly, swamping admins.
- Issued letters silently re-edited.
- Pressure to alter an issued record erodes trust.
- Regressions in the existing monolithic `server.py` (welfare cases, fee ledger, Iraq transit, Ambassador Pulse, etc.).

**Safeguards**

- Mandatory admin verification before any letter generation; nurses cannot trigger generation.
- Active grading scale is admin-versioned, never overwritten; each application stores `scale_version_id` so re-printing always uses the scale active at approval time.
- Override of percentage or grade requires a typed reason logged to immutable audit.
- Documents stored with SHA-256 recorded on the application and audit; any swap is detectable.
- One active application per nurse per qualification; rate-limit submissions per IP and per nurse_id (e.g., 3/day).
- Issued letters and their files are write-locked; reissue creates a new application referencing the original.
- Audit log is append-only at the code path; a daily integrity job hashes the table and stores the chain hash so tampering is detectable.
- All new endpoints behind existing auth; no new public routes.
- Add new tables only; do not alter existing tables; do not share row IDs or sequences with existing flows.
- Feature flag `FEATURE_GRADING_LETTER` defaulting on only after migrations succeed; existing flows untouched if the flag is off.

---

## 12. Suggested Minimal First Version

Ship in 1–2 weeks:

- New nurse tab "Grading Letter" with the form described in §2.
- Modes: Marks, Percentage, GPA (LINEAR conversion only).
- One default grading scale, editable from a single admin settings page (full versioning UI deferred — DB still records `scale_version_id`).
- Admin list + detail view + actions: Request Correction, Approve, Generate Letter, Mark Issued, Reject, Cancel.
- Docx letter generation (PDF deferred — admin can save-as PDF locally for v1).
- Audit log (append-only).
- Repeat-application rule.
- Reference number generation (`GL-2026-000123`).
- CSV export of the admin list.

Deferred to v2+:

- TABLE GPA conversion.
- Versioned scales with full UI for diffing/restoring.
- Email/SMS notifications to nurse.
- Auto PDF + e-signature + verification QR.
- Bulk approve.
- Per-nurse permit table for parallel applications (v1: just the global flag).
- OCR ingestion of degree scans.
- Public tracker page.

---

## 13. Future Improvements

- OCR ingestion of degree/transcript with field-by-field confidence and admin approval — can reuse the same approval-review pattern already used by the project's OCR matching workflow.
- Digital signature + QR code on PDF for verifiability; Embassy hosts a public verify endpoint.
- Multi-language templates (Urdu/English).
- Public applicant tracker (passport + ref number, no login).
- API for HEC or universities to verify a letter.
- Batch issuance for cohorts (e.g., 30 graduates from one nursing college).
- Rule-based auto-approval for high-confidence cases, still gated by admin.
- Dashboards for processing time, backlog, rejection reasons.
- Generalize `gl_*` to a generic `letter_*` engine and roll the same flow to NOC, Experience Letter, etc.

---

## 14. Implementation Prompt for Codex / Cursor

Paste the block below into Codex/Cursor against the existing `server.py` repository. It is self-contained and intended to add the workflow without touching existing features.

---

````
You are extending an existing Embassy of Pakistan, Kuwait Community Welfare portal implemented as a single-file Python stdlib monolith (`server.py`) using `http.server` style routing and SQLite. Existing features that MUST keep working unchanged: nurse registration/login, nurse complaints, legal cases, death cases, welfare cases, fee ledger, Iraq transit, Ambassador Pulse export. Do not modify any of their tables, routes, templates, JS, or shared utilities except to add small additive helpers.

# constraints

- Python 3 stdlib only unless `python-docx` is already imported in `server.py`. If it is, reuse it. If not, reuse whatever docx-templating helper already exists in the file (look for functions that build .docx for other letter types and follow that exact pattern).
- All new code lives behind a feature flag `FEATURE_GRADING_LETTER` near the top of the file; default to True only after migrations succeed.
- All new tables and routes are prefixed `gl_` / `/gl/...` and `/admin/gl/...` to avoid collisions.
- No new external services, no new network calls, no new dependencies.
- Add new tables only; do not alter existing tables.
- Append-only audit: never UPDATE or DELETE rows of `gl_audit`.
- Do not change formatting on existing lines; restrict diffs to additions.

# migrations (idempotent CREATE TABLE IF NOT EXISTS, run on startup after existing migrations)

1. `gl_applications` with columns:
   id INTEGER PK, ref_no TEXT UNIQUE, nurse_id INTEGER FK, qualification_code TEXT,
   qualification_other TEXT, degree_title TEXT, student_no TEXT, institute TEXT,
   university TEXT, year_of_passing INTEGER, mode TEXT CHECK(mode IN ('MARKS','PERCENT','GPA')),
   total_marks REAL, obtained_marks REAL, entered_percentage REAL,
   entered_gpa REAL CHECK(entered_gpa IS NULL OR (entered_gpa >= 0 AND entered_gpa <= 4.0)),
   computed_percentage REAL, final_percentage REAL, final_grade_label TEXT,
   override_reason TEXT, relation_override TEXT, scale_version_id INTEGER,
   status TEXT NOT NULL, correction_notes TEXT, internal_notes TEXT,
   letter_path TEXT, letter_pdf_path TEXT,
   created_at, updated_at, submitted_at, approved_at, generated_at, issued_at
2. `gl_documents` (id, application_id, doc_type, original_name, storage_path, sha256, uploaded_at)
3. `gl_audit` (id, application_id, actor_role, actor_id, event_type, field_name, old_value, new_value, note, created_at)
4. `gl_grading_scale` (id, name, is_active, created_at, created_by) + `gl_grading_scale_band` (id, scale_id, min_pct, max_pct, label)
   Seed one active row "Embassy Default" with bands:
     80–100 Excellent, 70–79.99 Very Good, 60–69.99 Good, 50–59.99 Pass, 0–49.99 Fail
   (Embassy must confirm before going live.)
5. `gl_gpa_conversion` (id, name, is_active, method, created_at, created_by) + `gl_gpa_conversion_band`
   Seed one active LINEAR row.
6. `gl_settings` (key TEXT PK, value TEXT) — keys: rounding_dp=2, allow_parallel_applications=0, letter_template_path='letter_templates/grading_letter_v1.docx', ref_no_pattern='GL-{year}-{seq:06d}'
7. `gl_ref_counter` (year INTEGER PK, next_seq INTEGER) for atomic ref numbers (BEGIN IMMEDIATE).

Indexes: nurse_id, status, ref_no, submitted_at.

# helpers

- `gl_next_ref_no(year)` -> str. Locks `gl_ref_counter` with BEGIN IMMEDIATE; returns formatted ref no.
- `gl_compute_percentage(mode, total, obtained, entered_pct, entered_gpa, settings, conversion) -> float` rounded to settings.rounding_dp. GPA path uses LINEAR by default: (gpa/4.0)*100. Raises ValueError on GPA > 4.0, obtained > total, or out-of-range percent.
- `gl_lookup_grade(pct, scale_id) -> Optional[str]`.
- `gl_write_audit(application_id, actor_role, actor_id, event_type, field=None, old=None, new=None, note=None)`.
- `gl_render_letter(application_id) -> path`. Loads template at settings.letter_template_path, replaces placeholders {{ref_no}},{{date}},{{name}},{{relation}},{{father_name}},{{passport_no}},{{degree_title}},{{student_no}},{{institute}},{{university}},{{year}},{{percentage}},{{grade}}. Saves to generated_letters/{ref_no}.docx. relation defaults to 'D/o' if nurse.gender == 'F' else 'S/o', overridable by relation_override.

# routes — nurse side (require existing nurse auth)

- GET  /nurse/grading-letter — render tab; banner if active app, form if none/terminal.
- POST /nurse/grading-letter/submit — server-side validate (required fields, GPA<=4.0, obtained<=total, percent 0–100, year sane, file mime in {pdf,jpg,jpeg,png}, file size <=5MB). Enforce repeat rule (block if any row in SUBMITTED/UNDER_REVIEW/CORRECTION_REQUIRED/APPROVED/LETTER_GENERATED unless allow_parallel_applications=1 AND different qualification_code). On success, allocate ref_no, compute percentage, look up grade, store final_*, attach docs with sha256, status=SUBMITTED, write audit, return 201.
- POST /nurse/grading-letter/cancel — only from SUBMITTED or CORRECTION_REQUIRED -> CANCELLED, audit.
- POST /nurse/grading-letter/resubmit — from CORRECTION_REQUIRED, recompute, -> SUBMITTED, audit.

# routes — admin side (require existing admin auth + community welfare role)

- GET  /admin/gl/list — paginated, filters (status, qualification, date range, search). 
- GET  /admin/gl/list.csv — CSV export of current filter.
- GET  /admin/gl/<id> — detail.
- POST /admin/gl/<id>/start-review — SUBMITTED -> UNDER_REVIEW.
- POST /admin/gl/<id>/edit — edit any data field; per-field audit; recompute if mode/inputs changed.
- POST /admin/gl/<id>/override — set final_percentage and/or final_grade_label with required override_reason.
- POST /admin/gl/<id>/request-correction — UNDER_REVIEW -> CORRECTION_REQUIRED with required correction_notes.
- POST /admin/gl/<id>/approve — UNDER_REVIEW -> APPROVED, freeze scale_version_id = currently active scale id, lock data row, audit.
- POST /admin/gl/<id>/reopen — APPROVED -> UNDER_REVIEW with required reason.
- POST /admin/gl/<id>/generate — APPROVED -> LETTER_GENERATED, render docx, write letter_path.
- POST /admin/gl/<id>/regenerate — only while LETTER_GENERATED, hash old file, overwrite, audit.
- POST /admin/gl/<id>/mark-issued — LETTER_GENERATED -> ISSUED, chmod 0444 the file, set issued_at, audit.
- POST /admin/gl/<id>/reject — any non-terminal -> REJECTED with reason.
- POST /admin/gl/<id>/cancel — any non-terminal -> CANCELLED.
- GET  /admin/gl/<id>/letter.docx — stream generated docx.
- GET  /admin/gl/settings, POST /admin/gl/settings/update — edit grading scale bands, conversion method, rounding, parallel-apps flag.

Every state-changing route writes a gl_audit row. Reject any state transition that is not in the allowed set above with HTTP 409.

# letter template

Place template at letter_templates/grading_letter_v1.docx. Use the placeholders listed in helpers. If you cannot generate a docx programmatically in this environment, leave a TODO comment and produce letter_templates/grading_letter_v1.txt with the same placeholders so v1 can ship a plain-text equivalent.

# UI

Reuse the existing portal CSS classes and layout helpers. Do not introduce a new framework. The nurse tab is a new section in the existing nurse dashboard template; admin pages live under the existing Community Welfare admin section. Keep table/list styling identical to other admin lists (e.g., welfare cases list).

# verification before declaring done

- Start the server, log in as a nurse, submit a grading letter with each of the three modes; confirm computed percentage matches: marks 425/500 -> 85.00; pct 91.25 -> 91.25; gpa 3.65 -> 91.25.
- Confirm a second submission while the first is SUBMITTED is blocked with 409.
- Log in as admin, walk a record through Submitted -> Under Review -> Approve -> Generate -> Issued; confirm the docx contains the right values and chmod is 0444 after Issued.
- Confirm an Issued record cannot be regenerated.
- Smoke-test every existing menu (nurse registration/login, complaints, legal cases, death cases, welfare cases, fee ledger, Iraq transit, Ambassador Pulse export) — verify nothing 500s and existing data is untouched.
- Confirm the grading scale bands seed exists and is editable from the settings page.

# deliverables

1. Modified server.py with the additions described.
2. letter_templates/grading_letter_v1.docx (or .txt fallback).
3. CHANGES.md listing every new route, table, function, template, migration, and the line ranges in server.py you touched.

Stop after these deliverables. Do not refactor existing code.
````

---

*End of design document.*
