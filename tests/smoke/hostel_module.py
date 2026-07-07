#!/usr/bin/env python3
"""Read-only smoke checks for the hostel partner module.

Usage: python3 tests/smoke/hostel_module.py http://localhost:8080

Same contract as tests/smoke/routes.py: stdlib only, no login, no mutations,
any 5xx is a failure regardless of the allowed set.
"""
import http.client
import sys
import time
from urllib.parse import urlsplit

CHECKS = [
    # Partner pages
    {"name": "partner login page", "method": "GET", "path": "/hostel/login", "allowed": {200}},
    {"name": "partner dashboard gate", "method": "GET", "path": "/hostel/dashboard", "allowed": {302}},
    {"name": "hostel root redirect", "method": "GET", "path": "/hostel", "allowed": {302}},
    # Partner APIs require the hostel session
    {"name": "partner summary gate", "method": "GET", "path": "/api/hostel/summary", "allowed": {401}},
    {"name": "partner nurses gate", "method": "GET", "path": "/api/hostel/nurses", "allowed": {401}},
    {"name": "partner agreement file gate", "method": "GET", "path": "/api/hostel/agreements/file?id=1", "allowed": {401}},
    {"name": "partner export gate", "method": "GET", "path": "/api/hostel/export.csv", "allowed": {401}},
    {"name": "partner acknowledge gate", "method": "POST", "path": "/api/hostel/acknowledge",
     "body": b"{}", "headers": {"Content-Type": "application/json"}, "allowed": {401}},
    {"name": "partner login bad creds", "method": "POST", "path": "/api/hostel/login",
     "body": b'{"username":"smoke-no-such-user","password":"smoke-wrong"}',
     "headers": {"Content-Type": "application/json"}, "allowed": {401, 429}},
    # Staff page + APIs require the portal session (unauthenticated -> 302 to /login)
    {"name": "admin hostel page gate", "method": "GET", "path": "/admin/hostel-accommodation", "allowed": {302}},
    {"name": "admin partners gate", "method": "GET", "path": "/api/admin/hostel/partners", "allowed": {302}},
    {"name": "admin nurse-search gate", "method": "GET", "path": "/api/admin/hostel/nurse-search?q=xx", "allowed": {302}},
    {"name": "admin assignments gate", "method": "GET", "path": "/api/admin/hostel/assignments", "allowed": {302}},
    {"name": "admin audit gate", "method": "GET", "path": "/api/admin/hostel/audit", "allowed": {302}},
    {"name": "admin export gate", "method": "GET", "path": "/api/admin/hostel/export.csv", "allowed": {302}},
    {"name": "admin assignment create gate", "method": "POST", "path": "/api/admin/hostel/assignments/create",
     "body": b"{}", "headers": {"Content-Type": "application/json"}, "allowed": {302}},
    {"name": "admin agreement upload gate", "method": "POST", "path": "/api/admin/hostel/agreements/upload",
     "body": b"{}", "headers": {"Content-Type": "application/json"}, "allowed": {302}},
    {"name": "unknown hostel api 404", "method": "GET", "path": "/api/hostel/nope", "allowed": {401, 404}},
    # Existing neighbours must be unaffected
    {"name": "health", "method": "GET", "path": "/health", "allowed": {200}},
    {"name": "login page", "method": "GET", "path": "/login", "allowed": {200}},
    {"name": "aja reconciliation gate", "method": "GET", "path": "/admin/aja-reconciliation", "allowed": {302}},
]


def _request(base, method, path, body=None, headers=None):
    parts = urlsplit(base)
    conn_cls = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
    conn = conn_cls(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80), timeout=10)
    try:
        merged = {"User-Agent": "hostel-module-smoke/1.0", "Connection": "close"}
        merged.update(headers or {})
        conn.request(method, (parts.path.rstrip('/') or '') + path, body=body, headers=merged)
        resp = conn.getresponse()
        resp.read()
        return resp.status
    finally:
        conn.close()


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080'
    started = time.time()
    passed = failed = fivexx = 0
    for check in CHECKS:
        try:
            status = _request(base, check["method"], check["path"],
                              body=check.get("body"), headers=check.get("headers"))
        except Exception as exc:
            print(f'FAIL ERR {check["method"]:5} {check["path"]} -> {exc}')
            failed += 1
            continue
        is_5xx = status >= 500
        ok = (status in check["allowed"]) and not is_5xx
        if is_5xx:
            fivexx += 1
        if ok:
            passed += 1
        else:
            failed += 1
        print(f'{"PASS" if ok else "FAIL"} {status} {check["method"]:5} {check["path"]} ({check["name"]})')
    print(f'\nPassed: {passed}\nFailed: {failed}\n5xx failures: {fivexx}\nElapsed: {time.time() - started:.1f}s')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
