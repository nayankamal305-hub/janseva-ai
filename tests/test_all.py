import os, sys, tempfile, unittest, json, threading, urllib.request
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import DB
from app.service import Service
from app.connectors.mock_gov import MockSwachhata
from app.router import classify

PUNE = dict(lat=18.5204, lon=73.8567, city="Pune", state="Maharashtra", address="FC Road, Pune 411004", pincode="411004",
            photo_url="https://example.invalid/p.jpg", consent_submit=True, consent_share_personal=True)

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.mock = MockSwachhata()
    @classmethod
    def tearDownClass(cls): cls.mock.stop()
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = {}
        self.svc = Service(DB(os.path.join(self.tmp, "t.db")), env=self.env, sandbox_base=self.mock.url)
        self.u = self.svc.register("9876543210", "Test Citizen")
    def mk(self, **kw):
        d = dict(PUNE, description="Large garbage dump on the road", **kw); r = self.svc.create_complaint(self.u, d); return r
    def swachhata_rec(self, cid):
        return self.svc.db.one("SELECT * FROM external_records WHERE complaint_id=? AND platform_id='swachhata'", (cid,))

    def test_valid_complaint_and_sandbox_label(self):
        r = self.mk(); self.assertTrue(r["ok"]); out = self.svc.submit(r["id"]); self.assertTrue(out["ok"])
        rec = self.swachhata_rec(r["id"])
        self.assertEqual(rec["mode"], "sandbox"); self.assertTrue(rec["external_ref"].startswith("W03000C"))
        self.assertIn("SANDBOX", " ".join(t["message"] for t in self.svc.detail(r["id"])["timeline"]))
    def test_invalid_location(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, lat=51.5, lon=-0.1, description="garbage")); self.assertFalse(r["ok"])
    def test_missing_photo_not_submitted(self):
        r = self.mk(photo_url=None); out = self.svc.submit(r["id"])
        self.assertIsNone(self.swachhata_rec(r["id"]))
        self.assertTrue(any(x.get("status") == "invalid" for x in out["results"]))
    def test_unsupported_category_goes_guided_not_api(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="Train coach was filthy, PNR 123", lat=19.0, lon=72.8))
        self.assertEqual(r["category"], "railway"); out = self.svc.submit(r["id"])
        rec = self.svc.db.one("SELECT * FROM external_records WHERE complaint_id=?", (r["id"],))
        self.assertEqual(rec["platform_id"], "railmadad"); self.assertEqual(rec["mode"], "guided"); self.assertIsNone(rec["external_ref"])
        self.assertEqual(rec["status"], "pending_citizen_submission")
    def test_no_consent_no_submit(self):
        r = self.mk(consent_submit=False); self.assertFalse(self.svc.submit(r["id"])["ok"])
    def test_no_personal_data_consent_blocks_api(self):
        r = self.mk(consent_share_personal=False); out = self.svc.submit(r["id"]); self.assertIsNone(self.swachhata_rec(r["id"]))
        self.assertTrue(any(x.get("status") == "blocked" for x in out["results"]))
    def test_unauthorized_credentials(self):
        self.env.update(SWACHHATA_VENDOR_NAME="x", SWACHHATA_ACCESS_KEY="bad401")
        # live flag off -> still sandbox but uses the supplied key against the mock
        r = self.mk(); self.svc.submit(r["id"])
        self.assertIsNone(self.swachhata_rec(r["id"])); l = self.svc.db.one("SELECT * FROM integration_log WHERE ok=0"); self.assertEqual(l["http_code"], 401)
    def test_expired_credentials(self):
        self.env.update(SWACHHATA_VENDOR_NAME="x", SWACHHATA_ACCESS_KEY="expired403")
        r = self.mk(); self.svc.submit(r["id"]); self.assertEqual(self.svc.db.one("SELECT * FROM integration_log WHERE ok=0")["http_code"], 403)
        self.assertEqual(self.svc.control_center()["credential_problems"][0]["http_code"], 403)
    def test_duplicate_complaint(self):
        self.assertTrue(self.mk()["ok"]); d = self.mk(); self.assertFalse(d["ok"]); self.assertIn("duplicate", d["errors"][0])
    def test_platform_duplicate_response(self):
        self.env.update(SWACHHATA_VENDOR_NAME="x", SWACHHATA_ACCESS_KEY="dup")
        r = self.mk(); self.svc.submit(r["id"]); self.assertIsNone(self.swachhata_rec(r["id"]))
    def test_api_timeout(self):
        self.env.update(SWACHHATA_VENDOR_NAME="x", SWACHHATA_ACCESS_KEY="slow")
        r = self.mk(); self.svc.submit(r["id"]); self.assertEqual(self.svc.db.one("SELECT * FROM integration_log WHERE ok=0")["http_code"], 0)
        self.assertIsNone(self.swachhata_rec(r["id"]))
    def test_api_failure_500(self):
        self.env.update(SWACHHATA_VENDOR_NAME="x", SWACHHATA_ACCESS_KEY="fail500")
        r = self.mk(); self.svc.submit(r["id"]); self.assertIsNone(self.swachhata_rec(r["id"]))
    def test_missing_acknowledgement_never_claimed(self):
        self.env.update(SWACHHATA_VENDOR_NAME="x", SWACHHATA_ACCESS_KEY="noack")
        r = self.mk(); self.svc.submit(r["id"]); self.assertIsNone(self.swachhata_rec(r["id"]))
        self.assertIn("no acknowledgement", self.svc.db.one("SELECT detail FROM integration_log WHERE ok=0")["detail"])
    def test_status_sync_and_parent_not_resolved_by_one(self):
        r = self.mk(); self.svc.submit(r["id"]); rec = self.swachhata_rec(r["id"])
        cid_num = int("".join(ch for ch in rec["external_ref"].split("C")[1]))
        self.mock.set_status(cid_num, 3, "Assigned to engineer"); self.svc.sync(r["id"])
        self.assertEqual(self.swachhata_rec(r["id"])["status"], "assigned")
        self.mock.set_status(cid_num, 4, "Cleaned"); self.svc.sync(r["id"])
        self.assertEqual(self.swachhata_rec(r["id"])["status"], "resolved")
        # guided municipal record is still pending -> parent must not be official_resolved
        self.assertEqual(self.svc.get(r["id"])["status"], "partially_resolved")
    def test_parent_resolved_only_when_all_and_citizen_verify(self):
        r = self.mk(); self.svc.submit(r["id"])
        rec = self.swachhata_rec(r["id"]); n = int(rec["external_ref"].split("C")[1])
        self.svc.record_reference(r["id"], "pmc_grievance", "PMC-1", self.u["id"])
        self.mock.set_status(n, 4, "done"); self.svc.sync(r["id"])
        self.svc.db.run("UPDATE external_records SET status='resolved',terminal=1 WHERE platform_id='pmc_grievance'"); self.svc.refresh_parent(r["id"])
        self.assertEqual(self.svc.get(r["id"])["status"], "official_resolved")
        self.svc.citizen_verify(r["id"], True, self.u["id"]); self.assertEqual(self.svc.get(r["id"])["status"], "resolved_verified")
    def test_reopened_complaint(self):
        r = self.mk(); self.svc.submit(r["id"]); rec = self.swachhata_rec(r["id"]); n = int(rec["external_ref"].split("C")[1])
        self.mock.set_status(n, 4); self.svc.sync(r["id"])
        self.svc.citizen_verify(r["id"], False, self.u["id"])
        self.assertNotEqual(self.svc.get(r["id"])["status"], "resolved_verified")
    def test_government_rejection(self):
        r = self.mk(); self.svc.submit(r["id"]); n = int(self.swachhata_rec(r["id"])["external_ref"].split("C")[1])
        self.mock.set_status(n, 6, "Not a ULB matter"); self.svc.sync(r["id"])
        self.assertEqual(self.swachhata_rec(r["id"])["status"], "rejected"); self.assertEqual(self.swachhata_rec(r["id"])["terminal"], 1)
    def test_guided_reference_is_citizen_reported(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="Pension not credited for 4 months", lat=25.6, lon=85.1, city="Patna", state="Bihar"))
        self.svc.submit(r["id"]); self.assertEqual(r["category"], "pension")
        self.assertTrue(self.svc.record_reference(r["id"], "cpgrams", "DARPG/E/2026/0001", self.u["id"])["ok"])
        rec = self.svc.db.one("SELECT * FROM external_records WHERE platform_id='cpgrams'"); self.assertEqual(rec["reference_source"], "citizen_reported")
        # never synced via API
        self.assertEqual(self.svc.sync(r["id"]), [])
    def test_cpgrams_no_email_and_not_duplicated_when_local_channel(self):
        r = self.mk(); plan = self.svc.route(r["id"]); ids = [t["platform_id"] for t in plan["targets"]]
        self.assertNotIn("cpgrams", ids); self.assertIn("swachhata", ids)
    def test_road_owner_asked_not_guessed(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="Big pothole near the bridge", lat=18.53, lon=73.85))
        out = self.svc.submit(r["id"]); self.assertIn("needs", out)
    def test_nhai_road(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="Huge pothole on NH-48 highway", lat=18.6, lon=73.7)); out = self.svc.submit(r["id"])
        self.assertIn("nhai", [x["platform"] for x in out["results"]])
    def test_rural_not_ulb_no_swachhata(self):
        r = self.svc.create_complaint(self.u, dict(PUNE, description="garbage dump", city="SampleVillage", state="Bihar", lat=25.0, lon=85.0))
        plan = self.svc.route(r["id"]); self.assertNotIn("swachhata", [t["platform_id"] for t in plan["targets"]])
    def test_escalation_and_appeal(self):
        r = self.mk(); self.svc.submit(r["id"])
        self.assertEqual(self.svc.escalations(), [])
        late = datetime.now(timezone.utc) + timedelta(days=9)
        e = self.svc.escalations(late); self.assertEqual(e[0]["action"], "reminder_only"); self.assertIn("NOT an official appeal", e[0]["note"])
        r2 = self.svc.create_complaint(self.u, dict(PUNE, description="Pension not credited", lat=25.6, lon=85.1, city="Patna"))
        self.svc.submit(r2["id"]); self.svc.record_reference(r2["id"], "cpgrams", "X1", self.u["id"])
        e = [x for x in self.svc.escalations(datetime.now(timezone.utc) + timedelta(days=25)) if x["platform"] == "cpgrams"]
        self.assertEqual(e[0]["action"], "official_appeal")
    def test_analytics_unique_vs_records(self):
        r = self.mk(); self.svc.submit(r["id"]); a = self.svc.analytics()
        self.assertEqual(a["unique_citizen_complaints"], 1); self.assertGreaterEqual(a["external_records_total"], 2)
    def test_add_platform_without_code_change(self):
        res = self.svc.add_platform(dict(id="demo_water", name="Demo Jal Board", level=3, connector="guided", categories=["water"], jurisdiction={"scope": "city", "cities": ["pune"]}), "admin")
        self.assertTrue(res["ok"]); self.assertIn("demo_water", self.svc.connectors())
        self.assertFalse(self.svc.add_platform(dict(id="bad"), "admin")["ok"])
    def test_pending_mode_when_no_sandbox_or_creds(self):
        s = Service(DB(os.path.join(self.tmp, "p.db")), env={}, sandbox_base=None)
        self.assertEqual(s.connectors()["swachhata"].mode(), "pending")
        self.assertEqual(s.control_center()["live_connected"], [])
    def test_classifier_hindi(self): self.assertEqual(classify("यहाँ कचरा पड़ा है"), "garbage")
    def test_audit_log_written(self):
        self.mk(); self.assertTrue(self.svc.db.all("SELECT * FROM audit_log WHERE action='complaint_created'"))

class HTTP(unittest.TestCase):
    def test_api_flow_and_auth(self):
        from http.server import ThreadingHTTPServer
        from app.server import make_handler
        mock = MockSwachhata(); tmp = tempfile.mkdtemp(); svc = Service(DB(os.path.join(tmp, "h.db")), env={}, sandbox_base=mock.url)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(svc, "adm")); threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % srv.server_address[1]
        def call(m, p, d=None, tok=None):
            req = urllib.request.Request(base + p, method=m, data=json.dumps(d).encode() if d is not None else None)
            if tok: req.add_header("Authorization", "Bearer " + tok)
            try: return json.loads(urllib.request.urlopen(req).read())
            except urllib.error.HTTPError as e: return {"_code": e.code}
        self.assertEqual(call("GET", "/api/complaints")["_code"], 401)
        self.assertEqual(call("GET", "/api/admin/control-center", tok="nope")["_code"], 403)
        tok = call("POST", "/api/register", {"phone": "9000000001", "name": "A"})["token"]
        c = call("POST", "/api/complaints", dict(PUNE, description="garbage dump"), tok); self.assertTrue(c["ok"])
        s = call("POST", "/api/complaints/%d/submit" % c["id"], dict(consent_submit=True, consent_share_personal=True), tok); self.assertTrue(s["ok"])
        other = call("POST", "/api/register", {"phone": "9000000002", "name": "B"})["token"]
        self.assertEqual(call("GET", "/api/complaints/%d" % c["id"], tok=other)["_code"], 404)
        self.assertEqual(call("GET", "/api/admin/control-center", tok="adm")["total_platforms"], 10)
        srv.shutdown(); mock.stop()

if __name__ == "__main__": unittest.main()
