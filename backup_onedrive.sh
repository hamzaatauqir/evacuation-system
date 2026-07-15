#!/usr/bin/env bash
# ============================================================
# OneDrive Backup Script
# Citizen Support for Transit KSA System
# Embassy of Pakistan, Kuwait
#
# Usage: ./backup_onedrive.sh
# Cron:  0 */6 * * * /data/backup_onedrive.sh >> /data/backup_onedrive.log 2>&1
#
# Verified against: server-5.py (6674 lines, single-file portal)
# Database: SQLite 3 with WAL journal mode
# DB path (Render): /data/evacuation.db
# DB path (local):  ./evacuation.db
# No file uploads on disk — all data lives inside the DB,
# EXCEPT advertisement images (ad_uploads/), backed up additively
# in Step 3b below; their failure never affects the DB backup.
# ============================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────
# Auto-detect: use /data/ on Render, fallback to script directory locally
if [ -d "/data" ] && [ -f "/data/evacuation.db" ]; then
    DB_PATH="/data/evacuation.db"
    BACKUP_DIR="/data/backups"
    LOG_FILE="/data/backup_onedrive.log"
elif [ -f "$(dirname "$0")/evacuation.db" ]; then
    DB_PATH="$(dirname "$0")/evacuation.db"
    BACKUP_DIR="$(dirname "$0")/backups"
    LOG_FILE="$(dirname "$0")/backup_onedrive.log"
else
    echo "FATAL: Cannot find evacuation.db in /data/ or script directory"
    exit 1
fi

RCLONE_REMOTE="onedrive"
ONEDRIVE_FOLDER="PortalBackups"
DATE_FOLDER=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="evacuation_${TIMESTAMP}_onedrive.db"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Encryption — set BACKUP_ENCRYPTION_KEY env var to enable
ENCRYPT_BACKUPS="yes"
GPG_PASSPHRASE="${BACKUP_ENCRYPTION_KEY:-}"

# Retention: keep last N days of OneDrive backups
RETENTION_DAYS=30

# ── Functions ──────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

die() {
    log "FATAL: $1"
    exit 1
}

# ── Pre-checks ─────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    die "Database not found at $DB_PATH"
fi

if ! command -v rclone &> /dev/null; then
    die "rclone is not installed"
fi

if ! command -v sqlite3 &> /dev/null; then
    die "sqlite3 CLI is not installed"
fi

# ── Step 1: Create safe SQLite backup ──────────────────────
log "Starting backup..."
log "Creating SQLite backup: $BACKUP_FILENAME"
log "Source database: $DB_PATH"

# Check if WAL files exist (server uses PRAGMA journal_mode=WAL)
if [ -f "${DB_PATH}-wal" ]; then
    WAL_SIZE=$(stat -c%s "${DB_PATH}-wal" 2>/dev/null || stat -f%z "${DB_PATH}-wal" 2>/dev/null || echo "unknown")
    log "WAL file detected (${WAL_SIZE} bytes) — .backup command will include uncommitted WAL data"
fi

# Use SQLite's .backup command — this is safe because:
# 1. It acquires a shared lock (reads can continue)
# 2. It reads the WAL file and includes any uncommitted data
# 3. The output is a single self-contained .db file (no WAL/SHM needed)
# 4. This matches how the portal's own do_backup() works (Python sqlite3.backup)
sqlite3 "$DB_PATH" ".backup '${BACKUP_PATH}'"

if [ ! -f "$BACKUP_PATH" ]; then
    die "Backup file was not created"
fi

BACKUP_SIZE=$(stat -c%s "$BACKUP_PATH" 2>/dev/null || stat -f%z "$BACKUP_PATH" 2>/dev/null)
log "Backup created: ${BACKUP_FILENAME} (${BACKUP_SIZE} bytes)"

# Verify the backup is a valid SQLite database
INTEGRITY=$(sqlite3 "$BACKUP_PATH" "PRAGMA integrity_check;" 2>&1)
if echo "$INTEGRITY" | grep -q "^ok$"; then
    log "Backup integrity check: PASSED"
else
    die "Backup integrity check FAILED: ${INTEGRITY}"
fi

# Quick data verification — count records in key tables
EVACUEE_COUNT=$(sqlite3 "$BACKUP_PATH" "SELECT COUNT(*) FROM evacuees;" 2>/dev/null || echo "?")
USER_COUNT=$(sqlite3 "$BACKUP_PATH" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "?")
AUDIT_COUNT=$(sqlite3 "$BACKUP_PATH" "SELECT COUNT(*) FROM audit_log;" 2>/dev/null || echo "?")
log "Data check: ${EVACUEE_COUNT} evacuees, ${USER_COUNT} users, ${AUDIT_COUNT} audit entries"

# ── Step 2: Encrypt backup (optional) ─────────────────────
UPLOAD_FILE="$BACKUP_PATH"
UPLOAD_FILENAME="$BACKUP_FILENAME"

if [ "$ENCRYPT_BACKUPS" = "yes" ]; then
    if [ -z "$GPG_PASSPHRASE" ]; then
        log "WARNING: ENCRYPT_BACKUPS=yes but BACKUP_ENCRYPTION_KEY env var not set. Uploading unencrypted."
    else
        ENCRYPTED_PATH="${BACKUP_PATH}.gpg"
        echo "$GPG_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 \
            --symmetric --cipher-algo AES256 \
            --output "$ENCRYPTED_PATH" "$BACKUP_PATH" 2>>"$LOG_FILE"
        if [ -f "$ENCRYPTED_PATH" ]; then
            UPLOAD_FILE="$ENCRYPTED_PATH"
            UPLOAD_FILENAME="${BACKUP_FILENAME}.gpg"
            ENC_SIZE=$(stat -c%s "$ENCRYPTED_PATH" 2>/dev/null || stat -f%z "$ENCRYPTED_PATH" 2>/dev/null)
            log "Backup encrypted: ${UPLOAD_FILENAME} (${ENC_SIZE} bytes)"
            # Remove the unencrypted local copy now that encrypted version exists
            rm -f "$BACKUP_PATH"
            log "Removed unencrypted local copy"
        else
            log "WARNING: Encryption failed, uploading unencrypted backup"
        fi
    fi
fi

# ── Step 3: Upload to OneDrive ─────────────────────────────
REMOTE_PATH="${RCLONE_REMOTE}:${ONEDRIVE_FOLDER}/${DATE_FOLDER}"
log "Uploading to OneDrive: ${REMOTE_PATH}/${UPLOAD_FILENAME}"

if rclone copy "$UPLOAD_FILE" "$REMOTE_PATH" \
    --log-file="$LOG_FILE" \
    --log-level INFO \
    --retries 3 \
    --retries-sleep 10s \
    --timeout 300s; then
    log "Upload SUCCESS: ${UPLOAD_FILENAME} → ${REMOTE_PATH}/"
else
    die "Upload FAILED — check network and rclone config"
fi

# Also keep a copy in "latest" folder for quick recovery
# This overwrites the previous latest — always the same (encrypted or unencrypted) version
rclone copy "$UPLOAD_FILE" "${RCLONE_REMOTE}:${ONEDRIVE_FOLDER}/latest" \
    --log-file="$LOG_FILE" --log-level INFO --retries 3 2>/dev/null || \
    log "WARNING: Failed to update latest folder (non-critical)"
log "Latest copy updated"

# ── Step 3b: Advertisement images (additive, best-effort) ─────
# The Website Advertisements module stores admin-uploaded homepage images
# on disk (ad_uploads/), outside the SQLite DB. Archive and upload them
# alongside the DB backup. Every failure here is a WARNING only — the DB
# backup above has already completed and is never affected by this step.
AD_UPLOADS_DIR=""
if [ -d "/data/ad_uploads" ]; then
    AD_UPLOADS_DIR="/data/ad_uploads"
elif [ -d "$(dirname "$0")/ad_uploads" ]; then
    AD_UPLOADS_DIR="$(dirname "$0")/ad_uploads"
fi
if [ -n "$AD_UPLOADS_DIR" ] && [ -n "$(ls -A "$AD_UPLOADS_DIR" 2>/dev/null || true)" ]; then
    AD_ARCHIVE="${BACKUP_DIR}/ad_uploads_${TIMESTAMP}.tar.gz"
    if tar -czf "$AD_ARCHIVE" -C "$(dirname "$AD_UPLOADS_DIR")" "$(basename "$AD_UPLOADS_DIR")" 2>>"$LOG_FILE"; then
        AD_SIZE=$(stat -c%s "$AD_ARCHIVE" 2>/dev/null || stat -f%z "$AD_ARCHIVE" 2>/dev/null || echo "?")
        if rclone copy "$AD_ARCHIVE" "$REMOTE_PATH" \
            --log-file="$LOG_FILE" --log-level INFO --retries 3 2>/dev/null; then
            log "Ad images backup uploaded: $(basename "$AD_ARCHIVE") (${AD_SIZE} bytes)"
        else
            log "WARNING: Ad images upload failed (non-critical; DB backup unaffected)"
        fi
        # Keep only the 5 most recent local ad-image archives
        ls -1t "${BACKUP_DIR}"/ad_uploads_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    else
        log "WARNING: Ad images archive failed (non-critical; DB backup unaffected)"
    fi
else
    log "No advertisement images to back up (ad_uploads absent or empty)"
fi

# ── Step 4: Clean up old local backups (keep last 20) ──────
# The portal's own do_backup() also cleans its backups (keeps 50),
# so we only clean our *_onedrive.* files separately
LOCAL_ONEDRIVE_BACKUPS=$(ls -1t "${BACKUP_DIR}"/evacuation_*_onedrive.db* 2>/dev/null || true)
LOCAL_COUNT=$(echo "$LOCAL_ONEDRIVE_BACKUPS" | grep -c "." 2>/dev/null || echo "0")
if [ "$LOCAL_COUNT" -gt 20 ]; then
    echo "$LOCAL_ONEDRIVE_BACKUPS" | tail -n +21 | xargs rm -f 2>/dev/null
    log "Cleaned old local OneDrive backups (kept 20)"
fi

# ── Step 5: Clean up old OneDrive backups ──────────────────
CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y-%m-%d 2>/dev/null || \
              date -v-${RETENTION_DAYS}d +%Y-%m-%d 2>/dev/null || echo "")

if [ -n "$CUTOFF_DATE" ]; then
    log "Checking for OneDrive folders older than ${RETENTION_DAYS} days (before ${CUTOFF_DATE})..."
    rclone lsd "${RCLONE_REMOTE}:${ONEDRIVE_FOLDER}/" 2>/dev/null | \
        awk '{print $NF}' | \
        while read -r folder; do
            if [[ "$folder" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && [[ "$folder" < "$CUTOFF_DATE" ]]; then
                log "Removing old backup folder: ${folder}"
                rclone purge "${RCLONE_REMOTE}:${ONEDRIVE_FOLDER}/${folder}" 2>/dev/null || true
            fi
        done
    log "OneDrive retention cleanup complete"
fi

# ── Done ───────────────────────────────────────────────────
log "============ BACKUP COMPLETE ============"
log "  Database: ${DB_PATH}"
log "  Local: ${UPLOAD_FILE}"
log "  OneDrive: ${REMOTE_PATH}/${UPLOAD_FILENAME}"
log "  Size: ${BACKUP_SIZE} bytes"
log "  Encrypted: ${ENCRYPT_BACKUPS}"
log "  Records: ${EVACUEE_COUNT} evacuees"
log "========================================="
