"""Website Advertisements module — append-only audit trail helpers."""
from . import core


def write_audit(db, ad_id, event_type, actor='', old_value='', new_value='', note=''):
    """Append one website_ad_audit row. Never raises — audit must not break the workflow."""
    try:
        db.execute(
            """INSERT INTO website_ad_audit (ad_id, event_type, actor, old_value, new_value, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [int(ad_id or 0), core.clean_text(event_type, 60), core.clean_text(actor, 120),
             core.clean_text(old_value, 500), core.clean_text(new_value, 500),
             core.clean_text(note, 1000)],
        )
    except Exception as exc:
        print(f'[Ads] audit write failed ({event_type}): {exc}', flush=True)


def list_audit(db, ad_id=0, limit=200):
    where, args = [], []
    if ad_id:
        where.append('ad_id = ?')
        args.append(int(ad_id))
    sql = 'SELECT * FROM website_ad_audit'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY id DESC LIMIT ?'
    args.append(max(1, min(int(limit or 200), 500)))
    return [dict(r) for r in db.execute(sql, args).fetchall()]
