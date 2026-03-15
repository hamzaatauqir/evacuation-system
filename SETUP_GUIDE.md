# Evacuation Management System - Setup Guide
## Pakistan Embassy Kuwait

---

## Quick Start (Local - 30 seconds)

```bash
# Just run this one command:
python3 server.py

# Open browser: http://localhost:8080
# Login: admin / embassy2026
```

**No dependencies needed** - uses only Python standard library.

---

## Deploy Online (So Your Boss Can Access It)

### Option 1: Render.com (Free, Recommended)

1. Create account at https://render.com
2. Click "New → Web Service"
3. Upload or connect your GitHub repo with `server.py`
4. Settings:
   - Runtime: Python 3
   - Build Command: (leave empty)
   - Start Command: `python3 server.py`
   - Environment Variable: `PORT = 10000`
5. Click "Deploy"
6. Share the URL (e.g. `https://your-app.onrender.com`) with your boss

### Option 2: Railway.app (Free tier)

1. Create account at https://railway.app
2. New Project → Deploy from GitHub or upload files
3. Add environment variable: `PORT = 8080`
4. Deploy — get a public URL

### Option 3: Any VPS (DigitalOcean, AWS, etc.)

```bash
# On your server:
scp server.py user@your-server:/opt/evacuation/
ssh user@your-server

# Run with nohup so it stays running:
cd /opt/evacuation
nohup python3 server.py &

# Or use systemd for auto-restart:
sudo tee /etc/systemd/system/evacuation.service << EOF
[Unit]
Description=Evacuation Management System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/evacuation
ExecStart=/usr/bin/python3 server.py
Restart=always
Environment=PORT=8080

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable evacuation
sudo systemctl start evacuation
```

---

## User Accounts

After first login as admin, create accounts for your team:

| Role     | Can Do                                       |
|----------|----------------------------------------------|
| admin    | Everything + manage users + webhook keys     |
| operator | Register, edit records, import CSV, reports   |
| viewer   | View dashboard and records only               |

---

## Microsoft Forms Auto-Sync

### Method 1: Power Automate (Fully Automatic)

1. Go to https://flow.microsoft.com
2. Create new flow → "Automated cloud flow"
3. Trigger: **"When a new response is submitted"** (Microsoft Forms)
4. Select your form
5. Add action: **"Get response details"**
6. Add action: **"HTTP"**
   - Method: POST
   - URI: `https://your-server.com/api/webhook/forms?key=YOUR_API_KEY`
   - Headers: Content-Type: application/json
   - Body:
   ```json
   {
     "name": "@{outputs('Get_response_details')?['body/Full_Name']}",
     "passport": "@{outputs('Get_response_details')?['body/Passport_Number']}",
     "gender": "@{outputs('Get_response_details')?['body/Gender']}",
     "country": "@{outputs('Get_response_details')?['body/Country_Resident']}",
     "civil_id": "@{outputs('Get_response_details')?['body/Civil_ID']}",
     "border_crossing": "@{outputs('Get_response_details')?['body/Border_Crossing']}",
     "mobile": "@{outputs('Get_response_details')?['body/Mobile_Number']}",
     "company": "@{outputs('Get_response_details')?['body/Profession']}",
     "cnic": "@{outputs('Get_response_details')?['body/CNIC']}",
     "email": "@{outputs('Get_response_details')?['body/Email_Address']}",
     "travel_status": "Pending"
   }
   ```
7. Save and test

### Method 2: Manual CSV Upload

1. Open Microsoft Forms → your form → Responses tab
2. Click "Open in Excel" → Save as CSV
3. Log into dashboard → CSV Import tab
4. Upload the CSV — duplicates are handled automatically

---

## CSV Import Duplicate Modes

| Mode              | Behavior                                        |
|-------------------|-------------------------------------------------|
| Smart (default)   | Skip exact duplicates, update partial matches   |
| Skip All          | Skip any record with matching passport          |
| Force Import      | Import everything, flag duplicates              |

The system checks duplicates by: **Passport Number** (primary), **CNIC**, and **Name**.

---

## Security Notes

- Change the default admin password immediately after first login
- Use HTTPS in production (Render/Railway provide this automatically)
- Generate a new webhook API key periodically
- Database is stored in `evacuation.db` — back this file up regularly

---

## Backup & Restore

```bash
# Backup
cp evacuation.db evacuation_backup_$(date +%Y%m%d).db

# Or export CSV from the dashboard: Records tab → Export CSV
```
