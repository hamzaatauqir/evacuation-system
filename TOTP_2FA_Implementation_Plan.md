# TOTP 2FA — Surgical Implementation Plan & Patch
**Embassy / Community Welfare Portal — `server.py` (Python stdlib HTTP + SQLite, Render)**
Prepared 2026-05-09. Companion to `TOTP_2FA_Feasibility_Report.md`.

---

## A. Implementation Audit (what's actually in `server.py`)

I read `server.py` (~46k lines, monolithic, stdlib `http.server`-based). The auth machinery is concentrated and clean enough to patch surgically. Findings are referenced to real line numbers so the diffs below land precisely.

### A.1 Authentication primitives

| Concern | Location | Notes |
|---|---|---|
| Cookie parser | `from http.cookies import SimpleCookie` (line 15) | Already imported. Reusable. |
| In-memory session store | `SESSIONS = {}`, `SESSIONS_LOCK = threading.Lock()` (lines 95–96) | Sessions are not persisted across restarts — acceptable for 2FA, since pending sessions are short-lived (10 min). |
| Session create | `def create_session(username, role)` (line 21686) | Returns a 32-byte hex token; row schema is `{'user', 'role', 'expires'}`. **We extend this to optionally produce a pending-2FA session.** |
| Session read | `def get_session(cookie_str)` (line 21692) | Reads the `session` cookie, validates expiry. **We do not change this — `_pending_2fa` becomes a transparent dict key.** |
| Login rate limit | `check_login_rate(ip)`, `record_login_failure(ip)`, `record_login_success(ip)` (lines 21663–21684) | Pre-existing; we layer 2FA-attempt rate limiting on top of this, without altering it. |
| Password hash | `hash_pw(pw)` SHA-256 (line 3265); `_verify_user_password(db, username, password)` (line 3275) | Out of scope for 2FA work. (Worth a separate conversation about migrating to argon2/bcrypt — but we will not touch it now.) |

### A.2 Login flow (current)

`POST /api/login` is at **line 37336**. Concretely:

```
client_ip = self.client_address[0]
if not check_login_rate(client_ip): -> 429
data = json.loads(body)
user = db.execute("SELECT * FROM users WHERE username = ?", [data.get('username','')]).fetchone()
if user and not _user_is_active(user):           -> 403 inactive
elif user and user['password_hash'] == hash_pw(data.get('password','')):
    record_login_success(client_ip)
    token = create_session(user['username'], user['role'])
    Set-Cookie: session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400
    return {success, user, role, redirect_url}
else:
    record_login_failure(client_ip) -> 401
```

`GET /login` (line 32626) just serves `LOGIN_PAGE` (a static HTML constant inside `server.py`). The JS in that page POSTs to `/api/login` and follows `redirect_url` on success.

**Cookie note:** `Secure` is **not** currently set. In production on Render (HTTPS), we must add it conditionally. Render also forwards client IP in `X-Forwarded-For`; the existing code uses `self.client_address[0]` for rate limiting, but `self.get_client_ip()` (line 32276) prefers `X-Forwarded-For` — we will use the latter for 2FA attempts to attribute correctly.

### A.3 Auth guard

`def require_auth(self)` at **line 32285** is the single chokepoint:

```
def require_auth(self):
    user = self.get_user()
    if not user:
        self.send_redirect('/login'); return None
    path = self.normalize_request_path(...)
    role = user.get('role') or ''
    allowed = can_access_api_route(role, path) if path.startswith('/api/') else can_access_admin_route(role, path)
    if not allowed:
        ... 403 / role-redirect
        return None
    return user
```

It is called **>400 times** across `do_GET` and `do_POST` (e.g. lines 32683, 32690, 32697, ...). This is exactly the surgery point: **we add one early return inside `require_auth` that rejects pending-2FA sessions** — and every protected route is automatically protected without touching its body.

### A.4 Roles structure

- **No `super_admin` role exists today.** The top role is `admin`. `FULL_SYSTEM_ROLES = {'admin', 'operator', 'operator_special'}` (line 5156).
- Other roles in active use: `fee_collector`, `iraq_cwa`, `nadra_staff`, `passport_staff`, `welfare_officer`, `legal_officer`, `death_case_officer`, `staff_opf`, `field_staff`, `community_desk`, `inspector_field`, `senior_review`, `ambassador_review`, `nurses_desk`, `nurses_welfare_desk`, etc.
- Helper: `is_full_admin_role(role)` already exists.
- Route gates: `can_access_admin_route(role, path)` (line 5267), `can_access_api_route(role, path)` (line 5319), `_default_redirect_for_role(role)` (line 5242).
- **Recommendation:** do **not** introduce a new `super_admin` role yet. Instead, designate "super-admin" as the subset of `admin` users named in env var `TOTP_SUPER_ADMINS` (comma-separated usernames). This avoids touching the role system, the route gates, or the user-management UI in Phase 0–1.

### A.5 Audit logging

There is **no central `audit_log()` helper**. Every call site inlines the SQL:

```python
db.execute("INSERT INTO audit_log (action, record_id, user, details) VALUES (?, ?, ?, ?)", ...)
```

The `audit_log` table schema (line 973):
```sql
audit_log (id, action, record_id, user, details, created_at)
```

We will follow the same pattern — every 2FA event becomes `INSERT INTO audit_log (action, user, details) VALUES ('2fa.<event>', <username>, <json blob>)`. We add a small wrapper `_2fa_audit(db, username, event, details_dict)` inside `totp_auth.py` to keep call sites tidy, but we do **not** change `audit_log`'s schema.

There are also subdomain audit tables (`gl_audit`, `nh_audit`, `nurse_onboarding_audit`) — none of them are appropriate for 2FA events. We use the global `audit_log`.

### A.6 DB access

`get_db()` (line 192) returns a connection. The codebase uses the pattern `db = get_db(); ... ; db.close()` everywhere. `init_db()` (line 909) runs `executescript` of all `CREATE TABLE IF NOT EXISTS` DDL on startup. **This is exactly where we hook the 2FA schema** — additive, idempotent, no migration system needed.

### A.7 Settings / admin menu area for "Security Settings"

The login page and admin shell are HTML constants embedded in `server.py`. The cleanest insertion point is a new top-level route `/admin/security` rendered with the existing `render_template_with_context` pattern (used at e.g. line 32687) — we add a tiny `templates/admin_security.html`. The dashboard navigation can be updated later (Phase 1.5); for Phase 1, we link to `/admin/security` from a banner shown after login if the user role is in `TOTP_REQUIRE_ROLES`. **Phase 1 does not require modifying any existing admin nav HTML.**

### A.8 Public applicant routes — confirmed isolated from 2FA path

Public routes (no `require_auth` call): `/`, `/login` (GET), `/api/login` (POST — only path that touches creds), `/poster`, `/transit`, `/nurses`, `/nurses/register`, `/nurses/track`, `/nurses/login`, `/nurses/grading-letter`, `/nurses/accommodation`, `/nurses/complaint`, `/nurses/leave-notice`, `/legal-opf`, `/legal-opf/track`, `/death-cases`, `/death-cases/track`, `/locating-assistance`, `/community-feedback`, `/iraq-public-form`, etc. (lines 32620–32680).

Our patch **does not touch any of these**. The only login-path code we modify is `/api/login` (line 37336), and the only auth-guard we modify is `require_auth` (line 32285) — both of which already had no effect on public routes.

---

## B. Surgical Patch Plan (additive, reversible)

### B.1 Files added (Phase 0 — dormant)

```
schema/totp.sql       (new — DDL only, idempotent)
totp_auth.py          (new — helpers; nothing imports it yet)
templates/admin_security.html   (Phase 1 — new template for /admin/security)
tests/smoke/test_totp.py        (optional — local smoke test)
```

### B.2 Files modified

```
server.py             (Phase 1 — small, well-bounded inserts described in §C)
requirements.txt      (Phase 1 — add pyotp, qrcode, cryptography)
```

### B.3 Phase boundaries (each phase is independently revertible)

| Phase | Files touched | Behavioral change |
|---|---|---|
| **0** | + `schema/totp.sql`, + `totp_auth.py`, + line in `init_db()` to `executescript` the new SQL | Tables created. **No flow change.** Module is unused. |
| **1** | `server.py` `/api/login`, `require_auth`, new routes `/auth/2fa/setup`, `/auth/2fa/verify`, `/admin/security`, `/api/admin/users/<id>/reset-2fa`. + `templates/admin_security.html`. + `requirements.txt`. | Optional 2FA for users in role set `TOTP_REQUIRE_ROLES` — defaults empty (no role mandated). Admins who voluntarily enroll get 2FA. **No staff is forced.** |
| **2** | `Render env`: `TOTP_REQUIRE_ROLES=admin` | Admins forced to enroll on next login. **No code change.** |
| **3** | `Render env`: `TOTP_REQUIRE_ROLES=admin,operator,operator_special,fee_collector` | Operators and fee collectors join. **No code change.** |
| **rollback** | `Render env`: `TOTP_ENABLED=0` | Verification short-circuits. Existing rows untouched. **30-second rollback.** |

### B.4 Environment variables (Render)

| Var | Required | Default | Purpose |
|---|---|---|---|
| `TOTP_ENABLED` | no | `1` | Master kill-switch. `0` skips all 2FA logic. |
| `TOTP_ENCRYPTION_KEY` | yes (when enabled) | — | Fernet key. Generated once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Server fails fast on startup if unset and `TOTP_ENABLED=1`. |
| `TOTP_ISSUER_NAME` | no | `"Embassy Portal"` | Shown in authenticator app. |
| `TOTP_REQUIRE_ROLES` | no | `""` (empty) | CSV of roles for which 2FA is mandatory. Empty = optional for everyone. |
| `TOTP_SUPER_ADMINS` | no | `""` | CSV of usernames who can reset other users' 2FA. Falls back to the existing default `admin` user if empty. |
| `TOTP_PENDING_TTL_SECONDS` | no | `600` | Pending session lifetime (10 min). |

### B.5 Backout / rollback recipe

1. **Set `TOTP_ENABLED=0`** in Render → redeploy. All login flows skip 2FA. Existing enrolled users keep their rows. ETA: 30 s.
2. **Roll back the deploy** in Render. SQLite tables stay (additive, harmless). ETA: 1 min.
3. **Per-user emergency unlock**: in Render shell, `sqlite3 /var/data/db.sqlite "UPDATE user_totp SET enabled=0 WHERE user_id=(SELECT id FROM users WHERE username='LOCKED_USER');"`. The next login bypasses 2FA for that user only.

---

## C. Exact Code Patches

### C.1 `schema/totp.sql` (new file — Phase 0)

See `schema/totp.sql` already created in this workspace. Idempotent `CREATE TABLE IF NOT EXISTS` for three tables: `user_totp`, `user_backup_codes`, `auth_2fa_attempts`. Run via existing `init_db()` (see C.3 patch #1).

### C.2 `totp_auth.py` (new file — Phase 0)

See `totp_auth.py` already created in this workspace. Self-contained module:

- `is_enabled()` — reads `TOTP_ENABLED` env
- `get_super_admins()` — reads `TOTP_SUPER_ADMINS` env
- `get_required_roles()` — reads `TOTP_REQUIRE_ROLES` env
- `generate_secret()`, `encrypt_secret()`, `decrypt_secret()`
- `build_otpauth_uri(username, secret)`
- `render_qr_png_data_uri(uri)` — returns inline `data:image/png;base64,...`
- `verify_totp(secret, code, last_counter)` — returns `(ok, new_counter)`
- `generate_backup_codes(n=10)`, `hash_backup_code(user_id, code)`, `consume_backup_code(db, user_id, code)`
- `is_2fa_locked(db, user_id, ip)`, `record_attempt(db, user_id, ip, success)`
- `audit(db, username, event, details=None)`
- `enroll_start(db, user_id, username)`, `enroll_confirm(db, user_id, code)`, `verify_for_login(db, user_id, code, ip)`
- `admin_reset(db, target_user_id, actor_username)`

Nothing in `server.py` imports it during Phase 0.

### C.3 `server.py` patches (Phase 1)

All patches are inserts. Nothing existing is removed; one method gets one early-return added.

#### Patch #1 — Wire schema into `init_db()` (top of file change)

Find (line 905, just before `def init_db():`):

```python
def init_db():
    global GRADING_LETTER_AVAILABLE
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
```

Add — at the **end** of `init_db()` (find the function's last statement and append before its `db.commit(); db.close()`-equivalent):

```python
    # ── TOTP 2FA schema (additive, idempotent) ─────────────────────
    try:
        _totp_sql_path = (Path(__file__).resolve().parent / 'schema' / 'totp.sql')
        if _totp_sql_path.is_file():
            db.executescript(_totp_sql_path.read_text(encoding='utf-8'))
    except Exception as _e:
        # Never let 2FA schema bootstrap break the rest of init_db.
        print(f'[totp] schema init skipped: {_e}', flush=True)
```

This is intentionally fail-soft: if `schema/totp.sql` is missing, the rest of the portal still boots normally.

#### Patch #2 — Import the helper module (top-of-file imports)

Add near the existing imports (after line 15 region):

```python
try:
    import totp_auth
except Exception as _totp_import_err:
    totp_auth = None
    print(f'[totp] module import failed (2FA disabled): {_totp_import_err}', flush=True)
```

Again fail-soft. If `pyotp`/`qrcode`/`cryptography` aren't installed, the portal continues without 2FA — exactly as today.

#### Patch #3 — Extend `create_session` for pending-2FA sessions

Find (line 21686):

```python
def create_session(username, role):
    token = secrets.token_hex(32)
    with SESSIONS_LOCK:
        SESSIONS[token] = {'user': username, 'role': role, 'expires': time.time() + 86400}
    return token
```

Replace with:

```python
def create_session(username, role, pending_2fa=False, user_id=None):
    token = secrets.token_hex(32)
    now = time.time()
    if pending_2fa:
        ttl = int(os.environ.get('TOTP_PENDING_TTL_SECONDS') or 600)
        record = {
            'user': username,
            'role': role,
            'expires': now + ttl,
            '_pending_2fa': True,
            '_password_verified_at': now,
            '_user_id': user_id,
        }
    else:
        record = {'user': username, 'role': role, 'expires': now + 86400}
    with SESSIONS_LOCK:
        SESSIONS[token] = record
    return token

def upgrade_session_after_2fa(old_token):
    """Rotate a pending session into a full authenticated session (defends against fixation)."""
    with SESSIONS_LOCK:
        old = SESSIONS.pop(old_token, None)
    if not old:
        return None
    new_token = secrets.token_hex(32)
    with SESSIONS_LOCK:
        SESSIONS[new_token] = {
            'user': old.get('user'),
            'role': old.get('role'),
            'expires': time.time() + 86400,
        }
    return new_token
```

Backward compatibility: existing call site `create_session(user['username'], user['role'])` continues to work — `pending_2fa` defaults to False.

#### Patch #4 — Add early reject for pending sessions in `require_auth`

Find (line 32285):

```python
def require_auth(self):
    user = self.get_user()
    if not user:
        self.send_redirect('/login')
        return None
    path = self.normalize_request_path(urlparse(getattr(self, 'path', '')).path)
```

Insert **between line 32289 (`return None`) and line 32290 (`path = ...`)**:

```python
    # ── 2FA: a pending session is NOT authenticated ────────────────
    if user.get('_pending_2fa'):
        path = self.normalize_request_path(urlparse(getattr(self, 'path', '')).path)
        # Allow the verify endpoint, the cancel endpoint, and logout.
        allowed_pending = (
            path == '/auth/2fa/verify'
            or path == '/api/auth/2fa/verify'
            or path == '/auth/2fa/cancel'
            or path == '/logout'
        )
        if not allowed_pending:
            if path.startswith('/api/'):
                self.send_json({'success': False, 'error': '2FA required', 'redirect_url': '/auth/2fa/verify'}, 401)
            else:
                self.send_redirect('/auth/2fa/verify')
            return None
        return user
```

This single insert covers every one of the **>400** existing `require_auth()` call sites.

#### Patch #5 — Modify `/api/login` to branch on 2FA-enabled users

Find (line 37336):

```python
        elif path == '/api/login':
            client_ip = self.client_address[0]
            if not check_login_rate(client_ip):
                self.send_json({'success': False, 'error': 'Too many failed attempts. Please wait 5 minutes.'}, 429)
                return
            data = json.loads(body)
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE username = ?", [data.get('username', '')]).fetchone()
            db.close()
            if user and not _user_is_active(user):
                record_login_failure(client_ip)
                self.send_json({'success': False, 'error': 'User account is inactive. Please contact the administrator.'}, 403)
            elif user and user['password_hash'] == hash_pw(data.get('password', '')):
                record_login_success(client_ip)
                token = create_session(user['username'], user['role'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400')
                redirect_url = _default_redirect_for_role(user['role'])
                resp = json.dumps({'success': True, 'user': user['username'], 'role': user['role'], 'redirect_url': redirect_url}).encode()
                self.send_header('Content-Length', len(resp))
                self.end_headers()
                self.wfile.write(resp)
            else:
                record_login_failure(client_ip)
                remaining = 5 - LOGIN_ATTEMPTS.get(client_ip, {}).get('count', 0)
                msg = 'Invalid credentials' + (f' ({remaining} attempts remaining)' if remaining > 0 else '')
                self.send_json({'success': False, 'error': msg}, 401)
```

Replace the `elif user and user['password_hash'] == hash_pw(...):` branch with:

```python
            elif user and user['password_hash'] == hash_pw(data.get('password', '')):
                record_login_success(client_ip)
                # ── 2FA gate ───────────────────────────────────────
                require_2fa = False
                force_setup = False
                user_2fa_row = None
                if totp_auth is not None and totp_auth.is_enabled():
                    db2 = get_db()
                    try:
                        user_2fa_row = db2.execute(
                            "SELECT * FROM user_totp WHERE user_id = ?", [user['id']]
                        ).fetchone()
                    finally:
                        db2.close()
                    role_required = (user['role'] or '') in totp_auth.get_required_roles()
                    has_confirmed = bool(user_2fa_row and user_2fa_row['enabled'])
                    if has_confirmed:
                        require_2fa = True
                    elif role_required:
                        force_setup = True

                cookie_secure = '; Secure' if self.request_scheme() == 'https' else ''

                if require_2fa:
                    token = create_session(user['username'], user['role'], pending_2fa=True, user_id=user['id'])
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Strict{cookie_secure}; Max-Age=600')
                    resp = json.dumps({'success': True, 'require_2fa': True, 'redirect_url': '/auth/2fa/verify'}).encode()
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                    return

                if force_setup:
                    # Pending session, but next stop is /auth/2fa/setup not /verify.
                    token = create_session(user['username'], user['role'], pending_2fa=True, user_id=user['id'])
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Strict{cookie_secure}; Max-Age=600')
                    resp = json.dumps({'success': True, 'force_2fa_setup': True, 'redirect_url': '/auth/2fa/setup'}).encode()
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                    return

                # ── Existing path: full session ────────────────────
                token = create_session(user['username'], user['role'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Strict{cookie_secure}; Max-Age=86400')
                redirect_url = _default_redirect_for_role(user['role'])
                resp = json.dumps({'success': True, 'user': user['username'], 'role': user['role'], 'redirect_url': redirect_url}).encode()
                self.send_header('Content-Length', len(resp))
                self.end_headers()
                self.wfile.write(resp)
```

Notes:
- `force_setup` requires the **GET `/auth/2fa/setup`** handler (added below) to also accept a pending session. We special-cased `/auth/2fa/setup` in Patch #4? **Yes** — add `/auth/2fa/setup` and `/api/auth/2fa/setup` to `allowed_pending` in Patch #4. (Easy to forget — flagging here.)
- The `Secure` cookie flag is now set when scheme is `https`. The existing call sites that didn't set `Secure` are left alone for backwards compatibility, but the new branches set it.

**Final Patch #4 update (with `/auth/2fa/setup` in the allow-list):**

```python
        allowed_pending = (
            path == '/auth/2fa/verify'
            or path == '/api/auth/2fa/verify'
            or path == '/auth/2fa/setup'
            or path == '/api/auth/2fa/setup'
            or path == '/auth/2fa/cancel'
            or path == '/logout'
        )
```

#### Patch #6 — New routes in `do_GET` (alongside existing `/login` block at ~line 32626)

Insert into `do_GET` (right after the `elif path == '/login':` block):

```python
        elif path == '/auth/2fa/verify':
            user = self.get_user()
            if not user:
                self.send_redirect('/login'); return
            if not user.get('_pending_2fa'):
                # Already authenticated — no reason to be here.
                self.send_redirect(_default_redirect_for_role(user.get('role') or '')); return
            self.send_html(self._render_2fa_verify_page())

        elif path == '/auth/2fa/setup':
            user = self.get_user()
            if not user:
                self.send_redirect('/login'); return
            db = get_db()
            try:
                user_id = (user.get('_user_id')
                           or (db.execute("SELECT id FROM users WHERE username = ?",
                                          [user.get('user')]).fetchone() or {})['id'])
                ctx = totp_auth.enroll_start(db, user_id, user.get('user'))
            finally:
                db.close()
            self.send_html(self._render_2fa_setup_page(ctx))

        elif path == '/admin/security':
            user = self.require_auth()
            if not user: return
            self.send_html(self._render_security_settings_page(user))
```

(`_render_2fa_verify_page`, `_render_2fa_setup_page`, `_render_security_settings_page` are small string-template methods on the handler class — see C.4 templates section below.)

#### Patch #7 — New routes in `do_POST` (alongside `/api/login` block at ~line 37336)

Insert into `do_POST` (right after the `/api/login` block):

```python
        elif path == '/api/auth/2fa/setup':
            # Confirm enrollment with first valid code.
            user = self.get_user()
            if not user:
                self.send_json({'success': False, 'error': 'Not authenticated'}, 401); return
            data = json.loads(body or b'{}')
            code = (data.get('code') or '').strip()
            db = get_db()
            try:
                user_id = (user.get('_user_id')
                           or (db.execute("SELECT id FROM users WHERE username = ?",
                                          [user.get('user')]).fetchone() or {})['id'])
                result = totp_auth.enroll_confirm(db, user_id, code)
            finally:
                db.close()
            if not result.get('ok'):
                self.send_json({'success': False, 'error': 'Invalid code. Please try again.'}, 400); return
            self.send_json({'success': True, 'backup_codes': result['backup_codes']})

        elif path == '/api/auth/2fa/verify':
            user = self.get_user()
            if not user or not user.get('_pending_2fa'):
                self.send_json({'success': False, 'error': 'No pending 2FA session', 'redirect_url': '/login'}, 401); return
            data = json.loads(body or b'{}')
            code = (data.get('code') or '').strip()
            ip = self.get_client_ip()
            db = get_db()
            try:
                if totp_auth.is_2fa_locked(db, user.get('_user_id'), ip):
                    self.send_json({'success': False, 'error': 'Too many attempts. Try again in 15 minutes.'}, 429); return
                ok = totp_auth.verify_for_login(db, user.get('_user_id'), code, ip)
            finally:
                db.close()
            if not ok:
                self.send_json({'success': False, 'error': 'Invalid code. Please try again.'}, 400); return
            # Rotate session.
            old_token = self._extract_session_cookie()
            new_token = upgrade_session_after_2fa(old_token)
            cookie_secure = '; Secure' if self.request_scheme() == 'https' else ''
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Set-Cookie', f'session={new_token}; Path=/; HttpOnly; SameSite=Strict{cookie_secure}; Max-Age=86400')
            redirect_url = _default_redirect_for_role(user.get('role') or '')
            resp = json.dumps({'success': True, 'redirect_url': redirect_url}).encode()
            self.send_header('Content-Length', len(resp))
            self.end_headers()
            self.wfile.write(resp)

        elif path == '/api/admin/users/2fa-reset':
            user = self.require_auth()
            if not user: return
            super_admins = totp_auth.get_super_admins() or {'admin'}
            if user.get('user') not in super_admins:
                self.send_json({'success': False, 'error': 'Forbidden'}, 403); return
            data = json.loads(body or b'{}')
            target_user_id = int(data.get('user_id') or 0)
            db = get_db()
            try:
                ok = totp_auth.admin_reset(db, target_user_id, user.get('user'))
            finally:
                db.close()
            self.send_json({'success': ok})
```

Helper `_extract_session_cookie`:

```python
    def _extract_session_cookie(self):
        cookie_str = self.headers.get('Cookie') or ''
        c = SimpleCookie(); c.load(cookie_str)
        m = c.get('session')
        return m.value if m else None
```

### C.4 Templates (Phase 1 — minimal, inline-able)

You can either add three small `templates/*.html` files or render inline strings inside `server.py`. Given the existing pattern (LOGIN_PAGE etc. are inline constants), inline is consistent. Each template is short:

- **2FA verify page** — single 6-digit input, "use a backup code" toggle, error region, POSTs to `/api/auth/2fa/verify`.
- **2FA setup page** — `<img src="{data_uri_qr}">`, secret in `<code>`, 6-digit confirm input, posts to `/api/auth/2fa/setup`. On success the JS swaps the page to show the 10 backup codes once with a "Download" button.
- **Security settings page** — shows enrollment status, "Regenerate backup codes", "Disable 2FA" (only if role not in `TOTP_REQUIRE_ROLES`), and (for super-admins) a tiny "Reset another user's 2FA" form.

These templates are non-secret and small enough that you may prefer to keep them as Python string constants near the existing `LOGIN_PAGE`. The plan does not assume one or the other.

### C.5 `requirements.txt` patch (Phase 1)

```
pyotp==2.9.0
qrcode[pil]==7.4.2
cryptography==42.0.5
```

(Versions are conservative current-stable as of writing. Pin tightly so a transitive bump doesn't surprise you on Render redeploy.)

### C.6 Render env vars (Phase 1 deploy)

Generate the encryption key once locally:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set in Render dashboard:

```
TOTP_ENABLED=1
TOTP_ENCRYPTION_KEY=<the generated value>
TOTP_ISSUER_NAME=Embassy Portal
TOTP_REQUIRE_ROLES=
TOTP_SUPER_ADMINS=admin
TOTP_PENDING_TTL_SECONDS=600
```

`TOTP_REQUIRE_ROLES` stays empty in Phase 1 (optional). Flip to `admin` in Phase 2.

**Back up `TOTP_ENCRYPTION_KEY` in your password manager AND in a sealed envelope.** Losing it means re-enrolling everyone.

---

## D. Local Testing Commands

### D.1 Lint-level smoke test (no DB, no HTTP)

```bash
cd "/Users/hamzatauqir/Desktop/NEw Update"
pip install --break-system-packages pyotp 'qrcode[pil]' cryptography
python3 -c "
import os, sys
os.environ['TOTP_ENABLED']='1'
os.environ['TOTP_ENCRYPTION_KEY']=__import__('cryptography.fernet', fromlist=['Fernet']).Fernet.generate_key().decode()
import totp_auth
secret = totp_auth.generate_secret()
enc = totp_auth.encrypt_secret(secret)
assert totp_auth.decrypt_secret(enc) == secret
import pyotp
code = pyotp.TOTP(secret).now()
ok, ctr = totp_auth.verify_totp(secret, code, None)
assert ok, 'verify failed'
ok2, _ = totp_auth.verify_totp(secret, code, ctr)
assert not ok2, 'replay should fail'
print('OK')
"
```

### D.2 Schema bootstrap test

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect(':memory:')
conn.executescript(open('schema/totp.sql').read())
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]
assert 'user_totp' in tables and 'user_backup_codes' in tables and 'auth_2fa_attempts' in tables
print('schema OK:', tables)
"
```

### D.3 End-to-end manual test (local)

1. `python3 server.py` (with the env vars from C.6 set locally).
2. Browser → `http://localhost:8000/login` → log in as `admin` / `embassy2026`.
3. Visit `/admin/security` → click "Enable 2FA".
4. QR appears. Open Google Authenticator, scan.
5. Enter the 6-digit code → see 10 backup codes once.
6. Log out. Log in again.
7. Should redirect to `/auth/2fa/verify`. Enter a code. Lands on dashboard.
8. Try direct URL `http://localhost:8000/admin/dashboard` while in pending state → must redirect to `/auth/2fa/verify`.

### D.4 Public regression test

While 2FA is enabled, visit the following URLs in incognito/no-cookie mode and confirm they all load without any auth prompt:

```
/                          /nurses                    /nurses/track
/nurses/login              /nurses/register           /transit
/legal-opf                 /legal-opf/track           /death-cases
/death-cases/track         /locating-assistance       /community-feedback
/iraq-public-form          /poster
```

---

## E. Testing Checklist

### E.1 Phase 0 (dormant deploy)

- [ ] `schema/totp.sql` runs on production SQLite copy without error.
- [ ] All three tables exist after deploy: `user_totp`, `user_backup_codes`, `auth_2fa_attempts`.
- [ ] `import totp_auth` succeeds (or fails-soft if deps not installed — confirm message in logs).
- [ ] No login flow change. Existing admin login still works.
- [ ] No public route affected.

### E.2 Phase 1 (optional admin enrollment)

- [ ] Admin without 2FA logs in normally (no extra step).
- [ ] Admin opens `/admin/security`, sees "Enable 2FA".
- [ ] QR renders inline (no file written to disk — `find /tmp /var/data -name "*.png" -newer ...` returns nothing).
- [ ] Authenticator app scans the QR cleanly.
- [ ] Wrong setup code → "Invalid code" error, secret remains `enabled=0`.
- [ ] Correct setup code → 10 backup codes shown once; refreshing does not re-show them.
- [ ] Login as that admin → redirected to `/auth/2fa/verify`.
- [ ] Pending session GET to `/admin/dashboard` → 302 → `/auth/2fa/verify`. (Test in browser AND with curl.)
- [ ] Pending session POST to `/api/admin/...` → 401 with `{"redirect_url": "/auth/2fa/verify"}`.
- [ ] Wrong TOTP code → generic error, attempt logged in `auth_2fa_attempts`.
- [ ] Correct TOTP code → session ID rotates (new `Set-Cookie` header), lands on dashboard.
- [ ] Same code submitted twice in same window → second attempt rejected (replay protection).
- [ ] Backup code accepted; same backup code rejected on second use.
- [ ] 5 wrong codes within 15 min → 429 lockout.
- [ ] Lockout expires after 15 min; correct code accepted.
- [ ] Operator/fee collector login flow unchanged (no `/auth/2fa/verify` redirect when `TOTP_REQUIRE_ROLES=""`).
- [ ] Admin who has not enrolled can still log in normally (Phase 1 = optional).
- [ ] Super-admin can reset another admin's 2FA via `POST /api/admin/users/2fa-reset`. The target's next login has 2FA disabled. Audit log shows `2fa.admin_reset` with actor and target.
- [ ] No row in `audit_log` contains a TOTP secret or a plaintext backup code (grep test).

### E.3 Phase 2 readiness

- [ ] Set `TOTP_REQUIRE_ROLES=admin` on staging. Admin login without enrollment redirects to `/auth/2fa/setup` (forced).
- [ ] Forced-setup pending session cannot reach any other admin URL.
- [ ] After confirmation, full session granted normally.

### E.4 Render-specific

- [ ] `TOTP_ENCRYPTION_KEY` missing → server logs a clear startup error and runs in `TOTP_ENABLED=0` mode (do not silently boot with broken 2FA).
- [ ] `TOTP_ENABLED=0` redeployed → enrolled users log in with password only (kill-switch verified).
- [ ] SQLite file is on Render persistent disk (`ls -la /var/data/db.sqlite` from Render shell).
- [ ] After redeploy, enrolled rows still exist (`SELECT COUNT(*) FROM user_totp WHERE enabled=1`).

---

## F. Risks & Mitigations (delta from feasibility report — patch-specific)

| Risk | Mitigation in this patch |
|---|---|
| `import totp_auth` fails on Render due to missing dep | Fail-soft import (Patch #2). Server boots; 2FA is treated as unavailable; existing logins continue. |
| `schema/totp.sql` fails to apply | Wrapped in try/except (Patch #1). The rest of `init_db()` continues. |
| Pending session leaked into a route we forgot to gate | The single insert in `require_auth` (Patch #4) is the chokepoint — every existing `require_auth()` site benefits without modification. The only protected calls that bypass `require_auth` would be ones that were never gated to begin with — those are public routes and are out of scope by design. |
| Admin types code into wrong field, ends up in lockout loop | Backup codes shown once at enrollment; super-admin reset via env-var allowlist, not requiring DB shell. |
| TOTP secret ever logged | `totp_auth.audit()` writes only the event name and user. The secret is never passed to `print`, `logging`, or `audit_log`. Add a CI grep as a guardrail: `! grep -nE "secret_encrypted|decrypt_secret\\(" server.py`. |
| Encryption key lost on Render | Backed up in password manager + sealed envelope. Documented in this file. |
| Session cookie not `Secure` on plain HTTP local dev | Added conditionally (`'; Secure' if scheme=='https' else ''`) so local dev still works without TLS. |
| `LOGIN_ATTEMPTS` dict (line 21661) and `auth_2fa_attempts` table grow unbounded | The dict is per-IP and self-rotating; the table is small (one row per attempt) — daily cleanup recommended but not required. |

---

## G. Final Recommendation

Apply Phase 0 today: create the two new files (already done in this workspace) and add the single `executescript` line to `init_db()`. This is fully dormant and reversible — the schema change is a no-op if you never wire the rest in.

When you have a 30-minute uninterrupted window for Phase 1, apply Patches #2–#7 and the `requirements.txt` change in a single PR, deploy to a Render staging service first, walk through §D.3 end-to-end as the only enrolled user, and only then promote to production with `TOTP_REQUIRE_ROLES` left empty for a week.

Phase 2 is a one-line env-var change once Phase 1 has been quiet for at least a week.

---

*End of plan. Files created in this workspace alongside this document: `schema/totp.sql`, `totp_auth.py`.*
