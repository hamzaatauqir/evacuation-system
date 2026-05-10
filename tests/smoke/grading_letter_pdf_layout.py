#!/usr/bin/env python3
"""Smoke checks for the grading-letter preview / final PDF layout.

Stdlib-only. This test focuses on the canonical HTML renderer, the final-PDF
generation path, and the admin download route behaviour. It avoids requiring
PyMuPDF at runtime while still checking the exact source wiring that feeds the
final PDF.
"""

from __future__ import annotations

import inspect
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import server  # noqa: E402


LETTER = {
    'reference_line': 'No. Pol-II/18/2021 (Attestation)',
    'applicant_name': 'Saadia Bibi',
    'certificate_line_1': 'This is to certify that according to the documents produced in this Embassy,',
    'certificate_line_2': 'daughter of Muhammad Aslam and holding Pakistani Passport No. AB1234567',
    'certificate_line_3': 'passed the examination of:',
    'qualification_subtitle': '',
    'degree_title': 'Bachelor of Science in Nursing',
    'identifier_label': 'Registration No.',
    'identifier_value': '2009-SWC-0043-UHS',
    'institute': 'Saida Waheed FMH College of Nursing, Lahore.',
    'university': 'University of Health Sciences, Lahore.',
    'year_of_passing': '2014',
    'final_percentage': '80.44',
    'final_grade_label': 'Excellent',
    'final_result_text': '80.44% "Excellent"',
    'qualifications': [],
    'footer_telephone': '+965-2225-6655',
    'footer_fax': '+965-2225-6666',
    'footer_email': 'parepkuwait@mofa.gov.pk',
    'passport_number': 'AB1234567',
    'warnings': [],
    'generation_blockers': [],
    'can_generate_official': True,
}


def main():
    print("Loading server.py …")

    fail = 0

    def expect(label, ok):
        nonlocal fail
        print(('  ✓' if ok else '  ✗ FAIL'), label)
        if not ok:
            fail += 1

    print()
    print("Test 1: final canonical HTML uses compact official layout with no watermark")
    final_html = server._gl_preview_html(LETTER, include_watermark=False, pdf_safe=True)
    expect("final HTML lacks 'NOT OFFICIAL'", 'NOT OFFICIAL' not in final_html)
    expect("final HTML lacks 'PREVIEW ONLY'", 'PREVIEW ONLY' not in final_html)
    expect("final HTML uses Times font stack", '"Times New Roman",Times,serif' in final_html)
    expect("final HTML has official heading", 'Embassy of Islamic Republic of Pakistan<br>Kuwait' in final_html)
    expect("final HTML has Arabic heading", 'سفارة جمهورية باكستان الإسلامية' in final_html)
    expect("final HTML has title", 'TO WHOM IT MAY CONCERN' in final_html)
    expect("final HTML has footer telephone", 'Telephone: +965-2225-6655' in final_html)
    expect("final HTML has footer fax", 'Fax: +965-2225-6666' in final_html)
    expect("final HTML has footer email", 'Email: parepkuwait@mofa.gov.pk' in final_html)

    print()
    print("Test 2: preview keeps watermark while using the same canonical letter shell")
    preview_html = server._gl_preview_html(
        LETTER,
        include_watermark=True,
        preview_title='Preview',
        pdf_safe=False,
    )
    expect("preview has 'NOT OFFICIAL FOR MOH USE'", 'NOT OFFICIAL FOR MOH USE' in preview_html)
    expect("preview has 'PREVIEW ONLY'", 'PREVIEW ONLY' in preview_html)
    expect("preview keeps heading", 'Embassy of Islamic Republic of Pakistan<br>Kuwait' in preview_html)
    expect("preview keeps footer", 'Telephone: +965-2225-6655' in preview_html)

    print()
    print("Test 3: qualification block uses stable table markup for preview and final")
    multi_letter = dict(LETTER)
    multi_letter['qualifications'] = [
        {
            'qualification_label': 'Bachelor of Science in Nursing',
            'identifier_type_label': 'Registration No.',
            'identifier_value': '2009-SWC-0043-UHS',
            'institute': 'Saida Waheed FMH College of Nursing, Lahore.',
            'university': 'University of Health Sciences, Lahore.',
            'year_of_passing': '2014',
            'final_percentage': '80.44',
            'final_grade_label': 'Excellent',
            'final_result_text': '80.44% "Excellent"',
        },
        {
            'qualification_label': 'Diploma in Cardiac Care',
            'identifier_type_label': 'Roll No.',
            'identifier_value': 'CC-22-018',
            'institute': 'Punjab Institute of Cardiology',
            'university': 'University of Health Sciences, Lahore.',
            'year_of_passing': '2017',
            'final_percentage': '76',
            'final_grade_label': 'Very Good',
            'final_result_text': '76% "Very Good"',
        },
    ]
    multi_final = server._gl_preview_html(multi_letter, include_watermark=False, pdf_safe=True)
    multi_preview = server._gl_preview_html(multi_letter, include_watermark=True, pdf_safe=False)
    for label, html in (
        ("final uses qualification table", multi_final),
        ("preview uses qualification table", multi_preview),
    ):
        expect(label, '<table class="gl-qualification-table gl-multi-qualification-list"' in html)
        expect(f"{label} has left cell", 'class="gl-qualification-table__left"' in html)
        expect(f"{label} has right cell", 'class="gl-qualification-table__right"' in html)
    expect("final PDF-safe identifiers use non-breaking hyphens", '2009‑SWC‑0043‑UHS' in multi_final)
    expect("preview keeps readable ASCII hyphens", '2009-SWC-0043-UHS' in multi_preview)

    print()
    print("Test 4: final PDF builder uses the canonical PDF-safe renderer and A4 story box")
    build_src = inspect.getsource(server._gl_build_pdf_bytes)
    expect("calls _gl_preview_html in PDF path", '_gl_preview_html(letter, include_watermark=False, pdf_safe=True)' in build_src)
    expect("uses updated story rect", 'fitz.Rect(12, 10, 583, 832)' in build_src)

    print()
    print("Test 5: final letter route supports inline print and forced regeneration")
    handler_src = inspect.getsource(server.Handler.do_GET)
    expect("reads disposition query param", "params.get('disposition')" in handler_src)
    expect("reads force query param", "params.get('force')" in handler_src)
    expect("sets inline/attachment Content-Disposition", "f'{disposition}; filename=\"{fname}\"'" in handler_src)
    expect("passes force_regenerate into api_admin_gl_letter", 'force_regenerate=force_regenerate' in handler_src)

    print()
    print("Test 6: regeneration helper still logs detailed failures and uses disk existence checks")
    letter_src = inspect.getsource(server.api_admin_gl_letter)
    generate_src = inspect.getsource(server._gl_generate_letter_file)
    expect("api_admin_gl_letter exposes force_regenerate option", 'force_regenerate=False' in letter_src)
    expect("logs detailed fallback context", 'Download fallback app_id=' in letter_src)
    expect("logs traceback on regeneration failure", 'traceback.print_exc()' in letter_src)
    expect("checks os.path.exists before serving", 'os.path.exists' in letter_src)
    expect("allows issued-row regeneration explicitly", 'allow_issued=True' in letter_src)
    expect("_gl_generate_letter_file ensures output dir exists", 'mkdir(parents=True, exist_ok=True)' in generate_src)
    expect("_gl_generate_letter_file writes bytes to returned path", 'target.write_bytes(pdf_bytes)' in generate_src)

    print()
    print("Test 7: api_admin_gl_letter regenerates an issued row with no stored file")
    generated_rel = 'generated_letters/GL-2026-000111.pdf'
    generated_abs = os.path.join(REPO_ROOT, generated_rel)
    generated_bytes = b'%PDF-1.4 smoke regeneration test'
    os.makedirs(os.path.dirname(generated_abs), exist_ok=True)
    if os.path.exists(generated_abs):
        os.remove(generated_abs)

    class DummyDB:
        def __init__(self):
            self.executed = []
            self.commits = 0
            self.rollbacks = 0
            self.closed = 0

        def execute(self, query, params):
            self.executed.append((query, list(params)))
            return self

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed += 1

    def run_letter_flow(initial_rel, build_bytes, force_regenerate=False, seed_existing=False):
        dummy_db = DummyDB()
        app_state = {'letter_pdf_path': initial_rel}
        fetch_calls = {'count': 0}
        original_feature_enabled = server._gl_feature_enabled
        original_can_view = server.gl_user_can_view
        original_can_manage = server.gl_user_can_manage
        original_get_db = server.get_db
        original_fetch = server._gl_fetch_application
        original_letter_context = server._gl_letter_context
        original_build_pdf = server._gl_build_pdf_bytes

        if seed_existing:
            with open(generated_abs, 'wb') as handle:
                handle.write(b'OLD PDF BYTES')
        elif os.path.exists(generated_abs):
            os.remove(generated_abs)

        def fake_fetch(_db, _app_id):
            fetch_calls['count'] += 1
            return {
                'id': 111,
                'status': 'ISSUED',
                'ref_no': 'GL-2026-000111',
                'letter_pdf_path': app_state['letter_pdf_path'],
            }

        try:
            server._gl_feature_enabled = lambda: True
            server.gl_user_can_view = lambda _user: True
            server.gl_user_can_manage = lambda _user: True
            server.get_db = lambda: dummy_db
            server._gl_fetch_application = fake_fetch
            server._gl_letter_context = lambda app: {
                'application': dict(app),
                'generation_blockers': [],
            }
            server._gl_build_pdf_bytes = lambda _app: build_bytes

            def tracked_execute(query, params):
                dummy_db.executed.append((query, list(params)))
                if 'UPDATE gl_applications SET letter_pdf_path' in query:
                    app_state['letter_pdf_path'] = params[0]
                return dummy_db

            dummy_db.execute = tracked_execute

            body_pdf, fname, err = server.api_admin_gl_letter(
                '111',
                {'role': 'admin', 'user': 'smoke'},
                force_regenerate=force_regenerate,
            )
            return {
                'body_pdf': body_pdf,
                'fname': fname,
                'err': err,
                'fetch_calls': fetch_calls['count'],
                'app_state': dict(app_state),
                'dummy_db': dummy_db,
            }
        finally:
            server._gl_feature_enabled = original_feature_enabled
            server.gl_user_can_view = original_can_view
            server.gl_user_can_manage = original_can_manage
            server.get_db = original_get_db
            server._gl_fetch_application = original_fetch
            server._gl_letter_context = original_letter_context
            server._gl_build_pdf_bytes = original_build_pdf

    first_result = run_letter_flow('', generated_bytes)
    expect("application row fetched before, during, and after regeneration", first_result['fetch_calls'] >= 3)
    expect("returns regenerated PDF bytes", first_result['body_pdf'] == generated_bytes)
    expect("returns no error on regenerated PDF", first_result['err'] is None)
    expect("writes generated PDF to disk", os.path.exists(generated_abs))
    expect("persists regenerated letter path", first_result['app_state']['letter_pdf_path'] == generated_rel)
    expect("commits regenerated letter path update", first_result['dummy_db'].commits == 1)
    expect("returns expected filename", first_result['fname'] == 'GL-2026-000111.pdf')

    print()
    print("Test 8: force=1 regenerates even when a stale PDF already exists")
    fresh_bytes = b'%PDF-1.4 forced regeneration bytes'
    second_result = run_letter_flow(generated_rel, fresh_bytes, force_regenerate=True, seed_existing=True)
    overwritten_matches = False
    if os.path.exists(generated_abs):
        with open(generated_abs, 'rb') as handle:
            overwritten_matches = handle.read() == fresh_bytes
    expect("force regeneration returns fresh bytes", second_result['body_pdf'] == fresh_bytes)
    expect("force regeneration returns no error", second_result['err'] is None)
    expect("force regeneration updates stored path", second_result['app_state']['letter_pdf_path'] == generated_rel)
    expect("force regeneration commits path update", second_result['dummy_db'].commits == 1)
    expect("force regeneration overwrites stale file", overwritten_matches)

    if os.path.exists(generated_abs):
        os.remove(generated_abs)

    print()
    print(f'FAIL count: {fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
