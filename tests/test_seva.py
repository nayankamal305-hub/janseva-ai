from app.db import guard_test_database_url as _g; _g()
# Phase 1 (Seva Setu India): multilingual homepage, routing, config, catalogue integrity.
import os, sys, json, re, tempfile, unittest, threading, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer
from app.db import DB
from app.service import Service
from app.server import make_handler

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static")
OFFICIAL = {"myscheme.gov.in", "nsap.nic.in", "nfsa.gov.in", "serviceplus.gov.in", "crsorgi.gov.in",
            "www.india.gov.in", "india.gov.in", "pmkisan.gov.in", "scholarships.gov.in", "www.education.gov.in",
            "education.gov.in", "www.ncs.gov.in", "ncs.gov.in", "pmjay.gov.in", "eshram.gov.in",
            "udyamregistration.gov.in", "parivahan.gov.in", "voters.eci.gov.in", "www.incometax.gov.in",
            "incometax.gov.in", "www.passportindia.gov.in", "passportindia.gov.in", "rtionline.gov.in",
            "pgportal.gov.in", "web.umang.gov.in", "umang.gov.in", "www.digilocker.gov.in", "digilocker.gov.in"}

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        svc = Service(DB(os.path.join(tempfile.mkdtemp(), "s.db")), env={})
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(svc, "", 600))
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True); cls.th.start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()
    def get(self, path):
        return urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=10)
    def body(self, path):
        return self.get(path).read().decode("utf-8", "replace")

    def test_home_is_seva_landing(self):
        b = self.body("/")
        self.assertIn("seva.css", b); self.assertIn("seva-i18n.js", b); self.assertIn("<title>Seva Setu India</title>", b)
        self.assertIn("hero.searchPh", b)
    def test_app_route_serves_janseva_spa(self):
        b = self.body("/app")
        self.assertIn("/static/app.js", b); self.assertIn("JANSEVA", b)
    def test_dashboard_route(self):
        b = self.body("/dashboard")
        self.assertIn("seva-dash.js", b); self.assertIn("seva-dash.css", b)
        self.assertIn("/api/seva/", open(STATIC + "/seva-dash.js").read())
    def test_landing_login_points_to_dashboard(self):
        b = self.body("/")
        self.assertIn('href="/dashboard"', b)
    def test_info_pages_served(self):
        for slug in ("privacy", "contact", "grievance", "disclaimer", "help"):
            b = self.body("/p/" + slug)
            self.assertIn("seva-pages.js", b)
    def test_config_has_brand_and_wa(self):
        c = json.loads(self.body("/api/config"))
        self.assertEqual(c["brand_name"], "Seva Setu India")
        self.assertTrue(c["wa_number"].isdigit())
    def test_manifest_uses_brand(self):
        m = json.loads(self.body("/manifest.json"))
        self.assertIn("Seva Setu", m["name"])
    def test_eight_languages_aligned(self):
        s = open(os.path.join(STATIC, "seva-i18n.js"), encoding="utf-8").read()
        for code in ("hi", "en", "mr", "bn", "te", "ta", "gu", "kn"):
            self.assertIn('"%s":{' % code, s, code)
        keysets = {}
        for block in re.finditer(r'"(\w{2})":\{(.*?)\n\},\n?"', s, re.S):
            pass  # alignment is verified by key count below
        for code in ("hi", "en", "mr", "bn", "te", "ta", "gu", "kn"):
            m = re.search(r'"%s":\{(.*?)\n\}' % code, s, re.S)
            self.assertIsNotNone(m, code)
            keysets[code] = set(re.findall(r'"([\w.]+)":', m.group(1)))
        base = keysets["en"]
        for code, ks in keysets.items():
            self.assertEqual(ks, base, "key mismatch in " + code)
        self.assertGreaterEqual(len(base), 70)
    def test_catalogue_integrity(self):
        s = open(os.path.join(STATIC, "seva-data.js"), encoding="utf-8").read()
        ids = re.findall(r'\{id:"([\w-]+)"', s)
        self.assertEqual(len(ids), 25)
        self.assertEqual(len(set(ids)), 25)
        for u in re.findall(r'\{u:"([^"]+)"', s):
            self.assertTrue(u.startswith("https://"), u)
            host = u.split("/")[2]
            self.assertIn(host, OFFICIAL, host)
        self.assertIn('"2026-11-28"', s)
    def test_no_fake_promises_in_landing(self):
        b = self.body("/")
        for bad in ("guaranteed approval", "100% approval", "instant approval"):
            self.assertNotIn(bad, b.lower())
        self.assertIn("not a government", self.body("/").lower())

if __name__ == "__main__":
    unittest.main()
