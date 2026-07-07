# TOTP Two-Factor Authentication — Feasibility Report & Implementation Plan
**Embassy / Community Welfare Portal (Python stdlib + SQLite, deployed on Render)**

Prepared: 2026-05-09
Scope: Add Google Authenticator-compatible TOTP 2FA to the existing monolithic `server.py` portal, surgically and without disturbing public applicant workflows.

---

## 1. Executive Summary

Adding TOTP-based two-factor authentication (compatible with Google Authenticator, Microsoft Authenticator, Authy, 1Password, Bitwarden, etc.) to the existing portal is **fully feasible, low-risk when staged correctly, and zero-cost at runtime**. TOTP is an RFC 6238 standard implemented entirely in code on the server — there is no SMS gateway, no email OTP service, no third-party identity provider, and no per-login fee.

The recommended approach is a **surgical, additive patch**:

- Two new SQLite tables (`user_totp`, `user_backup_codes`) plus extensions to the existing audit log. No changes to the `users` table schema beyond optional columns. No changes to public applicant tables.
- Two small Python dependencies: `pyotp` (RFC 6238 TOTP) and `qrcode[pil]` (one-time QR rendering, in-memory only).
- A two-step login flow: password → pending session (cookie flagged `2fa_pending`) → TOTP verification → full authenticated session.
- A phased rollout starting with **optional 2FA for super-admins**, hardening to **mandatory for all admins**, then extending to operators and fee collectors. **Public applicant tracking is never gated by 2FA.**
- A clearly defined recovery model (10 single-use backup codes per user, admin-initiated reset with audit trail, super-admin override).

The most important non-technical decisions are (a) who is the **break-glass super-admin** with reset authority, and (b) whether to enable a "trusted device for 30 days" cookie. The report defaults both to the safer choice and flags them as decisions for you.

**Bottom line: Recommended. Proceed with Phase 1 (optional admin enrollment) within 1–2 weeks.**

---

## 2. Feasibility Assessment

### 2.1 Can TOTP be added to the current portal?

Yes. TOTP is a HMAC-SHA1 calculation over a shared secret and the current 30-second time window. It does not require a framework, an HTTP library, or an external service. The entire verification path is:

```
code_user_typed == HMAC-SHA1(secret, floor(unix_time / 30))[truncated to 6 digits]
```

Anything that can read POST form data and look up a row in SQLite can implement TOTP.

### 2.2 Is it suitable for a Python stdlib HTTP + SQLite portal?

Strongly suitable. TOTP has none of the architectural needs that would push you toward Flask/Django (no async, no background workers, no message queue, no cache layer). SQLite handles the read/write load trivially — verification is one indexed lookup per login. The stdlib `http.server` request handler pattern adds two routes (`GET/POST /auth/2fa/setup`, `GET/POST /auth/2fa/verify`) and one decorator-equivalent helper that wraps existing protected handlers.

### 2.3 Required libraries

| Library | Purpose | Maturity | Notes |
|---|---|---|---|
| `pyotp` | RFC 6238 TOTP + RFC 4226 HOTP | Mature, widely used (Django, FastAPI ecosystems use it indirectly) | ~300 LOC, no transitive deps. The recommended choice. |
| `qrcode[pil]` | Render the `otpauth://` URI as a PNG/SVG QR | Mature | Pulls in Pillow. If you want zero image deps, render an SVG QR with `qrcode` alone (no `[pil]`) and inline it in the HTML response. |
| `secrets` (stdlib) | Backup-code generation, secret-key generation | stdlib | Use this, never `random`. |
| `hmac`, `hashlib` (stdlib) | Backup-code hashing, constant-time compare | stdlib | Use `hmac.compare_digest` for all code comparisons. |
| `cryptography` (optional) | Encrypt TOTP secrets at rest | Mature | Recommended if the SQLite file is on a shared/persistent disk. Use `Fernet` with key from env var. |

**No SMS gateway, no Twilio, no SendGrid, no Auth0, no Firebase.** The full runtime cost is the 1.5 MB on disk for `pyotp` + `qrcode`.

### 2.4 Does it work on Render?

Yes, with two caveats:

1. **Persistent disk for SQLite.** If the SQLite file is on Render's ephemeral filesystem, every redeploy wipes 2FA secrets and locks every user out. The portal almost certainly already mounts a Render Persistent Disk for SQLite (otherwise the existing user accounts wouldn't survive deploys); 2FA simply uses the same store. Verify this before rollout.
2. **Wall-clock accuracy.** Render's containers use NTP-synced clocks. TOTP tolerates ±1 step (±30 s) by default, which absorbs any drift you'll see in practice. No special configuration needed.

Free-tier Render services that sleep on inactivity are still fine — the first request after wake re-reads the SQLite file like any other request.

### 2.5 Cost

Zero recurring cost. No SMS, no email OTP, no third-party MFA SaaS. The only cost is engineering time (estimated 2–4 days for Phase 1 including testing).

---

## 3. Recommended Security Model

### 3.1 Who must use 2FA?

| Role | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| Super-admin | **Mandatory** | Mandatory | Mandatory | Mandatory |
| Admin | Optional | **Mandatory** | Mandatory | Mandatory |
| Operator | — | Optional | **Mandatory** | Mandatory |
| Fee Collector | — | Optional | **Mandatory** | Mandatory |
| Public applicant | **Never** | Never | Never | Never |

Rationale: The blast radius of a compromised admin account (legal cases, Note Verbal workflows, embassy letters, fee data) is far higher than that of a public applicant tracking lookup. Public users are also the largest population, often on low-end devices, and gating their workflows risks operational disruption with little security benefit. **Public applicant tracking must remain frictionless.**

### 3.2 Why phase the rollout?

- **Catches deployment bugs before they affect operators.** A super-admin who gets locked out has direct DB access to recover. An operator does not.
- **Surfaces UX and training issues** (QR scanning, backup-code storage) on a small audience.
- **Lets you validate the recovery flow on a real human** before mandating it for 30+ staff.

### 3.3 Emergency access and recovery — at a glance

- Every enrolled user receives **10 single-use backup codes** at enrollment, hashed in the DB.
- **Admins can reset another user's 2FA** (clearing their secret and forcing re-enrollment on next login). Every reset is audit-logged.
- A **break-glass super-admin** account is created with mandatory 2FA and stored backup codes printed on paper in a sealed envelope kept by the head of the office. This is the only out if the entire admin team is locked out.
- **No email-based reset.** Email accounts are themselves frequently compromised; an attacker who controls a staff email could self-reset 2FA. If you must offer email reset later, gate it on a manual confirmation step from a different admin.

---

## 4. Recommended Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Existing server.py                                          │
│                                                             │
│   /login (POST)  ──┐                                        │
│                    │   password OK?                         │
│                    ▼                                        │
│              ┌──────────────┐                               │
│              │ has 2FA?     │── no ──► full session ───►    │
│              └──────┬───────┘                               │
│                     │ yes                                   │
│                     ▼                                       │
│              pending session cookie (2fa_pending=1)         │
│                     │                                       │
│   /auth/2fa/verify  ▼                                       │
│              verify TOTP or backup code                     │
│                     │                                       │
│                     ▼                                       │
│              upgrade to full session                        │
│                                                             │
│   /auth/2fa/setup  (admin opens own "Security Settings")    │
│              generate secret → render QR → confirm code     │
│                                                             │
│   require_2fa()    helper used by admin/operator routes     │
│   audit_log()      existing helper, extended with 2fa.*     │
└─────────────────────────────────────────────────────────────┘
```

A single new module — `totp_auth.py` — holds enrollment, verification, backup-code generation, and rate-limit helpers. `server.py` imports it and adds three routes plus one guard helper. Nothing in the existing routing, templating, or session model changes.

---

## 5. Database Changes

All changes are **additive**. No existing column is altered, no row is rewritten, no table is dropped.

### 5.1 New table: `user_totp`

```sql
CREATE TABLE IF NOT EXISTS user_totp (
    user_id              INTEGER PRIMARY KEY,
    secret_encrypted     TEXT    NOT NULL,            -- Fernet ciphertext of base32 secret
    enabled              INTEGER NOT NULL DEFAULT 0,  -- 0 until first successful verify
    confirmed_at         TEXT,                        -- ISO8601 timestamp of activation
    last_used_at         TEXT,                        -- updated on each successful verify
    last_used_counter    INTEGER,                     -- replay protection (last accepted step)
    failed_attempts      INTEGER NOT NULL DEFAULT 0,
    locked_until         TEXT,                        -- ISO8601, NULL when not locked
    created_at           TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

`secret_encrypted` is stored encrypted with `cryptography.fernet.Fernet`, key sourced from `TOTP_ENCRYPTION_KEY` env var (32 url-safe base64 bytes). If the SQLite file is ever exfiltrated, secrets remain useless without the env-var key.

`last_used_counter` prevents the well-known TOTP replay window: if a user's code for step `N` is accepted, the same code cannot be replayed within the same 30-second window.

### 5.2 New table: `user_backup_codes`

```sql
CREATE TABLE IF NOT EXISTS user_backup_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    code_hash   TEXT    NOT NULL,                     -- sha256 of code, salted with user_id
    used_at     TEXT,                                 -- NULL until consumed
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_backup_codes_user ON user_backup_codes(user_id);
```

Backup codes are **never stored in plaintext**. Only the SHA-256 of the code (with user_id as salt-equivalent) is stored. The plaintext is shown to the user exactly once, at enrollment.

### 5.3 New table: `auth_2fa_attempts` (rate limiting)

```sql
CREATE TABLE IF NOT EXISTS auth_2fa_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    ip          TEXT,
    success     INTEGER NOT NULL,
    attempted_at TEXT   NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_2fa_attempts_user_time
    ON auth_2fa_attempts(user_id, attempted_at);
```

A small rolling window of attempts per user/IP, used by the rate limiter. Old rows can be pruned by a daily cleanup or kept indefinitely for forensics — the table is tiny.

### 5.4 Extensions to the existing audit log

The portal almost certainly already has an audit/activity log. Add the following event types — no schema change required, just new `event_type` values:

| Event | When |
|---|---|
| `2fa.enroll.start` | `/auth/2fa/setup` viewed (secret generated) |
| `2fa.enroll.confirm` | First valid code accepted, 2FA activated |
| `2fa.enroll.cancel` | User abandoned setup before confirming |
| `2fa.verify.success` | TOTP code accepted at login |
| `2fa.verify.fail` | TOTP code rejected |
| `2fa.backup_code.used` | A backup code consumed |
| `2fa.backup_codes.regenerated` | User regenerated backup codes |
| `2fa.lockout` | User locked out by repeated failures |
| `2fa.admin_reset` | An admin cleared another user's 2FA |
| `2fa.disabled.self` | User disabled their own 2FA (only allowed if not mandatory) |

Every entry records: actor user_id, target user_id (where applicable), IP, user-agent, timestamp.

### 5.5 Optional: `trusted_devices` (Phase 4 only)

```sql
CREATE TABLE IF NOT EXISTS trusted_devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    token_hash  TEXT    NOT NULL,                     -- sha256 of opaque cookie value
    label       TEXT,                                 -- "Chrome on Windows, Karachi"
    expires_at  TEXT    NOT NULL,                     -- 30 days
    created_at  TEXT    NOT NULL,
    last_seen_at TEXT,
    revoked_at  TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

Recommended **not** to implement until Phase 4. Trusted-device cookies meaningfully reduce the security benefit of 2FA on shared workstations and should be opt-in per user, with a "revoke all devices" button in Security Settings.

---

## 6. Login & Enrollment Flow

### 6.1 Login flow (the critical path)

```
1. User POSTs username + password to /login
2. server.py validates credentials as it does today.
3. If credentials invalid → existing failure path (unchanged).
4. If credentials valid:
     a. Look up user_totp row for this user.
     b. If no row OR enabled=0:
          → Create full session (existing behavior).
          → If user role is in mandatory-2FA set AND no row exists,
            redirect to /auth/2fa/setup (forced enrollment).
     c. If enabled=1:
          → Create a PENDING session: set cookie with claim
            `2fa_pending=1, user_id=N, password_verified_at=now`.
          → Pending session has NO permissions — it can only hit
            /auth/2fa/verify, /auth/2fa/cancel, /logout.
          → Redirect to GET /auth/2fa/verify.
5. GET /auth/2fa/verify renders a 6-digit input + "use backup code" link.
6. POST /auth/2fa/verify:
     a. Reject if no pending session cookie.
     b. Reject if rate-limited (see §7.1).
     c. Verify code with pyotp (±1 step tolerance).
     d. On success:
          → Replace session ID (session-fixation defense).
          → Clear 2fa_pending claim, mark session fully authenticated.
          → Update user_totp.last_used_at, last_used_counter.
          → Audit-log 2fa.verify.success.
          → Redirect to original target (or default landing).
     e. On failure:
          → Increment failed_attempts, log 2fa.verify.fail.
          → If failed_attempts >= 5 within 15 min → lock for 15 min,
            log 2fa.lockout, force re-login.
          → Otherwise re-render with generic error
            ("Invalid code. Please try again.") — no enumeration.
```

**Bypass prevention.** The `require_login()` helper used by every protected route must be extended to **also reject sessions where `2fa_pending=1`**. A pending session must not be treated as authenticated by any handler. This is one line of code in the helper, plus a unit test that hits an admin URL with a pending cookie and asserts 302→/auth/2fa/verify.

### 6.2 Enrollment flow

```
1. User clicks "Security → Enable Two-Factor Authentication"
   from their account menu, or is force-redirected after login
   if their role mandates 2FA.
2. GET /auth/2fa/setup:
     a. If user_totp row exists with enabled=1 → redirect (already enrolled).
     b. Generate a fresh 160-bit base32 secret with pyotp.random_base32().
     c. Encrypt and UPSERT into user_totp with enabled=0.
     d. Build otpauth URI:
          otpauth://totp/Embassy%20Portal:{username}?secret=...&issuer=Embassy%20Portal&digits=6&period=30
     e. Render QR (in-memory PNG or SVG, never written to disk).
     f. Show secret in plain text below QR for users whose
        scanner can't read the QR (small, but real population).
     g. Audit-log 2fa.enroll.start.
3. User scans QR with Google Authenticator / Microsoft Authenticator / Authy.
4. POST /auth/2fa/setup with the 6-digit code:
     a. Verify code against the (still-disabled) secret.
     b. On success:
          → Set enabled=1, confirmed_at=now.
          → Generate 10 backup codes (8-char alphanumeric, e.g. "K3F9-PWQX").
          → Hash each, insert into user_backup_codes.
          → Render the 10 codes ONCE on the next page with a
            "Download as text file" button and a clear warning.
          → Audit-log 2fa.enroll.confirm and 2fa.backup_codes.generated.
     c. On failure: re-render setup page with error.
5. User confirms they have stored backup codes and clicks "Done".
```

The QR and the secret are **never written to disk and never returned twice**. If the user navigates away mid-setup, the next visit to `/auth/2fa/setup` generates a new secret (the previous, unconfirmed one is overwritten because `enabled=0`).

---

## 7. Security Controls

### 7.1 Rate limiting and lockout

- **Per user, per IP**: max 5 failed verifications in 15 minutes. After threshold, return 429 and require re-login. The `auth_2fa_attempts` table is the source of truth; lookups are indexed.
- **Per user, global**: max 10 failed verifications in 1 hour, regardless of IP. Mitigates a distributed brute-force.
- **Per IP, global**: max 30 failed verifications across all users in 15 minutes. Mitigates an attacker iterating through the user list.

A successful verification clears `failed_attempts` and `locked_until` for that user.

### 7.2 Time-drift tolerance

Use `pyotp.TOTP(secret).verify(code, valid_window=1)`. This accepts the previous step, current step, and next step — a 90-second total window. Do **not** widen further; each additional step doubles the brute-force surface.

### 7.3 QR codes

- Generated **on demand** in memory.
- Returned as a `data:image/png;base64,...` inline in the HTML, or as a one-shot `/auth/2fa/setup/qr.png` endpoint that requires the active enrollment session and returns `Cache-Control: no-store`.
- **Never** written to disk, never logged, never included in audit-log payloads.

### 7.4 Encrypting secrets at rest

```python
from cryptography.fernet import Fernet
fernet = Fernet(os.environ["TOTP_ENCRYPTION_KEY"].encode())
secret_encrypted = fernet.encrypt(secret.encode()).decode()
# ...
secret = fernet.decrypt(row["secret_encrypted"].encode()).decode()
```

The `TOTP_ENCRYPTION_KEY` lives in Render's environment variables, never in the repo, never in the SQLite file. **Rotating this key requires a re-encryption pass** — write the migration helper now even if you don't use it on day 1.

### 7.5 Backup codes

- 10 codes per user, format: `XXXX-XXXX` from alphabet `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (Crockford-ish, ambiguity-free).
- Generated with `secrets.token_hex` / custom alphabet using `secrets.choice`.
- Stored as `sha256(user_id || ":" || code)` — the `user_id` prefix prevents a stolen DB row from being usable across user accounts.
- **Single use**: on consumption, set `used_at`. Reject if already used.
- User can regenerate codes at any time from Security Settings — regeneration **invalidates all previous codes** and audit-logs `2fa.backup_codes.regenerated`.

### 7.6 Session fixation

On successful 2FA verification, **rotate the session ID**. The pending cookie's session ID must not be reused. Standard mitigation: delete the old session row, create a new one, set a new cookie with `Secure; HttpOnly; SameSite=Lax; Path=/`.

### 7.7 CSRF

The `/auth/2fa/verify` and `/auth/2fa/setup` POST endpoints must carry the same CSRF token mechanism the rest of the portal uses. If the portal currently relies only on `SameSite=Lax` cookies (common in stdlib portals), add a per-form CSRF token specifically for these two endpoints — they are the highest-value targets in the system.

### 7.8 HTTPS

2FA assumes the entire login flow is over TLS. Render terminates TLS by default, but enforce it in code:

```python
if request_scheme == "http" and not is_local_dev:
    return redirect("https://" + host + path, 301)
```

Mark all auth cookies `Secure`. Do not accept POSTs to `/login` or `/auth/2fa/verify` over plain HTTP in production.

### 7.9 Audit logging

Every event from §5.4 is logged with: actor user_id, target user_id, source IP, user-agent, ISO timestamp, success flag, and a freeform context string (e.g., "via backup code", "via TOTP"). Audit log writes are best-effort but must not silently fail — wrap in try/except that logs to stderr if the DB write fails.

### 7.10 Generic error messages

Verification errors return the same message regardless of cause (wrong code vs. expired code vs. used backup code vs. locked-out vs. unknown user). The HTTP status is the same. Internal logs distinguish them; the user-facing response does not.

---

## 8. Render Deployment Considerations

### 8.1 Environment variables

Add to Render service config:

| Variable | Purpose | Example |
|---|---|---|
| `TOTP_ENCRYPTION_KEY` | Fernet key for secret encryption | `Fernet.generate_key()` output |
| `TOTP_ISSUER_NAME` | Shown in authenticator app | `"Embassy Portal"` |
| `TOTP_REQUIRE_ROLES` | Comma-separated roles that must use 2FA | `"super_admin,admin"` (Phase 2) |
| `TOTP_ENABLED` | Master kill-switch | `"1"` or `"0"` |

The kill-switch is important. If 2FA causes a production incident, flipping `TOTP_ENABLED=0` and redeploying disables verification (existing rows untouched) so login proceeds on password alone. Keep this in env, not in DB — env can be flipped from Render's dashboard in seconds.

### 8.2 Secret key management

Generate `TOTP_ENCRYPTION_KEY` once, store in Render's environment, **and store a copy in your password manager / sealed envelope**. If you lose this key, every existing 2FA secret becomes undecryptable and every user must re-enroll. Document this clearly in the runbook.

### 8.3 SQLite migration

The migration is a single file (`migrations/0007_totp.sql` or whatever your numbering convention is). Run it on first request after deploy via the existing migration runner, or manually via a Render shell. Migration is idempotent (`CREATE TABLE IF NOT EXISTS`) so a re-run is safe.

If the existing migration system doesn't exist, the absolute minimal pattern:

```python
def ensure_totp_schema(conn):
    conn.executescript(open("schema/totp.sql").read())
    conn.commit()
# called once at server startup
```

### 8.4 Persistent disk

Confirm before rollout: `ls -la` on the SQLite file path inside a Render shell. The path must be inside a mounted disk (typically `/var/data` or `/data` on Render), not under the build directory. If 2FA secrets are written to ephemeral storage, the next deploy locks every admin out.

### 8.5 Deployment risks

- **Migration runs but app fails to start** → users locked out of password login because migration left tables in inconsistent state. Mitigation: migration is one transaction, runs `CREATE TABLE IF NOT EXISTS`, never alters existing tables.
- **`TOTP_ENCRYPTION_KEY` env var missing on first deploy** → enrollment crashes. Mitigation: server startup check that fails fast with a clear error if 2FA is enabled but the key is unset.
- **`pyotp` / `qrcode` not in `requirements.txt`** → ImportError at runtime. Mitigation: pin versions, deploy to a staging Render service first.
- **Clock skew on a misconfigured Render region** → all codes rejected. Mitigation: log the verification step counter on each failure for one week post-rollout; if a pattern of off-by-one rejections appears, widen `valid_window` to 2 temporarily.

### 8.6 Rollback plan

Three layers, in order of preference:

1. **Set `TOTP_ENABLED=0` in Render env, redeploy.** Verification short-circuits to "skip TOTP". Existing rows stay; no data loss. ~30 seconds.
2. **Revert the deploy in Render's dashboard.** Returns to previous binary. SQLite tables stay (they're additive, no harm). ~1 minute.
3. **DB-level reset for a single locked-out user**: `UPDATE user_totp SET enabled=0 WHERE user_id = ?;` from a Render shell. The next login then bypasses 2FA for that user only.

---

## 9. Implementation Plan (Surgical Patch, Step by Step)

This plan is designed so each step is independently revertible and so production traffic is never blocked at any point.

### Step 1 — Schema migration (no code path uses it yet)

- Create `schema/totp.sql` with the three new tables from §5.
- Wire it into the existing migration runner OR the startup `ensure_*_schema` pattern.
- Deploy. Verify tables exist via Render shell. **No user-visible change.**

### Step 2 — Add `totp_auth.py` helper module

A single new file containing:

```python
# totp_auth.py
import os, secrets, hashlib, hmac, time, sqlite3, base64, io
import pyotp, qrcode
from cryptography.fernet import Fernet

ISSUER = os.environ.get("TOTP_ISSUER_NAME", "Embassy Portal")
_FERNET = Fernet(os.environ["TOTP_ENCRYPTION_KEY"].encode())
VALID_WINDOW = 1  # ±30s

def generate_secret() -> str: ...
def encrypt_secret(s: str) -> str: ...
def decrypt_secret(c: str) -> str: ...
def build_otpauth_uri(username: str, secret: str) -> str: ...
def render_qr_png_bytes(uri: str) -> bytes: ...
def verify_totp(secret: str, code: str, last_counter: int|None) -> tuple[bool, int|None]: ...
def generate_backup_codes(n: int = 10) -> list[str]: ...
def hash_backup_code(user_id: int, code: str) -> str: ...
def consume_backup_code(conn, user_id: int, code: str) -> bool: ...
def is_rate_limited(conn, user_id: int, ip: str) -> bool: ...
def record_attempt(conn, user_id: int, ip: str, success: bool): ...
```

Unit-test this module **in isolation** (no HTTP, no `server.py`). The existing portal continues to import nothing from it. **No user-visible change.**

### Step 3 — Add `/auth/2fa/setup` (GET + POST)

- New routes that require an active full session (existing `require_login`).
- Implement enrollment per §6.2.
- Add a "Security" link in the admin account menu.
- **Roll out to staging first.** A super-admin enrolls. Confirm the QR scans in Google Authenticator and the code verifies.

At this point: 2FA is **opt-in for admins only**. Login flow is unchanged. A single admin can choose to enable 2FA but the next login still uses password only — verification doesn't run yet. **Still safe to roll back.**

### Step 4 — Add `/auth/2fa/verify` (GET + POST)

- Implement the pending-session pattern from §6.1.
- Add a `require_full_auth()` helper that rejects pending sessions.
- Modify `/login` POST: after password verification, check for `enabled=1` row, branch into pending session if present.
- **Critical**: leave `require_login()` calls on existing routes unchanged for now — they accept full sessions only, which means a pending session cannot reach any protected page. Verify this with a manual test before continuing.

After this step, an admin who has enrolled is now protected by 2FA. An admin who has not enrolled is still protected by password only — same as today.

### Step 5 — Force enrollment for mandatory roles (Phase 2)

- After successful password login, if user role is in `TOTP_REQUIRE_ROLES` and no `user_totp` row exists, redirect to `/auth/2fa/setup` with `force=1` and a non-dismissible banner: "Two-factor authentication is required for your role. Please complete setup to continue."
- The forced-setup session has the same restricted permissions as a pending session — only `/auth/2fa/setup` and `/logout` are reachable.
- Communicate to staff **at least 7 days in advance** of flipping this.

### Step 6 — Admin reset and recovery UI

- Add `/admin/users/:id/reset-2fa` (super-admin only). Sets `enabled=0`, deletes backup codes, audit-logs.
- Add "Regenerate backup codes" button in user's own Security Settings.
- Add "Disable 2FA" button — only available if user's role does **not** mandate 2FA, and requires re-entering password + current TOTP code.

### Step 7 — Hardening

- Rate limiting (§7.1) — added as middleware on `/auth/2fa/verify`.
- Audit log entries for every event in §5.4.
- HTTPS-only cookies, session rotation on verify, CSRF tokens on the two POST endpoints.

### Step 8 — Phase 3: extend to operators / fee collectors

Add their roles to `TOTP_REQUIRE_ROLES`. No code change beyond env config. Communicate, schedule a help session, monitor lockouts the first week.

### Step 9 — Optional Phase 4: trusted devices

Implement the `trusted_devices` table from §5.5 and a "Remember this device for 30 days" checkbox on the verify page. Defer until Phases 1–3 have been stable for at least a quarter.

---

## 10. Testing Checklist

### 10.1 Pre-rollout (staging)

- [ ] Migration runs cleanly on a copy of production SQLite.
- [ ] `TOTP_ENCRYPTION_KEY` set; server fails fast if missing.
- [ ] Admin without 2FA logs in normally (existing flow unchanged).
- [ ] Admin opens Security Settings, sees "Enable 2FA" button.
- [ ] QR code renders inline; secret is also shown in text form.
- [ ] Google Authenticator scans QR successfully.
- [ ] Microsoft Authenticator scans QR successfully.
- [ ] Authy scans QR successfully.
- [ ] First valid code activates 2FA; backup codes display once.
- [ ] Refreshing the backup-codes page does **not** show them again.

### 10.2 Login flow

- [ ] Wrong password → existing failure (no enumeration of 2FA status).
- [ ] Correct password, no 2FA → full session created, lands on dashboard.
- [ ] Correct password, 2FA enabled → redirect to `/auth/2fa/verify`.
- [ ] Pending session cannot reach `/admin` (302 → verify page).
- [ ] Pending session cannot reach `/api/...` admin endpoints.
- [ ] Direct GET `/admin` with a pending cookie → 302 → verify.
- [ ] Direct POST to `/admin/...` with a pending cookie → 401/403, audit-logged.
- [ ] Wrong TOTP code → generic error, attempt logged.
- [ ] Correct TOTP code → full session, session ID rotated, lands on original target.
- [ ] Code from previous 30-second window accepted (drift tolerance).
- [ ] Code from two windows ago rejected.
- [ ] Same code accepted twice within window? **Must be rejected** (replay).

### 10.3 Backup codes

- [ ] Backup code accepted at `/auth/2fa/verify`.
- [ ] Same backup code rejected on second use.
- [ ] Used count reflects in user's Security Settings (e.g., "3 of 10 remaining").
- [ ] Regenerating codes invalidates all previous codes immediately.

### 10.4 Lockout and rate limiting

- [ ] 5 wrong codes within 15 min → lockout, forced re-login.
- [ ] Lockout expires after 15 min; correct code then accepted.
- [ ] Successful code clears `failed_attempts`.
- [ ] Distributed attempt across multiple IPs against one user → still rate-limited.

### 10.5 Recovery

- [ ] Super-admin resets another admin's 2FA; that admin's next login bypasses TOTP and forces re-enrollment.
- [ ] Reset is audit-logged with actor and target.
- [ ] User who disabled 2FA (where allowed) can no longer use old backup codes.

### 10.6 Public workflows (regression)

- [ ] Public applicant tracking page loads without any auth prompts.
- [ ] Fee receipt PDF download (public) works unchanged.
- [ ] Note Verbal status check (public) works unchanged.
- [ ] Nurses registration public lookup works unchanged.
- [ ] Transit visa public application status works unchanged.

### 10.7 Operator/fee collector during admin-only rollout (Phase 1)

- [ ] Operator login flow is unchanged (no `/auth/2fa/verify` redirect).
- [ ] Fee collector login flow is unchanged.
- [ ] Operator dashboards render identically.

### 10.8 Render deployment

- [ ] SQLite file confirmed on persistent disk.
- [ ] `TOTP_ENABLED=0` kill-switch genuinely disables verification.
- [ ] Rollback to previous deploy retains 2FA tables (additive, no data loss).
- [ ] `pyotp`, `qrcode`, `cryptography` versions pinned in `requirements.txt`.

### 10.9 Security audit checks

- [ ] No QR PNG written to disk anywhere (grep build dir, `/tmp`).
- [ ] No TOTP secret in any log file.
- [ ] No backup code in plaintext after enrollment page is closed.
- [ ] HTTPS enforced on `/login`, `/auth/2fa/*`.
- [ ] All auth cookies `Secure; HttpOnly; SameSite=Lax`.
- [ ] CSRF token present on POST `/auth/2fa/setup` and `/auth/2fa/verify`.

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Admin loses phone, no backup codes saved | Medium | High | Mandatory display of backup codes at enrollment; "I have saved my codes" checkbox required to finish; super-admin reset path. |
| Entire admin team locked out simultaneously | Low | Critical | Break-glass super-admin with backup codes in sealed envelope; documented runbook for DB-level `UPDATE user_totp SET enabled=0`. |
| Pending session bypassed by a missed `require_full_auth` check | Low | High | Single source of truth for the auth check; explicit test for every protected route in §10.2. Code review required for any new admin route. |
| Shared staff account (one login used by multiple operators) | Medium | High | Forbid shared accounts before enabling 2FA. Audit `users` table for accounts logged in from >3 distinct IPs in 30 days; convert to per-person accounts. |
| Lost-phone "social engineering" reset abuse | Medium | High | Reset only by super-admin; reset request must include a ticket/email trail; audit log reviewed weekly. |
| Time sync drift on Render container | Low | Medium | `valid_window=1` (±30s) absorbs realistic drift; monitor failure rate post-rollout. |
| TOTP secret leak via log accident | Low | Critical | Encrypt at rest; never log secret or the otpauth URI; lint check that `secret` variable is never passed to logging functions. |
| Encryption key (`TOTP_ENCRYPTION_KEY`) lost | Low | Critical | Backup key in password manager + sealed envelope; document re-encryption migration. |
| Public applicant workflow accidentally gated by 2FA | Low | High | Public routes never call `require_login`; explicit regression test in §10.6; staging walkthrough before each phase. |
| `pyotp` or `qrcode` security CVE | Low | Medium | Pin versions; subscribe to GitHub security advisories for both repos; quarterly review. |
| User stores TOTP secret in same password manager as portal password | Medium | Medium | This collapses 2FA back to single-factor for that user. Document in user training: authenticator app must be on a different device or in a different vault than the portal password. |
| Rate-limit table grows unbounded | Low | Low | Daily cleanup deletes rows older than 30 days; even without cleanup, 30k rows/day ≈ negligible for SQLite. |

---

## 12. Final Recommendation

**Proceed.** The change is technically straightforward, costs nothing at runtime, materially reduces the blast radius of credential phishing against admin staff, and can be staged so that any phase is independently rollback-safe.

### Recommended rollout

| Phase | Scope | Duration | Gate to next phase |
|---|---|---|---|
| **Phase 0** | Schema migration + `totp_auth.py` module deployed dormant. | 2–3 days | Migration verified on persistent disk; module unit-tested. |
| **Phase 1** | Optional 2FA for super-admin and admin. Self-enrollment via Security Settings. | 2 weeks | At least 2 admins enrolled, login flow stable, no public-side regressions, recovery flow rehearsed once on a real account. |
| **Phase 2** | Mandatory 2FA for admin and super-admin. Forced enrollment on next login. | 4 weeks | <1% support tickets related to 2FA in the second week; no lockouts requiring DB intervention in the final week. |
| **Phase 3** | Mandatory 2FA for operators and fee collectors. | After 4 weeks of Phase 2 stability | Same gates as Phase 2, but for the larger population. |
| **Phase 4** *(optional)* | Trusted-device cookies, advanced audit dashboards, IP allow-listing for super-admin actions. | Quarter-scale project | Separate evaluation. |

### What this report deliberately does *not* recommend

- **No rewrite of the auth system.** Existing password verification, session storage, and role checks stay exactly as they are. 2FA layers on top of, not into, the existing system.
- **No framework migration.** `http.server` + SQLite is sufficient for this change.
- **No SMS, email OTP, or third-party identity provider.** All add cost, complexity, attack surface, or all three, with no security gain over TOTP.
- **No 2FA for public applicants.** The portal's accessibility to the community it serves is itself a security property; gating public lookups behind authenticator apps would degrade service without proportional benefit.
- **No self-service email reset.** Until a manual second-admin approval flow is built, lost-2FA recovery goes through a super-admin ticket.

### Single decision still needed from you

**Who is the break-glass super-admin?** Pick one named individual whose backup codes will live in a sealed envelope in the office safe. Document the recovery runbook with their name. Without this decision, "admin reset" is a circular dependency.

---

*End of report.*
