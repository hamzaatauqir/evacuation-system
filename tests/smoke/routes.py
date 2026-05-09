#!/usr/bin/env python3
"""Stdlib-only smoke checks for key public, admin, and API routes."""

from __future__ import annotations

import http.client
import sys
import time
from urllib.parse import urlsplit


CHECKS = [
    {"name": "root public home", "method": "GET", "path": "/", "allowed": {200, 302}},
    {"name": "health", "method": "GET", "path": "/health", "allowed": {200}},
    {"name": "route health", "method": "GET", "path": "/api/health/routes", "allowed": {200}},
    {"name": "login", "method": "GET", "path": "/login", "allowed": {200}},
    {"name": "admin css", "method": "GET", "path": "/static/css/cwa-admin.css", "allowed": {200}},
    {"name": "public tracking page", "method": "GET", "path": "/track-application", "allowed": {200}},
    {"name": "iraq tracking page", "method": "GET", "path": "/iraq-track-application", "allowed": {200}},
    {"name": "travel interest", "method": "GET", "path": "/travel-interest", "allowed": {200}},
    {"name": "public registration", "method": "GET", "path": "/embassy-registration", "allowed": {200}},
    {"name": "public registration alias register", "method": "GET", "path": "/register", "allowed": {200}},
    {"name": "public registration alias ksa-transit", "method": "GET", "path": "/ksa-transit", "allowed": {200}},
    {"name": "public registration alias transit-visa", "method": "GET", "path": "/transit-visa", "allowed": {200}},
    {"name": "public registration alias apply", "method": "GET", "path": "/apply", "allowed": {200}},
    {"name": "iraq public form", "method": "GET", "path": "/iraq-public-form", "allowed": {200}},
    {"name": "transit gateway", "method": "GET", "path": "/transit", "allowed": {200}},
    {"name": "nurses home", "method": "GET", "path": "/nurses", "allowed": {200}},
    {"name": "nurses register", "method": "GET", "path": "/nurses/register", "allowed": {200}},
    {"name": "nurses track", "method": "GET", "path": "/nurses/track", "allowed": {200}},
    {"name": "legal public page", "method": "GET", "path": "/legal-opf", "allowed": {200}},
    {"name": "death public page", "method": "GET", "path": "/death-cases", "allowed": {200}},
    {"name": "locating assistance", "method": "GET", "path": "/locating-assistance", "allowed": {200}},
    {"name": "community feedback", "method": "GET", "path": "/community-feedback", "allowed": {200}},
    {
        "name": "public track api",
        "method": "GET",
        "path": "/api/public-track?q=ZZTEST123&type=passport",
        "allowed": {200},
    },
    {
        "name": "iraq public track api",
        "method": "GET",
        "path": "/api/iraq-public-track?q=ZZTEST123&type=passport",
        "allowed": {200},
    },
    {
        "name": "public request track api",
        "method": "GET",
        "path": "/api/public-request-track?reference=CWA-FBK-00000",
        "allowed": {200},
    },
    {
        "name": "public charter track api",
        "method": "GET",
        "path": "/api/public-charter-track?q=ZZTEST123",
        "allowed": {200},
    },
    {
        "name": "forms webhook auth gate",
        "method": "GET",
        "path": "/api/webhook/forms?key=phase0-smoke",
        "allowed": {401},
    },
    {"name": "dashboard gate", "method": "GET", "path": "/dashboard", "allowed": {302}},
    {"name": "community welfare gate", "method": "GET", "path": "/admin/community-welfare", "allowed": {302}},
    {"name": "nurses admin gate", "method": "GET", "path": "/admin/nurses", "allowed": {302}},
    {"name": "welfare cases gate", "method": "GET", "path": "/admin/welfare-cases", "allowed": {302}},
    {"name": "aja reconciliation gate", "method": "GET", "path": "/admin/aja-reconciliation", "allowed": {302}},
    {
        "name": "nurses react admin gate",
        "method": "GET",
        "path": "/admin/nurses/pending-accounts",
        "allowed": {302},
    },
    {"name": "staff cases gate", "method": "GET", "path": "/staff/my-cases", "allowed": {302}},
    {"name": "fee collection gate", "method": "GET", "path": "/fee-collection", "allowed": {302}},
    {"name": "stats api gate", "method": "GET", "path": "/api/stats", "allowed": {302}},
    {
        "name": "notification counts api gate",
        "method": "GET",
        "path": "/api/admin/notification-counts",
        "allowed": {302},
    },
    {
        "name": "welfare users api gate",
        "method": "GET",
        "path": "/api/admin/welfare-users",
        "allowed": {302},
    },
    {
        "name": "counsellor branches api gate",
        "method": "GET",
        "path": "/api/admin/counsellor-branches",
        "allowed": {302},
    },
    {
        "name": "staff transfer destinations api gate",
        "method": "GET",
        "path": "/api/staff/transfer-destinations",
        "allowed": {302},
    },
    {
        "name": "cases transfer post gate",
        "method": "POST",
        "path": "/api/admin/cases/transfer",
        "allowed": {302},
        "body": b"{}",
        "headers": {"Content-Type": "application/json"},
    },
    {
        "name": "fee settlement put gate",
        "method": "PUT",
        "path": "/api/fee-settlement-update",
        "allowed": {302},
        "body": b"{}",
        "headers": {"Content-Type": "application/json"},
    },
    # ── 2FA safety baseline (Phase 0C) ─────────────────────────────
    # These checks confirm the 2FA flow does not throw 5xx.
    # Without a logged-in session the GET pages must redirect to /login.
    # We deliberately do NOT submit a real OTP — automated smoke tests
    # must never attempt 2FA verification.
    {
        "name": "2fa verify page (unauth → redirect)",
        "method": "GET",
        "path": "/auth/2fa/verify",
        "allowed": {302},
    },
    {
        "name": "2fa setup page (unauth → redirect)",
        "method": "GET",
        "path": "/auth/2fa/setup",
        "allowed": {302},
    },
    {
        "name": "admin security page (unauth → redirect)",
        "method": "GET",
        "path": "/admin/security",
        "allowed": {302},
    },
    {
        "name": "2fa verify api (unauth → 401 or redirect, never 5xx)",
        "method": "POST",
        "path": "/api/auth/2fa/verify",
        "allowed": {302, 400, 401},
        "body": b"{}",
        "headers": {"Content-Type": "application/json"},
    },
    {
        "name": "2fa setup api (unauth → 401 or redirect, never 5xx)",
        "method": "POST",
        "path": "/api/auth/2fa/setup",
        "allowed": {302, 400, 401},
        "body": b"{}",
        "headers": {"Content-Type": "application/json"},
    },
    {
        "name": "2fa backup codes regenerate api (unauth → 401 or redirect)",
        "method": "POST",
        "path": "/api/auth/2fa/backup-codes/regenerate",
        "allowed": {302, 400, 401},
        "body": b"{}",
        "headers": {"Content-Type": "application/json"},
    },
    {
        "name": "2fa admin reset api (unauth → 302/403, never 5xx)",
        "method": "POST",
        "path": "/api/admin/users/2fa-reset",
        "allowed": {302, 401, 403},
        "body": b"{}",
        "headers": {"Content-Type": "application/json"},
    },
]


def _join_base_path(base_path: str, route_path: str) -> str:
    prefix = "" if base_path in ("", "/") else base_path.rstrip("/")
    suffix = route_path if route_path.startswith("/") else "/" + route_path
    return prefix + suffix


def _request(base_url: str, check: dict, timeout: float) -> tuple[int, dict[str, str], bytes]:
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme or '<missing>'}")
    if not parsed.hostname:
        raise ValueError("Base URL must include a host")

    path = _join_base_path(parsed.path, check["path"])
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.hostname, port, timeout=timeout)
    headers = {
        "User-Agent": "phase0-route-smoke/1.0",
        "Connection": "close",
    }
    headers.update(check.get("headers", {}))
    body = check.get("body")

    try:
        conn.request(check["method"], path, body=body, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        return response.status, dict(response.getheaders()), payload
    finally:
        conn.close()


def _describe(check: dict) -> str:
    return f'{check["method"]} {check["path"]}'


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python3 tests/smoke/routes.py http://localhost:8080")
        return 2

    base_url = argv[1].rstrip("/")
    timeout = 10.0
    started = time.time()
    passes = []
    failures = []
    five_xx_failures = []

    print(f"Smoke target: {base_url}")
    print(f"Checks: {len(CHECKS)}")

    for check in CHECKS:
        label = _describe(check)
        try:
            status, headers, _payload = _request(base_url, check, timeout)
        except Exception as exc:
            message = f"ERROR {label} -> {exc}"
            failures.append(message)
            print(message)
            continue

        location = headers.get("Location", "")
        suffix = f" location={location}" if location else ""
        if 500 <= status <= 599:
            message = f"FAIL {status} {label} expected {sorted(check['allowed'])}{suffix}"
            failures.append(message)
            five_xx_failures.append(message)
            print(message)
            continue
        if status not in check["allowed"]:
            message = f"FAIL {status} {label} expected {sorted(check['allowed'])}{suffix}"
            failures.append(message)
            print(message)
            continue

        message = f"PASS {status} {label}{suffix}"
        passes.append(message)
        print(message)

    elapsed = time.time() - started
    print(f"Passed: {len(passes)}")
    print(f"Failed: {len(failures)}")
    print(f"5xx failures: {len(five_xx_failures)}")
    print(f"Elapsed: {elapsed:.2f}s")

    if failures:
        if five_xx_failures:
            print("5xx failure details:")
            for item in five_xx_failures:
                print(item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
