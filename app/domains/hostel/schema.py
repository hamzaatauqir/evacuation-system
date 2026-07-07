"""Hostel partner module — additive, idempotent SQLite schema.

Called from init_db() in server.py inside a try/except guard, mirroring the
grading-letter / nurse-onboarding bootstrappers. Never alters existing tables.
"""


def ensure_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS hostel_partners (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        partner_code      TEXT UNIQUE NOT NULL,
        partner_name      TEXT NOT NULL,
        display_name      TEXT DEFAULT '',
        contact_person    TEXT DEFAULT '',
        email             TEXT DEFAULT '',
        phone             TEXT DEFAULT '',
        address           TEXT DEFAULT '',
        status            TEXT NOT NULL DEFAULT 'ACTIVE',
        can_mark_arrival  INTEGER NOT NULL DEFAULT 1,
        notes             TEXT DEFAULT '',
        created_by        TEXT DEFAULT '',
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS hostel_partner_users (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        partner_id        INTEGER NOT NULL REFERENCES hostel_partners(id),
        username          TEXT UNIQUE NOT NULL,
        full_name         TEXT DEFAULT '',
        email             TEXT DEFAULT '',
        password_hash     TEXT NOT NULL DEFAULT '',
        password_salt     TEXT NOT NULL DEFAULT '',
        role              TEXT NOT NULL DEFAULT 'HOSTEL_PARTNER',
        status            TEXT NOT NULL DEFAULT 'ACTIVE',
        last_login_at     TIMESTAMP,
        created_by        TEXT DEFAULT '',
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS hostel_assignments (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_ref           TEXT UNIQUE NOT NULL,
        nurse_registration_id    INTEGER NOT NULL REFERENCES nurse_registrations(id),
        gl_application_id        INTEGER,
        partner_id               INTEGER NOT NULL REFERENCES hostel_partners(id),
        nurse_name               TEXT DEFAULT '',
        passport_number          TEXT DEFAULT '',
        nurse_reference          TEXT DEFAULT '',
        hostel_name              TEXT DEFAULT '',
        room_number              TEXT DEFAULT '',
        bed_number               TEXT DEFAULT '',
        assigned_date            TEXT DEFAULT '',
        expected_arrival_date    TEXT DEFAULT '',
        actual_arrival_date      TEXT DEFAULT '',
        status                   TEXT NOT NULL DEFAULT 'ASSIGNED',
        notes                    TEXT DEFAULT '',
        note_for_partner         TEXT DEFAULT '',
        partner_note             TEXT DEFAULT '',
        acknowledged_at          TIMESTAMP,
        acknowledged_by          TEXT DEFAULT '',
        assigned_by              TEXT DEFAULT '',
        cancelled_by             TEXT DEFAULT '',
        cancelled_at             TIMESTAMP,
        cancellation_reason      TEXT DEFAULT '',
        created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS hostel_agreements (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id            INTEGER NOT NULL REFERENCES hostel_assignments(id),
        nurse_registration_id    INTEGER NOT NULL,
        partner_id               INTEGER NOT NULL REFERENCES hostel_partners(id),
        document_type            TEXT NOT NULL DEFAULT 'ACCOMMODATION_AGREEMENT',
        file_name                TEXT NOT NULL DEFAULT '',
        stored_name              TEXT NOT NULL DEFAULT '',
        mime_type                TEXT NOT NULL DEFAULT 'application/pdf',
        file_size                INTEGER NOT NULL DEFAULT 0,
        status                   TEXT NOT NULL DEFAULT 'ACTIVE',
        visible_to_partner       INTEGER NOT NULL DEFAULT 1,
        uploaded_by              TEXT DEFAULT '',
        uploaded_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cancelled_by             TEXT DEFAULT '',
        cancelled_at             TIMESTAMP,
        cancellation_reason      TEXT DEFAULT '',
        replaced_by_document_id  INTEGER,
        notes                    TEXT DEFAULT '',
        created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS hostel_audit (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type              TEXT NOT NULL DEFAULT '',
        entity_id                INTEGER NOT NULL DEFAULT 0,
        partner_id               INTEGER NOT NULL DEFAULT 0,
        nurse_registration_id    INTEGER NOT NULL DEFAULT 0,
        actor_type               TEXT NOT NULL DEFAULT 'STAFF',
        actor                    TEXT NOT NULL DEFAULT '',
        event_type               TEXT NOT NULL DEFAULT '',
        old_value                TEXT DEFAULT '',
        new_value                TEXT DEFAULT '',
        note                     TEXT DEFAULT '',
        ip                       TEXT DEFAULT '',
        created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS hostel_ref_counter (
        year     INTEGER PRIMARY KEY,
        next_seq INTEGER NOT NULL DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_hostel_assign_nurse ON hostel_assignments(nurse_registration_id);
    CREATE INDEX IF NOT EXISTS idx_hostel_assign_partner ON hostel_assignments(partner_id);
    CREATE INDEX IF NOT EXISTS idx_hostel_assign_status ON hostel_assignments(status);
    CREATE INDEX IF NOT EXISTS idx_hostel_assign_passport ON hostel_assignments(passport_number);
    CREATE INDEX IF NOT EXISTS idx_hostel_agreement_assignment ON hostel_agreements(assignment_id);
    CREATE INDEX IF NOT EXISTS idx_hostel_agreement_partner ON hostel_agreements(partner_id);
    CREATE INDEX IF NOT EXISTS idx_hostel_agreement_status ON hostel_agreements(status);
    CREATE INDEX IF NOT EXISTS idx_hostel_audit_entity ON hostel_audit(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_hostel_audit_partner ON hostel_audit(partner_id);
    CREATE INDEX IF NOT EXISTS idx_hostel_audit_created ON hostel_audit(created_at);
    CREATE INDEX IF NOT EXISTS idx_hostel_partner_users_partner ON hostel_partner_users(partner_id);
    """)

    # Seed the first hostel partner: AJA Care.
    row = db.execute("SELECT id FROM hostel_partners WHERE partner_code = 'AJA_CARE'").fetchone()
    if not row:
        db.execute(
            """INSERT INTO hostel_partners
               (partner_code, partner_name, display_name, status, created_by, notes)
               VALUES ('AJA_CARE', 'AJA Care', 'AJA Care Hostel', 'ACTIVE', 'system',
                       'Seeded automatically as the first nurse accommodation partner.')"""
        )
        db.execute(
            """INSERT INTO hostel_audit (entity_type, entity_id, actor_type, actor, event_type, note)
               VALUES ('partner', (SELECT id FROM hostel_partners WHERE partner_code='AJA_CARE'),
                       'SYSTEM', 'system', 'partner_created', 'AJA Care seeded by schema bootstrap')"""
        )
    db.commit()
