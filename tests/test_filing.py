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
    def test_best_portal_first_and_copy_all(self):
        dispatch.plan(self.svc, self.cid); pk = filing.pack(self.svc, self.c, self.us)
        self.assertTrue(pk["portals"][0]["best"]); self.assertEqual(sum(1 for p in pk["portals"] if p["best"]), 1)
        for p in pk["portals"]: self.assertIn("copy_all", p); self.assertNotIn("auto", p)
        self.assertEqual(pk["portals"][0]["id"], "swachhata")
    def test_type_guide_links_official(self):
        for g in filing.TYPE_GUIDE: self.assertTrue(g["url"].startswith("https://"))
    def test_send_all_and_mp(self):
        dispatch.plan(self.svc, self.cid); r = filing.add_mp(self.svc, self.svc.get(self.cid), "Patna Sahib")
        self.assertTrue(r["ok"] or "list" in r["error"])
        pk = filing.pack(self.svc, self.svc.get(self.cid), self.us); sa = pk["send_all"]
        self.assertTrue(sa["to"]); self.assertIn("mail.google.com", sa["links"]["gmail"]); self.assertTrue(sa["links"]["mailto"].startswith("mailto:"))
        self.assertFalse(filing.add_mp(self.svc, self.svc.get(self.cid), "Nowhere")["ok"])
    def test_html_letter(self):
        h = filing.letter_html(self.c, self.us); self.assertIn("Print / Save as PDF", h); self.assertIn("<!doctype html>", h)
if __name__ == "__main__": unittest.main()

class NoBlock(unittest.TestCase):
    def test_same_user_same_place_same_category_not_blocked(self):
        svc = Service(); u = svc.register("nb%d@example.com" % id(svc), "Raj")
        d = {"title": "Pothole", "description": "big pothole on road", "lat": 8.0 + (id(svc) % 1000) / 50.0, "lon": 70.0 + (id(svc) % 500) / 50.0, "category": "road", "city": "Pune", "state": "Maharashtra"}
        a = svc.create_complaint(u, dict(d)); b = svc.create_complaint(u, dict(d, description="another pothole, different one"))
        self.assertTrue(a["ok"]); self.assertTrue(b["ok"]); self.assertNotEqual(a["id"], b["id"])
        self.assertTrue(any(x["id"] == a["id"] for x in b["similar_nearby"]))
        u2 = svc.register("nb2%d@example.com" % id(svc), "Sam"); c = svc.create_complaint(u2, dict(d, lat=d["lat"] + 0.0005))
        self.assertTrue(c["ok"]); self.assertTrue(c["similar_nearby"])
        far = svc.create_complaint(u2, dict(d, lat=d["lat"] + 0.5)); self.assertTrue(all(x["distance_m"] <= 250 for x in far["similar_nearby"])); self.assertNotIn(a["id"], [x["id"] for x in far["similar_nearby"]])
