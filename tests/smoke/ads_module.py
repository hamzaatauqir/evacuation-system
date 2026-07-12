#!/usr/bin/env python3
"""Read-only smoke gates for the Website Advertisements module.

Stdlib-only, no login, no mutations — safe against any environment.
Usage: python3 tests/smoke/ads_module.py http://localhost:8080
"""
from __future__ import annotations

import http.client
import sys
from urllib.parse import urlsplit

FAILURES = []
PASSES = 0


def request(base_url, method, path, body=None, headers=None):
    parsed = urlsplit(base_url)
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
    conn = conn_cls(parsed.hostname, port, timeout=10)
    hdrs = {'User-Agent': 'ads-module-smoke/1.0', 'Connection': 'close'}
    hdrs.update(headers or {})
    try:
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        payload = resp.read()
        return resp.status, dict(resp.getheaders()), payload
    finally:
        conn.close()


def check(name, ok, detail=''):
    global PASSES
    if ok:
        PASSES += 1
        print(f'  PASS  {name}')
    else:
        FAILURES.append(name)
        print(f'  FAIL  {name} {detail}')


def main(argv):
    if len(argv) != 2:
        print('Usage: python3 tests/smoke/ads_module.py http://localhost:8080')
        return 2
    base = argv[1].rstrip('/')
    json_hdr = {'Content-Type': 'application/json'}

    print('— Unauthenticated gates (admin management must be unreachable) —')
    for method, path, body in [
        ('GET', '/admin/advertisements', None),
        ('GET', '/admin/advertisements/preview?id=1', None),
        ('GET', '/api/admin/advertisements', None),
        ('GET', '/api/admin/advertisements/detail?id=1', None),
        ('GET', '/api/admin/advertisements/audit?id=1', None),
        ('POST', '/api/admin/advertisements/save', b'{}'),
        ('POST', '/api/admin/advertisements/status', b'{}'),
        ('POST', '/api/admin/advertisements/duplicate', b'{}'),
        ('POST', '/api/admin/advertisements/upload-image', b''),
    ]:
        status, _, _ = request(base, method, path, body=body,
                               headers=json_hdr if body is not None else None)
        # 302 = redirected to /login (flag on); 404 = feature flag off.
        check(f'{method} {path} gated', status in (302, 404), f'(got {status})')

    print('— Public media route —')
    status, _, _ = request(base, 'GET', '/ads/media/does-not-exist.png')
    check('missing media -> 404 (or 404 flag-off)', status == 404, f'(got {status})')
    status, _, _ = request(base, 'GET', '/ads/media/..%2f..%2fserver.py')
    check('traversal attempt not served', status != 200, f'(got {status})')
    status, _, _ = request(base, 'GET', '/ads/media/evil.svg')
    check('svg never served from media route', status == 404, f'(got {status})')

    print('— Public homepage integration & regression —')
    status, _, body = request(base, 'GET', '/')
    html = body.decode('utf-8', errors='replace')
    check('homepage 200', status == 200, f'(got {status})')
    if status == 200:
        check('homepage still has hero heading',
              'Community Welfare Wing Digital Services' in html)
        check('homepage still has seasonal campaign element',
              'internationalNursesDayBanner' in html)
        check('homepage still has contact info', '+965 5597 7292' in html)
        check('homepage still has service grid', 'cwa-service-grid' in html)
        check('ad banner slot present', 'cwaAdBannerSlot' in html)
        check('ad payload embedded', 'window.CWA_ADS =' in html)
        check('ad payload token substituted', '__AD_PAYLOAD_JSON__' not in html)
        check('site-ads.js referenced', 'site-ads.js' in html)

    status, _, body = request(base, 'GET', '/static/js/site-ads.js')
    check('site-ads.js served', status == 200, f'(got {status})')
    if status == 200:
        js = body.decode('utf-8', errors='replace')
        check('site-ads.js exposes CwaSiteAds', 'CwaSiteAds' in js)
        check('site-ads.js never uses innerHTML', 'innerHTML' not in js)

    print(f'\nPassed: {PASSES}  Failed: {len(FAILURES)}')
    if FAILURES:
        for name in FAILURES:
            print(f'  - {name}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
