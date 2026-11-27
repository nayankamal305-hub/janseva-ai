ALTER TABLE complaints ADD COLUMN consent_x INTEGER DEFAULT 0;
CREATE TABLE x_queue(id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id INTEGER UNIQUE, text TEXT NOT NULL, handles TEXT, text_hash TEXT UNIQUE, status TEXT DEFAULT 'queued', tweet_url TEXT, created_at TEXT, picked_at TEXT, posted_at TEXT, error TEXT);
