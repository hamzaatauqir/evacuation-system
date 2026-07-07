#!/usr/bin/env python3
"""Focused logic test for the nurse service-access matrix.

Stdlib-only. Does NOT exercise HTTP, auth, sessions, or 2FA. Pure
in-memory checks of `_nurse_service_access` plus a representative
`nh_check_service_access` call against an in-memory SQLite shaped
just enough for nh_get_account.

Scenarios:
  1.  PENDING_ARRIVAL nurse → basic services allowed
  2.  PENDING_ARRIVAL nurse → arrival_required services denied with
      structured `arrival_required` error
  3.  ACTIVE nurse → all services allowed
  4.  SUSPENDED nurse → all services denied with `account_suspended`
  5.  Unknown service code → fails closed (treated as arrival_required)
  6.  Legacy / blank account_status → treated as ACTIVE for safety

Usage:
    python3 tests/smoke/nurse_service_access.py
Exits 0 on success, 1 on first failure.
"""

from __future__ import annotations

import os
import sqlite3
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)


def _import_server():
    """Import server.py without booting the HTTP listener.

    server.py guards init_db()/HTTP startup behind `if __name__ == '__main__':`,
    so a plain `import server` exposes the helpers safely.
    """
    import server  # noqa: E402
    server._nh_ensure_schema = lambda *a, **k: None
    return server


def assert_eq(label, got, expected):
    if got != expected:
        print(f'  ✗ FAIL {label}: got={got!r} expected={expected!r}')
        return 1
    print(f'  ✓ {label}')
    return 0


# -- Phase 1: pure-matrix decisions, no DB ---------------------------------

BASIC_SERVICES = [
    'profile_view', 'profile_correction',
    'complaint_create', 'complaint_view',
    'accommodation_request', 'accommodation_update',
    'onboarding_view', 'onboarding_update',
    'guidance_view',
]
ARRIVAL_REQUIRED_SERVICES = [
    'grading_letter_request', 'grading_letter_resubmit', 'grading_letter_cancel',
    'facility_confirmation', 'leaving_notice', 'hostel_roster',
    'final_documents', 'post_arrival_movement',
]


def main():
    print("Loading server.py …")
    server = _import_server()
    sa = server._nurse_service_access

    fail = 0

    # Test 1: PENDING_ARRIVAL — basic services allowed.
    print()
    print("Test 1: PENDING_ARRIVAL nurse → basic services allowed")
    pending = {'account_status': 'PENDING_ARRIVAL', 'portal_banner': 'Arrival pending.'}
    for svc in BASIC_SERVICES:
        r = sa(pending, svc)
        fail += assert_eq(f"{svc} allowed", r['allowed'], True)
        fail += assert_eq(f"{svc} tier", r['service_tier'], 'basic_pre_arrival')

    # Test 2: PENDING_ARRIVAL — arrival_required services denied with structured error.
    print()
    print("Test 2: PENDING_ARRIVAL nurse → arrival_required services denied")
    for svc in ARRIVAL_REQUIRED_SERVICES:
        r = sa(pending, svc)
        fail += assert_eq(f"{svc} blocked", r['allowed'], False)
        fail += assert_eq(f"{svc} error code", r['error'], 'arrival_required')
        fail += assert_eq(f"{svc} tier", r['service_tier'], 'arrival_required')
        ok_msg = bool(r['message']) and 'unlock' in r['message']
        fail += assert_eq(f"{svc} message mentions unlock", ok_msg, True)

    # Test 3: ACTIVE — all services allowed.
    print()
    print("Test 3: ACTIVE nurse → all services allowed")
    active = {'account_status': 'ACTIVE'}
    for svc in BASIC_SERVICES + ARRIVAL_REQUIRED_SERVICES:
        r = sa(active, svc)
        fail += assert_eq(f"{svc} allowed (ACTIVE)", r['allowed'], True)

    # Test 4: SUSPENDED — all services denied with account_suspended error.
    print()
    print("Test 4: SUSPENDED nurse → all services denied with account_suspended")
    suspended = {'account_status': 'SUSPENDED'}
    for svc in BASIC_SERVICES + ARRIVAL_REQUIRED_SERVICES:
        r = sa(suspended, svc)
        fail += assert_eq(f"{svc} blocked (SUSPENDED)", r['allowed'], False)
        fail += assert_eq(f"{svc} error code (SUSPENDED)", r['error'], 'account_suspended')

    # Test 5: unknown service code — fails closed.
    print()
    print("Test 5: unknown service code → fails closed (arrival_required)")
    r = sa(pending, 'this_service_does_not_exist')
    fail += assert_eq("unknown svc tier", r['service_tier'], 'arrival_required')
    fail += assert_eq("unknown svc denied for PENDING_ARRIVAL", r['allowed'], False)
    fail += assert_eq("unknown svc allowed for ACTIVE", sa(active, 'this_service_does_not_exist')['allowed'], True)

    # Test 6: legacy / blank account_status — treated as ACTIVE for safety.
    print()
    print("Test 6: blank account_status → treated as ACTIVE")
    legacy = {'account_status': ''}
    for svc in [BASIC_SERVICES[0], ARRIVAL_REQUIRED_SERVICES[0]]:
        r = sa(legacy, svc)
        fail += assert_eq(f"{svc} allowed (legacy)", r['allowed'], True)

    # Test 7: nh_check_service_access wrapper returns None on allow,
    # structured dict on block, with `housing_account` payload.
    print()
    print("Test 7: nh_check_service_access wrapper shape")
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE nurse_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT, batch_number TEXT
        );
        CREATE TABLE nh_arrival_batch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_code TEXT, status TEXT, arrival_date TEXT
        );
        CREATE TABLE nh_nurse_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nurse_registration_id INTEGER,
            account_status TEXT,
            arrival_batch_id INTEGER,
            batch_code TEXT,
            activated_at TIMESTAMP,
            activated_by TEXT,
            notes TEXT DEFAULT ''
        );
    """)
    db.commit()
    cur = db.execute(
        "INSERT INTO nurse_registrations (full_name, batch_number) VALUES (?, ?)",
        ['Test', '33']
    )
    nurse_id = cur.lastrowid
    db.execute(
        "INSERT INTO nh_nurse_account (nurse_registration_id, account_status, batch_code) "
        "VALUES (?, 'PENDING_ARRIVAL', '33')", [nurse_id]
    )
    db.commit()
    nurse_d = dict(db.execute("SELECT * FROM nurse_registrations WHERE id = ?", [nurse_id]).fetchone())

    allowed_response = server.nh_check_service_access(db, nurse_d, 'complaint_create')
    fail += assert_eq("allowed → returns None", allowed_response, None)

    denied_response = server.nh_check_service_access(db, nurse_d, 'grading_letter_request')
    fail += assert_eq("denied → returns dict", isinstance(denied_response, dict), True)
    fail += assert_eq("denied success=False", denied_response.get('success'), False)
    fail += assert_eq("denied error=arrival_required", denied_response.get('error'), 'arrival_required')
    fail += assert_eq("denied service_code present", denied_response.get('service_code'), 'grading_letter_request')
    fail += assert_eq("denied includes housing_account", isinstance(denied_response.get('housing_account'), dict), True)
    db.close()

    print()
    print(f'FAIL count: {fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
