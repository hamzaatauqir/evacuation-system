#!/usr/bin/env python3
"""Embassy Forms Library — localhost-only E2E workflow test. MUTATES the local DB.

Covers: permissions (unauthenticated vs staff vs admin-only actions), lifecycle
(create -> upload -> publish -> unpublish -> archive -> restore), the replace
workflow and its version retention, public visibility rules, download headers,
the download counter, path-traversal and id-probing defences, category
management, and the public JSON payload shape.

Test artifacts (forms titled 'FORMS-SMOKE …' and their uploaded PDFs) are left
in the local DB, archived, mirroring the hostel and ads workflow convention.

Usage:
  python3 tests/smoke/forms_workflow.py http://localhost:8080
"""
from __future__ import annotations

import http.client
import json
import os
import re
import secrets
import sys
from urllib.parse import urlsplit

ADMIN_USER = os.environ.get('FORMS_SMOKE_ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('FORMS_SMOKE_ADMIN_PASS', 'embassy2026')

FAILURES = []
PASSES = 0
BASE = ''


def check(name, ok, detail=''):
    global PASSES
    if ok:
        PASSES += 1
        print(f'  PASS  {name}')
    else:
        FAILURES.append(name)
        print(f'  FAIL  {name} {detail}')


def request(method, path, body=None, headers=None, cookie=None):
    parsed = urlsplit(BASE)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=30)
    hdrs = {'User-Agent': 'forms-workflow-smoke/1.0', 'Connection': 'close'}
    if cookie:
        hdrs['Cookie'] = cookie
    hdrs.update(headers or {})
    try:
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        payload = resp.read()
        return resp.status, dict(resp.getheaders()), payload
    finally:
        conn.close()


def jreq(method, path, data=None, cookie=None):
    body = json.dumps(data).encode() if data is not None else None
    status, headers, payload = request(
        method, path, body=body, cookie=cookie,
        headers={'Content-Type': 'application/json'} if body else None)
    try:
        parsed = json.loads(payload.decode('utf-8', errors='replace'))
    except Exception:
        parsed = {}
    return status, headers, parsed


def login(username, password):
    status, headers, body = jreq('POST', '/api/login',
                                 {'username': username, 'password': password})
    if status != 200 or not body.get('success', True):
        return None
    match = re.search(r'session=([0-9a-f]+)', headers.get('Set-Cookie', ''))
    return f'session={match.group(1)}' if match else None


def build_pdf(marker=b'v1', pad=600):
    """Minimal structurally-valid PDF: header near the start, %%EOF near the end."""
    return (b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n'
            + b'1 0 obj<</Type/Catalog>>endobj\n'
            + b'% ' + marker + b'\n'
            + b'0' * pad + b'\n'
            + b'trailer<</Root 1 0 R>>\n%%EOF\n')


def multipart(fields, file_field, filename, file_bytes):
    boundary = 'formsSmoke' + secrets.token_hex(8)
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
                  f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
                 + file_bytes + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def upload(cookie, form_id, filename, file_bytes):
    body, content_type = multipart({'form_id': str(form_id)}, 'file', filename, file_bytes)
    status, _headers, payload = request('POST', '/api/admin/forms/upload-file', body=body,
                                        cookie=cookie, headers={'Content-Type': content_type})
    try:
        return status, json.loads(payload.decode('utf-8', errors='replace'))
    except Exception:
        return status, {}


def main():
    global BASE
    BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080').rstrip('/')
    print(f'Embassy Forms Library workflow smoke — {BASE}\n')

    tag = secrets.token_hex(3).upper()

    # ── 1. Unauthenticated access ───────────────────────────────
    print('1. Public / unauthenticated surface')
    status, _h, body = jreq('GET', '/api/public/forms')
    check('public API reachable without a session', status == 200 and body.get('success') is True,
          f'status={status}')
    check('public API returns a forms list', isinstance(body.get('forms'), list))

    status, _h, _b = jreq('GET', '/forms')
    check('public page reachable without a session', status == 200, f'status={status}')

    status, _h, _b = jreq('POST', '/api/public/forms', {})
    check('public API rejects POST with 405', status == 405, f'status={status}')

    for path in ('/admin/forms', '/api/admin/forms', '/api/admin/forms/detail?id=1'):
        status, _h, _b = jreq('GET', path)
        check(f'{path} blocked when logged out', status in (302, 401, 403), f'status={status}')
    status, _h, _b = jreq('POST', '/api/admin/forms/save', {'title': 'nope'})
    check('save blocked when logged out', status in (302, 401, 403), f'status={status}')

    # ── 2. Admin session ────────────────────────────────────────
    print('\n2. Admin session')
    admin = login(ADMIN_USER, ADMIN_PASS)
    if not admin:
        check('admin login', False, '(cannot continue without a session)')
        return summarize()
    check('admin login', True)

    status, _h, listing = jreq('GET', '/api/admin/forms', cookie=admin)
    check('admin can list forms', status == 200 and listing.get('success') is True, f'status={status}')
    categories = listing.get('categories') or []
    check('categories are seeded', len(categories) >= 7, f'count={len(categories)}')
    nadra = next((c for c in categories if c['slug'] == 'nadra'), None)
    check('NADRA category present', bool(nadra))
    if not nadra:
        return summarize()

    # ── 3. Validation ───────────────────────────────────────────
    print('\n3. Metadata validation')
    status, _h, body = jreq('POST', '/api/admin/forms/save',
                            {'id': 0, 'title': '', 'category_id': nadra['id']}, cookie=admin)
    check('empty title rejected', body.get('success') is False)
    status, _h, body = jreq('POST', '/api/admin/forms/save',
                            {'id': 0, 'title': 'x', 'category_id': 0}, cookie=admin)
    check('missing category rejected', body.get('success') is False)
    status, _h, body = jreq('POST', '/api/admin/forms/save',
                            {'id': 0, 'title': 'x', 'category_id': 999999}, cookie=admin)
    check('unknown category rejected', body.get('success') is False)
    status, _h, body = jreq('POST', '/api/admin/forms/save',
                            {'id': 0, 'title': 'x', 'category_id': nadra['id'],
                             'effective_date': '2026-13-45'}, cookie=admin)
    check('impossible effective date rejected', body.get('success') is False)

    # ── 4. Create ───────────────────────────────────────────────
    print('\n4. Create and attach')
    title = f'FORMS-SMOKE {tag} NICOP Modification'
    xss = '<img src=x onerror=alert(1)>'
    status, _h, body = jreq('POST', '/api/admin/forms/save', {
        'id': 0, 'title': title, 'description': f'Smoke test form {xss}',
        'category_id': nadra['id'], 'language': 'en+ur',
        'version_label': 'Aug 2026 revision', 'effective_date': '2026-08-01',
        'display_order': 5,
    }, cookie=admin)
    check('form created', body.get('success') is True, str(body))
    form_id = body.get('id') or 0
    if not form_id:
        return summarize()

    # Publishing without a file must be refused.
    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'publish'}, cookie=admin)
    check('cannot publish without a file', body.get('success') is False, str(body))

    # ── 5. Upload validation matrix ─────────────────────────────
    print('\n5. Upload validation')
    pdf_v1 = build_pdf(b'v1')
    status, body = upload(admin, form_id, 'form.docx', pdf_v1)
    check('DOCX extension rejected', body.get('success') is False, str(body))
    status, body = upload(admin, form_id, 'form.pdf', b'PK\x03\x04' + b'0' * 900)
    check('ZIP content in a .pdf rejected', body.get('success') is False, str(body))
    status, body = upload(admin, form_id, 'form.pdf', b'%PDF-1.7\n' + b'0' * 900)
    check('PDF without a trailer rejected', body.get('success') is False, str(body))
    status, body = upload(admin, form_id, 'form.pdf', b'')
    check('empty upload rejected', body.get('success') is False, str(body))
    status, body = upload(admin, form_id, 'form.pdf', b'%PDF-1.7\n' + b'0' * (11 * 1024 * 1024) + b'%%EOF')
    check('oversize upload rejected', body.get('success') is False, str(body))

    status, body = upload(admin, form_id, 'NICOP_Form_2026-01.pdf', pdf_v1)
    check('valid PDF accepted', body.get('success') is True, str(body))
    check('first upload is version 1', body.get('version_number') == 1, str(body))
    check('first upload is not a replacement', body.get('replaced') is False, str(body))

    status, body = upload(admin, form_id, 'NICOP_Form_2026-01.pdf', pdf_v1)
    check('identical re-upload refused', body.get('success') is False, str(body))

    # ── 6. Draft is invisible to the public ─────────────────────
    print('\n6. Draft invisibility')
    _s, _h, public = jreq('GET', '/api/public/forms')
    check('draft absent from public payload',
          all(f['id'] != form_id for f in public.get('forms', [])))
    status, _h, _b = jreq('GET', f'/forms/download/{form_id}')
    check('draft not downloadable', status == 404, f'status={status}')

    # ── 7. Publish ──────────────────────────────────────────────
    print('\n7. Publish and download')
    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'publish'}, cookie=admin)
    check('publish succeeds', body.get('success') is True, str(body))

    _s, _h, public = jreq('GET', '/api/public/forms')
    entry = next((f for f in public.get('forms', []) if f['id'] == form_id), None)
    check('published form appears publicly', bool(entry))
    if entry:
        check('public payload hides internal fields',
              'stored_filename' not in entry and 'created_by' not in entry, str(entry.keys()))
        check('download URL points at the download route',
              str(entry.get('downloadUrl', '')).endswith(f'/forms/download/{form_id}'),
              entry.get('downloadUrl'))
        check('file size exposed', entry.get('fileSize') == len(pdf_v1), str(entry.get('fileSize')))
        check('nadra category label present', entry.get('category') == 'NADRA', str(entry.get('category')))

    status, headers, payload = request('GET', f'/forms/download/{form_id}')
    check('download returns 200', status == 200, f'status={status}')
    check('download body matches uploaded bytes', payload == pdf_v1)
    disp = headers.get('Content-Disposition', '')
    check('download forces attachment', disp.startswith('attachment;'), disp)
    check('download filename preserved', 'NICOP_Form_2026-01.pdf' in disp, disp)
    check('download content type is PDF',
          headers.get('Content-Type') == 'application/pdf', headers.get('Content-Type'))
    check('download sets nosniff',
          headers.get('X-Content-Type-Options') == 'nosniff', headers.get('X-Content-Type-Options'))
    check('download cache is bounded, not immutable',
          'max-age=300' in headers.get('Cache-Control', '')
          and 'immutable' not in headers.get('Cache-Control', ''),
          headers.get('Cache-Control'))

    # ── 8. Download counter ─────────────────────────────────────
    print('\n8. Download counter')
    _s, _h, detail = jreq('GET', f'/api/admin/forms/detail?id={form_id}', cookie=admin)
    before = (detail.get('form') or {}).get('download_count', 0)
    request('GET', f'/forms/download/{form_id}')
    request('GET', f'/forms/download/{form_id}')
    _s, _h, detail = jreq('GET', f'/api/admin/forms/detail?id={form_id}', cookie=admin)
    after = (detail.get('form') or {}).get('download_count', 0)
    check('download_count increments', after == before + 2, f'{before} -> {after}')

    # ── 9. Traversal and id probing ─────────────────────────────
    print('\n9. Download route hardening')
    for bad in ('/forms/download/abc', '/forms/download/', '/forms/download/1%2e%2e%2f',
                '/forms/download/-1', '/forms/download/99999999'):
        status, _h, _b = jreq('GET', bad)
        check(f'{bad} refused', status == 404, f'status={status}')
    status, _h, body = jreq('GET', '/forms/download/999999')
    check('unknown id gives the same message as a draft',
          body.get('error') == 'Form not found', str(body))

    # ── 10. Replace keeps the URL, retains the old version ──────
    print('\n10. Replace workflow')
    pdf_v2 = build_pdf(b'v2-newer', pad=800)
    status, body = upload(admin, form_id, 'NICOP_Form_2026-08.pdf', pdf_v2)
    check('replacement accepted', body.get('success') is True, str(body))
    check('replacement flagged as such', body.get('replaced') is True, str(body))
    check('version bumped to 2', body.get('version_number') == 2, str(body))

    status, headers, payload = request('GET', f'/forms/download/{form_id}')
    check('same URL now serves the new file', payload == pdf_v2, f'status={status}')
    check('new filename in disposition',
          'NICOP_Form_2026-08.pdf' in headers.get('Content-Disposition', ''),
          headers.get('Content-Disposition'))

    _s, _h, detail = jreq('GET', f'/api/admin/forms/detail?id={form_id}', cookie=admin)
    versions = detail.get('versions') or []
    check('old version retained in history', len(versions) == 1, str(len(versions)))
    if versions:
        check('retained version records the old filename',
              versions[0].get('original_filename') == 'NICOP_Form_2026-01.pdf', str(versions[0]))
        check('retained version records who replaced it',
              bool(versions[0].get('replaced_by')), str(versions[0]))
    check('form still published after replace',
          (detail.get('form') or {}).get('status') == 'PUBLISHED', str(detail.get('form', {}).get('status')))

    # ── 11. Unpublish / archive / restore ───────────────────────
    print('\n11. Lifecycle transitions')
    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'unpublish'}, cookie=admin)
    check('unpublish succeeds', body.get('success') is True, str(body))
    status, _h, _b = jreq('GET', f'/forms/download/{form_id}')
    check('unpublished form is no longer downloadable', status == 404, f'status={status}')

    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'unpublish'}, cookie=admin)
    check('double unpublish refused', body.get('success') is False, str(body))

    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'archive'}, cookie=admin)
    check('admin can archive', body.get('success') is True, str(body))

    status, body = upload(admin, form_id, 'x.pdf', build_pdf(b'v3'))
    check('archived form rejects uploads', body.get('success') is False, str(body))
    status, _h, body = jreq('POST', '/api/admin/forms/save',
                            {'id': form_id, 'title': 'changed', 'category_id': nadra['id']},
                            cookie=admin)
    check('archived form rejects metadata edits', body.get('success') is False, str(body))
    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'publish'}, cookie=admin)
    check('archived form cannot be published directly', body.get('success') is False, str(body))

    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'restore'}, cookie=admin)
    check('admin can restore', body.get('success') is True, str(body))
    check('restore returns to DRAFT', body.get('new_status') == 'DRAFT', str(body))

    # ── 12. There is no delete route ────────────────────────────
    print('\n12. No hard delete')
    for path in ('/api/admin/forms/delete', '/api/admin/forms/remove'):
        status, _h, _b = jreq('POST', path, {'id': form_id}, cookie=admin)
        check(f'{path} does not exist', status == 404, f'status={status}')
    status, _h, body = jreq('POST', '/api/admin/forms/status',
                            {'id': form_id, 'action': 'delete'}, cookie=admin)
    check('delete is not a valid status action', body.get('success') is False, str(body))

    # ── 13. Categories ──────────────────────────────────────────
    print('\n13. Category management')
    new_label = f'FORMS-SMOKE {tag} Category'
    status, _h, body = jreq('POST', '/api/admin/forms/categories',
                            {'action': 'create', 'label': new_label}, cookie=admin)
    check('admin can create a category', body.get('success') is True, str(body))
    cat_id = body.get('id') or 0
    status, _h, body = jreq('POST', '/api/admin/forms/categories',
                            {'action': 'create', 'label': new_label}, cookie=admin)
    check('duplicate category refused', body.get('success') is False, str(body))
    if cat_id:
        status, _h, body = jreq('POST', '/api/admin/forms/categories',
                                {'action': 'deactivate', 'id': cat_id}, cookie=admin)
        check('unused category can be deactivated', body.get('success') is True, str(body))
    status, _h, body = jreq('POST', '/api/admin/forms/categories',
                            {'action': 'deactivate', 'id': nadra['id']}, cookie=admin)
    check('category in use cannot be deactivated', body.get('success') is False, str(body))

    # ── 14. Audit trail ─────────────────────────────────────────
    print('\n14. Audit trail')
    status, _h, body = jreq('GET', f'/api/admin/forms/audit?id={form_id}', cookie=admin)
    check('admin can read the audit trail', body.get('success') is True, f'status={status}')
    events = {row.get('event_type') for row in body.get('items', [])}
    for expected in ('form_created', 'file_uploaded', 'file_replaced',
                     'form_published', 'form_unpublished', 'form_archived', 'form_restored'):
        check(f'audit records {expected}', expected in events, str(sorted(events)))

    # ── 15. Reorder ─────────────────────────────────────────────
    print('\n15. Reorder')
    status, _h, body = jreq('POST', '/api/admin/forms/reorder',
                            {'order': [form_id]}, cookie=admin)
    check('reorder accepts a known id', body.get('success') is True, str(body))
    status, _h, body = jreq('POST', '/api/admin/forms/reorder',
                            {'order': [form_id, 99999999]}, cookie=admin)
    check('reorder rejects an unknown id', body.get('success') is False, str(body))
    status, _h, body = jreq('POST', '/api/admin/forms/reorder', {'order': []}, cookie=admin)
    check('reorder rejects an empty list', body.get('success') is False, str(body))

    # ── 16. Public page renders staff content safely ────────────
    print('\n16. Public page rendering')
    status, _h, payload = request('GET', '/forms')
    html = payload.decode('utf-8', errors='replace')
    check('public page renders', status == 200, f'status={status}')
    check('no unreplaced template placeholders', not re.search(r'__[A-Z_]+__', html),
          str(re.findall(r'__[A-Z_]+__', html)[:3]))
    check('raw XSS payload never reaches the HTML', '<img src=x onerror=' not in html)
    check('payload is injected as JSON', 'window.CWA_FORMS =' in html)

    return summarize()


def summarize():
    print(f'\nPassed: {PASSES}   Failed: {len(FAILURES)}')
    if FAILURES:
        for name in FAILURES:
            print(f'  - {name}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
