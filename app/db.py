import json, os, sqlite3, threading, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lock = threading.RLock()

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

class DB:
    def __init__(self, path=None):
        self.path = path or os.environ.get("JANSEVA_DB", os.path.join(ROOT, "jansevaai.sqlite3"))
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.migrate()
        self.load_platforms()

    def migrate(self):
        mdir = os.path.join(ROOT, "migrations")
        with _lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, applied_at TEXT)")
            done = {r[0] for r in self.conn.execute("SELECT name FROM schema_migrations")}
            for f in sorted(os.listdir(mdir)):
                if f.endswith(".sql") and f not in done:
                    self.conn.executescript(open(os.path.join(mdir, f)).read())
                    self.conn.execute("INSERT INTO schema_migrations VALUES(?,?)", (f, now()))
            self.conn.commit()

    def load_platforms(self):
        # seed registry from JSON; admin-added platforms (already in DB) are kept
        for p in json.load(open(os.path.join(ROOT, "data", "platforms.json"))):
            if not self.one("SELECT id FROM platforms WHERE id=?", (p["id"],)):
                self.add_platform(p)

    def add_platform(self, p):
        self.run("INSERT OR REPLACE INTO platforms(id,data,approval_status,last_verified,admin_owner) VALUES(?,?,?,?,?)",
                 (p["id"], json.dumps(p), p.get("approval_status", "unverified"), p.get("last_verified"), p.get("admin_owner", "unassigned")))

    def run(self, sql, args=()):
        with _lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def all(self, sql, args=()):
        with _lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        r = self.all(sql, args)
        return r[0] if r else None

    def platforms(self):
        return [json.loads(r["data"]) for r in self.all("SELECT data FROM platforms ORDER BY id")]

    def platform(self, pid):
        r = self.one("SELECT data FROM platforms WHERE id=?", (pid,))
        return json.loads(r["data"]) if r else None

    def audit(self, actor, action, detail=""):
        self.run("INSERT INTO audit_log(ts,actor,action,detail) VALUES(?,?,?,?)", (now(), actor, action, detail))

    def timeline(self, cid, source, kind, message, ext_id=None):
        self.run("INSERT INTO timeline(complaint_id,ts,source,kind,message,external_record_id) VALUES(?,?,?,?,?,?)",
                 (cid, now(), source, kind, message, ext_id))

    def ilog(self, platform_id, cid, action, ok, code=None, detail=""):
        self.run("INSERT INTO integration_log(ts,platform_id,complaint_id,action,ok,http_code,detail) VALUES(?,?,?,?,?,?,?)",
                 (now(), platform_id, cid, action, 1 if ok else 0, code, str(detail)[:500]))
