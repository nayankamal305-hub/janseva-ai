from app.db import guard_test_database_url as _g; _g()
# Phase 6 (Seva Setu India): super-admin console - overview, citizens, staff, catalog, translations, settings, audit.
import os, sys, json, tempfile, unittest, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer
from app.db import DB
from app.service import Service
from app.server import make_handler
from app import accounts, seva

class Adm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.svc = Service(DB(os.path.join(cls.dir, "a.db")), env={})
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.svc, "", 600))
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True); cls.th.start()
        cls.cit = cls.svc.register("9222222222", "Babu")
        cls.admin = accounts.create_admin(cls.svc.db, "Boss", "super_admin")
        cls.op = accounts.create_admin(cls.svc.db, "Ops", "seva_operator")
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, method="GET", body=None, tok=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), method=method)
        if tok: req.add_header("Authorization", "Bearer " + tok)
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        try:
            r = urllib.request.urlopen(req, data, timeout=10)
            return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try: return e.code, json.loads(e.read().decode())
            except Exception: return e.code, {}

    def test_perm_gate(self):
        st, r = self.call("/api/admin/overview")
        self.assertEqual(st, 403)
        st, r = self.call("/api/admin/overview", tok=self.op)  # operator perm is not admin perm
        self.assertEqual(st, 403)
        st, r = self.call("/api/admin/overview", tok=self.cit["token"])  # citizen token is not staff
        self.assertEqual(st, 403)

    def test_overview(self):
        seva.create_application(self.svc.db, self.cit, "welfare-schemes", "Test app")
        st, r = self.call("/api/admin/overview", tok=self.admin)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(r["citizens"], 1)
        self.assertGreaterEqual(r["applications"], 1)
        self.assertIn("request_received", r["applications_by_status"])

    def test_settings_roundtrip_and_public_config(self):
        st, r = self.call("/api/admin/settings", "POST", {"brand_name": "Seva Setu Test", "wa_number": "+91 98765-43210", "bad_key": "x"}, self.admin)
        self.assertEqual(st, 200)
        self.assertEqual(r["saved"]["wa_number"], "919876543210")  # digits only
        self.assertNotIn("bad_key", r["saved"])  # whitelist
        st, r = self.call("/api/config")
        self.assertEqual(r["brand_name"], "Seva Setu Test")
        self.assertEqual(r["wa_number"], "919876543210")
        st, r = self.call("/manifest.json")
        self.assertEqual(r["name"], "Seva Setu Test")
        self.call("/api/admin/settings", "POST", {"brand_name": "", "wa_number": ""}, self.admin)  # reset to defaults
        st, r = self.call("/api/config")
        self.assertEqual(r["brand_name"], "Seva Setu India")

    def test_staff_create_disable(self):
        st, r = self.call("/api/admin/staff", "POST", {"name": "New Op", "role": "seva_operator"}, self.admin)
        self.assertEqual(st, 200)
        tok = r["token"]
        st, r = self.call("/api/op/applications", tok=tok)  # token works
        self.assertEqual(st, 200)
        st, r = self.call("/api/admin/staff", "POST", {"name": "Bad", "role": "nonsense"}, self.admin)
        self.assertEqual(st, 422)
        st, r = self.call("/api/admin/staff", tok=self.admin)
        row = [x for x in r["items"] if x["name"] == "New Op"][0]
        st, r = self.call("/api/admin/staff/%d/disable" % row["id"], "POST", {}, self.admin)
        self.assertEqual(st, 200)
        st, r = self.call("/api/op/applications", tok=tok)  # disabled token rejected
        self.assertEqual(st, 403)

    def test_citizen_suspend_blocks_login(self):
        st, r = self.call("/api/seva/profile", tok=self.cit["token"])
        self.assertEqual(st, 200)
        st, r = self.call("/api/admin/citizens/%d/flag" % self.cit["id"], "POST", {"flag": "suspended", "reason": "test spam"}, self.admin)
        self.assertEqual(st, 200)
        st, r = self.call("/api/seva/profile", tok=self.cit["token"])  # suspended: token stops working
        self.assertEqual(st, 401)
        st, r = self.call("/api/admin/citizens/%d/flag" % self.cit["id"], "POST", {"flag": "clear"}, self.admin)
        self.assertEqual(st, 200)
        st, r = self.call("/api/seva/profile", tok=self.cit["token"])
        self.assertEqual(st, 200)

    def test_catalog_crud(self):
        st, r = self.call("/api/admin/catalog/category", "POST", {"id": "test-cat", "name": "Test Category", "blurb": "b"}, self.admin)
        self.assertEqual(st, 200); self.assertTrue(r["created"])
        st, r = self.call("/api/admin/catalog/service", "POST", {"category_id": "test-cat", "name": "Test Service", "dept": "Test Dept", "link": "https://example.gov.in"}, self.admin)
        self.assertEqual(st, 200); self.assertTrue(r["created"])
        st, r = self.call("/api/admin/catalog/scheme", "POST", {"slug": "test-scheme", "name": "Test Scheme", "link": "https://example.gov.in/s", "source": "https://example.gov.in"}, self.admin)
        self.assertEqual(st, 200); self.assertTrue(r["created"])
        st, r = self.call("/api/admin/catalog/scheme", "POST", {"slug": "test-scheme", "name": "Test Scheme v2"}, self.admin)
        self.assertFalse(r["created"])  # update path
        st, r = self.call("/api/admin/catalog", tok=self.admin)
        self.assertIn("test-cat", [c["id"] for c in r["categories"]])
        self.assertIn("Test Service", [s["name"] for s in r["services"]])
        st, r = self.call("/api/seva/catalog")  # public catalog picks up admin additions
        self.assertIn("test-cat", [c["id"] for c in r["categories"]])
        st, r = self.call("/api/admin/catalog/service", "POST", {"category_id": "no-such", "name": "X"}, self.admin)
        self.assertEqual(st, 422)

    def test_translations(self):
        st, r = self.call("/api/admin/translations", "POST", {"key": "test-cat", "lang": "hi", "text": "परीक्षण श्रेणी"}, self.admin)
        self.assertEqual(st, 200); self.assertFalse(r["updated"])
        st, r = self.call("/api/admin/translations", "POST", {"key": "test-cat", "lang": "hi", "text": "परीक्षण श्रेणी २"}, self.admin)
        self.assertTrue(r["updated"])
        st, r = self.call("/api/admin/translations", tok=self.admin)
        row = [x for x in r["items"] if x["key"] == "test-cat" and x["lang"] == "hi"][0]
        self.assertEqual(row["text"], "परीक्षण श्रेणी २")

    def test_audit_records_admin_actions(self):
        self.call("/api/admin/settings", "POST", {"support_text": "call 1800-test"}, self.admin)
        st, r = self.call("/api/admin/audit", tok=self.admin)
        acts = [x["action"] for x in r["items"]]
        self.assertIn("settings_updated", acts)

    def test_admin_page_served(self):
        req = urllib.request.Request("http://127.0.0.1:%d/admin" % self.port)
        body = urllib.request.urlopen(req, timeout=10).read().decode()
        self.assertIn("Admin console", body)
        self.assertIn("noindex", body)

if __name__ == "__main__":
    unittest.main()
