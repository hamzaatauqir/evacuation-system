#!/usr/bin/env python3
"""End-to-end workflow test for the hostel partner module. LOCAL DEV ONLY.

Usage: python3 tests/smoke/hostel_workflow.py http://localhost:8080

This script MUTATES the local database (creates a test partner login, assigns
a nurse, uploads/cancels an agreement, then cancels the assignment). It
refuses to run against anything but localhost. It uses the default local
admin credentials (admin / embassy2026) and an existing nurse row.
"""
import http.client
import json
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ADMIN_USER, ADMIN_PASS = 'admin', 'embassy2026'
PARTNER_USERNAME, PARTNER_PASS = 'hostel-smoke-partner', 'SmokeTest123!'
TINY_PDF = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
            b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
            b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n'
            b'trailer<</Root 1 0 R>>\n%%EOF\n')

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append(ok)
    print(f'{"PASS" if ok else "FAIL"} {name}{(" — " + str(detail)) if detail and not ok else ""}')
    return ok


class Client:
    def __init__(self, base):
        self.parts = urlsplit(base)
        self.cookies = {}

    def request(self, method, path, body=None, content_type='application/json', raw_body=None):
        conn = http.client.HTTPConnection(self.parts.hostname, self.parts.port or 80, timeout=20)
        try:
            headers = {'User-Agent': 'hostel-workflow-smoke/1.0', 'Connection': 'close'}
            payload = raw_body
            if payload is None and body is not None:
                payload = json.dumps(body).encode()
            if payload is not None:
                headers['Content-Type'] = content_type
            if self.cookies:
                headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            for header, value in resp.getheaders():
                if header.lower() == 'set-cookie':
                    pair = value.split(';', 1)[0]
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        if v:
                            self.cookies[k.strip()] = v.strip()
                        else:
                            self.cookies.pop(k.strip(), None)
            try:
                parsed = json.loads(data) if data else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = None
            return resp.status, parsed, data
        finally:
            conn.close()


def multipart(fields, file_field, file_name, file_bytes, mime):
    boundary = 'hostelworkflowboundary42'
    out = []
    for k, v in fields.items():
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
               f'filename="{file_name}"\r\nContent-Type: {mime}\r\n\r\n'.encode())
    out.append(file_bytes)
    out.append(f'\r\n--{boundary}--\r\n'.encode())
    return b''.join(out), f'multipart/form-data; boundary={boundary}'


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080'
    host = urlsplit(base).hostname or ''
    if host not in ('localhost', '127.0.0.1'):
        print(f'REFUSED: this test mutates data and only runs against localhost (got {host}).')
        sys.exit(2)

    db_path = Path(__file__).resolve().parents[2] / 'evacuation.db'
    nurse_id = None
    if db_path.is_file():
        db = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT id, full_name FROM nurse_registrations ORDER BY id DESC LIMIT 1').fetchone()
        db.close()
        if row:
            nurse_id = row['id']
            print(f'Using existing nurse #{nurse_id} ({row["full_name"]}) for the workflow.')
    if not nurse_id:
        print('REFUSED: no nurse_registrations rows in local DB; register a nurse first.')
        sys.exit(2)

    staff = Client(base)
    partner = Client(base)

    # 1. Admin login
    status, j, _ = staff.request('POST', '/api/login', {'username': ADMIN_USER, 'password': ADMIN_PASS})
    if not check('admin login', status == 200 and j and j.get('success'), j):
        sys.exit(1)

    # 2. AJA Care partner seeded
    status, j, _ = staff.request('GET', '/api/admin/hostel/partners?include_users=1')
    partners = (j or {}).get('partners') or []
    aja = next((p for p in partners if p.get('partner_code') == 'AJA_CARE'), None)
    if not check('AJA Care partner seeded', status == 200 and aja is not None, j):
        sys.exit(1)
    pid = aja['id']

    # 3. Ensure test partner login exists with a known password
    existing = next((u for p in partners for u in (p.get('users') or [])
                     if u['username'] == PARTNER_USERNAME), None)
    if existing:
        status, j, _ = staff.request('POST', '/api/admin/hostel/partner-users/save',
                                     {'action': 'reset_password', 'partner_user_id': existing['id'],
                                      'password': PARTNER_PASS})
        check('partner login password reset', status == 200 and j.get('success'), j)
        staff.request('POST', '/api/admin/hostel/partner-users/save',
                      {'action': 'set_status', 'partner_user_id': existing['id'], 'status': 'ACTIVE'})
    else:
        status, j, _ = staff.request('POST', '/api/admin/hostel/partner-users/save',
                                     {'action': 'create', 'partner_id': pid,
                                      'username': PARTNER_USERNAME, 'password': PARTNER_PASS,
                                      'full_name': 'Smoke Test Partner'})
        check('partner login created', status == 200 and j.get('success'), j)

    # 4. Clean slate: cancel any open assignment for this nurse+partner from earlier runs
    status, j, _ = staff.request('GET', f'/api/admin/hostel/assignments?partner_id={pid}&status=OPEN&q=')
    for item in (j or {}).get('items') or []:
        if item['nurse_registration_id'] == nurse_id:
            staff.request('POST', '/api/admin/hostel/assignments/update',
                          {'id': item['id'], 'status': 'CANCELLED',
                           'cancellation_reason': 'smoke test cleanup'})

    # 5. Nurse search finds portal data
    status, j, _ = staff.request('GET', '/api/admin/hostel/nurse-search?q=' + str(nurse_id and 'a'))
    check('nurse search responds', status == 200 and j.get('success'), j)

    # 6. Assign nurse to AJA Care
    status, j, _ = staff.request('POST', '/api/admin/hostel/assignments/create',
                                 {'nurse_ids': [nurse_id], 'partner_id': pid,
                                  'room_number': 'S-1', 'bed_number': 'B-2',
                                  'note_for_partner': 'Smoke test placement'})
    created = (j or {}).get('created') or []
    if not check('assignment created', status == 200 and len(created) == 1, j):
        sys.exit(1)
    status, j, _ = staff.request('GET', f'/api/admin/hostel/assignments?partner_id={pid}&status=OPEN&q=')
    assignment = next((i for i in (j or {}).get('items') or []
                       if i['nurse_registration_id'] == nurse_id), None)
    assignment_id = assignment['id']

    # 7. Duplicate assignment is skipped
    status, j, _ = staff.request('POST', '/api/admin/hostel/assignments/create',
                                 {'nurse_ids': [nurse_id], 'partner_id': pid})
    check('duplicate assignment skipped', status == 200 and len((j or {}).get('skipped') or []) == 1, j)

    # 8. Reject a disallowed file type
    body, ctype = multipart({'assignment_id': assignment_id}, 'file', 'evil.txt', b'hello', 'text/plain')
    status, j, _ = staff.request('POST', '/api/admin/hostel/agreements/upload',
                                 raw_body=body, content_type=ctype)
    check('txt upload rejected', status == 400, (status, j))

    # 9. Reject mismatched content (txt bytes named .pdf)
    body, ctype = multipart({'assignment_id': assignment_id}, 'file', 'fake.pdf', b'not a pdf', 'application/pdf')
    status, j, _ = staff.request('POST', '/api/admin/hostel/agreements/upload',
                                 raw_body=body, content_type=ctype)
    check('mismatched pdf rejected', status == 400, (status, j))

    # 10. Upload a real (tiny) PDF agreement
    body, ctype = multipart({'assignment_id': assignment_id, 'document_type': 'ACCOMMODATION_AGREEMENT',
                             'visible_to_partner': '1'}, 'file', 'agreement.pdf', TINY_PDF, 'application/pdf')
    status, j, _ = staff.request('POST', '/api/admin/hostel/agreements/upload',
                                 raw_body=body, content_type=ctype)
    if not check('agreement uploaded', status == 200 and (j or {}).get('success'), j):
        sys.exit(1)
    doc_id = j['document_id']

    # 11. Partner login
    status, j, _ = partner.request('POST', '/api/hostel/login',
                                   {'username': PARTNER_USERNAME, 'password': PARTNER_PASS})
    if not check('partner login', status == 200 and (j or {}).get('success'), j):
        sys.exit(1)
    check('partner got hostel_session cookie', 'hostel_session' in partner.cookies)

    # 12. Partner sees only its own assigned nurses, including the new one
    status, j, _ = partner.request('GET', '/api/hostel/nurses')
    items = (j or {}).get('items') or []
    check('partner sees assignment', status == 200 and any(i['id'] == assignment_id for i in items), j)
    check('partner list has no internal notes', all('notes' not in i for i in items))

    # 13. Partner detail + agreement visible
    status, j, _ = partner.request('GET', f'/api/hostel/nurses/detail?id={assignment_id}')
    docs = (j or {}).get('agreements') or []
    check('partner sees uploaded agreement', status == 200 and any(d['id'] == doc_id for d in docs), j)
    check('partner detail hides internal notes', 'notes' not in ((j or {}).get('assignment') or {}))

    # 14. Partner downloads the agreement
    status, _, raw = partner.request('GET', f'/api/hostel/agreements/file?id={doc_id}&download=1')
    check('partner downloads agreement', status == 200 and raw.startswith(b'%PDF'), status)

    # 15. Partner cannot use staff APIs / staff cannot use partner APIs
    status, _, _ = partner.request('GET', '/api/admin/hostel/assignments')
    check('partner blocked from admin APIs', status in (302, 401, 403), status)
    status, _, _ = partner.request('GET', '/api/admin/nurses/registrations')
    check('partner blocked from nurse admin APIs', status in (302, 401, 403), status)
    status, _, _ = staff.request('GET', '/api/hostel/summary')
    check('staff session not valid on partner APIs', status == 401, status)

    # 16. Partner cannot fetch an unrelated/nonexistent document
    status, _, _ = partner.request('GET', '/api/hostel/agreements/file?id=999999')
    check('unrelated document denied', status == 404, status)

    # 17. Partner acknowledges + adds a note
    status, j, _ = partner.request('POST', '/api/hostel/acknowledge', {'id': assignment_id})
    check('partner acknowledges', status == 200 and (j or {}).get('success'), j)
    status, j, _ = partner.request('POST', '/api/hostel/note',
                                   {'id': assignment_id, 'note': 'Smoke test note from partner'})
    check('partner note saved', status == 200 and (j or {}).get('success'), j)

    # 18. Partner CSV export
    status, _, raw = partner.request('GET', '/api/hostel/export.csv')
    check('partner csv export', status == 200 and b'assignment_ref' in raw, status)

    # 19. Staff cancels the agreement -> partner no longer sees or downloads it
    status, j, _ = staff.request('POST', '/api/admin/hostel/agreements/update',
                                 {'id': doc_id, 'action': 'cancel', 'reason': 'smoke test cancellation'})
    check('staff cancels agreement', status == 200 and (j or {}).get('success'), j)
    status, j, _ = partner.request('GET', f'/api/hostel/nurses/detail?id={assignment_id}')
    check('cancelled agreement hidden from partner',
          status == 200 and not any(d['id'] == doc_id for d in (j or {}).get('agreements') or []), j)
    status, _, _ = partner.request('GET', f'/api/hostel/agreements/file?id={doc_id}')
    check('cancelled agreement download denied', status == 404, status)
    status, j, _ = staff.request('GET', f'/api/admin/hostel/assignments/detail?id={assignment_id}')
    cancelled_doc = next((d for d in (j or {}).get('agreements') or [] if d['id'] == doc_id), None)
    check('cancelled agreement still auditable for staff',
          cancelled_doc is not None and cancelled_doc['status'] == 'CANCELLED', j)

    # 20. Staff cancels the assignment -> gone from partner list
    status, j, _ = staff.request('POST', '/api/admin/hostel/assignments/update',
                                 {'id': assignment_id, 'status': 'CANCELLED',
                                  'cancellation_reason': 'smoke test cleanup'})
    check('assignment cancelled', status == 200 and (j or {}).get('success'), j)
    status, j, _ = partner.request('GET', '/api/hostel/nurses')
    check('cancelled assignment not in partner list',
          status == 200 and not any(i['id'] == assignment_id for i in (j or {}).get('items') or []), j)

    # 21. Audit trail covers the workflow
    status, j, _ = staff.request('GET', '/api/admin/hostel/audit?limit=300')
    events = {e['event_type'] for e in (j or {}).get('items') or []}
    for expected in ('assignment_created', 'agreement_uploaded', 'partner_login_success',
                     'agreement_downloaded_by_partner', 'agreement_cancelled',
                     'assignment_acknowledged', 'partner_note_added', 'assignment_cancelled',
                     'partner_access_denied'):
        check(f'audit event {expected}', expected in events)

    # 22. Partner logout ends the session
    status, j, _ = partner.request('POST', '/api/hostel/logout', {})
    status, _, _ = partner.request('GET', '/api/hostel/summary')
    check('partner logout ends session', status == 401, status)

    total, failed = len(RESULTS), RESULTS.count(False)
    print(f'\nTotal: {total}\nPassed: {total - failed}\nFailed: {failed}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
