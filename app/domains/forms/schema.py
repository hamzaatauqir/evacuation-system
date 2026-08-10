"""Embassy Forms Library — additive, idempotent SQLite schema.

Called from init_db() in server.py inside a try/except guard, mirroring the
hostel and ads module bootstrap. Never alters existing tables. PDF binaries are
never stored here — only generated basenames under the embassy_forms directory.

Column conventions follow website_advertisements / hostel_*:
- every column NOT NULL with a '' or 0 default, so no NULL handling anywhere;
- created_at / updated_at as TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
- lifecycle stamps (published_at, archived_at, superseded_at) as TEXT, matching
  website_advertisements.archived_at;
- no foreign keys — PRAGMA foreign_keys is never enabled in this codebase.
"""
from . import core


def ensure_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS embassy_form_categories (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        slug           TEXT NOT NULL DEFAULT '',
        label          TEXT NOT NULL DEFAULT '',
        label_ur       TEXT NOT NULL DEFAULT '',
        display_order  INTEGER NOT NULL DEFAULT 0,
        is_active      INTEGER NOT NULL DEFAULT 1,
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS embassy_forms (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        title              TEXT NOT NULL DEFAULT '',
        title_ur           TEXT NOT NULL DEFAULT '',
        description        TEXT NOT NULL DEFAULT '',
        description_ur     TEXT NOT NULL DEFAULT '',
        category_id        INTEGER NOT NULL DEFAULT 0,
        language           TEXT NOT NULL DEFAULT 'en',
        status             TEXT NOT NULL DEFAULT 'DRAFT',
        original_filename  TEXT NOT NULL DEFAULT '',
        stored_filename    TEXT NOT NULL DEFAULT '',
        mime_type          TEXT NOT NULL DEFAULT '',
        file_size          INTEGER NOT NULL DEFAULT 0,
        file_sha256        TEXT NOT NULL DEFAULT '',
        version_label      TEXT NOT NULL DEFAULT '',
        version_number     INTEGER NOT NULL DEFAULT 1,
        effective_date     TEXT NOT NULL DEFAULT '',
        display_order      INTEGER NOT NULL DEFAULT 0,
        is_featured        INTEGER NOT NULL DEFAULT 0,
        download_count     INTEGER NOT NULL DEFAULT 0,
        created_by         TEXT NOT NULL DEFAULT '',
        updated_by         TEXT NOT NULL DEFAULT '',
        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        published_at       TEXT NOT NULL DEFAULT '',
        archived_at        TEXT NOT NULL DEFAULT ''
    );

    -- Superseded files. Retained deliberately: government forms are a
    -- records-retention matter, and it makes a mistaken 'Replace File'
    -- recoverable rather than permanent data loss.
    CREATE TABLE IF NOT EXISTS embassy_form_versions (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        form_id            INTEGER NOT NULL DEFAULT 0,
        version_number     INTEGER NOT NULL DEFAULT 1,
        original_filename  TEXT NOT NULL DEFAULT '',
        stored_filename    TEXT NOT NULL DEFAULT '',
        mime_type          TEXT NOT NULL DEFAULT '',
        file_size          INTEGER NOT NULL DEFAULT 0,
        file_sha256        TEXT NOT NULL DEFAULT '',
        version_label      TEXT NOT NULL DEFAULT '',
        superseded_at      TEXT NOT NULL DEFAULT '',
        replaced_by        TEXT NOT NULL DEFAULT '',
        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS embassy_form_audit (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        form_id      INTEGER NOT NULL DEFAULT 0,
        event_type   TEXT NOT NULL DEFAULT '',
        actor        TEXT NOT NULL DEFAULT '',
        old_value    TEXT NOT NULL DEFAULT '',
        new_value    TEXT NOT NULL DEFAULT '',
        note         TEXT NOT NULL DEFAULT '',
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_eforms_public
        ON embassy_forms(status, category_id, display_order);
    CREATE INDEX IF NOT EXISTS idx_eforms_updated
        ON embassy_forms(updated_at);
    CREATE INDEX IF NOT EXISTS idx_eform_cat_order
        ON embassy_form_categories(is_active, display_order);
    CREATE INDEX IF NOT EXISTS idx_eform_ver_form
        ON embassy_form_versions(form_id);
    CREATE INDEX IF NOT EXISTS idx_eform_audit_form
        ON embassy_form_audit(form_id);
    CREATE INDEX IF NOT EXISTS idx_eform_audit_created
        ON embassy_form_audit(created_at);
    """)
    seed_categories(db)
    db.commit()


def seed_categories(db):
    """Insert the starter categories once. Idempotent and non-destructive.

    Only ever inserts a missing slug — it never updates or reactivates an
    existing row, so an admin who renames 'Other' or deactivates a category
    does not get it silently reverted on the next restart.
    """
    try:
        existing = {
            str(row['slug'] or '')
            for row in db.execute('SELECT slug FROM embassy_form_categories').fetchall()
        }
    except Exception:
        existing = set()
    for slug, label, order in core.DEFAULT_CATEGORIES:
        if slug in existing:
            continue
        db.execute(
            """INSERT INTO embassy_form_categories (slug, label, display_order, is_active)
               VALUES (?, ?, ?, 1)""",
            [slug, label, order],
        )
