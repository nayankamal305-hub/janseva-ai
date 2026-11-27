CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, phone TEXT UNIQUE, name TEXT, token TEXT UNIQUE, role TEXT DEFAULT 'citizen', created_at TEXT);
CREATE TABLE IF NOT EXISTS complaints(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE, user_id INTEGER, title TEXT, description TEXT, category TEXT,
  lat REAL, lon REAL, address TEXT, city TEXT, state TEXT, district TEXT, ward TEXT, pincode TEXT,
  photo_url TEXT, asset_owner TEXT, ulb_id TEXT, status TEXT DEFAULT 'draft',
  consent_submit INTEGER DEFAULT 0, consent_share_personal INTEGER DEFAULT 0, notify_representative INTEGER DEFAULT 0,
  citizen_verified INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS external_records(
  id INTEGER PRIMARY KEY, complaint_id INTEGER, platform_id TEXT, department TEXT, level INTEGER, mode TEXT,
  method TEXT, external_ref TEXT, status TEXT, latest_update TEXT, tracking_url TEXT,
  submitted_at TEXT, acknowledged_at TEXT, last_sync_at TEXT, evidence TEXT, reference_source TEXT, terminal INTEGER DEFAULT 0,
  UNIQUE(complaint_id, platform_id));
CREATE TABLE IF NOT EXISTS timeline(id INTEGER PRIMARY KEY, complaint_id INTEGER, ts TEXT, source TEXT, kind TEXT, message TEXT, external_record_id INTEGER);
CREATE TABLE IF NOT EXISTS integration_log(id INTEGER PRIMARY KEY, ts TEXT, platform_id TEXT, complaint_id INTEGER, action TEXT, ok INTEGER, http_code INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, ts TEXT, actor TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, complaint_id INTEGER, ts TEXT, audience TEXT, channel TEXT, target TEXT, status TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS platforms(id TEXT PRIMARY KEY, data TEXT NOT NULL, approval_status TEXT, last_verified TEXT, admin_owner TEXT);
