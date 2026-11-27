import os, tempfile, unittest
from app.db import DB, now
from app import density

class TestDensity(unittest.TestCase):
    def setUp(self): self.db = DB(os.path.join(tempfile.mkdtemp(), "d.db"))
    def _c(self, lat, lon, status="submitted"):
        self.db.run("INSERT INTO complaints(code,user_id,title,description,category,lat,lon,status,created_at,updated_at,anonymous) VALUES(?,?,?,?,?,?,?,?,?,?,0)",
                    ("C%s%s" % (lat, lon), 1, "t", "d", "garbage", lat, lon, status, now(), now()))
    def test_points_land_in_right_state_and_district(self):
        for (la, lo, st, di) in [(18.52, 73.86, "MAHARASHTRA", "Pune"), (28.61, 77.21, "DELHI", "New Delhi"), (12.97, 77.59, "KARNATAKA", "Bengaluru Urban")]:
            self.assertEqual(density.locate(la, lo, "states")["name"], st); self.assertEqual(density.locate(la, lo, "districts")["name"], di)
        self.assertIsNone(density.locate(15.0, 60.0, "states"))
    def test_empty_is_honest(self):
        r = density.density(self.db, {}); self.assertTrue(r["empty"]); self.assertEqual((r["total"], r["states"], r["districts"]), (0, {}, {}))
    def test_counts_are_real_and_drafts_excluded(self):
        self._c(18.52, 73.86); self._c(18.53, 73.85); self._c(28.61, 77.21); self._c(15.0, 60.0); self._c(19.0, 73.0, "draft")
        r = density.density(self.db, {})
        self.assertEqual(r["total"], 4); self.assertEqual(r["unlocated"], 1); self.assertEqual(r["states"]["27"], 2); self.assertEqual(r["states"]["7"], 1)
        self.assertEqual(sum(r["districts"].values()), 3)
        self.assertNotIn("lat", str(r)); self.assertFalse(r["empty"])
    def test_geo_files_present_and_small(self):
        d = os.path.join(os.path.dirname(density.__file__), "static", "geo")
        self.assertLess(os.path.getsize(os.path.join(d, "india_districts.geojson")), 1_200_000)
        self.assertEqual(len(density._load("states")), 36); self.assertEqual(len(density._load("districts")), 785)
