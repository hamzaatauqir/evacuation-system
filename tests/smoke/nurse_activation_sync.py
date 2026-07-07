#!/usr/bin/env python3
"""Focused logic test for _sync_nurse_activation_from_arrival_status.

Stdlib-only. Spins up an in-memory SQLite, builds the minimal `nurse_registrations`,
`nh_arrival_batch`, `nh_nurse_account`, and `nh_audit` schema needed by the
helper, and exercises:

  1. Happy path:   batch is ARRIVED and only one row exists  → activates.
  2. Duplicate row gotcha:  PLANNED + ARRIVED rows for same code → activates
     because the helper prefers the ARRIVED row.
  3. Idempotent:   second call after activation → 'already_active', no audit.
  4. Not arrived:  batch is PLANNED only → 'batch_not_arrived', no activation.
  5. Missing field: batch ARRIVED but visa_number empty → defers, lists field.
  6. Normalization:  batch_number = ' Batch  39 ' → digits-only normalized to '39'.

Does NOT exercise HTTP, auth, sessions, or 2FA. Does NOT touch production DB.

Usage:
    python3 tests/smoke/nurse_activation_sync.py
Exits 0 on success, 1 on first failed assertion.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

# Build the smallest viable schema. Mirrors the live shape — column additions
# beyond what the helper reads are unnecessary here.
SCHEMA = """
CREATE TABLE nurse_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT,
    full_name TEXT,
    father_name TEXT,
    passport_number TEXT,
    civil_id TEXT,
    cnic TEXT,
    visa_number TEXT,
    hospital TEXT,
    hospital_workplace TEXT,
    hospital_or_medical_center TEXT,
    arrival_date TEXT,
    batch_number TEXT,
    updated_at TIMESTAMP,
    updated_by TEXT
);
CREATE TABLE nh_arrival_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_code TEXT,
    arrival_date TEXT,
    status TEXT,
    arrived_at TIMESTAMP,
    arrived_by TEXT,
    remarks TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE TABLE nh_nurse_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nurse_registration_id INTEGER,
    account_status TEXT,
    arrival_batch_id INTEGER,
    batch_code TEXT,
    activated_at TIMESTAMP,
    activated_by TEXT,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE TABLE nh_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT,
    entity_id INTEGER,
    event_type TEXT,
    nurse_registration_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    note TEXT,
    actor TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _import_helper_in_isolation():
    """Import server.py as a module and return its namespace.

    server.py guards init_db()/HTTP startup behind `if __name__ == '__main__':`,
    so a plain `import server` exposes every helper without booting the
    server, opening the real SQLite, or starting the listener.

    The activation helper indirectly calls `_nh_ensure_schema` /
    `_normalize_existing_arrival_batch_data`, which in production migrate
    DOZENS of tables (gl_grading_scale, nh_audit, etc.). For this isolated
    test we control the seeded schema directly, so we monkey-patch those
    schema-management entry points to no-ops. The helper logic itself is
    unmodified.
    """
    import server  # noqa: E402  (delayed import after sys.path tweak)
    server._nh_ensure_schema = lambda *a, **k: None
    server._normalize_existing_arrival_batch_data = lambda *a, **k: ({}, {})
    ns = {k: getattr(server, k) for k in dir(server)}
    if '_sync_nurse_activation_from_arrival_status' not in ns:
        raise RuntimeError("activation helper not present in server.py")
    return ns


def _build_schema(db):
    db.executescript(SCHEMA)
    db.commit()


def _seed_nurse(db, *, batch_number, complete_fields=True):
    fields = {
        'reference_id': 'NUR-TEST-001',
        'full_name': 'Test Nurse',
        'father_name': 'Test Father',
        'passport_number': 'AB1234567',
        'civil_id': '291010100000',
        'cnic': '12345-1234567-1',
        'visa_number': 'V-99999' if complete_fields else '',
        'hospital': 'Test Hospital',
        'hospital_workplace': 'Test Hospital',
        'hospital_or_medical_center': 'Test Hospital',
        'arrival_date': '2026-04-01',
        'batch_number': batch_number,
    }
    cols = ','.join(fields.keys())
    placeholders = ','.join('?' for _ in fields)
    cur = db.execute(
        f"INSERT INTO nurse_registrations ({cols}) VALUES ({placeholders})",
        list(fields.values())
    )
    db.commit()
    return int(cur.lastrowid)


def _seed_batch(db, *, batch_code, status):
    cur = db.execute(
        "INSERT INTO nh_arrival_batch (batch_code, arrival_date, status) VALUES (?, ?, ?)",
        [batch_code, '2026-04-01', status]
    )
    db.commit()
    return int(cur.lastrowid)


def _seed_account(db, *, nurse_id, status, batch_id=None, batch_code=''):
    cur = db.execute(
        "INSERT INTO nh_nurse_account (nurse_registration_id, account_status, arrival_batch_id, batch_code) "
        "VALUES (?, ?, ?, ?)",
        [nurse_id, status, batch_id, batch_code]
    )
    db.commit()
    return int(cur.lastrowid)


def assert_eq(label, got, expected):
    if got != expected:
        print(f'  ✗ FAIL {label}: got={got!r} expected={expected!r}')
        return 1
    print(f'  ✓ {label}')
    return 0


def main():
    print("Loading helpers from server.py …")
    ns = _import_helper_in_isolation()
    sync = ns['_sync_nurse_activation_from_arrival_status']
    norm = ns['_normalize_batch_no']

    # Quick normalizer sanity.
    print()
    print("Normalizer sanity:")
    fail = 0
    for raw, expected in [('39', '39'), (' 39 ', '39'), ('Batch 39', '39'),
                          ('39 batch', '39'), ('Flight #39', '39'),
                          ('', ''), ('abc', '')]:
        fail += assert_eq(f"normalize({raw!r})", norm(raw), expected)

    # Test 1: happy path — single ARRIVED row.
    print()
    print("Test 1: single ARRIVED row → activates")
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    _build_schema(db)
    nurse_id = _seed_nurse(db, batch_number='39')
    _seed_batch(db, batch_code='39', status='ARRIVED')
    _seed_account(db, nurse_id=nurse_id, status='PENDING_ARRIVAL')
    r = sync(db, nurse_id, reason='correction_approved', actor='admin')
    fail += assert_eq('changed', r['changed'], True)
    fail += assert_eq('activated', r['activated'], True)
    fail += assert_eq('previous_status', r['previous_status'], 'PENDING_ARRIVAL')
    fail += assert_eq('new_status', r['new_status'], 'ACTIVE')
    fail += assert_eq('batch_status', r['batch_status'], 'ARRIVED')
    fail += assert_eq('reason_skipped', r['reason_skipped'], '')
    audit_rows = db.execute("SELECT event_type FROM nh_audit").fetchall()
    audited = any('activated_via_correction_approved' in (row['event_type'] or '') for row in audit_rows)
    fail += assert_eq('audit row written', audited, True)
    db.close()

    # Test 2: duplicate batch rows — one PLANNED (older), one ARRIVED (newer).
    print()
    print("Test 2: duplicate batch rows (PLANNED + ARRIVED) → prefers ARRIVED → activates")
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    _build_schema(db)
    nurse_id = _seed_nurse(db, batch_number='39')
    _seed_batch(db, batch_code='39', status='PLANNED')   # older id, would defeat naive lookup
    _seed_batch(db, batch_code='39', status='ARRIVED')   # newer id, must be preferred
    _seed_account(db, nurse_id=nurse_id, status='PENDING_ARRIVAL')
    r = sync(db, nurse_id, reason='correction_approved', actor='admin')
    fail += assert_eq('changed', r['changed'], True)
    fail += assert_eq('activated', r['activated'], True)
    fail += assert_eq('batch_status', r['batch_status'], 'ARRIVED')
    db.close()

    # Test 3: idempotent — second call after activation is a no-op.
    print()
    print("Test 3: idempotent on already-active account")
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    _build_schema(db)
    nurse_id = _seed_nurse(db, batch_number='39')
    _seed_batch(db, batch_code='39', status='ARRIVED')
    _seed_account(db, nurse_id=nurse_id, status='ACTIVE')
    r = sync(db, nurse_id, reason='correction_approved', actor='admin')
    fail += assert_eq('changed (no-op)', r['changed'], False)
    fail += assert_eq('activated (still active)', r['activated'], True)
    fail += assert_eq('reason_skipped', r['reason_skipped'], 'already_active')
    audit_count = db.execute("SELECT COUNT(*) c FROM nh_audit").fetchone()['c']
    fail += assert_eq('no audit row added', audit_count, 0)
    db.close()

    # Test 4: not arrived — PLANNED only.
    print()
    print("Test 4: batch is PLANNED only → no activation")
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    _build_schema(db)
    nurse_id = _seed_nurse(db, batch_number='33')
    _seed_batch(db, batch_code='33', status='PLANNED')
    _seed_account(db, nurse_id=nurse_id, status='PENDING_ARRIVAL')
    r = sync(db, nurse_id, reason='correction_approved', actor='admin')
    fail += assert_eq('changed', r['changed'], False)
    fail += assert_eq('activated', r['activated'], False)
    fail += assert_eq('batch_status', r['batch_status'], 'PLANNED')
    fail += assert_eq('reason_skipped', r['reason_skipped'], 'batch_not_arrived')
    db.close()

    # Test 5: missing required field.
    print()
    print("Test 5: ARRIVED batch but visa_number missing → defers")
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    _build_schema(db)
    nurse_id = _seed_nurse(db, batch_number='39', complete_fields=False)
    _seed_batch(db, batch_code='39', status='ARRIVED')
    _seed_account(db, nurse_id=nurse_id, status='PENDING_ARRIVAL')
    r = sync(db, nurse_id, reason='correction_approved', actor='admin')
    fail += assert_eq('changed', r['changed'], False)
    fail += assert_eq('activated', r['activated'], False)
    fail += assert_eq('reason starts with missing', r['reason_skipped'].startswith('missing_required_fields:'), True)
    fail += assert_eq('Visa Number listed', 'Visa Number' in (r['missing_fields'] or []), True)
    db.close()

    # Test 6: normalization at the helper boundary.
    print()
    print("Test 6: nurse.batch_number stored as ' Batch  39 ' → resolves to '39'")
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    _build_schema(db)
    nurse_id = _seed_nurse(db, batch_number=' Batch  39 ')
    _seed_batch(db, batch_code='39', status='ARRIVED')
    _seed_account(db, nurse_id=nurse_id, status='PENDING_ARRIVAL')
    r = sync(db, nurse_id, reason='correction_approved', actor='admin')
    fail += assert_eq('batch_code resolved', r['batch_code'], '39')
    fail += assert_eq('activated', r['activated'], True)
    db.close()

    print()
    print(f'FAIL count: {fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
