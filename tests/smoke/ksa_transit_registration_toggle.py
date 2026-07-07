#!/usr/bin/env python3
"""Smoke checks for the KSA Transit Visa new-registration open/pause switch."""

from __future__ import annotations

import inspect
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import server  # noqa: E402


class _DummyPublicRenderer:
    def inject_public_route_context(self, html: str) -> str:
        replacements = {
            "__BASE_PATH__": "",
            "__KSA_TRACK_URL__": "/track-application",
            "__KSA_SUCCESS_URL__": "/embassy-registration/success",
        }
        for key, value in replacements.items():
            html = html.replace(key, value)
        return html


def _create_minimal_db(db_path: Path) -> None:
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    try:
        db.executescript(
            """
            CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                record_id INTEGER,
                user TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE evacuees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                passport TEXT,
                visa_status TEXT DEFAULT 'Pending',
                travel_status TEXT DEFAULT 'Pending',
                mofa_status TEXT DEFAULT '',
                mofa_ksa_status TEXT DEFAULT '',
                fee_status TEXT DEFAULT 'pending',
                embassy_letter_issued_at TEXT DEFAULT '',
                embassy_letter_print_count INTEGER DEFAULT 0,
                applicant_travel_date TEXT,
                applicant_airline TEXT,
                applicant_flight_number TEXT,
                applicant_ticket_number TEXT,
                applicant_departure_from TEXT,
                applicant_arrival_to TEXT,
                applicant_border_route TEXT,
                applicant_travel_remarks TEXT,
                applicant_travel_submitted_at TIMESTAMP,
                applicant_travel_updated_at TIMESTAMP,
                applicant_travel_locked INTEGER DEFAULT 0,
                applicant_travel_source TEXT DEFAULT '',
                updated_at TIMESTAMP,
                updated_by TEXT
            );
            """
        )
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            [server.KSA_TRANSIT_REGISTRATION_SETTING_KEY, "1"],
        )
        db.execute(
            """INSERT INTO evacuees
               (id, name, passport, visa_status, travel_status, fee_status)
               VALUES (1, 'Smoke Applicant', 'AB1234567', 'Approved', 'Visa Obtained', 'pending')"""
        )
        db.commit()
    finally:
        db.close()


def _count_ev_rows(db_path: Path) -> int:
    db = sqlite3.connect(str(db_path))
    try:
        return int(db.execute("SELECT COUNT(*) FROM evacuees").fetchone()[0])
    finally:
        db.close()


def main() -> int:
    print("Loading KSA Transit registration toggle smoke checks ...")
    fail = 0

    def expect(label: str, ok: bool) -> None:
        nonlocal fail
        print(("  ✓" if ok else "  ✗ FAIL"), label)
        if not ok:
            fail += 1

    get_src = inspect.getsource(server.Handler.do_GET)
    post_src = inspect.getsource(server.Handler.do_POST)
    render_src = inspect.getsource(server.Handler.render_public_ksa_registration_page)
    template_src = server.PUBLIC_REGISTER_PAGE
    app_src = server.MAIN_APP

    print()
    print("Test 1: public and admin UI wiring")
    expect(
        "public closed notice text is present",
        "KSA Transit Visa registration is currently closed." in template_src
        and "New applications are not being accepted at this time." in template_src
        and "submit or update flight details where required." in template_src,
    )
    expect("public submit button has close/open placeholder", "__KSA_REG_SUBMIT_DISABLED_ATTR__" in template_src)
    expect("public JS checks open flag before submit", "KSA_REGISTRATION_OPEN" in template_src and "KSA_REGISTRATION_CLOSED_MESSAGE" in template_src)
    expect("public render injects current setting", "is_ksa_transit_registration_open()" in render_src)
    expect("admin control label exists", "Accept New KSA Transit Visa Registrations" in app_src)
    expect("admin open/pause buttons exist", "Open Registration" in app_src and "Pause Registration" in app_src)
    expect("admin warning preserves existing applicants", "This will not affect tracking, flight-number submission, or already registered applicants." in app_src)

    print()
    print("Test 2: API routes and source gates")
    expect("GET admin setting endpoint exists", "path == '/api/admin/settings/ksa-transit-registration'" in get_src)
    expect("POST admin setting endpoint exists", "path == '/api/admin/settings/ksa-transit-registration'" in post_src)
    expect("new registration submit checks KSA gate", "ksa_transit_registration_block_response_if_closed()" in post_src)
    expect("new registration gate runs before insert", post_src.index("ksa_transit_registration_block_response_if_closed()") < post_src.index("result = api_save_record(data, 'public')"))
    track_slice = get_src[get_src.index("elif path == '/api/public-track':"):get_src.index("elif path in ('/travel-interest'", get_src.index("elif path == '/api/public-track':"))]
    expect("public tracking API is not gated by registration setting", "ksa_transit_registration" not in track_slice)
    travel_slice = post_src[post_src.index("if path == '/api/public-travel-details':"):post_src.index("if path == '/api/stay-confirm':", post_src.index("if path == '/api/public-travel-details':"))]
    expect("flight-detail update API is not gated by registration setting", "ksa_transit_registration" not in travel_slice)
    expect("flight-detail route still calls existing helper", "api_public_travel_details_submit(data, self.client_address[0])" in travel_slice)

    print()
    print("Test 3: functional setting toggle, audit, and persistence")
    original_db_path = server.DB_PATH
    original_wal = getattr(server, "_DB_WAL_APPLIED", False)
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db_path = Path(tmpdir) / "ksa-transit-toggle-smoke.db"
        _create_minimal_db(temp_db_path)
        server.DB_PATH = temp_db_path
        server._DB_WAL_APPLIED = False
        try:
            expect("default setting is open", server.is_ksa_transit_registration_open())
            expect("open setting allows new registration path", server.ksa_transit_registration_block_response_if_closed() is None)

            admin_user = {"user": "smoke_admin", "role": "admin", "user_id": 42}
            paused = server.api_admin_update_ksa_transit_registration_setting(
                {"open": False, "reason": "smoke pause"},
                admin_user,
            )
            expect("admin can pause registration", paused.get("success") and paused.get("open") is False)
            blocked = server.ksa_transit_registration_block_response_if_closed()
            expect("closed setting blocks new registration with friendly message", bool(blocked) and blocked.get("registration_closed") and server.KSA_TRANSIT_REGISTRATION_CLOSED_MESSAGE in blocked.get("error", ""))
            closed_html = server.Handler.render_public_ksa_registration_page(_DummyPublicRenderer())
            expect("closed public page shows red notice", 'id="ksaRegistrationClosedNotice"' in closed_html and "display:block" in closed_html)
            expect("closed public page disables submit", 'id="submitBtn" disabled aria-disabled="true"' in closed_html)
            expect("closed public page has no KSA placeholders left", "__KSA_REG_" not in closed_html and "__KSA_REGISTRATION_" not in closed_html)
            before_count = _count_ev_rows(temp_db_path)
            _ = server.ksa_transit_registration_block_response_if_closed()
            after_count = _count_ev_rows(temp_db_path)
            expect("closed new-registration gate does not create a record", before_count == after_count == 1)

            db = sqlite3.connect(str(temp_db_path))
            db.row_factory = sqlite3.Row
            try:
                setting_row = db.execute(
                    "SELECT value FROM settings WHERE key = ?",
                    [server.KSA_TRANSIT_REGISTRATION_SETTING_KEY],
                ).fetchone()
                audit_row = db.execute(
                    "SELECT * FROM audit_log WHERE action = 'ksa_transit_registration_setting_update' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                details = json.loads(audit_row["details"]) if audit_row else {}
                expect("paused setting is persisted", setting_row and setting_row["value"] == "0")
                expect("audit row records admin username", audit_row and audit_row["user"] == "smoke_admin" and details.get("admin_username") == "smoke_admin")
                expect("audit row records old/new values and reason", details.get("old_value") == "1" and details.get("new_value") == "0" and details.get("reason") == "smoke pause")
                expect("audit row includes timestamp and user id", bool(details.get("timestamp")) and details.get("admin_user_id") == 42)
            finally:
                db.close()

            server._DB_WAL_APPLIED = False
            expect("closed setting persists after simulated restart", server.get_portal_setting(server.KSA_TRANSIT_REGISTRATION_SETTING_KEY, "1") == "0")

            reopened = server.api_admin_update_ksa_transit_registration_setting(
                {"value": "open", "reason": "smoke reopen"},
                admin_user,
            )
            expect("admin can reopen registration", reopened.get("success") and reopened.get("open") is True)
            expect("reopened setting allows new registration path", server.ksa_transit_registration_block_response_if_closed() is None)
            open_html = server.Handler.render_public_ksa_registration_page(_DummyPublicRenderer())
            expect("open public page hides closed notice", 'id="ksaRegistrationClosedNotice"' in open_html and "display:none" in open_html)
            expect("open public page leaves submit enabled", 'id="submitBtn" disabled' not in open_html)

            server.set_portal_setting(server.KSA_TRANSIT_REGISTRATION_SETTING_KEY, "0")
            token = server._public_tracking_token(1, "AB1234567")
            travel_result = server.api_public_travel_details_submit(
                {
                    "record_id": 1,
                    "tracking_token": token,
                    "travel_date": "2026-06-01",
                    "airline": "Smoke Air",
                    "flight_number": "SM123",
                    "ticket_number": "PNR123",
                    "departure_from": "Kuwait",
                    "arrival_to": "Pakistan",
                    "border_route": "Khafji Border",
                    "remarks": "Smoke test update while registration is paused",
                },
                "127.0.0.1",
            )
            expect("flight number update still works while registration is paused", bool(travel_result.get("success")))
            db = sqlite3.connect(str(temp_db_path))
            db.row_factory = sqlite3.Row
            try:
                row = db.execute("SELECT applicant_flight_number, applicant_airline FROM evacuees WHERE id = 1").fetchone()
                expect("flight details persisted while paused", row["applicant_flight_number"] == "SM123" and row["applicant_airline"] == "Smoke Air")
            finally:
                db.close()
        finally:
            server.DB_PATH = original_db_path
            server._DB_WAL_APPLIED = original_wal

    print()
    print(f"FAIL count: {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
