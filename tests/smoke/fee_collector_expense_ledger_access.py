#!/usr/bin/env python3
"""Stdlib-only smoke test for fee_collector expense-ledger access.

Validates:
  1. fee_collector default redirect still lands on the fee workflow.
  2. fee_collector can reach the fee workflow page, office expense APIs,
     and the printable office expense record route.
  3. The rendered fee workflow page still exposes the Office Expense Ledger
     tab and submit flow.
  4. fee_collector is not silently promoted into unrelated admin-only areas.

Usage:
    python3 tests/smoke/fee_collector_expense_ledger_access.py
"""

from __future__ import annotations

import inspect
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import server  # noqa: E402


def main():
    print("Loading server.py …")

    fail = 0

    def expect(label, ok):
        nonlocal fail
        print(('  ✓' if ok else '  ✗ FAIL'), label)
        if not ok:
            fail += 1

    fee_user = {'role': 'fee_collector', 'user': 'fee-smoke'}

    print()
    print("Test 1: fee_collector redirect and route gates")
    expect("default redirect is /fee-collection", server._default_redirect_for_role('fee_collector') == '/fee-collection')
    expect("fee_collector can open /fee-collection", server.can_access_admin_route('fee_collector', '/fee-collection') is True)
    expect("fee_collector can open /dashboard", server.can_access_admin_route('fee_collector', '/dashboard') is True)
    expect(
        "fee_collector can open printable office expense record",
        server.can_access_admin_route('fee_collector', '/print/office-expense-record') is True,
    )
    expect("fee_collector can call /api/office-expenses", server.can_access_api_route('fee_collector', '/api/office-expenses') is True)
    expect(
        "fee_collector can call /api/office-expense-access",
        server.can_access_api_route('fee_collector', '/api/office-expense-access') is True,
    )
    expect(
        "fee_collector cannot call office expense approve/reject API",
        server.can_access_api_route('fee_collector', '/api/office-expense-decision') is False,
    )
    expect(
        "fee_collector cannot call office expense correction API",
        server.can_access_api_route('fee_collector', '/api/office-expense-update') is False,
    )
    expect("fee_collector cannot open /admin/dashboard", server.can_access_admin_route('fee_collector', '/admin/dashboard') is False)
    expect("fee_collector cannot open /admin/community-welfare", server.can_access_admin_route('fee_collector', '/admin/community-welfare') is False)
    expect(
        "fee_collector cannot call community welfare summary API",
        server.can_access_api_route('fee_collector', '/api/admin/dashboard/community-welfare-summary') is False,
    )

    print()
    print("Test 2: fee workflow page keeps office expense ledger UI")
    page = server.FEE_COLLECTION_PAGE
    expect("Office Expense Ledger tab label present", 'Office Expense Ledger' in page)
    expect("Office expense submit CTA present", 'Submit Office Expense' in page)
    expect("Office expense access endpoint wired", "/api/office-expense-access" in page)
    expect("Office expense list/create endpoint wired", "/api/office-expenses" in page)
    expect("office tab handler present", "showPortalTab('office')" in page)
    expect("office access modal still present", 'Open Ledger' in page)
    expect("office ledger tab query/hash parser present", 'requestedPortalTab' in page and 'office-expense-ledger' in page)
    expect("office tab URL state is preserved", 'syncPortalTabUrl' in page and "url.searchParams.set('tab','office-expense-ledger')" in page)
    expect("office unlock uses server-rendered session state", '__OFFICE_EXPENSE_UNLOCKED__' in page)
    expect("office unlock success activates the ledger tab in place", "await showPortalTab('office')" in page)
    expect("reauth expiry no longer bounces to the fee tab", "showPortalTab('fees');" not in page)

    locked_page = server.fee_collection_page_html(fee_user)
    unlocked_page = server.fee_collection_page_html({
        'role': 'fee_collector',
        'user': 'fee-smoke',
        'office_expense_unlock_until': time.time() + 60,
    })
    expect("rendered locked page replaces unlock placeholder", '__OFFICE_EXPENSE_UNLOCKED__' not in locked_page)
    expect("rendered locked page starts locked for fee_collector", "let officeTabUnlocked=USER_ROLE==='admin'||false;" in locked_page)
    expect("rendered unlocked page starts unlocked for fee_collector", "let officeTabUnlocked=USER_ROLE==='admin'||true;" in unlocked_page)

    print()
    print("Test 3: GET handlers route fee_collector to the fee workflow page")
    get_src = inspect.getsource(server.Handler.do_GET)
    expect("fee collection page route exists", "elif path == '/fee-collection':" in get_src)
    expect("dashboard fee_collector branch exists", "elif user['role'] == 'fee_collector':" in get_src)
    expect("print office expense record route exists", "elif path == '/print/office-expense-record':" in get_src)

    for route in ('/dashboard', '/fee-collection'):
        captured = {}
        handler = server.Handler.__new__(server.Handler)
        handler.path = route
        handler.headers = {}
        handler.require_auth = lambda route_user=fee_user: route_user
        handler.normalize_request_path = lambda raw_path: raw_path
        handler.send_html = lambda html, status=200, extra_headers=None: captured.update({
            'html': html,
            'status': status,
            'headers': extra_headers or {},
        })
        server.Handler.do_GET(handler)
        expect(f"{route} responds with 200", captured.get('status') == 200)
        expect(f"{route} renders Office Expense Ledger", 'Office Expense Ledger' in (captured.get('html') or ''))
        expect(f"{route} renders expense submit flow", 'Submit Office Expense' in (captured.get('html') or ''))
        expect(f"{route} replaces unlock placeholder", '__OFFICE_EXPENSE_UNLOCKED__' not in (captured.get('html') or ''))

    print()
    print("Test 4: office expense GET/POST handlers still allow fee_collector")
    post_src = inspect.getsource(server.Handler.do_POST)
    put_src = inspect.getsource(server.Handler.do_PUT)
    access_segment = post_src.split("elif path == '/api/office-expense-access':", 1)[1].split("elif path == '/api/office-expense-decision':", 1)[0]
    expect("office expenses GET handler exists", "elif path == '/api/office-expenses':" in get_src)
    expect("office expenses POST handler exists", "elif path == '/api/office-expenses':" in post_src)
    expect("office expense access POST handler exists", "elif path == '/api/office-expense-access':" in post_src)
    expect("office expense POST keeps fee collector/admin guard", 'Only fee collector/admin can create office expenses' in post_src)
    expect("fee settlement POST keeps fee collector/admin guard", 'Only fee collector/admin can record settlements' in post_src)
    expect("office expense access persists unlock into session store", "cookie_str=self.headers.get('Cookie')" in access_segment)
    expect("office expense access returns ledger tab redirect hint", 'OFFICE_EXPENSE_LEDGER_URL' in access_segment)
    expect("office expense access does not redirect to plain dashboard", '/dashboard' not in access_segment)
    expect("office expense decision remains admin-only", "if user['role'] != 'admin':" in post_src and 'Only admin can approve or reject office expenses' in post_src)
    expect("office expense correction remains admin-only", "if path == '/api/office-expense-update':" in put_src and "if user['role'] != 'admin':" in put_src)

    print()
    print("Test 5: office expense unlock flag persists across session copies")
    token = server.create_session('fee-smoke', 'fee_collector', ttl_seconds=600)
    cookie = f'session={token}'
    try:
        session_copy = server.get_session(cookie)
        expect("new fee_collector session starts locked", server._office_expense_access_granted(session_copy) is False)
        server._grant_office_expense_access(session_copy, minutes=1, cookie_str=cookie)
        persisted_session = server.get_session(cookie)
        expect("current request copy is unlocked", server._office_expense_access_granted(session_copy) is True)
        expect("stored session remains unlocked for next request", server._office_expense_access_granted(persisted_session) is True)
    finally:
        server.destroy_session(token)

    print()
    print("Test 6: unlocked fee_collector can reach office expense create route")
    captured = {}
    created = {}
    original_create = server.api_office_expense_create

    def fake_create(data, username):
        created.update({'data': data, 'username': username})
        return {'success': True, 'record_number': 'SMOKE-OE'}

    handler = server.Handler.__new__(server.Handler)
    handler.path = '/api/office-expenses'
    handler.headers = {}
    handler.normalize_request_path = lambda raw_path: raw_path
    handler.read_body = lambda: b'{"expense_date":"2026-05-11","description":"Smoke","amount":1}'
    handler.require_auth = lambda: {
        'role': 'fee_collector',
        'user': 'fee-smoke',
        'office_expense_unlock_until': time.time() + 60,
    }
    handler.send_json = lambda obj, status=200, extra_headers=None: captured.update({
        'json': obj,
        'status': status,
        'headers': extra_headers or {},
    })
    server.api_office_expense_create = fake_create
    try:
        server.Handler.do_POST(handler)
    finally:
        server.api_office_expense_create = original_create
    expect("unlocked fee_collector create route returns 200", captured.get('status') == 200)
    expect("unlocked fee_collector create route calls create API", created.get('username') == 'fee-smoke')
    expect("unlocked fee_collector create route returns success payload", (captured.get('json') or {}).get('record_number') == 'SMOKE-OE')

    print()
    if fail:
        print(f"{fail} check(s) failed.")
        raise SystemExit(1)
    print("All fee_collector expense-ledger access checks passed.")


if __name__ == '__main__':
    main()
