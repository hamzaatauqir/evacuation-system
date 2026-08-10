"""Embassy Forms Library — HTTP dispatch layer.

server.py forwards any request whose path matches matches_path() to
handle_get()/handle_post(). The handler argument is the live
BaseHTTPRequestHandler instance, so responses reuse the portal's existing
send_json/send_html helpers (security headers included).

Public surfaces (no authentication):
  GET /api/public/forms      read-only JSON for the cross-origin React site.
                             Under /api/ so the portal's _cors_headers_if_api()
                             applies the CORS allowlist automatically.
  GET /forms/download/<id>   the PDF itself. Deliberately NOT under /api/:
                             send_file-style responses carry no CORS headers, so
                             this must be reached by top-level navigation
                             (a plain <a href>), which CORS does not govern.
                             Keeping it off /api/ stops anyone later assuming
                             it is fetchable. Same reasoning as /ads/media/*.
  GET /forms                 backend-rendered fallback page, so the Render-hosted
                             homepage has a working target and the feature is
                             testable before any frontend deploy.

Management endpoints require require_auth() plus an explicit in-handler role
check. Route-level RBAC cannot help here: admin, operator and operator_special
are all in FULL_SYSTEM_ROLES and pass can_access_admin_route() unconditionally.
"""
import json
import re

from . import core, service, storage
from .audit import EVENT_TYPES, list_audit

PUBLIC_PAGE_PATH = '/forms'
PUBLIC_API_PATH = '/api/public/forms'
DOWNLOAD_PREFIX = '/forms/download/'
ADMIN_PAGE_PATH = '/admin/forms'
ADMIN_API_PREFIX = '/api/admin/forms'

# Short TTL: a form published by staff should appear publicly within a minute,
# while still absorbing homepage traffic spikes. Matches the ads endpoint.
_PUBLIC_CACHE_HEADERS = {'Cache-Control': 'public, max-age=60'}

# The download URL is stable across file replacements, so the response must not
# be cached immutably — a replaced form would keep serving the old PDF.
_DOWNLOAD_CACHE = 'public, max-age=300'

_PREVIEW_HEADERS = {
    'X-Robots-Tag': 'noindex, nofollow',
    'Cache-Control': 'no-store, no-cache, must-revalidate, private',
    'Pragma': 'no-cache',
    'Expires': '0',
}

_DOWNLOAD_ID_RE = re.compile(r'^\d{1,12}$')


def matches_path(path):
    """Exact paths and bounded prefixes only — never a bare startswith('/forms')."""
    return (
        path == PUBLIC_PAGE_PATH
        or path == PUBLIC_API_PATH
        or path.startswith(DOWNLOAD_PREFIX)
        or path == ADMIN_PAGE_PATH
        or path == ADMIN_API_PREFIX
        or path.startswith(ADMIN_API_PREFIX + '/')
    )


def _send_api_result(handler, result):
    """Send a service result. 'status' in the dict, when present, is the HTTP code.

    The int() is guarded: a service accidentally returning a non-numeric
    'status' (a form status, say) would otherwise raise inside the response
    writer and drop the connection with no reply at all. Falling back to the
    success/failure default keeps the API answering.
    """
    status = result.pop('status', None) if isinstance(result, dict) else None
    default = 200 if result.get('success') else 400
    try:
        status = int(status) if status is not None else default
    except (TypeError, ValueError):
        print(f'[Forms] non-numeric status in service result: {status!r}', flush=True)
        status = default
    handler.send_json(result, status)


def _parse_json(handler, body):
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError:
        handler.send_json({'success': False, 'error': 'Invalid request'}, 400)
        return None


def _staff_user(handler):
    """Manage-role gate. Sends the error response itself on failure."""
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
        values[match.group(1)] = rest.rstrip(b'\r\n').rstrip(b'\n').decode(
            'utf-8', errors='replace').strip()
    return values


def _send_document(handler, raw, filename, mime, disposition='attachment',
                   cache=_DOWNLOAD_CACHE, extra=None):
    """Serve a PDF with an explicit disposition.

    'attachment' for the public route: the file is never rendered inside the
    Embassy's own origin, which removes the residual risk of a crafted PDF
    running script in-origin, and it is what citizens actually want.
    """
    handler.send_response(200)
    handler.send_header('Content-Type', mime or core.ALLOWED_MIME)
    handler.send_header('Content-Disposition', f'{disposition}; filename="{filename}"')
    handler.send_header('Content-Length', str(len(raw)))
    handler.send_header('Cache-Control', cache)
    for header, value in (extra or {}).items():
        handler.send_header(str(header), str(value))
    handler._security_headers()
    handler.end_headers()
    handler.wfile.write(raw)


def _render_public_page(handler):
    """Backend-rendered /forms.

    The payload is injected as one JSON blob and the page builds its DOM with
    textContent — staff-entered titles and descriptions are never interpolated
    into HTML tokens. render_template_with_context() escapes nothing, so this
    is the only safe way to put admin content on a server-rendered page (same
    strategy as the homepage advertisement payload).
    """
    payload = service.public_payload_api()
    context = dict(handler.public_route_context())
    context['FORMS_PAYLOAD_JSON'] = json.dumps(payload, ensure_ascii=True).replace('<', '\\u003c')
    context['FORMS_URL'] = handler.app_path(PUBLIC_PAGE_PATH)
    if handler.render_template_with_context('public_forms.html', context):
        return
    handler.send_html(
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Embassy Forms &amp; Downloads</title></head>'
        '<body style="font-family:Arial,sans-serif;padding:40px;max-width:720px;margin:0 auto">'
        '<h1>Embassy Forms &amp; Downloads</h1>'
        '<p>This page is temporarily unavailable. Please try again shortly, or contact the '
        'Community Welfare Wing at <a href="mailto:parepkuwaitcwa37@gmail.com">'
        'parepkuwaitcwa37@gmail.com</a>.</p></body></html>', 503)


# ── GET ──────────────────────────────────────────────────────────

def handle_get(handler, path, params):
    # ── Public surfaces: handled BEFORE the staff gate below. ──

    if path == PUBLIC_API_PATH:
        handler.send_json(service.public_payload_api(), 200,
                          extra_headers=_PUBLIC_CACHE_HEADERS)
        return

    if path.startswith(DOWNLOAD_PREFIX):
        raw_id = path[len(DOWNLOAD_PREFIX):].strip('/')
        if not _DOWNLOAD_ID_RE.match(raw_id):
            handler.send_json({'success': False, 'error': 'Form not found'}, 404)
            return
        raw, filename, mime, err = service.resolve_download(raw_id)
        if err:
            handler.send_json({'success': False, 'error': err}, 404)
            return
        _send_document(handler, raw, filename, mime)
        return

    if path == PUBLIC_PAGE_PATH:
        _render_public_page(handler)
        return

    # ── Staff surfaces ──
    user = _staff_user(handler)
    if not user:
        return

    if path == ADMIN_PAGE_PATH:
        context = {
            'USER_NAME': user['user'],
            'USER_ROLE': user['role'],
            'CAN_ADMIN': 'true' if core.user_is_admin(user) else 'false',
            'MAX_FILE_MB': str(core.MAX_FILE_BYTES // (1024 * 1024)),
            'PUBLIC_FORMS_URL': handler.app_path(PUBLIC_PAGE_PATH),
        }
        if not handler.render_template_with_context('admin_forms.html', context):
            handler.send_html('<html><body><h1>Forms Library</h1>'
                              '<p>Template admin_forms.html missing.</p></body></html>', 500)
        return

    if path == ADMIN_API_PREFIX:
        _send_api_result(handler, service.list_forms(user, params))
        return

    if path == ADMIN_API_PREFIX + '/detail':
        _send_api_result(handler, service.form_detail(params, user))
        return

    if path == ADMIN_API_PREFIX + '/preview':
        raw, filename, mime, err = service.resolve_preview(params.get('id'), user)
        if err:
            handler.send_json({'success': False, 'error': err},
                              403 if err == 'Access denied' else 404)
            return
        # Inline is safe here: authenticated staff, noindex, never cached.
        _send_document(handler, raw, filename, mime, disposition='inline',
                       cache=_PREVIEW_HEADERS['Cache-Control'],
                       extra={k: v for k, v in _PREVIEW_HEADERS.items()
                              if k != 'Cache-Control'})
        return

    if path == ADMIN_API_PREFIX + '/audit':
        if not core.user_is_admin(user):
            handler.send_json({'success': False,
                               'error': 'Only an administrator can view the audit trail.'}, 403)
            return
        db = core.get_db()
        try:
            rows = list_audit(db, form_id=int(params.get('id') or 0),
                              limit=params.get('limit') or 200)
            for row in rows:
                row['created_at_kw'] = core.utc_to_kuwait_display(row.get('created_at'))
            _send_api_result(handler, {'success': True, 'items': rows,
                                       'event_types': list(EVENT_TYPES)})
        finally:
            db.close()
        return

    handler.send_json({'success': False, 'error': 'Not found'}, 404)


# ── POST ─────────────────────────────────────────────────────────

def handle_post(handler, path, body):
    # Public surfaces are GET-only. Answer 405 rather than sending an
    # unauthenticated caller through the admin login redirect.
    if path in (PUBLIC_API_PATH, PUBLIC_PAGE_PATH) or path.startswith(DOWNLOAD_PREFIX):
        handler.send_json({'success': False, 'error': 'Method not allowed'}, 405)
        return

    user = _staff_user(handler)
    if not user:
        return

    if path == ADMIN_API_PREFIX + '/upload-file':
        content_type = handler.headers.get('Content-Type') or ''
        # storage.extract_upload, not the shared server.py helper — see the
        # docstring there: the shared one truncates files ending in a newline.
        original_name, raw = storage.extract_upload(body, content_type)
        fields = _multipart_text_fields(body, content_type, ('form_id',))
        _send_api_result(handler, service.attach_file(fields, original_name, raw, user))
        return

    data = _parse_json(handler, body)
    if data is None:
        return
    if path == ADMIN_API_PREFIX + '/save':
        _send_api_result(handler, service.save_form(data, user))
    elif path == ADMIN_API_PREFIX + '/status':
        _send_api_result(handler, service.set_status(data, user))
    elif path == ADMIN_API_PREFIX + '/reorder':
        _send_api_result(handler, service.reorder_forms(data, user))
    elif path == ADMIN_API_PREFIX + '/categories':
        _send_api_result(handler, service.manage_category(data, user))
    else:
        handler.send_json({'success': False, 'error': 'Not found'}, 404)
