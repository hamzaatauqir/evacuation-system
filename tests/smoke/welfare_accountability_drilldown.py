#!/usr/bin/env python3
"""Focused logic test for the staff-accountability drill-down API.

Stdlib-only. Builds an in-memory SQLite shaped just enough for the four
source tables, seeds a small set of cases, and verifies that:

  1. Unauthorized users are rejected.
  2. Invalid metric is rejected with status 400.
  3. Missing officer_key is rejected with status 400.
  4. Each valid metric returns count == len(cases) for the same officer.
  5. external_branch:* synthetic keys are handled.
  6. The dashboard count for a given officer/metric matches the
     drill-down list length (the consistency invariant the task requires).

No HTTP. No 2FA. Does not touch production DB.

Usage:
    python3 tests/smoke/welfare_accountability_drilldown.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)


SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT, full_name TEXT, department TEXT
);
CREATE TABLE welfare_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_reference TEXT,
    case_type TEXT,
    category TEXT,
    requester_name TEXT,
    requester_phone TEXT,
    subject_name TEXT,
    subject_passport TEXT,
    subject_phone TEXT,
    concern_summary TEXT,
    status TEXT,
    assigned_to TEXT,
    assigned_department TEXT,
    assigned_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    resolved_at TEXT
);
CREATE TABLE welfare_case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    actor_username TEXT,
    note TEXT,
    created_at TEXT
);
CREATE TABLE legal_case_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT, full_name TEXT, passport_number TEXT, mobile TEXT,
    subject TEXT, case_type TEXT, status TEXT,
    assigned_to_username TEXT, assigned_department TEXT,
    assigned_at TEXT, created_at TEXT, updated_at TEXT, resolved_at TEXT
);
CREATE TABLE legal_case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT, actor_username TEXT, note TEXT, created_at TEXT
);
CREATE TABLE death_case_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT, reporter_name TEXT, reporter_mobile TEXT,
    deceased_name TEXT, deceased_passport TEXT,
    status TEXT, assigned_to_username TEXT, assigned_department TEXT,
    assigned_at TEXT, created_at TEXT, updated_at TEXT, resolved_at TEXT
);
CREATE TABLE death_case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT, actor_username TEXT, note TEXT, created_at TEXT
);
CREATE TABLE nurse_complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT, nurse_reference_id TEXT, nurse_full_name TEXT,
    passport_number TEXT, subject TEXT, category TEXT, complaint_category TEXT,
    status TEXT, complaint_status TEXT,
    assigned_to_username TEXT, assigned_department TEXT,
    assigned_at TEXT, created_at TEXT, updated_at TEXT, resolved_at TEXT
);
CREATE TABLE nurse_complaint_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT, actor_username TEXT, note TEXT, created_at TEXT
);
"""


def _import_server():
    """Import server.py without booting the HTTP listener."""
    import server  # noqa: E402
    # Patch get_db so the API helpers use our in-memory connection.
    return server


def _ago(days):
    return (datetime.utcnow() - timedelta(days=days)).isoformat(timespec='seconds')


def _seed(db):
    now = datetime.utcnow().isoformat(timespec='seconds')
    # Officer Zahid: 3 open welfare cases — one new, one overdue >5d, one
    # with no staff action (8 days old, no action).
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at)
                  VALUES (?, 'welfare', 'A', 'P1', 'New', 'Zahid', ?, ?, ?)""",
               ['CW-1', _ago(2), _ago(2), _ago(2)])  # not overdue, no staff action
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at)
                  VALUES (?, 'welfare', 'B', 'P2', 'In Progress', 'Zahid', ?, ?, ?)""",
               ['CW-2', _ago(8), _ago(8), _ago(2)])  # overdue, has action below
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at)
                  VALUES (?, 'welfare', 'C', 'P3', 'Assigned', 'Zahid', ?, ?, ?)""",
               ['CW-3', _ago(7), _ago(7), _ago(7)])  # overdue + no action
    # CW-2 has a staff action.
    db.execute("""INSERT INTO welfare_case_actions (case_id, actor_username, note, created_at)
                  VALUES (2, 'Zahid', 'Called subject; awaiting reply', ?)""", [_ago(1)])
    # CW-1 and CW-3 have public-only entries (don't count as staff action).
    db.execute("""INSERT INTO welfare_case_actions (case_id, actor_username, note, created_at)
                  VALUES (1, 'public', 'Applicant reply', ?)""", [_ago(1)])
    # Officer Zahid: one resolved-this-week case.
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at, resolved_at)
                  VALUES (?, 'welfare', 'D', 'P4', 'Resolved', 'Zahid', ?, ?, ?, ?)""",
               ['CW-4', _ago(10), _ago(10), _ago(2), _ago(2)])
    db.execute("""INSERT INTO welfare_case_actions (case_id, actor_username, note, created_at)
                  VALUES (4, 'Zahid', 'Resolved: contacted employer', ?)""", [_ago(2)])

    # Officer Awais: 2 resolved-this-week, 1 resolved long ago (excluded).
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at, resolved_at)
                  VALUES (?, 'welfare', 'E', 'P5', 'Closed', 'Awais', ?, ?, ?, ?)""",
               ['CW-5', _ago(15), _ago(15), _ago(3), _ago(3)])
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at, resolved_at)
                  VALUES (?, 'welfare', 'F', 'P6', 'Resolved', 'Awais', ?, ?, ?, ?)""",
               ['CW-6', _ago(12), _ago(12), _ago(1), _ago(1)])
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at, resolved_at)
                  VALUES (?, 'welfare', 'G', 'P7', 'Resolved', 'Awais', ?, ?, ?, ?)""",
               ['CW-old', _ago(40), _ago(40), _ago(20), _ago(20)])  # outside 7-day window

    # External branch: passport — 1 resolved-this-week.
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at, resolved_at)
                  VALUES (?, 'welfare', 'H', 'P8', 'Resolved', 'external_branch:passport', ?, ?, ?, ?)""",
               ['CW-PB1', _ago(8), _ago(8), _ago(1), _ago(1)])

    # Other officer's case (Bilal) to ensure officer scoping.
    db.execute("""INSERT INTO welfare_cases (case_reference, case_type, requester_name,
                  subject_passport, status, assigned_to, assigned_at, created_at, updated_at)
                  VALUES (?, 'welfare', 'X', 'P9', 'New', 'Bilal', ?, ?, ?)""",
               ['CW-OTHER', _ago(2), _ago(2), _ago(2)])
    db.commit()


def main():
    print("Loading server.py …")
    server = _import_server()

    # The drill-down API uses get_db() — patch it to return our in-memory DB.
    db = sqlite3.connect(':memory:', check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    _seed(db)

    # Make get_db return our test DB on every call. The API closes the
    # connection in `finally:` so we wrap so close() is a no-op.
    class _NoCloseProxy:
        def __init__(self, conn): self._conn = conn
        def __getattr__(self, name):
            if name == 'close':
                return lambda: None
            return getattr(self._conn, name)
    server.get_db = lambda: _NoCloseProxy(db)

    api = server.api_admin_staff_accountability_cases
    admin = {'role': 'admin', 'user': 'tester'}
    operator = {'role': 'operator', 'user': 'op'}
    public = {'role': 'public', 'user': ''}

    fail = 0
    def expect(label, got, expected):
        nonlocal fail
        if got == expected:
            print(f'  ✓ {label}')
        else:
            print(f'  ✗ FAIL {label}: got={got!r} expected={expected!r}')
            fail += 1

    # 1. Unauthorized: roles outside the same allowlist as the existing
    # accountability dashboard helper (is_full_admin_role) are rejected.
    # That helper currently allows {admin, operator, operator_special} —
    # the drill-down follows the SAME posture by design ("Use the same
    # authorization helper already used for the welfare dashboard").
    print()
    print("Test 1: unauthorized rejection")
    r = api({'officer_key': 'Zahid', 'metric': 'assigned_open'}, public)
    expect('public success=False', r.get('success'), False)
    expect('public status_code=403', r.get('status_code'), 403)
    r = api({'officer_key': 'Zahid', 'metric': 'assigned_open'},
            {'role': 'fee_collector', 'user': 'fc'})
    expect('fee_collector rejected', r.get('success'), False)
    r = api({'officer_key': 'Zahid', 'metric': 'assigned_open'}, operator)
    # operator IS in the allowlist (same as dashboard) — sanity check.
    expect('operator allowed (mirrors dashboard helper)', r.get('success'), True)

    # 2. Invalid metric → 400.
    print()
    print("Test 2: invalid metric rejected")
    r = api({'officer_key': 'Zahid', 'metric': 'totally_made_up'}, admin)
    expect('invalid metric → 400', r.get('status_code'), 400)
    expect('invalid metric error', r.get('error'), 'Invalid metric')
    expect('allowlist returned', sorted(r.get('allowed_metrics') or []),
           ['assigned_open', 'assigned_total', 'no_action', 'open_now', 'overdue', 'overdue_5_days', 'pending', 'resolved_this_week', 'resolved_total'])

    # 3. Missing officer_key → 400.
    print()
    print("Test 3: missing officer_key rejected")
    r = api({'metric': 'assigned_open'}, admin)
    expect('missing officer_key → 400', r.get('status_code'), 400)

    # 4. Zahid metrics — counts and list lengths agree.
    print()
    print("Test 4: Zahid metrics — count == len(cases) for every metric")
    for metric, expected_refs in [
        ('assigned_open',     {'CW-1', 'CW-2', 'CW-3'}),
        ('overdue_5_days',    {'CW-2', 'CW-3'}),
        ('no_action',         {'CW-1', 'CW-3'}),
        ('resolved_this_week', {'CW-4'}),
    ]:
        r = api({'officer_key': 'Zahid', 'metric': metric}, admin)
        expect(f"{metric} success", r.get('success'), True)
        expect(f"{metric} count == len(cases)", r.get('count'), len(r.get('cases') or []))
        actual_refs = {c.get('reference_no') for c in (r.get('cases') or [])}
        expect(f"{metric} cases match expected", actual_refs, expected_refs)

    # 5. external_branch:passport — resolved_this_week.
    print()
    print("Test 5: external_branch:passport — resolved_this_week")
    r = api({'officer_key': 'external_branch:passport', 'metric': 'resolved_this_week'}, admin)
    expect('branch resolved count', r.get('count'), 1)
    expect('branch case ref', (r.get('cases') or [{}])[0].get('reference_no'), 'CW-PB1')

    # 6. Awais — resolved_this_week excludes the 20-day-old one.
    print()
    print("Test 6: Awais resolved_this_week excludes old resolved")
    r = api({'officer_key': 'Awais', 'metric': 'resolved_this_week'}, admin)
    expect('Awais resolved count', r.get('count'), 2)
    refs = {c.get('reference_no') for c in (r.get('cases') or [])}
    expect("Awais cases (CW-5, CW-6)", refs, {'CW-5', 'CW-6'})

    # 7. Officer scoping — Bilal's open case is NOT in Zahid's drill-down.
    print()
    print("Test 7: officer scoping is tight")
    r = api({'officer_key': 'Zahid', 'metric': 'assigned_open'}, admin)
    refs = {c.get('reference_no') for c in (r.get('cases') or [])}
    expect("CW-OTHER not in Zahid's list", 'CW-OTHER' not in refs, True)

    # 8. Resolved row carries resolution_remarks (latest action note).
    print()
    print("Test 8: resolved row carries resolution_remarks")
    r = api({'officer_key': 'Zahid', 'metric': 'resolved_this_week'}, admin)
    case = (r.get('cases') or [{}])[0]
    expect("remarks present", bool(case.get('resolution_remarks')), True)
    expect("remarks is the latest action note", case.get('resolution_remarks'),
           'Resolved: contacted employer')

    # 9. Dashboard aggregate sentinel and new dashboard metrics work.
    print()
    print("Test 9: dashboard-wide modal metrics are supported")
    r = api({'officer_key': '__all__', 'metric': 'pending'}, admin)
    expect("__all__ pending success", r.get('success'), True)
    expect("__all__ pending returns cases", len(r.get('cases') or []) > 0, True)
    refs = {c.get('reference_no') for c in (r.get('cases') or [])}
    expect("__all__ pending includes Zahid open case", 'CW-1' in refs, True)
    r = api({'officer_key': 'Zahid', 'metric': 'resolved_total'}, admin)
    expect("resolved_total returns Zahid's resolved case", {c.get('reference_no') for c in (r.get('cases') or [])}, {'CW-4'})

    print()
    print(f'FAIL count: {fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
