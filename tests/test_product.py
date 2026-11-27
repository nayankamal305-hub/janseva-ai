import os, sys, tempfile, unittest, json, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer
from app.db import DB
from app.service import Service
from app.server import make_handler
from app.connectors.mock_gov import MockSwachhata
from app import accounts, public, assistant, ai
from tests.test_all import PUNE

class P(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.mock = MockSwachhata()
    @classmethod
    def tearDownClass(cls): cls.mock.stop()
    def setUp(self):
        self.svc = Service(DB(os.path.join(tempfile.mkdtemp(), "p.db")), env={}, sandbox_base=self.mock.url)
        self.u = self.svc.register("9111111111", "A"); self.u2 = self.svc.register("9222222222", "B")
    def mk(self, u=None, **kw): return self.svc.create_complaint(u or self.u, dict(PUNE, description="Large garbage dump on the road", **kw))

    def test_ai_low_confidence_needs_confirmation(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="something odd here"))
        self.assertEqual(r["status"], "awaiting_citizen_confirmation")
        self.assertFalse(self.svc.submit(r["id"])["ok"])
        self.svc.confirm_category(r["id"], "garbage", self.u["id"])
        self.assertEqual(self.svc.get(r["id"])["status"], "ready_for_submission")
    def test_ai_fields_and_emergency(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="Open manhole with no cover and live wire", lat=18.6))
        self.assertTrue(r["ai"]["emergency"]); self.assertEqual(r["ai"]["severity"], 5); self.assertIn("112", r["emergency_notice"])
        self.assertIn("text only", r["ai"]["engine"])
    def test_lifecycle_statuses_and_sandbox_basis(self):
        r = self.mk(); self.svc.submit(r["id"]); c = self.svc.get(r["id"])
        self.assertEqual(c["status"], "acknowledged"); self.assertEqual(c["official_basis"], "sandbox")
        self.assertEqual(public.stats(self.svc.db, {})["officially_submitted_government_confirmed"], 0)
        self.assertEqual(public.stats(self.svc.db, {})["sandbox_test_complaints"], 1)
    def test_closure_is_not_citizen_verified_and_reopen(self):
        r = self.mk(); self.svc.submit(r["id"]); n = int(self.svc.db.one("SELECT external_ref e FROM external_records WHERE platform_id='swachhata'")["e"].split("C")[1])
        self.svc.record_reference(r["id"], "pmc_grievance", "P1", self.u["id"])
        self.svc.db.run("UPDATE external_records SET status='resolved',terminal=1 WHERE platform_id='pmc_grievance'")
        self.mock.set_status(n, 4, "cleaned"); self.svc.sync(r["id"])
        self.assertEqual(self.svc.get(r["id"])["status"], "authority_marked_resolved")
        self.svc.citizen_verify(r["id"], False, self.u["id"], "/uploads/after.jpg", "still dirty")
        self.assertEqual(self.svc.get(r["id"])["status"], "reopened")
        self.assertEqual(self.svc.get(r["id"])["after_photo_url"], "/uploads/after.jpg")
        self.svc.citizen_verify(r["id"], True, self.u["id"]); self.assertEqual(self.svc.get(r["id"])["status"], "citizen_verified_resolved")
    def test_duplicate_group_merges_without_second_gov_complaint(self):
        a = self.mk(self.u); self.svc.submit(a["id"])
        b = self.mk(self.u2); self.assertEqual(self.svc.get(b["id"])["duplicate_group"], self.svc.get(a["id"])["duplicate_group"])
        out = self.svc.submit(b["id"]); self.assertIn("merged_into", out)
        self.assertEqual(self.svc.db.one("SELECT count(*) n FROM external_records WHERE complaint_id=?", (b["id"],))["n"], 0)
        self.assertEqual(self.svc.get(b["id"])["user_id"], self.u2["id"])   # own reference kept
    def test_anonymous_blocks_official_submission(self):
        r = self.mk(anonymous=True); out = self.svc.submit(r["id"])
        self.assertIsNone(self.svc.db.one("SELECT id FROM external_records WHERE platform_id='swachhata'"))
        self.assertTrue(any(x.get("status") == "blocked" for x in out["results"]))
    def test_no_target_goes_to_human_queue(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="Hospital building has cracks and seepage", category="health", lat=18.52, lon=73.80))
        # health maps to generic portals only, but force empty: unknown category
        r2 = self.svc.create_complaint(self.u, dict(PUNE, description="odd thing", category="spaceport", lat=19.2, lon=73.1))
        out = self.svc.submit(r2["id"]); self.assertFalse(out["ok"]); self.assertEqual(self.svc.get(r2["id"])["needs_human"], 1)
    def test_four_roles_never_guessed(self):
        r = self.mk(); self.svc.submit(r["id"]); rt = json.loads(self.svc.get(r["id"])["routing_json"])
        self.assertIsNone(rt["operational_authority"]); self.assertIsNone(rt["elected_representative"])
        self.svc.db.run("INSERT INTO authorities(name,type,state,city,categories,verified,last_verified,source_url) VALUES('PMC Solid Waste','operational','maharashtra','pune','garbage',1,'2026-11-27','https://pmc.gov.in')")
        r2 = self.mk(lat=18.60, lon=73.90); self.svc.submit(r2["id"]); rt = json.loads(self.svc.get(r2["id"])["routing_json"])
        self.assertEqual(rt["operational_authority"]["name"], "PMC Solid Waste")
    def test_otp(self):
        res = accounts.otp_request(self.svc.db, "9333333333", dev=True); self.assertFalse(res["sent"])
        self.assertIsNone(accounts.otp_verify(self.svc, "9333333333", "000000", "C") if res["dev_code"] != "000000" else None)
        self.assertTrue(accounts.otp_verify(self.svc, "9333333333", res["dev_code"], "C"))
        self.assertIsNone(accounts.otp_verify(self.svc, "9333333333", res["dev_code"], "C"))   # single use
    def test_account_deletion_anonymises(self):
        r = self.mk(); accounts.delete_account(self.svc.db, self.u["id"])
        self.assertEqual(self.svc.db.one("SELECT name,deleted FROM users WHERE id=?", (self.u["id"],))["deleted"], 1)
        self.assertEqual(self.svc.get(r["id"])["anonymous"], 1)
    def test_public_feed_privacy(self):
        r = self.mk(); self.svc.submit(r["id"]); f = public.feed(self.svc.db, {})[0]
        self.assertNotIn("phone", json.dumps(f)); self.assertEqual(f["approx_lat"], round(PUNE["lat"], 3)); self.assertIsNone(f["photo"]); self.assertEqual(f["official_ids"], [])
        self.svc.db.run("UPDATE complaints SET photo_public_ok=1"); self.assertTrue(public.feed(self.svc.db, {})[0]["photo"])
    def test_public_filters_and_report(self):
        self.mk(); self.assertEqual(public.stats(self.svc.db, {"state": "maharashtra"})["total_reported"], 1)
        self.assertEqual(public.stats(self.svc.db, {"state": "bihar"})["total_reported"], 0)
        self.assertEqual(public.stats(self.svc.db, {"days": "7", "category": "garbage"})["total_reported"], 1)
        self.assertIn("metric", public.monthly_report(self.svc.db, "2026-11", "csv")); self.assertTrue(public.heatmap(self.svc.db, {}))
    def test_assistant(self):
        self.assertIn("112", assistant.answer("there is a fallen wire", "en")["answer"]); self.assertIn("112", assistant.answer("खतरा wire", "hi")["answer"])
        self.assertIn("not have a verified", assistant.answer("who won the match", "en")["answer"])
    def test_escalation_levels_recorded(self):
        from datetime import datetime, timedelta, timezone
        r = self.mk(); self.svc.submit(r["id"])
        res = self.svc.run_escalation(datetime.now(timezone.utc) + timedelta(days=9))
        self.assertTrue(res); self.assertEqual(self.svc.db.one("SELECT level FROM escalation_records")["level"], 2)
        self.assertEqual(self.svc.get(r["id"])["status"], "escalated")

class H(unittest.TestCase):
    def setUp(self):
        self.mock = MockSwachhata(); self.svc = Service(DB(os.path.join(tempfile.mkdtemp(), "h.db")), env={}, sandbox_base=self.mock.url)
        os.environ["JANSEVA_UPLOADS"] = tempfile.mkdtemp()
        import app.server as S; S.UPLOADS = os.environ["JANSEVA_UPLOADS"]
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.svc, "root", rate=40)); threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]
    def tearDown(self): self.srv.shutdown(); self.mock.stop()
    def call(self, m, p, d=None, tok=None, raw=None):
        data = raw if raw is not None else (json.dumps(d).encode() if d is not None else None)
        req = urllib.request.Request(self.base + p, method=m, data=data)
        if tok: req.add_header("Authorization", "Bearer " + tok)
        try: return json.loads(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e:
            try: b = json.loads(e.read())
            except Exception: b = {}
            b["_code"] = e.code; return b
    def test_upload_validation(self):
        tok = self.call("POST", "/api/register", {"phone": "9000000011", "name": "A"})["token"]
        self.assertEqual(self.call("POST", "/api/upload", tok=tok, raw=b"MZ not an image")["_code"], 415)
        ok = self.call("POST", "/api/upload", tok=tok, raw=b"\x89PNG\r\n\x1a\n" + b"0" * 50); self.assertTrue(ok["url"].endswith(".png"))
        self.assertEqual(self.call("POST", "/api/upload", raw=b"\x89PNG")["_code"], 401)
    def test_roles_and_privacy(self):
        tok = self.call("POST", "/api/register", {"phone": "9000000012", "name": "Secret Name"})["token"]
        c = self.call("POST", "/api/complaints", dict(PUNE, description="garbage dump"), tok)
        st = self.call("POST", "/api/admin/admins", {"name": "mh", "role": "state_admin", "scope_state": "Maharashtra"}, "root")["token"]
        bi = self.call("POST", "/api/admin/admins", {"name": "bh", "role": "state_admin", "scope_state": "Bihar"}, "root")["token"]
        lst = self.call("GET", "/api/admin/complaints", tok=st); self.assertEqual(len(lst), 1); self.assertNotIn("Secret Name", json.dumps(lst)); self.assertNotIn("phone", json.dumps(lst))
        self.assertEqual(self.call("GET", "/api/admin/complaints", tok=bi), [])
        self.assertEqual(self.call("GET", "/api/admin/control-center", tok=st)["_code"], 403)
        self.assertEqual(self.call("GET", "/api/admin/audit", tok=st)["_code"], 403)
        self.assertEqual(self.call("POST", "/api/admin/authorities", {"name": "X", "state": "Bihar"}, st)["_code"], 403)
        self.assertEqual(self.call("POST", "/api/admin/authorities", {"name": "X", "state": "Maharashtra", "verified": True}, st)["_code"], 422)
        self.assertEqual(self.call("GET", "/api/complaints/%d" % c["id"], tok=bi)["_code"], 404)
        vo = self.call("POST", "/api/admin/admins", {"name": "v", "role": "verification_officer"}, "root")["token"]
        self.assertEqual(self.call("GET", "/api/admin/verification-queue", tok=vo).__class__, list)
    def test_public_endpoints_open_and_rate_limit(self):
        self.assertIn("total_reported", self.call("GET", "/api/public/stats")); self.assertEqual(self.call("GET", "/api/emergency")["number"], "112")
        codes = {self.call("GET", "/api/health").get("_code") for _ in range(60)}; self.assertIn(429, codes)
    def test_support_and_full_flow(self):
        t1 = self.call("POST", "/api/register", {"phone": "9000000021", "name": "A"})["token"]; t2 = self.call("POST", "/api/register", {"phone": "9000000022", "name": "B"})["token"]
        c = self.call("POST", "/api/complaints", dict(PUNE, description="garbage dump"), t1)
        self.assertTrue(self.call("POST", "/api/complaints/%d/support" % c["id"], {}, t2)["ok"])
        s = self.call("POST", "/api/complaints/%d/submit" % c["id"], dict(consent_submit=True, consent_share_personal=True), t1); self.assertTrue(s["ok"])
        self.assertEqual(self.call("GET", "/api/public/feed")[0]["supporters"], 2)
        self.assertEqual(self.call("POST", "/api/complaints/%d/submit" % c["id"], dict(consent_submit=True), t2)["_code"], 404)
        self.assertIn("letter", self.call("GET", "/api/complaints/%d/letter" % c["id"], tok=t1))

if __name__ == "__main__": unittest.main()
