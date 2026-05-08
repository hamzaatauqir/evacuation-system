"""
TOTP 2FA helpers for the Embassy / Community Welfare Portal.

Self-contained module. Imported defensively from server.py — if pyotp /
qrcode / cryptography are not installed, server.py treats 2FA as
disabled and continues to operate exactly as it did before.

Environment variables consumed:
  TOTP_ENABLED              "1" (default) or "0" — master kill-switch.
  TOTP_ENCRYPTION_KEY       Fernet key. Required when TOTP_ENABLED=1.
                            Generate once with:
                              python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  TOTP_ISSUER_NAME          Shown in authenticator app. Default "Embassy Portal".
  TOTP_REQUIRE_ROLES        CSV of roles that MUST use 2FA. Default "".
  TOTP_SUPER_ADMINS         CSV of usernames allowed to reset another user's 2FA.
                            Default {"admin"}.
  TOTP_PENDING_TTL_SECONDS  Pending-session lifetime. Default 600 (10 min).

DB tables (see schema/totp.sql):
  user_totp           — per-user secret, state, replay counter
  user_backup_codes   — 10 single-use recovery codes per user
  auth_2fa_attempts   — verification attempt log (rate limit + forensics)

Audit events written into existing audit_log:
  2fa.enroll.start, 2fa.enroll.confirm,
  2fa.verify.success, 2fa.verify.fail,
  2fa.backup_code.used, 2fa.backup_codes.regenerated,
  2fa.lockout, 2fa.admin_reset.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

# --- Soft imports so server.py can fail-soft if deps are missing -----------
try:
    import pyotp  # type: ignore
except Exception as _e:  # pragma: no cover
    pyotp = None  # type: ignore
    _import_error_pyotp = _e
else:
    _import_error_pyotp = None

try:
    import qrcode  # type: ignore
    from qrcode.image.pil import PilImage  # type: ignore
except Exception as _e:  # pragma: no cover
    qrcode = None  # type: ignore
    PilImage = None  # type: ignore
    _import_error_qrcode = _e
else:
    _import_error_qrcode = None

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except Exception as _e:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _import_error_cryptography = _e
else:
    _import_error_cryptography = None


# ──────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────
VALID_WINDOW = 1            # ±30s
MAX_FAILED_ATTEMPTS = 5     # before per-user/IP lockout
LOCKOUT_WINDOW_MIN = 15     # rolling window
BACKUP_CODE_COUNT = 10
BACKUP_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # ambiguity-free


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def is_enabled() -> bool:
    """Master kill-switch — returns False if any required dep is missing."""
    if str(os.environ.get('TOTP_ENABLED', '1')).strip().lower() in ('0', 'false', 'no', 'off'):
        return False
    if pyotp is None or Fernet is None:
        # No deps → behave as disabled. server.py logs the import error once.
        return False
    return True


def get_required_roles() -> set:
    raw = os.environ.get('TOTP_REQUIRE_ROLES', '') or ''
    return {r.strip() for r in raw.split(',') if r.strip()}


def get_super_admins() -> set:
    raw = os.environ.get('TOTP_SUPER_ADMINS', '') or ''
    out = {u.strip() for u in raw.split(',') if u.strip()}
    return out or {'admin'}


def _issuer() -> str:
    return os.environ.get('TOTP_ISSUER_NAME', 'Embassy Portal')


# ──────────────────────────────────────────────────────────────────────────
# Encryption (Fernet)
# ──────────────────────────────────────────────────────────────────────────
_FERNET_CACHE = {'inst': None}

def _fernet():
    if _FERNET_CACHE['inst'] is not None:
        return _FERNET_CACHE['inst']
    if Fernet is None:
        raise RuntimeError('cryptography.Fernet not available')
    key = os.environ.get('TOTP_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError(
            'TOTP_ENCRYPTION_KEY env var is required when TOTP_ENABLED=1. '
            'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    _FERNET_CACHE['inst'] = Fernet(key.encode() if isinstance(key, str) else key)
    return _FERNET_CACHE['inst']


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode('utf-8')).decode('utf-8')


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except InvalidToken as e:
        raise RuntimeError('TOTP secret could not be decrypted (key mismatch?)') from e


# ──────────────────────────────────────────────────────────────────────────
# Secret + URI + QR
# ──────────────────────────────────────────────────────────────────────────
def generate_secret() -> str:
    if pyotp is None:
        raise RuntimeError('pyotp not available')
    # 160-bit secret, base32 encoded — RFC 4226 recommended length
    return pyotp.random_base32(length=32)


def build_otpauth_uri(username: str, secret: str) -> str:
    if pyotp is None:
        raise RuntimeError('pyotp not available')
    issuer = _issuer()
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name=issuer,
    )


def render_qr_png_data_uri(otpauth_uri: str) -> str:
    """Renders a PNG QR as a data: URI (no file ever written to disk)."""
    if qrcode is None:
        raise RuntimeError('qrcode not available')
    img = qrcode.make(otpauth_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


# ──────────────────────────────────────────────────────────────────────────
# Verification (with replay protection)
# ──────────────────────────────────────────────────────────────────────────
def _current_step(period: int = 30) -> int:
    return int(time.time()) // period


def verify_totp(secret: str, code: str, last_counter):
    """
    Returns (ok, new_counter).
    ok=True only if the code is valid AND the step has not been used before.
    """
    if pyotp is None:
        return (False, last_counter)
    code = (code or '').strip().replace(' ', '')
    if not code.isdigit() or len(code) != 6:
        return (False, last_counter)
    totp = pyotp.TOTP(secret)
    now_step = _current_step()
    for offset in range(-VALID_WINDOW, VALID_WINDOW + 1):
        step = now_step + offset
        if last_counter is not None and step <= int(last_counter):
            continue  # replay
        expected = totp.at(for_time=step * 30)
        if hmac.compare_digest(expected, code):
            return (True, step)
    return (False, last_counter)


# ──────────────────────────────────────────────────────────────────────────
# Backup codes
# ──────────────────────────────────────────────────────────────────────────
def _generate_one_backup_code() -> str:
    chars = ''.join(secrets.choice(BACKUP_CODE_ALPHABET) for _ in range(8))
    return f'{chars[:4]}-{chars[4:]}'


def generate_backup_codes(n: int = BACKUP_CODE_COUNT) -> list:
    return [_generate_one_backup_code() for _ in range(n)]


def hash_backup_code(user_id: int, code: str) -> str:
    canon = (code or '').strip().upper().replace('-', '')
    payload = f'{int(user_id)}:{canon}'.encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def consume_backup_code(db, user_id: int, code: str) -> bool:
    """Returns True iff the code was valid and unused. Marks it used atomically."""
    h = hash_backup_code(user_id, code)
    row = db.execute(
        "SELECT id, used_at FROM user_backup_codes WHERE user_id = ? AND code_hash = ?",
        [user_id, h],
    ).fetchone()
    if not row:
        return False
    if row['used_at']:
        return False
    db.execute(
        "UPDATE user_backup_codes SET used_at = ? WHERE id = ? AND used_at IS NULL",
        [_utcnow_iso(), row['id']],
    )
    db.commit()
    return True


# ──────────────────────────────────────────────────────────────────────────
# Rate limiting
# ──────────────────────────────────────────────────────────────────────────
def is_2fa_locked(db, user_id, ip: str) -> bool:
    """Per-user OR per-IP rolling-window failure cap."""
    if user_id is None:
        return False
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_WINDOW_MIN)).isoformat(timespec='seconds')
    user_fails = db.execute(
        "SELECT COUNT(*) AS n FROM auth_2fa_attempts "
        "WHERE user_id = ? AND success = 0 AND attempted_at > ?",
        [user_id, cutoff],
    ).fetchone()['n']
    if user_fails >= MAX_FAILED_ATTEMPTS:
        return True
    if ip:
        ip_fails = db.execute(
            "SELECT COUNT(*) AS n FROM auth_2fa_attempts "
            "WHERE ip = ? AND success = 0 AND attempted_at > ?",
            [ip, cutoff],
        ).fetchone()['n']
        if ip_fails >= MAX_FAILED_ATTEMPTS * 6:  # generous global per-IP
            return True
    return False


def record_attempt(db, user_id, ip: str, success: bool) -> None:
    db.execute(
        "INSERT INTO auth_2fa_attempts (user_id, ip, success, attempted_at) VALUES (?, ?, ?, ?)",
        [user_id, ip or '', 1 if success else 0, _utcnow_iso()],
    )
    db.commit()


# ──────────────────────────────────────────────────────────────────────────
# Audit (writes into the existing audit_log table)
# ──────────────────────────────────────────────────────────────────────────
def audit(db, username: str, event: str, details=None) -> None:
    try:
        payload = json.dumps(details or {}, default=str)
    except Exception:
        payload = '{}'
    try:
        db.execute(
            "INSERT INTO audit_log (action, user, details) VALUES (?, ?, ?)",
            [f'2fa.{event}', username or '', payload],
        )
        db.commit()
    except Exception as e:
        # Never let an audit failure mask the user-facing flow.
        print(f'[totp] audit write failed: {e}', flush=True)


# ──────────────────────────────────────────────────────────────────────────
# High-level flows used by server.py
# ──────────────────────────────────────────────────────────────────────────
def enroll_start(db, user_id: int, username: str) -> dict:
    """
    Generate (or rotate, if not yet confirmed) a secret and return everything
    the setup page needs to render. Does NOT enable 2FA — that happens only
    after enroll_confirm().
    """
    secret = generate_secret()
    enc = encrypt_secret(secret)
    existing = db.execute(
        "SELECT user_id, enabled FROM user_totp WHERE user_id = ?", [user_id]
    ).fetchone()
    if existing and existing['enabled']:
        # Already enrolled — caller should redirect to security settings.
        return {'already_enrolled': True}
    if existing:
        db.execute(
            "UPDATE user_totp SET secret_encrypted = ?, enabled = 0, confirmed_at = NULL, "
            "last_used_at = NULL, last_used_counter = NULL, failed_attempts = 0, locked_until = NULL "
            "WHERE user_id = ?",
            [enc, user_id],
        )
    else:
        db.execute(
            "INSERT INTO user_totp (user_id, secret_encrypted, enabled, created_at) VALUES (?, ?, 0, ?)",
            [user_id, enc, _utcnow_iso()],
        )
    db.commit()
    audit(db, username, 'enroll.start', {'user_id': user_id})
    uri = build_otpauth_uri(username, secret)
    return {
        'already_enrolled': False,
        'secret_plain': secret,    # shown to user once for manual entry fallback
        'otpauth_uri': uri,
        'qr_data_uri': render_qr_png_data_uri(uri),
        'issuer': _issuer(),
    }


def enroll_confirm(db, user_id: int, code: str) -> dict:
    """
    Verify the first code against the just-stored secret. On success, flip
    enabled=1, generate 10 backup codes, and return the plaintext codes
    (caller MUST show them to the user exactly once and never store them).
    """
    row = db.execute(
        "SELECT secret_encrypted, enabled FROM user_totp WHERE user_id = ?", [user_id]
    ).fetchone()
    if not row:
        return {'ok': False, 'error': 'no_pending_enrollment'}
    if row['enabled']:
        return {'ok': False, 'error': 'already_enrolled'}
    secret = decrypt_secret(row['secret_encrypted'])
    ok, new_counter = verify_totp(secret, code, last_counter=None)
    if not ok:
        return {'ok': False, 'error': 'invalid_code'}
    db.execute(
        "UPDATE user_totp SET enabled = 1, confirmed_at = ?, last_used_counter = ?, last_used_at = ? "
        "WHERE user_id = ?",
        [_utcnow_iso(), new_counter, _utcnow_iso(), user_id],
    )
    # Backup codes (regenerate from clean state).
    db.execute("DELETE FROM user_backup_codes WHERE user_id = ?", [user_id])
    plain_codes = generate_backup_codes()
    for code_plain in plain_codes:
        db.execute(
            "INSERT INTO user_backup_codes (user_id, code_hash, created_at) VALUES (?, ?, ?)",
            [user_id, hash_backup_code(user_id, code_plain), _utcnow_iso()],
        )
    db.commit()
    username = (db.execute("SELECT username FROM users WHERE id = ?", [user_id]).fetchone() or {}).get('username') or ''
    audit(db, username, 'enroll.confirm', {'user_id': user_id})
    audit(db, username, 'backup_codes.generated', {'user_id': user_id, 'count': len(plain_codes)})
    return {'ok': True, 'backup_codes': plain_codes}


def verify_for_login(db, user_id, code: str, ip: str) -> bool:
    """
    Accepts either a 6-digit TOTP code or an 8-char (XXXX-XXXX) backup code.
    Records the attempt, updates replay counter on success, and audits.
    """
    if user_id is None:
        return False
    cleaned = (code or '').strip()
    is_backup = ('-' in cleaned) or (len(cleaned.replace('-', '')) == 8 and not cleaned.isdigit())
    row = db.execute(
        "SELECT secret_encrypted, last_used_counter FROM user_totp WHERE user_id = ? AND enabled = 1",
        [user_id],
    ).fetchone()
    if not row:
        record_attempt(db, user_id, ip, False)
        return False

    username = (db.execute("SELECT username FROM users WHERE id = ?", [user_id]).fetchone() or {}).get('username') or ''

    if is_backup:
        ok = consume_backup_code(db, user_id, cleaned)
        record_attempt(db, user_id, ip, ok)
        audit(db, username, 'verify.success' if ok else 'verify.fail',
              {'user_id': user_id, 'method': 'backup_code', 'ip': ip})
        if ok:
            audit(db, username, 'backup_code.used', {'user_id': user_id, 'ip': ip})
            db.execute(
                "UPDATE user_totp SET last_used_at = ? WHERE user_id = ?",
                [_utcnow_iso(), user_id],
            )
            db.commit()
        return ok

    secret = decrypt_secret(row['secret_encrypted'])
    ok, new_counter = verify_totp(secret, cleaned, row['last_used_counter'])
    record_attempt(db, user_id, ip, ok)
    audit(db, username, 'verify.success' if ok else 'verify.fail',
          {'user_id': user_id, 'method': 'totp', 'ip': ip})
    if ok:
        db.execute(
            "UPDATE user_totp SET last_used_counter = ?, last_used_at = ? WHERE user_id = ?",
            [new_counter, _utcnow_iso(), user_id],
        )
        db.commit()
    return ok


def admin_reset(db, target_user_id: int, actor_username: str) -> bool:
    """Disable the target user's 2FA and clear backup codes. Forces re-enroll on next login."""
    row = db.execute("SELECT user_id FROM user_totp WHERE user_id = ?", [target_user_id]).fetchone()
    if row:
        db.execute(
            "UPDATE user_totp SET enabled = 0, confirmed_at = NULL, last_used_at = NULL, "
            "last_used_counter = NULL, failed_attempts = 0, locked_until = NULL "
            "WHERE user_id = ?",
            [target_user_id],
        )
    db.execute("DELETE FROM user_backup_codes WHERE user_id = ?", [target_user_id])
    db.commit()
    target_username = (db.execute("SELECT username FROM users WHERE id = ?", [target_user_id]).fetchone() or {}).get('username') or ''
    audit(db, actor_username, 'admin_reset',
          {'target_user_id': target_user_id, 'target_username': target_username})
    return True


def regenerate_backup_codes(db, user_id: int) -> list:
    """Returns the 10 new plaintext codes; previous codes are invalidated."""
    db.execute("DELETE FROM user_backup_codes WHERE user_id = ?", [user_id])
    plain_codes = generate_backup_codes()
    for code_plain in plain_codes:
        db.execute(
            "INSERT INTO user_backup_codes (user_id, code_hash, created_at) VALUES (?, ?, ?)",
            [user_id, hash_backup_code(user_id, code_plain), _utcnow_iso()],
        )
    db.commit()
    username = (db.execute("SELECT username FROM users WHERE id = ?", [user_id]).fetchone() or {}).get('username') or ''
    audit(db, username, 'backup_codes.regenerated', {'user_id': user_id})
    return plain_codes


# ──────────────────────────────────────────────────────────────────────────
# Diagnostics (safe for ops to call)
# ──────────────────────────────────────────────────────────────────────────
def diagnose() -> dict:
    return {
        'enabled': is_enabled(),
        'pyotp_available': pyotp is not None,
        'qrcode_available': qrcode is not None,
        'cryptography_available': Fernet is not None,
        'encryption_key_set': bool(os.environ.get('TOTP_ENCRYPTION_KEY')),
        'required_roles': sorted(get_required_roles()),
        'super_admins': sorted(get_super_admins()),
        'issuer': _issuer(),
    }
