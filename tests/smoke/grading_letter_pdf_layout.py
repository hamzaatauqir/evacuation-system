#!/usr/bin/env python3
"""Focused smoke test for the grading-letter PDF/preview parity fix.

Stdlib-only. Imports server.py and exercises _gl_preview_html() in three
modes:

  preview  — include_watermark=True, pdf_safe=False  (browser preview)
  final    — include_watermark=False, pdf_safe=True  (the official PDF)
  legacy   — include_watermark=False, pdf_safe=False (pre-fix behaviour)

Asserts the user-listed structural requirements without invoking PyMuPDF
(which may not be installed in the sandbox). The HTML content is the
single source of truth that flows into insert_htmlbox; verifying it
covers the layout/watermark requirements directly.

Usage:
    python3 tests/smoke/grading_letter_pdf_layout.py
Exits 0 on success, 1 on first failure.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import server  # noqa: E402

# Letter context shaped exactly like _gl_letter_context() output, with the
# fields _gl_preview_html actually reads.
LETTER = {
    'reference_line': 'Ref. No. GL-2026-000111',
    'applicant_name': 'Saadia Bibi',
    'certificate_line_1': 'This is to certify that according to the documents produced in this Embassy,',
    'certificate_line_2': 'daughter of Muhammad Aslam and holding Pakistani Passport No. AB1234567',
    'certificate_line_3': '',
    'qualification_subtitle': '',
    'degree_title': 'Bachelor of Science in Nursing',
    'identifier_label': 'Registration No.',
    'identifier_value': '2009-SWC-0043-UHS',
    'institute': 'Saida Waheed FMH College of Nursing, Lahore.',
    'university': 'University of Health Sciences, Lahore.',
    'year_of_passing': '2014',
    'final_result_text': '80.44% "Excellent"',
    'qualifications': [],   # single-qualification path
    'footer_telephone': '+965-2225-6655',
    'footer_fax': '+965-2225-6666',
    'footer_email': 'parepkuwait@mofa.gov.pk',
    'reference_no': 'GL-2026-000111',
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
        if not ok: fail += 1

    # -- 1. Final PDF HTML: no watermark, no NOT OFFICIAL, no PREVIEW ONLY ----
    print()
    print("Test 1: final PDF HTML — no watermark text")
    final_html = server._gl_preview_html(LETTER, include_watermark=False, pdf_safe=True)
    expect("final HTML lacks 'NOT OFFICIAL'",   'NOT OFFICIAL' not in final_html)
    expect("final HTML lacks 'PREVIEW ONLY'",   'PREVIEW ONLY' not in final_html)
    expect("final HTML has gl-pdf-safe class",  'gl-pdf-safe' in final_html)

    # -- 2. Final PDF HTML contains the user-listed text ----------------------
    print()
    print("Test 2: final PDF HTML contains all required content")
    expected_strings = [
        'TO WHOM IT MAY CONCERN',
        'Saadia Bibi',
        'AB1234567',
        'Bachelor of Science in Nursing',
        # Registration line in PDF mode uses non-breaking hyphens (‑),
        # so don't search for ASCII hyphens.
        'Registration No.',
        '2009‑SWC‑0043‑UHS',
        'Saida Waheed FMH College of Nursing',
        'University of Health Sciences',
        '2014',
        '80.44%',
        'Excellent',
    ]
    for needle in expected_strings:
        expect(f"contains: {needle!r}", needle in final_html)

    # -- 3. Preview HTML keeps watermark + ASCII hyphens ----------------------
    print()
    print("Test 3: preview HTML still has watermark + readable hyphens")
    preview_html = server._gl_preview_html(
        LETTER, include_watermark=True, preview_title='Preview',
        pdf_safe=False
    )
    expect("preview has 'NOT OFFICIAL FOR MOH USE'",   'NOT OFFICIAL FOR MOH USE' in preview_html)
    expect("preview has 'PREVIEW ONLY'",               'PREVIEW ONLY' in preview_html)
    expect("preview keeps ASCII registration hyphens", '2009-SWC-0043-UHS' in preview_html)

    # -- 4. Multi-qualification block uses real <table> in pdf_safe mode -----
    print()
    print("Test 4: multi-qualification block uses real <table> in pdf_safe mode")
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
        },
    ]
    final_multi = server._gl_preview_html(multi_letter, include_watermark=False, pdf_safe=True)
    expect("uses <table class='gl-multi-qualification-list'>",
           "<table class=\"gl-multi-qualification-list\"" in final_multi)
    expect("uses <tr class='gl-multi-qualification-row'>",
           "<tr class=\"gl-multi-qualification-row\"" in final_multi)
    expect("uses <td class='gl-multi-qualification-left'>",
           "<td class=\"gl-multi-qualification-left\"" in final_multi)
    expect("does NOT keep div-based table-row in pdf_safe",
           "<div class=\"gl-multi-qualification-row\"" not in final_multi)

    # -- 5. Same multi-qualification preview keeps div-based layout ---------
    print()
    print("Test 5: preview multi-qualification still uses div-based layout")
    preview_multi = server._gl_preview_html(multi_letter, include_watermark=True, pdf_safe=False)
    expect("preview uses <div class='gl-multi-qualification-row'>",
           "<div class=\"gl-multi-qualification-row\"" in preview_multi)
    expect("preview does NOT use real <tr>",
           "<tr class=\"gl-multi-qualification-row\"" not in preview_multi)

    # -- 6. _gl_build_pdf_bytes is wired with pdf_safe=True ------------------
    print()
    print("Test 6: _gl_build_pdf_bytes wires pdf_safe=True")
    import inspect
    src = inspect.getsource(server._gl_build_pdf_bytes)
    expect("pdf_safe=True passed to _gl_preview_html",
           'pdf_safe=True' in src)
    expect("include_watermark=False in PDF path",
           'include_watermark=False' in src)

    # -- 7. _gl_pdf_safe_text helper ----------------------------------------
    print()
    print("Test 7: _gl_pdf_safe_text replaces ASCII hyphens with non-breaking ones")
    expect("digits-with-hyphens normalized",
           server._gl_pdf_safe_text('2009-SWC-0043-UHS') == '2009‑SWC‑0043‑UHS')
    expect("idempotent on already-safe input",
           server._gl_pdf_safe_text('2009‑SWC') == '2009‑SWC')
    expect("None handled",
           server._gl_pdf_safe_text(None) == '')

    # -- 8. api_admin_gl_letter source has regeneration fallback ------------
    print()
    print("Test 8: api_admin_gl_letter source has regeneration fallback")
    letter_src = inspect.getsource(server.api_admin_gl_letter)
    action_src = inspect.getsource(server.api_admin_gl_action)
    generate_src = inspect.getsource(server._gl_generate_letter_file)
    expect("calls _gl_generate_letter_file",
           '_gl_generate_letter_file' in letter_src)
    expect("does not keep legacy missing-file error return",
           'Letter file not found.' not in letter_src)
    expect("has regeneration fallback error",
           'Letter could not be regenerated. Please try Generate PDF first.' in letter_src)
    expect("checks os.path.exists before serving",
           'os.path.exists' in letter_src)
    expect("logs traceback for regeneration failures",
           'traceback.print_exc()' in letter_src)
    expect("reloads the app with the same fetch helper used by generate action",
           '_gl_fetch_application(db, app_id)' in action_src and letter_src.count('_gl_fetch_application(db, app_id)') >= 3)
    expect("allows issued-row fallback regeneration explicitly",
           'allow_issued=True' in letter_src)
    expect("_gl_generate_letter_file ensures output dir exists recursively",
           'mkdir(parents=True, exist_ok=True)' in generate_src)
    expect("_gl_generate_letter_file writes the generated bytes to disk",
           'target.write_bytes(pdf_bytes)' in generate_src)

    # -- 9. api_admin_gl_letter regenerates an issued row with no path ------
    print()
    print("Test 9: api_admin_gl_letter regenerates an issued row with no stored path")
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

    dummy_db = DummyDB()
    app_state = {'letter_pdf_path': ''}
    fetch_calls = {'count': 0}
    original_feature_enabled = server._gl_feature_enabled
    original_can_view = server.gl_user_can_view
    original_can_manage = server.gl_user_can_manage
    original_get_db = server.get_db
    original_fetch = server._gl_fetch_application
    original_letter_context = server._gl_letter_context
    original_build_pdf = server._gl_build_pdf_bytes

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
        server._gl_build_pdf_bytes = lambda _app: generated_bytes

        def tracked_execute(query, params):
            dummy_db.executed.append((query, list(params)))
            if 'UPDATE gl_applications SET letter_pdf_path' in query:
                app_state['letter_pdf_path'] = params[0]
            return dummy_db

        dummy_db.execute = tracked_execute

        body_pdf, fname, err = server.api_admin_gl_letter('111', {'role': 'admin', 'user': 'smoke'})
        expect("application row fetched before, during, and after regeneration",
               fetch_calls['count'] >= 3)
        expect("returns regenerated PDF bytes",
               body_pdf == generated_bytes)
        expect("returns no error on regenerated PDF",
               err is None)
        expect("writes generated PDF to the returned relative path",
               os.path.exists(generated_abs))
        expect("persists regenerated letter path",
               app_state['letter_pdf_path'] == generated_rel)
        expect("commits regenerated letter path update",
               dummy_db.commits == 1)
        expect("returns expected filename",
               fname == 'GL-2026-000111.pdf')
    finally:
        server._gl_feature_enabled = original_feature_enabled
        server.gl_user_can_view = original_can_view
        server.gl_user_can_manage = original_can_manage
        server.get_db = original_get_db
        server._gl_fetch_application = original_fetch
        server._gl_letter_context = original_letter_context
        server._gl_build_pdf_bytes = original_build_pdf
        if os.path.exists(generated_abs):
            os.remove(generated_abs)

    print()
    print(f'FAIL count: {fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
