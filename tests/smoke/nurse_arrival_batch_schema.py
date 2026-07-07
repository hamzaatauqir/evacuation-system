#!/usr/bin/env python3
"""Smoke tests for nurse arrival-batch schema healing and GET handler resilience.

Stdlib-only. Does NOT exercise HTTP, auth, sessions, or 2FA.

Covers:
  1. Schema drift — legacy nh_arrival_batch missing newer columns.
  2. Schema drift — legacy nh_nurse_account missing newer columns.
  3. Aggregation survives blank / malformed batch numbers.
  4. Handler failure returns JSON-style error instead of propagating.
  5. Normalization OperationalError falls back to read-only snapshot.

Usage:
    python3 tests/smoke/nurse_arrival_batch_schema.py
Exits 0 on success, 1 on first failed assertion.
"""

from __future__ import annotations

import os
import sqlite3
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

LEGACY_ARRIVAL_BATCH = """
CREATE TABLE nh_arrival_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_code TEXT UNIQUE NOT NULL,
    arrival_date TEXT,
    status TEXT,
    created_at TEXT
);
"""

LEGACY_NURSE_ACCOUNT = """
CREATE TABLE nh_nurse_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nurse_registration_id INTEGER NOT NULL,
    arrival_batch_id INTEGER,
    created_at TEXT
);
"""

MINIMAL_NURSE_REG = """
CREATE TABLE nurse_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT,
    full_name TEXT,
    batch_number TEXT,
    arrival_date TEXT,
    updated_at TEXT
);
"""


def _import_server():
    import server  # noqa: E402
    return server


def assert_eq(label, got, expected):
    if got != expected:
        print(f'  ✗ FAIL {label}: got={got!r} expected={expected!r}')
        return 1
    print(f'  ✓ {label}')
    return 0


def assert_true(label, cond):
    if not cond:
        print(f'  ✗ FAIL {label}')
        return 1
    print(f'  ✓ {label}')
    return 0


def _columns(db, table):
    return {
        c['name'] if isinstance(c, sqlite3.Row) else c[1]
        for c in db.execute(f"PRAGMA table_info({table})").fetchall()
    }


def test_schema_drift_arrival_batch(server):
    print()
    print('Test 1: legacy nh_arrival_batch schema healing')
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript(LEGACY_ARRIVAL_BATCH)
    db.commit()
    server._nh_heal_legacy_columns(db)
    cols = _columns(db, 'nh_arrival_batch')
    fail = 0
    for col in ('arrived_at', 'arrived_by', 'remarks', 'updated_at'):
        fail += assert_true(f'column {col} present', col in cols)
    db.close()
    return fail


def test_schema_drift_nurse_account(server):
    print()
    print('Test 2: legacy nh_nurse_account schema healing')
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript(LEGACY_NURSE_ACCOUNT)
    db.commit()
    server._nh_heal_legacy_columns(db)
    cols = _columns(db, 'nh_nurse_account')
    fail = 0
    for col in ('batch_code', 'account_status', 'updated_at'):
        fail += assert_true(f'column {col} present', col in cols)
    db.close()
    return fail


def test_malformed_batch_aggregation(server):
    print()
    print('Test 3: aggregation with blank / malformed batch numbers')
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript(MINIMAL_NURSE_REG)
    db.executescript("""
    CREATE TABLE nh_arrival_batch (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_code TEXT UNIQUE NOT NULL,
        arrival_date TEXT DEFAULT '',
        status TEXT DEFAULT 'PLANNED',
        remarks TEXT DEFAULT '',
        arrived_at TEXT,
        arrived_by TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE nh_nurse_account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nurse_registration_id INTEGER NOT NULL,
        account_status TEXT DEFAULT 'PENDING_ARRIVAL',
        arrival_batch_id INTEGER,
        batch_code TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    seeds = [
        ('', 'PLANNED'),
        ('Batch 39', 'PLANNED'),
        ('Flight#7', 'ARRIVED'),
        ('39', 'PLANNED'),
    ]
    for code, status in seeds:
        try:
            db.execute(
                "INSERT INTO nh_arrival_batch (batch_code, status) VALUES (?, ?)",
                [code, status],
            )
        except sqlite3.IntegrityError:
            pass
    db.execute(
        "INSERT INTO nurse_registrations (reference_id, full_name, batch_number) VALUES (?, ?, ?)",
        ['N-1', 'Nurse One', 'Batch 39'],
    )
    db.commit()
    fail = 0
    try:
        _, items = server._arrival_batch_group_items(db, '')
        fail += assert_true('aggregation returned list', isinstance(items, list))
        codes = {item.get('batch_code') for item in items}
        fail += assert_true('normalized batch 39 present', '39' in codes)
        fail += assert_true('normalized batch 7 present', '7' in codes)
    except Exception as exc:
        print(f'  ✗ FAIL aggregation raised: {exc!r}')
        fail += 1
    db.close()
    return fail


def test_handler_failure_json(server):
    print()
    print('Test 4: arrival-batches handler returns JSON failure on exception')
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row

    def _boom(*a, **k):
        raise RuntimeError('simulated aggregation failure')

    orig = server._arrival_batch_group_items
    orig_get_db = server.get_db
    server._arrival_batch_group_items = _boom
    server.get_db = lambda: db
    fail = 0
    try:
        result = server.api_admin_nurse_arrival_batches({}, user={'role': 'admin'})
        fail += assert_eq('success flag', result.get('success'), False)
        fail += assert_true(
            'user-facing error message',
            'Could not load arrival batches' in (result.get('error') or ''),
        )
    finally:
        server._arrival_batch_group_items = orig
        server.get_db = orig_get_db
        db.close()
    return fail


def test_pending_handler_failure_json(server):
    print()
    print('Test 5: pending-accounts handler returns JSON failure on exception')
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row

    def _boom(*a, **k):
        raise RuntimeError('simulated query failure')

    orig = server._normalize_existing_arrival_batch_data
    orig_get_db = server.get_db
    server._normalize_existing_arrival_batch_data = _boom
    server.get_db = lambda: db
    fail = 0
    try:
        result = server.api_admin_nurse_pending_accounts({}, user={'role': 'admin'})
        fail += assert_eq('success flag', result.get('success'), False)
        fail += assert_true(
            'user-facing error message',
            'Could not load pending nurse accounts' in (result.get('error') or ''),
        )
    finally:
        server._normalize_existing_arrival_batch_data = orig
        server.get_db = orig_get_db
        db.close()
    return fail


def test_normalize_lock_fallback(server):
    print()
    print('Test 6: normalization OperationalError → read-only fallback')
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE nh_arrival_batch (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_code TEXT UNIQUE NOT NULL,
        arrival_date TEXT DEFAULT '',
        status TEXT DEFAULT 'PLANNED',
        remarks TEXT DEFAULT '',
        arrived_at TEXT,
        arrived_by TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE nh_nurse_account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nurse_registration_id INTEGER NOT NULL,
        account_status TEXT DEFAULT 'PENDING_ARRIVAL',
        arrival_batch_id INTEGER,
        batch_code TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE nurse_registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_number TEXT,
        arrival_date TEXT,
        updated_at TEXT
    );
    """)
    db.execute("INSERT INTO nh_arrival_batch (batch_code, status) VALUES ('42', 'PLANNED')")
    db.commit()

    orig_writes = server._normalize_existing_arrival_batch_data_writes

    def _locked_writes(inner_db):
        raise sqlite3.OperationalError('database is locked')

    server._normalize_existing_arrival_batch_data_writes = _locked_writes
    fail = 0
    try:
        changed, canonical = server._normalize_existing_arrival_batch_data(db)
        fail += assert_eq('changed flag on lock fallback', changed, False)
        fail += assert_true('canonical map returned', '42' in canonical)
    finally:
        server._normalize_existing_arrival_batch_data_writes = orig_writes
        db.close()
    return fail


def main():
    print('Loading server.py …')
    server = _import_server()
    fail = 0
    fail += test_schema_drift_arrival_batch(server)
    fail += test_schema_drift_nurse_account(server)
    fail += test_malformed_batch_aggregation(server)
    fail += test_handler_failure_json(server)
    fail += test_pending_handler_failure_json(server)
    fail += test_normalize_lock_fallback(server)
    print()
    print(f'FAIL count: {fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
