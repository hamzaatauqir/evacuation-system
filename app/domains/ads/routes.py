"""Website Advertisements module — HTTP dispatch layer.

server.py forwards any request whose path matches matches_path() to
handle_get()/handle_post(). The handler argument is the live
BaseHTTPRequestHandler instance, so responses reuse the portal's existing
send_json/send_html helpers (security headers included).

Management endpoints are strictly admin-role only (owner decision #1): the
portal's require_auth() runs first, then an explicit in-handler role check —
operator / operator_special are rejected even though route-level RBAC would
admit them. The only public surfaces are /ads/media/* (read-only images with
generated names) and the payload server.py embeds into the homepage.
"""
import json
import re

from . import core, media, service
from .audit import list_audit

ADMIN_PAGE_PATH = '/admin/advertisements'
PREVIEW_PATH = '/admin/advertisements/preview'
MEDIA_PREFIX = '/ads/media/'


def matches_path(path):
    return (
        path == ADMIN_PAGE_PATH
        or path == PREVIEW_PATH
        or path.startswith('/api/admin/advertisements')
        or path.startswith(MEDIA_PREFIX)
    )


def _send_api_result(handler, result):
    status = result.pop('status', None) if isinstance(result, dict) else None
    if status is None:
        status = 200 if result.get('success') else 400
    handler.send_json(result, int(status))


def _parse_json(handler, body):
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError:
        handler.send_json({'success': False, 'error': 'Invalid request'}, 400)
        return None


def _admin_user(handler):
    """Strict admin gate. Sends the error response itself on failure."""
    user = handler.require_auth()
    if not user:
        return None
    if not core.user_can_manage(user):
        handler.send_json({'success': False, 'error': 'Access denied'}, 403)
        return None
    return user


def _multipart_text_fields(body, content_type, field_names):
    """Extract simple text fields from a multipart body (upload side-channel data)."""
    values = {}
    if not body or 'boundary=' not in (content_type or ''):
        return values
    boundary = content_type.split('boundary=', 1)[1].strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    for part in body.split(b'--' + boundary.encode()):
        sep = b'\r\n\r\n' if b'\r\n\r\n' in part else (b'\n\n' if b'\n\n' in part else None)
        if not sep:
            continue
        head, _, rest = part.partition(sep)
        try:
            disp = head.decode('latin-1', errors='replace')
        except Exception:
            continue
        if 'filename="' in disp:
            continue
        match = re.search(r'name="([^"]+)"', disp)
        if not match or match.group(1) not in field_names:
            continue
        values[match.group(1)] = rest.rstrip(b'\r\n').rstrip(b'\n').decode('utf-8', errors='replace').strip()
    return values


def _send_media(handler, target, mime):
    """Serve a stored ad image. Names are unique per upload, so an immutable
    long-lived cache is safe and replaces never serve stale content."""
    try:
        raw = target.read_bytes()
    except Exception:
        handler.send_json({'success': False, 'error': 'File not found'}, 404)
        return
    handler.send_response(200)
    handler.send_header('Content-Type', mime)
    handler.send_header('Content-Length', str(len(raw)))
    handler.send_header('Cache-Control', 'public, max-age=31536000, immutable')
    handler._security_headers()
    handler.end_headers()
    handler.wfile.write(raw)


_PREVIEW_HEADERS = {
    'X-Robots-Tag': 'noindex, nofollow',
    'Cache-Control': 'no-store, no-cache, must-revalidate, private',
    'Pragma': 'no-cache',
    'Expires': '0',
}


def _render_preview(handler, ad_id):
    """Render the real homepage template with the selected advertisement forced in."""
    payload_json = service.preview_payload_json(ad_id, handler.request_base_path())
    if payload_json is None:
        handler.send_json({'success': False, 'error': 'Advertisement not found.'}, 404)
        return
    template_path = core.PROJECT_ROOT / 'templates' / 'cwa_home.html'
    try:
        html = template_path.read_text(encoding='utf-8')
    except Exception:
        handler.send_html('<html><body><h1>Preview unavailable</h1>'
                          '<p>The public homepage template could not be loaded.</p></body></html>', 500,
                          extra_headers=_PREVIEW_HEADERS)
        return
    context = dict(handler.public_route_context())
    context['AD_PAYLOAD_JSON'] = payload_json
    for key, value in context.items():
        html = html.replace(f'__{key}__', str(value or ''))
    handler.send_html(html, extra_headers=_PREVIEW_HEADERS)


# ── GET ──────────────────────────────────────────────────────────

def handle_get(handler, path, params):
    # Public, read-only ad images (generated names only; long-lived cache).
    if path.startswith(MEDIA_PREFIX):
        target, mime = media.resolve_media(path[len(MEDIA_PREFIX):])
        if not target:
            handler.send_json({'success': False, 'error': 'File not found'}, 404)
        else:
            _send_media(handler, target, mime)
        return

    user = _admin_user(handler)
    if not user:
        return

    if path == ADMIN_PAGE_PATH:
        context = {'USER_NAME': user['user'], 'USER_ROLE': user['role']}
        if not handler.render_template_with_context('admin_advertisements.html', context):
            handler.send_html('<html><body><h1>Website Advertisements</h1>'
                              '<p>Template admin_advertisements.html missing.</p></body></html>', 500)
        return

    if path == PREVIEW_PATH:
        _render_preview(handler, params.get('id'))
        return

    if path == '/api/admin/advertisements':
        _send_api_result(handler, service.list_ads(user))
        return
    if path == '/api/admin/advertisements/detail':
        _send_api_result(handler, service.ad_detail(params, user))
        return
    if path == '/api/admin/advertisements/audit':
        db = core.get_db()
        try:
            rows = list_audit(db, ad_id=int(params.get('id') or 0),
                              limit=params.get('limit') or 200)
            for row in rows:
                row['created_at_kw_display'] = core.utc_to_kuwait_display(row.get('created_at'))
            _send_api_result(handler, {'success': True, 'items': rows})
        finally:
            db.close()
        return

    handler.send_json({'success': False, 'error': 'Not found'}, 404)


# ── POST ─────────────────────────────────────────────────────────

def handle_post(handler, path, body):
    user = _admin_user(handler)
    if not user:
        return

    if path == '/api/admin/advertisements/upload-image':
        content_type = handler.headers.get('Content-Type') or ''
        extract = core.dep('extract_multipart_upload')
        original_name, raw = extract(body, content_type, field_names=('file', 'image'))
        fields = _multipart_text_fields(body, content_type, ('ad_id', 'slot'))
        _send_api_result(handler, service.attach_image(fields, original_name, raw, user))
        return

    data = _parse_json(handler, body)
    if data is None:
        return
    if path == '/api/admin/advertisements/save':
        _send_api_result(handler, service.save_ad(data, user))
    elif path == '/api/admin/advertisements/status':
        _send_api_result(handler, service.set_status(data, user))
    elif path == '/api/admin/advertisements/duplicate':
        _send_api_result(handler, service.duplicate_ad(data, user))
    else:
        handler.send_json({'success': False, 'error': 'Not found'}, 404)
