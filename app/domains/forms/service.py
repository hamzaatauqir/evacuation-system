"""Embassy Forms Library — lifecycle, validation, and public payload.

Statuses: DRAFT -> PUBLISHED -> ARCHIVED, all reversible except that nothing
is ever hard-deleted (owner decision). Unlike the ads module there is no
scheduling window and therefore no derived status — a form is exactly what its
stored status says, which keeps the public query a plain indexed lookup.

Replacement keeps the public URL stable: /forms/download/<id> always serves the
current file. The superseded file stays on disk and gains a row in
embassy_form_versions, so a mistaken replace is recoverable.
"""
from . import core, storage
from .audit import write_audit, write_global

# Metadata a staff member may set through save_form. Deliberately excludes
# every file-derived column (stored_filename, mime_type, file_size,
# file_sha256, version_number) and every lifecycle stamp — those are owned by
# attach_file() and set_status() respectively, so a crafted save payload can
# never point a row at a different file or forge a publication date.
EDITABLE_FIELDS = (
    'title', 'title_ur', 'description', 'description_ur',
    'category_id', 'language', 'version_label', 'effective_date',
    'display_order', 'is_featured',
)


# ── Row shaping ──────────────────────────────────────────────────

def _category_map(db):
    rows = db.execute(
        'SELECT * FROM embassy_form_categories ORDER BY display_order, id'
    ).fetchall()
    return {int(r['id']): dict(r) for r in rows}


def _admin_dict(row, categories):
    d = dict(row)
    cat = categories.get(int(row['category_id'] or 0)) or {}
    d['category_label'] = cat.get('label') or ''
    d['category_slug'] = cat.get('slug') or ''
    d['has_file'] = bool(row['stored_filename'])
    d['file_size_display'] = core.human_file_size(row['file_size'])
    d['language_label'] = core.LANGUAGE_LABELS.get(row['language'], row['language'])
    d['updated_at_kw'] = core.utc_to_kuwait_display(row['updated_at'])
    d['updated_display'] = core.display_date(row['updated_at'])
    return d


def _public_dict(row, categories):
    """Citizen-facing shape. Only fields a member of the public should see.

    Deliberately omits stored_filename, created_by/updated_by and every
    internal stamp — the public payload must not leak staff usernames or the
    on-disk naming scheme.
    """
    cat = categories.get(int(row['category_id'] or 0)) or {}
    updated = row['published_at'] or row['updated_at']
    return {
        'id': int(row['id']),
        'title': row['title'],
        'titleUr': row['title_ur'],
        'description': row['description'],
        'descriptionUr': row['description_ur'],
        'category': cat.get('label') or 'Other',
        'categorySlug': cat.get('slug') or 'other',
        'language': row['language'],
        'languageLabel': core.LANGUAGE_LABELS.get(row['language'], row['language']),
        'fileType': 'PDF',
        'fileSize': int(row['file_size'] or 0),
        'fileSizeDisplay': core.human_file_size(row['file_size']),
        'versionLabel': row['version_label'],
        'effectiveDate': row['effective_date'],
        'updatedDisplay': core.display_date(updated),
        'updatedAt': str(updated or ''),
        'featured': bool(row['is_featured']),
        'downloadUrl': core.public_download_url(row['id']),
    }


# ── Staff reads ──────────────────────────────────────────────────

def list_forms(user, params=None):
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    params = params or {}
    db = core.get_db()
    try:
        categories = _category_map(db)
        where, args = [], []
        status = core.normalize_status(params.get('status'))
        if status:
            where.append('status = ?')
            args.append(status)
        category_id = int(params.get('category_id') or 0)
        if category_id:
            where.append('category_id = ?')
            args.append(category_id)
        sql = 'SELECT * FROM embassy_forms'
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY is_featured DESC, display_order, updated_at DESC, id DESC'
        rows = db.execute(sql, args).fetchall()
        return {
            'success': True,
            'items': [_admin_dict(r, categories) for r in rows],
            'categories': [dict(c) for c in categories.values()],
            'statuses': list(core.STATUSES),
            'languages': [{'value': v, 'label': core.LANGUAGE_LABELS[v]} for v in core.LANGUAGES],
            'can_admin': core.user_is_admin(user),
            'max_file_mb': core.MAX_FILE_BYTES // (1024 * 1024),
        }
    finally:
        db.close()


def form_detail(params, user):
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    form_id = int((params or {}).get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM embassy_forms WHERE id = ?', [form_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Form not found.', 'status': 404}
        categories = _category_map(db)
        versions = db.execute(
            'SELECT * FROM embassy_form_versions WHERE form_id = ? ORDER BY version_number DESC',
            [form_id],
        ).fetchall()
        return {
            'success': True,
            'form': _admin_dict(row, categories),
            'versions': [dict(v) for v in versions],
        }
    finally:
        db.close()


# ── Validation ───────────────────────────────────────────────────

def _validate_fields(data, db):
    """Returns (values_dict, error). Only EDITABLE_FIELDS are ever returned."""
    title = core.clean_text(data.get('title'), core.MAX_TITLE_LEN)
    if not title:
        return None, 'A form title is required.'

    category_id = int(data.get('category_id') or 0)
    if not category_id:
        return None, 'Please choose a category.'
    cat = db.execute(
        'SELECT id, is_active FROM embassy_form_categories WHERE id = ?', [category_id]
    ).fetchone()
    if not cat:
        return None, 'The selected category no longer exists.'
    if not int(cat['is_active'] or 0):
        return None, 'The selected category is inactive. Choose an active category.'

    effective_date, err = core.validate_date(data.get('effective_date'), 'Effective date')
    if err:
        return None, err

    try:
        display_order = int(data.get('display_order') or 0)
    except (TypeError, ValueError):
        return None, 'Display order must be a whole number.'
    if display_order < 0 or display_order > 99999:
        return None, 'Display order must be between 0 and 99999.'

    return {
        'title': title,
        'title_ur': core.clean_text(data.get('title_ur'), core.MAX_TITLE_LEN),
        'description': core.clean_text(data.get('description'), core.MAX_DESCRIPTION_LEN),
        'description_ur': core.clean_text(data.get('description_ur'), core.MAX_DESCRIPTION_LEN),
        'category_id': category_id,
        'language': core.normalize_language(data.get('language')),
        'version_label': core.clean_text(data.get('version_label'), core.MAX_VERSION_LABEL_LEN),
        'effective_date': effective_date,
        'display_order': display_order,
        'is_featured': 1 if str(data.get('is_featured', '0')).strip().lower()
                       in ('1', 'true', 'yes', 'on') else 0,
    }, None


# ── Staff writes ─────────────────────────────────────────────────

def save_form(data, user):
    """Create (id == 0) or update a form's metadata. Never touches the file."""
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    data = data or {}
    form_id = int(data.get('id') or 0)
    db = core.get_db()
    try:
        values, err = _validate_fields(data, db)
        if err:
            return {'success': False, 'error': err}

        if form_id:
            row = db.execute('SELECT * FROM embassy_forms WHERE id = ?', [form_id]).fetchone()
            if not row:
                return {'success': False, 'error': 'Form not found.', 'status': 404}
            if row['status'] == 'ARCHIVED':
                return {'success': False, 'status': 409,
                        'error': 'Archived forms cannot be edited. Restore the form first.'}
            assignments = ', '.join(f'{k} = ?' for k in values)
            db.execute(
                f'UPDATE embassy_forms SET {assignments}, updated_by = ?, '
                f'updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                list(values.values()) + [user['user'], form_id],
            )
            changed = [k for k in values if str(row[k] or '') != str(values[k] or '')]
            write_audit(db, form_id, 'form_updated', actor=user['user'],
                        old_value=core.clean_text(row['title'], 200),
                        new_value=values['title'],
                        note='changed: ' + (', '.join(changed) if changed else 'nothing'))
        else:
            columns = ', '.join(values)
            placeholders = ', '.join('?' for _ in values)
            cur = db.execute(
                f'INSERT INTO embassy_forms ({columns}, status, created_by, updated_by) '
                f'VALUES ({placeholders}, ?, ?, ?)',
                list(values.values()) + ['DRAFT', user['user'], user['user']],
            )
            form_id = cur.lastrowid
            write_audit(db, form_id, 'form_created', actor=user['user'],
                        new_value=values['title'])
        db.commit()
        return {'success': True, 'id': form_id}
    finally:
        db.close()


def attach_file(fields, original_name, raw, user):
    """Attach the first PDF, or replace an existing one (retaining the old).

    Validation and the disk write both happen before any DB mutation, so a
    rejected or failed upload leaves the current published file untouched.
    """
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    form_id = int((fields or {}).get('form_id') or 0)
    if not form_id:
        return {'success': False, 'error': 'Save the form details before uploading a file.'}

    mime, err = storage.validate_pdf(original_name, raw)
    if err:
        return {'success': False, 'error': err}

    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM embassy_forms WHERE id = ?', [form_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Form not found.', 'status': 404}
        if row['status'] == 'ARCHIVED':
            return {'success': False, 'status': 409,
                    'error': 'Archived forms cannot be modified. Restore the form first.'}

        digest = storage.sha256_hex(raw)
        is_replacement = bool(row['stored_filename'])
        if is_replacement and digest == str(row['file_sha256'] or ''):
            return {'success': False, 'status': 409,
                    'error': 'That is byte-for-byte the file already attached. '
                             'Upload the new revision instead.'}

        new_version = int(row['version_number'] or 1) + 1 if is_replacement else 1
        try:
            stored = storage.store_file(form_id, new_version, raw)
        except Exception as exc:
            print(f'[Forms] store failed for form {form_id}: {exc}', flush=True)
            return {'success': False, 'status': 500,
                    'error': 'The file could not be saved on the server. Please try again.'}

        if is_replacement:
            # Record the outgoing file BEFORE the row starts pointing elsewhere.
            db.execute(
                """INSERT INTO embassy_form_versions
                       (form_id, version_number, original_filename, stored_filename,
                        mime_type, file_size, file_sha256, version_label,
                        superseded_at, replaced_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [form_id, int(row['version_number'] or 1), row['original_filename'],
                 row['stored_filename'], row['mime_type'], int(row['file_size'] or 0),
                 row['file_sha256'], row['version_label'],
                 core.utc_now_str(), user['user']],
            )

        db.execute(
            """UPDATE embassy_forms
                  SET original_filename = ?, stored_filename = ?, mime_type = ?,
                      file_size = ?, file_sha256 = ?, version_number = ?,
                      updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
            [core.clean_text(original_name, 200), stored, mime, len(raw), digest,
             new_version, user['user'], form_id],
        )
        write_audit(
            db, form_id, 'file_replaced' if is_replacement else 'file_uploaded',
            actor=user['user'],
            old_value=core.clean_text(row['original_filename'], 200) if is_replacement else '',
            new_value=core.clean_text(original_name, 200),
            note=f'v{new_version}, {len(raw)} bytes, sha256 {digest[:12]}',
        )
        db.commit()
        return {'success': True, 'id': form_id, 'version_number': new_version,
                'replaced': is_replacement,
                'file_size_display': core.human_file_size(len(raw))}
    finally:
        db.close()


# Which role may drive each transition. publish/unpublish is day-to-day work;
# archive/restore removes a document from public record and stays with admins.
_ACTION_RULES = {
    'publish': ('PUBLISHED', 'form_published', False),
    'unpublish': ('DRAFT', 'form_unpublished', False),
    'archive': ('ARCHIVED', 'form_archived', True),
    'restore': ('DRAFT', 'form_restored', True),
}


def set_status(data, user):
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    data = data or {}
    action = core.clean_text(data.get('action'), 20).lower()
    rule = _ACTION_RULES.get(action)
    if not rule:
        return {'success': False, 'error': 'Unknown action.'}
    new_status, event, admin_only = rule
    if admin_only and not core.user_is_admin(user):
        return {'success': False, 'status': 403,
                'error': 'Only an administrator can archive or restore a form.'}

    form_id = int(data.get('id') or 0)
    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM embassy_forms WHERE id = ?', [form_id]).fetchone()
        if not row:
            return {'success': False, 'error': 'Form not found.', 'status': 404}
        old_status = row['status']
        if old_status == new_status:
            return {'success': False, 'status': 409,
                    'error': f'This form is already {new_status.lower()}.'}
        if action == 'publish':
            if not row['stored_filename']:
                return {'success': False,
                        'error': 'Attach a PDF before publishing this form.'}
            if old_status == 'ARCHIVED':
                return {'success': False, 'status': 409,
                        'error': 'Restore the form before publishing it again.'}
        if action == 'restore' and old_status != 'ARCHIVED':
            return {'success': False, 'status': 409,
                    'error': 'Only archived forms can be restored.'}
        if action == 'unpublish' and old_status != 'PUBLISHED':
            return {'success': False, 'status': 409,
                    'error': 'Only published forms can be unpublished.'}

        stamps = ''
        if new_status == 'PUBLISHED':
            stamps = ", published_at = '" + core.utc_now_str() + "', archived_at = ''"
        elif new_status == 'ARCHIVED':
            stamps = ", archived_at = '" + core.utc_now_str() + "'"
        elif action == 'restore':
            stamps = ", archived_at = ''"
        db.execute(
            f'UPDATE embassy_forms SET status = ?, updated_by = ?, '
            f'updated_at = CURRENT_TIMESTAMP{stamps} WHERE id = ?',
            [new_status, user['user'], form_id],
        )
        write_audit(db, form_id, event, actor=user['user'],
                    old_value=old_status, new_value=new_status,
                    note=core.clean_text(row['title'], 200))
        if action in ('publish', 'archive'):
            write_global(db, f'forms.{action}', form_id, actor=user['user'],
                         details=core.clean_text(row['title'], 200))
        db.commit()
        # Deliberately 'new_status', not 'status': routes._send_api_result pops
        # 'status' as the HTTP status code, so a form status here would be cast
        # to int and blow up the response.
        return {'success': True, 'id': form_id, 'new_status': new_status,
                'title': row['title']}
    finally:
        db.close()


def reorder_forms(data, user):
    """Bulk display_order update from a drag-and-drop reorder."""
    if not core.user_can_manage(user):
        return {'success': False, 'error': 'Access denied', 'status': 403}
    order = (data or {}).get('order')
    if not isinstance(order, list) or not order:
        return {'success': False, 'error': 'No ordering was supplied.'}
    if len(order) > 1000:
        return {'success': False, 'error': 'Too many forms in one reorder request.'}
    try:
        ids = [int(x) for x in order]
    except (TypeError, ValueError):
        return {'success': False, 'error': 'Invalid ordering payload.'}

    db = core.get_db()
    try:
        known = {int(r['id']) for r in db.execute('SELECT id FROM embassy_forms').fetchall()}
        unknown = [i for i in ids if i not in known]
        if unknown:
            return {'success': False, 'status': 404,
                    'error': 'The list is out of date. Reload the page and try again.'}
        for position, form_id in enumerate(ids, start=1):
            db.execute(
                'UPDATE embassy_forms SET display_order = ?, updated_by = ?, '
                'updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                [position * 10, user['user'], form_id],
            )
        write_audit(db, 0, 'forms_reordered', actor=user['user'],
                    note=f'{len(ids)} forms reordered')
        db.commit()
        return {'success': True, 'count': len(ids)}
    finally:
        db.close()


def manage_category(data, user):
    """Admin-only category create / rename / reorder / activate / deactivate."""
    if not core.user_is_admin(user):
        return {'success': False, 'status': 403,
                'error': 'Only an administrator can manage categories.'}
    data = data or {}
    action = core.clean_text(data.get('action'), 20).lower()
    db = core.get_db()
    try:
        if action == 'create':
            label = core.clean_text(data.get('label'), core.MAX_CATEGORY_LABEL_LEN)
            if not label:
                return {'success': False, 'error': 'A category name is required.'}
            slug = core.clean_slug(data.get('slug') or label)
            if not slug:
                return {'success': False,
                        'error': 'The category name must contain at least one letter or number.'}
            clash = db.execute(
                'SELECT id FROM embassy_form_categories WHERE slug = ?', [slug]
            ).fetchone()
            if clash:
                return {'success': False, 'status': 409,
                        'error': 'A category with that name already exists.'}
            try:
                display_order = int(data.get('display_order') or 0)
            except (TypeError, ValueError):
                display_order = 0
            cur = db.execute(
                """INSERT INTO embassy_form_categories (slug, label, label_ur, display_order, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                [slug, label, core.clean_text(data.get('label_ur'), core.MAX_CATEGORY_LABEL_LEN),
                 display_order or 900],
            )
            write_audit(db, 0, 'category_changed', actor=user['user'],
                        new_value=label, note=f'created category {slug}')
            db.commit()
            return {'success': True, 'id': cur.lastrowid}

        category_id = int(data.get('id') or 0)
        row = db.execute(
            'SELECT * FROM embassy_form_categories WHERE id = ?', [category_id]
        ).fetchone()
        if not row:
            return {'success': False, 'error': 'Category not found.', 'status': 404}

        if action == 'update':
            label = core.clean_text(data.get('label'), core.MAX_CATEGORY_LABEL_LEN) or row['label']
            try:
                display_order = int(data.get('display_order', row['display_order']) or 0)
            except (TypeError, ValueError):
                display_order = int(row['display_order'] or 0)
            db.execute(
                """UPDATE embassy_form_categories
                      SET label = ?, label_ur = ?, display_order = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                [label, core.clean_text(data.get('label_ur'), core.MAX_CATEGORY_LABEL_LEN),
                 display_order, category_id],
            )
            write_audit(db, 0, 'category_changed', actor=user['user'],
                        old_value=row['label'], new_value=label,
                        note=f'updated category {row["slug"]}')
        elif action in ('activate', 'deactivate'):
            active = 1 if action == 'activate' else 0
            if not active:
                in_use = db.execute(
                    "SELECT COUNT(*) AS n FROM embassy_forms "
                    "WHERE category_id = ? AND status != 'ARCHIVED'",
                    [category_id],
                ).fetchone()
                if int(in_use['n'] or 0):
                    return {'success': False, 'status': 409,
                            'error': f'{in_use["n"]} active form(s) still use this category. '
                                     f'Move or archive them first.'}
            db.execute(
                'UPDATE embassy_form_categories SET is_active = ?, updated_at = CURRENT_TIMESTAMP '
                'WHERE id = ?',
                [active, category_id],
            )
            write_audit(db, 0, 'category_changed', actor=user['user'],
                        old_value=str(row['is_active']), new_value=str(active),
                        note=f'{action}d category {row["slug"]}')
        else:
            return {'success': False, 'error': 'Unknown action.'}
        db.commit()
        return {'success': True, 'id': category_id}
    finally:
        db.close()


# ── Public surfaces ──────────────────────────────────────────────

def public_payload():
    """Every published form plus the categories that actually have one.

    Passed no request state on purpose: the response is cacheable and must not
    vary with client-supplied headers.
    """
    db = core.get_db()
    try:
        categories = _category_map(db)
        rows = db.execute(
            """SELECT * FROM embassy_forms
                WHERE status = ? AND stored_filename != ''
                ORDER BY is_featured DESC, display_order, updated_at DESC, id DESC""",
            [core.PUBLIC_STATUS],
        ).fetchall()
        forms = [_public_dict(r, categories) for r in rows]
        used = {f['categorySlug'] for f in forms}
        visible = [
            {'slug': c['slug'], 'label': c['label'], 'labelUr': c['label_ur']}
            for c in categories.values()
            if int(c['is_active'] or 0) and c['slug'] in used
        ]
        latest = max((f['updatedAt'] for f in forms), default='')
        return {
            'success': True,
            'forms': forms,
            'categories': visible,
            'updatedDisplay': core.display_date(latest),
        }
    finally:
        db.close()


def public_payload_api():
    """Never raises and never returns an error shape to the public site.

    A database or module failure must degrade to "no forms yet", not a 500 —
    the same contract as the ads public endpoint.
    """
    try:
        return public_payload()
    except Exception as exc:
        print(f'[Forms] public payload failed: {exc}', flush=True)
        return {'success': True, 'forms': [], 'categories': [], 'updatedDisplay': ''}


def resolve_download(form_id):
    """Public download. Returns (bytes, filename, mime, error).

    Only PUBLISHED forms resolve. Draft, archived and non-existent ids all
    produce the identical error so ids cannot be probed for unpublished work.
    """
    not_found = (None, None, None, 'Form not found')
    try:
        form_id = int(form_id or 0)
    except (TypeError, ValueError):
        return not_found
    if form_id <= 0:
        return not_found

    db = core.get_db()
    try:
        row = db.execute(
            'SELECT * FROM embassy_forms WHERE id = ? AND status = ?',
            [form_id, core.PUBLIC_STATUS],
        ).fetchone()
        if not row or not row['stored_filename']:
            return not_found
        raw, err = storage.read_stored(row['stored_filename'])
        if err:
            # The row says published but the file is gone — an operational
            # fault, not a bad request. Log it loudly; tell the citizen nothing
            # about the internals.
            print(f'[Forms] published form {form_id} has no readable file '
                  f'({row["stored_filename"]!r})', flush=True)
            return not_found
        try:
            db.execute(
                'UPDATE embassy_forms SET download_count = download_count + 1 WHERE id = ?',
                [form_id],
            )
            db.commit()
        except Exception as exc:
            # A counter is never worth failing a citizen's download over.
            print(f'[Forms] download_count update failed for {form_id}: {exc}', flush=True)
        return raw, storage.safe_download_filename(row['original_filename'], form_id,
                                                    row['title']), \
            row['mime_type'] or core.ALLOWED_MIME, None
    finally:
        db.close()


def resolve_preview(form_id, user):
    """Staff preview of any status, including DRAFT. Returns the same tuple."""
    if not core.user_can_manage(user):
        return None, None, None, 'Access denied'
    db = core.get_db()
    try:
        row = db.execute('SELECT * FROM embassy_forms WHERE id = ?',
                         [int(form_id or 0)]).fetchone()
        if not row or not row['stored_filename']:
            return None, None, None, 'Form not found'
        raw, err = storage.read_stored(row['stored_filename'])
        if err:
            return None, None, None, err
        return raw, storage.safe_download_filename(row['original_filename'], row['id'],
                                                   row['title']), \
            row['mime_type'] or core.ALLOWED_MIME, None
    finally:
        db.close()
