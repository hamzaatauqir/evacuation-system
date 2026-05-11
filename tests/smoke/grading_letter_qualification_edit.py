#!/usr/bin/env python3
"""Smoke checks for grading-letter qualification edit/verify/override flow."""

from __future__ import annotations

import inspect
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import server  # noqa: E402


def _create_minimal_db(db_path: Path) -> None:
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    try:
        db.execute(
            """CREATE TABLE nurse_registrations (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               reference_id TEXT DEFAULT '',
               full_name TEXT DEFAULT '',
               father_name TEXT DEFAULT '',
               passport_number TEXT DEFAULT '',
               cnic TEXT DEFAULT '',
               civil_id TEXT DEFAULT '',
               mobile TEXT DEFAULT '',
               mobile_full TEXT DEFAULT '',
               whatsapp_full TEXT DEFAULT '',
               email TEXT DEFAULT '',
               mton_number TEXT DEFAULT '',
               gender TEXT DEFAULT '',
               hospital TEXT DEFAULT '',
               hospital_workplace TEXT DEFAULT '',
               hospital_or_medical_center TEXT DEFAULT ''
            )"""
        )
        server._init_grading_letter_db(db)
        db.execute(
            """INSERT INTO nurse_registrations
               (id, reference_id, full_name, father_name, passport_number, email)
               VALUES (1, 'NR-1', 'Smoke Nurse', 'Smoke Father', 'AB1234567', 'smoke@example.test')"""
        )
        db.execute(
            """INSERT INTO gl_applications
               (id, ref_no, nurse_id, status, qualification_code, mode,
                total_marks, obtained_marks, computed_percentage,
                final_percentage, final_grade_label, submitted_at)
               VALUES (1, 'GL-2026-SMOKE', 1, 'UNDER_REVIEW', 'BSN_4Y',
                'MARKS', 500, 400, 80, 80, 'Excellent', CURRENT_TIMESTAMP)"""
        )
        db.execute(
            """INSERT INTO gl_application_qualifications
               (id, application_id, qualification_code, qualification_label,
                mode, total_marks, obtained_marks, computed_percentage,
                final_percentage, final_grade_label, verification_status,
                sort_order)
               VALUES (1, 1, 'BSN_4Y', 'BSN Nursing 4 Years', 'MARKS',
                '500', '400', '80', '80', 'Excellent', 'VERIFIED', 0)"""
        )
        db.commit()
    finally:
        db.close()


def main() -> int:
    print("Loading grading-letter qualification edit smoke checks ...")
    fail = 0

    def expect(label: str, ok: bool) -> None:
        nonlocal fail
        print(("  ✓" if ok else "  ✗ FAIL"), label)
        if not ok:
            fail += 1

    template_path = os.path.join(REPO_ROOT, "templates", "admin_nurse_grading_letters.html")
    with open(template_path, "r", encoding="utf-8") as handle:
        template_src = handle.read()
    action_src = inspect.getsource(server.api_admin_gl_action)
    validator_src = inspect.getsource(server._gl_validate_qualification_edit_payload)
    handler_src = inspect.getsource(server.Handler.do_POST)

    print()
    print("Test 1: template still wires the qualification buttons to the API")
    expect("Save Qualification button exists", "Save Qualification" in template_src)
    expect("Mark Verified button exists", "Mark Verified" in template_src)
    expect("Save button is not a form submit", 'type="button" onclick="saveSelectedQualification()"' in template_src)
    expect("Verify button is not a form submit", 'type="button" onclick="verifySelectedQualification()"' in template_src)
    expect("saveSelectedQualification function exists once", template_src.count("function saveSelectedQualification(") == 1)
    expect("verifySelectedQualification function exists once", template_src.count("function verifySelectedQualification(") == 1)
    expect("save posts to /api/admin/gl/action", "/api/admin/gl/action" in template_src)
    expect("payload includes marks fields", "total_marks" in template_src and "obtained_marks" in template_src)
    expect("payload includes percentage/GPA fields", "entered_percentage" in template_src and "entered_gpa" in template_src)
    expect("payload includes backward-compatible aliases", "percentage:enteredPercentage" in template_src and "gpa:enteredGpa" in template_src)

    print()
    print("Test 2: backend route and role gates support operator/admin workflow")
    expect("POST route exists", "path == '/api/admin/gl/action'" in handler_src)
    expect("action API uses grading-letter manage gate", "gl_user_can_manage(user)" in action_src)
    expect("edit qualification action exists", "elif action == 'edit-qualification':" in action_src)
    expect("verify qualification action exists", "elif action == 'verify-qualification':" in action_src)
    expect("operator role is allowed to manage", server.gl_user_can_manage({"role": "operator", "user": "smoke"}))
    expect("admin role is allowed to manage", server.gl_user_can_manage({"role": "admin", "user": "smoke"}))
    expect("issued rows remain locked for qualification edits", server.GL_QUALIFICATION_EDIT_LOCKED_STATUSES == {"ISSUED", "REJECTED", "CANCELLED"})
    expect("letter-generated rows can be verified before issue", "LETTER_GENERATED" in server.GL_QUALIFICATION_VERIFY_ALLOWED_STATUSES)
    expect("action API commits successful updates", "db.commit()" in action_src)

    print()
    print("Test 3: marks save accepts aliases and does not require override reason")
    expect("qualification validator accepts marks mode alias", "marks_mode" in validator_src)
    expect("qualification validator accepts percent alias", "'percentage'" in validator_src and "'percent'" in validator_src)
    expect("qualification validator accepts GPA alias", "'gpa'" in validator_src and "'cgpa'" in validator_src)
    expect("qualification validator is not tied to override reason", "override_reason" not in validator_src)
    expect("override action still requires reason", "Override reason is required." in action_src)

    print()
    print("Test 4: functional edit, verify, and override against a temporary DB")
    original_db_path = server.DB_PATH
    original_wal = getattr(server, "_DB_WAL_APPLIED", False)
    user = {"role": "operator", "user": "smoke_operator"}
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db_path = Path(tmpdir) / "grading-letter-smoke.db"
        _create_minimal_db(temp_db_path)
        server.DB_PATH = temp_db_path
        server._DB_WAL_APPLIED = False
        try:
            save_result = server.api_admin_gl_action(
                {
                    "id": 1,
                    "action": "edit_qualification",
                    "qualification_id": 1,
                    "marks_mode": "PERCENT",
                    "percentage": "88.5",
                },
                user,
            )
            expect("ordinary qualification save succeeds without override reason", bool(save_result.get("success")))

            db = sqlite3.connect(str(temp_db_path))
            db.row_factory = sqlite3.Row
            try:
                q = db.execute("SELECT * FROM gl_application_qualifications WHERE id = 1").fetchone()
                app = db.execute("SELECT * FROM gl_applications WHERE id = 1").fetchone()
                expect("qualification mode updated from alias", q["mode"] == "PERCENT")
                expect("qualification percentage saved", q["entered_percentage"] == "88.5")
                expect("qualification computed/final result saved", q["computed_percentage"] == "88.5" and q["final_percentage"] == "88.5")
                expect("qualification requires reverification after marks correction", q["verification_status"] == "CORRECTED_BY_OPERATOR")
                expect("parent flat fields synced from first qualification", str(app["final_percentage"]) == "88.5")
            finally:
                db.close()

            verify_result = server.api_admin_gl_action(
                {"id": 1, "action": "verify_qualification", "qualification_id": 1},
                user,
            )
            expect("mark verified succeeds", bool(verify_result.get("success")))

            db = sqlite3.connect(str(temp_db_path))
            db.row_factory = sqlite3.Row
            try:
                q = db.execute("SELECT verification_status, verified_by FROM gl_application_qualifications WHERE id = 1").fetchone()
                expect("qualification row marked verified", q["verification_status"] == "VERIFIED")
                expect("verified_by is recorded", q["verified_by"] == "smoke_operator")
            finally:
                db.close()

            missing_reason = server.api_admin_gl_action(
                {"id": 1, "action": "override", "final_percentage": "72.4", "grade": "Good"},
                user,
            )
            expect("override without reason is rejected", not missing_reason.get("success") and "reason" in missing_reason.get("error", "").lower())

            override_result = server.api_admin_gl_action(
                {
                    "id": 1,
                    "action": "override",
                    "final_percentage": "72.4",
                    "result_grade": "Good",
                    "override_reason": "Transcript reviewed by operator",
                },
                user,
            )
            expect("override with reason succeeds", bool(override_result.get("success")))

            db = sqlite3.connect(str(temp_db_path))
            db.row_factory = sqlite3.Row
            try:
                app = db.execute("SELECT final_percentage, final_grade_label, override_reason FROM gl_applications WHERE id = 1").fetchone()
                q = db.execute("SELECT final_percentage, final_grade_label FROM gl_application_qualifications WHERE id = 1").fetchone()
                expect("parent final result override saved", str(app["final_percentage"]) == "72.4" and app["final_grade_label"] == "Good")
                expect("override reason saved on parent", app["override_reason"] == "Transcript reviewed by operator")
                expect("first qualification mirrors final override", q["final_percentage"] == "72.4" and q["final_grade_label"] == "Good")
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
