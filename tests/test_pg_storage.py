import datetime as dt, os, tempfile, threading, unittest, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from app.db import pg_sql, pg_migration, DB
from app import storage

class TestSqlTranslation(unittest.TestCase):
    def test_placeholders_like_ignore(self):
        self.assertEqual(pg_sql("SELECT * FROM t WHERE a=? AND b LIKE ?"), "SELECT * FROM t WHERE a=%s AND b ILIKE %s")
        self.assertEqual(pg_sql("INSERT OR IGNORE INTO supports(a,b) VALUES(?,?)"), "INSERT INTO supports(a,b) VALUES(%s,%s) ON CONFLICT DO NOTHING")
    def test_replace_uses_conflict_target(self):
        q = pg_sql("INSERT OR REPLACE INTO otps(phone,code_hash,expires,attempts) VALUES(?,?,?,0)")
        self.assertIn("ON CONFLICT (phone) DO UPDATE SET code_hash=EXCLUDED.code_hash", q); self.assertNotIn("phone=EXCLUDED", q)
        q = pg_sql("INSERT OR REPLACE INTO external_records(complaint_id,platform_id,status) VALUES(?,?,?)")
        self.assertIn("ON CONFLICT (complaint_id, platform_id) DO UPDATE SET status=EXCLUDED.status", q)
    def test_percent_escaped(self):
        self.assertIn("100%%", pg_sql("SELECT '100%' x WHERE a=?"))
    def test_migration_dialect(self):
        m = pg_migration("CREATE TABLE a(id INTEGER PRIMARY KEY AUTOINCREMENT, lat REAL, n INTEGER);")
        self.assertIn("SERIAL PRIMARY KEY", m); self.assertIn("DOUBLE PRECISION", m); self.assertNotIn("AUTOINCREMENT", m)

@unittest.skipUnless(os.environ.get("DATABASE_URL", "").startswith("postgres"), "set DATABASE_URL to run against Postgres")
class TestPostgresLive(unittest.TestCase):
    def test_roundtrip_and_upsert(self):
        os.environ["JANSEVA_PG_ISOLATE"] = "1"
        db = DB()
        self.assertTrue(db.pg)
        a = db.run("INSERT INTO audit_log(ts,actor,action,detail) VALUES(?,?,?,?)", ("t", "x", "y", "z")); b = db.run("INSERT INTO audit_log(ts,actor,action,detail) VALUES(?,?,?,?)", ("t", "x", "y", "z"))
        self.assertEqual(b, a + 1)
        db.run("INSERT OR REPLACE INTO otps(phone,code_hash,expires,attempts) VALUES(?,?,?,0)", ("1", "a", "e")); db.run("INSERT OR REPLACE INTO otps(phone,code_hash,expires,attempts) VALUES(?,?,?,0)", ("1", "b", "e"))
        self.assertEqual(db.one("SELECT code_hash FROM otps WHERE phone=?", ("1",))["code_hash"], "b")
        r = db.one("SELECT ROUND(AVG(5),2) avg, (1=1) mine")
        self.assertEqual((r["avg"], r["mine"]), (5.0, 1))

class TestSigV4(unittest.TestCase):
    def test_aws_published_vector(self):
        h = storage.sigv4_headers("GET", "https://example.amazonaws.com/", {"Host": "example.amazonaws.com"}, b"", "AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "us-east-1", "service", dt.datetime(2015, 8, 30, 12, 36, 0, tzinfo=dt.timezone.utc))
        self.assertTrue(h["Authorization"].endswith("Signature=5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"))

class FakeS3(BaseHTTPRequestHandler):
    store = {}
    def log_message(self, *a): pass
    def _ok(self): return self.headers.get("Authorization", "").startswith("AWS4-HMAC-SHA256 Credential=AK/") and "x-amz-content-sha256" in self.headers
    def do_PUT(self):
        n = int(self.headers.get("Content-Length", 0)); d = self.rfile.read(n)
        if not self._ok(): self.send_response(403); self.end_headers(); return
        FakeS3.store[self.path] = d; self.send_response(200); self.end_headers()
    def do_GET(self):
        if not self._ok(): self.send_response(403); self.end_headers(); return
        d = FakeS3.store.get(self.path)
        if d is None: self.send_response(404); self.end_headers(); return
        self.send_response(200); self.end_headers(); self.wfile.write(d)

class TestStorage(unittest.TestCase):
    def test_local_roundtrip_and_traversal(self):
        s = storage.LocalStorage(tempfile.mkdtemp()); s.put("a.png", b"x"); self.assertEqual(s.get("a.png"), (b"x", "image/png"))
        self.assertIsNone(s.get("../etc/passwd")); self.assertIsNone(s.get("nope.png"))
        with self.assertRaises(ValueError): s.put("../x.png", b"")
    def test_s3_roundtrip_signed(self):
        srv = HTTPServer(("127.0.0.1", 0), FakeS3); threading.Thread(target=srv.serve_forever, daemon=True).start()
        s = storage.from_env({"S3_ENDPOINT": "http://127.0.0.1:%d" % srv.server_port, "S3_BUCKET": "b", "S3_ACCESS_KEY_ID": "AK", "S3_SECRET_ACCESS_KEY": "SK"}, tempfile.mkdtemp())
        self.assertEqual(s.kind, "s3")
        s.put("p1.jpg", b"\xff\xd8abc", "image/jpeg"); self.assertIn("/b/uploads/p1.jpg", FakeS3.store)
        self.assertEqual(s.get("p1.jpg"), (b"\xff\xd8abc", "image/jpeg")); self.assertIsNone(s.get("missing.jpg")); srv.shutdown()
    def test_env_selects_local_when_incomplete(self):
        self.assertEqual(storage.from_env({"S3_BUCKET": "b"}, tempfile.mkdtemp()).kind, "local")
