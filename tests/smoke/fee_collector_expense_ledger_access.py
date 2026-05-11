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

    print()
    print("Test 4: office expense GET/POST handlers still allow fee_collector")
    post_src = inspect.getsource(server.Handler.do_POST)
    expect("office expenses GET handler exists", "elif path == '/api/office-expenses':" in get_src)
    expect("office expenses POST handler exists", "elif path == '/api/office-expenses':" in post_src)
    expect("office expense access POST handler exists", "elif path == '/api/office-expense-access':" in post_src)
    expect("office expense POST keeps fee collector/admin guard", 'Only fee collector/admin can create office expenses' in post_src)
    expect("fee settlement POST keeps fee collector/admin guard", 'Only fee collector/admin can record settlements' in post_src)

    print()
    if fail:
        print(f"{fail} check(s) failed.")
        raise SystemExit(1)
    print("All fee_collector expense-ledger access checks passed.")


if __name__ == '__main__':
    main()
