#!/usr/bin/env python3
"""
Run this ONCE before starting the server to pre-load all your existing data.
Usage: python3 preload_data.py
"""
import sys, os, json
from pathlib import Path

# Set up DB path
sys.path.insert(0, str(Path(__file__).parent))
import server
server.DB_PATH = Path(__file__).parent / 'evacuation.db'

from server import init_db, import_csv_data, get_db, check_duplicates

print("Initializing database...")
init_db()

db = get_db()
existing = db.execute("SELECT COUNT(*) c FROM evacuees").fetchone()['c']
if existing > 0:
    resp = input(f"Database already has {existing} records. Clear and reimport? (y/N): ")
    if resp.lower() != 'y':
        print("Aborted.")
        db.close()
        sys.exit(0)
    db.execute("DELETE FROM evacuees")
    db.commit()
    print("Cleared existing data.")

# Step 1: Import Excel data (your master sheet)
excel_file = Path(__file__).parent / 'excel_data.json'
if excel_file.exists():
    with open(excel_file) as f:
        excel_data = json.load(f)

    field_map = {'civilId':'civil_id','borderCrossing':'border_crossing','visaStatus':'visa_status',
                 'travelStatus':'travel_status','ticketNumber':'ticket_number','departureAirport':'departure_airport',
                 'destinationCountry':'destination_country','dateOfRequest':'date_of_request','dupFlag':'dup_flag'}
    valid_cols = ['name','passport','cnic','gender','country','civil_id','border_crossing','mobile',
                  'company','visa_status','travel_status','airline','ticket_number','departure_airport',
                  'destination_country','date_of_request','dup_flag']

    count = 0
    for r in excel_data:
        rec = {}
        for k, v in r.items():
            db_key = field_map.get(k, k)
            if db_key in valid_cols and v:
                rec[db_key] = v
        if not rec.get('name'): continue
        cols = list(rec.keys())
        vals = [rec[c] for c in cols]
        db.execute(f"INSERT INTO evacuees ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals)
        count += 1
    db.commit()
    print(f"Imported {count} records from Excel master sheet")
else:
    print("No excel_data.json found, skipping Excel import")

db.close()

# Step 2: Import Microsoft Forms CSV
csv_file = Path(__file__).parent / 'forms_data.csv'
if csv_file.exists():
    with open(csv_file, encoding='latin-1') as f:
        csv_text = f.read()
    stats = import_csv_data(csv_text, 'preload', 'smart')
    print(f"CSV Import: {stats['imported']} new, {stats['skipped_dup']} skipped, {stats['updated']} updated, {stats['errors']} errors")
else:
    print("No forms_data.csv found, skipping CSV import")

# Final summary
db = get_db()
total = db.execute("SELECT COUNT(*) c FROM evacuees").fetchone()['c']
dups = db.execute("SELECT COUNT(*) c FROM evacuees WHERE dup_flag='DUPLICATE'").fetchone()['c']
print(f"\nDone! Database has {total} records ({dups} flagged as duplicates)")
print("Start the server with: python3 server.py")
db.close()
