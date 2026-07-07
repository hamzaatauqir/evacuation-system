"""Hostel partner module — business logic (no HTTP objects in here).

All functions take plain dicts and return plain dicts; the routes layer maps
them onto JSON responses. Staff identity arrives as the session dict from
require_auth(); partner identity as the hostel session dict.
"""
import csv
import io

from . import core
from .audit import write_audit

# ── Partners & partner users ─────────────────────────────────────

def list_partners(db, include_users=False):
    partners = [dict(r) for r in db.execute(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM hostel_assignments a
                    WHERE a.partner_id = p.id AND a.status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT')) AS open_assignments,
                  (SELECT COUNT(*) FROM hostel_partner_users u WHERE u.partner_id = p.id) AS user_count
           FROM hostel_partners p ORDER BY p.id"""
    ).fetchall()]
    if include_users:
        for p in partners:
            p['users'] = [dict(r) for r in db.execute(
                """SELECT id, username, full_name, email, status, last_login_at, created_at
                   FROM hostel_partner_users WHERE partner_id = ? ORDER BY id""", [p['id']]
            ).fetchall()]
    return partners


def save_partner(data, user):
    if not core.staff_is_partner_admin(user):
        return {'success': False, 'error': 'Only admin can manage hostel partners.', 'status': 403}
    db = core.get_db()
    try:
        partner_id = int(data.get('id') or 0)
        fields = {
            'partner_name': core.clean_text(data.get('partner_name'), 200),
            'display_name': core.clean_text(data.get('display_name'), 200),
            'contact_person': core.clean_text(data.get('contact_person'), 200),
            'email': core.clean_text(data.get('email'), 200),
            'phone': core.clean_text(data.get('phone'), 60),
            'address': core.clean_text(data.get('address'), 500),
            'notes': core.clean_text(data.get('notes'), 1000),
        }
        status = core.clean_text(data.get('status'), 20) or 'ACTIVE'
        if status not in core.PARTNER_STATUSES:
            return {'success': False, 'error': 'Invalid partner status.'}
        can_mark_arrival = 1 if str(data.get('can_mark_arrival', '1')).strip() in ('1', 'true', 'True', 'on') else 0
        if partner_id:
            row = db.execute('SELECT * FROM hostel_partners WHERE id = ?', [partner_id]).fetchone()
            if not row:
                return {'success': False, 'error': 'Partner not found.', 'status': 404}
            db.execute(
                """UPDATE hostel_partners SET partner_name=?, display_name=?, contact_person=?, email=?,
                       phone=?, address=?, notes=?, status=?, can_mark_arrival=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                [fields['partner_name'] or row['partner_name'], fields['display_name'], fields['contact_person'],
                 fields['email'], fields['phone'], fields['address'], fields['notes'], status,
                 can_mark_arrival, partner_id],
            )
            write_audit(db, 'partner', partner_id, 'partner_updated', actor=user['user'],
                        partner_id=partner_id, old_value=row['status'], new_value=status)
        else:
            if not fields['partner_name']:
                return {'success': False, 'error': 'Partner name is required.'}
            code = core.clean_text(data.get('partner_code'), 60).upper().replace(' ', '_') \
                or fields['partner_name'].upper().replace(' ', '_')[:60]
            existing = db.execute('SELECT id FROM hostel_partners WHERE partner_code = ?', [code]).fetchone()
            if existing:
                return {'success': False, 'error': f'Partner code {code} already exists.'}
            cur = db.execute(
                """INSERT INTO hostel_partners (partner_code, partner_name, display_name, contact_person,
                       email, phone, address, notes, status, can_mark_arrival, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [code, fields['partner_name'], fields['display_name'], fields['contact_person'],
                 fields['email'], fields['phone'], fields['address'], fields['notes'], status,
                 can_mark_arrival, user['user']],
            )
            partner_id = cur.lastrowid
            write_audit(db, 'partner', partner_id, 'partner_created', actor=user['user'], partner_id=partner_id,
                        new_value=fields['partner_name'])
        db.commit()
        return {'success': True, 'partner_id': partner_id}
    finally:
        db.close()


def save_partner_user(data, user):
    """Create a partner login, reset its password, or enable/disable it (admin only)."""
    if not core.staff_is_partner_admin(user):
        return {'success': False, 'error': 'Only admin can manage hostel partner logins.', 'status': 403}
    db = core.get_db()
    try:
        action = core.clean_text(data.get('action'), 30) or 'create'
        hash_password = core.dep('hash_password')
        if action == 'create':
            partner_id = int(data.get('partner_id') or 0)
            username = core.clean_text(data.get('username'), 120).lower()
            password = str(data.get('password') or '')
            if not partner_id or not username or not password:
                return {'success': False, 'error': 'Partner, username and password are required.'}
            if len(password) < 8:
                return {'success': False, 'error': 'Password must be at least 8 characters.'}
            partner = db.execute('SELECT id FROM hostel_partners WHERE id = ?', [partner_id]).fetchone()
            if not partner:
                return {'success': False, 'error': 'Partner not found.', 'status': 404}
            if db.execute('SELECT id FROM hostel_partner_users WHERE LOWER(username)=?', [username]).fetchone():
                return {'success': False, 'error': 'Username already exists.'}
            pw_hash, salt = hash_password(password)
            cur = db.execute(
                """INSERT INTO hostel_partner_users
                       (partner_id, username, full_name, email, password_hash, password_salt, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [partner_id, username, core.clean_text(data.get('full_name'), 200),
                 core.clean_text(data.get('email'), 200), pw_hash, salt, user['user']],
            )
            write_audit(db, 'partner_user', cur.lastrowid, 'partner_user_created', actor=user['user'],
                        partner_id=partner_id, new_value=username)
            db.commit()
            return {'success': True, 'partner_user_id': cur.lastrowid}

        user_id = int(data.get('partner_user_id') or 0)
        row = db.execute('SELECT * FROM hostel_partner_users WHERE id = ?', [user_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Partner user not found.', 'status': 404}
        if action == 'reset_password':
            password = str(data.get('password') or '')
            if len(password) < 8:
                return {'success': False, 'error': 'Password must be at least 8 characters.'}
            pw_hash, salt = hash_password(password)
            db.execute('UPDATE hostel_partner_users SET password_hash=?, password_salt=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                       [pw_hash, salt, user_id])
            write_audit(db, 'partner_user', user_id, 'partner_user_password_reset', actor=user['user'],
                        partner_id=row['partner_id'], note=row['username'])
        elif action == 'set_status':
            status = core.clean_text(data.get('status'), 20)
            if status not in core.PARTNER_USER_STATUSES:
                return {'success': False, 'error': 'Invalid status.'}
            db.execute('UPDATE hostel_partner_users SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                       [status, user_id])
            write_audit(db, 'partner_user', user_id, 'partner_user_status_changed', actor=user['user'],
                        partner_id=row['partner_id'], old_value=row['status'], new_value=status,
                        note=row['username'])
        else:
            return {'success': False, 'error': 'Unknown action.'}
        db.commit()
        return {'success': True}
    finally:
        db.close()


# ── Nurse search (pulls from existing portal data; nothing re-entered) ──

def nurse_search(params, user):
    if not core.staff_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    q = core.clean_text(params.get('q'), 120)
    if len(q) < 2:
        return {'success': True, 'results': [], 'note': 'Enter at least 2 characters.'}
    like = f'%{q.upper()}%'
    db = core.get_db()
    try:
        rows = db.execute(
            """SELECT n.id, n.reference_id, n.full_name, n.passport_number, n.civil_id, n.cnic,
                      COALESCE(NULLIF(n.mobile_full,''), n.mobile) AS mobile, n.email,
                      n.hospital_workplace, n.registration_status, n.arrival_date
               FROM nurse_registrations n
               WHERE UPPER(IFNULL(n.reference_id,'')) LIKE ?
                  OR UPPER(IFNULL(n.full_name,'')) LIKE ?
                  OR UPPER(IFNULL(n.passport_number,'')) LIKE ?
                  OR UPPER(IFNULL(n.civil_id,'')) LIKE ?
                  OR UPPER(IFNULL(n.cnic,'')) LIKE ?
                  OR UPPER(IFNULL(n.mobile,'')) LIKE ?
                  OR UPPER(IFNULL(n.email,'')) LIKE ?
                  OR n.id IN (SELECT g.nurse_id FROM gl_applications g WHERE UPPER(IFNULL(g.ref_no,'')) LIKE ?)
               ORDER BY n.id DESC LIMIT 30""",
            [like] * 8,
        ).fetchall()
        results = []
        for r in rows:
            item = dict(r)
            gl = db.execute(
                """SELECT ref_no, status FROM gl_applications
                   WHERE nurse_id = ? ORDER BY id DESC LIMIT 1""", [r['id']]
            ).fetchone()
            item['gl_ref'] = gl['ref_no'] if gl else ''
            item['gl_status'] = gl['status'] if gl else ''
            assignment = db.execute(
                """SELECT a.id, a.assignment_ref, a.status, a.partner_id, p.display_name, p.partner_name
                   FROM hostel_assignments a JOIN hostel_partners p ON p.id = a.partner_id
                   WHERE a.nurse_registration_id = ? AND a.status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT')
                   ORDER BY a.id DESC LIMIT 1""", [r['id']]
            ).fetchone()
            item['current_assignment'] = dict(assignment) if assignment else None
            results.append(item)
        return {'success': True, 'results': results}
    finally:
        db.close()


# ── Assignments ──────────────────────────────────────────────────

def create_assignments(data, user):
    """Assign one or many nurses (by nurse_registrations.id) to a partner."""
    if not core.staff_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    nurse_ids = data.get('nurse_ids') or ([data.get('nurse_id')] if data.get('nurse_id') else [])
    try:
        nurse_ids = [int(n) for n in nurse_ids if int(n or 0) > 0]
    except (TypeError, ValueError):
        return {'success': False, 'error': 'Invalid nurse ids.'}
    if not nurse_ids:
        return {'success': False, 'error': 'Select at least one nurse.'}
    partner_id = int(data.get('partner_id') or 0)
    db = core.get_db()
    try:
        partner = db.execute("SELECT * FROM hostel_partners WHERE id = ? AND status = 'ACTIVE'",
                             [partner_id]).fetchone()
        if not partner:
            return {'success': False, 'error': 'Hostel partner not found or not active.', 'status': 404}
        created, skipped = [], []
        for nurse_id in nurse_ids:
            nurse = db.execute(
                'SELECT id, reference_id, full_name, passport_number FROM nurse_registrations WHERE id = ?',
                [nurse_id],
            ).fetchone()
            if not nurse:
                skipped.append({'nurse_id': nurse_id, 'reason': 'Nurse not found'})
                continue
            open_existing = db.execute(
                """SELECT assignment_ref FROM hostel_assignments
                   WHERE nurse_registration_id = ? AND partner_id = ?
                     AND status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT')""",
                [nurse_id, partner_id],
            ).fetchone()
            if open_existing:
                skipped.append({'nurse_id': nurse_id, 'nurse_name': nurse['full_name'],
                                'reason': f"Already assigned ({open_existing['assignment_ref']})"})
                continue
            gl = db.execute('SELECT id FROM gl_applications WHERE nurse_id = ? ORDER BY id DESC LIMIT 1',
                            [nurse_id]).fetchone()
            ref = core.next_assignment_ref(db)
            cur = db.execute(
                """INSERT INTO hostel_assignments
                       (assignment_ref, nurse_registration_id, gl_application_id, partner_id,
                        nurse_name, passport_number, nurse_reference, hostel_name, room_number, bed_number,
                        assigned_date, expected_arrival_date, notes, note_for_partner, assigned_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [ref, nurse_id, gl['id'] if gl else None, partner_id,
                 nurse['full_name'] or '', nurse['passport_number'] or '', nurse['reference_id'] or '',
                 core.clean_text(data.get('hostel_name'), 200) or (partner['display_name'] or partner['partner_name']),
                 core.clean_text(data.get('room_number'), 40), core.clean_text(data.get('bed_number'), 40),
                 core.now_str()[:10], core.clean_date(data.get('expected_arrival_date')),
                 core.clean_text(data.get('notes'), 1000), core.clean_text(data.get('note_for_partner'), 1000),
                 user['user']],
            )
            write_audit(db, 'assignment', cur.lastrowid, 'assignment_created', actor=user['user'],
                        partner_id=partner_id, nurse_registration_id=nurse_id,
                        new_value=f"{nurse['full_name']} -> {partner['partner_name']}", note=ref)
            created.append({'nurse_id': nurse_id, 'nurse_name': nurse['full_name'], 'assignment_ref': ref})
        db.commit()
        return {'success': True, 'created': created, 'skipped': skipped}
    finally:
        db.close()


def list_assignments(params, user):
    if not core.staff_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    db = core.get_db()
    try:
        where, args = [], []
        partner_id = int(params.get('partner_id') or 0)
        if partner_id:
            where.append('a.partner_id = ?')
            args.append(partner_id)
        status = core.clean_text(params.get('status'), 20)
        if status == 'OPEN':
            where.append("a.status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT')")
        elif status in core.ASSIGNMENT_STATUSES:
            where.append('a.status = ?')
            args.append(status)
        q = core.clean_text(params.get('q'), 120)
        if q:
            like = f'%{q.upper()}%'
            where.append("""(UPPER(a.nurse_name) LIKE ? OR UPPER(a.passport_number) LIKE ?
                             OR UPPER(a.nurse_reference) LIKE ? OR UPPER(a.assignment_ref) LIKE ?)""")
            args.extend([like] * 4)
        page = max(1, int(params.get('page') or 1))
        page_size = min(100, max(10, int(params.get('page_size') or 50)))
        where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
        total = db.execute(f'SELECT COUNT(*) AS c FROM hostel_assignments a{where_sql}', args).fetchone()['c']
        rows = db.execute(
            f"""SELECT a.*, p.partner_name, p.display_name,
                       (SELECT COUNT(*) FROM hostel_agreements g
                         WHERE g.assignment_id = a.id AND g.status = 'ACTIVE') AS active_agreements
                FROM hostel_assignments a JOIN hostel_partners p ON p.id = a.partner_id
                {where_sql} ORDER BY a.id DESC LIMIT ? OFFSET ?""",
            args + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {'success': True, 'items': [dict(r) for r in rows], 'total': total,
                'page': page, 'page_size': page_size}
    finally:
        db.close()


def assignment_detail(params, user):
    if not core.staff_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    assignment_id = int(params.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute(
            """SELECT a.*, p.partner_name, p.display_name
               FROM hostel_assignments a JOIN hostel_partners p ON p.id = a.partner_id
               WHERE a.id = ?""", [assignment_id],
        ).fetchone()
        if not row:
            return {'success': False, 'error': 'Assignment not found.', 'status': 404}
        agreements = [dict(r) for r in db.execute(
            'SELECT * FROM hostel_agreements WHERE assignment_id = ? ORDER BY id DESC', [assignment_id]
        ).fetchall()]
        audit_rows = [dict(r) for r in db.execute(
            """SELECT * FROM hostel_audit
               WHERE (entity_type = 'assignment' AND entity_id = ?)
                  OR (entity_type = 'agreement' AND entity_id IN
                        (SELECT id FROM hostel_agreements WHERE assignment_id = ?))
               ORDER BY id DESC LIMIT 100""", [assignment_id, assignment_id],
        ).fetchall()]
        return {'success': True, 'assignment': dict(row), 'agreements': agreements, 'audit': audit_rows}
    finally:
        db.close()


def update_assignment(data, user):
    if not core.staff_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    assignment_id = int(data.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM hostel_assignments WHERE id = ?', [assignment_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Assignment not found.', 'status': 404}
        changes = []

        for field, max_len in (('room_number', 40), ('bed_number', 40), ('hostel_name', 200),
                               ('notes', 1000), ('note_for_partner', 1000)):
            if field in data:
                new_val = core.clean_text(data.get(field), max_len)
                if new_val != (row[field] or ''):
                    db.execute(f'UPDATE hostel_assignments SET {field}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                               [new_val, assignment_id])
                    changes.append((field, row[field] or '', new_val))
        for field in ('expected_arrival_date', 'actual_arrival_date'):
            if field in data:
                new_val = core.clean_date(data.get(field))
                if new_val != (row[field] or ''):
                    db.execute(f'UPDATE hostel_assignments SET {field}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                               [new_val, assignment_id])
                    changes.append((field, row[field] or '', new_val))

        new_status = core.clean_text(data.get('status'), 20)
        if new_status and new_status != row['status']:
            allowed = core.ASSIGNMENT_TRANSITIONS.get(row['status'], set())
            if new_status not in allowed:
                return {'success': False, 'status': 409,
                        'error': f"Cannot move assignment from {row['status']} to {new_status}."}
            reason = core.clean_text(data.get('cancellation_reason') or data.get('reason'), 500)
            if new_status == 'CANCELLED':
                if not reason:
                    return {'success': False, 'error': 'A cancellation reason is required.'}
                db.execute(
                    """UPDATE hostel_assignments SET status=?, cancelled_by=?, cancelled_at=CURRENT_TIMESTAMP,
                           cancellation_reason=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    [new_status, user['user'], reason, assignment_id])
            else:
                db.execute('UPDATE hostel_assignments SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                           [new_status, assignment_id])
                if new_status == 'ARRIVED' and not (row['actual_arrival_date'] or '') and 'actual_arrival_date' not in data:
                    db.execute('UPDATE hostel_assignments SET actual_arrival_date=? WHERE id=?',
                               [core.now_str()[:10], assignment_id])
            event = 'assignment_cancelled' if new_status == 'CANCELLED' else 'assignment_status_changed'
            write_audit(db, 'assignment', assignment_id, event, actor=user['user'],
                        partner_id=row['partner_id'], nurse_registration_id=row['nurse_registration_id'],
                        old_value=row['status'], new_value=new_status, note=reason)
            changes.append(('status', row['status'], new_status))

        if changes:
            field_changes = [c for c in changes if c[0] != 'status']
            if field_changes:
                write_audit(db, 'assignment', assignment_id, 'assignment_updated', actor=user['user'],
                            partner_id=row['partner_id'], nurse_registration_id=row['nurse_registration_id'],
                            note='; '.join(f'{f}: "{o}" -> "{n}"' for f, o, n in field_changes)[:900])
            db.commit()
        return {'success': True, 'changed': [c[0] for c in changes]}
    finally:
        db.close()


# ── CSV exports ──────────────────────────────────────────────────

def export_assignments_csv(params, user):
    """Staff export. Returns (bytes, filename, err)."""
    if not core.staff_can_manage(user):
        return None, None, 'Access denied'
    db = core.get_db()
    try:
        where, args = ["a.status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT')"], []
        partner_id = int(params.get('partner_id') or 0)
        if partner_id:
            where.append('a.partner_id = ?')
            args.append(partner_id)
        status = core.clean_text(params.get('status'), 20)
        if status in core.ASSIGNMENT_STATUSES:
            where = ['a.status = ?'] + (['a.partner_id = ?'] if partner_id else [])
            args = [status] + ([partner_id] if partner_id else [])
        rows = db.execute(
            f"""SELECT a.assignment_ref, a.nurse_name, a.passport_number, a.nurse_reference,
                       p.partner_name, a.hostel_name, a.room_number, a.bed_number, a.status,
                       a.assigned_date, a.expected_arrival_date, a.actual_arrival_date,
                       (SELECT COUNT(*) FROM hostel_agreements g
                         WHERE g.assignment_id = a.id AND g.status = 'ACTIVE') AS active_agreements,
                       a.acknowledged_at, a.assigned_by
                FROM hostel_assignments a JOIN hostel_partners p ON p.id = a.partner_id
                WHERE {' AND '.join(where)} ORDER BY a.id DESC""",
            args,
        ).fetchall()
        return _rows_to_csv(rows), f'hostel_assignments_{core.now_str()[:10]}.csv', None
    finally:
        db.close()


def export_partner_csv(session):
    """Partner-scoped export. Returns (bytes, filename, err)."""
    db = core.get_db()
    try:
        rows = db.execute(
            """SELECT assignment_ref, nurse_name, passport_number, status,
                      room_number, bed_number, assigned_date, expected_arrival_date,
                      actual_arrival_date, acknowledged_at
               FROM hostel_assignments
               WHERE partner_id = ? AND status IN ('ASSIGNED','ARRIVED','ACTIVE_TENANT')
               ORDER BY id DESC""",
            [session['partner_id']],
        ).fetchall()
        write_audit(db, 'partner', session['partner_id'], 'partner_export_downloaded',
                    actor=session['username'], actor_type='PARTNER', partner_id=session['partner_id'],
                    note=f'{len(rows)} rows')
        db.commit()
        return _rows_to_csv(rows), f'aja_assigned_nurses_{core.now_str()[:10]}.csv', None
    finally:
        db.close()


def _rows_to_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    if rows:
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow([r[k] for k in r.keys()])
    else:
        writer.writerow(['no_records'])
    return buf.getvalue().encode('utf-8-sig')
