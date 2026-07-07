"""Hostel partner module — shared core: injected dependencies, constants, helpers.

This module is pure Python with no import-time side effects. server.py calls
configure(...) once at startup to inject the helpers the module needs, so the
module never imports server.py (which would re-execute the monolith).
"""
from datetime import datetime
from pathlib import Path

_DEPS = {}


def configure(**kwargs):
    """Called once from server.py with the shared helpers this module uses."""
    _DEPS.update(kwargs)
    data_root = kwargs.get('data_root')
    if data_root:
        global UPLOAD_DIR
        UPLOAD_DIR = Path(data_root) / 'hostel_agreement_uploads'


def dep(name):
    fn = _DEPS.get(name)
    if fn is None:
        raise RuntimeError(f'hostel module dependency not configured: {name}')
    return fn


def get_db():
    return dep('get_db')()


# Resolved by configure(); default keeps local tooling working.
UPLOAD_DIR = Path(__file__).resolve().parents[3] / 'hostel_agreement_uploads'

# ── Constants ────────────────────────────────────────────────────
PARTNER_STATUS_ACTIVE = 'ACTIVE'
PARTNER_STATUSES = ('ACTIVE', 'SUSPENDED', 'ARCHIVED')
PARTNER_USER_STATUSES = ('ACTIVE', 'DISABLED')

ASSIGNMENT_STATUSES = ('ASSIGNED', 'ARRIVED', 'ACTIVE_TENANT', 'LEFT_HOSTEL', 'CANCELLED')
ASSIGNMENT_OPEN_STATUSES = ('ASSIGNED', 'ARRIVED', 'ACTIVE_TENANT')
ASSIGNMENT_TRANSITIONS = {
    'ASSIGNED': {'ARRIVED', 'ACTIVE_TENANT', 'CANCELLED'},
    'ARRIVED': {'ACTIVE_TENANT', 'LEFT_HOSTEL', 'CANCELLED'},
    'ACTIVE_TENANT': {'LEFT_HOSTEL'},
    'LEFT_HOSTEL': set(),
    'CANCELLED': set(),
}

AGREEMENT_STATUSES = ('ACTIVE', 'CANCELLED', 'REPLACED', 'ARCHIVED')
AGREEMENT_DOCUMENT_TYPES = ('ACCOMMODATION_AGREEMENT', 'CANCELLATION', 'REPLACEMENT', 'OTHER')

# Staff roles allowed to operate the hostel module (view/assign/upload).
HOSTEL_MANAGE_ROLES = {'admin', 'operator', 'operator_special', 'community_desk'}
# Staff roles allowed to manage partner organisations and partner logins.
HOSTEL_PARTNER_ADMIN_ROLES = {'admin'}

MAX_AGREEMENT_BYTES = 10 * 1024 * 1024  # 10 MB per agreement file

ALLOWED_UPLOAD_EXTENSIONS = {
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
}


def staff_can_manage(user):
    return bool(user) and (user.get('role') or '').strip() in HOSTEL_MANAGE_ROLES


def staff_is_partner_admin(user):
    return bool(user) and (user.get('role') or '').strip() in HOSTEL_PARTNER_ADMIN_ROLES


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def next_assignment_ref(db, year=None):
    """Race-safe reference generator (same pattern as gl_ref_counter)."""
    year = int(year or datetime.now().year)
    db.execute("INSERT OR IGNORE INTO hostel_ref_counter (year, next_seq) VALUES (?, 1)", [year])
    row = db.execute("SELECT next_seq FROM hostel_ref_counter WHERE year = ?", [year]).fetchone()
    seq = int(row['next_seq'] or 1)
    db.execute("UPDATE hostel_ref_counter SET next_seq = ? WHERE year = ?", [seq + 1, year])
    return f'HST-{year}-{seq:05d}'


def clean_text(value, max_len=2000):
    return str(value or '').strip()[:max_len]


def clean_date(value):
    s = str(value or '').strip()[:10]
    if not s:
        return ''
    try:
        datetime.strptime(s, '%Y-%m-%d')
        return s
    except ValueError:
        return ''
