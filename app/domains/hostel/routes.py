"""Hostel partner module — HTTP dispatch layer.

server.py forwards any request whose path matches matches_path() to
handle_get()/handle_post(). The handler argument is the live
BaseHTTPRequestHandler instance, so all responses go through the portal's
existing send_json/send_html/send_redirect helpers (security headers included).

Staff endpoints run behind the portal's require_auth() plus the module role
sets; partner endpoints run behind the module's own hostel_session guard.
"""
import json
import re

from . import auth, core, documents, partner_api, service
from .audit import list_audit

ADMIN_PAGE_PATH = '/admin/hostel-accommodation'


def matches_path(path):
    return (
        path == ADMIN_PAGE_PATH
        or path == '/hostel'
        or path.startswith('/hostel/')
        or path.startswith('/api/hostel/')
        or path.startswith('/api/admin/hostel/')
    )


def _client_ip(handler):
    try:
        return handler.client_address[0]
    except Exception:
        return ''


def _send_api_result(handler, result):
    """Map an api dict (optionally carrying 'status'/'_set_cookie') onto send_json."""
    status = result.pop('status', None) if isinstance(result, dict) else None
    extra = None
    if isinstance(result, dict) and result.get('_set_cookie'):
        extra = {'Set-Cookie': result.pop('_set_cookie')}
    if status is None:
        status = 200 if result.get('success') else 400
    handler.send_json(result, int(status), extra_headers=extra)


def _send_document(handler, raw, file_name, mime, download):
    safe_name = re.sub(r'[\r\n"]+', '_', file_name or 'agreement.pdf')
    disposition = 'attachment' if download else 'inline'
    handler.send_response(200)
    handler.send_header('Content-Type', mime or 'application/octet-stream')
    handler.send_header('Content-Length', str(len(raw)))
    handler.send_header('Content-Disposition', f'{disposition}; filename="{safe_name}"')
    handler.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, private')
    handler.send_header('Pragma', 'no-cache')
    handler.send_header('Expires', '0')
    handler._security_headers()
    handler.end_headers()
    handler.wfile.write(raw)


def _send_csv(handler, raw, file_name):
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/csv; charset=utf-8')
    handler.send_header('Content-Length', str(len(raw)))
    handler.send_header('Content-Disposition', f'attachment; filename="{file_name}"')
    handler._security_headers()
    handler.end_headers()
    handler.wfile.write(raw)


def _parse_json(handler, body):
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError:
        handler.send_json({'success': False, 'error': 'Invalid request'}, 400)
        return None


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


def _staff_user(handler):
    """Staff gate: portal session + module role set. Sends the response on failure."""
    user = handler.require_auth()
    if not user:
        return None
    if not core.staff_can_manage(user):
        handler.send_json({'success': False, 'error': 'Access denied'}, 403)
        return None
    return user


# ── GET ──────────────────────────────────────────────────────────

def handle_get(handler, path, params):
    # Partner pages (own session mechanism, independent of staff auth)
    if path in ('/hostel', '/hostel/'):
        handler.send_redirect('/hostel/dashboard')
        return
    if path == '/hostel/login':
        if auth.get_partner_session(handler):
            handler.send_redirect('/hostel/dashboard')
            return
        if not handler.render_template_with_context('hostel_login.html', {}):
            handler.send_html(_FALLBACK_LOGIN_PAGE)
        return
    if path == '/hostel/dashboard':
        session = auth.require_partner_page(handler)
        if not session:
            return
        context = {'PARTNER_NAME': session['partner_name'], 'PARTNER_USER': session['full_name']}
        if not handler.render_template_with_context('hostel_dashboard.html', context):
            handler.send_html('<html><body><h1>Hostel Dashboard</h1><p>Template missing. '
                              'Contact the Embassy portal administrator.</p></body></html>', 500)
        return

    # Partner APIs
    if path.startswith('/api/hostel/'):
        session = auth.require_partner_api(handler)
        if not session:
            return
        if path == '/api/hostel/summary':
            _send_api_result(handler, partner_api.summary(session))
        elif path == '/api/hostel/nurses':
            _send_api_result(handler, partner_api.list_nurses(params, session))
        elif path == '/api/hostel/nurses/detail':
            _send_api_result(handler, partner_api.nurse_detail(params, session, ip=_client_ip(handler)))
        elif path == '/api/hostel/agreements/file':
            raw, name, mime, err = documents.resolve_partner_download(
                params.get('id'), session, ip=_client_ip(handler))
            if err:
                handler.send_json({'success': False, 'error': err}, 404)
            else:
                _send_document(handler, raw, name, mime, params.get('download') == '1')
        elif path == '/api/hostel/export.csv':
            raw, fname, err = service.export_partner_csv(session)
            if err:
                handler.send_json({'success': False, 'error': err}, 400)
            else:
                _send_csv(handler, raw, fname)
        else:
            handler.send_json({'success': False, 'error': 'Not found'}, 404)
        return

    # Staff page + APIs (portal auth)
    if path == ADMIN_PAGE_PATH:
        user = handler.require_auth()
        if not user:
            return
        if not core.staff_can_manage(user):
            handler.send_json({'success': False, 'error': 'Access denied'}, 403)
            return
        context = {'USER_NAME': user['user'], 'USER_ROLE': user['role']}
        if not handler.render_template_with_context('admin_hostel_accommodation.html', context):
            handler.send_html('<html><body><h1>Hostel Accommodation</h1>'
                              '<p>Template admin_hostel_accommodation.html missing.</p></body></html>', 500)
        return

    if path.startswith('/api/admin/hostel/'):
        user = _staff_user(handler)
        if not user:
            return
        if path == '/api/admin/hostel/partners':
            include_users = params.get('include_users') == '1' and core.staff_is_partner_admin(user)
            db = core.get_db()
            try:
                _send_api_result(handler, {'success': True,
                                           'partners': service.list_partners(db, include_users=include_users)})
            finally:
                db.close()
        elif path == '/api/admin/hostel/nurse-search':
            _send_api_result(handler, service.nurse_search(params, user))
        elif path == '/api/admin/hostel/assignments':
            _send_api_result(handler, service.list_assignments(params, user))
        elif path == '/api/admin/hostel/assignments/detail':
            _send_api_result(handler, service.assignment_detail(params, user))
        elif path == '/api/admin/hostel/agreements/file':
            raw, name, mime, err = documents.resolve_staff_download(params.get('id'), user)
            if err:
                handler.send_json({'success': False, 'error': err}, 404 if 'not found' in err.lower() else 403)
            else:
                _send_document(handler, raw, name, mime, params.get('download') == '1')
        elif path == '/api/admin/hostel/export.csv':
            raw, fname, err = service.export_assignments_csv(params, user)
            if err:
                handler.send_json({'success': False, 'error': err}, 403)
            else:
                _send_csv(handler, raw, fname)
        elif path == '/api/admin/hostel/audit':
            db = core.get_db()
            try:
                rows = list_audit(db,
                                  entity_type=core.clean_text(params.get('entity_type'), 40),
                                  entity_id=int(params.get('entity_id') or 0),
                                  partner_id=int(params.get('partner_id') or 0),
                                  limit=params.get('limit') or 200)
                _send_api_result(handler, {'success': True, 'items': rows})
            finally:
                db.close()
        else:
            handler.send_json({'success': False, 'error': 'Not found'}, 404)
        return

    handler.send_response(404)
    handler.end_headers()


# ── POST ─────────────────────────────────────────────────────────

def handle_post(handler, path, body):
    # Partner auth endpoints (public: login; session: logout)
    if path == '/api/hostel/login':
        data = _parse_json(handler, body)
        if data is None:
            return
        result, status = auth.login(handler, data)
        result['status'] = status
        _send_api_result(handler, result)
        return
    if path == '/api/hostel/logout':
        result, status = auth.logout(handler)
        result['status'] = status
        _send_api_result(handler, result)
        return

    # Partner APIs (hostel session)
    if path.startswith('/api/hostel/'):
        session = auth.require_partner_api(handler)
        if not session:
            return
        data = _parse_json(handler, body)
        if data is None:
            return
        ip = _client_ip(handler)
        if path == '/api/hostel/acknowledge':
            _send_api_result(handler, partner_api.acknowledge(data, session, ip=ip))
        elif path == '/api/hostel/note':
            _send_api_result(handler, partner_api.add_note(data, session, ip=ip))
        elif path == '/api/hostel/mark-arrival':
            _send_api_result(handler, partner_api.mark_arrival(data, session, ip=ip))
        else:
            handler.send_json({'success': False, 'error': 'Not found'}, 404)
        return

    # Staff APIs (portal auth)
    if path.startswith('/api/admin/hostel/'):
        user = _staff_user(handler)
        if not user:
            return

        if path == '/api/admin/hostel/agreements/upload':
            content_type = handler.headers.get('Content-Type') or ''
            extract = core.dep('extract_multipart_upload')
            original_name, raw = extract(body, content_type,
                                         field_names=('file', 'agreement', 'document', 'pdf'))
            fields = _multipart_text_fields(body, content_type,
                                            ('assignment_id', 'document_type', 'visible_to_partner',
                                             'replace_document_id', 'notes'))
            result = documents.save_agreement(fields, original_name, raw, user)
            _send_api_result(handler, result)
            return

        data = _parse_json(handler, body)
        if data is None:
            return
        if path == '/api/admin/hostel/partners/save':
            _send_api_result(handler, service.save_partner(data, user))
        elif path == '/api/admin/hostel/partner-users/save':
            _send_api_result(handler, service.save_partner_user(data, user))
        elif path == '/api/admin/hostel/assignments/create':
            _send_api_result(handler, service.create_assignments(data, user))
        elif path == '/api/admin/hostel/assignments/update':
            _send_api_result(handler, service.update_assignment(data, user))
        elif path == '/api/admin/hostel/agreements/update':
            _send_api_result(handler, documents.update_agreement(data, user))
        else:
            handler.send_json({'success': False, 'error': 'Not found'}, 404)
        return

    handler.send_response(404)
    handler.end_headers()


_FALLBACK_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hostel Partner Login</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#f2f5f8;display:flex;justify-content:center;padding-top:80px">
<form onsubmit="return doLogin(event)" style="background:#fff;border:1px solid #dde5ec;border-radius:10px;padding:28px;width:340px">
<h2 style="margin:0 0 4px;color:#15324a">Hostel Partner Login</h2>
<p style="color:#68798a;font-size:13px;margin:0 0 16px">Embassy of Pakistan Kuwait — Accommodation Partners</p>
<label style="font-size:12px;font-weight:700;color:#4f6374">Username</label>
<input id="u" style="width:100%;box-sizing:border-box;padding:10px;margin:5px 0 12px;border:1px solid #cfdde7;border-radius:6px">
<label style="font-size:12px;font-weight:700;color:#4f6374">Password</label>
<input id="p" type="password" style="width:100%;box-sizing:border-box;padding:10px;margin:5px 0 16px;border:1px solid #cfdde7;border-radius:6px">
<button style="width:100%;padding:11px;background:#15324a;color:#fff;border:0;border-radius:6px;font-weight:700;cursor:pointer">Sign In</button>
<div id="err" style="color:#9d1d1d;font-size:13px;margin-top:10px"></div>
</form>
<script>
async function doLogin(e){e.preventDefault();
const r=await fetch('/api/hostel/login',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({username:document.getElementById('u').value,password:document.getElementById('p').value})});
const j=await r.json();
if(j.success){location.href=j.redirect_url||'/hostel/dashboard'}else{document.getElementById('err').textContent=j.error||'Login failed'}
return false}
</script></body></html>"""
