from app.db import guard_test_database_url as _g; _g()
import os, unittest
from unittest import mock
from app import social
from app.service import Service
class X(unittest.TestCase):
    def setUp(self):
        self.svc = Service(); db = self.svc.db; db.run("DELETE FROM x_queue")
        u = self.svc.register("x%d@example.com" % id(self), "X")
        self.cid = self.svc.create_complaint(u, {"title": "No power", "description": "power cut 3 days", "lat": 25.5, "lon": 85.1, "city": "Patna", "state": "Bihar"})["id"]
        db.run("UPDATE complaints SET category='electricity', consent_submit=1 WHERE id=?", (self.cid,))
    def test_needs_consent(self): self.assertFalse(social.enqueue(self.svc, self.cid)["ok"])
    def test_flow(self):
        self.svc.db.run("UPDATE complaints SET consent_x=1 WHERE id=?", (self.cid,))
        h = sorted(social.known_handles())[0]
        with mock.patch.object(social, "draft", return_value={"text": "No power for 3 days in Patna, Bihar. Tracking JS-1 @%s #JANSEVA" % h}):
            r = social.enqueue(self.svc, self.cid)
        self.assertTrue(r["ok"], r)
        self.assertFalse(social.enqueue(self.svc, self.cid, "x")["ok"])
        self.assertFalse(social.enqueue(self.svc, self.cid, "@nobody fake")["ok"])
        it = social.next_pending(self.svc)["item"]; self.assertEqual(it["complaint_id"], self.cid)
        self.assertEqual(social.next_pending(self.svc)["item"], None)
        self.assertFalse(social.mark(self.svc, it["id"], True, "http://evil/x")["ok"])
        self.assertTrue(social.mark(self.svc, it["id"], True, "https://x.com/jansevaai/status/1234567890123")["ok"])
    def test_cap_and_abuse(self):
        with mock.patch.dict(os.environ, {"X_DAILY_CAP": "0"}): self.assertEqual(social.next_pending(self.svc)["reason"], "daily cap reached")
        self.svc.db.run("UPDATE complaints SET consent_x=1 WHERE id=?", (self.cid,))
        self.assertFalse(social.enqueue(self.svc, self.cid, "Officer is a thief @x")["ok"])
if __name__ == "__main__": unittest.main()
class H(unittest.TestCase):
    def test_extra_handles_have_sources(self):
        from app.service import load_data
        e = load_data("social_handles_extra.json"); assert len(e) >= 5
        for x in e: assert x["found_on"].startswith("https://") and x["last_verified"]
class T(unittest.TestCase):
    def test_state_district_tags(self):
        class D:
            def one(s, *a): return {"category": "electricity", "state": "Bihar", "city": "Patna", "title": "x", "code": "JS-1"}
        class S: db = D()
        r = social.draft(S(), 1); self.assertIn("MinOfPower", r["tags"]); self.assertLessEqual(len(r["tags"]), 3)
        for x in r["tag_sources"]: self.assertTrue(x["found_on"].startswith("http"))
