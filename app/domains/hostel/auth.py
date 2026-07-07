"""Hostel partner module — partner authentication.

Deliberately isolated from staff auth: partner users live in
hostel_partner_users (PBKDF2-hashed passwords), sessions live in a
module-private dict under its own lock, and the browser cookie is
`hostel_session` — a partner session can never satisfy the staff
require_auth() gate, and a staff session can never satisfy this one.
"""
import secrets
import threading
import time
from http.cookies import SimpleCookie

from . import core
from .audit import write_audit

SESSION_TTL_SECONDS = 12 * 3600
COOKIE_NAME = 'hostel_session'

_SESSIONS = {}
_SESSIONS_LOCK = threading.Lock()

# Per (ip, username) lockout: 5 failures -> 300 s, mirrors staff LOGIN_ATTEMPTS.
_LOGIN_ATTEMPTS = {}
_LOGIN_LOCK = threading.Lock()
_MAX_FAILURES = 5
_LOCKOUT_SECONDS = 300


def _client_ip(handler):
    try:
        return handler.client_address[0]
    except Exception:
        return ''


def _attempt_key(ip, username):
    return f'{ip}|{(username or "").strip().lower()}'


def _is_locked(ip, username):
    with _LOGIN_LOCK:
        rec = _LOGIN_ATTEMPTS.get(_attempt_key(ip, username))
        if not rec:
            return False
        count, first_ts = rec
        if count < _MAX_FAILURES:
            return False
        if time.time() - first_ts > _LOCKOUT_SECONDS:
            _LOGIN_ATTEMPTS.pop(_attempt_key(ip, username), None)
            return False
        return True


def _record_failure(ip, username):
    key = _attempt_key(ip, username)
    with _LOGIN_LOCK:
        count, first_ts = _LOGIN_ATTEMPTS.get(key, (0, time.time()))
        if time.time() - first_ts > _LOCKOUT_SECONDS:
            count, first_ts = 0, time.time()
        _LOGIN_ATTEMPTS[key] = (count + 1, first_ts)


def _record_success(ip, username):
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(_attempt_key(ip, username), None)


def _session_token_from_headers(handler):
    raw = handler.headers.get('Cookie') or ''
    if not raw:
        return ''
    try:
        cookie = SimpleCookie()
        cookie.load(raw)
        morsel = cookie.get(COOKIE_NAME)
        return morsel.value if morsel else ''
    except Exception:
        return ''


def get_partner_session(handler):
    """Return the live partner session dict or None. Never consults staff SESSIONS."""
    token = _session_token_from_headers(handler)
    if not token:
        return None
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(token)
        if not session:
            return None
        if session['expires'] < time.time():
            _SESSIONS.pop(token, None)
            return None
        return dict(session)


def require_partner_api(handler):
    """Guard for /api/hostel/* JSON endpoints: 401 JSON when not signed in."""
    session = get_partner_session(handler)
    if not session:
        handler.send_json({'success': False, 'error': 'Not signed in', 'redirect_url': '/hostel/login'}, 401)
        return None
    return session


def require_partner_page(handler):
    """Guard for /hostel/* HTML pages: redirect to the partner login."""
    session = get_partner_session(handler)
    if not session:
        handler.send_redirect('/hostel/login')
        return None
    return session


def login(handler, data):
    """POST /api/hostel/login — authenticate a hostel partner user."""
    username = core.clean_text(data.get('username'), 120)
    password = str(data.get('password') or '')
    ip = _client_ip(handler)
    db = core.get_db()
    try:
        if not username or not password:
            return {'success': False, 'error': 'Username and password are required.'}, 400
        if _is_locked(ip, username):
            write_audit(db, 'partner_user', 0, 'partner_login_locked', actor=username,
                        actor_type='PARTNER', note='Login attempt while locked out', ip=ip)
            db.commit()
            return {'success': False, 'error': 'Too many failed attempts. Try again in a few minutes.'}, 429

        row = db.execute(
            """SELECT u.*, p.partner_name, p.display_name, p.status AS partner_status,
                      p.can_mark_arrival
               FROM hostel_partner_users u
               JOIN hostel_partners p ON p.id = u.partner_id
               WHERE LOWER(u.username) = LOWER(?)""",
            [username],
        ).fetchone()
        verify = core.dep('verify_password')
        ok = bool(row) and verify(password, row['password_salt'], row['password_hash'])
        if not ok or row['status'] != 'ACTIVE' or row['partner_status'] != 'ACTIVE':
            _record_failure(ip, username)
            reason = 'bad credentials'
            if row and row['status'] != 'ACTIVE':
                reason = 'user disabled'
            elif row and row['partner_status'] != 'ACTIVE':
                reason = 'partner not active'
            write_audit(db, 'partner_user', row['id'] if row else 0, 'partner_login_failed',
                        actor=username, actor_type='PARTNER',
                        partner_id=row['partner_id'] if row else 0, note=reason, ip=ip)
            db.commit()
            return {'success': False, 'error': 'Invalid username or password.'}, 401

        _record_success(ip, username)
        token = secrets.token_hex(32)
        session = {
            'partner_user_id': int(row['id']),
            'partner_id': int(row['partner_id']),
            'username': row['username'],
            'full_name': row['full_name'] or row['username'],
            'partner_name': row['display_name'] or row['partner_name'],
            'can_mark_arrival': int(row['can_mark_arrival'] or 0),
            'expires': time.time() + SESSION_TTL_SECONDS,
        }
        with _SESSIONS_LOCK:
            _SESSIONS[token] = session
        db.execute('UPDATE hostel_partner_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?', [row['id']])
        write_audit(db, 'partner_user', row['id'], 'partner_login_success', actor=row['username'],
                    actor_type='PARTNER', partner_id=row['partner_id'], ip=ip)
        db.commit()
        cookie = f'{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SECONDS}'
        return {
            'success': True,
            'partner_name': session['partner_name'],
            'full_name': session['full_name'],
            'redirect_url': '/hostel/dashboard',
            '_set_cookie': cookie,
        }, 200
    finally:
        db.close()


def logout(handler):
    token = _session_token_from_headers(handler)
    session = None
    if token:
        with _SESSIONS_LOCK:
            session = _SESSIONS.pop(token, None)
    if session:
        db = core.get_db()
        try:
            write_audit(db, 'partner_user', session.get('partner_user_id') or 0, 'partner_logout',
                        actor=session.get('username') or '', actor_type='PARTNER',
                        partner_id=session.get('partner_id') or 0, ip=_client_ip(handler))
            db.commit()
        finally:
            db.close()
    cookie = f'{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
    return {'success': True, 'redirect_url': '/hostel/login', '_set_cookie': cookie}, 200
