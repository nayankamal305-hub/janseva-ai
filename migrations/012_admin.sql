-- Phase 6 (Seva Setu India): admin dashboard. Additive; existing tables untouched.
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT, updated_at TEXT, updated_by TEXT);
CREATE TABLE IF NOT EXISTS citizen_flags(
  user_id INTEGER PRIMARY KEY, flag TEXT, reason TEXT,
  created_by TEXT, created_at TEXT);
