ALTER TABLE complaints ADD COLUMN anonymous INTEGER DEFAULT 0;
ALTER TABLE complaints ADD COLUMN severity INTEGER;
ALTER TABLE complaints ADD COLUMN confidence REAL;
ALTER TABLE complaints ADD COLUMN safety_risk TEXT;
ALTER TABLE complaints ADD COLUMN emergency INTEGER DEFAULT 0;
ALTER TABLE complaints ADD COLUMN duplicate_group INTEGER;
ALTER TABLE complaints ADD COLUMN photo_public_ok INTEGER DEFAULT 0;
ALTER TABLE complaints ADD COLUMN after_photo_url TEXT;
ALTER TABLE complaints ADD COLUMN reopened INTEGER DEFAULT 0;
ALTER TABLE complaints ADD COLUMN lang TEXT DEFAULT 'en';
ALTER TABLE complaints ADD COLUMN official_basis TEXT DEFAULT 'none';
ALTER TABLE complaints ADD COLUMN routing_json TEXT;
ALTER TABLE complaints ADD COLUMN needs_human INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN deleted INTEGER DEFAULT 0;
CREATE TABLE ai_analysis(id INTEGER PRIMARY KEY, complaint_id INTEGER, ts TEXT, engine TEXT, category TEXT, confidence REAL, severity INTEGER, safety_risk TEXT, emergency INTEGER, suggested_department TEXT, notes TEXT);
CREATE TABLE duplicate_groups(id INTEGER PRIMARY KEY, parent_complaint_id INTEGER, lat REAL, lon REAL, category TEXT, created_at TEXT);
CREATE TABLE supports(id INTEGER PRIMARY KEY, complaint_id INTEGER, user_id INTEGER, kind TEXT, ts TEXT, UNIQUE(complaint_id,user_id,kind));
CREATE TABLE admin_users(id INTEGER PRIMARY KEY, name TEXT, token TEXT UNIQUE, role TEXT, scope_state TEXT, scope_city TEXT, department TEXT, created_at TEXT);
CREATE TABLE authorities(id INTEGER PRIMARY KEY, name TEXT, type TEXT, state TEXT, district TEXT, city TEXT, categories TEXT, grievance_url TEXT, grievance_email TEXT, helpline TEXT, escalation_to INTEGER, verified INTEGER DEFAULT 0, last_verified TEXT, source_url TEXT);
CREATE TABLE representatives(id INTEGER PRIMARY KEY, name TEXT, office TEXT, constituency TEXT, state TEXT, city TEXT, public_contact TEXT, profile_url TEXT, verified INTEGER DEFAULT 0, last_verified TEXT, source_url TEXT);
CREATE TABLE escalation_policy(level INTEGER PRIMARY KEY, name TEXT, description TEXT, after_days_factor REAL DEFAULT 1.0);
CREATE TABLE escalation_records(id INTEGER PRIMARY KEY, complaint_id INTEGER, ts TEXT, level INTEGER, platform_id TEXT, action TEXT, note TEXT);
CREATE TABLE verifications(id INTEGER PRIMARY KEY, complaint_id INTEGER, ts TEXT, kind TEXT, photo_url TEXT, note TEXT, user_id INTEGER);
CREATE TABLE otps(phone TEXT PRIMARY KEY, code_hash TEXT, expires TEXT, attempts INTEGER DEFAULT 0);
CREATE INDEX idx_c_geo ON complaints(lat,lon);
CREATE INDEX idx_c_status ON complaints(status);
CREATE INDEX idx_ext_c ON external_records(complaint_id);
INSERT INTO escalation_policy VALUES
 (1,'Primary responsible authority','Initial official complaint',1.0),
 (2,'Department grievance officer','Reminder through a verified channel',1.0),
 (3,'Senior departmental authority','Second reminder / senior officer',1.5),
 (4,'District-level administrative authority','Where jurisdiction justifies',2.0),
 (5,'State grievance portal or nodal authority','Guided submission',2.5),
 (6,'Eligible central grievance / appeal channel','Only where jurisdiction permits (e.g. CPGRAMS appeal)',3.0),
 (7,'Further lawful remedies and RTI assistance','Information only, no legal advice',4.0);
