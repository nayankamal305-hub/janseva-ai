from app.db import guard_test_database_url as _g; _g()
import os, sys, tempfile, unittest, json, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import DB
from app.service import Service
from app import accounts

class TestPassword(unittest.TestCase):
    def setUp(self):
        self.svc = Service(DB(os.path.join(tempfile.mkdtemp(), "p.db")), env={}, sandbox_base="http://127.0.0.1:1")
        self.id = "citizen@example.com"
    def code(self):
        return accounts.otp_request(self.svc.db, self.id, True)["dev_code"]
    def test_hash_is_salted_and_verifies(self):
        a, b = accounts.pw_hash("correct horse 9"), accounts.pw_hash("correct horse 9")
        self.assertNotEqual(a, b); self.assertTrue(a.startswith("scrypt$")); self.assertNotIn("correct", a)
        self.assertTrue(accounts.pw_check("correct horse 9", a)); self.assertFalse(accounts.pw_check("wrong", a)); self.assertFalse(accounts.pw_check("x", "garbage"))
    def test_policy(self):
        self.assertIsNotNone(accounts.pw_policy("short")); self.assertIsNotNone(accounts.pw_policy("password")); self.assertIsNone(accounts.pw_policy("long enough pw"))
    def test_signup_then_login_without_otp(self):
        u, err = accounts.password_signup_or_reset(self.svc, self.id, self.code(), "my secret pw", "Asha"); self.assertIsNone(err); self.assertEqual(u["name"], "Asha")
        row = self.svc.db.one("SELECT pw_hash FROM users WHERE id=?", (u["id"],)); self.assertTrue(row["pw_hash"].startswith("scrypt$"))
        v, st = accounts.password_login(self.svc, self.id, "my secret pw", "1.1.1.1"); self.assertEqual(st, "ok"); self.assertEqual(v["token"], u["token"])
    def test_signup_needs_valid_otp_and_policy(self):
        self.code(); u, err = accounts.password_signup_or_reset(self.svc, self.id, "000000", "my secret pw"); self.assertIsNone(u); self.assertIn("code", err)
        u, err = accounts.password_signup_or_reset(self.svc, self.id, self.code(), "short"); self.assertIsNone(u); self.assertIn("8", err)
    def test_wrong_password_and_unknown_user_same_answer(self):
        accounts.password_signup_or_reset(self.svc, self.id, self.code(), "my secret pw")
        a = accounts.password_login(self.svc, self.id, "nope nope", "2.2.2.2"); b = accounts.password_login(self.svc, "nobody@example.com", "nope nope", "3.3.3.3")
        self.assertEqual(a, (None, "bad")); self.assertEqual(b, (None, "bad"))
    def test_otp_only_user_cannot_password_login(self):
        self.svc.register(self.id, "x"); self.assertEqual(accounts.password_login(self.svc, self.id, "anything at all", "4.4.4.4")[1], "bad")
    def test_lockout_after_5_failures_then_reset_unlocks(self):
        accounts.password_signup_or_reset(self.svc, self.id, self.code(), "my secret pw")
        for i in range(5): accounts.password_login(self.svc, self.id, "wrong wrong", "5.5.5.%d" % i)
        self.assertEqual(accounts.password_login(self.svc, self.id, "my secret pw", "9.9.9.9")[1], "locked")
        u, err = accounts.password_signup_or_reset(self.svc, self.id, self.code(), "brand new pw 1", reset=True); self.assertIsNone(err)
        self.assertEqual(accounts.password_login(self.svc, self.id, "brand new pw 1", "9.9.9.9")[1], "ok")
        self.assertEqual(accounts.password_login(self.svc, self.id, "my secret pw", "9.9.9.9")[1], "bad")
    def test_ip_lockout(self):
        for i in range(5): accounts.password_login(self.svc, "u%d@example.com" % i, "wrong wrong", "7.7.7.7")
        self.assertEqual(accounts.password_login(self.svc, "other@example.com", "x", "7.7.7.7")[1], "locked")

class TestHttp(unittest.TestCase):
    def test_endpoints(self):
        import subprocess, time, socket
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        env = dict(os.environ, PORT=str(port), JANSEVA_DB=os.path.join(tempfile.mkdtemp(), "h.db"), JANSEVA_DEV_OTP="1"); env.pop("DATABASE_URL", None)
        pr = subprocess.Popen([sys.executable, "-m", "app.server"], env=env, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = "http://127.0.0.1:%d" % port
            for _ in range(50):
                try: urllib.request.urlopen(base + "/api/health"); break
                except Exception: time.sleep(0.2)
            def post(p, d):
                rq = urllib.request.Request(base + p, json.dumps(d).encode(), {"Content-Type": "application/json"})
                try: r = urllib.request.urlopen(rq); return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
            c = post("/api/otp/request", {"email": "a@example.com"})[1]["dev_code"]
            st, j = post("/api/auth/signup", {"email": "a@example.com", "code": c, "password": "pass phrase 1", "name": "A"}); self.assertEqual(st, 200); self.assertIn("token", j)
            st, j2 = post("/api/auth/login", {"email": "a@example.com", "password": "pass phrase 1"}); self.assertEqual((st, j2["token"]), (200, j["token"]))
            self.assertEqual(post("/api/auth/login", {"email": "a@example.com", "password": "bad bad bad"})[0], 401)
            self.assertEqual(post("/api/auth/signup", {"email": "b@example.com", "code": "123456", "password": "pass phrase 1"})[0], 401)
        finally: pr.terminate(); pr.wait(5)
