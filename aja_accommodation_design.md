# Nurse Housing & AJA Accommodation — System Design

Embassy of Pakistan, Kuwait — Community Welfare Portal
Author: design pass for Raza Ali, 2026-05-05

This document covers three intertwined problems: (a) gating who is allowed to use the active nurse portal at all, (b) showing the AJA accommodation workflow only to the right nurses at the right time, and (c) routing nurse complaints cleanly to the Nurses Welfare Desk so they never sit unassigned in the general queue.

---

## 1. Overall Architecture

Three additive subsystems sitting beside the existing portal, all behind a feature flag `FEATURE_NURSE_HOUSING`:

- **Arrival Batch Management** — admin creates batches (e.g., "BATCH-2026-04-30") with arrival date, expected count, hotel/temp provider, AJA eligibility flag, and the lead time before AJA shift opens. Batches are the system of record for "who is officially in Kuwait under Embassy purview."
- **Account Eligibility Gate** — a sidecar table `nh_nurse_account` controls whether a nurse account is `PENDING_ARRIVAL`, `ACTIVE`, `SUSPENDED`, or `REJECTED`. Existing nurses with no sidecar row default to `ACTIVE` (zero migration cost, no regression). New registrations always start `PENDING_ARRIVAL`.
- **AJA Accommodation Module** — nurse-facing tab (only rendered if eligibility passes), agreement signing, decision tracking, vendor export, and post-shift roster (room/bed/check-in/contract).

Plus a fourth, smaller change:

- **Nurse Complaint Routing** — complaints submitted from the nurse portal carry a `source = NURSE_PORTAL` flag (or land in a parallel `nurse_complaints` table — see §13) and are auto-assigned to the Nurses Welfare Desk user (configurable, defaults to Awais). They never sit unassigned and never appear in the general complaints queue.

Roles touched: existing `admin`, plus a new `nurses_welfare_desk` role for Awais (and any backup). Existing roles untouched.

---

## 2. Nurse Registration Eligibility Workflow

Two stages. The existing "register & login" flow stays — but a gate is added before the nurse gets full portal capabilities.

**Stage 1 — Pre-registration (existing flow + sidecar row)**

The nurse fills the existing registration form. On successful registration the system also creates an `nh_nurse_account` row with `account_status = PENDING_ARRIVAL`, `batch_id = NULL`. The nurse can log in but sees only:

- Profile (read-only beyond personal contact info)
- A clear status banner: "Your account is pending arrival confirmation by the Embassy. Most features will unlock after your batch arrives in Kuwait."
- No Complaints tab, no AJA tab, no Grading Letter tab.

This is enforced server-side on every protected route, not just hidden in UI.

**Stage 2 — Activation**

A nurse's account becomes `ACTIVE` only when admin (or the system) does *one* of:

- Links the nurse to an approved arrival batch and marks the batch as `ARRIVED`. All linked nurses flip to `ACTIVE` automatically.
- Manually flips a single nurse to `ACTIVE` with a recorded reason (rare, e.g., a late joiner who arrived outside a batch).

`REJECTED` is terminal (visa denied, withdrew, etc.). `SUSPENDED` is for active nurses who must be temporarily blocked (rare).

**Backward compatibility:** existing nurses without an `nh_nurse_account` row default to `ACTIVE` so the existing portal keeps working without migration ceremony. A one-shot backfill job can be run later when convenient.

---

## 3. Arrival Batch Management Workflow

Admin → Community Welfare → Nurse Housing → **Batches** tab.

A batch carries:

- `batch_code` (e.g., `BATCH-2026-04-30`, auto-suggested from arrival date)
- `arrival_date`
- `expected_count` (e.g., 167–200)
- `temp_accommodation_provider` (e.g., "Hotel XYZ")
- `temp_accommodation_end_estimate` (e.g., arrival_date + 90 days)
- `aja_eligible` (boolean)
- `aja_window_opens_at` (date — when the AJA tab becomes visible to nurses in this batch)
- `aja_window_closes_at` (date — last day to sign)
- `status` — `DRAFT` → `OPEN` → `ARRIVED` → `CLOSED`
- `notes` (free text)

Admin actions:

- Create / edit batch
- Attach nurses (CSV upload of passport/name/mobile, OR pick from already-registered pending nurses by passport, OR add manually)
- Mark batch as `ARRIVED` — flips all linked `PENDING_ARRIVAL` accounts to `ACTIVE` and starts the AJA window timer
- Open / close the AJA window
- Close batch (terminal)

The `OPEN` state means batch is created and accepting nurse linkage, but no one has arrived yet. `ARRIVED` is the activation event.

---

## 4. Nurse-Side AJA Accommodation Tab/Form

Visible only when eligibility passes (§5). Otherwise the tab does not appear in the nav at all.

**Header card:** "AJA Accommodation — for batch BATCH-2026-04-30, expected shift after Hotel XYZ stay ends around 2026-07-30." Clear note: "Signing this does not mean immediate shift. The Embassy will share details with the AJA vendor only when shift is due."

**Section A — Your Decision** (radio):

- I want AJA accommodation
- I will arrange my own accommodation
- Undecided (deadline shown)

The decision is editable until the vendor list for the batch is exported. After that, the radio becomes read-only and shows "Locked: list sent to vendor on YYYY-MM-DD. Contact Nurses Welfare Desk if you need to change."

**Section B — Contact Confirmation** (only if AJA chosen): WhatsApp number, alternate mobile, emergency contact name + relation + number.

**Section C — Agreement** (only if AJA chosen): full agreement text (§6). Typed full name + checkbox "I have read and agreed" + dated electronic signature. Submit produces an `nh_aja_agreement` row with `signed_at` and IP/user-agent for audit.

**Section D — Withdraw** (only if AJA already signed and not yet sent to vendor): a clearly marked "Withdraw my AJA request" button with confirmation. After vendor send, this is replaced with "Contact Nurses Welfare Desk."

After submission, the page becomes a status panel: decision, agreement signed date, current pipeline stage (e.g., "Awaiting vendor list export" → "Sent to vendor" → "Room assigned" → "Checked in"), and admin contact for changes.

---

## 5. Eligibility Logic for Showing/Hiding the AJA Tab

The tab renders iff *all* of:

- `nurse.gender == 'F'` (the workflow is for the female nurse cohort)
- `nh_nurse_account.account_status == 'ACTIVE'`
- `nh_nurse_account.batch_id IS NOT NULL`
- `batch.aja_eligible = 1`
- `batch.status IN ('OPEN','ARRIVED')` (not `DRAFT`, not `CLOSED`)
- `today() BETWEEN batch.aja_window_opens_at AND batch.aja_window_closes_at` (inclusive)
- The nurse has not been individually excluded (`nh_nurse_account.aja_excluded = 0`)

If any of these fail, the tab does not render in the nav and the route returns 404. Eligibility is recomputed on every request — do not cache it in the session.

The same eligibility function is reused on every AJA route, not just the page render — so a clever URL can't bypass it.

---

## 6. AJA Agreement Wording and Disclaimers

Plain English (Urdu translation deferred to v2). The exact text is admin-editable in settings; the version in force at signing is snapshot-stored on the agreement row.

> **AJA Hostel Accommodation Request — Future Shift**
>
> I, [Full Name], holder of Pakistani passport [Passport No.], currently part of arrival batch [Batch Code], request that the Embassy of Pakistan, Kuwait, share my contact details with the AJA Hostel / vendor accommodation arrangement for the purpose of being allotted a bed when my current temporary accommodation arrangement ends.
>
> I understand and accept the following:
>
> 1. Signing this request does not mean I am shifting to AJA today. The shift will happen only after the temporary accommodation period ends, on a date set by the Embassy and the vendor.
> 2. The Embassy is acting only as a facilitator. The accommodation contract, room/bed assignment, maintenance, and house rules are between me and the vendor.
> 3. The Embassy may share my name, passport number, mobile/WhatsApp number, and batch reference with the vendor when shifting is due.
> 4. I may withdraw this request at any time before the Embassy sends the confirmed list to the vendor. After that, withdrawal must be coordinated with the Nurses Welfare Desk.
> 5. The Embassy assumes no liability for vendor performance, billing disputes, room conditions, or interpersonal issues at the hostel.
> 6. I confirm the contact details I have provided are accurate and that I will respond to confirmation messages from the Embassy or vendor within the time stated.
>
> Signed electronically: [typed full name] | Date: [auto] | IP: [auto] | Agreement version: [auto]

The agreement text is stored as a row in `nh_message_template` (or a dedicated `nh_agreement_version` table) so admin can revise wording and old signed agreements still reference the version they signed.

---

## 7. Admin AJA Accommodation Control Center

A new top-level admin section: **Community Welfare → Nurse Housing**, with sub-tabs.

**Batches.** Create/edit batches, attach nurses (CSV or pick), mark arrived, open/close AJA window. Each row shows: code, arrival date, expected count, linked count, AJA-window status, decisions made, agreements signed.

**Eligibility.** A read-only view computing eligibility per nurse: name, passport, gender, batch, account status, AJA visible (yes/no), reason if no. Useful for debugging and answering "why doesn't nurse X see the AJA tab?"

**Decisions & Agreements.** Pipeline columns: Undecided | Wants AJA (no agreement yet) | Agreement Signed | Withdrawn | Wants Own. Click a card → detail with full agreement text snapshot, contact info, audit log. Bulk "Send reminder" button (uses copy-message templates in v1).

**Roster.** Active occupants only (post-shift). Columns: name, passport, room, bed, check-in date, contract start, contract end, vendor invoice ref, status. Filters: by batch, by status, by contract end month.

**Vendor Export.** Pick batch + filter (e.g., "all who signed by date X"), preview, confirm, download CSV, mark exported. See §9.

**Messages.** Template CRUD; copy-WhatsApp links per nurse; bulk copy as broadcast text. Send log shows what was copied/clicked, by which admin.

**Settings.** Eligibility window defaults; agreement template; Nurses Welfare Desk user id; vendor export columns; reminder cadence.

---

## 8. AJA Roster Design

Once a nurse physically checks into AJA, admin records:

- `room_no`, `bed_no`
- `check_in_date`
- `contract_start_date`, `contract_end_date`
- `vendor_id` and `vendor_invoice_ref` (free text in v1)
- `nurse_status`: `ACTIVE_OCCUPANT`, `VACATED`, `TRANSFERRED`, `TERMINATED`
- `vacate_date`, `vacate_reason` when applicable

Roster is its own table (`nh_aja_roster`) so admin can have multiple successive stays per nurse (e.g., transfer between rooms creates a `VACATED` row and a new `ACTIVE_OCCUPANT` row).

Bed-level inventory (a fixed list of all rooms/beds at AJA) is *deferred to v2*. v1 just records what admin types per nurse, with a uniqueness check on `(room_no, bed_no, nurse_status='ACTIVE_OCCUPANT')` to prevent double-booking.

---

## 9. Vendor Export Workflow

Strictly admin-driven, never automatic. Steps:

1. Admin opens **Vendor Export**, picks a batch and a "shift due date."
2. System lists candidates: all linked nurses with `Decision = AJA`, `Agreement Signed`, not withdrawn, not already exported.
3. Admin reviews; can deselect rows individually with a reason.
4. Admin clicks **Generate Export** → system writes an `nh_aja_vendor_export` job row, generates a CSV with the columns admin chose (defaults: `name, passport_no, mobile, whatsapp, batch_code, agreement_signed_date, expected_shift_date`), and atomically marks each included agreement with `sent_to_vendor_export_id`.
5. Admin downloads the CSV and shares it with the vendor through whatever channel is appropriate (email, WhatsApp file).
6. As vendor confirms allotments, admin enters room/bed/check-in details into the roster (§8) for each nurse — that flips their pipeline stage forward.

After a nurse is part of an export job, their AJA tab self-locks (decision read-only) and shows "Sent to vendor on YYYY-MM-DD." Withdrawal after this point routes through the Nurses Welfare Desk and is recorded as a manual cancel-with-vendor.

CSV file is also stored on the server (`vendor_exports/{export_id}.csv`) for audit. Each export row in the audit log captures the filter used, the count, and the admin who clicked.

---

## 10. Statuses and Allowed Transitions

**Account (`nh_nurse_account.account_status`)**
- `PENDING_ARRIVAL` → `ACTIVE` (on batch arrival or manual approval)
- `PENDING_ARRIVAL` → `REJECTED` (terminal)
- `ACTIVE` → `SUSPENDED` (manual, with reason)
- `SUSPENDED` → `ACTIVE` (manual)
- `ACTIVE` → `CLOSED` (terminal — left service)

**Batch (`nh_arrival_batch.status`)**
- `DRAFT` → `OPEN` → `ARRIVED` → `CLOSED`
- `OPEN` → `CANCELLED` (terminal, no nurses arrived)

**AJA Pipeline (`nh_aja_decision.stage` + `nh_aja_agreement` joins)**
- `UNDECIDED` → `WANTS_OWN` (terminal for AJA flow; nurse may switch back while window open)
- `UNDECIDED` → `WANTS_AJA` (intent only, no agreement yet)
- `WANTS_AJA` → `AGREEMENT_SIGNED`
- `AGREEMENT_SIGNED` → `WITHDRAWN` (allowed only if not yet exported)
- `AGREEMENT_SIGNED` → `SENT_TO_VENDOR` (admin export action)
- `SENT_TO_VENDOR` → `ROOM_ASSIGNED` (admin enters room/bed)
- `ROOM_ASSIGNED` → `CHECKED_IN`
- `CHECKED_IN` → `ACTIVE_OCCUPANT`
- `ACTIVE_OCCUPANT` → `VACATED` / `TRANSFERRED` / `TERMINATED`

Disallowed transitions return HTTP 409 and write nothing.

---

## 11. Manual WhatsApp / Copy-Message Workflow for v1

No API. Two patterns, both admin-driven.

**Per-nurse one-click open.** Each nurse row in admin has a 💬 button generating `https://wa.me/{e164_number}?text={url-encoded message}`. The message body comes from a selected template with merge fields (`{{name}}`, `{{batch_code}}`, `{{aja_window_close}}`, `{{portal_link}}`). Clicking opens WhatsApp Web/desktop pre-filled; admin reviews and presses send. The system logs `template_id`, `nurse_id`, `actor`, `clicked_at` to `nh_message_log` so we know who was contacted.

**Bulk broadcast clipboard.** For a filtered set, admin clicks "Copy as broadcast" which produces a plain-text block of `+965XXXXXXX\t<personalized message>` lines, one per nurse. Admin pastes into a WhatsApp broadcast or a CRM. The same `nh_message_log` entry is written per nurse, marked `BULK_COPY`.

Templates live in `nh_message_template` and are admin-editable. Default templates seeded:
- Arrival confirmation
- AJA window opened
- AJA window closing soon (3 days)
- Vendor list sent
- Room assignment confirmed
- Check-in reminder

---

## 12. Future WhatsApp API Workflow (v2)

When ready, swap the manual layer for a queued sender:

- Provider abstraction: Meta WhatsApp Business or Twilio (driver pattern, single config switch).
- Pre-approved Meta templates mirroring `nh_message_template`.
- New tables `nh_message_outbox` (queue) and `nh_message_inbox` (replies via webhook).
- A small worker dequeues outbox rows on a schedule (cron in stdlib `sched`), respecting per-day rate limits.
- Delivery / read receipts captured against `nh_message_log` rows so admin sees "delivered ✓" without leaving the portal.
- Auto-reminders driven by status: e.g., 3 days before AJA window close, queue a reminder to anyone still `UNDECIDED`.
- Inbound replies surfaced to Nurses Welfare Desk inbox — a triage UI.

The contract surface (templates table, log table, render function) stays the same — v1 fills it manually, v2 fills it programmatically.

---

## 13. Nurse Complaint Management Redesign

Two acceptable approaches. Pick **B** to honor the additive constraint cleanly.

**Approach A (minimal):** add a `source` column to the existing complaints table (`GENERAL` | `NURSE_PORTAL`) and an `assignee_id` column. Filter all existing complaint queries with `source = 'GENERAL'` so the general queue stays unchanged. Add a new admin queue filtered by `source = 'NURSE_PORTAL'`.

**Approach B (additive — recommended):** create a parallel `nurse_complaints` table mirroring the existing complaints schema. Nurse-portal submissions write here; general portal submissions are unchanged. This keeps the existing complaints table untouched and prevents any chance of regression in the operator_special reports or Ambassador Pulse export.

Either way, the nurse-portal submit handler:

1. Verifies `nh_nurse_account.account_status = 'ACTIVE'` — `PENDING_ARRIVAL` or `SUSPENDED` accounts get HTTP 403 with a friendly "your account is not yet active" page.
2. Writes the complaint with `assignee_id = settings.nurses_welfare_desk_user_id` (configurable, defaults to Awais).
3. Sets `source = 'NURSE_PORTAL'` (Approach A) or just inserts into `nurse_complaints` (Approach B).
4. Stamps `auto_assigned_at`, `auto_assignee_id`.
5. Writes an `nh_complaint_audit` row.

A new admin tab **Nurse Complaints** lists these separately, sorted by `submitted_at` desc, with status pipeline (New → In Progress → Resolved → Closed) and a re-assign button.

---

## 14. Auto-Assignment Rules for Nurse Complaints

- Default assignee: `settings.nurses_welfare_desk_user_id` (Awais).
- If Awais is on leave (admin-toggle `on_leave=1` on the user record, or a dated leave window), fallback to `settings.nurses_welfare_fallback_user_id`. If neither is reachable, fall back to the first user with role `nurses_welfare_desk`, otherwise the first `admin` and flag the complaint as **needs_triage**.
- Round-robin between multiple desk staff is *deferred to v2* — keep v1 single-pivot.
- Re-assignment is allowed by admin or the current assignee, with a required reason recorded to audit.
- Category routing (accommodation / salary / harassment / other) is captured from a dropdown the nurse picks at submission time. Auto-routing by keyword is deferred to v2.

---

## 15. Control for Non-Arrived / Visa-Awaiting Nurses

The bright line: **no full portal account until the Embassy confirms arrival.**

Implementation:

- New nurse registrations create `nh_nurse_account.account_status = PENDING_ARRIVAL`.
- A login succeeds and shows the dashboard, but every protected route checks `account_status = ACTIVE` and otherwise renders a "pending arrival" page.
- Pending nurses can:
  - Update profile (name, mobile, photo)
  - Upload arrival documents (visa copy, ticket — optional)
  - View their batch link if any
  - Read static notices from Embassy (read-only)
- Pending nurses cannot:
  - Submit complaints
  - Access AJA tab (it's not even rendered)
  - Access grading letter tab
  - Access any other workflow

Admin sees a **Pending Accounts** tab to review, approve, link to batch, or reject. Reject is terminal and logs reason.

A safety net: a nightly job auto-suspends pending accounts older than N days (default 180) with no batch link, so leftovers don't accumulate.

---

## 16. Database Table Design

All new tables prefixed `nh_`. SQLite-friendly. Existing tables are not altered.

**`nh_nurse_account`** *(sidecar to existing `nurses` table)*
- `nurse_id` INTEGER PK FK → `nurses(id)`
- `account_status` TEXT — `PENDING_ARRIVAL`, `ACTIVE`, `SUSPENDED`, `REJECTED`, `CLOSED`
- `batch_id` INTEGER NULL FK → `nh_arrival_batch(id)`
- `arrival_confirmed_at` DATETIME NULL
- `aja_excluded` INTEGER DEFAULT 0
- `notes` TEXT NULL
- `created_at`, `updated_at`

Default behavior in code: if no row exists for a nurse, treat as `ACTIVE` so existing nurses keep working.

**`nh_arrival_batch`**
- `id` PK, `batch_code` TEXT UNIQUE, `arrival_date` DATE, `expected_count` INT
- `temp_accommodation_provider` TEXT, `temp_accommodation_end_estimate` DATE
- `aja_eligible` INT, `aja_window_opens_at` DATE, `aja_window_closes_at` DATE
- `status` TEXT (`DRAFT`/`OPEN`/`ARRIVED`/`CLOSED`/`CANCELLED`)
- `notes` TEXT, `created_at`, `created_by`

**`nh_aja_decision`**
- `id` PK, `nurse_id` FK, `batch_id` FK
- `stage` TEXT (see §10)
- `decided_at` DATETIME, `last_changed_by` (NURSE/ADMIN)
- Unique on `(nurse_id, batch_id)`

**`nh_aja_agreement`**
- `id` PK, `decision_id` FK, `agreement_version_id` FK
- `signed_name` TEXT, `signed_at` DATETIME, `ip` TEXT, `user_agent` TEXT
- `whatsapp_number` TEXT, `alt_mobile` TEXT
- `emergency_name` TEXT, `emergency_relation` TEXT, `emergency_number` TEXT
- `withdrawn_at` DATETIME NULL, `withdrawn_reason` TEXT NULL
- `vendor_export_id` INTEGER NULL FK

**`nh_agreement_version`**
- `id` PK, `version_label` TEXT, `body_text` TEXT, `is_active` INT, `created_at`, `created_by`

**`nh_aja_roster`**
- `id` PK, `nurse_id` FK, `agreement_id` FK
- `room_no`, `bed_no`, `check_in_date`, `contract_start`, `contract_end`
- `vendor_id` INT NULL, `vendor_invoice_ref` TEXT
- `nurse_status` TEXT
- `vacate_date` DATE NULL, `vacate_reason` TEXT NULL
- Partial unique index on `(room_no, bed_no)` where `nurse_status='ACTIVE_OCCUPANT'`

**`nh_aja_vendor_export`**
- `id` PK, `batch_id` FK, `filter_json` TEXT, `row_count` INT
- `csv_path` TEXT, `created_at`, `created_by`

**`nh_message_template`** — `id`, `code`, `name`, `body_text`, `is_active`, `created_at`, `updated_at`.

**`nh_message_log`** — `id`, `nurse_id`, `template_id`, `mode` (`PER_NURSE_LINK`/`BULK_COPY`), `actor_id`, `clicked_at`, `notes`.

**`nh_audit`** — append-only — `id`, `entity` (`account`/`batch`/`agreement`/`roster`/`export`/`complaint`/`message`), `entity_id`, `actor_role`, `actor_id`, `event_type`, `field`, `old`, `new`, `note`, `created_at`.

**`nurse_complaints`** *(if Approach B from §13)* — mirror columns of existing complaints + `auto_assignee_id`, `auto_assigned_at`, `category`, `status`.

**`nh_complaint_audit`** — append-only audit for nurse complaint state changes and reassignments.

Indexes on `nurse_id`, `batch_id`, `account_status`, `status`, `signed_at`.

---

## 17. API / Routes Design

All new routes behind `FEATURE_NURSE_HOUSING`. All require existing auth + role checks.

**Nurse-side**
- `GET  /nurse/dashboard` — existing; add a check that conditionally shows AJA card and a banner for pending accounts. Minimal additive change to existing route.
- `GET  /nurse/aja` — render tab; eligibility-gated; 404 if not eligible.
- `POST /nurse/aja/decision` — set `WANTS_AJA` / `WANTS_OWN` / `UNDECIDED`.
- `POST /nurse/aja/sign` — sign agreement; requires `WANTS_AJA`; captures IP/UA.
- `POST /nurse/aja/withdraw` — withdraw before vendor export; 409 otherwise.
- `POST /nurse/complaint` — existing route, modified to: enforce `account_status = ACTIVE`; route into `nurse_complaints` (Approach B) or stamp `source/assignee` (Approach A).

**Admin — Nurse Housing**
- `GET/POST /admin/nh/batches` — list/create
- `GET/POST /admin/nh/batches/<id>` — view/edit
- `POST /admin/nh/batches/<id>/attach-nurses` — CSV or picker
- `POST /admin/nh/batches/<id>/mark-arrived` — flips linked accounts to `ACTIVE`
- `GET  /admin/nh/eligibility` — debug view
- `GET  /admin/nh/agreements` — pipeline
- `GET  /admin/nh/agreements/<id>` — detail
- `POST /admin/nh/agreements/<id>/admin-withdraw` — admin-side withdraw with reason
- `GET  /admin/nh/roster` — active occupants
- `POST /admin/nh/roster/<id>` — set room/bed/contract
- `POST /admin/nh/roster/<id>/vacate` — vacate with reason
- `GET  /admin/nh/export` — preview
- `POST /admin/nh/export/generate` — atomically create export job, write CSV, stamp agreements
- `GET  /admin/nh/export/<id>.csv` — download
- `GET/POST /admin/nh/messages/templates` — CRUD
- `POST /admin/nh/messages/log-click` — record copy/click
- `GET  /admin/nh/settings` — eligibility window defaults, NWD user, agreement version

**Admin — Pending Accounts**
- `GET  /admin/nh/accounts/pending`
- `POST /admin/nh/accounts/<nurse_id>/approve` — set `ACTIVE`, optionally link to batch
- `POST /admin/nh/accounts/<nurse_id>/reject` — terminal with reason
- `POST /admin/nh/accounts/<nurse_id>/suspend` / `/reactivate`

**Admin — Nurse Complaints**
- `GET  /admin/nurse-complaints` — separate queue
- `GET  /admin/nurse-complaints/<id>` — detail
- `POST /admin/nurse-complaints/<id>/assign` — re-assign with reason
- `POST /admin/nurse-complaints/<id>/status` — update status with note

State-changing routes write `nh_audit` rows. Disallowed transitions return 409.

---

## 18. Admin UI Layout

Top-level menu (existing): Community Welfare ▸

Add inside Community Welfare:

- **Nurse Housing** ▸ Batches | Pending Accounts | Eligibility | Agreements | Roster | Vendor Export | Messages | Settings
- **Nurse Complaints** (separate item, sibling to existing Complaints)

Visual conventions: identical to existing welfare-cases list (table, top filter bar, status pills). Status pills use distinct colors per stage so admins recognize the pipeline at a glance.

The Agreements tab is a kanban-style columnar view by stage; everything else is a normal filtered table.

---

## 19. Nurse UI Layout

Nurse dashboard (existing) gets:

- A status banner if `account_status != ACTIVE` (e.g., "Your account is pending arrival confirmation. Most features will unlock after your arrival is confirmed by the Embassy.").
- Conditional cards: Profile, Complaints (if ACTIVE), Grading Letter (existing), AJA Accommodation (only if eligible per §5).

The AJA card itself shows the current pipeline stage as a one-line summary so the nurse always sees status without clicking.

Mobile-friendly: existing portal styles already handle this; reuse them.

---

## 20. Risks and Safeguards

**Risks**
- Wrong nurse sees AJA tab → leaks vendor flow, may sign without eligibility.
- Vendor receives wrong list → privacy + operational mess.
- Nurses awaiting visa register, complain, look like active staff.
- Awais on leave; nurse complaints sit unattended.
- Issued/exported records silently rewritten under pressure.
- Existing portal regressions when adding code to monolithic `server.py`.
- Phone numbers shared with vendor improperly (privacy under Kuwait regulations).

**Safeguards**
- Eligibility check is server-side and recomputed on every request — no session caching.
- Vendor export requires preview + explicit confirm + writes immutable export job + stamps each agreement; never automatic.
- Pre-arrival accounts are gated server-side on every protected route, not just hidden in UI.
- `assignee_id` on every nurse complaint — never NULL — with fallback chain.
- `nh_audit` is append-only; daily integrity hash recommended.
- Feature flag `FEATURE_NURSE_HOUSING` defaults off until migrations succeed; existing flows untouched if off.
- Additive tables only; the only existing route changed is `/nurse/complaint` (gate + assignee), and that change is gated by the feature flag too.
- Vendor CSV contains only the agreed fields; admin can preview the exact CSV before export. No CNIC, no email unless admin explicitly enables.
- Withdrawal allowed up to vendor export; after that, manual coordination with Nurses Welfare Desk and recorded as cancel-with-vendor.
- Backups: nightly DB snapshot already exists in the portal; ensure new tables are included.

---

## 21. Minimal v1 Implementation

Ship in 2–3 weeks:

- `nh_nurse_account` sidecar with login-time gate; default `ACTIVE` if no row (zero migration impact).
- New nurse registrations create row `PENDING_ARRIVAL`.
- Admin **Pending Accounts** tab to approve/reject.
- **Batches** CRUD with `mark-arrived` flipping linked accounts to `ACTIVE`.
- AJA tab on nurse side with eligibility check, decision radio, agreement signing, withdraw.
- Admin Agreements pipeline view + Roster manual entry.
- Vendor Export: preview → confirm → CSV → stamp.
- Copy-WhatsApp link buttons + bulk-copy templates.
- Nurse complaints routed to `nurse_complaints` table (Approach B) and auto-assigned to Awais via settings.
- New admin **Nurse Complaints** tab.
- Append-only audit on every state change.
- Feature flag.

Defer to v2:

- WhatsApp Business API integration.
- Bed-level inventory.
- Round-robin assignment.
- Auto-reminders.
- Urdu translation of agreement.
- Photo uploads of room.
- Vendor portal for receiving lists directly.

---

## 22. Future v2 Improvements

- WhatsApp Business API (Meta or Twilio) with template-approved messages and webhook for delivery/read receipts.
- Two-way messaging triaged by Nurses Welfare Desk.
- Auto-reminders based on stage and dates.
- Bed-level inventory with floor plan view; capacity dashboards per floor.
- Vendor self-serve mini-portal for receiving lists and confirming allotments.
- Bulk import of historic AJA roster data from spreadsheets.
- Multi-language UI (English/Urdu) including agreement.
- Analytics: occupancy %, time-to-shift, complaint resolution time, batch comparison.
- Integration with the OCR matching workflow already in this project — pre-arrival passport copy ingestion.
- Integration with grading-letter feature: a single "Nurse 360" view showing all workflows for a given nurse.

---

## 23. Implementation Prompt for Codex / Cursor

Paste the block below into Codex/Cursor against the existing `server.py` repository. It is self-contained, additive-only, and gated behind a feature flag.

---

````
You are extending an existing Embassy of Pakistan, Kuwait Community Welfare portal implemented as a single-file Python stdlib monolith (`server.py`) using `http.server`-style routing and SQLite. Existing features that MUST keep working unchanged: nurse registration, nurse login, nurse complaints (general flow), nurse grading letters, legal cases, death cases, welfare cases, fee ledger, CWA advance ledger, Iraq transit, Ambassador Pulse CSV export, operator_special reports, Nurses Management, facility roster, facility occupancy. Do not modify any of their tables, routes, templates, JS, or shared utilities except to add small additive helpers and the two minimal hooks listed below.

# constraints

- Python 3 stdlib only unless `python-docx` / `csv` / `email` are already imported in `server.py`; reuse what's there.
- All new code lives behind a feature flag `FEATURE_NURSE_HOUSING` (default True only after migrations succeed).
- All new tables and routes are prefixed `nh_` / `/nurse/aja*`, `/admin/nh/...`, `/admin/nurse-complaints/...` to avoid collisions.
- No new external services, no new network calls, no new dependencies.
- Add new tables only. Do not alter existing tables.
- Append-only audit: never UPDATE or DELETE rows in `nh_audit` or `nh_complaint_audit`.
- Existing routes touched: ONLY `/nurse/dashboard` (add conditional banner + AJA card include) and `/nurse/complaint` (add account-status gate + route to `nurse_complaints`). Wrap both modifications in `if FEATURE_NURSE_HOUSING:` checks so disabling the flag returns the file to its pre-change behavior.
- Do not change formatting on existing lines; restrict diffs to additions.

# migrations (idempotent CREATE TABLE IF NOT EXISTS, run on startup after existing migrations)

1. nh_nurse_account(nurse_id PK FK, account_status TEXT, batch_id INTEGER NULL, arrival_confirmed_at DATETIME, aja_excluded INTEGER DEFAULT 0, notes TEXT, created_at, updated_at). Code default: missing row == ACTIVE.
2. nh_arrival_batch(id PK, batch_code TEXT UNIQUE, arrival_date DATE, expected_count INT, temp_accommodation_provider TEXT, temp_accommodation_end_estimate DATE, aja_eligible INT, aja_window_opens_at DATE, aja_window_closes_at DATE, status TEXT, notes TEXT, created_at, created_by).
3. nh_aja_decision(id PK, nurse_id FK, batch_id FK, stage TEXT, decided_at, last_changed_by, UNIQUE(nurse_id, batch_id)).
4. nh_agreement_version(id PK, version_label, body_text, is_active INT, created_at, created_by). Seed one active row with the agreement text from the design doc §6.
5. nh_aja_agreement(id PK, decision_id FK, agreement_version_id FK, signed_name, signed_at, ip, user_agent, whatsapp_number, alt_mobile, emergency_name, emergency_relation, emergency_number, withdrawn_at, withdrawn_reason, vendor_export_id NULL).
6. nh_aja_roster(id PK, nurse_id FK, agreement_id FK, room_no, bed_no, check_in_date, contract_start, contract_end, vendor_id, vendor_invoice_ref, nurse_status, vacate_date, vacate_reason). Partial unique index on (room_no, bed_no) WHERE nurse_status='ACTIVE_OCCUPANT'.
7. nh_aja_vendor_export(id PK, batch_id FK, filter_json TEXT, row_count INT, csv_path TEXT, created_at, created_by).
8. nh_message_template(id PK, code TEXT UNIQUE, name, body_text, is_active, created_at, updated_at). Seed templates from design doc §11.
9. nh_message_log(id PK, nurse_id, template_id, mode TEXT, actor_id, clicked_at, notes).
10. nh_audit(id PK, entity, entity_id, actor_role, actor_id, event_type, field, old, new, note, created_at).
11. nurse_complaints(id PK, nurse_id FK, category TEXT, subject, body, status TEXT, auto_assignee_id INT, auto_assigned_at, current_assignee_id INT, submitted_at, updated_at). Mirror only the columns the existing complaints table actually uses.
12. nh_complaint_audit (same shape as nh_audit, scoped to nurse complaints).
13. nh_settings(key TEXT PK, value TEXT). Seed: nurses_welfare_desk_user_id, nurses_welfare_fallback_user_id, default_aja_window_lead_days=90, vendor_export_columns (JSON list).

Indexes: nh_nurse_account.account_status, nh_aja_decision.batch_id, nh_aja_agreement.signed_at, nurse_complaints.status, nurse_complaints.current_assignee_id.

# helpers

- nh_get_account(nurse_id) -> dict; missing row defaults to {'account_status': 'ACTIVE', 'batch_id': None, ...}.
- nh_eligibility(nurse_id) -> {'aja_visible': bool, 'reasons': [...]}; uses §5 rules exactly.
- nh_assign_nurse_complaint() -> user_id; resolves NWD primary, then fallback, then any user with role nurses_welfare_desk, then any admin; flags 'needs_triage' if nothing matched.
- nh_render_template(template_code, nurse_row, batch_row, **extra) -> str; supports {{name}}, {{batch_code}}, {{aja_window_close}}, {{portal_link}}.
- nh_wa_link(e164_number, body) -> str; returns 'https://wa.me/{n}?text={urlencode(body)}'.
- nh_write_audit(entity, entity_id, actor_role, actor_id, event_type, field=None, old=None, new=None, note=None) -> None.
- nh_export_vendor_csv(batch_id, filter, columns, actor_id) -> (export_id, path, row_count); transactional, stamps each included agreement.

# routes — nurse side

- GET  /nurse/aja                — eligibility-gated render; 404 if nh_eligibility().aja_visible is False.
- POST /nurse/aja/decision       — set stage to WANTS_AJA / WANTS_OWN / UNDECIDED on nh_aja_decision.
- POST /nurse/aja/sign           — requires WANTS_AJA; capture IP+UA; insert nh_aja_agreement; transition to AGREEMENT_SIGNED.
- POST /nurse/aja/withdraw       — only if AGREEMENT_SIGNED and not exported; sets withdrawn_at, transitions to WITHDRAWN.

Also modify (additive):
- /nurse/dashboard: include AJA card + pending banner conditionally on nh_eligibility() and account_status. Wrap in `if FEATURE_NURSE_HOUSING`.
- /nurse/complaint (existing handler): if FEATURE_NURSE_HOUSING and submitted from authenticated nurse session, require account_status='ACTIVE' (else 403 with friendly page) and write to nurse_complaints with auto_assignee = nh_assign_nurse_complaint(); ELSE preserve existing behavior exactly.

# routes — admin (require existing admin auth)

- GET /admin/nh/accounts/pending             — list PENDING_ARRIVAL accounts.
- POST /admin/nh/accounts/<nurse_id>/approve — set ACTIVE, optional batch link.
- POST /admin/nh/accounts/<nurse_id>/reject  — terminal, with reason.
- POST /admin/nh/accounts/<nurse_id>/suspend — with reason.
- POST /admin/nh/accounts/<nurse_id>/reactivate.
- GET/POST /admin/nh/batches                 — list, create, edit.
- POST /admin/nh/batches/<id>/attach-nurses  — CSV upload or pick.
- POST /admin/nh/batches/<id>/mark-arrived   — flips linked accounts to ACTIVE; audit per nurse.
- GET  /admin/nh/eligibility                 — debug view.
- GET  /admin/nh/agreements                  — pipeline.
- GET  /admin/nh/agreements/<id>             — detail.
- POST /admin/nh/agreements/<id>/admin-withdraw.
- GET/POST /admin/nh/roster                  — list / create roster row.
- POST /admin/nh/roster/<id>/vacate          — with reason.
- GET  /admin/nh/export                      — preview.
- POST /admin/nh/export/generate             — atomic export job + CSV write.
- GET  /admin/nh/export/<id>.csv             — download.
- GET/POST /admin/nh/messages/templates      — CRUD.
- POST /admin/nh/messages/log-click          — record click/copy.
- GET/POST /admin/nh/settings.

- GET  /admin/nurse-complaints               — list, filterable by status/assignee.
- GET  /admin/nurse-complaints/<id>          — detail.
- POST /admin/nurse-complaints/<id>/assign   — reassign with reason.
- POST /admin/nurse-complaints/<id>/status   — status change with note.

Every state-changing route writes to nh_audit (or nh_complaint_audit). Disallowed transitions return HTTP 409 and write nothing.

# UI

Reuse existing portal CSS classes and layout helpers. Do not introduce a new framework. Nurse pages live inside the existing nurse dashboard layout. Admin pages live under Community Welfare. Match the styling of the welfare-cases list exactly.

# verification before declaring done

- Toggle FEATURE_NURSE_HOUSING off → portal behaves identically to before this change.
- Existing nurses (no nh_nurse_account row) can still log in and use everything they could before.
- A new nurse registration creates account_status=PENDING_ARRIVAL; that account cannot submit a complaint or see AJA.
- Create a batch with aja_eligible=1, link a female nurse, mark arrived → her account flips ACTIVE and she sees the AJA tab.
- Sign agreement → row in nh_aja_agreement; withdraw works before export and is blocked after.
- Generate vendor export → CSV file written, agreements stamped, agreements lock to read-only on nurse side.
- Submit a nurse complaint → lands in nurse_complaints with auto_assignee = NWD user; does NOT appear in the general complaints queue; appears in /admin/nurse-complaints.
- Smoke-test: nurse registration, nurse login, grading letters, legal cases, death cases, welfare cases, fee ledger, CWA advance ledger, Iraq transit, Ambassador Pulse CSV export, operator_special reports — verify nothing 500s and existing data is untouched.

# deliverables

1. Modified server.py with the additions described.
2. CHANGES.md listing every new route, table, function, template, migration, and the line ranges in server.py you touched.
3. A brief admin runbook (RUNBOOK_NH.md) covering: how to create a batch, mark arrival, send vendor list, handle a withdrawal post-export.

Stop after these deliverables. Do not refactor existing code.
````

---

*End of design document.*
