"""Website Advertisements module — additive, idempotent SQLite schema.

Called from init_db() in server.py inside a try/except guard, mirroring the
hostel module bootstrap. Never alters existing tables. Image binaries are
never stored here — only generated filenames under the ad_uploads directory.
"""


def ensure_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS website_advertisements (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        internal_name          TEXT NOT NULL DEFAULT '',
        campaign_reference     TEXT NOT NULL DEFAULT '',
        status                 TEXT NOT NULL DEFAULT 'DRAFT',
        language               TEXT NOT NULL DEFAULT 'en',
        content_version        INTEGER NOT NULL DEFAULT 1,
        disclosure_label       TEXT NOT NULL DEFAULT 'Announcement',
        popup_enabled          INTEGER NOT NULL DEFAULT 0,
        banner_enabled         INTEGER NOT NULL DEFAULT 0,
        popup_image            TEXT NOT NULL DEFAULT '',
        popup_mobile_image     TEXT NOT NULL DEFAULT '',
        banner_image           TEXT NOT NULL DEFAULT '',
        banner_mobile_image    TEXT NOT NULL DEFAULT '',
        image_alt_text         TEXT NOT NULL DEFAULT '',
        heading                TEXT NOT NULL DEFAULT '',
        heading_ur             TEXT NOT NULL DEFAULT '',
        description            TEXT NOT NULL DEFAULT '',
        description_ur         TEXT NOT NULL DEFAULT '',
        cta_label              TEXT NOT NULL DEFAULT '',
        cta_url                TEXT NOT NULL DEFAULT '',
        cta_new_tab            INTEGER NOT NULL DEFAULT 1,
        contact_number         TEXT NOT NULL DEFAULT '',
        external_website       TEXT NOT NULL DEFAULT '',
        banner_heading         TEXT NOT NULL DEFAULT '',
        banner_heading_ur      TEXT NOT NULL DEFAULT '',
        banner_description     TEXT NOT NULL DEFAULT '',
        banner_description_ur  TEXT NOT NULL DEFAULT '',
        banner_button_label    TEXT NOT NULL DEFAULT '',
        banner_button_url      TEXT NOT NULL DEFAULT '',
        banner_dismissible     INTEGER NOT NULL DEFAULT 1,
        display_frequency      TEXT NOT NULL DEFAULT 'once_per_version',
        dismissal_hours        INTEGER NOT NULL DEFAULT 168,
        starts_at              TEXT NOT NULL DEFAULT '',
        ends_at                TEXT NOT NULL DEFAULT '',
        created_by             TEXT NOT NULL DEFAULT '',
        updated_by             TEXT NOT NULL DEFAULT '',
        created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        archived_at            TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS website_ad_audit (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_id        INTEGER NOT NULL DEFAULT 0,
        event_type   TEXT NOT NULL DEFAULT '',
        actor        TEXT NOT NULL DEFAULT '',
        old_value    TEXT NOT NULL DEFAULT '',
        new_value    TEXT NOT NULL DEFAULT '',
        note         TEXT NOT NULL DEFAULT '',
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_webads_status
        ON website_advertisements(status, starts_at, ends_at);
    CREATE INDEX IF NOT EXISTS idx_webads_updated
        ON website_advertisements(updated_at);
    CREATE INDEX IF NOT EXISTS idx_webad_audit_ad
        ON website_ad_audit(ad_id);
    CREATE INDEX IF NOT EXISTS idx_webad_audit_created
        ON website_ad_audit(created_at);
    """)
    db.commit()
