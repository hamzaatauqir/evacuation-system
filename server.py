#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVACUATION MANAGEMENT SYSTEM - Pakistan Embassy Kuwait
Zero-dependency Python server (stdlib only). Run: python3 server.py
Access: http://localhost:8080
Default login: admin / embassy2026
"""

import http.server, sqlite3, json, hashlib, uuid, csv, io, os, re, time, secrets, shutil, threading
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timedelta
from pathlib import Path

PORT = int(os.environ.get('PORT', 8080))

# Use /data/ for persistent Render Disk, fallback to local directory for development
RENDER_DISK = Path('/data')
if RENDER_DISK.exists() and RENDER_DISK.is_dir():
    DB_PATH = RENDER_DISK / 'evacuation.db'
    BACKUP_DIR = RENDER_DISK / 'backups'
else:
    DB_PATH = Path(__file__).parent / 'evacuation.db'
    BACKUP_DIR = Path(__file__).parent / 'backups'
SESSIONS = {}  # token -> {user, role, expires}

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'operator',
        full_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS evacuees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        passport TEXT,
        cnic TEXT,
        gender TEXT,
        country TEXT,
        civil_id TEXT,
        border_crossing TEXT,
        mobile TEXT,
        company TEXT,
        visa_status TEXT DEFAULT 'Pending',
        travel_status TEXT DEFAULT 'Pending',
        airline TEXT,
        ticket_number TEXT,
        departure_airport TEXT,
        destination_country TEXT,
        date_of_request TEXT,
        email TEXT,
        dob TEXT,
        emergency_contact TEXT,
        medical TEXT,
        family_group_id TEXT,
        dependents INTEGER DEFAULT 0,
        accommodation TEXT,
        priority TEXT DEFAULT 'Normal',
        remarks TEXT,
        planned_departure TEXT,
        saudi_city TEXT,
        traveling_with_family TEXT DEFAULT 'No',
        confirm_ksa_3days TEXT DEFAULT 'No',
        mofa_status TEXT DEFAULT '',
        dup_flag TEXT DEFAULT 'CLEAR',
        form_submission_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_by TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        record_id INTEGER,
        user TEXT,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_passport ON evacuees(passport);
    CREATE INDEX IF NOT EXISTS idx_cnic ON evacuees(cnic);
    CREATE INDEX IF NOT EXISTS idx_travel_status ON evacuees(travel_status);
    CREATE INDEX IF NOT EXISTS idx_name ON evacuees(name);
    """)
    # Default admin user
    pw_hash = hashlib.sha256('embassy2026'.encode()).hexdigest()
    try:
        db.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, 'admin', 'Administrator')", ('admin', pw_hash))
        db.commit()
    except sqlite3.IntegrityError:
        pass
    # Migrate: add new columns if they don't exist
    for col, coltype in [('planned_departure', 'TEXT'), ('saudi_city', 'TEXT'),
                         ('traveling_with_family', "TEXT DEFAULT 'No'"), ('confirm_ksa_3days', "TEXT DEFAULT 'No'"),
                         ('mofa_status', "TEXT DEFAULT ''")]:
        try:
            db.execute(f"ALTER TABLE evacuees ADD COLUMN {col} {coltype}")
            db.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    db.close()

# ═══════════════════════════════════════════════════════════════
# BACKUP SYSTEM
# ═══════════════════════════════════════════════════════════════
def do_backup(reason='scheduled'):
    """Create a timestamped backup of the database"""
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f'evacuation_{ts}_{reason}.db'
    try:
        # Use SQLite's built-in backup (safe even while server is running)
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(str(backup_path))
        src.backup(dst)
        dst.close()
        src.close()
        # Keep only last 50 backups
        backups = sorted(BACKUP_DIR.glob('*.db'), key=lambda p: p.stat().st_mtime)
        while len(backups) > 50:
            backups.pop(0).unlink()
        return str(backup_path)
    except Exception as e:
        return f"Backup failed: {e}"

def list_backups():
    BACKUP_DIR.mkdir(exist_ok=True)
    backups = sorted(BACKUP_DIR.glob('*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{'name': b.name, 'size': b.stat().st_size, 'date': datetime.fromtimestamp(b.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')} for b in backups[:20]]

def restore_backup(backup_name):
    backup_path = BACKUP_DIR / backup_name
    if not backup_path.exists():
        return {'success': False, 'error': 'Backup not found'}
    # Backup current before restoring
    do_backup('pre_restore')
    try:
        src = sqlite3.connect(str(backup_path))
        dst = sqlite3.connect(str(DB_PATH))
        src.backup(dst)
        dst.close()
        src.close()
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def auto_backup_scheduler():
    """Run automatic backup every 2 hours"""
    while True:
        time.sleep(7200)  # 2 hours
        try:
            do_backup('auto')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-backup completed")
        except: pass

# ═══════════════════════════════════════════════════════════════
# WORKFLOW ENGINE — Automatic Status Transitions
# ═══════════════════════════════════════════════════════════════
def apply_workflow_rules(db, record_id, field_changed, new_value, user='system'):
    """
    Automatic status transitions:
    1. visa_status → 'Approved'  ⇒  travel_status auto-set to 'Visa Obtained'
    2. ticket_number is filled   ⇒  travel_status auto-set to 'Departed' (if visa approved)
    3. airline is filled         ⇒  (same as ticket, helps catch partial updates)
    """
    changes = []
    rec = dict(db.execute("SELECT * FROM evacuees WHERE id = ?", [record_id]).fetchone())

    # Rule 1: Visa approved → move to "Visa Obtained"
    if field_changed == 'visa_status' and new_value == 'Approved':
        if rec['travel_status'] == 'Pending':
            db.execute("UPDATE evacuees SET travel_status = 'Visa Obtained', updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE id = ?", [user, record_id])
            changes.append('Travel status auto-updated: Pending → Visa Obtained (visa approved)')

    # Rule 2: Ticket number entered → move to "Departed" (if visa is approved)
    if field_changed == 'ticket_number' and new_value and new_value.strip() not in ['', '-', 'Transit']:
        if rec['visa_status'] == 'Approved' and rec['travel_status'] in ('Visa Obtained', 'Pending'):
            db.execute("UPDATE evacuees SET travel_status = 'Departed', updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE id = ?", [user, record_id])
            changes.append(f'Travel status auto-updated: {rec["travel_status"]} → Departed (ticket entered)')

    # Rule 3: Visa rejected → keep pending but add flag
    if field_changed == 'visa_status' and new_value == 'Rejected':
        if rec['travel_status'] == 'Visa Obtained':
            db.execute("UPDATE evacuees SET travel_status = 'Pending', updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE id = ?", [user, record_id])
            changes.append('Travel status auto-updated: Visa Obtained → Pending (visa rejected)')

    # Log workflow actions
    for change in changes:
        db.execute("INSERT INTO audit_log (action, record_id, user, details) VALUES ('workflow', ?, ?, ?)",
                   (record_id, user, change))

    return changes

def bulk_update_visa_status(passport_list, new_status, user='system'):
    """
    Bulk update visa status for a list of passport numbers.
    Used when you receive a batch of visa approvals from KSA.
    """
    db = get_db()
    results = {'updated': 0, 'not_found': 0, 'workflow_changes': [], 'details': []}
    for pp in passport_list:
        pp = pp.strip().upper()
        if not pp: continue
        rec = db.execute("SELECT id, name, visa_status, travel_status FROM evacuees WHERE UPPER(TRIM(passport)) = ?", [pp]).fetchone()
        if rec:
            db.execute("UPDATE evacuees SET visa_status = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE id = ?",
                       [new_status, user, rec['id']])
            workflow = apply_workflow_rules(db, rec['id'], 'visa_status', new_status, user)
            results['updated'] += 1
            results['details'].append(f"{rec['name']} ({pp}): visa → {new_status}" + (f" | {'; '.join(workflow)}" if workflow else ""))
            results['workflow_changes'].extend(workflow)
        else:
            results['not_found'] += 1
            results['details'].append(f"Passport {pp}: NOT FOUND in system")

    db.commit()
    db.execute("INSERT INTO audit_log (action, user, details) VALUES ('bulk_visa_update', ?, ?)",
               (user, json.dumps(results)))
    db.commit()
    db.close()
    return results

# ═══════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def create_session(username, role):
    token = secrets.token_hex(32)
    SESSIONS[token] = {'user': username, 'role': role, 'expires': time.time() + 86400}
    return token

def get_session(cookie_str):
    if not cookie_str: return None
    c = SimpleCookie()
    c.load(cookie_str)
    token = c.get('session')
    if not token: return None
    s = SESSIONS.get(token.value)
    if s and s['expires'] > time.time(): return s
    return None

# ═══════════════════════════════════════════════════════════════
# DUPLICATE DETECTION
# ═══════════════════════════════════════════════════════════════
def check_duplicates(db, record, exclude_id=None):
    flags = []
    passport = (record.get('passport') or '').strip().upper()
    cnic = re.sub(r'[\s\-]', '', record.get('cnic') or '')
    name = (record.get('name') or '').strip().lower()

    if passport:
        q = "SELECT id, name FROM evacuees WHERE UPPER(TRIM(passport)) = ?"
        params = [passport]
        if exclude_id: q += " AND id != ?"; params.append(exclude_id)
        dup = db.execute(q, params).fetchone()
        if dup: flags.append(f"Passport match with #{dup['id']} ({dup['name']})")

    if cnic:
        q = "SELECT id, name FROM evacuees WHERE REPLACE(REPLACE(cnic, '-', ''), ' ', '') = ?"
        params = [cnic]
        if exclude_id: q += " AND id != ?"; params.append(exclude_id)
        dup = db.execute(q, params).fetchone()
        if dup: flags.append(f"CNIC match with #{dup['id']} ({dup['name']})")

    if name and len(name) > 3:
        q = "SELECT id, name FROM evacuees WHERE LOWER(TRIM(name)) = ?"
        params = [name]
        if exclude_id: q += " AND id != ?"; params.append(exclude_id)
        dup = db.execute(q, params).fetchone()
        if dup: flags.append(f"Name match with #{dup['id']} ({dup['name']})")

    return flags

# ═══════════════════════════════════════════════════════════════
# CSV IMPORT WITH SMART DEDUP
# ═══════════════════════════════════════════════════════════════
def import_csv_data(csv_text, user='system', mode='smart'):
    """mode: 'smart' = skip exact dups, update partial matches; 'force' = import all; 'skip' = skip all dups"""
    db = get_db()
    reader = csv.DictReader(io.StringIO(csv_text))
    headers_raw = reader.fieldnames or []

    # Map MS Forms / Google Forms headers to our DB fields
    header_map = {}
    for h in headers_raw:
        hl = h.lower().strip()
        if 'full name' in hl or (hl == 'name' and 'full' not in ''.join(headers_raw).lower()):
            header_map[h] = 'name'
        elif 'passport' in hl: header_map[h] = 'passport'
        elif 'gender' in hl: header_map[h] = 'gender'
        elif 'country' in hl or 'resident' in hl: header_map[h] = 'country'
        elif 'civil id' in hl or 'kuwaiti' in hl: header_map[h] = 'civil_id'
        elif 'border' in hl or 'crossing' in hl: header_map[h] = 'border_crossing'
        elif 'mobile' in hl or 'phone' in hl: header_map[h] = 'mobile'
        elif 'profession' in hl or 'company' in hl: header_map[h] = 'company'
        elif 'cnic' in hl: header_map[h] = 'cnic'
        elif 'email' in hl and 'address' in hl: header_map[h] = 'email'
        elif hl == 'email': pass  # skip the MS Forms system email
        elif 'start time' in hl or 'completion' in hl: header_map[h] = 'date_of_request'
        elif hl == 'id': header_map[h] = 'form_submission_id'
        elif 'visa' in hl and 'status' in hl: header_map[h] = 'visa_status'
        elif 'travel' in hl and 'status' in hl: header_map[h] = 'travel_status'
        elif 'airline' in hl: header_map[h] = 'airline'
        elif 'ticket' in hl: header_map[h] = 'ticket_number'
        elif 'departure' in hl or 'airport' in hl: header_map[h] = 'departure_airport'
        elif 'destination' in hl: header_map[h] = 'destination_country'
        elif 'priority' in hl: header_map[h] = 'priority'
        elif 'remark' in hl or 'note' in hl: header_map[h] = 'remarks'

    stats = {'imported': 0, 'skipped_dup': 0, 'updated': 0, 'errors': 0, 'details': []}

    for row_num, row in enumerate(reader, 1):
        try:
            rec = {}
            for orig_h, db_field in header_map.items():
                val = (row.get(orig_h) or '').strip()
                if val: rec[db_field] = val

            if not rec.get('name'):
                stats['errors'] += 1
                stats['details'].append(f"Row {row_num}: No name found, skipped")
                continue

            # Clean up data
            if rec.get('cnic'):
                rec['cnic'] = re.sub(r'[\s]', '', rec['cnic'])
            if rec.get('passport'):
                rec['passport'] = rec['passport'].strip().upper()
            if rec.get('date_of_request'):
                # Parse MS Forms date format
                try:
                    dt = datetime.strptime(rec['date_of_request'].split('.')[0], '%m/%d/%Y %H:%M')
                    rec['date_of_request'] = dt.strftime('%Y-%m-%d')
                except: pass

            # Check for duplicate by passport
            passport = rec.get('passport', '')
            existing = None
            if passport:
                existing = db.execute("SELECT id, name, travel_status, visa_status FROM evacuees WHERE UPPER(TRIM(passport)) = ?", [passport.upper()]).fetchone()

            if existing:
                if mode == 'skip':
                    stats['skipped_dup'] += 1
                    stats['details'].append(f"Row {row_num}: {rec['name']} — duplicate passport {passport}, skipped")
                    continue
                elif mode == 'smart':
                    # Update only empty fields in existing record
                    updates = []
                    params = []
                    for field in ['mobile', 'civil_id', 'cnic', 'email', 'company', 'border_crossing']:
                        if rec.get(field):
                            updates.append(f"{field} = COALESCE(NULLIF({field}, ''), ?)")
                            params.append(rec[field])
                    if updates:
                        params.append(existing['id'])
                        db.execute(f"UPDATE evacuees SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE id = ?",
                                   params[:-1] + [user, existing['id']])
                        stats['updated'] += 1
                        stats['details'].append(f"Row {row_num}: {rec['name']} — updated existing record #{existing['id']}")
                    else:
                        stats['skipped_dup'] += 1
                        stats['details'].append(f"Row {row_num}: {rec['name']} — exact duplicate, skipped")
                    continue
                # mode == 'force' falls through to insert

            # Check for duplicates and flag
            dup_flags = check_duplicates(db, rec)
            rec['dup_flag'] = 'DUPLICATE' if dup_flags else 'CLEAR'

            # Insert
            fields = [k for k in rec.keys() if k in (
                'name','passport','cnic','gender','country','civil_id','border_crossing',
                'mobile','company','visa_status','travel_status','airline','ticket_number',
                'departure_airport','destination_country','date_of_request','email',
                'dob','emergency_contact','medical','family_group_id','dependents',
                'accommodation','priority','remarks','planned_departure','saudi_city',
                'traveling_with_family','confirm_ksa_3days','dup_flag','form_submission_id'
            )]
            if 'travel_status' not in fields:
                fields.append('travel_status')
                rec['travel_status'] = 'Pending'

            placeholders = ', '.join(['?'] * len(fields))
            db.execute(
                f"INSERT INTO evacuees ({', '.join(fields)}) VALUES ({placeholders})",
                [rec.get(f, '') for f in fields]
            )
            stats['imported'] += 1
            if rec['dup_flag'] == 'DUPLICATE':
                stats['details'].append(f"Row {row_num}: {rec['name']} — imported with DUPLICATE flag ({'; '.join(dup_flags)})")
            else:
                stats['details'].append(f"Row {row_num}: {rec['name']} — imported OK")

        except Exception as e:
            stats['errors'] += 1
            stats['details'].append(f"Row {row_num}: Error — {str(e)}")

    db.commit()
    db.execute("INSERT INTO audit_log (action, user, details) VALUES (?, ?, ?)",
               ('csv_import', user, json.dumps(stats)))
    db.commit()
    db.close()
    return stats

# ═══════════════════════════════════════════════════════════════
# API HANDLERS
# ═══════════════════════════════════════════════════════════════
def api_dashboard_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM evacuees").fetchone()['c']
    departed = db.execute("SELECT COUNT(*) c FROM evacuees WHERE travel_status='Departed'").fetchone()['c']
    visa_obtained = db.execute("SELECT COUNT(*) c FROM evacuees WHERE travel_status='Visa Obtained'").fetchone()['c']
    pending = db.execute("SELECT COUNT(*) c FROM evacuees WHERE travel_status='Pending' AND dup_flag='CLEAR'").fetchone()['c']
    visa_approved = db.execute("SELECT COUNT(*) c FROM evacuees WHERE visa_status='Approved'").fetchone()['c']
    iraq_entries = db.execute("SELECT COUNT(*) c FROM evacuees WHERE country='Iraq'").fetchone()['c']

    by_country = [dict(r) for r in db.execute("""
        SELECT country, COUNT(*) total,
        SUM(CASE WHEN travel_status='Departed' THEN 1 ELSE 0 END) departed,
        SUM(CASE WHEN travel_status='Visa Obtained' THEN 1 ELSE 0 END) visa_obtained,
        SUM(CASE WHEN travel_status='Pending' THEN 1 ELSE 0 END) pending,
        SUM(CASE WHEN gender='Male' THEN 1 ELSE 0 END) males,
        SUM(CASE WHEN gender='Female' THEN 1 ELSE 0 END) females,
        SUM(CASE WHEN gender='Child' THEN 1 ELSE 0 END) children
        FROM evacuees GROUP BY country ORDER BY COUNT(*) DESC
    """).fetchall()]

    by_gender = [dict(r) for r in db.execute("""
        SELECT gender, COUNT(*) count,
        SUM(CASE WHEN travel_status='Departed' THEN 1 ELSE 0 END) departed
        FROM evacuees GROUP BY gender
    """).fetchall()]

    by_date = [dict(r) for r in db.execute("""
        SELECT date_of_request date, COUNT(*) new_requests,
        SUM(CASE WHEN travel_status='Departed' THEN 1 ELSE 0 END) departed,
        SUM(CASE WHEN travel_status='Visa Obtained' THEN 1 ELSE 0 END) visa_obtained,
        SUM(CASE WHEN travel_status='Pending' THEN 1 ELSE 0 END) pending
        FROM evacuees WHERE date_of_request IS NOT NULL AND date_of_request != ''
        GROUP BY date_of_request ORDER BY date_of_request
    """).fetchall()]

    by_visa = [dict(r) for r in db.execute("SELECT COALESCE(visa_status,'Not Set') status, COUNT(*) count FROM evacuees GROUP BY visa_status").fetchall()]
    by_border = [dict(r) for r in db.execute("SELECT border_crossing, COUNT(*) count FROM evacuees WHERE border_crossing != '' GROUP BY border_crossing").fetchall()]

    duplicates = db.execute("SELECT COUNT(*) c FROM evacuees WHERE dup_flag='DUPLICATE'").fetchone()['c']

    db.close()
    return {
        'kpi': {'total': total, 'departed': departed, 'visa_obtained': visa_obtained, 'pending': pending,
                'visa_approved': visa_approved, 'iraq_entries': iraq_entries, 'duplicates': duplicates},
        'by_country': by_country, 'by_gender': by_gender, 'by_date': by_date,
        'by_visa': by_visa, 'by_border': by_border
    }

def api_records(params):
    db = get_db()
    where = ["1=1"]
    qparams = []
    if params.get('search'):
        s = f"%{params['search']}%"
        where.append("(name LIKE ? OR passport LIKE ? OR cnic LIKE ? OR mobile LIKE ?)")
        qparams.extend([s, s, s, s])
    if params.get('status'):
        where.append("travel_status = ?"); qparams.append(params['status'])
    if params.get('country'):
        where.append("country = ?"); qparams.append(params['country'])
    if params.get('gender'):
        where.append("gender = ?"); qparams.append(params['gender'])
    if params.get('visa'):
        where.append("visa_status = ?"); qparams.append(params['visa'])
    if params.get('dup'):
        where.append("dup_flag = ?"); qparams.append(params['dup'])

    rows = db.execute(f"SELECT * FROM evacuees WHERE {' AND '.join(where)} ORDER BY id DESC", qparams).fetchall()
    result = [dict(r) for r in rows]
    db.close()
    return result

def api_save_record(data, user):
    db = get_db()
    rec_id = data.get('id')
    fields = ['name','passport','cnic','gender','country','civil_id','border_crossing',
              'mobile','company','visa_status','travel_status','airline','ticket_number',
              'departure_airport','destination_country','date_of_request','email',
              'dob','emergency_contact','medical','family_group_id','dependents',
              'accommodation','priority','remarks','planned_departure','saudi_city',
              'traveling_with_family','confirm_ksa_3days']

    if rec_id:  # Update
        # Get old record to detect changes
        old_rec = dict(db.execute("SELECT * FROM evacuees WHERE id = ?", [rec_id]).fetchone())

        sets = [f"{f} = ?" for f in fields]
        vals = [data.get(f, '') for f in fields]
        dup_flags = check_duplicates(db, data, exclude_id=rec_id)
        dup_flag = 'DUPLICATE' if dup_flags else 'CLEAR'
        sets.append("dup_flag = ?"); vals.append(dup_flag)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        sets.append("updated_by = ?"); vals.append(user)
        vals.append(rec_id)
        db.execute(f"UPDATE evacuees SET {', '.join(sets)} WHERE id = ?", vals)
        db.execute("INSERT INTO audit_log (action, record_id, user, details) VALUES ('update', ?, ?, ?)",
                   (rec_id, user, json.dumps(data)))

        # Apply workflow rules for changed fields
        workflow_changes = []
        for field in ['visa_status', 'ticket_number']:
            old_val = old_rec.get(field, '')
            new_val = data.get(field, '')
            if old_val != new_val:
                wf = apply_workflow_rules(db, rec_id, field, new_val, user)
                workflow_changes.extend(wf)

        db.commit(); db.close()
        return {'success': True, 'id': rec_id, 'dup_flag': dup_flag, 'dup_details': dup_flags, 'workflow': workflow_changes}
    else:  # Insert
        if not data.get('date_of_request'):
            data['date_of_request'] = datetime.now().strftime('%Y-%m-%d')
        dup_flags = check_duplicates(db, data)
        dup_flag = 'DUPLICATE' if dup_flags else 'CLEAR'
        vals = [data.get(f, '') for f in fields] + [dup_flag]
        placeholders = ', '.join(['?'] * (len(fields) + 1))
        cur = db.execute(f"INSERT INTO evacuees ({', '.join(fields)}, dup_flag) VALUES ({placeholders})", vals)
        new_id = cur.lastrowid
        db.execute("INSERT INTO audit_log (action, record_id, user, details) VALUES ('create', ?, ?, ?)",
                   (new_id, user, json.dumps(data)))
        db.commit(); db.close()
        return {'success': True, 'id': new_id, 'dup_flag': dup_flag, 'dup_details': dup_flags}

def api_delete_record(rec_id, user):
    db = get_db()
    db.execute("DELETE FROM evacuees WHERE id = ?", [rec_id])
    db.execute("INSERT INTO audit_log (action, record_id, user) VALUES ('delete', ?, ?)", (rec_id, user))
    db.commit(); db.close()
    return {'success': True}

def api_users_list():
    db = get_db()
    users = [dict(r) for r in db.execute("SELECT id, username, role, full_name, created_at FROM users").fetchall()]
    db.close()
    return users

def api_create_user(data):
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                   (data['username'], hash_pw(data['password']), data.get('role', 'operator'), data.get('full_name', '')))
        db.commit(); db.close()
        return {'success': True}
    except sqlite3.IntegrityError:
        db.close()
        return {'success': False, 'error': 'Username already exists'}

def api_export_csv():
    db = get_db()
    rows = db.execute("SELECT * FROM evacuees ORDER BY id").fetchall()
    db.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['S.No','Name','Passport','CNIC','Gender','Country','Civil ID','Border Crossing',
                     'Mobile','Company','Visa Status','Travel Status','Airline','Ticket Number',
                     'Departure Airport','Destination Country','Date of Request','Email','DOB',
                     'Emergency Contact','Medical','Family Group','Dependents','Accommodation',
                     'Priority','Remarks','Planned Departure','Saudi City',
                     'Traveling with Family','Confirm KSA 3-Days','Duplicate Flag','Created At'])
    def safe_get(row, key, default=''):
        try:
            return row[key]
        except (IndexError, KeyError):
            return default
    for i, r in enumerate(rows, 1):
        writer.writerow([i, r['name'], r['passport'], r['cnic'], r['gender'], r['country'],
                        r['civil_id'], r['border_crossing'], r['mobile'], r['company'],
                        r['visa_status'], r['travel_status'], r['airline'], r['ticket_number'],
                        r['departure_airport'], r['destination_country'], r['date_of_request'],
                        r['email'], r['dob'], r['emergency_contact'], r['medical'],
                        r['family_group_id'], r['dependents'], r['accommodation'],
                        r['priority'], r['remarks'],
                        safe_get(r,'planned_departure'), safe_get(r,'saudi_city'),
                        safe_get(r,'traveling_with_family'), safe_get(r,'confirm_ksa_3days'),
                        r['dup_flag'], r['created_at']])
    return output.getvalue()

def api_audit_log():
    db = get_db()
    logs = [dict(r) for r in db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200").fetchall()]
    db.close()
    return logs

# ═══════════════════════════════════════════════════════════════
# WORD DOCUMENT GENERATOR (pure Python, no dependencies)
# ═══════════════════════════════════════════════════════════════
def generate_sitrep_docx(data):
    """Generate a .docx file from SITREP data using pure XML (no python-docx needed)"""
    import zipfile

    def escape_xml(s):
        return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    def make_para(text, bold=False, size=22, align='left', space_after=100):
        b_xml = '<w:b/>' if bold else ''
        sz = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        jc = f'<w:jc w:val="{align}"/>' if align != 'left' else ''
        return f'<w:p><w:pPr>{jc}<w:spacing w:after="{space_after}"/><w:rPr>{b_xml}{sz}</w:rPr></w:pPr><w:r><w:rPr>{b_xml}{sz}</w:rPr><w:t xml:space="preserve">{escape_xml(text)}</w:t></w:r></w:p>'

    def make_multiline(text, bold=False, size=22):
        lines = (text or '').split('\n')
        return ''.join(make_para(line, bold, size) for line in lines)

    def make_section(num, title, content):
        return make_para(f'{num}. {title}', bold=True, size=24, space_after=60) + make_multiline(content, size=22)

    def make_table_row(cells, bold=False):
        row_xml = '<w:tr>'
        for cell in cells:
            b = '<w:b/>' if bold else ''
            row_xml += f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr><w:p><w:r><w:rPr>{b}<w:sz w:val="22"/></w:rPr><w:t xml:space="preserve">{escape_xml(cell)}</w:t></w:r></w:p></w:tc>'
        row_xml += '</w:tr>'
        return row_xml

    # Build document body
    body = ''
    body += make_para('SITUATION REPORT', bold=True, size=32, align='center', space_after=60)
    body += make_para("PAKISTAN'S MISSION IN KUWAIT", bold=True, size=26, align='center', space_after=200)

    # Header table
    body += '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders><w:top w:val="single" w:sz="4" w:color="000000"/><w:left w:val="single" w:sz="4" w:color="000000"/><w:bottom w:val="single" w:sz="4" w:color="000000"/><w:right w:val="single" w:sz="4" w:color="000000"/><w:insideH w:val="single" w:sz="4" w:color="000000"/><w:insideV w:val="single" w:sz="4" w:color="000000"/></w:tblBorders></w:tblPr>'
    body += make_table_row(['Country/Region:', data.get('country', 'Kuwait')], bold=False)
    body += make_table_row(['Date & Time of Report:', data.get('date', '')], bold=False)
    body += make_table_row(['Emergency Hotline # of Mission:', data.get('hotline', '')], bold=False)
    body += make_table_row(['Number of Stranded Pakistanis:', data.get('stranded', 'Nil')], bold=False)
    body += '</w:tbl>'
    body += make_para('', size=10)

    body += make_section('1', 'Overall Situation', data.get('situation', ''))
    body += make_para('', size=10)

    # Diaspora Profile
    body += make_para('2. Diaspora Profile', bold=True, size=24, space_after=60)
    body += '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders><w:top w:val="single" w:sz="4" w:color="000000"/><w:left w:val="single" w:sz="4" w:color="000000"/><w:bottom w:val="single" w:sz="4" w:color="000000"/><w:right w:val="single" w:sz="4" w:color="000000"/><w:insideH w:val="single" w:sz="4" w:color="000000"/><w:insideV w:val="single" w:sz="4" w:color="000000"/></w:tblBorders></w:tblPr>'
    body += make_table_row(['Estimated Number:', data.get('diaspora_num', '101,976')])
    body += make_table_row(['Key Diaspora Locations:', data.get('diaspora_loc', '')])
    body += make_table_row(['Evacuation Requested:', data.get('evac_requested', '')])
    body += make_table_row(['Number of Stranded:', data.get('stranded', 'Nil')])
    body += make_table_row(['Registered with Mission:', data.get('registered', '')])
    body += '</w:tbl>'
    body += make_para('', size=10)

    body += make_section('3', 'Airspace Status',
        f"Airspace: {data.get('airspace', '')}\nAirport Operations: {data.get('airport', '')}\nNOTAM: {data.get('notam', '')}")
    body += make_para('', size=10)

    body += make_section('4', 'Land Routes Status & Options', data.get('land', ''))
    body += make_para('', size=10)

    body += make_section('5', 'Facilitation Measures Taken by Mission', data.get('facilitation', ''))
    body += make_para('', size=10)

    body += make_section('6', 'Coordination with Host Government', data.get('coordination', ''))
    body += make_para('', size=10)

    body += make_para('7. Evacuation Options', bold=True, size=24, space_after=60)
    body += make_para('By Air:', bold=True, size=22, space_after=40)
    body += make_multiline(data.get('evac_air', ''))
    body += make_para('By Land:', bold=True, size=22, space_after=40)
    body += make_multiline(data.get('evac_land', ''))
    body += make_para('', size=10)

    body += make_section('8', 'Status of Evacuation', data.get('evac_status', ''))
    body += make_para('', size=10)

    body += make_section('9', 'Risks & Challenges', data.get('risks', ''))
    body += make_para('', size=10)

    body += make_section('10', 'Overall Assessment of the Mission', data.get('assessment', ''))

    # Build the complete OOXML document
    ns = 'xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"'

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document {ns}>
<w:body>{body}
<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
</w:body></w:document>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    word_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>'''

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels)
        zf.writestr('word/_rels/document.xml.rels', word_rels)
        zf.writestr('word/document.xml', document_xml)
    return buf.getvalue()

# ═══════════════════════════════════════════════════════════════
# HTTP SERVER
# ═══════════════════════════════════════════════════════════════
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length else b''

    def get_user(self):
        return get_session(self.headers.get('Cookie'))

    def require_auth(self):
        user = self.get_user()
        if not user:
            self.send_response(302)
            self.send_header('Location', '/login')
            self.end_headers()
            return None
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        params = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

        if path in ('/embassy-registration', '/register'):
            # Public registration page — no login needed
            db = get_db()
            enabled = db.execute("SELECT value FROM settings WHERE key='public_registration'").fetchone()
            db.close()
            if enabled and enabled['value'] == 'disabled':
                self.send_html('<html><body style="font-family:Arial;text-align:center;padding:60px"><h1>Registration Closed</h1><p>Public registration is currently closed. Please contact the Embassy directly.</p></body></html>')
            else:
                self.send_html(PUBLIC_REGISTER_PAGE)
        elif path in ('/embassy-registration/success', '/register/success'):
            self.send_html(REGISTER_SUCCESS_PAGE)
        elif path == '/login':
            self.send_html(LOGIN_PAGE)
        elif path == '/':
            user = self.require_auth()
            if not user: return
            # Inject user role into the page
            app_html = MAIN_APP.replace('__USER_ROLE__', user['role']).replace('__USER_NAME__', user['user'])
            self.send_html(app_html)
        elif path == '/api/stats':
            if not self.require_auth(): return
            self.send_json(api_dashboard_stats())
        elif path == '/api/records':
            if not self.require_auth(): return
            self.send_json(api_records(params))
        elif path == '/api/export':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Only admin can export data'}, 403); return
            csv_data = api_export_csv()
            body = csv_data.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', f'attachment; filename="evacuation_data_{datetime.now().strftime("%Y%m%d")}.csv"')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        elif path == '/api/mofa-pending':
            user = self.require_auth()
            if not user: return
            db = get_db()
            # Check if mofa_status column exists
            cols = [c[1] for c in db.execute("PRAGMA table_info(evacuees)").fetchall()]
            has_mofa = 'mofa_status' in cols
            if has_mofa:
                rows = db.execute("""SELECT id, name, passport, border_crossing, mofa_status FROM evacuees
                    WHERE travel_status='Pending' AND dup_flag='CLEAR'
                    ORDER BY id""").fetchall()
            else:
                rows = db.execute("""SELECT id, name, passport, border_crossing FROM evacuees
                    WHERE travel_status='Pending' AND dup_flag='CLEAR'
                    ORDER BY id""").fetchall()
            db.close()
            result = []
            for r in rows:
                d = dict(r)
                if not has_mofa:
                    d['mofa_status'] = ''
                else:
                    d['mofa_status'] = d.get('mofa_status', '') or ''
                result.append(d)
            self.send_json(result)
        elif path == '/api/mofa-export':
            user = self.require_auth()
            if not user: return
            from_id = int(params.get('from', 0))
            to_id = int(params.get('to', 999999))
            db = get_db()
            rows = db.execute("""SELECT id, name, passport, border_crossing FROM evacuees
                WHERE id >= ? AND id <= ? AND travel_status='Pending' AND dup_flag='CLEAR'
                ORDER BY id""", [from_id, to_id]).fetchall()
            db.close()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['S.No', 'Name', 'Passport Number', 'Border Entry Point'])
            for i, r in enumerate(rows, 1):
                writer.writerow([i, r['name'], r['passport'], r['border_crossing']])
            body = output.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="MOFA_visa_request_{datetime.now().strftime("%Y%m%d")}.csv"')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        elif path == '/api/users':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            self.send_json(api_users_list())
        elif path == '/api/audit':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            self.send_json(api_audit_log())
        elif path == '/api/backups':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            self.send_json(list_backups())
        elif path == '/logout':
            cookie_str = self.headers.get('Cookie', '')
            c = SimpleCookie(); c.load(cookie_str)
            token = c.get('session')
            if token and token.value in SESSIONS: del SESSIONS[token.value]
            self.send_response(302)
            self.send_header('Set-Cookie', 'session=; Path=/; Max-Age=0')
            self.send_header('Location', '/login')
            self.end_headers()
        # MS Forms webhook endpoint (public, uses API key)
        elif path == '/api/webhook/forms':
            api_key = params.get('key', '')
            db = get_db()
            stored_key = db.execute("SELECT value FROM settings WHERE key='webhook_key'").fetchone()
            db.close()
            if not stored_key or api_key != stored_key['value']:
                self.send_json({'error': 'Invalid API key'}, 401)
            else:
                self.send_json({'status': 'ok', 'message': 'Webhook active'})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        body = self.read_body()

        if path == '/api/public-register':
            # Public registration — no auth needed, but with spam protection
            db = get_db()
            enabled = db.execute("SELECT value FROM settings WHERE key='public_registration'").fetchone()
            if enabled and enabled['value'] == 'disabled':
                db.close()
                self.send_json({'success': False, 'error': 'Registration is currently closed'}, 403)
                return

            # Rate limiting: max 10 submissions per IP per hour
            client_ip = self.client_address[0]
            one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            recent = db.execute("SELECT COUNT(*) c FROM audit_log WHERE user = ? AND action = 'public_register' AND created_at > ?",
                               [client_ip, one_hour_ago]).fetchone()['c']
            if recent >= 10:
                db.close()
                self.send_json({'success': False, 'error': 'Too many submissions. Please try again later.'}, 429)
                return
            db.close()

            data = json.loads(body)
            # Validate required fields
            if not data.get('name') or not data.get('passport') or not data.get('mobile'):
                self.send_json({'success': False, 'error': 'Name, Passport, and Mobile are required'}, 400)
                return

            # Clean data
            data['passport'] = data['passport'].strip().upper()
            if data.get('cnic'):
                data['cnic'] = re.sub(r'[\s]', '', data['cnic'])
            if not data.get('date_of_request'):
                data['date_of_request'] = datetime.now().strftime('%Y-%m-%d')
            if not data.get('travel_status'):
                data['travel_status'] = 'Pending'

            result = api_save_record(data, 'public')
            # Log for rate limiting
            db = get_db()
            db.execute("INSERT INTO audit_log (action, record_id, user, details) VALUES ('public_register', ?, ?, ?)",
                       (result.get('id'), client_ip, json.dumps({'name': data['name'], 'passport': data['passport']})))
            db.commit()
            db.close()
            self.send_json(result)
            return

        elif path == '/api/login':
            data = json.loads(body)
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE username = ?", [data.get('username', '')]).fetchone()
            db.close()
            if user and user['password_hash'] == hash_pw(data.get('password', '')):
                token = create_session(user['username'], user['role'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400')
                resp = json.dumps({'success': True, 'user': user['username'], 'role': user['role']}).encode()
                self.send_header('Content-Length', len(resp))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_json({'success': False, 'error': 'Invalid credentials'}, 401)

        elif path == '/api/record':
            user = self.require_auth()
            if not user: return
            data = json.loads(body)
            result = api_save_record(data, user['user'])
            self.send_json(result)

        elif path == '/api/record/delete':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Only admin can delete records'}, 403); return
            data = json.loads(body)
            self.send_json(api_delete_record(data['id'], user['user']))

        elif path == '/api/upload-csv':
            user = self.require_auth()
            if not user: return
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' in content_type:
                boundary = content_type.split('boundary=')[1].strip()
                parts = body.split(f'--{boundary}'.encode())
                csv_data = None
                mode = 'smart'
                for part in parts:
                    part_str = part.decode('latin-1')
                    if 'name="file"' in part_str:
                        csv_data = part_str.split('\r\n\r\n', 1)[1].rsplit('\r\n', 1)[0]
                    if 'name="mode"' in part_str:
                        mode = part_str.split('\r\n\r\n', 1)[1].rsplit('\r\n', 1)[0].strip()
                if csv_data:
                    stats = import_csv_data(csv_data, user['user'], mode)
                    self.send_json(stats)
                else:
                    self.send_json({'error': 'No CSV data found'}, 400)
            else:
                csv_data = body.decode('latin-1')
                self.send_json(import_csv_data(csv_data, user['user']))

        elif path == '/api/user':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            data = json.loads(body)
            self.send_json(api_create_user(data))

        elif path == '/api/webhook/forms':
            params = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            api_key = params.get('key', '')
            db = get_db()
            stored_key = db.execute("SELECT value FROM settings WHERE key='webhook_key'").fetchone()
            db.close()
            if not stored_key or api_key != stored_key['value']:
                self.send_json({'error': 'Invalid API key'}, 401); return
            # Accept single record from webhook
            data = json.loads(body)
            result = api_save_record(data, 'webhook')
            self.send_json(result)

        elif path == '/api/generate-webhook-key':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            key = secrets.token_hex(24)
            db = get_db()
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('webhook_key', ?)", [key])
            db.commit(); db.close()
            self.send_json({'key': key})

        elif path == '/api/change-password':
            user = self.require_auth()
            if not user: return
            data = json.loads(body)
            db = get_db()
            db.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_pw(data['new_password']), user['user']))
            db.commit(); db.close()
            self.send_json({'success': True})

        elif path == '/api/setting':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            data = json.loads(body)
            db = get_db()
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", [data['key'], data['value']])
            db.commit(); db.close()
            self.send_json({'success': True})

        elif path == '/api/generate-sitrep-docx':
            user = self.require_auth()
            if not user: return
            data = json.loads(body)
            docx_bytes = generate_sitrep_docx(data)
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            self.send_header('Content-Disposition', f'attachment; filename="SITREP_{datetime.now().strftime("%Y%m%d")}.docx"')
            self.send_header('Content-Length', len(docx_bytes))
            self.end_headers()
            self.wfile.write(docx_bytes)

        elif path == '/api/mofa-mark-sent':
            user = self.require_auth()
            if not user: return
            try:
                data = json.loads(body)
                from_id = data.get('from_id')
                to_id = data.get('to_id')
                ids = data.get('ids', [])
                db = get_db()
                # Ensure mofa_status column exists
                try:
                    db.execute("ALTER TABLE evacuees ADD COLUMN mofa_status TEXT DEFAULT ''")
                    db.commit()
                except sqlite3.OperationalError:
                    pass  # column already exists
                if from_id is not None and to_id is not None:
                    from_id = int(from_id)
                    to_id = int(to_id)
                    cur = db.execute("""UPDATE evacuees SET mofa_status='Sent to MOFA', updated_at=CURRENT_TIMESTAMP, updated_by=?
                        WHERE id >= ? AND id <= ? AND travel_status='Pending' AND dup_flag='CLEAR'
                        AND (mofa_status IS NULL OR mofa_status = '' OR mofa_status = 'New')""",
                        [user['username'], from_id, to_id])
                    count = cur.rowcount
                    db.commit()
                elif ids and len(ids) > 0:
                    placeholders = ','.join(['?'] * len(ids))
                    cur = db.execute(f"""UPDATE evacuees SET mofa_status='Sent to MOFA', updated_at=CURRENT_TIMESTAMP, updated_by=?
                        WHERE id IN ({placeholders}) AND (mofa_status IS NULL OR mofa_status = '' OR mofa_status = 'New')""",
                        [user['username']] + [int(i) for i in ids])
                    count = cur.rowcount
                    db.commit()
                else:
                    db.close()
                    self.send_json({'success': False, 'error': 'No records selected'}, 400)
                    return
                db.execute("INSERT INTO audit_log (action, record_id, user, details) VALUES ('mofa_batch_sent', 0, ?, ?)",
                          [user['username'], f'Marked {count} records as Sent to MOFA'])
                db.commit()
                db.close()
                self.send_json({'success': True, 'count': count})
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)}, 500)

        elif path == '/api/bulk-visa-update':
            user = self.require_auth()
            if not user: return
            data = json.loads(body)
            passports = data.get('passports', [])
            status = data.get('status', 'Approved')
            if isinstance(passports, str):
                passports = [p.strip() for p in re.split(r'[,\n;]+', passports) if p.strip()]
            result = bulk_update_visa_status(passports, status, user['user'])
            self.send_json(result)

        elif path == '/api/backup':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            path_result = do_backup('manual')
            self.send_json({'success': True, 'path': path_result})

        elif path == '/api/restore':
            user = self.require_auth()
            if not user: return
            if user['role'] != 'admin': self.send_json({'error': 'Unauthorized'}, 403); return
            data = json.loads(body)
            result = restore_backup(data.get('name', ''))
            self.send_json(result)

        else:
            self.send_response(404)
            self.end_headers()

# ═══════════════════════════════════════════════════════════════
# LOGIN PAGE
# ═══════════════════════════════════════════════════════════════
LOGIN_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login - Evacuation Management System</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(135deg,#006600,#004d00);min-height:100vh;display:flex;align-items:center;justify-content:center}
.login-box{background:#fff;border-radius:16px;padding:40px;width:380px;box-shadow:0 20px 60px rgba(0,0,0,0.3)}
.login-box h1{text-align:center;color:#006600;font-size:1.4em;margin-bottom:6px}
.login-box .sub{text-align:center;color:#777;font-size:0.85em;margin-bottom:30px}
.login-box .flag{text-align:center;font-size:2.5em;margin-bottom:10px}
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:0.82em;font-weight:600;color:#555;margin-bottom:4px}
.form-group input{width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:1em}
.form-group input:focus{border-color:#006600;outline:none;box-shadow:0 0 0 3px rgba(0,102,0,0.1)}
.btn{width:100%;padding:14px;background:#006600;color:#fff;border:none;border-radius:8px;font-size:1em;font-weight:600;cursor:pointer}
.btn:hover{background:#004d00}
.error{color:#c62828;font-size:0.85em;margin-top:10px;text-align:center;display:none}
</style></head><body>
<div class="login-box">
<div class="flag">&#127477;&#127472;</div>
<h1>EVACUATION MANAGEMENT</h1>
<div class="sub">Pakistan Embassy Kuwait</div>
<form onsubmit="return doLogin(event)">
<div class="form-group"><label>Username</label><input id="username" required autofocus></div>
<div class="form-group"><label>Password</label><input id="password" type="password" required></div>
<button class="btn" type="submit">Sign In</button>
<div class="error" id="error"></div>
</form></div>
<script>
async function doLogin(e){
e.preventDefault();
const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({username:document.getElementById('username').value,password:document.getElementById('password').value})});
const d=await r.json();
if(d.success){window.location='/'}
else{const el=document.getElementById('error');el.textContent=d.error||'Login failed';el.style.display='block'}
return false}
</script></body></html>"""

# ═══════════════════════════════════════════════════════════════
# PUBLIC REGISTRATION PAGE (no login required)
# ═══════════════════════════════════════════════════════════════
PUBLIC_REGISTER_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Saudi Transit Visa Registration - Pakistan Embassy Kuwait</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f5f5;color:#212121}
.hdr{background:linear-gradient(135deg,#006600,#004d00);color:#fff;padding:20px 24px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.2)}
.hdr h1{font-size:1.4em;margin-bottom:4px}.hdr .sub{font-size:.85em;opacity:.9}
.hdr .flag{font-size:2em;margin-bottom:6px}
.ctr{max-width:700px;margin:0 auto;padding:20px}
.notice{background:#fff3e0;border:1px solid #ffcc80;border-radius:10px;padding:14px 18px;margin-bottom:18px;font-size:.88em;color:#e65100;line-height:1.5}
.notice strong{display:block;margin-bottom:4px}
.fs{background:#fff;border-radius:12px;padding:22px;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-bottom:16px}
.fs h3{margin-bottom:14px;padding-bottom:6px;border-bottom:2px solid #e8f5e9;color:#006600;font-size:1.05em}
.fg{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.fgp{display:flex;flex-direction:column}.fgp label{font-size:.82em;font-weight:600;margin-bottom:3px;color:#757575}
.fgp .req{color:#c62828}
.fgp input,.fgp select{padding:10px 12px;border:1px solid #e0e0e0;border-radius:8px;font-size:.9em;transition:border .2s}
.fgp input:focus,.fgp select:focus{border-color:#006600;outline:none;box-shadow:0 0 0 3px rgba(0,102,0,.1)}
.btn{padding:14px 32px;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:1em;transition:.2s;width:100%}
.btn-p{background:#006600;color:#fff}.btn-p:hover{background:#004d00}
.btn-p:disabled{background:#999;cursor:not-allowed}
.error{color:#c62828;font-size:.85em;margin-top:8px;display:none}
.footer{text-align:center;padding:20px;font-size:.8em;color:#999}
.dup-warning{background:#ffebee;border:1px solid #ef9a9a;border-radius:8px;padding:12px;margin-top:12px;display:none;color:#c62828;font-size:.88em}
@media(max-width:600px){.fg{grid-template-columns:1fr}.ctr{padding:12px}}
</style></head><body>
<div class="hdr">
<svg width="70" height="70" viewBox="0 0 200 200" style="margin-bottom:8px"><circle cx="100" cy="100" r="96" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="4"/><circle cx="100" cy="100" r="88" fill="#006600"/><circle cx="100" cy="100" r="85" fill="none" stroke="#fff" stroke-width="1.5"/><text x="100" y="42" text-anchor="middle" fill="#fff" font-size="11" font-family="Arial" font-weight="bold">EMBASSY OF THE ISLAMIC</text><text x="100" y="55" text-anchor="middle" fill="#fff" font-size="11" font-family="Arial" font-weight="bold">REPUBLIC OF PAKISTAN</text><g transform="translate(100,105)"><circle cx="-8" cy="0" r="28" fill="none" stroke="#fff" stroke-width="2.5"/><circle cx="5" cy="-5" r="23" fill="#006600"/><polygon points="18,-12 20,-5 27,-5 21,-1 23,6 18,2 13,6 15,-1 9,-5 16,-5" fill="#fff"/></g><text x="100" y="168" text-anchor="middle" fill="#fff" font-size="16" font-family="Arial" font-weight="bold">KUWAIT</text></svg>
<h1>SAUDI TRANSIT VISA REGISTRATION</h1>
<div class="sub">Pakistan Embassy Kuwait &mdash; Consular Services</div>
</div>
<div class="ctr">
<div class="notice">
<strong>&#9888;&#65039; Important Information</strong>
The situation in Kuwait remains stable and under control. This registration facility has been established as a measure to assist Pakistani nationals who may require travel facilitation, and, at present, this service is primarily intended for individuals on Visit Visas in Kuwait who may require three-day transit visa facilitation through the Kingdom of Saudi Arabia to return to Pakistan.<br><br>All Pakistani nationals are advised to remain calm and continue their normal activities, while staying updated through official announcements issued by the Government of Kuwait, and to strictly follow the guidance and instructions issued by Kuwaiti authorities.<br><br>The Embassy remains in close coordination with the relevant Kuwaiti authorities and will continue to provide updates and assistance as required.<br><br><hr style="border:none;border-top:1px solid #ffcc80;margin:14px 0"><div dir="rtl" style="text-align:right;font-family:'Noto Nastaliq Urdu','Jameel Noori Nastaleeq','Urdu Typesetting',Tahoma,Arial,sans-serif;line-height:2;font-size:.95em">کویت میں الحمدلله کویتی حکومت کے موثر اقدامات کی وجہ سے زندگی معمول کے مطابق ہے ۔ تاہم پاکستانی شہریوں سے گذارش ہے کہ غیر ضروری سفر سے احتراز کریں -<br><br>پاکستانی شہری (خاص طور پہ جو لوگ وزٹ ویزا پہ آۓ ہوئے ہیں اور واپس جانا چاہتے ہیں یا وہ لوگ جن کا کسی فیملی ایمرجنسی کی وجہ سے پاکستان جانا ناگزیر ہو ) رجسٹریشن کراسکتے ہیں ۔ تاکہ سفارتخانہ پاکستان واپسی کے لیے سعودی عرب کا تین روزہ ٹرانزٹ ویزا حاصل کرنے میں آپ کی مدد کر سکے ۔<br><br>تمام پاکستانی شہریوں سے گزارش ہے کہ وہ پُرسکون رہیں اور اپنی معمول کی سرگرمیاں جاری رکھیں۔ مزید یہ کہ معلومات کے حصول کے لیے صرف حکومتِ کویت کے سرکاری ذرائع سے جاری کردہ اعلانات پر توجہ دیں اور کویتی حکام کی جانب سے جاری ہدایات پر عمل کریں۔ سفارت خانہ متعلقہ کویتی حکام کے ساتھ مسلسل رابطے میں ہے اور ضرورت کے مطابق پاکستانی شہریوں کو رہنمائی اور معاونت فراہم کرتا رہے گا -</div><br>Please fill in all required fields accurately. Your passport number will be used to track your application. Do not submit multiple times — duplicate entries are automatically detected.
</div>
<form id="regForm" onsubmit="return submitForm(event)">
<div class="fs"><h3>Personal Information</h3>
<div class="fg">
<div class="fgp"><label>Full Name <span class="req">*</span></label><input name="name" required placeholder="As shown on passport"></div>
<div class="fgp"><label>Passport Number <span class="req">*</span></label><input name="passport" required placeholder="e.g. ML3955083" style="text-transform:uppercase"></div>
<div class="fgp"><label>Gender <span class="req">*</span></label><select name="gender" required><option value="">Select Gender</option><option>Male</option><option>Female</option><option>Child</option></select></div>
<div class="fgp"><label>CNIC Number (without dashes)</label><input name="cnic" placeholder="e.g. 3520112345671"></div>
<div class="fgp"><label>Mobile Number <span class="req">*</span></label><input name="mobile" required placeholder="e.g. 00965-99816580"></div>
<div class="fgp"><label>Email Address</label><input name="email" type="email" placeholder="your@email.com"></div>
</div></div>
<div class="fs"><h3>Residence &amp; Location</h3>
<div class="fg">
<div class="fgp"><label>Country of Residence <span class="req">*</span></label><select name="country" required><option value="">Select Country</option><option>Kuwait</option><option>Pakistan</option><option>Iraq</option><option>KSA</option><option>US</option><option>Bahrain</option><option>Qatar</option><option>Oman</option><option>UAE</option></select></div>
<div class="fgp"><label>Kuwaiti Civil ID Number (if any)</label><input name="civil_id" placeholder="Ignore if on visit visa"></div>
<div class="fgp"><label>Border Crossing Area <span class="req">*</span></label><select name="border_crossing" required><option value="">Select Crossing</option><option>Khafji Border</option><option>Salmi Boarder</option><option>Salmi Crossing</option></select></div>
<div class="fgp"><label>Profession / Company</label><input name="company" placeholder="Your profession or company"></div>
</div></div>
<div class="fs"><h3>Travel Details</h3>
<div class="fg">
<div class="fgp"><label>Planned Departure from Kuwait <span class="req">*</span></label><input type="date" name="planned_departure" required></div>
<div class="fgp"><label>Transit Stay in Saudi City (Planned) <span class="req">*</span></label><input name="saudi_city" required placeholder="e.g. Riyadh, Jeddah, Dammam"></div>
<div class="fgp"><label>Traveling with Family or Alone? <span class="req">*</span></label><select name="traveling_with_family" required><option value="">Select</option><option value="Yes">Yes — Traveling with Family</option><option value="No">No — Traveling Alone</option></select></div>
<div class="fgp"><label>You have to leave KSA in Three Days as per the requirements <span class="req">*</span></label><select name="confirm_ksa_3days" required><option value="">Select</option><option value="Yes">Yes — I Confirm</option></select></div>
</div></div>
<div style="margin-top:8px">
<button type="submit" class="btn btn-p" id="submitBtn">Submit Registration</button>
<div class="error" id="errorMsg"></div>
<div class="dup-warning" id="dupWarning"></div>
</div>
</form>
</div>
<div class="footer" style="line-height:1.8">
<strong style="color:#333">Embassy of Pakistan, Kuwait</strong><br>
Villa 440, Street 108, Block 12, Jabriya, Kuwait<br>
Tel: (+965) 25327651, 25354073 | Fax: (+965) 25327648, 25356594<br>
<strong>Emergency Contacts:</strong> Awais: +965-55977292 | Zahid: +965-55964923 | Shahid Khan: +965-66568265<br><br>
<strong style="color:#c62828">IMPORTANT:</strong> After registering, please send your passport copies to: <a href="mailto:parepkuwaitcwa37@gmail.com" style="color:#006600;font-weight:600">parepkuwaitcwa37@gmail.com</a>
</div>
<script>
async function submitForm(e){
e.preventDefault();
const btn=document.getElementById('submitBtn');
btn.disabled=true;btn.textContent='Submitting...';
document.getElementById('errorMsg').style.display='none';
document.getElementById('dupWarning').style.display='none';

const fd=new FormData(e.target);const data={};
fd.forEach((v,k)=>data[k]=v);
data.travel_status='Pending';

try{
const r=await fetch('/api/public-register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const d=await r.json();
if(d.success){
  if(d.dup_details && d.dup_details.length > 0){
    document.getElementById('dupWarning').innerHTML='<strong>&#9888; Note:</strong> Your record was saved but a possible duplicate was detected: '+d.dup_details.join('; ')+'. If you already registered, you do not need to register again.';
    document.getElementById('dupWarning').style.display='block';
  }
  window.location='/embassy-registration/success';
}else{
  document.getElementById('errorMsg').textContent=d.error||'Submission failed. Please try again.';
  document.getElementById('errorMsg').style.display='block';
  btn.disabled=false;btn.textContent='Submit Registration';
}
}catch(err){
document.getElementById('errorMsg').textContent='Network error. Please check your connection and try again.';
document.getElementById('errorMsg').style.display='block';
btn.disabled=false;btn.textContent='Submit Registration';
}return false}
</script></body></html>"""

REGISTER_SUCCESS_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registration Successful - Pakistan Embassy Kuwait</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f5f5;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
.card{background:#fff;border-radius:16px;padding:40px;max-width:500px;width:90%;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.1)}
.check{font-size:4em;margin-bottom:12px}
h1{color:#2e7d32;font-size:1.5em;margin-bottom:8px}
p{color:#555;line-height:1.6;margin-bottom:16px}
.info{background:#e8f5e9;border-radius:8px;padding:14px;font-size:.88em;color:#1b5e20;margin-bottom:16px;text-align:left}
.info strong{display:block;margin-bottom:4px}
a{display:inline-block;padding:12px 24px;background:#006600;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;margin-top:8px}
a:hover{background:#004d00}
</style></head><body>
<div class="card">
<div class="check">&#9989;</div>
<h1>Registration Successful!</h1>
<p>Your details have been submitted to Pakistan Embassy Kuwait. Your application is now being processed.</p>
<div class="info">
<strong>What happens next?</strong>
Your visa application will be reviewed by the Embassy team. You will be contacted on the mobile number you provided once there is an update on your Saudi transit visa status.
</div>
<div style="background:#fff3e0;border:1px solid #ffcc80;border-radius:8px;padding:14px;font-size:.9em;color:#e65100;margin-bottom:16px;text-align:left">
<strong style="display:block;margin-bottom:4px">&#9888;&#65039; Required: Send Passport Copies</strong>
Please email a copy of your passport to:<br><a href="mailto:parepkuwaitcwa37@gmail.com" style="color:#006600;font-weight:600">parepkuwaitcwa37@gmail.com</a>
</div>
<p style="font-size:.85em;color:#999">Please do not submit multiple times. If you need to update your information, contact the Embassy directly.<br>Embassy of Pakistan: Villa 440, Street 108, Block 12, Jabriya, Kuwait<br>Tel: (+965) 25327651, 25354073<br>Emergency: Awais: +965-55977292 | Zahid: +965-55964923 | Shahid Khan: +965-66568265</p>
<a href="/embassy-registration">Submit Another Registration</a>
</div>
</body></html>"""

# ═══════════════════════════════════════════════════════════════
# MAIN APPLICATION (single-page app)
# ═══════════════════════════════════════════════════════════════
MAIN_APP = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evacuation Management System</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--p:#006600;--pl:#e8f5e9;--d:#c62828;--dl:#ffebee;--w:#e65100;--wl:#fff3e0;--i:#1565c0;--il:#e3f2fd;--s:#2e7d32;--bg:#f5f5f5;--card:#fff;--t:#212121;--tl:#757575;--bd:#e0e0e0;--sh:0 2px 8px rgba(0,0,0,.1)}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;background:var(--bg);color:var(--t)}
.hdr{background:linear-gradient(135deg,var(--p),#004d00);color:#fff;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 10px rgba(0,0,0,.2)}
.hdr h1{font-size:1.2em}.hdr .sub{font-size:.8em;opacity:.9}.hdr .flag{font-size:1.6em;margin-right:10px}
.hdr .user-info{display:flex;align-items:center;gap:12px;font-size:.85em}
.hdr .user-info a{color:#fff;text-decoration:none;background:rgba(255,255,255,.15);padding:6px 14px;border-radius:6px}
.nav{background:#fff;border-bottom:1px solid var(--bd);display:flex;padding:0 16px;box-shadow:var(--sh);flex-wrap:wrap}
.nav button{padding:12px 20px;border:none;background:none;cursor:pointer;font-size:.88em;font-weight:500;color:var(--tl);border-bottom:3px solid transparent;transition:.2s}
.nav button.active{color:var(--p);border-bottom-color:var(--p);background:var(--pl)}.nav button:hover{background:#f0f0f0}
.ctr{max-width:1400px;margin:0 auto;padding:16px}.tab{display:none}.tab.active{display:block}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:14px;margin-bottom:20px}
.kc{background:var(--card);border-radius:10px;padding:16px;box-shadow:var(--sh);border-left:4px solid var(--p)}
.kc.d{border-left-color:var(--d)}.kc.w{border-left-color:var(--w)}.kc.i{border-left-color:var(--i)}.kc.s{border-left-color:var(--s)}
.kc .lb{font-size:.75em;color:var(--tl);text-transform:uppercase;letter-spacing:.5px}
.kc .vl{font-size:2em;font-weight:700;margin:2px 0}
.kc.d .vl{color:var(--d)}.kc.w .vl{color:var(--w)}.kc.i .vl{color:var(--i)}.kc.s .vl{color:var(--s)}
.kc .su{font-size:.75em;color:var(--tl)}
.alert{background:var(--dl);border:1px solid #ef9a9a;border-radius:8px;padding:10px 16px;margin-bottom:16px;display:none;align-items:center;gap:8px;font-weight:500;color:var(--d)}
.cg{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px;margin-bottom:20px}
.cc{background:var(--card);border-radius:10px;padding:16px;box-shadow:var(--sh)}.cc h3{font-size:.95em;margin-bottom:10px}
.tc{background:var(--card);border-radius:10px;padding:16px;box-shadow:var(--sh);margin-bottom:16px;overflow-x:auto}.tc h3{margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:.82em}
th{background:#f8f9fa;padding:8px 10px;text-align:left;font-weight:600;border-bottom:2px solid var(--bd);position:sticky;top:0}
td{padding:7px 10px;border-bottom:1px solid #f0f0f0}tr:hover{background:#f8f9fa}
.bdg{padding:2px 8px;border-radius:10px;font-size:.75em;font-weight:600}
.bdg-dep{background:#c8e6c9;color:#1b5e20}.bdg-pen{background:#fff9c4;color:#f57f17}.bdg-vis{background:#bbdefb;color:#0d47a1}
.bdg-app{background:#c8e6c9;color:#1b5e20}.bdg-rej{background:#ffcdd2;color:#b71c1c}.bdg-clr{background:#e8f5e9;color:#2e7d32}
.bdg-dup{background:#ffcdd2;color:var(--d)}
.fg{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.fgp{display:flex;flex-direction:column}.fgp label{font-size:.8em;font-weight:600;margin-bottom:3px;color:var(--tl)}
.fgp input,.fgp select,.fgp textarea{padding:9px 10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em}
.fgp input:focus,.fgp select:focus{border-color:var(--p);outline:none;box-shadow:0 0 0 3px rgba(0,102,0,.1)}
.fs{background:var(--card);border-radius:10px;padding:20px;box-shadow:var(--sh);margin-bottom:16px}
.fs h3{margin-bottom:14px;padding-bottom:6px;border-bottom:2px solid var(--pl)}
.btn{padding:9px 20px;border:none;border-radius:7px;cursor:pointer;font-weight:600;font-size:.88em;transition:.2s}
.btn-p{background:var(--p);color:#fff}.btn-p:hover{background:#004d00}
.btn-d{background:var(--d);color:#fff}.btn-i{background:var(--i);color:#fff}.hidden{display:none!important}
.btn-w{background:var(--w);color:#fff}
.bg{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.sb{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap;align-items:center}
.sb input,.sb select{padding:9px 12px;border:1px solid var(--bd);border-radius:7px;font-size:.88em}
.sb input{flex:1;min-width:180px}
.rc{font-size:.82em;color:var(--tl);margin-bottom:8px}
.scroll-t{max-height:560px;overflow-y:auto}
.rp{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:35px;max-width:780px;margin:16px auto;font-family:'Times New Roman',serif}
.rp h1{text-align:center;font-size:1.5em;border-bottom:3px double #333;padding-bottom:8px;margin-bottom:4px}
.rp h2{text-align:center;font-size:1em;margin-bottom:16px;color:#555}
.rp .rs{margin-bottom:16px}.rp .rs h3{font-size:1em;border-bottom:1px solid #ccc;padding-bottom:3px;margin-bottom:8px}
.rp table{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:.87em}
.rp table th,.rp table td{border:1px solid #999;padding:5px 8px}.rp table th{background:#e8e8e8}
.mo{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.5);z-index:1000;justify-content:center;align-items:center}
.mo.show{display:flex}.ml{background:#fff;border-radius:12px;padding:24px;max-width:680px;width:92%;max-height:85vh;overflow-y:auto}
.ml h3{margin-bottom:14px}.ml .cb{float:right;background:none;border:none;font-size:1.5em;cursor:pointer}
.toast{position:fixed;bottom:16px;right:16px;background:var(--s);color:#fff;padding:12px 20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.2);z-index:2000;display:none;font-weight:500}
.imp-result{max-height:300px;overflow-y:auto;font-size:.82em;background:#f8f9fa;padding:12px;border-radius:6px;margin-top:12px;white-space:pre-wrap}
.stat-box{display:inline-block;padding:4px 12px;border-radius:6px;margin:4px;font-weight:600;font-size:.9em}
.stat-ok{background:#c8e6c9;color:#1b5e20}.stat-skip{background:#fff9c4;color:#f57f17}.stat-upd{background:#bbdefb;color:#0d47a1}.stat-err{background:#ffcdd2;color:#b71c1c}
@media print{.hdr,.nav,.btn,.sb,.np{display:none!important}.tab{display:none!important}#tab-report{display:block!important}.rp{border:none;box-shadow:none;padding:0;margin:0;max-width:100%}body{background:#fff}}
@media(max-width:768px){.kg{grid-template-columns:repeat(2,1fr)}.cg{grid-template-columns:1fr}.nav button{padding:8px 12px;font-size:.8em}}
</style></head><body>
<div class="hdr"><div style="display:flex;align-items:center"><span class="flag">&#127477;&#127472;</span><div><h1>EVACUATION MANAGEMENT SYSTEM</h1><div class="sub">Pakistan Embassy Kuwait &mdash; CWA Kuwait</div></div></div>
<div class="user-info"><span id="userDisplay"></span><a href="/logout">Logout</a></div></div>
<div class="nav">
<button class="active" onclick="go('dash',this)">Dashboard</button>
<button onclick="go('reg',this)">New Registration</button>
<button onclick="go('recs',this)">All Records</button>
<button onclick="go('mofa',this)">MOFA Export</button>
<button onclick="go('csv',this)">CSV Import</button>
<button onclick="go('report',this)">SITREP Report</button>
<button onclick="go('sitrep',this)">SITREP Editor</button>
<button onclick="go('admin',this)">Admin</button>
</div>

<!-- DASHBOARD -->
<div id="tab-dash" class="tab active"><div class="ctr">
<div class="alert" id="alertBar"><span>&#9888;&#65039;</span><span id="alertText"></span></div>
<div class="kg" id="kpiGrid"></div>
<div class="cg"><div class="cc"><h3>Status Breakdown</h3><canvas id="c1"></canvas></div><div class="cc"><h3>Country Distribution</h3><canvas id="c2"></canvas></div></div>
<div class="cg"><div class="cc"><h3>Gender Breakdown</h3><canvas id="c3"></canvas></div><div class="cc"><h3>Daily Requests &amp; Cumulative</h3><canvas id="c4"></canvas></div></div>
<div class="cg"><div class="cc"><h3>KSA Visa Status</h3><canvas id="c5"></canvas></div><div class="cc"><h3>Border Crossings</h3><canvas id="c6"></canvas></div></div>
<div class="tc"><h3>Country Breakdown</h3><table id="countryTbl"></table></div>
</div></div>

<!-- REGISTER -->
<div id="tab-reg" class="tab"><div class="ctr">
<div style="text-align:center;margin-bottom:18px">
<svg width="70" height="70" viewBox="0 0 200 200" style="margin-bottom:8px"><circle cx="100" cy="100" r="96" fill="none" stroke="rgba(0,102,0,0.3)" stroke-width="4"/><circle cx="100" cy="100" r="88" fill="#006600"/><circle cx="100" cy="100" r="85" fill="none" stroke="#fff" stroke-width="1.5"/><text x="100" y="42" text-anchor="middle" fill="#fff" font-size="11" font-family="Arial" font-weight="bold">EMBASSY OF THE ISLAMIC</text><text x="100" y="55" text-anchor="middle" fill="#fff" font-size="11" font-family="Arial" font-weight="bold">REPUBLIC OF PAKISTAN</text><g transform="translate(100,105)"><circle cx="-8" cy="0" r="28" fill="none" stroke="#fff" stroke-width="2.5"/><circle cx="5" cy="-5" r="23" fill="#006600"/><polygon points="18,-12 20,-5 27,-5 21,-1 23,6 18,2 13,6 15,-1 9,-5 16,-5" fill="#fff"/></g><text x="100" y="168" text-anchor="middle" fill="#fff" font-size="16" font-family="Arial" font-weight="bold">KUWAIT</text></svg>
<h2 style="color:#006600;margin-top:6px;font-size:1.1em">New Evacuee Registration</h2>
</div>
<form id="regForm" onsubmit="return doRegister(event)">
<div class="fs"><h3>Personal Information</h3><div class="fg">
<div class="fgp"><label>Full Name *</label><input name="name" required></div>
<div class="fgp"><label>Passport Number *</label><input name="passport" required></div>
<div class="fgp"><label>CNIC</label><input name="cnic" placeholder="Without dashes"></div>
<div class="fgp"><label>Gender *</label><select name="gender" required><option value="">Select</option><option>Male</option><option>Female</option><option>Child</option></select></div>
<div class="fgp"><label>Date of Birth</label><input type="date" name="dob"></div>
<div class="fgp"><label>Mobile *</label><input name="mobile" required></div>
<div class="fgp"><label>Email</label><input name="email" type="email"></div>
<div class="fgp"><label>Emergency Contact</label><input name="emergency_contact"></div>
<div class="fgp"><label>Medical/Special Needs</label><input name="medical"></div>
</div></div>
<div class="fs"><h3>Residence &amp; Location</h3><div class="fg">
<div class="fgp"><label>Country of Residence *</label><select name="country" required><option value="">Select</option><option>Kuwait</option><option>Pakistan</option><option>KSA</option><option>Iraq</option><option>US</option><option>Bahrain</option><option>Qatar</option><option>Oman</option><option>UAE</option><option>Dubai</option></select></div>
<div class="fgp"><label>Civil ID</label><input name="civil_id"></div>
<div class="fgp"><label>Company/Purpose</label><input name="company"></div>
<div class="fgp"><label>Border Crossing</label><select name="border_crossing"><option value="">Select</option><option>Khafji Border</option><option>Khafji Crossing</option><option>Salmi Crossing</option><option>Salmi Boarder</option></select></div>
<div class="fgp"><label>Family Group ID</label><input name="family_group_id" placeholder="e.g. FAM-001"></div>
<div class="fgp"><label>Dependents</label><input type="number" name="dependents" min="0" value="0"></div>
<div class="fgp"><label>Accommodation</label><input name="accommodation"></div>
</div></div>
<div class="fs"><h3>Visa &amp; Travel</h3><div class="fg">
<div class="fgp"><label>KSA Visa Status</label><select name="visa_status"><option value="">Select</option><option>Approved</option><option>Pending</option><option>Rejected</option></select></div>
<div class="fgp"><label>Travel Status *</label><select name="travel_status" required><option value="">Select</option><option>Pending</option><option>Visa Obtained</option><option>Departed</option></select></div>
<div class="fgp"><label>Airline</label><select name="airline"><option value="">Select</option><option>PIA</option><option>Kuwait Airways</option><option>Jazeera</option><option>Emirates</option><option>Air Blue</option></select></div>
<div class="fgp"><label>Ticket Number</label><input name="ticket_number"></div>
<div class="fgp"><label>Departure Airport</label><input name="departure_airport"></div>
<div class="fgp"><label>Destination</label><input name="destination_country"></div>
<div class="fgp"><label>Priority</label><select name="priority"><option value="">Normal</option><option>High</option><option>Medium</option><option>Low</option></select></div>
<div class="fgp"><label>Date of Request</label><input type="date" name="date_of_request"></div>
<div class="fgp"><label>Planned Departure from Kuwait</label><input type="date" name="planned_departure"></div>
<div class="fgp"><label>Transit Stay in Saudi City (Planned)</label><input name="saudi_city" placeholder="e.g. Riyadh, Jeddah, Dammam"></div>
<div class="fgp"><label>Traveling with Family?</label><select name="traveling_with_family"><option value="">Select</option><option value="Yes">Yes</option><option value="No">No</option></select></div>
<div class="fgp"><label>Confirm KSA 3-Day Requirement</label><select name="confirm_ksa_3days"><option value="">Select</option><option value="Yes">Yes</option><option value="No">No</option></select></div>
</div></div>
<div class="fs"><h3>Remarks</h3><div class="fgp"><textarea name="remarks" rows="2"></textarea></div>
<div class="bg"><button type="submit" class="btn btn-p">Register Evacuee</button><button type="reset" class="btn" style="background:#eee">Clear</button></div>
</div></form></div></div>

<!-- RECORDS -->
<div id="tab-recs" class="tab"><div class="ctr"><div class="tc">
<h3>All Registered Evacuees</h3>
<div class="sb">
<input id="sInput" placeholder="Search name, passport, CNIC, mobile..." oninput="loadRecords()">
<select id="fStatus" onchange="loadRecords()"><option value="">All Status</option><option>Departed</option><option>Visa Obtained</option><option>Pending</option></select>
<select id="fCountry" onchange="loadRecords()"><option value="">All Countries</option><option>Kuwait</option><option>Pakistan</option><option>Iraq</option><option>US</option><option>KSA</option><option>UAE</option><option>Dubai</option></select>
<select id="fGender" onchange="loadRecords()"><option value="">All Gender</option><option>Male</option><option>Female</option><option>Child</option></select>
<select id="fDup" onchange="loadRecords()"><option value="">All</option><option value="DUPLICATE">Duplicates Only</option><option value="CLEAR">Clean Only</option></select>
<a href="/api/export" class="btn btn-i" style="text-decoration:none;color:#fff" data-admin-only>Export CSV</a>
</div>
<div class="rc" id="recCount"></div>
<div class="scroll-t"><table id="recTbl"></table></div>
</div></div></div>

<!-- CSV IMPORT -->
<div id="tab-csv" class="tab"><div class="ctr">
<div class="fs"><h3>Import from Microsoft Forms / Google Forms CSV</h3>
<p style="margin-bottom:12px;font-size:.88em;color:var(--tl)">Upload the CSV exported from your form. The system auto-maps columns and handles duplicates intelligently.</p>
<div class="fg" style="margin-bottom:14px">
<div class="fgp"><label>CSV File</label><input type="file" id="csvFile" accept=".csv"></div>
<div class="fgp"><label>Duplicate Handling</label><select id="csvMode">
<option value="smart">Smart (skip exact dupes, update partial)</option>
<option value="skip">Skip All Duplicates</option>
<option value="force">Import All (flag duplicates)</option>
</select></div>
</div>
<button class="btn btn-p" onclick="uploadCSV()">Upload &amp; Import</button>
<div id="importResult" style="display:none;margin-top:16px">
<div id="importStats"></div>
<div class="imp-result" id="importDetails"></div>
</div>
</div>
<div class="fs"><h3>Microsoft Forms Auto-Sync Guide</h3>
<p style="font-size:.88em;line-height:1.6;color:var(--tl)">
<strong>Option 1: Power Automate (Recommended)</strong><br>
1. Go to <a href="https://flow.microsoft.com" target="_blank">flow.microsoft.com</a><br>
2. Create flow: "When a new response is submitted" (Microsoft Forms trigger)<br>
3. Add action: "HTTP" → POST to your server's webhook URL<br>
4. Map form fields to JSON body<br><br>
<strong>Option 2: Manual CSV Export</strong><br>
1. Open your form in Microsoft Forms → Responses tab<br>
2. Click "Open in Excel" or download CSV<br>
3. Upload here using the form above<br><br>
<strong>Webhook URL:</strong> <code id="webhookUrl">Set up in Admin tab</code>
</p></div>
</div></div>

<!-- MOFA EXPORT -->
<div id="tab-mofa" class="tab"><div class="ctr">
<div class="fs">
<h3 style="color:var(--p)">MOFA Visa Request — Download &amp; Send</h3>
<p style="font-size:.88em;color:var(--tl);margin-bottom:14px">Select a range of pending cases to download for MOFA Saudi Arabia. Only shows clean (non-duplicate) pending records. Download contains: Name, Passport Number, and Border Entry Point.</p>
<div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin-bottom:14px">
<div class="fgp"><label style="font-size:.82em;font-weight:600">From Record #</label><select id="mofaFrom" style="padding:8px 10px;border:1px solid var(--bd);border-radius:7px;min-width:220px"></select></div>
<div class="fgp"><label style="font-size:.82em;font-weight:600">To Record #</label><select id="mofaTo" style="padding:8px 10px;border:1px solid var(--bd);border-radius:7px;min-width:220px"></select></div>
<button class="btn btn-p" style="padding:10px 20px" onclick="loadMofaPreview()">Preview</button>
</div>
<div id="mofaStats" style="margin-bottom:12px;font-size:.9em;display:none">
<span style="background:var(--pl);color:var(--p);padding:4px 12px;border-radius:20px;font-weight:600" id="mofaCount"></span>
<span style="margin-left:8px;color:var(--tl)" id="mofaRange"></span>
</div>
<div class="scroll-t"><table id="mofaTbl" style="font-size:.88em"></table></div>
<div style="display:flex;gap:10px;margin-top:14px" id="mofaActions" class="hidden">
<button class="btn btn-p" style="padding:10px 20px" onclick="downloadMofa()">Download CSV for MOFA</button>
<button class="btn" style="padding:10px 20px;background:#fff3e0;color:#e65100;border:1px solid #ffcc80" onclick="markSentToMofa()">Mark as Sent to MOFA</button>
</div>
</div>
<div class="fs" style="margin-top:16px">
<h3>Previously Sent Batches</h3>
<p style="font-size:.88em;color:var(--tl);margin-bottom:10px">Records already marked as "Sent to MOFA"</p>
<div class="scroll-t"><table id="mofaSentTbl" style="font-size:.88em"></table></div>
</div>
</div></div>

<!-- REPORT -->
<div id="tab-report" class="tab"><div class="ctr">
<div class="np" style="margin-bottom:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
<label style="font-weight:600">Report Date:</label>
<input type="date" id="repDate" style="padding:7px 10px;border:1px solid #ccc;border-radius:6px">
<button class="btn btn-p" onclick="genReport()">Generate SITREP</button>
<button class="btn btn-i" onclick="window.print()">Print / Save PDF</button>
</div>
<div id="repContent"></div>
</div></div>

<!-- SITREP EDITOR -->
<div id="tab-sitrep" class="tab"><div class="ctr">
<div class="np" style="margin-bottom:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
<button class="btn btn-p" onclick="loadSitrepData()">Refresh Data from Dashboard</button>
<button class="btn btn-i" onclick="downloadSitrepDocx()">Download as Word (.docx)</button>
<button class="btn btn-w" onclick="window.print()">Print / PDF</button>
</div>
<div class="fs"><h3>SITUATION REPORT — Editable Template</h3>
<p style="font-size:.85em;color:var(--tl);margin-bottom:14px">Data fields are auto-populated from the dashboard. Edit any text below, then download as Word document.</p>
<div class="fg">
<div class="fgp"><label>Date &amp; Time of Report</label><input id="sr_date" value=""></div>
<div class="fgp"><label>Country/Region</label><input id="sr_country" value="Kuwait"></div>
</div>
<div class="fg" style="margin-top:10px">
<div class="fgp"><label>Emergency Hotline</label><textarea id="sr_hotline" rows="3">Awais: +965-55977292\nZahid: +965-55964923\nShahid Khan: +965-66568265
Mr. Awais Saeed: +965-5597292
Mr. Zahid Iqbal: +965-55964923
Mr. Munir Khan: +965 9856 2753</textarea></div>
<div class="fgp"><label>Number of Stranded Pakistanis</label><input id="sr_stranded" value="Nil"></div>
</div>
</div>

<div class="fs"><h3>1. Overall Situation</h3>
<textarea id="sr_situation" rows="6" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">a) Kuwait continues to face intermittent missile and drone threats as part of the ongoing regional escalation.
b) Kuwaiti air defence systems remain actively engaged in intercepting hostile aerial targets.
c) Government institutions remain focused on maintaining defensive readiness and protecting critical infrastructure.
d) Despite the tense security environment, the overall situation inside the country remains stable.</textarea>
</div>

<div class="fs"><h3>2. Diaspora Profile</h3>
<div class="fg">
<div class="fgp"><label>Estimated Number</label><input id="sr_diaspora_num" value="101,976"></div>
<div class="fgp"><label>Key Diaspora Locations</label><input id="sr_diaspora_loc" value="Farwaniya, Jleeb Al-Shuyoukh, Hawally, Ahmadi"></div>
<div class="fgp"><label>Total Registered with Mission</label><input id="sr_registered" readonly></div>
<div class="fgp"><label>Evacuation Requested</label><input id="sr_evac_requested" readonly></div>
</div>
</div>

<div class="fs"><h3>3. Airspace Status</h3>
<div class="fg">
<div class="fgp"><label>Airspace</label><select id="sr_airspace"><option>Closed until further orders</option><option>Open</option><option>Partially Open</option><option>Closed</option></select></div>
<div class="fgp"><label>Airport Operations</label><select id="sr_airport"><option>Suspended</option><option>Normal</option><option>Limited</option></select></div>
<div class="fgp"><label>NOTAM</label><input id="sr_notam" value="Closed till further instructions"></div>
</div>
</div>

<div class="fs"><h3>4. Land Routes Status</h3>
<textarea id="sr_land" rows="2" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">Land borders are open. Al-Khafji and Salmi borders operational.</textarea>
</div>

<div class="fs"><h3>5. Facilitation Measures</h3>
<textarea id="sr_facilitation" rows="5" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">Emergency response mechanism activated.
Dedicated hotline functioning.
Emergency contact numbers widely circulated across community networks.
Special Facilitation Desk operational.
Embassy fully functional and accessible.
Kuwait visit visa extensions facilitated / Saudi visa facilitation where needed being coordinated with Parep Riyadh.</textarea>
</div>

<div class="fs"><h3>6. Coordination with Host Government</h3>
<textarea id="sr_coordination" rows="4" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">Coordination ongoing with:
Kuwaiti Ministry of Foreign Affairs & Ministry of Interior
Kuwaiti Civil Aviation and Airport Authorities
Airlines and Pakistani community representatives</textarea>
</div>

<div class="fs"><h3>7. Evacuation Options</h3>
<div class="fg">
<div class="fgp"><label>By Air Status</label><textarea id="sr_evac_air" rows="2" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">Not possible at the moment due to airspace closure</textarea></div>
<div class="fgp"><label>By Land Status</label><textarea id="sr_evac_land" rows="2" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">Al-Khafji and Salmi borders. Ground situation stable. Travel time: 01:30 hours</textarea></div>
</div>
</div>

<div class="fs"><h3>8. Status of Evacuation (Auto-populated)</h3>
<div id="sr_evac_status" style="padding:10px;background:#f8f9fa;border-radius:6px;font-size:.88em"></div>
</div>

<div class="fs"><h3>9. Risks &amp; Challenges</h3>
<textarea id="sr_risks" rows="3" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">Airspace disruption affecting outbound travel.
No deterioration in ground security situation.</textarea>
</div>

<div class="fs"><h3>10. Overall Assessment</h3>
<textarea id="sr_assessment" rows="3" style="width:100%;padding:10px;border:1px solid var(--bd);border-radius:7px;font-size:.88em">No mass evacuation initiated.
No Kuwaiti advisory for mass departure.
No deterioration in ground security situation so far.</textarea>
</div>
</div></div>

<!-- ADMIN -->
<div id="tab-admin" class="tab"><div class="ctr">
<div class="fs"><h3>User Management</h3>
<div class="fg" style="margin-bottom:14px">
<div class="fgp"><label>Username</label><input id="nu_user"></div>
<div class="fgp"><label>Password</label><input id="nu_pass" type="password"></div>
<div class="fgp"><label>Full Name</label><input id="nu_name"></div>
<div class="fgp"><label>Role</label><select id="nu_role"><option>operator</option><option>admin</option><option>viewer</option></select></div>
</div>
<button class="btn btn-p" onclick="createUser()">Create User</button>
<div style="margin-top:14px"><table id="usersTbl"></table></div>
</div>
<div class="fs" style="border-left:3px solid var(--s)">
<h3>Public Registration Link</h3>
<p style="margin-bottom:10px;font-size:.88em;color:var(--tl)">Share this link with the public. Anyone can register through it — no login needed. Data goes directly into your dashboard.</p>
<div style="background:#f0f7f0;padding:14px;border-radius:8px;margin-bottom:12px">
<strong>Public Link:</strong> <code id="publicLink" style="font-size:1em;color:var(--p)"></code>
<button class="btn" style="padding:4px 12px;font-size:.8em;background:#eee;margin-left:8px" onclick="navigator.clipboard.writeText(document.getElementById('publicLink').textContent);toast('Link copied!')">Copy</button>
</div>
<div style="display:flex;align-items:center;gap:12px">
<label style="font-weight:600">Registration Status:</label>
<select id="regToggle" onchange="togglePublicReg()" style="padding:8px;border-radius:6px;border:1px solid var(--bd)">
<option value="enabled">Open (accepting registrations)</option>
<option value="disabled">Closed (show closed message)</option>
</select>
</div>
</div>
<div class="fs"><h3>Webhook / API Key</h3>
<p style="margin-bottom:10px;font-size:.88em;color:var(--tl)">Generate an API key for Microsoft Forms Power Automate integration.</p>
<button class="btn btn-w" onclick="genWebhookKey()">Generate New API Key</button>
<div id="webhookKeyDisplay" style="margin-top:10px;font-family:monospace;font-size:.9em"></div>
</div>
<div class="fs" style="border-left:3px solid #1565c0">
<h3>Bulk Visa Status Update</h3>
<p style="margin-bottom:10px;font-size:.88em;color:var(--tl)">Paste passport numbers (comma, newline, or semicolon separated) to bulk-update visa status. The system will <strong>automatically transition</strong> travel status too.</p>
<div class="fg" style="margin-bottom:10px">
<div class="fgp"><label>Passport Numbers</label><textarea id="bulkPassports" rows="4" placeholder="ML3955083, FJ5136551, PO5125521&#10;Or one per line..."></textarea></div>
<div class="fgp"><label>New Visa Status</label><select id="bulkStatus"><option>Approved</option><option>Pending</option><option>Rejected</option></select></div>
</div>
<button class="btn btn-p" onclick="bulkVisaUpdate()">Update All</button>
<div id="bulkResult" style="display:none;margin-top:12px"><div id="bulkStats"></div><div class="imp-result" id="bulkDetails"></div></div>
</div>
<div class="fs" style="border-left:3px solid var(--s)">
<h3>Backup &amp; Recovery</h3>
<p style="margin-bottom:10px;font-size:.88em;color:var(--tl)">Database is automatically backed up every 2 hours and on server start/stop. You can also create manual backups and restore from any point.</p>
<div class="bg" style="margin-bottom:14px">
<button class="btn btn-p" onclick="createBackup()">Create Backup Now</button>
</div>
<div id="backupList"></div>
</div>
<div class="fs"><h3>Change Your Password</h3>
<div class="fg"><div class="fgp"><label>New Password</label><input id="newPw" type="password"></div></div>
<button class="btn btn-p" style="margin-top:10px" onclick="changePw()">Change Password</button>
</div>
<div class="fs"><h3>Audit Log (Recent)</h3><div class="scroll-t"><table id="auditTbl"></table></div></div>
</div></div>

<!-- EDIT MODAL -->
<div class="mo" id="editModal"><div class="ml">
<button class="cb" onclick="closeEdit()">&times;</button>
<h3>Edit Record <span id="editId"></span></h3>
<form id="editForm" onsubmit="return saveEdit(event)">
<input type="hidden" id="e_id">
<div class="fg">
<div class="fgp"><label>Name</label><input id="e_name"></div>
<div class="fgp"><label>Passport</label><input id="e_passport"></div>
<div class="fgp"><label>CNIC</label><input id="e_cnic"></div>
<div class="fgp"><label>Gender</label><select id="e_gender"><option>Male</option><option>Female</option><option>Child</option></select></div>
<div class="fgp"><label>Country</label><select id="e_country"><option>Kuwait</option><option>Pakistan</option><option>KSA</option><option>Iraq</option><option>US</option><option>Bahrain</option><option>Qatar</option><option>Oman</option><option>UAE</option><option>Dubai</option></select></div>
<div class="fgp"><label>Mobile</label><input id="e_mobile"></div>
<div class="fgp"><label>Civil ID</label><input id="e_civil_id"></div>
<div class="fgp"><label>Email</label><input id="e_email"></div>
<div class="fgp"><label>Company</label><input id="e_company"></div>
<div class="fgp"><label>Border Crossing</label><input id="e_border_crossing"></div>
<div class="fgp"><label>KSA Visa Status</label><select id="e_visa_status"><option value="">Select</option><option>Approved</option><option>Pending</option><option>Rejected</option></select></div>
<div class="fgp"><label>Travel Status</label><select id="e_travel_status"><option>Pending</option><option>Visa Obtained</option><option>Departed</option></select></div>
<div class="fgp"><label>Airline</label><input id="e_airline"></div>
<div class="fgp"><label>Ticket Number</label><input id="e_ticket_number"></div>
<div class="fgp"><label>Departure Airport</label><input id="e_departure_airport"></div>
<div class="fgp"><label>Destination</label><input id="e_destination_country"></div>
<div class="fgp"><label>Date of Request</label><input type="date" id="e_date_of_request"></div>
<div class="fgp"><label>Priority</label><select id="e_priority"><option value="">Normal</option><option>High</option><option>Medium</option><option>Low</option></select></div>
<div class="fgp" style="grid-column:1/-1"><label>Remarks</label><textarea id="e_remarks" rows="2"></textarea></div>
</div>
<div class="bg">
<button type="submit" class="btn btn-p">Save Changes</button>
<button type="button" class="btn btn-d" onclick="delRecord()" data-admin-only>Delete</button>
<button type="button" class="btn" style="background:#eee" onclick="closeEdit()">Cancel</button>
</div></form></div></div>

<div class="toast" id="toast"></div>

<script>
let charts={},allRecords=[];
const F=['name','passport','cnic','gender','country','civil_id','border_crossing','mobile','company',
'visa_status','travel_status','airline','ticket_number','departure_airport','destination_country',
'date_of_request','email','dob','emergency_contact','medical','family_group_id','dependents',
'accommodation','priority','remarks'];

function go(tab,btn){
document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active'));
document.getElementById('tab-'+tab).classList.add('active');
btn.classList.add('active');
if(tab==='dash')loadDash();if(tab==='recs')loadRecords();if(tab==='mofa')loadMofaData();if(tab==='admin')loadAdmin();
}

async function api(url,opts){const r=await fetch(url,opts);if(r.status===302||r.redirected){window.location='/login';return null}return r.json()}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',3000)}

// DASHBOARD
async function loadDash(){
const d=await api('/api/stats');if(!d)return;
const k=d.kpi;
document.getElementById('kpiGrid').innerHTML=`
<div class="kc i"><div class="lb">Total Registered</div><div class="vl">${k.total}</div><div class="su">All evacuees</div></div>
<div class="kc s"><div class="lb">Departed</div><div class="vl">${k.departed}</div><div class="su">${k.total?(k.departed/k.total*100).toFixed(1):0}% of total</div></div>
<div class="kc i"><div class="lb">Visa Obtained</div><div class="vl">${k.visa_obtained}</div><div class="su">Awaiting travel</div></div>
<div class="kc d"><div class="lb">Pending Visa</div><div class="vl">${k.pending}</div><div class="su">Requires action</div></div>
<div class="kc s"><div class="lb">KSA Approved</div><div class="vl">${k.visa_approved}</div><div class="su">Mission KSA</div></div>
<div class="kc w"><div class="lb">Iraq Entries</div><div class="vl">${k.iraq_entries}</div><div class="su">Cross-border</div></div>`;
if(k.pending>k.visa_approved){document.getElementById('alertBar').style.display='flex';document.getElementById('alertText').textContent=`ALERT: Pending (${k.pending}) outpacing resolved (${k.visa_approved}) — urgent KSA action needed`}
else document.getElementById('alertBar').style.display='none';

// Charts
mkChart('c1','doughnut',{labels:['Departed','Visa Obtained','Pending'],datasets:[{data:[k.departed,k.visa_obtained,k.pending],backgroundColor:['#4caf50','#2196f3','#ff9800'],borderWidth:2}]},{plugins:{legend:{position:'bottom'}}});
const cn=d.by_country;
mkChart('c2','bar',{labels:cn.map(c=>c.country||'Unknown'),datasets:[{label:'Total',data:cn.map(c=>c.total),backgroundColor:'#1565c0'}]},{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}});
mkChart('c3','doughnut',{labels:d.by_gender.map(g=>g.gender||'Unknown'),datasets:[{data:d.by_gender.map(g=>g.count),backgroundColor:['#1565c0','#e91e63','#ff9800','#9e9e9e'],borderWidth:2}]},{plugins:{legend:{position:'bottom'}}});
const dd=d.by_date;let cum=0;const cumD=dd.map(x=>{cum+=x.new_requests;return cum});
mkChart('c4','bar',{labels:dd.map(x=>(x.date||'').slice(5)),datasets:[{type:'line',label:'Cumulative',data:cumD,borderColor:'#c62828',backgroundColor:'transparent',borderWidth:2,yAxisID:'y1',tension:.3},{label:'New',data:dd.map(x=>x.new_requests),backgroundColor:'#1565c0',yAxisID:'y'}]},{scales:{y:{beginAtZero:true,title:{display:true,text:'Daily'}},y1:{position:'right',beginAtZero:true,title:{display:true,text:'Cum.'},grid:{drawOnChartArea:false}}}});
mkChart('c5','pie',{labels:d.by_visa.map(v=>v.status),datasets:[{data:d.by_visa.map(v=>v.count),backgroundColor:['#4caf50','#ff9800','#f44336','#9e9e9e'],borderWidth:2}]},{plugins:{legend:{position:'bottom'}}});
mkChart('c6','bar',{labels:d.by_border.map(b=>b.border_crossing),datasets:[{label:'Count',data:d.by_border.map(b=>b.count),backgroundColor:'#006600'}]},{plugins:{legend:{display:false}},indexAxis:'y',scales:{x:{beginAtZero:true}}});

let thtml='<thead><tr><th>Country</th><th>Total</th><th>Departed</th><th>Visa</th><th>Pending</th><th>M</th><th>F</th><th>Ch</th><th>%</th></tr></thead><tbody>';
cn.forEach(c=>{thtml+=`<tr><td><strong>${c.country||'?'}</strong></td><td>${c.total}</td><td>${c.departed}</td><td>${c.visa_obtained}</td><td>${c.pending}</td><td>${c.males}</td><td>${c.females}</td><td>${c.children}</td><td>${(c.total/k.total*100).toFixed(1)}%</td></tr>`});
thtml+='</tbody>';document.getElementById('countryTbl').innerHTML=thtml;
}
function mkChart(id,type,data,opts){if(charts[id])charts[id].destroy();charts[id]=new Chart(document.getElementById(id),{type,data,options:{responsive:true,...opts}})}

// RECORDS
async function loadRecords(){
const p=new URLSearchParams();
const s=document.getElementById('sInput').value;if(s)p.set('search',s);
const st=document.getElementById('fStatus').value;if(st)p.set('status',st);
const co=document.getElementById('fCountry').value;if(co)p.set('country',co);
const ge=document.getElementById('fGender').value;if(ge)p.set('gender',ge);
const du=document.getElementById('fDup').value;if(du)p.set('dup',du);
allRecords=await api('/api/records?'+p.toString());if(!allRecords)return;
document.getElementById('recCount').textContent=`Showing ${allRecords.length} records`;
let h='<thead><tr><th>#</th><th>Name</th><th>Passport</th><th>Gender</th><th>Country</th><th>Mobile</th><th>Visa</th><th>Status</th><th>Date</th><th>Dup</th><th>MOFA</th><th>Edit</th></tr></thead><tbody>';
allRecords.forEach((r,i)=>{
const sb=r.travel_status==='Departed'?'bdg-dep':r.travel_status==='Pending'?'bdg-pen':'bdg-vis';
const vb=r.visa_status==='Approved'?'bdg-app':r.visa_status==='Rejected'?'bdg-rej':'bdg-pen';
const db=(!r.dup_flag||r.dup_flag==='CLEAR')?'bdg-clr':'bdg-dup';
const ms=r.mofa_status==='Sent to MOFA'?'<span class="bdg" style="background:#c8e6c9;color:#1b5e20;font-size:.7em">Sent</span>':'-';
h+=`<tr><td>${i+1}</td><td><strong>${r.name||''}</strong></td><td>${r.passport||''}</td><td>${r.gender||''}</td><td>${r.country||''}</td><td>${r.mobile||''}</td><td><span class="bdg ${vb}">${r.visa_status||'-'}</span></td><td><span class="bdg ${sb}">${r.travel_status||'-'}</span></td><td>${r.date_of_request||'-'}</td><td><span class="bdg ${db}">${r.dup_flag||'CLEAR'}</span></td><td>${ms}</td><td><button class="btn btn-i" style="padding:3px 8px;font-size:.75em" onclick="openEdit(${r.id})">Edit</button></td></tr>`;
});h+='</tbody>';document.getElementById('recTbl').innerHTML=h;
}

// REGISTER
async function doRegister(e){e.preventDefault();const fd=new FormData(e.target);const data={};fd.forEach((v,k)=>data[k]=v);
const r=await api('/api/record',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
if(r&&r.success){e.target.reset();toast(`Registered: ${data.name} (${r.dup_flag})`+(r.dup_details?.length?` — ${r.dup_details.join('; ')}`:''));loadDash()}
else toast('Error: '+(r?.error||'unknown'));return false}

// EDIT
function openEdit(id){const r=allRecords.find(x=>x.id===id);if(!r){toast('Record not found');return}
document.getElementById('e_id').value=id;document.getElementById('editId').textContent='#'+id;
F.forEach(f=>{const el=document.getElementById('e_'+f);if(el)el.value=r[f]||''});
document.getElementById('editModal').classList.add('show')}
function closeEdit(){document.getElementById('editModal').classList.remove('show')}
async function saveEdit(e){e.preventDefault();const data={id:parseInt(document.getElementById('e_id').value)};
F.forEach(f=>{const el=document.getElementById('e_'+f);if(el)data[f]=el.value});
const r=await api('/api/record',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
if(r&&r.success){closeEdit();loadRecords();loadDash();toast('Updated'+(r.dup_details?.length?' — '+r.dup_details.join('; '):''))}return false}
async function delRecord(){const id=parseInt(document.getElementById('e_id').value);
if(!confirm('Delete this record?'))return;
await api('/api/record/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
closeEdit();loadRecords();loadDash();toast('Deleted')}

// CSV UPLOAD
async function uploadCSV(){const file=document.getElementById('csvFile').files[0];if(!file){toast('Select a file');return}
const mode=document.getElementById('csvMode').value;
const fd=new FormData();fd.append('file',file);fd.append('mode',mode);
const r=await fetch('/api/upload-csv',{method:'POST',body:fd});const d=await r.json();
document.getElementById('importResult').style.display='block';
document.getElementById('importStats').innerHTML=`
<span class="stat-box stat-ok">Imported: ${d.imported||0}</span>
<span class="stat-box stat-skip">Skipped: ${d.skipped_dup||0}</span>
<span class="stat-box stat-upd">Updated: ${d.updated||0}</span>
<span class="stat-box stat-err">Errors: ${d.errors||0}</span>`;
document.getElementById('importDetails').textContent=(d.details||[]).join('\n');
loadDash();toast(`Import done: ${d.imported} new, ${d.skipped_dup} skipped, ${d.updated} updated`)}

// MOFA EXPORT
let mofaRecords=[];
async function loadMofaData(){
try{
const resp=await fetch('/api/mofa-pending');
const rows=await resp.json();
if(!rows||rows.error){console.log('MOFA load error:',rows);return}
mofaRecords=rows;
const selFrom=document.getElementById('mofaFrom');
const selTo=document.getElementById('mofaTo');
selFrom.innerHTML='';selTo.innerHTML='';
const newRecs=rows.filter(r=>!r.mofa_status||r.mofa_status===''||r.mofa_status==='New');
const sentRecs=rows.filter(r=>r.mofa_status==='Sent to MOFA');
newRecs.forEach(r=>{
selFrom.innerHTML+=`<option value="${r.id}">#${r.id} — ${r.name} (${r.passport})</option>`;
selTo.innerHTML+=`<option value="${r.id}">#${r.id} — ${r.name} (${r.passport})</option>`;
});
if(newRecs.length>0)selTo.value=newRecs[newRecs.length-1].id;
// Sent table
let sh='<thead><tr><th>#</th><th>Name</th><th>Passport</th><th>Border Entry</th><th>Status</th></tr></thead><tbody>';
sentRecs.forEach((r,i)=>{
sh+=`<tr><td>${r.id}</td><td>${r.name}</td><td>${r.passport}</td><td>${r.border_crossing||'-'}</td><td><span class="bdg" style="background:#c8e6c9;color:#1b5e20">Sent to MOFA</span></td></tr>`;
});
sh+=sentRecs.length?'</tbody>':`<tr><td colspan="5" style="text-align:center;color:var(--tl);padding:20px">No records sent to MOFA yet</td></tr></tbody>`;
document.getElementById('mofaSentTbl').innerHTML=sh;
document.getElementById('mofaStats').style.display='none';
document.getElementById('mofaTbl').innerHTML='';
document.getElementById('mofaActions').classList.add('hidden');
}catch(err){console.log('MOFA load exception:',err)}
}
function loadMofaPreview(){
const fromId=parseInt(document.getElementById('mofaFrom').value);
const toId=parseInt(document.getElementById('mofaTo').value);
if(fromId>toId){toast('From record must be before To record');return}
const filtered=mofaRecords.filter(r=>r.id>=fromId&&r.id<=toId&&(!r.mofa_status||r.mofa_status===''||r.mofa_status==='New'));
document.getElementById('mofaStats').style.display='block';
document.getElementById('mofaCount').textContent=filtered.length+' cases ready for MOFA';
document.getElementById('mofaRange').textContent=`Record #${fromId} to #${toId}`;
let h='<thead><tr><th>S.No</th><th>Record #</th><th>Name</th><th>Passport Number</th><th>Border Entry Point</th></tr></thead><tbody>';
filtered.forEach((r,i)=>{
h+=`<tr><td>${i+1}</td><td>${r.id}</td><td>${r.name}</td><td>${r.passport}</td><td>${r.border_crossing||'-'}</td></tr>`;
});
h+=filtered.length?'</tbody>':`<tr><td colspan="5" style="text-align:center;color:var(--tl);padding:20px">No new records in this range</td></tr></tbody>`;
document.getElementById('mofaTbl').innerHTML=h;
document.getElementById('mofaActions').classList.toggle('hidden',filtered.length===0);
}
function downloadMofa(){
const fromId=document.getElementById('mofaFrom').value;
const toId=document.getElementById('mofaTo').value;
window.open(`/api/mofa-export?from=${fromId}&to=${toId}`,'_blank');
}
async function markSentToMofa(){
try{
const fromId=parseInt(document.getElementById('mofaFrom').value);
const toId=parseInt(document.getElementById('mofaTo').value);
const filtered=mofaRecords.filter(r=>r.id>=fromId&&r.id<=toId&&(!r.mofa_status||r.mofa_status===''||r.mofa_status==='New'));
if(filtered.length===0){toast('No new records in this range');return}
if(!confirm('Mark '+filtered.length+' records (#'+fromId+' to #'+toId+') as Sent to MOFA? This cannot be undone.'))return;
const resp=await fetch('/api/mofa-mark-sent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({from_id:fromId,to_id:toId})});
const r=await resp.json();
if(r&&r.success){toast(r.count+' records marked as Sent to MOFA');await loadMofaData();loadMofaPreview()}
else{toast('Error: '+(r?.error||'Server returned error'));console.log('MOFA mark error:',r)}
}catch(err){toast('Error: '+err.message);console.log('MOFA mark exception:',err)}
}

// REPORT
async function genReport(){const d=await api('/api/stats');if(!d)return;
const k=d.kpi;const date=document.getElementById('repDate').value||new Date().toISOString().slice(0,10);
const fmtDate=new Date(date+'T00:00').toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'});
let h=`<div class="rp"><h1>EVACUATION SITREP</h1><h2>${fmtDate}</h2>
<div style="text-align:center;margin-bottom:16px"><strong>PAKISTAN EMBASSY KUWAIT</strong><br>CWA Kuwait</div>
<div class="rs"><h3>1. KEY METRICS</h3><table>
<tr><td>Total Registered</td><td style="text-align:right"><strong>${k.total}</strong></td></tr>
<tr><td>Total Departed</td><td style="text-align:right"><strong>${k.departed}</strong></td></tr>
<tr><td>Visa Obtained (Awaiting Travel)</td><td style="text-align:right"><strong>${k.visa_obtained}</strong></td></tr>
<tr><td>Pending Visas from Mission KSA</td><td style="text-align:right;color:#c62828"><strong>${k.pending}</strong></td></tr>
<tr><td>KSA Visa Approved</td><td style="text-align:right"><strong>${k.visa_approved}</strong></td></tr>
<tr><td>Entered from Iraq</td><td style="text-align:right"><strong>${k.iraq_entries}</strong></td></tr></table></div>
<div class="rs"><h3>2. BREAKDOWN BY COUNTRY</h3><table><thead><tr><th>Country</th><th>Total</th><th>Departed</th><th>Visa</th><th>Pending</th><th>M</th><th>F</th><th>Ch</th><th>%</th></tr></thead><tbody>`;
d.by_country.forEach(c=>{h+=`<tr><td>${c.country}</td><td>${c.total}</td><td>${c.departed}</td><td>${c.visa_obtained}</td><td>${c.pending}</td><td>${c.males}</td><td>${c.females}</td><td>${c.children}</td><td>${(c.total/k.total*100).toFixed(1)}%</td></tr>`});
h+=`</tbody></table></div><div class="rs"><h3>3. GENDER</h3><table><thead><tr><th>Gender</th><th>Count</th><th>Departed</th><th>%</th></tr></thead><tbody>`;
d.by_gender.forEach(g=>{h+=`<tr><td>${g.gender}</td><td>${g.count}</td><td>${g.departed}</td><td>${(g.count/k.total*100).toFixed(1)}%</td></tr>`});
h+=`</tbody></table></div><div class="rs"><h3>4. ASSESSMENT</h3><p>${k.pending>k.visa_approved?`<strong style="color:#c62828">ALERT:</strong> Pending (${k.pending}) outpacing resolved (${k.visa_approved}) — urgent KSA action required`:`Situation under control. Resolved (${k.visa_approved}) keeping pace with pending (${k.pending}).`}</p></div>
<div style="margin-top:30px;padding-top:15px;border-top:1px solid #ccc;font-size:.82em;color:#777"><p>Generated: ${new Date().toLocaleString()}<br>Pakistan Embassy Kuwait - Evacuation Management System</p></div></div>`;
document.getElementById('repContent').innerHTML=h}

// ADMIN
async function loadAdmin(){
const u=await api('/api/users');
if(u&&!u.error){let h='<thead><tr><th>Username</th><th>Full Name</th><th>Role</th><th>Created</th></tr></thead><tbody>';
u.forEach(x=>{h+=`<tr><td>${x.username}</td><td>${x.full_name||'-'}</td><td>${x.role}</td><td>${x.created_at}</td></tr>`});
h+='</tbody>';document.getElementById('usersTbl').innerHTML=h}
const a=await api('/api/audit');
if(a&&!a.error){let h='<thead><tr><th>Time</th><th>Action</th><th>User</th><th>Record</th></tr></thead><tbody>';
a.slice(0,50).forEach(x=>{h+=`<tr><td>${x.created_at}</td><td>${x.action}</td><td>${x.user||'-'}</td><td>${x.record_id||'-'}</td></tr>`});
h+='</tbody>';document.getElementById('auditTbl').innerHTML=h}
loadBackups()}
async function createUser(){
const data={username:document.getElementById('nu_user').value,password:document.getElementById('nu_pass').value,
full_name:document.getElementById('nu_name').value,role:document.getElementById('nu_role').value};
if(!data.username||!data.password){toast('Username and password required');return}
const r=await api('/api/user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
if(r?.success){toast('User created');loadAdmin()}else toast('Error: '+(r?.error||'unknown'))}
async function genWebhookKey(){
const r=await api('/api/generate-webhook-key',{method:'POST'});
if(r?.key){const url=window.location.origin+'/api/webhook/forms?key='+r.key;
document.getElementById('webhookKeyDisplay').innerHTML=`<strong>API Key:</strong> ${r.key}<br><strong>Webhook URL:</strong> <code>${url}</code>`;
document.getElementById('webhookUrl').textContent=url;toast('Key generated')}}
// PUBLIC REGISTRATION TOGGLE
document.getElementById('publicLink').textContent=window.location.origin+'/embassy-registration';
async function togglePublicReg(){const val=document.getElementById('regToggle').value;
await api('/api/setting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'public_registration',value:val})});
toast('Public registration '+(val==='enabled'?'OPENED':'CLOSED'))}
async function changePw(){const pw=document.getElementById('newPw').value;if(!pw){toast('Enter password');return}
await api('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_password:pw})});
document.getElementById('newPw').value='';toast('Password changed')}

// BULK VISA UPDATE
async function bulkVisaUpdate(){
const pp=document.getElementById('bulkPassports').value;if(!pp.trim()){toast('Enter passport numbers');return}
const st=document.getElementById('bulkStatus').value;
const r=await api('/api/bulk-visa-update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passports:pp,status:st})});
if(r){document.getElementById('bulkResult').style.display='block';
document.getElementById('bulkStats').innerHTML=`<span class="stat-box stat-ok">Updated: ${r.updated||0}</span><span class="stat-box stat-err">Not Found: ${r.not_found||0}</span>${r.workflow_changes?.length?'<span class="stat-box stat-upd">Auto-transitions: '+r.workflow_changes.length+'</span>':''}`;
document.getElementById('bulkDetails').textContent=(r.details||[]).join('\n');
loadDash();toast(`Updated ${r.updated} records`)}}

// BACKUP
async function createBackup(){const r=await api('/api/backup',{method:'POST'});if(r?.success){toast('Backup created');loadBackups()}}
async function loadBackups(){const r=await api('/api/backups');if(!r||r.error)return;
let h='<table><thead><tr><th>Backup</th><th>Size</th><th>Date</th><th>Action</th></tr></thead><tbody>';
r.forEach(b=>{h+=`<tr><td>${b.name}</td><td>${(b.size/1024).toFixed(0)} KB</td><td>${b.date}</td><td><button class="btn btn-w" style="padding:3px 8px;font-size:.75em" onclick="restoreBackup('${b.name}')">Restore</button></td></tr>`});
h+='</tbody></table>';document.getElementById('backupList').innerHTML=h}
async function restoreBackup(name){if(!confirm('Restore from '+name+'? Current data will be backed up first.')){return}
const r=await api('/api/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
if(r?.success){toast('Restored successfully');loadDash();loadRecords()}else toast('Restore failed: '+(r?.error||'unknown'))}

// SITREP EDITOR
async function loadSitrepData(){
const d=await api('/api/stats');if(!d)return;
const k=d.kpi;const now=new Date();
document.getElementById('sr_date').value=now.toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'})+' ('+now.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})+')';
document.getElementById('sr_registered').value=k.total+' (Departed: '+k.departed+', Visa Obtained: '+k.visa_obtained+', Pending: '+k.pending+')';
document.getElementById('sr_evac_requested').value=k.total+' persons registered for evacuation assistance';
let evac='Total Registered: '+k.total+'\nDeparted: '+k.departed+'\nVisa Obtained: '+k.visa_obtained+'\nPending KSA Visa: '+k.pending+'\nKSA Visa Approved: '+k.visa_approved+'\n\nBreakdown by Country:\n';
d.by_country.forEach(c=>{evac+=c.country+': '+c.total+' (Departed: '+c.departed+', Pending: '+c.pending+')\n'});
evac+='\nGender:\n';d.by_gender.forEach(g=>{evac+=g.gender+': '+g.count+' (Departed: '+g.departed+')\n'});
document.getElementById('sr_evac_status').innerText=evac;
toast('SITREP data refreshed')}

async function downloadSitrepDocx(){
const data={date:document.getElementById('sr_date').value,country:document.getElementById('sr_country').value,
hotline:document.getElementById('sr_hotline').value,stranded:document.getElementById('sr_stranded').value,
situation:document.getElementById('sr_situation').value,diaspora_num:document.getElementById('sr_diaspora_num').value,
diaspora_loc:document.getElementById('sr_diaspora_loc').value,registered:document.getElementById('sr_registered').value,
evac_requested:document.getElementById('sr_evac_requested').value,airspace:document.getElementById('sr_airspace').value,
airport:document.getElementById('sr_airport').value,notam:document.getElementById('sr_notam').value,
land:document.getElementById('sr_land').value,facilitation:document.getElementById('sr_facilitation').value,
coordination:document.getElementById('sr_coordination').value,evac_air:document.getElementById('sr_evac_air').value,
evac_land:document.getElementById('sr_evac_land').value,evac_status:document.getElementById('sr_evac_status').innerText,
risks:document.getElementById('sr_risks').value,assessment:document.getElementById('sr_assessment').value};
const r=await fetch('/api/generate-sitrep-docx',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
if(r.ok){const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);
a.download='SITREP_'+new Date().toISOString().slice(0,10)+'.docx';a.click();toast('SITREP downloaded')}
else toast('Generation failed')}

// ROLE-BASED ACCESS CONTROL
const USER_ROLE='__USER_ROLE__';
const USER_NAME='__USER_NAME__';
function applyRoleRestrictions(){
document.getElementById('userDisplay').textContent=USER_NAME+' ('+USER_ROLE+')';
// Viewer: can only see dashboard and reports
if(USER_ROLE==='viewer'){
document.querySelectorAll('.nav button').forEach(b=>{
const tab=b.textContent.trim();
if(['New Registration','CSV Import','MOFA Export','Admin'].includes(tab)){b.style.display='none'}});
document.querySelectorAll('.btn-d').forEach(b=>b.style.display='none');// hide delete buttons
}
// Operator: can register, import, edit, but NOT delete data, export, or manage users
if(USER_ROLE==='operator'){
document.querySelectorAll('.nav button').forEach(b=>{
const tab=b.textContent.trim();
if(tab==='Admin')b.style.display='none'});
// Hide dangerous buttons
document.querySelectorAll('[data-admin-only]').forEach(el=>el.style.display='none');
}
// Admin: full access (nothing hidden)
}

// INIT
document.getElementById('repDate').value=new Date().toISOString().slice(0,10);
document.getElementById('sr_date').value=new Date().toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'});
applyRoleRestrictions();
loadDash();
setTimeout(loadSitrepData,1000);

// Auto-refresh dashboard every 30s
setInterval(()=>{if(document.getElementById('tab-dash').classList.contains('active'))loadDash()},30000);
</script></body></html>"""

# ═══════════════════════════════════════════════════════════════
# START SERVER
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    init_db()
    BACKUP_DIR.mkdir(exist_ok=True)
    do_backup('startup')
    # Start auto-backup thread
    backup_thread = threading.Thread(target=auto_backup_scheduler, daemon=True)
    backup_thread.start()
    print(f"""
╔══════════════════════════════════════════════════════════╗
║   EVACUATION MANAGEMENT SYSTEM                          ║
║   Pakistan Embassy Kuwait                               ║
║                                                         ║
║   Server running on: http://localhost:{PORT}              ║
║                                                         ║
║   Default login:                                        ║
║     Username: admin                                     ║
║     Password: embassy2026                               ║
║                                                         ║
║   Features:                                             ║
║   - Auto-backup every 2 hours (./backups/)              ║
║   - Workflow: visa approved → auto-updates status       ║
║   - Backup on every startup                             ║
║                                                         ║
║   Press Ctrl+C to stop                                  ║
╚══════════════════════════════════════════════════════════╝
""")
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCreating shutdown backup...")
        do_backup('shutdown')
        print("Server stopped.")
        server.server_close()
