ALTER TABLE complaints ADD COLUMN consent_email INTEGER DEFAULT 0;
ALTER TABLE complaints ADD COLUMN constituency TEXT;
ALTER TABLE complaints ADD COLUMN reply_to_user INTEGER DEFAULT 0;
ALTER TABLE complaints ADD COLUMN company TEXT;
CREATE TABLE dispatches(id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id INTEGER, level INTEGER, kind TEXT, target_name TEXT, target_email TEXT, source_url TEXT, source_date TEXT,
  tier TEXT, status TEXT, due_at TEXT, sent_at TEXT, error TEXT, UNIQUE(complaint_id, target_email, kind));
CREATE INDEX idx_disp_due ON dispatches(status, due_at);
