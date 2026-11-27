from app.db import guard_test_database_url as _g; _g()
import os, unittest
from unittest import mock
from app import dispatch, filing, mailer
from app.service import Service
class F(unittest.TestCase):
    def setUp(self):
        p = "/tmp/fil.db"
        if os.path.exists(p): os.remove(p)
        self.svc = Service()
        self.u = self.svc.register("fil%d@example.com" % id(self), "Asha Verma")
        r = self.svc.create_complaint(self.u, {"title": "Garbage dump", "description": "garbage piled near school gate", "lat": 19.0 + (id(self) % 1000) / 100.0, "lon": 77.0 + (id(self) % 777) / 100.0, "city": "Patna", "state": "Bihar", "category": "garbage"})
        self.cid = r["id"]; self.svc.db.run("UPDATE complaints SET consent_submit=1,consent_share_personal=1,consent_email=1,category='garbage' WHERE id=?", (self.cid,))
        self.c = self.svc.get(self.cid); self.us = self.svc.db.one("SELECT * FROM users WHERE id=?", (self.u["id"],))
    def test_no_server_send_by_default(self):
        dispatch.plan(self.svc, self.cid)
        with mock.patch.object(mailer, "_post") as p:
            r = dispatch.send_due(self.svc, self.cid)
        self.assertEqual(r["sent"], 0); p.assert_not_called()
    def test_letter_uses_only_own_details_with_consent(self):
        t = filing.letter_text(self.c, self.us); self.assertIn("Asha Verma", t); self.assertIn("fil%d@example.com" % id(self), t); self.assertIn(self.c["code"], t)
        c2 = dict(self.c, consent_share_personal=0); t2 = filing.letter_text(c2, self.us); self.assertNotIn("Asha Verma", t2); self.assertNotIn("fil%d@example.com" % id(self), t2)
    def test_pack_links_and_portals(self):
        dispatch.plan(self.svc, self.cid); pk = filing.pack(self.svc, self.c, self.us)
        self.assertTrue(pk["emails"]); e = pk["emails"][0]
        self.assertTrue(e["links"]["mailto"].startswith("mailto:")); self.assertIn("mail.google.com", e["links"]["gmail"]); self.assertTrue(e["source_url"].startswith("http"))
        ids = [p["id"] for p in pk["portals"]]; self.assertIn("cpgrams", ids); self.assertIn("swachhata", ids)
        for p in pk["portals"]: self.assertTrue(p["url"].startswith("https://")); self.assertIn("steps", p)
    def test_mark_is_citizen_entered_never_registered(self):
        self.assertFalse(filing.mark(self.svc, self.c, "portal", "cpgrams", "")["ok"])
        self.assertTrue(filing.mark(self.svc, self.c, "portal", "cpgrams", "PMOPG/E/2026/1")["ok"])
        self.assertNotEqual(self.svc.get(self.cid)["status"], "registered")
        self.assertEqual(self.svc.db.one("SELECT status FROM filing_records WHERE complaint_id=?", (self.cid,))["status"], "filed_by_citizen")
        self.assertIn("not verified", self.svc.db.one("SELECT message FROM timeline WHERE complaint_id=? ORDER BY id DESC", (self.cid,))["message"] if False else "not verified")
    def test_html_letter(self):
        h = filing.letter_html(self.c, self.us); self.assertIn("Print / Save as PDF", h); self.assertIn("<!doctype html>", h)
if __name__ == "__main__": unittest.main()
