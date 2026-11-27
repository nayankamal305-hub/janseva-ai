import json, os, unittest
from app import accounts, mailer
from app.service import load_data
class V05(unittest.TestCase):
    def test_idents(self):
        self.assertEqual(accounts.norm_ident("A@B.com"), "a@b.com"); self.assertEqual(accounts.norm_ident("+91 98765 43210"), "9876543210"); self.assertIsNone(accounts.norm_ident("x"))
    def test_no_smtp_no_send(self):
        self.assertFalse(mailer.send("a@b.com", "s", "b", env={})["sent"])
    def test_tracking_code(self):
        self.assertEqual(mailer.tracking_code("Re: [JSV-AB12CD] grievance"), "JSV-AB12CD"); self.assertIsNone(mailer.tracking_code("hello"))
    def test_directory(self):
        st = load_data("authorities_state_nodal.json"); cen = load_data("authorities_central_nodal.json"); mp = load_data("representatives_parliament.json")
        self.assertGreaterEqual(len(st), 36); self.assertGreaterEqual(len(cen), 80); self.assertGreaterEqual(len(mp), 700)
        for r in st + cen: self.assertTrue(r["source_url"].startswith("https://pgportal.gov.in")); self.assertEqual(r["email_accepts_citizen_complaints"], "unverified")

class V06(unittest.TestCase):
    def test_igod(self):
        self.assertGreaterEqual(len(load_data("igod_districts.json")), 780); self.assertGreaterEqual(len(load_data("igod_state_ut.json")), 6000)
        self.assertEqual(sum(1 for r in load_data("igod_state_ut.json") if r["type"] == "SPORT"), 36)
        for r in load_data("igod_districts.json")[:50]: self.assertTrue(r["source"].startswith("https://www.india.gov.in"))
class V07(unittest.TestCase):
    def test_utility_contacts(self):
        for r in load_data("utility_contacts.json"):
            for e in r["emails_published_on_official_page"]: self.assertIn("@", e["email"]); self.assertTrue(e["found_on"].startswith("http"))
            self.assertEqual(r["accepts_citizen_complaints"], "unverified")

if __name__ == "__main__": unittest.main()
