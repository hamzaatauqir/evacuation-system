"""Embassy Forms Library — append-only audit trail helpers.

A dedicated table rather than the global audit_log, matching every recent
module (website_ad_audit, hostel_audit, gl_audit, nh_audit): the global table
has no structured old/new value columns. server.py additionally writes one
summary row to audit_log for publish and archive only, so the Embassy-wide
trail stays meaningful without being flooded.

Public downloads are deliberately NOT audited — that would create a
high-volume table holding IP-adjacent data for no operational gain.
embassy_forms.download_count carries the same insight and retains nothing
personal.
"""
from . import core

# Every staff-initiated lifecycle event. Kept as a tuple so the admin audit
# view can render a stable filter list.
EVENT_TYPES = (
    'form_created',
    'form_updated',
    'form_published',
    'form_unpublished',
    'file_uploaded',
    'file_replaced',
    'form_archived',
    'form_restored',
    'forms_reordered',
    'category_changed',
)


def write_audit(db, form_id, event_type, actor='', old_value='', new_value='', note=''):
    """Append one embassy_form_audit row.

    Never raises — a failed audit write must not break a staff action. Mirrors
    ads/audit.py; the caller commits.
    """
    try:
        db.execute(
            """INSERT INTO embassy_form_audit
                   (form_id, event_type, actor, old_value, new_value, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [int(form_id or 0), core.clean_text(event_type, 60), core.clean_text(actor, 120),
             core.clean_text(old_value, 500), core.clean_text(new_value, 500),
             core.clean_text(note, 1000)],
        )
    except Exception as exc:
        print(f'[Forms] audit write failed ({event_type}): {exc}', flush=True)


def write_global(db, action, form_id, actor='', details=''):
    """Append one summary row to the portal-wide audit_log table.

    Called for publish and archive only. Those two are the events an Embassy-wide
    trail should show — writing every metadata edit here would flood a table
    shared by every domain. Like write_audit, this never raises.
    """
    try:
        db.execute(
            'INSERT INTO audit_log (action, record_id, user, details) VALUES (?, ?, ?, ?)',
            [core.clean_text(action, 60), int(form_id or 0),
             core.clean_text(actor, 120), core.clean_text(details, 500)],
        )
    except Exception as exc:
        print(f'[Forms] global audit write failed ({action}): {exc}', flush=True)


def list_audit(db, form_id=0, limit=200):
    where, args = [], []
    if form_id:
        where.append('form_id = ?')
        args.append(int(form_id))
    sql = 'SELECT * FROM embassy_form_audit'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY id DESC LIMIT ?'
    args.append(max(1, min(int(limit or 200), 500)))
    return [dict(r) for r in db.execute(sql, args).fetchall()]
