import json, unittest
from app import dispatch
from app.service import load_data
class C(unittest.TestCase):
    def test_every_state_and_ut_gets_a_state_nodal_officer(self):
        miss = []
        for r in load_data("coverage.json"):
            l = dispatch.ladder({"category": "general", "state": r["state"]})
            if not any(t["level"] == 2 for t in l): miss.append(r["state"])
        self.assertEqual(miss, [], "states without L2 officer: %s" % miss)
    def test_alias_names(self):
        for n in ("Delhi", "NCT of Delhi", "Jammu & Kashmir", "Keralam", "Chhattisgarh"):
            self.assertTrue(any(t["level"] == 2 for t in dispatch.ladder({"category": "general", "state": n})), n)
