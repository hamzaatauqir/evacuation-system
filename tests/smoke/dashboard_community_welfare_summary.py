#!/usr/bin/env python3
"""Stdlib-only smoke test for the Community Welfare dashboard summary API.

Validates:
  1. The admin dashboard alias route exists.
  2. Empty datasets do not crash the summary helper.
  3. Seeded welfare/legal/nurse/death rows produce summary, trends,
     staff accountability, and recent activity payloads.
  4. The GET route alias returns HTTP 200 for an authenticated admin.

Usage:
    python3 tests/smoke/dashboard_community_welfare_summary.py
"""

from __future__ import annotations

import inspect
import os
import sqlite3
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import server  # noqa: E402


SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    full_name TEXT,
    department TEXT
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
    priority TEXT,
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
    action_type TEXT,
    note TEXT,
    created_at TEXT
);
CREATE TABLE legal_case_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT,
    full_name TEXT,
    passport_number TEXT,
    mobile TEXT,
    case_type TEXT,
    subject TEXT,
    priority TEXT,
    status TEXT,
    assigned_to_username TEXT,
    assigned_department TEXT,
    assigned_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    last_action_at TEXT,
    resolved_at TEXT
);
CREATE TABLE legal_case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT,
    actor_username TEXT,
    action_type TEXT,
    note TEXT,
    created_at TEXT
);
CREATE TABLE death_case_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT,
    reporter_name TEXT,
    deceased_name TEXT,
    deceased_passport TEXT,
    reporter_mobile TEXT,
    priority TEXT,
    status TEXT,
    assigned_to_username TEXT,
    assigned_department TEXT,
    assigned_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    last_action_at TEXT,
    resolved_at TEXT
);
CREATE TABLE death_case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT,
    actor_username TEXT,
    action_type TEXT,
    note TEXT,
    created_at TEXT
);
CREATE TABLE nurse_complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT,
    nurse_reference_id TEXT,
    complaint_category TEXT,
    category TEXT,
    nurse_full_name TEXT,
    subject TEXT,
    passport_number TEXT,
    priority TEXT,
    status TEXT,
    complaint_status TEXT,
    assigned_to_username TEXT,
    assigned_department TEXT,
    assigned_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    resolved_at TEXT
);
CREATE TABLE nurse_complaint_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT,
    actor_username TEXT,
    action_type TEXT,
    note TEXT,
    created_at TEXT
);
"""


class _NoCloseProxy:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        if name == 'close':
            return lambda: None
        return getattr(self._conn, name)


def _ago(days, hours=0):
    return (datetime.utcnow() - timedelta(days=days, hours=hours)).strftime('%Y-%m-%d %H:%M:%S')


def _make_db():
    db = sqlite3.connect(':memory:', check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def _seed(db):
    db.executemany(
        "INSERT INTO users (username, full_name, department) VALUES (?, ?, ?)",
        [
            ('zahid', 'Zahid Hussain', 'Community Welfare'),
            ('ayesha', 'Ayesha Khan', 'Legal / Welfare'),
        ],
    )

    db.execute(
        """INSERT INTO welfare_cases
           (case_reference, case_type, category, requester_name, requester_phone,
            subject_name, subject_passport, concern_summary, priority, status,
            assigned_to, assigned_department, assigned_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            'CWA-1001', 'community_feedback', 'Service Complaint', 'Bilal', '+96511111111',
            'Bilal', 'P1', 'Follow-up pending', 'Urgent', 'Assigned',
            'zahid', 'Community Welfare', _ago(7), _ago(7), _ago(1),
        ),
    )
    db.execute(
        """INSERT INTO welfare_case_actions
           (case_id, actor_username, action_type, note, created_at)
           VALUES (1, 'zahid', 'call_made', 'Called applicant and logged the follow-up.', ?)""",
        (_ago(1),),
    )

    db.execute(
        """INSERT INTO nurse_complaints
           (complaint_id, nurse_reference_id, complaint_category, category, nurse_full_name,
            subject, passport_number, priority, status, complaint_status,
            assigned_to_username, assigned_department, assigned_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            'NUR-3001', 'NR-1', 'Accommodation', 'Accommodation', 'Hina',
            'Accommodation issue', 'NP1', 'Normal', 'Assigned', 'Assigned',
            'zahid', 'Community Welfare', _ago(6), _ago(6), _ago(2),
        ),
    )

    db.execute(
        """INSERT INTO legal_case_requests
           (reference_id, full_name, passport_number, mobile, case_type, subject,
            priority, status, assigned_to_username, assigned_department,
            assigned_at, created_at, updated_at, last_action_at, resolved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            'LGL-2001', 'Sajid', 'LP1', '+96522222222', 'Labour Complaint', 'Salary not paid',
            'Important', 'Resolved', 'ayesha', 'Legal / Welfare',
            _ago(9), _ago(9), _ago(2), _ago(2), _ago(2),
        ),
    )
    db.execute(
        """INSERT INTO legal_case_actions
           (reference_id, actor_username, action_type, note, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ('LGL-2001', 'ayesha', 'resolved', 'Employer contacted and salary released.', _ago(2)),
    )

    db.execute(
        """INSERT INTO death_case_requests
           (reference_id, reporter_name, deceased_name, deceased_passport, reporter_mobile,
            priority, status, assigned_to_username, assigned_department,
            assigned_at, created_at, updated_at, last_action_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            'DTH-4001', 'Family Contact', 'Late Ahmed', 'DP1', '+96533333333',
            'Urgent', 'In Progress', 'ayesha', 'Legal / Welfare',
            _ago(8), _ago(8), _ago(1), _ago(1),
        ),
    )
    db.execute(
        """INSERT INTO death_case_actions
           (reference_id, actor_username, action_type, note, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ('DTH-4001', 'ayesha', 'update', 'Documentation requested from hospital.', _ago(1)),
    )
    db.commit()


def main():
    print("Loading server.py …")

    fail = 0

    def expect(label, ok):
        nonlocal fail
        print(('  ✓' if ok else '  ✗ FAIL'), label)
        if not ok:
            fail += 1

    admin = {'role': 'admin', 'user': 'smoke-admin'}

    print()
    print("Test 1: source-level dashboard route and UI markers exist")
    route_src = inspect.getsource(server.Handler.do_GET)
    payload_src = inspect.getsource(server._community_welfare_dashboard_payload)
    expect("route alias exists", "/api/admin/dashboard/community-welfare-summary" in route_src)
    expect("summary payload helper includes staff_accountability", 'staff_accountability' in payload_src)
    expect("summary payload helper includes recent_activity", 'recent_activity' in payload_src)
    expect("summary payload helper includes avg_resolution_days", 'avg_resolution_days' in payload_src)
    expect("summary payload helper includes priority_level", 'priority_level' in payload_src)
    expect("summary payload helper includes priority_reason", 'priority_reason' in payload_src)
    expect("main dashboard prioritises Community Welfare title", 'Community Welfare Command Dashboard' in server.MAIN_APP)
    expect("staff dashboard has inline drill-down action bar", 'cwaStaffActionButtons' in server.MAIN_APP)
    expect("staff dashboard keeps modal on same page", 'cwaAcctOverlay' in server.MAIN_APP and 'openCwaAccountabilityDrilldown' in server.MAIN_APP)
    expect("staff dashboard modal offers Open Case action", 'Open Case' in server.MAIN_APP)
    expect("main dashboard includes priority activity title", 'Recent &amp; Priority Community Welfare Activity' in server.MAIN_APP)
    expect("main dashboard keeps visa standby section lower", 'Visa / Transit Processing &mdash; Standby / Historical' in server.MAIN_APP)
    expect("removed visa analytics label Processing Trend absent", 'Processing Trend' not in server.MAIN_APP)
    expect("removed visa analytics label Top Professions Helped absent", 'Top Professions Helped' not in server.MAIN_APP)
    expect("removed visa analytics label Pending Age Buckets absent", 'Pending Age Buckets' not in server.MAIN_APP)

    original_get_db = server.get_db
    try:
        print()
        print("Test 2: empty data does not crash the summary helper")
        empty_db = _make_db()
        server.get_db = lambda: _NoCloseProxy(empty_db)
        empty_payload = server.api_admin_community_welfare_summary(admin)
        expect("empty payload success", empty_payload.get('success') is True)
        expect("empty payload has summary", isinstance(empty_payload.get('summary'), dict))
        expect("empty total complaints is 0", empty_payload.get('summary', {}).get('total_complaints') == 0)
        expect("empty staff_accountability is []", empty_payload.get('staff_accountability') == [])
        expect("empty recent_activity is []", empty_payload.get('recent_activity') == [])

        print()
        print("Test 3: seeded summary contains complaint, trend, staff, and activity data")
        seeded_db = _make_db()
        _seed(seeded_db)
        server.get_db = lambda: _NoCloseProxy(seeded_db)
        payload = server.api_admin_community_welfare_summary(admin)
        summary = payload.get('summary') or {}
        staff = payload.get('staff_accountability') or []
        recent = payload.get('recent_activity') or []
        expect("summary total_complaints populated", summary.get('total_complaints', 0) >= 4)
        expect("summary overdue populated", summary.get('overdue', 0) >= 1)
        expect("summary pending_staff_action populated", summary.get('pending_staff_action', 0) >= 1)
        expect("avg_resolution_days available", summary.get('avg_resolution_days') is not None)
        expect("staff_accountability populated", len(staff) >= 2)
        expect("recent_activity populated", len(recent) >= 1)
        expect("recent_activity includes priority fields",
               all('priority_level' in item and 'priority_reason' in item for item in recent))
        expect("recent_activity prioritises no-action delayed case first",
               recent[0].get('reference') == 'NUR-3001')
        expect("recent_activity top item explains missing staff action",
               'No staff action recorded' in (recent[0].get('priority_reason') or ''))
        expect("status breakdown includes open/in_progress/resolved/closed",
               [x.get('status') for x in payload.get('by_status', [])] == ['open', 'in_progress', 'resolved', 'closed'])
        drill = server.api_admin_staff_accountability_cases({'officer_key': '__all__', 'metric': 'pending'}, admin)
        expect("dashboard drill-down supports all-staff pending metric", drill.get('success') is True)
        expect("dashboard drill-down returns case rows", len(drill.get('cases') or []) >= 1)

        print()
        print("Test 4: dashboard alias route returns HTTP 200 for admin")
        captured = {}
        handler = server.Handler.__new__(server.Handler)
        handler.path = '/api/admin/dashboard/community-welfare-summary'
        handler.headers = {}
        handler.require_auth = lambda: admin
        handler.normalize_request_path = lambda raw_path: raw_path
        handler.send_json = lambda data, status=200, extra_headers=None: captured.update({
            'data': data,
            'status': status,
            'headers': extra_headers or {},
        })
        server.Handler.do_GET(handler)
        expect("captured HTTP status is 200", captured.get('status') == 200)
        expect("route payload has summary", isinstance((captured.get('data') or {}).get('summary'), dict))
        expect("route payload has staff_accountability", isinstance((captured.get('data') or {}).get('staff_accountability'), list))
        expect("route payload has recent_activity", isinstance((captured.get('data') or {}).get('recent_activity'), list))
        route_recent = (captured.get('data') or {}).get('recent_activity') or []
        expect("route recent_activity retains priority fields when populated",
               (not route_recent) or ('priority_level' in route_recent[0] and 'priority_reason' in route_recent[0]))

    finally:
        server.get_db = original_get_db

    print()
    if fail:
        print(f"{fail} check(s) failed.")
        raise SystemExit(1)
    print("All dashboard Community Welfare summary checks passed.")


if __name__ == '__main__':
    main()
