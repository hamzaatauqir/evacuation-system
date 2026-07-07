#!/usr/bin/env python3
"""Smoke checks for the grading-letter preview, final PDF, and DOCX export."""

from __future__ import annotations

import inspect
import io
import os
import sys
import zipfile

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
    'application': {'id': 111, 'status': 'ISSUED', 'ref_no': 'GL-2026-000111'},
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
    print("Test 1: preview keeps watermark and final preview shell stays official")
    final_html = server._gl_preview_html(LETTER, include_watermark=False, pdf_safe=True)
    preview_html = server._gl_preview_html(LETTER, include_watermark=True, preview_title='Preview', pdf_safe=False)
    expect("final HTML lacks 'NOT OFFICIAL'", 'NOT OFFICIAL' not in final_html)
    expect("final HTML lacks 'PREVIEW ONLY'", 'PREVIEW ONLY' not in final_html)
    expect("preview keeps 'NOT OFFICIAL FOR MOH USE'", 'NOT OFFICIAL FOR MOH USE' in preview_html)
    expect("preview keeps 'PREVIEW ONLY'", 'PREVIEW ONLY' in preview_html)
    expect("final HTML uses Times font stack", '"Times New Roman",Times,serif' in final_html)
    expect("final HTML hides table borders", 'border:none' in final_html)
    expect("final HTML has official heading", 'Embassy of Islamic Republic of Pakistan<br>Kuwait' in final_html)
    expect("final HTML has title", 'TO WHOM IT MAY CONCERN' in final_html)

    print()
    print("Test 2: final PDF path uses direct drawing and compact official sizing")
    build_src = inspect.getsource(server._gl_build_pdf_bytes)
    draw_src = inspect.getsource(server._gl_draw_official_letter_pdf)
    expect("final PDF builder calls direct renderer", '_gl_draw_official_letter_pdf(page, letter)' in build_src)
    expect("final PDF builder no longer uses full-page insert_htmlbox", 'fitz.Rect(12, 10, 583, 832)' not in build_src)
    expect("draw helper uses emblem image", 'page.insert_image' in draw_src)
    expect("draw helper isolates Arabic heading", '_gl_insert_arabic_heading(page' in draw_src)
    expect("draw helper uses compact body font", 'body_fontsize = 10.9' in draw_src)
    expect("draw helper uses compact footer font", 'footer_fontsize = 9.4' in draw_src)
    expect("draw helper separates footer fields", 'Telephone:' in draw_src and 'Fax:' in draw_src and 'Email:' in draw_src)

    print()
    print("Test 3: admin routes and buttons support inline PDF, forced regeneration, and DOCX")
    handler_src = inspect.getsource(server.Handler.do_GET)
    template_path = os.path.join(REPO_ROOT, 'templates', 'admin_nurse_grading_letters.html')
    template_src = open(template_path, 'r', encoding='utf-8').read()
    expect("PDF route reads disposition query param", "params.get('disposition')" in handler_src)
    expect("PDF route reads force query param", "params.get('force')" in handler_src)
    expect("PDF route still sets inline/attachment disposition", "f'{disposition}; filename=\"{fname}\"'" in handler_src)
    expect("DOCX route exists", "/api/admin/gl/letter-docx" in handler_src)
    expect("DOCX content type is correct", "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in handler_src)
    expect("Print Final Letter forces regeneration", "Print Final Letter" in template_src and "&disposition=inline&force=1" in template_src)
    expect("Download Final PDF forces regeneration", "Download Final PDF" in template_src and "&force=1" in template_src)
    expect("Download Word Copy button exists", "Download Word Copy" in template_src)

    print()
    print("Test 4: final PDF bytes contain official content and no watermark")
    original_letter_context = server._gl_letter_context
    try:
        server._gl_letter_context = lambda _app: LETTER
        pdf_bytes = server._gl_build_pdf_bytes({'id': 111})
    finally:
        server._gl_letter_context = original_letter_context
    expect("PDF bytes start with %PDF", pdf_bytes.startswith(b'%PDF'))
    if server.HAVE_PYMUPDF and server.fitz is not None:
        doc = server.fitz.open(stream=pdf_bytes, filetype='pdf')
        try:
            text = '\n'.join(page.get_text() for page in doc)
        finally:
            doc.close()
        expect("final PDF contains official heading", 'Embassy of Islamic Republic of Pakistan' in text)
        expect("final PDF contains title", 'TO WHOM IT MAY CONCERN' in text)
        expect("final PDF contains telephone", 'Telephone: +965-2225-6655' in text)
        expect("final PDF contains fax", 'Fax: +965-2225-6666' in text)
        expect("final PDF contains email", 'Email: parepkuwait@mofa.gov.pk' in text)
        expect("final PDF omits NOT OFFICIAL watermark", 'NOT OFFICIAL' not in text)
        expect("final PDF omits PREVIEW ONLY watermark", 'PREVIEW ONLY' not in text)

    print()
    print("Test 5: DOCX export returns an official editable Word file")
    docx_src = inspect.getsource(server._gl_build_docx_bytes)
    borders_src = inspect.getsource(server._gl_docx_set_table_borders)
    expect("DOCX helper sets A4 portrait", 'WD_ORIENT.PORTRAIT' in docx_src)
    expect("DOCX helper uses footer table", 'footer.add_table' in docx_src)
    expect("DOCX helper uses hidden table borders", "_gl_docx_set_table_borders(header_table)" in docx_src and "_gl_docx_set_table_borders(qual_table)" in docx_src)
    expect("DOCX footer keeps only top rule", "top='single'" in docx_src)
    expect("table-border helper supports nil borders", "top='nil'" in borders_src)

    class DummyDB:
        def close(self):
            return None

    original_feature_enabled = server._gl_feature_enabled
    original_can_view = server.gl_user_can_view
    original_can_manage = server.gl_user_can_manage
    original_get_db = server.get_db
    original_fetch = server._gl_fetch_application
    original_letter_context = server._gl_letter_context
    try:
        server._gl_feature_enabled = lambda: True
        server.gl_user_can_view = lambda _user: True
        server.gl_user_can_manage = lambda _user: True
        server.get_db = lambda: DummyDB()
        server._gl_fetch_application = lambda _db, _app_id: {
            'id': 111,
            'status': 'ISSUED',
            'ref_no': 'GL-2026-000111',
            'letter_pdf_path': 'generated_letters/GL-2026-000111.pdf',
        }
        server._gl_letter_context = lambda app: dict(LETTER, application=dict(app))
        body_docx, fname, err = server.api_admin_gl_letter_docx('111', {'role': 'admin', 'user': 'smoke'})
    finally:
        server._gl_feature_enabled = original_feature_enabled
        server.gl_user_can_view = original_can_view
        server.gl_user_can_manage = original_can_manage
        server.get_db = original_get_db
        server._gl_fetch_application = original_fetch
        server._gl_letter_context = original_letter_context
    expect("DOCX helper returns no error", err is None)
    expect("DOCX filename is correct", fname == 'GL-2026-000111.docx')
    expect("DOCX bytes are a zip package", body_docx[:2] == b'PK')
    with zipfile.ZipFile(io.BytesIO(body_docx), 'r') as zf:
        document_xml = zf.read('word/document.xml').decode('utf-8', 'ignore')
        footer_xml = zf.read('word/footer1.xml').decode('utf-8', 'ignore')
    expect("DOCX contains embassy heading", 'Embassy of Islamic Republic of Pakistan' in document_xml)
    expect("DOCX contains title", 'TO WHOM IT MAY CONCERN' in document_xml)
    expect("DOCX contains no watermark text", 'NOT OFFICIAL' not in document_xml and 'PREVIEW ONLY' not in document_xml)
    expect("DOCX footer contains telephone", 'Telephone: +965-2225-6655' in footer_xml)
    expect("DOCX footer contains fax", 'Fax: +965-2225-6666' in footer_xml)
    expect("DOCX footer contains email", 'Email: parepkuwait@mofa.gov.pk' in footer_xml)

    print()
    print("Test 6: regeneration helper still logs details and writes generated PDFs")
    letter_src = inspect.getsource(server.api_admin_gl_letter)
    generate_src = inspect.getsource(server._gl_generate_letter_file)
    expect("api_admin_gl_letter exposes force_regenerate", 'force_regenerate=False' in letter_src)
    expect("api_admin_gl_letter logs fallback context", 'Download fallback app_id=' in letter_src)
    expect("api_admin_gl_letter logs traceback", 'traceback.print_exc()' in letter_src)
    expect("api_admin_gl_letter checks os.path.exists", 'os.path.exists' in letter_src)
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

    class DummyDB2:
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
        dummy_db = DummyDB2()
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
    print("Test 9: branding strings match the new admin/login naming")
    expect("login page shows new title", '<title>CWA Portal Official Login</title>' in server.LOGIN_PAGE)
    expect("login page shows new heading", '<h1>CWA Portal Official Login</h1>' in server.LOGIN_PAGE)
    expect("main app title updated", '<title>Community Welfare Wing Operations</title>' in server.MAIN_APP)
    expect("main app header updated", '<h1>Community Welfare Wing Operations</h1>' in server.MAIN_APP)
    expect("login page no longer shows old heading", 'CITIZEN SUPPORT FOR TRANSIT KSA</h1>' not in server.LOGIN_PAGE)
    expect("main app no longer shows old dashboard heading", 'CITIZEN SUPPORT FOR TRANSIT KSA SYSTEM</h1>' not in server.MAIN_APP)

    print()
    print(f'FAIL count: {fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
