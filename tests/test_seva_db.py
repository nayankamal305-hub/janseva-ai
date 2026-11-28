from app.db import guard_test_database_url as _g; _g()
# Phase 2 (Seva Setu India): schema, profiles, applications, honest official-status guard, consents.
import os, sys, json, tempfile, unittest, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer
from app.db import DB
from app.service import Service
from app.server import make_handler
from app import seva

class DBLayer(unittest.TestCase):
    def setUp(self):
        self.svc = Service(DB(os.path.join(tempfile.mkdtemp(), "s.db")), env={})
        self.db = self.svc.db
        self.u = self.svc.register("9111111111", "Asha")
        self.u2 = self.svc.register("9222222222", "Bala")

    def test_seed_catalog(self):
        self.assertEqual(self.db.one("SELECT count(*) c FROM service_categories")["c"], 25)
        self.assertGreaterEqual(self.db.one("SELECT count(*) c FROM schemes")["c"], 6)
        self.assertEqual(self.db.one("SELECT count(*) c FROM seva_states")["c"], 36)
        cat = seva.catalog(self.db)
        self.assertEqual(len(cat["categories"]), 25)
        self.assertIn("hi", cat["categories"][0]["names"])
    def test_profile_roundtrip(self):
        seva.upsert_profile(self.db, self.u["id"], {"preferred_lang": "mr", "state": "MH", "district": "Pune", "occupation": "farmer"})
        p = seva.get_profile(self.db, self.u["id"])
        self.assertEqual(p["preferred_lang"], "mr"); self.assertEqual(p["district"], "Pune")
        seva.upsert_profile(self.db, self.u["id"], {"district": "Satara"})
        self.assertEqual(seva.get_profile(self.db, self.u["id"])["district"], "Satara")
        self.assertEqual(seva.get_profile(self.db, self.u["id"])["preferred_lang"], "mr")
    def test_application_lifecycle(self):
        r = seva.create_application(self.db, self.u, "income-certificate", "Income cert for scholarship")
        self.assertTrue(r["ok"]); self.assertTrue(r["ref_no"].startswith("SSI-"))
        a = seva.get_application(self.db, r["ref_no"], self.u["id"])
        self.assertEqual(a["status"], "request_received")
        self.assertEqual(len(a["history"]), 1)
        self.assertIsNone(seva.get_application(self.db, r["ref_no"], self.u2["id"]))  # other citizen cannot read
    def test_unknown_category_rejected(self):
        self.assertFalse(seva.create_application(self.db, self.u, "made-up-service")["ok"])
    def test_official_status_needs_verified_submission(self):
        r = seva.create_application(self.db, self.u, "passport")
        aid = r["id"]
        bad = seva.set_status(self.db, aid, "submitted_to_portal", "citizen:1")
        self.assertFalse(bad["ok"])
        seva.add_submission(self.db, aid, "passportindia.gov.in", "guided", "", "citizen", verified=0)
        still_bad = seva.set_status(self.db, aid, "submitted_to_portal", "operator:1")
        self.assertFalse(still_bad["ok"])  # unverified submission without ack number is not enough
        seva.add_submission(self.db, aid, "passportindia.gov.in", "guided", "GOV-12345", "operator", verified=1)
        good = seva.set_status(self.db, aid, "submitted_to_portal", "operator:1")
        self.assertTrue(good["ok"])
        self.assertEqual(seva.get_application(self.db, r["ref_no"])["official_ack_no"], "GOV-12345")
    def test_bad_status_rejected(self):
        r = seva.create_application(self.db, self.u, "voter-services")
        self.assertFalse(seva.set_status(self.db, r["id"], "magically_done", "admin")["ok"])
    def test_consents(self):
        cid = seva.record_consent(self.db, self.u["id"], "operator_document_access", True)
        items = seva.consents(self.db, self.u["id"])
        self.assertEqual(len(items), 1); self.assertEqual(items[0]["granted"], 1)
        self.assertEqual(seva.consents(self.db, self.u2["id"]), [])

class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = Service(DB(os.path.join(tempfile.mkdtemp(), "a.db")), env={})
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.svc, "", 600))
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True); cls.th.start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()
    def call(self, path, method="GET", body=None, tok=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), method=method)
        if tok: req.add_header("Authorization", "Bearer " + tok)
        data = None
        if body is not None:
            data = json.dumps(body).encode(); req.add_header("Content-Type", "application/json")
        try:
            r = urllib.request.urlopen(req, data, timeout=10)
            return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")

    def test_catalog_public(self):
        st, c = self.call("/api/seva/catalog")
        self.assertEqual(st, 200); self.assertEqual(len(c["categories"]), 25)
    def test_auth_required(self):
        st, _ = self.call("/api/seva/applications")
        self.assertEqual(st, 401)
    def test_full_flow(self):
        u = self.svc.register("9333333333", "Chetan")
        tok = u["token"]
        st, r = self.call("/api/seva/applications", "POST", {"category_id": "ration-card", "title": "New ration card"}, tok)
        self.assertEqual(st, 200); self.assertTrue(r["ok"])
        ref = r["ref_no"]
        st, a = self.call("/api/seva/applications/" + ref, tok=tok)
        self.assertEqual(st, 200); self.assertEqual(a["status"], "request_received")
        st, p = self.call("/api/seva/profile", "POST", {"preferred_lang": "ta", "state": "TN"}, tok)
        self.assertEqual(p["preferred_lang"], "ta")
        st, c = self.call("/api/seva/consents", "POST", {"scope": "operator_document_access", "granted": True, "application_ref": ref}, tok)
        self.assertTrue(c["ok"])
        st, l = self.call("/api/seva/applications", tok=tok)
        self.assertEqual(len(l["items"]), 1)
        st, cl = self.call("/api/seva/consents", tok=tok)
        self.assertEqual(len(cl["items"]), 1)
    def test_create_validation(self):
        u = self.svc.register("9444444444", "Diya")
        st, r = self.call("/api/seva/applications", "POST", {"category_id": "nope"}, u["token"])
        self.assertEqual(st, 422)

if __name__ == "__main__":
    unittest.main()
