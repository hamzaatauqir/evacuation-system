"""Hostel partner module — agreement document storage and retrieval.

Security model:
- Upload is staff-only (routes enforce), PDF/JPG/PNG only, extension AND
  magic bytes must agree, 10 MB per file.
- Stored names are generated (timestamp + random hex + whitelist-sanitized
  original name); clients only ever send row ids, so no user input reaches
  the filesystem path.
- Partner downloads require: partner session -> agreement -> partner_id match
  from the session -> visible_to_partner -> status ACTIVE. Every partner
  download and every denied attempt is audited.
"""
import re
import secrets
from datetime import datetime

from . import core
from .audit import write_audit

_MAGIC_SNIFFERS = (
    (b'%PDF', 'application/pdf'),
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
)


def _sniff_mime(raw):
    for magic, mime in _MAGIC_SNIFFERS:
        if raw[:len(magic)] == magic:
            return mime
    return ''


def validate_upload(original_name, raw):
    """Return (mime_type, error). Extension and file content must agree."""
    if not raw:
        return '', 'No file received.'
    if len(raw) > core.MAX_AGREEMENT_BYTES:
        return '', f'File too large (max {core.MAX_AGREEMENT_BYTES // (1024 * 1024)} MB).'
    name = (original_name or '').lower()
    ext = name[name.rfind('.'):] if '.' in name else ''
    expected_mime = core.ALLOWED_UPLOAD_EXTENSIONS.get(ext, '')
    if not expected_mime:
        return '', 'Only PDF, JPG, JPEG or PNG files are allowed.'
    sniffed = _sniff_mime(raw)
    if sniffed != expected_mime:
        return '', 'File content does not match its extension. Upload the original PDF or image.'
    return expected_mime, None


def store_file(original_name, raw):
    """Write bytes under a generated safe name; return the stored basename."""
    core.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', original_name or 'agreement.pdf')[:120]
    stored = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(6)}_{safe}"
    (core.UPLOAD_DIR / stored).write_bytes(raw)
    return stored


def save_agreement(data, original_name, raw, user):
    """Staff upload of a signed agreement (optionally replacing an older one)."""
    if not core.staff_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    assignment_id = int(data.get('assignment_id') or 0)
    mime, err = validate_upload(original_name, raw)
    if err:
        return {'success': False, 'error': err}
    document_type = core.clean_text(data.get('document_type'), 40) or 'ACCOMMODATION_AGREEMENT'
    if document_type not in core.AGREEMENT_DOCUMENT_TYPES:
        return {'success': False, 'error': 'Invalid document type.'}
    visible = 0 if str(data.get('visible_to_partner', '1')).strip() in ('0', 'false', 'no', 'off') else 1
    db = core.get_db()
    try:
        assignment = db.execute('SELECT * FROM hostel_assignments WHERE id = ?', [assignment_id]).fetchone()
        if not assignment:
            return {'success': False, 'error': 'Assignment not found.', 'status': 404}
        if assignment['status'] == 'CANCELLED':
            return {'success': False, 'error': 'Cannot attach documents to a cancelled assignment.'}

        replace_id = int(data.get('replace_document_id') or 0)
        old_doc = None
        if replace_id:
            old_doc = db.execute(
                "SELECT * FROM hostel_agreements WHERE id = ? AND assignment_id = ? AND status = 'ACTIVE'",
                [replace_id, assignment_id]).fetchone()
            if not old_doc:
                return {'success': False, 'error': 'Document to replace not found or not active.', 'status': 404}

        stored = store_file(original_name, raw)
        cur = db.execute(
            """INSERT INTO hostel_agreements
                   (assignment_id, nurse_registration_id, partner_id, document_type, file_name,
                    stored_name, mime_type, file_size, visible_to_partner, uploaded_by, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [assignment_id, assignment['nurse_registration_id'], assignment['partner_id'],
             document_type, core.clean_text(original_name, 200), stored, mime, len(raw),
             visible, user['user'], core.clean_text(data.get('notes'), 500)],
        )
        doc_id = cur.lastrowid
        write_audit(db, 'agreement', doc_id, 'agreement_uploaded', actor=user['user'],
                    partner_id=assignment['partner_id'],
                    nurse_registration_id=assignment['nurse_registration_id'],
                    new_value=core.clean_text(original_name, 200),
                    note=f"{document_type}, {len(raw)} bytes, assignment {assignment['assignment_ref']}")
        if old_doc:
            db.execute(
                """UPDATE hostel_agreements SET status='REPLACED', replaced_by_document_id=?,
                       updated_at=CURRENT_TIMESTAMP WHERE id=?""", [doc_id, replace_id])
            write_audit(db, 'agreement', replace_id, 'agreement_replaced', actor=user['user'],
                        partner_id=assignment['partner_id'],
                        nurse_registration_id=assignment['nurse_registration_id'],
                        old_value='ACTIVE', new_value='REPLACED', note=f'Replaced by document {doc_id}')
        db.commit()
        return {'success': True, 'document_id': doc_id, 'replaced_document_id': replace_id or None}
    finally:
        db.close()


def update_agreement(data, user):
    """Staff: cancel / archive / restore-visibility actions on a document row."""
    if not core.staff_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    doc_id = int(data.get('id') or 0)
    action = core.clean_text(data.get('action'), 30)
    db = core.get_db()
    try:
        doc = db.execute('SELECT * FROM hostel_agreements WHERE id = ?', [doc_id]).fetchone()
        if not doc:
            return {'success': False, 'error': 'Document not found.', 'status': 404}
        if action == 'cancel':
            if doc['status'] != 'ACTIVE':
                return {'success': False, 'error': f"Only ACTIVE documents can be cancelled (current: {doc['status']}).",
                        'status': 409}
            reason = core.clean_text(data.get('reason'), 500)
            if not reason:
                return {'success': False, 'error': 'A cancellation reason is required.'}
            db.execute(
                """UPDATE hostel_agreements SET status='CANCELLED', cancelled_by=?, cancelled_at=CURRENT_TIMESTAMP,
                       cancellation_reason=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                [user['user'], reason, doc_id])
            write_audit(db, 'agreement', doc_id, 'agreement_cancelled', actor=user['user'],
                        partner_id=doc['partner_id'], nurse_registration_id=doc['nurse_registration_id'],
                        old_value='ACTIVE', new_value='CANCELLED', note=reason)
        elif action == 'archive':
            if doc['status'] not in ('ACTIVE', 'CANCELLED', 'REPLACED'):
                return {'success': False, 'error': 'Document cannot be archived.', 'status': 409}
            db.execute("UPDATE hostel_agreements SET status='ARCHIVED', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       [doc_id])
            write_audit(db, 'agreement', doc_id, 'agreement_archived', actor=user['user'],
                        partner_id=doc['partner_id'], nurse_registration_id=doc['nurse_registration_id'],
                        old_value=doc['status'], new_value='ARCHIVED')
        elif action == 'set_visibility':
            visible = 1 if str(data.get('visible_to_partner', '1')).strip() in ('1', 'true', 'yes', 'on') else 0
            db.execute('UPDATE hostel_agreements SET visible_to_partner=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                       [visible, doc_id])
            write_audit(db, 'agreement', doc_id, 'agreement_visibility_changed', actor=user['user'],
                        partner_id=doc['partner_id'], nurse_registration_id=doc['nurse_registration_id'],
                        old_value=str(doc['visible_to_partner']), new_value=str(visible))
        else:
            return {'success': False, 'error': 'Unknown action.'}
        db.commit()
        return {'success': True}
    finally:
        db.close()


def resolve_staff_download(doc_id, user):
    """Return (bytes, file_name, mime, err) for a staff download."""
    if not core.staff_can_manage(user):
        return None, None, None, 'Access denied'
    db = core.get_db()
    try:
        doc = db.execute('SELECT * FROM hostel_agreements WHERE id = ?', [int(doc_id or 0)]).fetchone()
        if not doc:
            return None, None, None, 'Document not found'
        raw, err = _read_stored(doc)
        if err:
            return None, None, None, err
        write_audit(db, 'agreement', doc['id'], 'agreement_downloaded_by_staff', actor=user['user'],
                    partner_id=doc['partner_id'], nurse_registration_id=doc['nurse_registration_id'],
                    note=doc['file_name'])
        db.commit()
        return raw, doc['file_name'] or doc['stored_name'], doc['mime_type'], None
    finally:
        db.close()


def resolve_partner_download(doc_id, session, ip=''):
    """Return (bytes, file_name, mime, err) for a partner download, fully scoped."""
    db = core.get_db()
    try:
        doc = db.execute('SELECT * FROM hostel_agreements WHERE id = ?', [int(doc_id or 0)]).fetchone()
        denied_reason = None
        if not doc:
            denied_reason = 'no such document'
        elif int(doc['partner_id']) != int(session['partner_id']):
            denied_reason = 'document belongs to another partner'
        elif not int(doc['visible_to_partner'] or 0):
            denied_reason = 'document hidden from partner'
        elif doc['status'] != 'ACTIVE':
            denied_reason = f"document status {doc['status']}"
        if denied_reason:
            write_audit(db, 'agreement', int(doc_id or 0), 'partner_access_denied',
                        actor=session['username'], actor_type='PARTNER',
                        partner_id=session['partner_id'], note=f'download denied: {denied_reason}', ip=ip)
            db.commit()
            # Same message for every denial: don't leak other partners' document ids.
            return None, None, None, 'Document not found'
        raw, err = _read_stored(doc)
        if err:
            return None, None, None, err
        write_audit(db, 'agreement', doc['id'], 'agreement_downloaded_by_partner',
                    actor=session['username'], actor_type='PARTNER',
                    partner_id=doc['partner_id'], nurse_registration_id=doc['nurse_registration_id'],
                    note=doc['file_name'], ip=ip)
        db.commit()
        return raw, doc['file_name'] or doc['stored_name'], doc['mime_type'], None
    finally:
        db.close()


def _read_stored(doc):
    path = core.UPLOAD_DIR / (doc['stored_name'] or '')
    if not doc['stored_name'] or not path.is_file():
        return None, 'Stored file is missing on disk'
    try:
        return path.read_bytes(), None
    except Exception as exc:
        return None, f'Could not read stored file: {exc}'
