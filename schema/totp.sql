-- TOTP 2FA schema for Embassy / Community Welfare Portal.
-- Idempotent. Safe to run on every server startup.
-- Phase 0: tables exist but no flow uses them yet.
-- Run via init_db() in server.py:
--     db.executescript(open('schema/totp.sql').read())

-- ─────────────────────────────────────────────────────────────────
-- 1) Per-user TOTP secret + state.
-- One row per user once enrollment begins (enabled=0 until confirmed).
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_totp (
    user_id              INTEGER PRIMARY KEY,
    secret_encrypted     TEXT    NOT NULL,            -- Fernet ciphertext of base32 secret
    enabled              INTEGER NOT NULL DEFAULT 0,  -- 1 only after first successful verification
    confirmed_at         TEXT,                        -- ISO8601 when activated
    last_used_at         TEXT,                        -- ISO8601 of last successful verify
    last_used_counter    INTEGER,                     -- replay protection: last accepted TOTP step
    failed_attempts      INTEGER NOT NULL DEFAULT 0,  -- consecutive wrong codes
    locked_until         TEXT,                        -- ISO8601, NULL when not locked
    created_at           TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ─────────────────────────────────────────────────────────────────
-- 2) Backup recovery codes.
-- 10 codes per user. Stored as sha256(user_id || ":" || code).
-- Single use: used_at is set on consumption.
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_backup_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    code_hash   TEXT    NOT NULL,
    used_at     TEXT,                                 -- NULL until consumed
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_backup_codes_user ON user_backup_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_backup_codes_hash ON user_backup_codes(code_hash);

-- ─────────────────────────────────────────────────────────────────
-- 3) Verification attempt log.
-- Used by rate limiter; small enough to keep indefinitely for forensics.
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auth_2fa_attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    ip           TEXT,
    success      INTEGER NOT NULL,
    attempted_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_2fa_attempts_user_time
    ON auth_2fa_attempts(user_id, attempted_at);
CREATE INDEX IF NOT EXISTS idx_2fa_attempts_ip_time
    ON auth_2fa_attempts(ip, attempted_at);
