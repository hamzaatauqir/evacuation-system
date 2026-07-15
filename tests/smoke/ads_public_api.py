#!/usr/bin/env python3
"""Unit gates for the public advertisement API selection + media URLs.

Runs against an in-memory SQLite database — no server, no login, no network,
and it never touches the real portal database.

Covers the two rules the public surface must never break:
  1. Only genuinely published advertisements are returned (ACTIVE and inside
     the schedule window). DRAFT / PAUSED / ARCHIVED / SCHEDULED / EXPIRED are
     excluded — the admin preview deliberately bypasses this, the API must not.
  2. Media URLs handed to the cross-origin React site are absolute, so the
     browser fetches them from the backend and not from cwakuwait.com.

Usage: python3 tests/smoke/ads_public_api.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.domains.ads import core, schema, service  # noqa: E402

FAILURES = []
PASSES = 0
BACKEND = 'https://evacuation-system.onrender.com'


def check(name, ok, detail=''):
    global PASSES
    if ok:
        PASSES += 1
        print(f'  PASS  {name}')
    else:
        FAILURES.append(name)
        print(f'  FAIL  {name} {detail}')


def utc(offset_hours=0):
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).strftime('%Y-%m-%d %H:%M:%S')


class KeepOpenConnection(sqlite3.Connection):
    """service.* closes the db it is handed; an in-memory DB would be lost."""

    def close(self):  # noqa: D102
        pass


_DB = None


def make_db():
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(':memory:', factory=KeepOpenConnection)
        _DB.row_factory = sqlite3.Row
        schema.ensure_schema(_DB)
    return _DB


def insert_ad(db, **over):
    fields = {
        'internal_name': 'Test ad',
        'status': 'ACTIVE',
        'popup_enabled': 1,
        'banner_enabled': 1,
        'popup_image': 'popup-abc.png',
        'popup_mobile_image': 'popup-m-abc.png',
        'banner_image': 'banner-abc.png',
        'banner_mobile_image': '',
        'image_alt_text': 'Poster',
        'heading': 'Heading',
        'banner_heading': 'Banner heading',
        'content_version': 1,
        'starts_at': '',
        'ends_at': '',
        'updated_at': utc(),
    }
    fields.update(over)
    cols = ', '.join(fields)
    marks = ', '.join('?' for _ in fields)
    cur = db.execute(f'INSERT INTO website_advertisements ({cols}) VALUES ({marks})',
                     list(fields.values()))
    db.commit()
    return cur.lastrowid


def reset(db):
    db.execute('DELETE FROM website_advertisements')
    db.commit()


def main():
    db = make_db()
    core.configure(get_db=lambda: db, data_root=Path('/tmp'), project_root=Path('/tmp'),
                   extract_multipart_upload=lambda *a, **k: (None, None))
    os.environ['PUBLIC_BACKEND_ORIGIN'] = BACKEND

    print('— Publication status filtering (public API must show only live ads) —')
    for status, visible in [
        ('ACTIVE', True),
        ('DRAFT', False),
        ('PAUSED', False),
        ('ARCHIVED', False),
    ]:
        reset(db)
        insert_ad(db, status=status)
        result = service.public_payload_api()
        ad = result.get('advertisement')
        got = ad is not None
        check(f'{status} advertisement {"is" if visible else "is NOT"} returned',
              got is visible, f'(got advertisement={ad!r})')

    print('— Schedule window (SCHEDULED / EXPIRED are derived, not stored) —')
    reset(db)
    insert_ad(db, status='ACTIVE', starts_at=utc(+48))
    check('SCHEDULED (starts in the future) is NOT returned',
          service.public_payload_api().get('advertisement') is None)

    reset(db)
    insert_ad(db, status='ACTIVE', ends_at=utc(-1))
    check('EXPIRED (already ended) is NOT returned',
          service.public_payload_api().get('advertisement') is None)

    reset(db)
    insert_ad(db, status='ACTIVE', starts_at=utc(-48), ends_at=utc(+48))
    check('ACTIVE inside its window IS returned',
          service.public_payload_api().get('advertisement') is not None)

    print('— Payload shape —')
    reset(db)
    ad_id = insert_ad(db, status='ACTIVE', heading='Nurses Day', banner_heading='Banner')
    result = service.public_payload_api()
    check('success flag set', result.get('success') is True)
    ad = result.get('advertisement') or {}
    check('popup present', isinstance(ad.get('popup'), dict))
    check('banner present', isinstance(ad.get('banner'), dict))
    check('preview flag never present', 'preview' not in ad)
    check('popup id matches', (ad.get('popup') or {}).get('id') == ad_id)
    check('popup heading carried', (ad.get('popup') or {}).get('heading') == 'Nurses Day')

    print('— Placement flags —')
    reset(db)
    insert_ad(db, popup_enabled=1, banner_enabled=0)
    ad = service.public_payload_api().get('advertisement') or {}
    check('popup-only ad has no banner', ad.get('banner') is None and ad.get('popup') is not None)

    reset(db)
    insert_ad(db, popup_enabled=0, banner_enabled=1)
    ad = service.public_payload_api().get('advertisement') or {}
    check('banner-only ad has no popup', ad.get('popup') is None and ad.get('banner') is not None)

    reset(db)
    insert_ad(db, popup_enabled=0, banner_enabled=0)
    check('ad with no placement is NOT returned',
          service.public_payload_api().get('advertisement') is None)

    print('— Absolute media URLs (cross-origin correctness) —')
    reset(db)
    insert_ad(db, status='ACTIVE')
    ad = service.public_payload_api().get('advertisement') or {}
    popup = ad.get('popup') or {}
    banner = ad.get('banner') or {}
    check('popup image is absolute',
          popup.get('image') == f'{BACKEND}/ads/media/popup-abc.png', f"(got {popup.get('image')!r})")
    check('popup mobile image is absolute',
          popup.get('mobileImage') == f'{BACKEND}/ads/media/popup-m-abc.png')
    check('banner image is absolute',
          banner.get('image') == f'{BACKEND}/ads/media/banner-abc.png')
    check('empty image stays empty (not a bare origin)', banner.get('mobileImage') == '')

    print('— PUBLIC_BACKEND_ORIGIN handling —')
    os.environ['PUBLIC_BACKEND_ORIGIN'] = f'{BACKEND}/'
    check('trailing slash normalised', core.public_backend_origin() == BACKEND)
    check('no duplicated slash in media url',
          '//ads/media' not in (service.public_payload_api()['advertisement']['popup']['image']))
    os.environ['PUBLIC_BACKEND_ORIGIN'] = f'{BACKEND}///'
    check('multiple trailing slashes normalised', core.public_backend_origin() == BACKEND)
    os.environ['PUBLIC_BACKEND_ORIGIN'] = 'not-a-url'
    check('garbage origin ignored', core.public_backend_origin() == '')
    os.environ['PUBLIC_BACKEND_ORIGIN'] = 'javascript:alert(1)'
    check('javascript: scheme ignored', core.public_backend_origin() == '')
    os.environ['PUBLIC_BACKEND_ORIGIN'] = 'data:text/html,<script>alert(1)</script>'
    check('data: scheme ignored', core.public_backend_origin() == '')
    os.environ['PUBLIC_BACKEND_ORIGIN'] = '//evil.example.com'
    check('protocol-relative origin ignored', core.public_backend_origin() == '')
    os.environ['PUBLIC_BACKEND_ORIGIN'] = BACKEND
    for slot in ('popup', 'banner'):
        url = service.public_payload_api()['advertisement'][slot]['image']
        check(f'{slot} media url has a safe scheme', url.startswith('https://'))
    del os.environ['PUBLIC_BACKEND_ORIGIN']
    check('unset origin degrades to relative', core.public_backend_origin() == '')
    ad = service.public_payload_api().get('advertisement') or {}
    check('unset origin still serves a relative media path',
          (ad.get('popup') or {}).get('image') == '/ads/media/popup-abc.png')

    print('— Mount prefix is env-only (never request-header controlled) —')
    os.environ['PUBLIC_BACKEND_ORIGIN'] = BACKEND
    os.environ['PUBLIC_BASE_PATH'] = '/portal'
    check('PUBLIC_BASE_PATH applied',
          service.public_payload_api()['advertisement']['popup']['image']
          == f'{BACKEND}/portal/ads/media/popup-abc.png')
    os.environ['PUBLIC_BASE_PATH'] = 'https://evil.example.com/x'
    check('host stripped from a prefix that carries one',
          core.public_base_path() == '/x')
    check('media origin stays the configured backend',
          service.public_payload_api()['advertisement']['popup']['image']
          .startswith(f'{BACKEND}/'))
    os.environ['PUBLIC_BASE_PATH'] = '/'
    check('bare slash prefix normalises to empty', core.public_base_path() == '')
    del os.environ['PUBLIC_BASE_PATH']
    check('unset prefix is empty', core.public_base_path() == '')
    # public_payload_api takes no request state at all — the signature itself
    # is the guarantee that no header can vary this cacheable response.
    import inspect
    check('public_payload_api accepts no request arguments',
          list(inspect.signature(service.public_payload_api).parameters) == [])

    print('— Embedded homepage payload keeps relative URLs (Flask + preview) —')
    os.environ['PUBLIC_BACKEND_ORIGIN'] = BACKEND
    reset(db)
    insert_ad(db, status='ACTIVE')
    embedded = service.public_payload_json()
    check('embedded payload is relative, not absolute',
          '/ads/media/popup-abc.png' in embedded and BACKEND not in embedded,
          f'(got {embedded[:120]!r})')
    reset(db)
    insert_ad(db, status='DRAFT')
    check('embedded payload is null for an unpublished ad',
          service.public_payload_json() == 'null')

    print('— Admin preview still shows unpublished ads (must NOT regress) —')
    reset(db)
    draft_id = insert_ad(db, status='DRAFT', heading='Unpublished')
    preview = service.preview_payload_json(draft_id)
    check('preview renders a DRAFT ad', preview is not None and 'Unpublished' in preview)
    check('preview marks itself as preview', '"preview": true' in (preview or '').replace('":true', '": true'))
    check('preview of a missing ad returns None', service.preview_payload_json(99999) is None)
    check('public API still hides that same DRAFT ad',
          service.public_payload_api().get('advertisement') is None)

    print(f'\nPassed: {PASSES}  Failed: {len(FAILURES)}')
    if FAILURES:
        for name in FAILURES:
            print(f'  - {name}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
