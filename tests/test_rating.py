import os, unittest
from app import rating
from app.service import Service
class R(unittest.TestCase):
    def setUp(self):
        self.svc = Service(); self.db = self.svc.db
        self.u1 = self.svc.register("r1%d@example.com" % id(self), "A"); self.u2 = self.svc.register("r2%d@example.com" % id(self), "B")
        self.i1, self.i2 = self.u1["id"] if isinstance(self.u1, dict) else self.u1, self.u2["id"] if isinstance(self.u2, dict) else self.u2
        self.k = rating.entities()[7]["key"]; self.db.run("DELETE FROM rating_reviews WHERE entity_key=?", (self.k,)); self.db.run("DELETE FROM rating_reports"); self.db.run("DELETE FROM rating_likes")
    def test_entities_have_sources(self):
        es = rating.entities(); self.assertGreater(len(es), 500)
        for e in es[:50] + es[-50:]: self.assertTrue(e["source_url"].startswith("http"))
    def test_one_per_user_and_avg(self):
        self.assertTrue(rating.rate(self.db, self.i1, self.k, 5, "Fast response on road repair")["ok"])
        self.assertTrue(rating.rate(self.db, self.i1, self.k, 3)["updated"] if False else rating.rate(self.db, self.i1, self.k, 3)["ok"])
        rating.rate(self.db, self.i2, self.k, 4)
        d = rating.detail(self.db, self.k, self.i1); self.assertEqual(d["count"], 2); self.assertEqual(d["avg"], 3.5)
    def test_validation(self):
        for st in (0, 6, "x"): self.assertFalse(rating.rate(self.db, self.i1, self.k, st)["ok"])
        self.assertFalse(rating.rate(self.db, self.i1, "mp:xx:nobody", 3)["ok"])
        self.assertFalse(rating.rate(self.db, self.i1, self.k, 3, "call him on 9876543210")["ok"])
        self.assertFalse(rating.rate(self.db, self.i1, self.k, 3, "x" * 501)["ok"])
    def test_report_hides_and_moderation(self):
        rating.rate(self.db, self.i1, self.k, 1, "No action on complaint"); rid = self.db.one("SELECT id FROM rating_reviews WHERE entity_key=?", (self.k,))["id"]
        self.assertFalse(rating.like(self.db, self.i1, rid)["ok"]); self.assertTrue(rating.like(self.db, self.i2, rid)["ok"])
        for uid in (101, 102, 103): rating.report(self.db, uid, rid)
        self.assertEqual(rating.detail(self.db, self.k)["count"], 0)
        self.assertEqual(len(rating.moderation_queue(self.db)), 1)
        rating.moderate(self.db, rid, "restore"); self.assertEqual(rating.detail(self.db, self.k)["count"], 1)
        rating.moderate(self.db, rid, "remove"); self.assertFalse(rating.rate(self.db, self.i1, self.k, 2)["ok"])
if __name__ == "__main__": unittest.main()
class Dist(unittest.TestCase):
    def test_district_offices_listed_with_sources(self):
        ds = [e for e in rating.entities() if e["key"].startswith("district:")]
        self.assertGreater(len(ds), 500)
        for e in ds[:30]: self.assertTrue(e["source_url"].startswith("http"))


class TestMLA(unittest.TestCase):
    def test_mla_entities_sourced(self):
        from app import rating
        m = [e for e in rating.entities() if e["type"] == "MLA"]
        self.assertGreater(len(m), 4000)
        self.assertTrue(all(e["source_url"].startswith("https://") and e["last_verified"] for e in m))
        self.assertGreaterEqual(len({e["state"] for e in m}), 30)


class TestLocalBodies(unittest.TestCase):
    def test_local_bodies_in_directory_with_source(self):
        from app import rating, localbody
        e = rating.entities()
        lb = [x for x in e if x["type"].startswith("Local body")]
        self.assertGreater(len(lb), 5000)
        self.assertGreater(len([x for x in e if x["type"].startswith("State department")]), 100)
        self.assertTrue(all(x["source_url"].startswith("https://") for x in lb))
        r = localbody.find("Pune", "Maharashtra"); self.assertEqual(r["status"], "matched"); self.assertEqual(r["bodies"][0]["ulb_type"], "Municipal Corporation")
        self.assertEqual(localbody.find("Nowhereville", "Maharashtra")["status"], "not_found")


class TestUlbContacts(unittest.TestCase):
    def test_contacts_sourced_and_used(self):
        import json
        from app import localbody
        from app.dispatch import ladder
        rows = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "ulb_contacts.json")))
        self.assertGreater(len(rows), 100)
        for r in rows:
            self.assertTrue(r["website"].startswith("https://")); self.assertIn(r["website_kind"], ("ulb_own_site", "district_site_listing", "state_cdma_portal_page"))
            for e in r["emails"]: self.assertTrue(e["found_on"].startswith("https://") and e["email"].endswith((".gov.in", ".nic.in")))
        l = ladder({"category": "garbage", "city": "Bhubaneswar", "state": "Odisha"})
        self.assertTrue(any(t["kind"] == "local_body_published_email" and t["email"].endswith("bmc.gov.in") for t in l))
