"""Website Advertisements module — shared core: injected deps, constants, helpers.

Pure Python with no import-time side effects. server.py calls configure(...)
once at startup to inject the helpers the module needs, so the module never
imports server.py.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

_DEPS = {}


def configure(**kwargs):
    """Called once from server.py with the shared helpers this module uses."""
    _DEPS.update(kwargs)
    data_root = kwargs.get('data_root')
    if data_root:
        global UPLOAD_DIR
        UPLOAD_DIR = Path(data_root) / 'ad_uploads'
    project_root = kwargs.get('project_root')
    if project_root:
        global PROJECT_ROOT
        PROJECT_ROOT = Path(project_root)


def dep(name):
    fn = _DEPS.get(name)
    if fn is None:
        raise RuntimeError(f'ads module dependency not configured: {name}')
    return fn


def get_db():
    return dep('get_db')()


# Resolved by configure(); defaults keep local tooling working.
UPLOAD_DIR = Path(__file__).resolve().parents[3] / 'ad_uploads'
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ── Constants ────────────────────────────────────────────────────
# Stored statuses reflect admin intent; SCHEDULED / EXPIRED are derived at
# read time from starts_at / ends_at (see effective_status in service.py).
STATUSES = ('DRAFT', 'ACTIVE', 'PAUSED', 'ARCHIVED')
DISPLAY_FREQUENCIES = ('once_per_version', 'once_per_session', 'every_visit')
DEFAULT_FREQUENCY = 'once_per_version'
DEFAULT_DISMISSAL_HOURS = 168  # 7 days
MAX_DISMISSAL_HOURS = 8760     # 1 year
DISCLOSURE_LABELS = ('Announcement', 'Advertisement', 'Campaign',
                     'Public Awareness', 'Embassy Initiative')
LANGUAGES = ('en', 'en+ur')
IMAGE_SLOTS = ('popup', 'popup_mobile', 'banner', 'banner_mobile')
SLOT_COLUMNS = {
    'popup': 'popup_image',
    'popup_mobile': 'popup_mobile_image',
    'banner': 'banner_image',
    'banner_mobile': 'banner_mobile_image',
}

# Image upload limits (owner-approved v1 values).
MAX_IMAGE_BYTES = 4 * 1024 * 1024   # 4 MB
MAX_IMAGE_DIMENSION = 4000          # px, each side
MIN_IMAGE_WIDTH = 400               # px
MAX_IMAGE_PIXELS = 16_000_000       # decompression-bomb guard (checked pre-decode)

# Strictly admin-only management (owner decision #1). Enforced in-handler
# even though route-level RBAC would also admit operator roles.
MANAGE_ROLES = {'admin'}


def user_can_manage(user):
    return bool(user) and (user.get('role') or '').strip() in MANAGE_ROLES


# ── Public origin (cross-origin media URLs) ──────────────────────
# The React site on cwakuwait.com is a different origin from this backend, so
# media URLs it receives must be absolute. Read at call time (not import time)
# so the value can be changed/tested without reimporting the module.

def public_backend_origin():
    """Normalised 'scheme://host[:port]' from PUBLIC_BACKEND_ORIGIN, or ''.

    Returns '' when unset or unusable, which makes callers fall back to
    backend-relative URLs — the pre-existing same-origin behaviour.
    """
    raw = str(os.environ.get('PUBLIC_BACKEND_ORIGIN') or '').strip().rstrip('/')
    if not raw:
        return ''
    try:
        parsed = urlparse(raw)
    except Exception:
        return ''
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'


def public_base_path():
    """Mount prefix from PUBLIC_BASE_PATH env, normalised to '' or '/prefix'.

    Deliberately env-only. The request-scoped equivalent in server.py also
    honours the X-Forwarded-Prefix / X-Script-Name request headers, which must
    not influence a response served with 'Cache-Control: public' — a client
    could otherwise vary a cacheable body via a request header.
    """
    raw = str(os.environ.get('PUBLIC_BASE_PATH') or '').strip()
    if not raw or raw == '/':
        return ''
    if '://' in raw:
        try:
            raw = urlparse(raw).path or ''
        except Exception:
            raw = ''
    raw = '/' + raw.strip('/')
    return '' if raw == '/' else raw


def public_media_base():
    """Prefix for media URLs handed to cross-origin consumers.

    Origin and mount prefix both come from the environment, never from the
    request, so the public payload is identical for every caller and safe to
    cache. Degrades to a relative path when PUBLIC_BACKEND_ORIGIN is unset
    rather than emitting a broken host.
    """
    return f'{public_backend_origin()}{public_base_path()}'


# ── Timezone (owner decision #10) ────────────────────────────────
# Kuwait is fixed UTC+3 all year (no DST). Admins enter and view times in
# Asia/Kuwait; the database stores naive UTC 'YYYY-MM-DD HH:MM:SS' strings,
# matching SQLite CURRENT_TIMESTAMP. This is the single conversion utility —
# do not scatter manual offset arithmetic elsewhere.
KUWAIT_UTC_OFFSET = timedelta(hours=3)
_UTC_FMT = '%Y-%m-%d %H:%M:%S'


def utc_now_str():
    from datetime import timezone
    return datetime.now(timezone.utc).strftime(_UTC_FMT)


def kuwait_input_to_utc(value):
    """Kuwait-local input ('YYYY-MM-DDTHH:MM[:SS]' or with space) -> UTC string.

    Returns '' for empty input, None for unparseable input.
    """
    s = str(value or '').strip().replace('T', ' ')[:19]
    if not s:
        return ''
    for fmt in (_UTC_FMT, '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    else:
        return None
    return (dt - KUWAIT_UTC_OFFSET).strftime(_UTC_FMT)


def utc_to_kuwait_input(value):
    """UTC 'YYYY-MM-DD HH:MM:SS' -> 'YYYY-MM-DDTHH:MM' for datetime-local inputs."""
    s = str(value or '').strip()
    if not s:
        return ''
    try:
        dt = datetime.strptime(s[:19], _UTC_FMT)
    except ValueError:
        try:
            dt = datetime.strptime(s[:16], '%Y-%m-%d %H:%M')
        except ValueError:
            return ''
    return (dt + KUWAIT_UTC_OFFSET).strftime('%Y-%m-%dT%H:%M')


def utc_to_kuwait_display(value):
    """UTC 'YYYY-MM-DD HH:MM:SS' -> 'YYYY-MM-DD HH:MM (Kuwait)' for listings."""
    s = str(value or '').strip()
    if not s:
        return ''
    try:
        dt = datetime.strptime(s[:19], _UTC_FMT)
    except ValueError:
        return s
    return (dt + KUWAIT_UTC_OFFSET).strftime('%Y-%m-%d %H:%M')


# ── Input validation helpers ─────────────────────────────────────

def clean_text(value, max_len=2000):
    return str(value or '').strip()[:max_len]


def clean_phone(value):
    """Return (clean, error). Digits, +, -, (), spaces; 5-30 chars or empty."""
    s = str(value or '').strip()
    if not s:
        return '', None
    if len(s) > 30 or not all(c.isdigit() or c in '+-() ' for c in s):
        return '', 'Contact number may only contain digits, +, -, ( ) and spaces (max 30).'
    if sum(1 for c in s if c.isdigit()) < 5:
        return '', 'Contact number must contain at least 5 digits.'
    return s, None


def validate_public_url(value, field='Link'):
    """Validate a public click-through URL (owner decision #9).

    Allowed: empty, internal relative path starting with a single '/', or an
    absolute https:// URL. Rejected: javascript:, data:, plain http:,
    protocol-relative //, embedded credentials, control characters,
    HTML-significant characters, malformed URLs.
    Returns (clean_value, error).
    """
    s = str(value or '').strip()
    if not s:
        return '', None
    if len(s) > 500:
        return '', f'{field} is too long (max 500 characters).'
    if any(ord(c) < 33 for c in s) or any(c in s for c in '"\'<>`\\'):
        return '', f'{field} contains invalid characters.'
    if s.startswith('//'):
        return '', f'{field}: protocol-relative links are not allowed.'
    if s.startswith('/'):
        return s, None
    try:
        parsed = urlparse(s)
    except Exception:
        return '', f'{field} is not a valid URL.'
    scheme = (parsed.scheme or '').lower()
    if scheme != 'https':
        return '', f'{field}: only HTTPS links or internal paths starting with "/" are allowed.'
    if not parsed.hostname:
        return '', f'{field} is not a valid URL.'
    if parsed.username or parsed.password:
        return '', f'{field}: links with embedded credentials are not allowed.'
    return s, None
