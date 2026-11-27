"""Demo seed (JANSEVA_SEED_DEMO=1). All rows are titled [DEMO] and carry sandbox basis so they are never mistaken for real reports."""
import random
from .db import now

DEMO = [
 ("[DEMO] Garbage dump near bus stop", "Large garbage dump near the bus stop, overflowing dustbin", 18.5204, 73.8567, "pune", "maharashtra", "acknowledged"),
 ("[DEMO] Open drain on main road", "Blocked drain with sewage overflowing onto the road", 18.5314, 73.8446, "pune", "maharashtra", "assigned"),
 ("[DEMO] Pothole near market", "Big pothole near the market causing accidents", 18.4977, 73.8205, "pune", "maharashtra", "in_progress"),
 ("[DEMO] Garbage not collected", "Garbage not collected for a week in our lane", 24.7914, 85.0002, "gaya", "bihar", "authority_marked_resolved"),
 ("[DEMO] Streetlight broken", "Streetlight broken, area is dark at night", 24.7955, 84.9994, "gaya", "bihar", "citizen_verified_resolved"),
 ("[DEMO] Water pipeline leaking", "Water leakage from broken pipeline wasting water", 25.5941, 85.1376, "patna", "bihar", "ready_for_submission"),
 ("[DEMO] Open manhole", "Open manhole without cover near school, danger", 18.5590, 73.7868, "pune", "maharashtra", "escalated"),
 ("[DEMO] Train coach unclean", "Train coach toilet was dirty, railway complaint", 19.0760, 72.8777, "mumbai", "maharashtra", "ready_for_submission"),
]
def seed(svc):
    if svc.db.one("SELECT id FROM complaints LIMIT 1"): return 0
    u = svc.register("0000000000", "Demo Citizen"); n = 0
    for title, desc, la, lo, city, state, status in DEMO:
        r = svc.create_complaint(u, {"title": title, "description": desc, "lat": la, "lon": lo, "city": city, "state": state, "anonymous": False})
        if not r.get("ok"): continue
        svc.db.run("UPDATE complaints SET status=?, official_basis=CASE WHEN ?='ready_for_submission' THEN 'none' ELSE 'sandbox' END, citizen_verified=? WHERE id=?", (status, status, 1 if status == "citizen_verified_resolved" else 0, r["id"]))
        svc.db.timeline(r["id"], "jansevaai", "demo", "Demo record for illustration only. Not a real report.")
        n += 1
    svc.db.audit("system", "demo_seeded", str(n)); return n
