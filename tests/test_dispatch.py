from app.db import guard_test_database_url as _g; _g()
import json, os, unittest
from unittest import mock
from app import dispatch, mailer
from app.db import DB
from app.service import Service
class D(unittest.TestCase):
    def setUp(self):
        p = "/tmp/dsp.db"
        if os.path.exists(p): os.remove(p)
        self.svc = Service(db_path=p) if "db_path" in Service.__init__.__code__.co_varnames else Service()
    def mk(self, **kw):
        u = self.svc.register("t%d@example.com" % id(kw), "Asha")
        r = self.svc.create_complaint(u, {"title": "No water supply", "description": "no water supply for days, pipeline leak", "lat": 25.59, "lon": 85.13, "city": "Patna", "state": "Bihar"})
        cid = r["id"]; self.svc.db.run("UPDATE complaints SET consent_submit=1,consent_share_personal=1,consent_email=?,category='water' WHERE id=?", (kw.get("consent", 1), cid)); return cid
    def test_ladder_sources(self):
        c = {"category": "water", "state": "Bihar"}
        l = dispatch.ladder(c); self.assertTrue(l)
        for t in l: self.assertTrue(t["source_url"].startswith("http")); self.assertTrue(t["source_date"]); self.assertNotIn(t["email"].split("@")[0], dispatch.BLOCK_LOCAL)
        self.assertIn(2, [t["level"] for t in l]); self.assertIn(3, [t["level"] for t in l])
    def test_company_ladder(self):
        l = dispatch.ladder({"company": "Swiggy", "category": "consumer", "state": "Bihar"}); self.assertEqual([t["email"] for t in l], ["grievances@swiggy.in"])
        self.assertEqual(dispatch.ladder({"company": "Zomato"}), [])
    def test_mp_only_with_constituency_and_optin(self):
        self.assertFalse([t for t in dispatch.ladder({"category": "water", "state": "Bihar"}) if t["level"] == 4])
    def test_no_consent_no_plan(self):
        cid = self.mk(consent=0); self.assertFalse(dispatch.plan(self.svc, cid)["ok"])
    def test_send_flow_and_caps(self):
        cid = self.mk(); env = {"JANSEVA_SERVER_EMAIL": "1", "EMAIL_PROVIDER": "brevo", "BREVO_API_KEY": "k", "MAIL_FROM": "J <a@b.com>"}
        with mock.patch.dict(os.environ, env), mock.patch.object(mailer, "_post", return_value={"sent": True}) as p:
            pl = dispatch.plan(self.svc, cid); self.assertTrue(pl["ok"])
            r = dispatch.send_due(self.svc, cid)
            self.assertGreaterEqual(r["sent"], 1); self.assertLessEqual(r["sent"], dispatch.MAX_INITIAL)
            body = p.call_args[0][2]; self.assertIn("Asha via JANSEVA AI", body["sender"]["name"]); self.assertIn("JS-", body["subject"])
            n = r["sent"]; self.assertEqual(dispatch.send_due(self.svc, cid)["sent"], 0)  # no duplicates, later levels not yet due
        self.svc.db.run("UPDATE complaints SET status='citizen_verified_resolved' WHERE id=?", (cid,))
        self.svc.db.run("UPDATE dispatches SET due_at='2000-01-01' WHERE status='scheduled'")
        with mock.patch.dict(os.environ, env), mock.patch.object(mailer, "_post", return_value={"sent": True}):
            self.assertEqual(dispatch.send_due(self.svc, cid)["sent"], 0)  # resolved: reminders/escalations cancelled
if __name__ == "__main__": unittest.main()
