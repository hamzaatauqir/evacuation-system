#!/usr/bin/env python3
"""Website Advertisements — localhost-only E2E workflow test. MUTATES the local DB.

Covers: permissions (admin vs operator/operator_special/unauth), lifecycle
(create/update/duplicate/activate/pause/archive), scheduling windows
(Kuwait-time boundaries), activation conflicts, optimistic locking,
content_version semantics, image uploads (accept + reject matrix, additive
replacement), XSS-payload embedding, URL validation, public homepage payload,
media serving, and the admin preview.

Test artifacts (users 'ads-smoke-operator'/'ads-smoke-opspecial', ads named
'ADS-SMOKE …', uploaded test images) are left in the local DB, archived,
mirroring the hostel workflow test convention.

Usage: python3 tests/smoke/ads_workflow.py http://localhost:8080
"""
from __future__ import annotations

import http.client
import io
import json
import os
import re
import secrets
import struct
import sys
import zlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

ADMIN_USER = os.environ.get('ADS_SMOKE_ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADS_SMOKE_ADMIN_PASS', 'embassy2026')

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
    hdrs = {'User-Agent': 'ads-workflow-smoke/1.0', 'Connection': 'close'}
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
    status, headers, payload = request(method, path, body=body, cookie=cookie,
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
    set_cookie = headers.get('Set-Cookie', '')
    match = re.search(r'session=([0-9a-f]+)', set_cookie)
    return f'session={match.group(1)}' if match else None


# ── Test image builders ──────────────────────────────────────────

def build_png(width=800, height=400):
    """Valid PNG via stdlib only (grayscale, filter 0)."""
    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)
    raw = b''.join(b'\x00' + bytes([(x + y) % 256 for x in range(width)])
                   for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def build_pil_image(fmt, width=800, height=400):
    try:
        from PIL import Image
    except Exception:
        return None
    img = Image.new('RGB', (width, height), (16, 110, 9))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def multipart(fields, file_field, filename, file_bytes):
    boundary = 'adsSmoke' + secrets.token_hex(8)
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
                  f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
                 + file_bytes + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def upload(cookie, ad_id, slot, filename, file_bytes):
    body, ctype = multipart({'ad_id': str(ad_id), 'slot': slot}, 'file', filename, file_bytes)
    status, _, payload = request('POST', '/api/admin/advertisements/upload-image',
                                 body=body, cookie=cookie, headers={'Content-Type': ctype})
    try:
        return status, json.loads(payload.decode('utf-8', errors='replace'))
    except Exception:
        return status, {}


# ── Save-payload helper (save is a full-row update) ──────────────

SAVE_FIELDS = ['internal_name', 'campaign_reference', 'disclosure_label', 'language',
               'display_frequency', 'dismissal_hours', 'popup_enabled', 'banner_enabled',
               'heading', 'heading_ur', 'description', 'description_ur', 'image_alt_text',
               'cta_label', 'cta_url', 'cta_new_tab', 'contact_number', 'external_website',
               'banner_heading', 'banner_heading_ur', 'banner_description', 'banner_description_ur',
               'banner_button_label', 'banner_button_url', 'banner_dismissible',
               'starts_at_kw', 'ends_at_kw']


def save_payload_from(item, **overrides):
    data = {f: item.get(f, '') for f in SAVE_FIELDS}
    data['id'] = item['id']
    data['expected_updated_at'] = item['updated_at']
    data.update(overrides)
    return data


def detail(cookie, ad_id):
    _, _, body = jreq('GET', f'/api/admin/advertisements/detail?id={ad_id}', cookie=cookie)
    return body.get('item') or {}


def homepage_payload():
    status, _, body = request('GET', '/')
    html = body.decode('utf-8', errors='replace')
    match = re.search(r'window\.CWA_ADS = (.*?);\s*</script>', html, re.S)
    if not match:
        return status, html, 'MISSING'
    try:
        return status, html, json.loads(match.group(1))
    except Exception:
        return status, html, 'UNPARSEABLE'


def kuwait_str(delta_hours=0):
    return (datetime.now(timezone.utc) + timedelta(hours=3 + delta_hours)).strftime('%Y-%m-%dT%H:%M')


def main(argv):
    global BASE
    if len(argv) != 2:
        print('Usage: python3 tests/smoke/ads_workflow.py http://localhost:8080')
        return 2
    BASE = argv[1].rstrip('/')
    host = urlsplit(BASE).hostname or ''
    if host not in ('localhost', '127.0.0.1'):
        print('Refusing to run: this E2E test mutates the DB and only runs against localhost.')
        return 2

    print('— Login / test users —')
    admin = login(ADMIN_USER, ADMIN_PASS)
    if not admin:
        print(f'FATAL: could not log in as {ADMIN_USER}. Set ADS_SMOKE_ADMIN_USER/ADS_SMOKE_ADMIN_PASS.')
        return 1
    check('admin login', True)

    op_pass = 'AdsSmoke-' + secrets.token_hex(6)
    operators = {}
    for username, role in (('ads-smoke-operator', 'operator'),
                           ('ads-smoke-opspecial', 'operator_special')):
        status, _, body = jreq('POST', '/api/user',
                               {'username': username, 'password': op_pass, 'role': role,
                                'full_name': f'Ads Smoke {role}'}, cookie=admin)
        created = bool(body.get('success'))
        exists = 'exists' in str(body.get('error', '')).lower()
        check(f'create {role} test user', created or exists, str(body))
        if exists:
            # Password unknown from a previous run with a random password —
            # reset it via the update API if available; otherwise skip login.
            uid = None
            _, _, users = jreq('GET', '/api/users', cookie=admin)
            for u in (users if isinstance(users, list) else users.get('users', []) or []):
                if u.get('username') == username:
                    uid = u.get('id')
            if uid:
                jreq('POST', '/api/user/update',
                     {'id': uid, 'new_password': op_pass, 'role': role}, cookie=admin)
        operators[role] = login(username, op_pass)
        check(f'{role} login', bool(operators[role]))

    print('— Permissions: strict admin-only management —')
    for role, cookie in operators.items():
        if not cookie:
            check(f'{role} denied (skipped — login unavailable)', False)
            continue
        status, _, body = jreq('GET', '/api/admin/advertisements', cookie=cookie)
        check(f'{role} list denied 403', status == 403, f'(got {status})')
        status, _, body = jreq('POST', '/api/admin/advertisements/save',
                               {'internal_name': 'x'}, cookie=cookie)
        check(f'{role} save denied 403', status == 403, f'(got {status})')
        status, _, _ = request('GET', '/admin/advertisements', cookie=cookie)
        check(f'{role} page denied 403', status == 403, f'(got {status})')
        status, _, _ = request('GET', '/admin/advertisements/preview?id=1', cookie=cookie)
        check(f'{role} preview denied 403', status == 403, f'(got {status})')
    status, _, _ = jreq('GET', '/api/admin/advertisements')
    check('unauthenticated list redirected', status == 302, f'(got {status})')

    print('— Create (with hostile content) —')
    xss_heading = 'ADS-SMOKE </script><b>Mangoes</b> & "quotes"  line'
    status, _, body = jreq('POST', '/api/admin/advertisements/save', {
        'internal_name': 'ADS-SMOKE popup campaign',
        'campaign_reference': 'SMOKE-2026-01',
        'disclosure_label': 'Campaign',
        'popup_enabled': '1',
        'heading': xss_heading,
        'description': 'Test description with <i>markup</i> & ampersand.',
        'heading_ur': 'پاکستانی آم',
        'description_ur': 'اردو تفصیل',
        'image_alt_text': '',
        'cta_label': 'View Details',
        'cta_url': 'https://mangoesfrompakistan.example/details',
        'contact_number': '+965 6667 2841',
        'external_website': 'https://mangoesfrompakistan.example',
        'display_frequency': 'once_per_version',
        'dismissal_hours': 168,
    }, cookie=admin)
    check('create ad1', body.get('success') is True, str(body))
    ad1 = (body.get('item') or {}).get('id')
    if not ad1:
        print('FATAL: cannot continue without ad1')
        return 1
    item1 = body['item']
    check('ad1 starts as DRAFT', item1.get('status') == 'DRAFT')
    check('ad1 content_version 1', item1.get('content_version') == 1)

    print('— URL validation —')
    for bad in ('javascript:alert(1)', 'data:text/html,x', 'http://plain.example',
                '//protocol-relative.example', 'https://user:pw@creds.example/x',
                'not a url'):
        _, _, body = jreq('POST', '/api/admin/advertisements/save',
                          save_payload_from(detail(admin, ad1), cta_url=bad), cookie=admin)
        check(f'cta_url rejected: {bad[:32]}', body.get('success') is False, str(body))
    for good in ('/nurses', 'https://mangoesfrompakistan.example/details'):
        _, _, body = jreq('POST', '/api/admin/advertisements/save',
                          save_payload_from(detail(admin, ad1), cta_url=good), cookie=admin)
        check(f'cta_url accepted: {good}', body.get('success') is True, str(body))

    print('— Image uploads —')
    png = build_png(800, 400)
    small_png = build_png(200, 200)
    jpeg = build_pil_image('JPEG')
    webp = build_pil_image('WEBP')

    status, body = upload(admin, ad1, 'popup', 'poster.png', png)
    if body.get('success') is False and 'Pillow' in str(body.get('error', '')):
        print('  SKIP  image accept/replacement/serving suite — server Python lacks Pillow')
        print('        (production installs it via requirements.txt; re-run with a Pillow-enabled')
        print('        interpreter to cover the accept path).')
        pil_server = False
    else:
        pil_server = True
        check('valid PNG accepted', body.get('success') is True, str(body))
    first_stored = (body.get('item') or {}).get('popup_image', '')

    if pil_server and jpeg is not None:
        _, body = upload(admin, ad1, 'popup_mobile', 'poster.jpg', jpeg)
        check('valid JPEG accepted', body.get('success') is True, str(body))
    if pil_server and webp is not None:
        _, body = upload(admin, ad1, 'banner', 'poster.webp', webp)
        check('valid WebP accepted', body.get('success') is True, str(body))

    _, body = upload(admin, ad1, 'popup', 'evil.svg', b'<svg onload="alert(1)"></svg>')
    check('SVG rejected', body.get('success') is False, str(body))
    _, body = upload(admin, ad1, 'popup', 'mismatch.jpg', png)
    check('extension/signature mismatch rejected', body.get('success') is False, str(body))
    _, body = upload(admin, ad1, 'popup', 'garbage.png', b'\x00\x01\x02\x03 not an image')
    check('invalid bytes rejected', body.get('success') is False, str(body))
    _, body = upload(admin, ad1, 'popup', 'big.png', b'\x89PNG\r\n\x1a\n' + b'0' * (4 * 1024 * 1024 + 100))
    check('oversized file rejected', body.get('success') is False, str(body))
    if pil_server:
        _, body = upload(admin, ad1, 'popup', 'small.png', small_png)
        check('below-minimum-width image rejected', body.get('success') is False, str(body))
        after = detail(admin, ad1)
        check('failed replacement preserves existing image',
              after.get('popup_image') == first_stored,
              f"({after.get('popup_image')} vs {first_stored})")
        if first_stored:
            status, headers, _ = request('GET', f'/ads/media/{first_stored}')
            check('stored image publicly served', status == 200, f'(got {status})')
            check('image immutable cache header',
                  'immutable' in headers.get('Cache-Control', ''), str(headers.get('Cache-Control')))
            check('image content-type', headers.get('Content-Type') == 'image/png')
            # additive replacement: upload a new popup image, old file must remain
            _, body = upload(admin, ad1, 'popup', 'poster2.png', build_png(900, 450))
            check('replacement upload accepted', body.get('success') is True, str(body))
            status, _, _ = request('GET', f'/ads/media/{first_stored}')
            check('previous image file retained after replacement', status == 200, f'(got {status})')

    print('— Activation validation + lifecycle —')
    item1 = detail(admin, ad1)
    if pil_server and item1.get('popup_image'):
        _, _, body = jreq('POST', '/api/admin/advertisements/status',
                          {'id': ad1, 'action': 'activate'}, cookie=admin)
        check('activation blocked without alt text', body.get('success') is False, str(body))
    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(detail(admin, ad1),
                                        image_alt_text='Fresh Pakistani mangoes promotion'),
                      cookie=admin)
    check('set alt text', body.get('success') is True, str(body))
    _, _, body = jreq('POST', '/api/admin/advertisements/status',
                      {'id': ad1, 'action': 'activate'}, cookie=admin)
    check('activate ad1', body.get('success') is True, str(body))

    print('— Public homepage payload —')
    status, html, payload = homepage_payload()
    check('homepage 200 with active ad', status == 200)
    check('payload parses as JSON', isinstance(payload, dict), str(payload)[:80])
    if isinstance(payload, dict):
        popup = payload.get('popup') or {}
        check('popup payload present', bool(popup))
        check('XSS heading survives round-trip intact', popup.get('heading') == xss_heading)
        check('Urdu content present', popup.get('headingUr') == 'پاکستانی آم')
    match = re.search(r'window\.CWA_ADS = (.*?);\s*</script>', html, re.S)
    payload_raw = match.group(1) if match else ''
    check('no raw </script> inside payload', '</script' not in payload_raw)
    check('script-closing sequence escaped', '\\u003c' in payload_raw)
    check('U+2028 escaped', '\\u2028' in payload_raw)

    print('— Pause / scheduling windows (Kuwait boundaries) —')
    _, _, body = jreq('POST', '/api/admin/advertisements/status',
                      {'id': ad1, 'action': 'pause'}, cookie=admin)
    check('pause ad1', body.get('success') is True, str(body))
    _, _, payload = homepage_payload()
    check('paused ad hidden from homepage', payload is None, str(payload)[:80])

    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(detail(admin, ad1),
                                        starts_at_kw=kuwait_str(+2), ends_at_kw=kuwait_str(+4)),
                      cookie=admin)
    check('set future window', body.get('success') is True, str(body))
    _, _, body = jreq('POST', '/api/admin/advertisements/status',
                      {'id': ad1, 'action': 'activate'}, cookie=admin)
    check('activate scheduled ad', body.get('success') is True, str(body))
    item1 = detail(admin, ad1)
    check('effective status SCHEDULED before start', item1.get('effective_status') == 'SCHEDULED',
          str(item1.get('effective_status')))
    _, _, payload = homepage_payload()
    check('scheduled ad hidden before start', payload is None, str(payload)[:80])

    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(detail(admin, ad1),
                                        starts_at_kw=kuwait_str(-2), ends_at_kw=kuwait_str(+2)),
                      cookie=admin)
    check('set open window', body.get('success') is True, str(body))
    _, _, payload = homepage_payload()
    check('active-in-window ad visible', isinstance(payload, dict) and bool(payload.get('popup')),
          str(payload)[:80])

    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(detail(admin, ad1),
                                        starts_at_kw=kuwait_str(-4), ends_at_kw=kuwait_str(-2)),
                      cookie=admin)
    check('set past window', body.get('success') is True, str(body))
    item1 = detail(admin, ad1)
    check('effective status EXPIRED after end', item1.get('effective_status') == 'EXPIRED',
          str(item1.get('effective_status')))
    _, _, payload = homepage_payload()
    check('expired ad hidden after end', payload is None, str(payload)[:80])

    # restore an open window for the conflict test below
    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(detail(admin, ad1), starts_at_kw='', ends_at_kw=''),
                      cookie=admin)
    check('clear window', body.get('success') is True, str(body))

    print('— content_version semantics —')
    item1 = detail(admin, ad1)
    v_before = item1['content_version']
    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(item1, internal_name='ADS-SMOKE popup campaign (renamed)'),
                      cookie=admin)
    check('internal-only edit does not bump version',
          body.get('success') is True and body['item']['content_version'] == v_before, str(body)[:120])
    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(detail(admin, ad1), heading=xss_heading + ' v2'),
                      cookie=admin)
    check('public edit bumps version',
          body.get('success') is True and body['item']['content_version'] == v_before + 1, str(body)[:120])

    print('— Conflict detection + confirmation —')
    _, _, body = jreq('POST', '/api/admin/advertisements/save', {
        'internal_name': 'ADS-SMOKE second popup',
        'popup_enabled': '1',
        'heading': 'Second campaign',
        'display_frequency': 'once_per_version',
        'dismissal_hours': 168,
    }, cookie=admin)
    ad2 = (body.get('item') or {}).get('id')
    check('create ad2', bool(ad2), str(body)[:120])
    status, _, body = jreq('POST', '/api/admin/advertisements/status',
                           {'id': ad2, 'action': 'activate'}, cookie=admin)
    check('conflicting activation returns 409 + conflict list',
          status == 409 and body.get('conflicts'), f'(got {status} {str(body)[:120]})')
    _, _, body = jreq('POST', '/api/admin/advertisements/status',
                      {'id': ad2, 'action': 'activate', 'confirm_conflict': '1'}, cookie=admin)
    check('confirmed activation succeeds', body.get('success') is True, str(body)[:120])
    item1 = detail(admin, ad1)
    check('previous ad auto-paused on confirm', item1.get('status') == 'PAUSED',
          str(item1.get('status')))

    print('— Optimistic locking —')
    status, _, body = jreq('POST', '/api/admin/advertisements/save',
                           save_payload_from(detail(admin, ad2),
                                             expected_updated_at='2000-01-01 00:00:00'),
                           cookie=admin)
    check('stale save returns 409', status == 409, f'(got {status} {str(body)[:100]})')

    print('— Duplicate / archive —')
    _, _, body = jreq('POST', '/api/admin/advertisements/duplicate', {'id': ad2}, cookie=admin)
    ad3 = (body.get('item') or {}).get('id')
    check('duplicate creates new DRAFT v1',
          bool(ad3) and body['item']['status'] == 'DRAFT' and body['item']['content_version'] == 1,
          str(body)[:120])
    _, _, payload = homepage_payload()
    check('draft duplicate not public',
          not (isinstance(payload, dict) and (payload.get('popup') or {}).get('id') == ad3))
    _, _, body = jreq('POST', '/api/admin/advertisements/status',
                      {'id': ad2, 'action': 'archive'}, cookie=admin)
    check('archive ad2', body.get('success') is True, str(body)[:120])
    _, _, payload = homepage_payload()
    check('archived ad hidden', payload is None, str(payload)[:80])
    _, _, body = jreq('POST', '/api/admin/advertisements/status',
                      {'id': ad2, 'action': 'activate'}, cookie=admin)
    check('archived ad cannot be reactivated', body.get('success') is False, str(body)[:120])
    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from({**detail(admin, ad2), 'updated_at': 'x'}),
                      cookie=admin)
    check('archived ad cannot be edited', body.get('success') is False, str(body)[:120])

    print('— Banner placement payload —')
    _, _, body = jreq('POST', '/api/admin/advertisements/save',
                      save_payload_from(detail(admin, ad3),
                                        internal_name='ADS-SMOKE banner',
                                        banner_enabled='1',
                                        banner_heading='Banner heading',
                                        banner_description='Short banner text',
                                        banner_button_label='View Details',
                                        banner_button_url='/nurses'),
                      cookie=admin)
    check('configure banner on ad3', body.get('success') is True, str(body)[:120])
    _, _, body = jreq('POST', '/api/admin/advertisements/status',
                      {'id': ad3, 'action': 'activate'}, cookie=admin)
    check('activate ad3', body.get('success') is True, str(body)[:120])
    _, _, payload = homepage_payload()
    if isinstance(payload, dict):
        check('banner payload present', bool(payload.get('banner')), str(payload)[:100])
        check('popup and banner from same ad allowed',
              (payload.get('popup') or {}).get('id') == ad3)
    else:
        check('banner payload present', False, str(payload)[:80])

    print('— Audit trail —')
    _, _, body = jreq('GET', f'/api/admin/advertisements/audit?id={ad1}', cookie=admin)
    events = {row.get('event_type') for row in body.get('items', [])}
    actors = {row.get('actor') for row in body.get('items', [])}
    check('audit records exist', bool(body.get('items')), str(body)[:80])
    check('audit covers lifecycle events',
          {'created', 'updated', 'activated'} <= events, str(sorted(events)))
    check('audit records actor', ADMIN_USER in actors, str(actors))

    print('— Admin preview —')
    status, headers, payload_bytes = request('GET', f'/admin/advertisements/preview?id={ad3}',
                                             cookie=admin)
    html = payload_bytes.decode('utf-8', errors='replace')
    check('preview 200 for admin', status == 200, f'(got {status})')
    check('preview marks payload as preview', '"preview": true' in html)
    check('preview sends noindex', 'noindex' in headers.get('X-Robots-Tag', ''),
          str(headers.get('X-Robots-Tag')))
    check('preview sends no-store', 'no-store' in headers.get('Cache-Control', ''),
          str(headers.get('Cache-Control')))
    status, _, _ = request('GET', f'/admin/advertisements/preview?id={ad3}')
    check('preview gated for unauth', status == 302, f'(got {status})')

    print('— Cleanup (archive test ads; rows retained for audit) —')
    for ad_id in (ad1, ad3):
        _, _, body = jreq('POST', '/api/admin/advertisements/status',
                          {'id': ad_id, 'action': 'archive'}, cookie=admin)
    _, _, payload = homepage_payload()
    check('homepage ad-free after cleanup', payload is None, str(payload)[:80])

    print(f'\nPassed: {PASSES}  Failed: {len(FAILURES)}')
    if FAILURES:
        for name in FAILURES:
            print(f'  - {name}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
