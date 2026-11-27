from app.db import guard_test_database_url as _g; _g()
"""Read-only / no-send acceptance: with every consent ticked, JANSEVA itself must send no complaint email, post nothing to X, and register nothing.
Also guards the wording: the UI must not promise official email/portal/X sending or automatic reminders."""
import json, os, re, tempfile, threading, unittest, urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock
from app import mailer, social
from app.db import DB
from app.server import make_handler
from app.service import Service
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static")

class NoSend(unittest.TestCase):
    def setUp(self):
        self.svc = Service(DB(os.path.join(tempfile.mkdtemp(), "n.db")), env={})
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.svc, "adm")); threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]
    def tearDown(self): self.srv.shutdown()
    def call(self, m, p, d=None, tok=None):
        req = urllib.request.Request(self.base + p, method=m, data=json.dumps(d).encode() if d is not None else None)
        if tok: req.add_header("Authorization", "Bearer " + tok)
        return json.loads(urllib.request.urlopen(req).read())
    def test_all_consents_still_sends_nothing(self):
        env = {"EMAIL_PROVIDER": "brevo", "BREVO_API_KEY": "k", "MAIL_FROM": "J <a@b.com>"}
        os.environ.pop("JANSEVA_SERVER_EMAIL", None); os.environ.pop("JANSEVA_X_AUTOPOST", None)
        with mock.patch.dict(os.environ, env), mock.patch.object(mailer, "_post", side_effect=AssertionError("server sent email")) as mp, \
             mock.patch.object(social, "enqueue", side_effect=AssertionError("X post queued")) as xq:
            tok = self.call("POST", "/api/register", {"phone": "9000000123", "name": "N"})["token"]
            c = self.call("POST", "/api/complaints", {"title": "t", "description": "garbage dump near my house", "lat": 19.07, "lon": 72.87, "city": "Mumbai", "state": "Maharashtra", "category": "garbage"}, tok)
            s = self.call("POST", "/api/complaints/%d/submit" % c["id"], {"consent_submit": True, "consent_share_personal": True, "consent_email": True, "reply_to_user": True, "consent_x": True, "notify_representative": True}, tok)
            self.assertTrue(s["ok"]); mp.assert_not_called(); xq.assert_not_called()
            self.assertEqual(s["email_dispatch"]["mode"], "citizen_own_email")
            self.assertFalse(self.svc.db.all("SELECT * FROM dispatches WHERE status='sent'"))
            from app import dispatch
            dispatch.tick(self.svc); mp.assert_not_called()
            f = self.call("GET", "/api/complaints/%d/filing" % c["id"], tok=tok)
            self.assertTrue(f["portals"]); self.assertFalse(any(r["status"] == "officially_submitted" for r in self.svc.db.all("SELECT status FROM complaints")))
            self.assertFalse(self.svc.db.all("SELECT * FROM external_records WHERE external_ref IS NOT NULL AND mode='live'"))
    def test_ui_wording_makes_no_unverified_promises(self):
        txt = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read() + open(os.path.join(ROOT, "app.js"), encoding="utf-8").read()
        for bad in ["reminders at 7", "queued for the JANSEVA", "Sent by JANSEVA", "Submit through matching official channels", "Sent with consent", "Sends it by official email", "emailed only with your consent", "Done. JANSEVA ID", "posted when slot is free", "Tag concerned authorities on X"]:
            self.assertNotIn(bad, txt, bad)
        self.assertIn("Saved in JANSEVA", txt); self.assertIn("you send or file it yourself", txt); self.assertIn("Registered only with a real authority reference", txt)
if __name__ == "__main__": unittest.main()
