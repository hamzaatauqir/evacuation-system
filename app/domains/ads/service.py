"""Website Advertisements module — lifecycle, validation, and public payload.

Statuses stored: DRAFT / ACTIVE / PAUSED / ARCHIVED (admin intent).
SCHEDULED / EXPIRED are derived from starts_at / ends_at at read time, so
expiry needs no background job and can never be missed by a stale cache.

content_version (owner decision #4) increments only when public-facing
content changes; browsers key their dismissal storage on it, so publishing a
new version re-shows the popup to users who dismissed an older one.
"""
import json

from . import core
from .audit import write_audit

# Fields whose change means the public sees something different, and which
# therefore bump content_version. Internal metadata (internal_name,
# campaign_reference) is deliberately excluded.
PUBLIC_FIELDS = (
    'language', 'disclosure_label', 'popup_enabled', 'banner_enabled',
    'popup_image', 'popup_mobile_image', 'banner_image', 'banner_mobile_image',
    'image_alt_text', 'heading', 'heading_ur', 'description', 'description_ur',
    'cta_label', 'cta_url', 'cta_new_tab', 'contact_number', 'external_website',
    'banner_heading', 'banner_heading_ur', 'banner_description',
    'banner_description_ur', 'banner_button_label', 'banner_button_url',
    'banner_dismissible', 'display_frequency', 'dismissal_hours',
    'starts_at', 'ends_at',
)

_INT_FIELDS = {'popup_enabled', 'banner_enabled', 'cta_new_tab',
               'banner_dismissible', 'dismissal_hours'}


def effective_status(row, now=None):
    """Derive the public-facing status from stored intent + schedule window."""
    now = now or core.utc_now_str()
    status = row['status']
    if status != 'ACTIVE':
        return status
    starts = str(row['starts_at'] or '')
    ends = str(row['ends_at'] or '')
    if starts and starts > now:
        return 'SCHEDULED'
    if ends and ends <= now:
        return 'EXPIRED'
    return 'ACTIVE'


def _placements(row):
    parts = []
    if row['popup_enabled']:
        parts.append('popup')
    if row['banner_enabled']:
        parts.append('banner')
    return parts


def _admin_dict(row, now=None):
    d = dict(row)
    d['effective_status'] = effective_status(row, now)
    d['placements'] = _placements(row)
    d['starts_at_kw'] = core.utc_to_kuwait_input(d.get('starts_at'))
    d['ends_at_kw'] = core.utc_to_kuwait_input(d.get('ends_at'))
    d['starts_at_kw_display'] = core.utc_to_kuwait_display(d.get('starts_at'))
    d['ends_at_kw_display'] = core.utc_to_kuwait_display(d.get('ends_at'))
    d['updated_at_kw_display'] = core.utc_to_kuwait_display(d.get('updated_at'))
    return d


def list_ads(user):
    db = core.get_db()
    try:
        now = core.utc_now_str()
        rows = db.execute(
            'SELECT * FROM website_advertisements ORDER BY (status = ?) DESC, updated_at DESC, id DESC',
            ['ACTIVE']).fetchall()
        return {'success': True, 'items': [_admin_dict(r, now) for r in rows]}
    finally:
        db.close()


def ad_detail(params, user):
    ad_id = int(params.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Advertisement not found.', 'status': 404}
        return {'success': True, 'item': _admin_dict(row)}
    finally:
        db.close()


def _validate_fields(data):
    """Validate + normalize a save payload. Returns (fields, error)."""
    fields = {}
    fields['internal_name'] = core.clean_text(data.get('internal_name'), 120)
    if not fields['internal_name']:
        return None, 'Internal advertisement name is required.'
    fields['campaign_reference'] = core.clean_text(data.get('campaign_reference'), 80)

    language = core.clean_text(data.get('language'), 10) or 'en'
    if language not in core.LANGUAGES:
        return None, 'Invalid language selection.'
    fields['language'] = language

    disclosure = core.clean_text(data.get('disclosure_label'), 40) or 'Announcement'
    if disclosure not in core.DISCLOSURE_LABELS:
        return None, 'Invalid disclosure label.'
    fields['disclosure_label'] = disclosure

    frequency = core.clean_text(data.get('display_frequency'), 40) or core.DEFAULT_FREQUENCY
    if frequency not in core.DISPLAY_FREQUENCIES:
        return None, 'Invalid display frequency.'
    fields['display_frequency'] = frequency

    try:
        dismissal = int(data.get('dismissal_hours', core.DEFAULT_DISMISSAL_HOURS))
    except (TypeError, ValueError):
        return None, 'Dismissal duration must be a number of hours.'
    if dismissal < 0 or dismissal > core.MAX_DISMISSAL_HOURS:
        return None, f'Dismissal duration must be between 0 and {core.MAX_DISMISSAL_HOURS} hours.'
    fields['dismissal_hours'] = dismissal

    for flag in ('popup_enabled', 'banner_enabled', 'cta_new_tab', 'banner_dismissible'):
        default = '1' if flag in ('cta_new_tab', 'banner_dismissible') else '0'
        fields[flag] = 0 if str(data.get(flag, default)).strip().lower() in ('0', 'false', 'no', 'off', '') else 1

    fields['heading'] = core.clean_text(data.get('heading'), 150)
    fields['heading_ur'] = core.clean_text(data.get('heading_ur'), 150)
    fields['description'] = core.clean_text(data.get('description'), 1000)
    fields['description_ur'] = core.clean_text(data.get('description_ur'), 1000)
    fields['image_alt_text'] = core.clean_text(data.get('image_alt_text'), 200)
    fields['cta_label'] = core.clean_text(data.get('cta_label'), 60)
    fields['banner_heading'] = core.clean_text(data.get('banner_heading'), 150)
    fields['banner_heading_ur'] = core.clean_text(data.get('banner_heading_ur'), 150)
    fields['banner_description'] = core.clean_text(data.get('banner_description'), 500)
    fields['banner_description_ur'] = core.clean_text(data.get('banner_description_ur'), 500)
    fields['banner_button_label'] = core.clean_text(data.get('banner_button_label'), 60)

    for url_field, label in (('cta_url', 'Call-to-action link'),
                             ('banner_button_url', 'Banner button link'),
                             ('external_website', 'Website address')):
        clean, err = core.validate_public_url(data.get(url_field), label)
        if err:
            return None, err
        fields[url_field] = clean

    phone, err = core.clean_phone(data.get('contact_number'))
    if err:
        return None, err
    fields['contact_number'] = phone

    starts = core.kuwait_input_to_utc(data.get('starts_at_kw'))
    if starts is None:
        return None, 'Start date/time is not valid.'
    ends = core.kuwait_input_to_utc(data.get('ends_at_kw'))
    if ends is None:
        return None, 'End date/time is not valid.'
    if starts and ends and ends <= starts:
        return None, 'End date/time must be after the start date/time.'
    fields['starts_at'] = starts
    fields['ends_at'] = ends
    return fields, None


def save_ad(data, user):
    """Create (no id) or update (id + expected_updated_at) an advertisement."""
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    fields, err = _validate_fields(data)
    if err:
        return {'success': False, 'error': err}

    ad_id = int(data.get('id') or 0)
    db = core.get_db()
    try:
        if not ad_id:
            cols = list(fields.keys()) + ['status', 'created_by', 'updated_by']
            values = list(fields.values()) + ['DRAFT', user['user'], user['user']]
            placeholders = ', '.join('?' for _ in cols)
            cur = db.execute(
                f"INSERT INTO website_advertisements ({', '.join(cols)}) VALUES ({placeholders})",
                values)
            new_id = cur.lastrowid
            write_audit(db, new_id, 'created', actor=user['user'],
                        new_value=fields['internal_name'])
            db.commit()
            row = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [new_id]).fetchone()
            return {'success': True, 'item': _admin_dict(row)}

        row = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Advertisement not found.', 'status': 404}
        if row['status'] == 'ARCHIVED':
            return {'success': False,
                    'error': 'Archived advertisements cannot be edited. Duplicate it into a new draft instead.'}
        expected = str(data.get('expected_updated_at') or '')
        if not expected:
            return {'success': False, 'error': 'Missing concurrency token. Reload and try again.', 'status': 409}

        # Image columns are in PUBLIC_FIELDS but only change via the upload
        # endpoint (which bumps content_version itself) — compare just the
        # fields this save payload actually carries.
        changed_public = []
        for f in PUBLIC_FIELDS:
            if f not in fields:
                continue
            old = int(row[f] or 0) if f in _INT_FIELDS else str(row[f] or '')
            new = int(fields[f] or 0) if f in _INT_FIELDS else str(fields[f] or '')
            if old != new:
                changed_public.append(f)
        new_version = int(row['content_version'] or 1) + (1 if changed_public else 0)

        set_clause = ', '.join(f'{k} = ?' for k in fields)
        args = list(fields.values()) + [new_version, user['user'], ad_id, expected]
        cur = db.execute(
            f"""UPDATE website_advertisements
                   SET {set_clause}, content_version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                 WHERE id = ? AND updated_at = ?""",
            args)
        if cur.rowcount == 0:
            db.rollback()
            return {'success': False,
                    'error': 'This advertisement was modified by another administrator. Reload to see the latest version.',
                    'status': 409}
        note = ('public content changed: ' + ', '.join(changed_public)) if changed_public \
            else 'internal metadata only'
        write_audit(db, ad_id, 'updated', actor=user['user'],
                    old_value=f"v{row['content_version']}", new_value=f'v{new_version}', note=note)
        db.commit()
        fresh = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        return {'success': True, 'item': _admin_dict(fresh), 'content_version_bumped': bool(changed_public)}
    finally:
        db.close()


def _activation_errors(row):
    errors = []
    if not row['popup_enabled'] and not row['banner_enabled']:
        errors.append('Enable the popup, the banner, or both before activating.')
    if row['popup_enabled'] and not str(row['heading'] or '').strip():
        errors.append('The popup requires a heading before activation.')
    if row['popup_enabled'] and str(row['popup_image'] or '') and not str(row['image_alt_text'] or '').strip():
        errors.append('Provide accessible alternative text for the popup image.')
    if row['banner_enabled'] and not str(row['banner_heading'] or '').strip():
        errors.append('The banner requires a heading before activation.')
    if row['banner_enabled'] and str(row['banner_image'] or '') and not str(row['image_alt_text'] or '').strip():
        errors.append('Provide accessible alternative text for the banner image.')
    now = core.utc_now_str()
    if str(row['ends_at'] or '') and str(row['ends_at']) <= now:
        errors.append('The end date/time has already passed. Update the schedule first.')
    return errors


def _find_conflicts(db, row, now):
    """Other ACTIVE, non-expired ads sharing an enabled placement (single-active model)."""
    conflicts = []
    others = db.execute(
        "SELECT * FROM website_advertisements WHERE status = 'ACTIVE' AND id != ?",
        [row['id']]).fetchall()
    for other in others:
        if effective_status(other, now) == 'EXPIRED':
            continue
        shared = [p for p in _placements(other) if p in _placements(row)]
        if shared:
            conflicts.append({'id': other['id'],
                              'internal_name': other['internal_name'],
                              'placements': shared})
    return conflicts


def set_status(data, user):
    """Actions: activate / pause / archive. Activation runs conflict detection."""
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    ad_id = int(data.get('id') or 0)
    action = core.clean_text(data.get('action'), 20).lower()
    if action not in ('activate', 'pause', 'archive'):
        return {'success': False, 'error': 'Invalid action.'}

    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Advertisement not found.', 'status': 404}
        old_status = row['status']

        if action == 'activate':
            if old_status == 'ARCHIVED':
                return {'success': False,
                        'error': 'Archived advertisements cannot be reactivated. Duplicate it into a new draft instead.'}
            if old_status == 'ACTIVE':
                return {'success': False, 'error': 'This advertisement is already active.'}
            errors = _activation_errors(row)
            if errors:
                return {'success': False, 'error': ' '.join(errors)}
            now = core.utc_now_str()
            conflicts = _find_conflicts(db, row, now)
            confirm = str(data.get('confirm_conflict', '')).strip().lower() in ('1', 'true', 'yes')
            if conflicts and not confirm:
                return {'success': False, 'status': 409, 'error': 'conflict',
                        'conflicts': conflicts,
                        'message': 'Another advertisement is active for the same placement. '
                                   'Confirm to pause it and activate this one.'}
            for conflict in conflicts:
                db.execute(
                    "UPDATE website_advertisements SET status = 'PAUSED', updated_by = ?, "
                    'updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    [user['user'], conflict['id']])
                write_audit(db, conflict['id'], 'conflict_paused', actor=user['user'],
                            old_value='ACTIVE', new_value='PAUSED',
                            note=f"Paused automatically when activating advertisement #{ad_id}")
            new_status = 'ACTIVE'
        elif action == 'pause':
            if old_status != 'ACTIVE':
                return {'success': False, 'error': 'Only an active advertisement can be paused.'}
            new_status = 'PAUSED'
        else:  # archive
            if old_status == 'ARCHIVED':
                return {'success': False, 'error': 'This advertisement is already archived.'}
            new_status = 'ARCHIVED'

        archived_at_clause = ", archived_at = ?" if new_status == 'ARCHIVED' else ''
        args = [new_status, user['user']]
        if new_status == 'ARCHIVED':
            args.append(core.utc_now_str())
        args.append(ad_id)
        db.execute(
            f"""UPDATE website_advertisements
                   SET status = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP{archived_at_clause}
                 WHERE id = ?""",
            args)
        write_audit(db, ad_id, action + 'd', actor=user['user'],
                    old_value=old_status, new_value=new_status)
        db.commit()
        fresh = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        return {'success': True, 'item': _admin_dict(fresh)}
    finally:
        db.close()


def duplicate_ad(data, user):
    """Copy an advertisement (any status) into a new DRAFT with content_version 1.

    Image files are shared by reference; files are never deleted in v1, so a
    shared filename stays valid even if the source advertisement changes.
    """
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    ad_id = int(data.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Advertisement not found.', 'status': 404}
        copy_fields = ['campaign_reference', 'language', 'disclosure_label',
                       'popup_enabled', 'banner_enabled',
                       'popup_image', 'popup_mobile_image', 'banner_image', 'banner_mobile_image',
                       'image_alt_text', 'heading', 'heading_ur', 'description', 'description_ur',
                       'cta_label', 'cta_url', 'cta_new_tab', 'contact_number', 'external_website',
                       'banner_heading', 'banner_heading_ur', 'banner_description',
                       'banner_description_ur', 'banner_button_label', 'banner_button_url',
                       'banner_dismissible', 'display_frequency', 'dismissal_hours',
                       'starts_at', 'ends_at']
        name = core.clean_text(f"Copy of {row['internal_name']}", 120)
        cols = ['internal_name', 'status', 'content_version', 'created_by', 'updated_by'] + copy_fields
        values = [name, 'DRAFT', 1, user['user'], user['user']] + [row[f] for f in copy_fields]
        placeholders = ', '.join('?' for _ in cols)
        cur = db.execute(
            f"INSERT INTO website_advertisements ({', '.join(cols)}) VALUES ({placeholders})",
            values)
        new_id = cur.lastrowid
        write_audit(db, new_id, 'duplicated', actor=user['user'],
                    old_value=f'source #{ad_id}', new_value=name)
        db.commit()
        fresh = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [new_id]).fetchone()
        return {'success': True, 'item': _admin_dict(fresh)}
    finally:
        db.close()


def attach_image(fields, original_name, raw, user):
    """Validate + store an uploaded image, then point the slot column at it.

    Additive replacement (owner decision #12): the new file is written first;
    the DB column changes only after storage succeeds; the old file remains.
    """
    from . import media
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    ad_id = int(fields.get('ad_id') or 0)
    slot = core.clean_text(fields.get('slot'), 20)
    if slot not in core.IMAGE_SLOTS:
        return {'success': False, 'error': 'Invalid image slot.'}
    column = core.SLOT_COLUMNS[slot]

    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Advertisement not found.', 'status': 404}
        if row['status'] == 'ARCHIVED':
            return {'success': False, 'error': 'Archived advertisements cannot be edited.'}

        ext, err = media.validate_image(original_name, raw)
        if err:
            return {'success': False, 'error': err}
        try:
            stored = media.store_image(ad_id, slot, raw, ext)
        except Exception as exc:
            print(f'[Ads] image store failed: {exc}', flush=True)
            return {'success': False, 'error': 'The image could not be stored. The previous image is unchanged.'}

        old_name = str(row[column] or '')
        new_version = int(row['content_version'] or 1) + 1
        db.execute(
            f"""UPDATE website_advertisements
                   SET {column} = ?, content_version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                 WHERE id = ?""",
            [stored, new_version, user['user'], ad_id])
        write_audit(db, ad_id, 'image_uploaded', actor=user['user'],
                    old_value=old_name, new_value=stored,
                    note=f'slot {slot}, {len(raw)} bytes')
        db.commit()
        fresh = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [ad_id]).fetchone()
        return {'success': True, 'item': _admin_dict(fresh), 'stored_name': stored}
    finally:
        db.close()


# ── Public payload (homepage) ────────────────────────────────────

def _media_url(base_path, name):
    return f'{base_path}/ads/media/{name}' if name else ''


def _popup_dict(row, base_path):
    return {
        'id': row['id'],
        'v': int(row['content_version'] or 1),
        'disclosure': row['disclosure_label'],
        'lang': row['language'],
        'image': _media_url(base_path, row['popup_image']),
        'mobileImage': _media_url(base_path, row['popup_mobile_image']),
        'alt': row['image_alt_text'],
        'heading': row['heading'],
        'headingUr': row['heading_ur'],
        'description': row['description'],
        'descriptionUr': row['description_ur'],
        'ctaLabel': row['cta_label'],
        'ctaUrl': row['cta_url'],
        'ctaNewTab': bool(row['cta_new_tab']),
        'contact': row['contact_number'],
        'website': row['external_website'],
        'frequency': row['display_frequency'],
        'dismissalHours': int(row['dismissal_hours'] or 0),
    }


def _banner_dict(row, base_path):
    return {
        'id': row['id'],
        'v': int(row['content_version'] or 1),
        'disclosure': row['disclosure_label'],
        'lang': row['language'],
        'image': _media_url(base_path, row['banner_image']),
        'mobileImage': _media_url(base_path, row['banner_mobile_image']),
        'alt': row['image_alt_text'],
        'heading': row['banner_heading'],
        'headingUr': row['banner_heading_ur'],
        'description': row['banner_description'],
        'descriptionUr': row['banner_description_ur'],
        'buttonLabel': row['banner_button_label'],
        'buttonUrl': row['banner_button_url'],
        'dismissible': bool(row['banner_dismissible']),
    }


def _effective_placement_row(db, column, now):
    rows = db.execute(
        f"SELECT * FROM website_advertisements WHERE status = 'ACTIVE' AND {column} = 1").fetchall()
    live = [r for r in rows if effective_status(r, now) == 'ACTIVE']
    if not live:
        return None
    live.sort(key=lambda r: (str(r['updated_at'] or ''), int(r['id'])), reverse=True)
    return live[0]


def payload_to_json(payload):
    """Serialize for direct embedding inside a <script> block in the homepage.

    ensure_ascii escapes U+2028/U+2029 and all non-ASCII; the extra '<'
    escape prevents '</script>' (and any other tag) from terminating the
    script element, since the template engine performs no escaping.
    """
    return json.dumps(payload, ensure_ascii=True).replace('<', '\\u003c')


def _public_payload_dict(db, now, media_base):
    """The single active-advertisement selection used by every public surface.

    Both the embedded homepage payload and the public JSON API go through
    here, so publication rules can never drift between them. Returns None when
    nothing is live. Only ever admits status='ACTIVE' rows that are also
    inside their schedule window (effective_status), so DRAFT / PAUSED /
    ARCHIVED / SCHEDULED / EXPIRED are all excluded.
    """
    popup_row = _effective_placement_row(db, 'popup_enabled', now)
    banner_row = _effective_placement_row(db, 'banner_enabled', now)
    if popup_row is None and banner_row is None:
        return None
    return {
        'popup': _popup_dict(popup_row, media_base) if popup_row is not None else None,
        'banner': _banner_dict(banner_row, media_base) if banner_row is not None else None,
    }


def public_payload_json(base_path=''):
    """Active-advertisement payload for the homepage. Returns a JSON string.

    Media URLs stay backend-relative here: this payload is embedded into a
    page served by this same backend (Flask homepage + admin preview).

    Never raises to the caller's benefit — server.py additionally wraps this
    in a try/except so a failure here can never break the homepage.
    """
    db = core.get_db()
    try:
        payload = _public_payload_dict(db, core.utc_now_str(), base_path)
        if payload is None:
            return 'null'
        return payload_to_json(payload)
    finally:
        db.close()


def public_payload_api():
    """Active-advertisement payload for the public JSON API. Returns a dict.

    Identical selection to public_payload_json (same _public_payload_dict),
    but media URLs are absolute because the caller is a different origin
    (the React site on cwakuwait.com). Never consults preview logic:
    unpublished advertisements are not returned here under any circumstance.

    Takes no request state on purpose: the media base is env-only, so this
    response is byte-identical for every caller and safe to cache publicly.
    """
    db = core.get_db()
    try:
        payload = _public_payload_dict(db, core.utc_now_str(),
                                       core.public_media_base())
        return {'success': True, 'advertisement': payload}
    finally:
        db.close()


def preview_payload_json(ad_id, base_path=''):
    """Payload for the admin preview: any status, dismissal persistence disabled."""
    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM website_advertisements WHERE id = ?', [int(ad_id or 0)]).fetchone()
        if not row:
            return None
        payload = {
            'preview': True,
            'popup': _popup_dict(row, base_path) if row['popup_enabled'] else None,
            'banner': _banner_dict(row, base_path) if row['banner_enabled'] else None,
        }
        return payload_to_json(payload)
    finally:
        db.close()
