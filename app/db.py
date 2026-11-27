import json, os, re, sqlite3, threading, uuid, decimal, datetime as dt


def guard_test_database_url():
    """Test-suite guard: refuse to run tests against a non-local DATABASE_URL.
    Run the suite against local Postgres, or against a separate Neon branch with
    JANSEVA_TEST_ALLOW_REMOTE=1 (never the production URL)."""
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgres://", "postgresql://")):
        return
    import urllib.parse
    host = urllib.parse.urlparse(url).hostname or ""
    if host in ("localhost", "127.0.0.1", "::1"):
        return
    if os.environ.get("JANSEVA_TEST_ALLOW_REMOTE") == "1":
        return
    raise RuntimeError(
        "tests refuse to run against non-local DATABASE_URL host %r. "
        "Use local Postgres, or a separate Neon branch with JANSEVA_TEST_ALLOW_REMOTE=1." % host)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lock = threading.RLock()

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

_CONFLICT = {"otps": ("phone",), "platforms": ("id",), "external_records": ("complaint_id", "platform_id")}

def pg_sql(sql):
    """Translate this app's SQLite-flavoured SQL (? placeholders, INSERT OR IGNORE/REPLACE, LIKE) to Postgres."""
    q = sql.strip().rstrip(";").replace("%", "%%").replace("?", "%s")
    q = re.sub(r"\bLIKE\b", "ILIKE", q)
    m = re.match(r"(?is)INSERT\s+OR\s+IGNORE\s+INTO\s+(.*)$", q)
    if m: return "INSERT INTO " + m.group(1) + " ON CONFLICT DO NOTHING"
    m = re.match(r"(?is)INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]*)\)(.*)$", q)
    if m:
        t, cols, rest = m.group(1), [c.strip() for c in m.group(2).split(",")], m.group(3)
        key = _CONFLICT[t]
        upd = ", ".join("%s=EXCLUDED.%s" % (c, c) for c in cols if c not in key)
        return "INSERT INTO %s(%s)%s ON CONFLICT (%s) DO UPDATE SET %s" % (t, ", ".join(cols), rest, ", ".join(key), upd)
    return q

def pg_migration(script):
    s = re.sub(r"(?i)\bINTEGER PRIMARY KEY( AUTOINCREMENT)?", "SERIAL PRIMARY KEY", script)
    return re.sub(r"\bREAL\b", "DOUBLE PRECISION", s)

def _clean(v):
    if isinstance(v, decimal.Decimal): return float(v)
    if isinstance(v, bool): return int(v)
    return v

class DB:
    """SQLite by default (local/tests). Postgres when DATABASE_URL is set (Neon). Same call surface either way:
    run/all/one with ? placeholders. JANSEVA_PG_ISOLATE=1 gives every DB() its own schema (used by the test-suite)."""
    def __init__(self, path=None, url=None):
        self.url = url if url is not None else os.environ.get("DATABASE_URL", "")
        self.pg = self.url.startswith(("postgres://", "postgresql://"))
        if self.pg:
            import psycopg2
            self._pg = psycopg2
            self.schema = ("t_" + uuid.uuid4().hex[:12]) if os.environ.get("JANSEVA_PG_ISOLATE") else None
            self.conn = None
            self._connect()
            if self.schema:
                self._exec("CREATE SCHEMA " + self.schema); self._exec("SET search_path TO " + self.schema)
        else:
            self.path = path or os.environ.get("JANSEVA_DB", os.path.join(ROOT, "jansevaai.sqlite3"))
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        self.migrate()
        self.load_platforms()

    # ---- postgres plumbing
    def _connect(self):
        self.conn = self._pg.connect(self.url, connect_timeout=15, keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3)
        self.conn.autocommit = True
        # Pooled connections (Neon pgbouncer) can carry a stale search_path from a
        # previous session (e.g. a dropped test schema) - always pin it explicitly.
        if self.schema: self._exec("SET search_path TO " + self.schema)
        else: self._exec("SET search_path TO public")
        self._ids = None

    def _exec(self, sql, args=None):
        cur = self.conn.cursor(); cur.execute(sql, args); return cur

    def _pg_do(self, sql, args, fetch):
        if not args: args = None; sql = sql.replace("%%", "%")
        # Neon scales to zero and drops idle connections: reconnect once.
        for attempt in (0, 1):
            try:
                cur = self._exec(sql, args)
                return cur.fetchall() if fetch and cur.description else ([] if fetch else cur), cur
            except (self._pg.OperationalError, self._pg.InterfaceError):
                if attempt: raise
                try: self.conn.close()
                except Exception: pass
                self._connect()

    def _id_tables(self):
        if self._ids is None:
            rows, cur = self._pg_do("SELECT table_name FROM information_schema.columns WHERE column_name='id' AND table_schema=current_schema()", None, True)
            self._ids = {r[0] for r in rows}
        return self._ids

    def migrate(self):
        mdir = os.path.join(ROOT, "migrations")
        with _lock:
            if self.pg:
                self._exec("SELECT pg_advisory_lock(727401)")
                try:
                    self._exec("CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, applied_at TEXT)")
                    done = {r[0] for r in self._exec("SELECT name FROM schema_migrations").fetchall()}
                    for f in sorted(os.listdir(mdir)):
                        if f.endswith(".sql") and f not in done:
                            self._exec("BEGIN; " + pg_migration(open(os.path.join(mdir, f)).read()) + "; INSERT INTO schema_migrations VALUES('%s','%s'); COMMIT;" % (f, now()))
                finally:
                    self._exec("SELECT pg_advisory_unlock(727401)")
                self._ids = None
                return
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
            if self.pg:
                q = pg_sql(sql)
                m = re.match(r"(?is)INSERT\s+INTO\s+(\w+)", q)
                rid = m and m.group(1) in self._id_tables() and "RETURNING" not in q.upper()
                if rid: q += " RETURNING id"
                rows, cur = self._pg_do(q, tuple(args), False)
                if rid:
                    r = cur.fetchone(); return r[0] if r else 0
                return None
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def all(self, sql, args=()):
        with _lock:
            if self.pg:
                rows, cur = self._pg_do(pg_sql(sql), tuple(args), True)
                names = [d[0] for d in cur.description] if cur.description else []
                return [{n: _clean(v) for n, v in zip(names, r)} for r in rows]
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
