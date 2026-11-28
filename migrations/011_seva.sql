-- Phase 2 (Seva Setu India): citizen platform schema. Additive; existing complaint tables untouched.
CREATE TABLE IF NOT EXISTS citizen_profiles(
  user_id INTEGER PRIMARY KEY REFERENCES users(id),
  preferred_lang TEXT DEFAULT 'hi',
  state TEXT, district TEXT, block TEXT, address TEXT, pincode TEXT,
  age_group TEXT, occupation TEXT, a11y TEXT DEFAULT '{}',
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS operators(
  id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
  display_name TEXT, phone TEXT, status TEXT DEFAULT 'pending',
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS operator_verifications(
  id INTEGER PRIMARY KEY, operator_id INTEGER REFERENCES operators(id),
  doc_type TEXT, status TEXT DEFAULT 'pending', note TEXT,
  verified_by TEXT, verified_at TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS departments(
  id INTEGER PRIMARY KEY, name TEXT, level TEXT, state TEXT);
CREATE TABLE IF NOT EXISTS seva_states(code TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS seva_districts(id INTEGER PRIMARY KEY, state_code TEXT, name TEXT);
CREATE TABLE IF NOT EXISTS service_categories(
  id TEXT PRIMARY KEY, icon TEXT, names TEXT, blurb TEXT, links TEXT,
  online TEXT, docs TEXT, complaint INTEGER DEFAULT 0, verified TEXT, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS services(
  id INTEGER PRIMARY KEY, category_id TEXT REFERENCES service_categories(id),
  name TEXT, dept TEXT, state TEXT, data TEXT, verified TEXT);
CREATE TABLE IF NOT EXISTS schemes(
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE, name TEXT, names TEXT, benefit TEXT,
  eligibility TEXT, docs TEXT, link TEXT, source TEXT, last_verified TEXT,
  state TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS scheme_eligibility(
  id INTEGER PRIMARY KEY, scheme_id INTEGER REFERENCES schemes(id), field TEXT, rule TEXT);
CREATE TABLE IF NOT EXISTS seva_documents(
  id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
  kind TEXT, filename TEXT, mime TEXT, size INTEGER, storage_key TEXT, sha256 TEXT,
  created_at TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS document_access_logs(
  id INTEGER PRIMARY KEY, document_id INTEGER, actor TEXT, actor_role TEXT,
  action TEXT, consent_id INTEGER, ts TEXT);
CREATE TABLE IF NOT EXISTS applications(
  id INTEGER PRIMARY KEY, ref_no TEXT UNIQUE, user_id INTEGER REFERENCES users(id),
  category_id TEXT, service_id INTEGER, title TEXT,
  status TEXT DEFAULT 'request_received',
  official_ack_no TEXT, next_action TEXT, assigned_operator INTEGER,
  created_at TEXT, updated_at TEXT);
CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE TABLE IF NOT EXISTS application_documents(
  id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES applications(id),
  document_id INTEGER, label TEXT, status TEXT DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS application_status_history(
  id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES applications(id),
  status TEXT, note TEXT, actor TEXT, ts TEXT);
CREATE INDEX IF NOT EXISTS idx_ash_app ON application_status_history(application_id);
CREATE TABLE IF NOT EXISTS government_submissions(
  id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES applications(id),
  portal TEXT, method TEXT, ack_no TEXT, receipt_url TEXT,
  submitted_by TEXT, verified INTEGER DEFAULT 0, ts TEXT);
CREATE TABLE IF NOT EXISTS user_notifications(
  id INTEGER PRIMARY KEY, user_id INTEGER, application_id INTEGER,
  kind TEXT, channel TEXT, body TEXT, status TEXT DEFAULT 'queued', ts TEXT);
CREATE INDEX IF NOT EXISTS idx_un_user ON user_notifications(user_id);
CREATE TABLE IF NOT EXISTS whatsapp_messages(
  id INTEGER PRIMARY KEY, direction TEXT, wa_id TEXT, phone TEXT,
  template TEXT, body TEXT, status TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS consent_records(
  id INTEGER PRIMARY KEY, user_id INTEGER, application_id INTEGER,
  scope TEXT, granted INTEGER, text_version TEXT, ts TEXT, revoked_at TEXT);
CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_records(user_id);
CREATE TABLE IF NOT EXISTS seva_translations(
  id INTEGER PRIMARY KEY, key TEXT, lang TEXT, text TEXT,
  status TEXT DEFAULT 'draft', updated_at TEXT, UNIQUE(key, lang));
CREATE TABLE IF NOT EXISTS support_tickets(
  id INTEGER PRIMARY KEY, user_id INTEGER, subject TEXT, body TEXT,
  status TEXT DEFAULT 'open', created_at TEXT, updated_at TEXT);
