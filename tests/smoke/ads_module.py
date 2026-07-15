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

    print('— Public active-advertisement API (unauthenticated, read-only) —')
    status, headers, body = request(base, 'GET', '/api/public/advertisements/active')
    # 404 only when FEATURE_ADVERTISEMENTS is off.
    check('public ads endpoint reachable without auth', status in (200, 404), f'(got {status})')
    if status == 200:
        import json as _json
        try:
            payload = _json.loads(body.decode('utf-8', errors='replace'))
        except Exception as exc:
            payload = None
            check('public ads endpoint returns JSON', False, f'({exc})')
        if payload is not None:
            check('public ads endpoint returns JSON', True)
            check('response has success flag', payload.get('success') is True)
            check('response has advertisement key', 'advertisement' in payload)
            ad = payload.get('advertisement')
            check('advertisement is null or an object', ad is None or isinstance(ad, dict))
            # Unpublished ads must never reach the public API.
            check('preview flag never exposed publicly',
                  not isinstance(ad, dict) or 'preview' not in ad)
            if isinstance(ad, dict):
                for slot in ('popup', 'banner'):
                    item = ad.get(slot)
                    if not isinstance(item, dict):
                        continue
                    for field in ('image', 'mobileImage'):
                        url = item.get(field) or ''
                        if not url:
                            continue
                        # Relative media URLs would be fetched from the React
                        # site's own origin, where they 404.
                        check(f'{slot}.{field} is an absolute backend URL',
                              url.startswith('http://') or url.startswith('https://'),
                              f'(got {url!r} — set PUBLIC_BACKEND_ORIGIN)')
        check('public ads endpoint is cacheable',
              'public' in (headers.get('Cache-Control') or '').lower(),
              f"(got {headers.get('Cache-Control')!r})")

    # CORS: the React site is a different origin and must be allowed.
    for origin in ('https://cwakuwait.com', 'https://www.cwakuwait.com'):
        status, headers, _ = request(base, 'GET', '/api/public/advertisements/active',
                                     headers={'Origin': origin})
        if status == 404:
            continue  # feature flag off
        check(f'CORS allows {origin}',
              headers.get('Access-Control-Allow-Origin') == origin,
              f"(got {headers.get('Access-Control-Allow-Origin')!r})")
        status, headers, _ = request(base, 'OPTIONS', '/api/public/advertisements/active',
                                     headers={'Origin': origin,
                                              'Access-Control-Request-Method': 'GET'})
        check(f'CORS preflight allows {origin}',
              headers.get('Access-Control-Allow-Origin') == origin,
              f"(got {status} {headers.get('Access-Control-Allow-Origin')!r})")

    status, headers, _ = request(base, 'GET', '/api/public/advertisements/active',
                                 headers={'Origin': 'https://evil.example.com'})
    if status != 404:
        check('CORS rejects an unlisted origin',
              headers.get('Access-Control-Allow-Origin') is None,
              f"(got {headers.get('Access-Control-Allow-Origin')!r})")

    status, _, _ = request(base, 'POST', '/api/public/advertisements/active', body=b'{}',
                           headers=json_hdr)
    check('public ads endpoint is GET-only', status in (405, 404), f'(got {status})')

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
