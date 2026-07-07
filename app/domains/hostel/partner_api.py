"""Hostel partner module — partner-facing API logic.

Every function takes the partner session dict; partner_id ALWAYS comes from
the session, never from the request payload.
"""
from . import core
from .audit import write_audit


def summary(session):
    db = core.get_db()
    try:
        pid = session['partner_id']
        today = core.now_str()[:10]
        counts = {}
        for key, sql, args in (
            ('active_tenants', "SELECT COUNT(*) c FROM hostel_assignments WHERE partner_id=? AND status='ACTIVE_TENANT'", [pid]),
            ('assigned', "SELECT COUNT(*) c FROM hostel_assignments WHERE partner_id=? AND status='ASSIGNED'", [pid]),
            ('arrived', "SELECT COUNT(*) c FROM hostel_assignments WHERE partner_id=? AND status='ARRIVED'", [pid]),
            ('pending_acknowledgement', "SELECT COUNT(*) c FROM hostel_assignments WHERE partner_id=? AND status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT') AND acknowledged_at IS NULL", [pid]),
            ('expected_today', "SELECT COUNT(*) c FROM hostel_assignments WHERE partner_id=? AND status='ASSIGNED' AND expected_arrival_date=?", [pid, today]),
            ('visible_agreements', "SELECT COUNT(*) c FROM hostel_agreements WHERE partner_id=? AND status='ACTIVE' AND visible_to_partner=1", [pid]),
        ):
            counts[key] = db.execute(sql, args).fetchone()['c']
        expected = [dict(r) for r in db.execute(
            """SELECT id, assignment_ref, nurse_name, passport_number, expected_arrival_date, room_number, bed_number
               FROM hostel_assignments
               WHERE partner_id=? AND status='ASSIGNED' AND expected_arrival_date != ''
                 AND expected_arrival_date >= ?
               ORDER BY expected_arrival_date LIMIT 15""", [pid, today]).fetchall()]
        recent_updates = [dict(r) for r in db.execute(
            """SELECT event_type, entity_type, entity_id, new_value, note, created_at
               FROM hostel_audit
               WHERE partner_id=? AND actor_type='STAFF'
                 AND event_type IN ('assignment_created','assignment_status_changed','assignment_updated',
                                    'agreement_uploaded','agreement_cancelled','agreement_replaced')
               ORDER BY id DESC LIMIT 15""", [pid]).fetchall()]
        return {'success': True, 'partner_name': session['partner_name'], 'counts': counts,
                'expected_arrivals': expected, 'recent_updates': recent_updates,
                'can_mark_arrival': bool(session.get('can_mark_arrival'))}
    finally:
        db.close()


def list_nurses(params, session):
    db = core.get_db()
    try:
        where = ['a.partner_id = ?']
        args = [session['partner_id']]
        status = core.clean_text(params.get('status'), 20)
        if status in core.ASSIGNMENT_STATUSES:
            where.append('a.status = ?')
            args.append(status)
        else:
            where.append("a.status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT')")
        q = core.clean_text(params.get('q'), 120)
        if q:
            like = f'%{q.upper()}%'
            where.append('(UPPER(a.nurse_name) LIKE ? OR UPPER(a.passport_number) LIKE ? OR UPPER(a.assignment_ref) LIKE ?)')
            args.extend([like] * 3)
        rows = db.execute(
            f"""SELECT a.id, a.assignment_ref, a.nurse_name, a.passport_number, a.status,
                       a.room_number, a.bed_number, a.assigned_date, a.expected_arrival_date,
                       a.actual_arrival_date, a.acknowledged_at, a.note_for_partner, a.partner_note,
                       (SELECT COUNT(*) FROM hostel_agreements g
                         WHERE g.assignment_id = a.id AND g.status='ACTIVE' AND g.visible_to_partner=1) AS agreements
                FROM hostel_assignments a
                WHERE {' AND '.join(where)}
                ORDER BY a.id DESC LIMIT 500""", args).fetchall()
        return {'success': True, 'items': [dict(r) for r in rows]}
    finally:
        db.close()


def nurse_detail(params, session, ip=''):
    assignment_id = int(params.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute(
            'SELECT * FROM hostel_assignments WHERE id = ? AND partner_id = ?',
            [assignment_id, session['partner_id']]).fetchone()
        if not row:
            write_audit(db, 'assignment', assignment_id, 'partner_access_denied',
                        actor=session['username'], actor_type='PARTNER',
                        partner_id=session['partner_id'], note='detail denied: not this partner', ip=ip)
            db.commit()
            return {'success': False, 'error': 'Record not found.', 'status': 404}
        assignment = dict(row)
        # Partner-safe projection: internal staff notes are not included.
        assignment.pop('notes', None)
        agreements = [dict(r) for r in db.execute(
            """SELECT id, document_type, file_name, mime_type, file_size, uploaded_at, status
               FROM hostel_agreements
               WHERE assignment_id = ? AND status = 'ACTIVE' AND visible_to_partner = 1
               ORDER BY id DESC""", [assignment_id]).fetchall()]
        write_audit(db, 'assignment', assignment_id, 'agreement_viewed_by_partner',
                    actor=session['username'], actor_type='PARTNER',
                    partner_id=session['partner_id'],
                    nurse_registration_id=row['nurse_registration_id'],
                    note=f'detail viewed ({len(agreements)} visible agreements)', ip=ip)
        db.commit()
        return {'success': True, 'assignment': assignment, 'agreements': agreements}
    finally:
        db.close()


def acknowledge(data, session, ip=''):
    assignment_id = int(data.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute(
            'SELECT * FROM hostel_assignments WHERE id = ? AND partner_id = ?',
            [assignment_id, session['partner_id']]).fetchone()
        if not row:
            return {'success': False, 'error': 'Record not found.', 'status': 404}
        if row['acknowledged_at']:
            return {'success': True, 'note': 'Already acknowledged.'}
        db.execute(
            """UPDATE hostel_assignments SET acknowledged_at=CURRENT_TIMESTAMP, acknowledged_by=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            [session['username'], assignment_id])
        write_audit(db, 'assignment', assignment_id, 'assignment_acknowledged',
                    actor=session['username'], actor_type='PARTNER',
                    partner_id=session['partner_id'],
                    nurse_registration_id=row['nurse_registration_id'], ip=ip)
        db.commit()
        return {'success': True}
    finally:
        db.close()


def add_note(data, session, ip=''):
    assignment_id = int(data.get('id') or 0)
    note = core.clean_text(data.get('note'), 1000)
    if not note:
        return {'success': False, 'error': 'Note text is required.'}
    db = core.get_db()
    try:
        row = db.execute(
            'SELECT * FROM hostel_assignments WHERE id = ? AND partner_id = ?',
            [assignment_id, session['partner_id']]).fetchone()
        if not row:
            return {'success': False, 'error': 'Record not found.', 'status': 404}
        stamped = f"[{core.now_str()} {session['username']}] {note}"
        combined = (row['partner_note'] + '\n' if row['partner_note'] else '') + stamped
        db.execute('UPDATE hostel_assignments SET partner_note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   [combined[-4000:], assignment_id])
        write_audit(db, 'assignment', assignment_id, 'partner_note_added',
                    actor=session['username'], actor_type='PARTNER',
                    partner_id=session['partner_id'],
                    nurse_registration_id=row['nurse_registration_id'], new_value=note[:400], ip=ip)
        db.commit()
        return {'success': True}
    finally:
        db.close()


def mark_arrival(data, session, ip=''):
    if not session.get('can_mark_arrival'):
        return {'success': False, 'error': 'Arrival confirmation is not enabled for your account.', 'status': 403}
    assignment_id = int(data.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute(
            'SELECT * FROM hostel_assignments WHERE id = ? AND partner_id = ?',
            [assignment_id, session['partner_id']]).fetchone()
        if not row:
            return {'success': False, 'error': 'Record not found.', 'status': 404}
        if row['status'] != 'ASSIGNED':
            return {'success': False, 'error': f"Arrival can only be confirmed for ASSIGNED records (current: {row['status']}).",
                    'status': 409}
        arrival_date = core.clean_date(data.get('actual_arrival_date')) or core.now_str()[:10]
        db.execute(
            """UPDATE hostel_assignments SET status='ARRIVED', actual_arrival_date=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            [arrival_date, assignment_id])
        write_audit(db, 'assignment', assignment_id, 'arrival_marked_by_partner',
                    actor=session['username'], actor_type='PARTNER',
                    partner_id=session['partner_id'],
                    nurse_registration_id=row['nurse_registration_id'],
                    old_value='ASSIGNED', new_value='ARRIVED', note=f'arrival date {arrival_date}', ip=ip)
        db.commit()
        return {'success': True, 'actual_arrival_date': arrival_date}
    finally:
        db.close()
