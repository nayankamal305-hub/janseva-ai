CREATE TABLE wa_login(id TEXT PRIMARY KEY, code TEXT UNIQUE, poll_hash TEXT, created TEXT, expires TEXT, phone TEXT, verified_at TEXT, token_taken INTEGER DEFAULT 0);
