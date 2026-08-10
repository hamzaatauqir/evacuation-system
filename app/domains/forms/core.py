"""Embassy Forms Library — shared core: injected deps, constants, helpers.

Pure Python with no import-time side effects. server.py calls configure(...)
once at startup to inject the helpers the module needs, so the module never
imports server.py (mirrors app/domains/ads/core.py).

Owner decisions locked 2026-08-10:
- PDF only for v1. No DOC/DOCX (ZIP container, weak content validation, poor
  mobile support, and the Embassy wants a fixed non-editable document).
- No permanent delete. ARCHIVED is terminal-but-reversible; nothing in this
  module removes a row or a file from disk.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

_DEPS = {}


def configure(**kwargs):
    """Called once from server.py with the shared helpers this module uses."""
    _DEPS.update(kwargs)
    data_root = kwargs.get('data_root')
    if data_root:
        global UPLOAD_DIR
        UPLOAD_DIR = Path(data_root) / 'embassy_forms'
    project_root = kwargs.get('project_root')
    if project_root:
        global PROJECT_ROOT
        PROJECT_ROOT = Path(project_root)


def dep(name):
    fn = _DEPS.get(name)
    if fn is None:
        raise RuntimeError(f'forms module dependency not configured: {name}')
    return fn


def get_db():
    return dep('get_db')()


# Resolved by configure(); defaults keep local tooling and unit tests working.
UPLOAD_DIR = Path(__file__).resolve().parents[3] / 'embassy_forms'
PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ── Constants ────────────────────────────────────────────────────
# DRAFT   — staff-only, never public, downloadable only via the staff preview.
# PUBLISHED — visible on /forms and downloadable by the public.
# ARCHIVED  — withdrawn from public view, retained for the record. Reversible
#             via restore; there is deliberately no hard-delete path.
STATUSES = ('DRAFT', 'PUBLISHED', 'ARCHIVED')
PUBLIC_STATUS = 'PUBLISHED'

LANGUAGES = ('en', 'ur', 'en+ur')
LANGUAGE_LABELS = {'en': 'English', 'ur': 'Urdu', 'en+ur': 'English/Urdu'}

# PDF only (owner decision). Extension AND magic bytes must agree — the strict
# ads/hostel policy, not the weaker extension-OR-magic used by the legacy
# note-verbal upload.
ALLOWED_EXTENSION = '.pdf'
ALLOWED_MIME = 'application/pdf'
MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB — matches the hostel module cap
                                    # and sits well under the 50 MB global
                                    # MAX_REQUEST_BODY_BYTES in server.py.

# Route-level RBAC in server.py cannot distinguish these roles: admin,
# operator and operator_special are all inside FULL_SYSTEM_ROLES and pass
# can_access_admin_route() unconditionally. The split below is therefore
# enforced in-handler, exactly as the ads module does.
MANAGE_ROLES = {'admin', 'operator'}   # upload, edit, replace, publish, reorder
ADMIN_ROLES = {'admin'}                # archive, restore, categories, audit
# operator_special is deliberately excluded: the dashboard already hides every
# [data-cwa-nav] community-portal button from that role.

# Seeded on first boot; admins may add, rename, reorder or deactivate rows.
# Categories are data, not an enum — the brief requires staff to manage the
# library without developer involvement, and a hard-coded list fails that on
# the first new consular category.
DEFAULT_CATEGORIES = (
    ('nadra', 'NADRA', 10),
    ('passport', 'Passport', 20),
    ('attestation', 'Attestation', 30),
    ('consular', 'Consular', 40),
    ('community-welfare', 'Community Welfare', 50),
    ('visa-travel', 'Visa / Travel', 60),
    ('other', 'Other', 70),
)

MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 600
MAX_VERSION_LABEL_LEN = 60
MAX_CATEGORY_LABEL_LEN = 60


def user_can_manage(user):
    """Day-to-day lifecycle: upload, edit, replace, publish/unpublish, reorder."""
    return bool(user) and (user.get('role') or '').strip() in MANAGE_ROLES


def user_is_admin(user):
    """Destructive or structural: archive/restore, categories, audit trail."""
    return bool(user) and (user.get('role') or '').strip() in ADMIN_ROLES


# ── Public origin (cross-origin download URLs) ───────────────────
# The React site on cwakuwait.com is a different origin from this backend, so
# download URLs it receives must be absolute. Read at call time (not import
# time) so the value can be changed/tested without reimporting the module.

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
    honours X-Forwarded-Prefix / X-Script-Name, which must not influence a
    response served with 'Cache-Control: public' — a client could otherwise
    vary a cacheable body via a request header.
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


def public_download_url(form_id):
    """Absolute (or relative, when unconfigured) download URL for a form.

    The path is stable across file replacements by design: citizens and staff
    may bookmark or print it, and replacing the PDF must not break the link.
    """
    return f'{public_backend_origin()}{public_base_path()}/forms/download/{int(form_id or 0)}'


# ── Time helpers ─────────────────────────────────────────────────
# Kuwait is fixed UTC+3 all year (no DST). The database stores naive UTC
# 'YYYY-MM-DD HH:MM:SS' strings, matching SQLite CURRENT_TIMESTAMP. Shared
# converter, same convention as ads/core.py — do not scatter offset arithmetic.
KUWAIT_UTC_OFFSET = timedelta(hours=3)
_UTC_FMT = '%Y-%m-%d %H:%M:%S'
_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def utc_now_str():
    return datetime.now(timezone.utc).strftime(_UTC_FMT)


def utc_to_kuwait_display(value):
    """UTC 'YYYY-MM-DD HH:MM:SS' -> 'YYYY-MM-DD HH:MM' in Kuwait local time."""
    s = str(value or '').strip()
    if not s:
        return ''
    try:
        dt = datetime.strptime(s[:19], _UTC_FMT)
    except ValueError:
        return s
    return (dt + KUWAIT_UTC_OFFSET).strftime('%Y-%m-%d %H:%M')


def display_date(value):
    """'YYYY-MM-DD[ HH:MM:SS]' -> '10 Aug 2026'. Returns '' when unparseable.

    Used for the citizen-facing 'Updated' line, where an ISO timestamp reads as
    machine output. Kuwait-local, consistent with utc_to_kuwait_display.
    """
    s = str(value or '').strip()
    if not s:
        return ''
    try:
        if len(s) >= 19:
            dt = datetime.strptime(s[:19], _UTC_FMT) + KUWAIT_UTC_OFFSET
        else:
            dt = datetime.strptime(s[:10], '%Y-%m-%d')
    except ValueError:
        return ''
    return f'{dt.day} {_MONTHS[dt.month - 1]} {dt.year}'


def human_file_size(num_bytes):
    """Byte count -> '240 KB' / '1.4 MB'. Shown to citizens on mobile data."""
    try:
        size = int(num_bytes or 0)
    except (TypeError, ValueError):
        return ''
    if size <= 0:
        return ''
    if size < 1024:
        return f'{size} B'
    kb = size / 1024.0
    if kb < 1024:
        return f'{int(round(kb))} KB'
    return f'{kb / 1024.0:.1f} MB'


# ── Input validation helpers ─────────────────────────────────────

_SLUG_RE = re.compile(r'[^a-z0-9]+')
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def clean_text(value, max_len=2000):
    return str(value or '').strip()[:max_len]


def clean_slug(value, max_len=40):
    """Free text -> 'community-welfare'. Returns '' when nothing usable remains."""
    slug = _SLUG_RE.sub('-', str(value or '').strip().lower()).strip('-')
    return slug[:max_len].strip('-')


def validate_date(value, field='Date'):
    """Validate an optional 'YYYY-MM-DD' date. Returns (clean, error)."""
    s = str(value or '').strip()[:10]
    if not s:
        return '', None
    if not _DATE_RE.match(s):
        return '', f'{field} must be in YYYY-MM-DD format.'
    try:
        datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        return '', f'{field} is not a real calendar date.'
    return s, None


def normalize_status(value):
    s = str(value or '').strip().upper()
    return s if s in STATUSES else ''


def normalize_language(value):
    s = str(value or '').strip().lower()
    return s if s in LANGUAGES else 'en'
