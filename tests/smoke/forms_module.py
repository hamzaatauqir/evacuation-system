#!/usr/bin/env python3
"""Embassy Forms Library — unit gates for storage, schema and public payload.

Runs against a throwaway SQLite file and a temporary upload directory in
/tmp — no server, no login, no network, and it never touches the real portal
database. Both are deleted when the run finishes.

Covers the rules the module must never break:
  1. PDF only, extension AND magic must agree, size capped.
  2. Stored names are generated; traversal and odd names never resolve.
  3. Uploads round-trip byte-for-byte (the shared server.py multipart helper
     truncates trailing newlines — this module must not).
  4. Only PUBLISHED forms with a file reach the public payload, and that
     payload never leaks internal columns.
  5. Replacing a file retains the old version and keeps the public URL stable.
  6. Download URLs handed to the cross-origin React site are absolute.
  7. Nothing in the module deletes a row or a file.

Usage: python3 tests/smoke/forms_module.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.domains.forms import audit, core, schema, service, storage  # noqa: E402

FAILURES = []
PASSES = 0
BACKEND = 'https://evacuation-system.onrender.com'

ADMIN = {'user': 'smoke-admin', 'role': 'admin'}
OPERATOR = {'user': 'smoke-operator', 'role': 'operator'}
OPSPECIAL = {'user': 'smoke-opspecial', 'role': 'operator_special'}
VIEWER = {'user': 'smoke-viewer', 'role': 'viewer'}


def check(name, ok, detail=''):
    global PASSES
    if ok:
        PASSES += 1
        print(f'  PASS  {name}')
    else:
        FAILURES.append(name)
        print(f'  FAIL  {name} {detail}')


def build_pdf(marker=b'v1', pad=400):
    return (b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n'
            + b'1 0 obj<</Type/Catalog>>endobj\n% ' + marker + b'\n'
            + b'0' * pad + b'\ntrailer<</Root 1 0 R>>\n%%EOF\n')


def multipart_body(fields, filename, file_bytes, boundary='FormsUnit123'):
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                  f'filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n').encode()
                 + file_bytes + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def main():
    tmp = Path(tempfile.mkdtemp(prefix='forms-unit-'))
    os.environ['PUBLIC_BACKEND_ORIGIN'] = BACKEND
    os.environ.pop('PUBLIC_BASE_PATH', None)

    # A temp file rather than ':memory:'. The service layer closes its
    # connection after every call (connection-per-request, like the portal), so
    # an in-memory database would be discarded between calls.
    db_path = tmp / 'forms-unit.db'

    def open_db():
        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    db = open_db()
    # The module writes two summary rows to the portal-wide audit_log.
    db.executescript("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, record_id INTEGER,
        user TEXT, details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
    db.commit()

    core.configure(get_db=open_db, data_root=tmp, project_root=Path('.'))

    try:
        print('Embassy Forms Library unit gates\n')

        # ── 1. Schema ───────────────────────────────────────────
        print('1. Schema')
        schema.ensure_schema(db)
        tables = {r['name'] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table in ('embassy_forms', 'embassy_form_categories',
                      'embassy_form_versions', 'embassy_form_audit'):
            check(f'{table} created', table in tables)
        count_before = db.execute('SELECT COUNT(*) n FROM embassy_form_categories').fetchone()['n']
        schema.ensure_schema(db)
        count_after = db.execute('SELECT COUNT(*) n FROM embassy_form_categories').fetchone()['n']
        check('ensure_schema is idempotent', count_before == count_after == 7,
              f'{count_before} -> {count_after}')

        db.execute("UPDATE embassy_form_categories SET label='Renamed' WHERE slug='other'")
        db.commit()
        schema.ensure_schema(db)
        label = db.execute("SELECT label FROM embassy_form_categories WHERE slug='other'").fetchone()['label']
        check('re-seeding never overwrites an admin rename', label == 'Renamed', label)

        # ── 2. Upload validation ────────────────────────────────
        print('\n2. Upload validation')
        good = build_pdf()
        check('valid PDF accepted', storage.validate_pdf('a.pdf', good) == (core.ALLOWED_MIME, None))
        for name, blob, label in (
            ('a.docx', good, 'DOCX extension'),
            ('a.doc', good, 'DOC extension'),
            ('a.PDF.exe', good, 'double extension'),
            ('a.svg', b'<svg/>', 'SVG'),
            ('a.pdf', b'PK\x03\x04' + b'0' * 900, 'ZIP content'),
            ('a.pdf', b'%PDF-1.7' + b'0' * 900, 'missing trailer'),
            ('a.pdf', b'', 'empty body'),
            ('', good, 'no filename'),
        ):
            mime, err = storage.validate_pdf(name, blob)
            check(f'{label} rejected', mime == '' and bool(err), f'{name} -> {err!r}')
        mime, err = storage.validate_pdf('a.pdf', b'%PDF-1.7\n' + b'0' * (11 * 1024 * 1024) + b'\n%%EOF')
        check('oversize rejected', mime == '' and 'too large' in (err or ''), str(err))
        check('a PDF merely mentioning %PDF- late is rejected',
              storage.validate_pdf('a.pdf', b'0' * 2000 + b'%PDF-1.7\n%%EOF')[0] == '')

        # ── 3. Stored names and traversal ───────────────────────
        print('\n3. Stored names and traversal')
        stored = storage.store_file(7, 3, good)
        check('generated name encodes form and version', stored.startswith('form7_v3_'), stored)
        check('generated name ends .pdf', stored.endswith('.pdf'), stored)
        check('stored file resolves', storage.resolve_stored(stored) is not None)
        for bad in ('../../etc/passwd', 'a/b.pdf', '..', '', 'x.exe', 'x.pdf.exe',
                    'form7_v3.txt', '/etc/passwd', '.\\x.pdf'):
            check(f'{bad!r} does not resolve', storage.resolve_stored(bad) is None)
        again = storage.store_file(7, 3, good)
        check('two stores never collide', again != stored, f'{stored} vs {again}')

        # ── 4. Byte-exact multipart round trip ──────────────────
        print('\n4. Byte-exact upload parsing')
        for trailing, label in ((b'', 'no trailing newline'),
                                (b'\n', 'trailing LF'),
                                (b'\r\n', 'trailing CRLF'),
                                (b'\n\n\n', 'several trailing newlines')):
            blob = build_pdf() + trailing
            body, ctype = multipart_body({'form_id': '1'}, 'x.pdf', blob)
            name, parsed = storage.extract_upload(body, ctype)
            check(f'round trip preserves bytes — {label}', parsed == blob,
                  f'{len(blob)} -> {len(parsed or b"")}')
            check(f'filename parsed — {label}', name == 'x.pdf', str(name))
        body, ctype = multipart_body({'form_id': '1'}, 'x.pdf', build_pdf())
        check('non-multipart content type ignored',
              storage.extract_upload(body, 'application/json') == (None, None))

        # ── 5. Download filename safety ─────────────────────────
        print('\n5. Download filename safety')
        injected = storage.safe_download_filename('evil"\r\nSet-Cookie: a=b\n.pdf', 1, 'T')
        check('CR/LF stripped from filename',
              '\r' not in injected and '\n' not in injected and '"' not in injected, injected)
        check('Urdu-only filename falls back to the title',
              storage.safe_download_filename('نادرا فارم.pdf', 5, 'NICOP Form') == 'NICOP Form.pdf',
              storage.safe_download_filename('نادرا فارم.pdf', 5, 'NICOP Form'))
        check('unusable name and title fall back to the id',
              storage.safe_download_filename('', 9, '') == 'embassy_form_9.pdf')
        check('normal name preserved',
              storage.safe_download_filename('NICOP_Form_2026-08.pdf', 1, 'x') == 'NICOP_Form_2026-08.pdf')

        # ── 6. Permissions ──────────────────────────────────────
        print('\n6. Permissions')
        check('admin can manage', core.user_can_manage(ADMIN))
        check('operator can manage', core.user_can_manage(OPERATOR))
        check('operator_special cannot manage', not core.user_can_manage(OPSPECIAL))
        check('viewer cannot manage', not core.user_can_manage(VIEWER))
        check('anonymous cannot manage', not core.user_can_manage(None))
        check('only admin is admin', core.user_is_admin(ADMIN) and not core.user_is_admin(OPERATOR))

        nadra = db.execute("SELECT id FROM embassy_form_categories WHERE slug='nadra'").fetchone()['id']
        result = service.save_form({'id': 0, 'title': 'X', 'category_id': nadra}, OPSPECIAL)
        check('operator_special save refused', result.get('status') == 403, str(result))
        result = service.manage_category({'action': 'create', 'label': 'Nope'}, OPERATOR)
        check('operator cannot manage categories', result.get('status') == 403, str(result))

        # ── 7. Lifecycle and public payload ─────────────────────
        print('\n7. Lifecycle and public payload')
        created = service.save_form({
            'id': 0, 'title': 'NICOP Modification Form', 'title_ur': 'نادرا فارم',
            'description': 'For correction of NICOP information.',
            'category_id': nadra, 'language': 'en+ur', 'version_label': 'Aug 2026',
        }, OPERATOR)
        check('operator can create a form', created.get('success') is True, str(created))
        form_id = created.get('id')

        payload = service.public_payload()
        check('form without a file is not public', not payload['forms'])

        published = service.set_status({'id': form_id, 'action': 'publish'}, OPERATOR)
        check('publish without a file refused', published.get('success') is False, str(published))

        body, ctype = multipart_body({'form_id': str(form_id)}, 'NICOP_2026-01.pdf', good)
        name, raw = storage.extract_upload(body, ctype)
        attached = service.attach_file({'form_id': form_id}, name, raw, OPERATOR)
        check('file attached', attached.get('success') is True, str(attached))

        payload = service.public_payload()
        check('draft with a file still not public', not payload['forms'])

        published = service.set_status({'id': form_id, 'action': 'publish'}, OPERATOR)
        check('operator can publish', published.get('success') is True, str(published))

        payload = service.public_payload()
        check('published form is public', len(payload['forms']) == 1, str(payload['forms']))
        entry = payload['forms'][0]
        check('download URL is absolute for the cross-origin site',
              entry['downloadUrl'] == f'{BACKEND}/forms/download/{form_id}', entry['downloadUrl'])
        for leaked in ('stored_filename', 'storedFilename', 'created_by', 'createdBy',
                       'file_sha256', 'status'):
            check(f'public payload omits {leaked}', leaked not in entry)
        check('public payload carries the category label', entry['category'] == 'NADRA', entry['category'])
        check('public payload carries a human size',
              entry['fileSizeDisplay'] == core.human_file_size(len(good)) and bool(entry['fileSizeDisplay']),
              entry['fileSizeDisplay'])
        check('public payload carries the raw byte count', entry['fileSize'] == len(good),
              str(entry['fileSize']))
        check('only used categories are offered as filters',
              [c['slug'] for c in payload['categories']] == ['nadra'], str(payload['categories']))

        # ── 8. Replace ──────────────────────────────────────────
        print('\n8. Replace and version retention')
        newer = build_pdf(b'v2', pad=700)
        replaced = service.attach_file({'form_id': form_id}, 'NICOP_2026-08.pdf', newer, OPERATOR)
        check('replacement accepted', replaced.get('success') is True, str(replaced))
        check('replacement flagged', replaced.get('replaced') is True, str(replaced))
        check('version bumped', replaced.get('version_number') == 2, str(replaced))
        versions = db.execute('SELECT * FROM embassy_form_versions WHERE form_id = ?',
                              [form_id]).fetchall()
        check('old version retained', len(versions) == 1, str(len(versions)))
        check('old file still on disk',
              storage.resolve_stored(versions[0]['stored_filename']) is not None)
        payload = service.public_payload()
        check('public URL unchanged after replace',
              payload['forms'][0]['downloadUrl'] == f'{BACKEND}/forms/download/{form_id}')
        raw_now, _fn, _mime, err = service.resolve_download(form_id)
        check('download serves the new bytes', raw_now == newer and err is None, str(err))

        duplicate = service.attach_file({'form_id': form_id}, 'again.pdf', newer, OPERATOR)
        check('byte-identical re-upload refused', duplicate.get('success') is False, str(duplicate))

        # ── 9. Archive is admin-only, delete does not exist ─────
        print('\n9. Archive and retention')
        result = service.set_status({'id': form_id, 'action': 'archive'}, OPERATOR)
        check('operator cannot archive', result.get('status') == 403, str(result))
        result = service.set_status({'id': form_id, 'action': 'archive'}, ADMIN)
        check('admin can archive', result.get('success') is True, str(result))
        check('archived form is not public', not service.public_payload()['forms'])
        _raw, _fn, _mime, err = service.resolve_download(form_id)
        check('archived form is not downloadable', err == 'Form not found', str(err))
        result = service.set_status({'id': form_id, 'action': 'delete'}, ADMIN)
        check('delete is not a valid action', result.get('success') is False, str(result))
        check('no delete function is exported',
              not any(n for n in dir(service) if 'delete' in n.lower() or 'purge' in n.lower()),
              str([n for n in dir(service) if 'delete' in n.lower()]))
        rows = db.execute('SELECT COUNT(*) n FROM embassy_forms').fetchone()['n']
        check('row still present after archive', rows == 1, str(rows))

        result = service.set_status({'id': form_id, 'action': 'restore'}, ADMIN)
        check('admin can restore', result.get('success') is True, str(result))
        check('restore lands in DRAFT', result.get('new_status') == 'DRAFT', str(result))

        # ── 10. Audit ───────────────────────────────────────────
        print('\n10. Audit')
        events = [r['event_type'] for r in audit.list_audit(db, form_id=form_id)]
        for expected in ('form_created', 'file_uploaded', 'file_replaced', 'form_published',
                         'form_archived', 'form_restored'):
            check(f'audit records {expected}', expected in events, str(sorted(set(events))))
        global_rows = db.execute('SELECT action FROM audit_log').fetchall()
        actions = {r['action'] for r in global_rows}
        check('publish written to the global audit_log', 'forms.publish' in actions, str(actions))
        check('archive written to the global audit_log', 'forms.archive' in actions, str(actions))
        check('routine edits stay out of the global audit_log', len(global_rows) == 2,
              str(len(global_rows)))

        # ── 11. Resilience ──────────────────────────────────────
        print('\n11. Resilience')
        core._DEPS['get_db'] = lambda: (_ for _ in ()).throw(RuntimeError('db down'))
        safe = service.public_payload_api()
        check('public API degrades to empty, never raises',
              safe == {'success': True, 'forms': [], 'categories': [], 'updatedDisplay': ''},
              str(safe))
        core._DEPS['get_db'] = open_db

        # ── 12. Helpers ─────────────────────────────────────────
        print('\n12. Helpers')
        check('human_file_size KB', core.human_file_size(240 * 1024) == '240 KB')
        check('human_file_size MB', core.human_file_size(1_500_000) == '1.4 MB')
        check('human_file_size zero', core.human_file_size(0) == '')
        check('display_date from timestamp', core.display_date('2026-08-10 09:05:00') == '10 Aug 2026')
        check('display_date from date', core.display_date('2026-08-01') == '1 Aug 2026')
        check('display_date rejects junk', core.display_date('not-a-date') == '')
        check('validate_date accepts empty', core.validate_date('') == ('', None))
        check('validate_date rejects 2026-13-45', core.validate_date('2026-13-45')[1] is not None)
        check('clean_slug normalises', core.clean_slug('Community  Welfare!') == 'community-welfare')
        check('normalize_language falls back', core.normalize_language('klingon') == 'en')
        check('normalize_status rejects unknown', core.normalize_status('BOGUS') == '')

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f'\nPassed: {PASSES}   Failed: {len(FAILURES)}')
    if FAILURES:
        for name in FAILURES:
            print(f'  - {name}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
