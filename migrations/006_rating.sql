CREATE TABLE rating_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_key TEXT NOT NULL, user_id INTEGER NOT NULL, stars INTEGER NOT NULL, comment TEXT, status TEXT DEFAULT 'visible', created_at TEXT, updated_at TEXT, UNIQUE(entity_key, user_id));
CREATE TABLE rating_likes(review_id INTEGER, user_id INTEGER, PRIMARY KEY(review_id, user_id));
CREATE TABLE rating_reports(review_id INTEGER, user_id INTEGER, reason TEXT, created_at TEXT, PRIMARY KEY(review_id, user_id));
CREATE INDEX idx_rr_entity ON rating_reviews(entity_key, status);
