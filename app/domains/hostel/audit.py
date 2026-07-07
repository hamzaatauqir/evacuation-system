"""Hostel partner module — append-only audit trail helpers."""
from . import core


def write_audit(db, entity_type, entity_id, event_type, actor='', actor_type='STAFF',
                partner_id=0, nurse_registration_id=0, old_value='', new_value='',
                note='', ip=''):
    """Append one hostel_audit row. Never raises — audit must not break the workflow."""
    try:
        db.execute(
            """INSERT INTO hostel_audit
               (entity_type, entity_id, partner_id, nurse_registration_id,
                actor_type, actor, event_type, old_value, new_value, note, ip)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                core.clean_text(entity_type, 40), int(entity_id or 0), int(partner_id or 0),
                int(nurse_registration_id or 0), core.clean_text(actor_type, 20),
                core.clean_text(actor, 120), core.clean_text(event_type, 60),
                core.clean_text(old_value, 500), core.clean_text(new_value, 500),
                core.clean_text(note, 1000), core.clean_text(ip, 64),
            ],
        )
    except Exception as exc:
        print(f'[Hostel] audit write failed ({event_type}): {exc}', flush=True)


def list_audit(db, entity_type='', entity_id=0, partner_id=0, limit=200):
    where, args = [], []
    if entity_type:
        where.append('entity_type = ?')
        args.append(entity_type)
    if entity_id:
        where.append('entity_id = ?')
        args.append(int(entity_id))
    if partner_id:
        where.append('partner_id = ?')
        args.append(int(partner_id))
    sql = 'SELECT * FROM hostel_audit'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY id DESC LIMIT ?'
    args.append(max(1, min(int(limit or 200), 500)))
    return [dict(r) for r in db.execute(sql, args).fetchall()]
