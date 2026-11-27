"""Public dashboard, feed, map, reports. Privacy: no phone/name/address, approximate coordinates (3 decimals), photos only after approval.
Only live government-confirmed records count as 'officially submitted'; sandbox and guided records are reported separately."""
import csv, io
from datetime import datetime, timedelta, timezone

def _where(f):
    w, a = ["c.status NOT IN ('draft') AND c.anonymous>=0"], []
    if f.get("state"): w.append("c.state=?"); a.append(f["state"].lower())
    if f.get("city"): w.append("c.city=?"); a.append(f["city"].lower())
    if f.get("category"): w.append("c.category=?"); a.append(f["category"])
    if f.get("status"): w.append("c.status=?"); a.append(f["status"])
    if f.get("severity"): w.append("c.severity>=?"); a.append(int(f["severity"]))
    if f.get("days"):
        w.append("c.created_at>=?"); a.append((datetime.now(timezone.utc) - timedelta(days=int(f["days"]))).isoformat())
    if f.get("from"): w.append("c.created_at>=?"); a.append(f["from"])
    if f.get("to"): w.append("c.created_at<=?"); a.append(f["to"])
    if f.get("department"):
        w.append("EXISTS(SELECT 1 FROM external_records e WHERE e.complaint_id=c.id AND e.department LIKE ?)"); a.append("%" + f["department"] + "%")
    return " AND ".join(w), a

def feed(db, f, limit=50):
    w, a = _where(f)
    rows = db.all("SELECT c.id,c.code,c.category,c.created_at,c.city,c.state,c.status,c.severity,c.emergency,c.official_basis,c.photo_url,c.photo_public_ok,c.duplicate_group,c.lat,c.lon "
                  "FROM complaints c WHERE " + w + " ORDER BY c.id DESC LIMIT ?", a + [limit])
    out = []
    for r in rows:
        ex = db.all("SELECT platform_id,department,external_ref,mode,reference_source,status FROM external_records WHERE complaint_id=?", (r["id"],))
        sup = db.one("SELECT count(*) n FROM supports WHERE complaint_id=? AND kind='support'", (r["id"],))["n"]
        out.append({"id": r["id"], "code": r["code"], "category": r["category"], "reported": r["created_at"][:10], "city": r["city"], "state": r["state"], "status": r["status"],
                    "severity": r["severity"], "emergency": bool(r["emergency"]), "basis": r["official_basis"],
                    "approx_lat": round(r["lat"], 3), "approx_lon": round(r["lon"], 3), "supporters": sup + 1,
                    "photo": r["photo_url"] if r["photo_public_ok"] else None,
                    "official_ids": [{"platform": e["platform_id"], "ref": e["external_ref"]} for e in ex if e["mode"] == "live" and e["reference_source"] == "government_response"],
                    "departments_verified": sorted({e["department"] for e in ex if e["mode"] == "live"}),
                    "label": "User-reported" + (", sandbox test" if r["official_basis"] == "sandbox" else "")})
    return out

def stats(db, f):
    w, a = _where(f)
    q = lambda extra="", args=(): db.one("SELECT count(*) n FROM complaints c WHERE " + w + extra, a + list(args))["n"]
    total = q()
    live_sub = q(" AND c.official_basis IN ('government_confirmed')")
    resolved_auth = q(" AND c.status IN ('authority_marked_resolved','citizen_verified_resolved')")
    verified = q(" AND c.status='citizen_verified_resolved'")
    rejected = q(" AND c.status='rejected'")
    closed_like = ('citizen_verified_resolved', 'rejected', 'closed')
    pending = q(" AND c.status NOT IN ('citizen_verified_resolved','rejected','closed')")
    times = db.all("SELECT c.created_at, c.updated_at FROM complaints c WHERE " + w + " AND c.status='citizen_verified_resolved'", a)
    avg = None
    if times:
        d = [(datetime.fromisoformat(t["updated_at"]) - datetime.fromisoformat(t["created_at"])).total_seconds() / 3600 for t in times]; avg = round(sum(d) / len(d), 1)
    by = lambda col: db.all("SELECT c.%s k, count(*) n FROM complaints c WHERE %s GROUP BY c.%s ORDER BY n DESC LIMIT 20" % (col, w, col), a)
    overdue = 0; plats = {x["id"]: x for x in db.platforms()}
    for r in db.all("SELECT e.platform_id, e.submitted_at FROM external_records e JOIN complaints c ON c.id=e.complaint_id WHERE " + w + " AND e.external_ref IS NOT NULL AND e.status NOT IN ('resolved','rejected') AND e.submitted_at IS NOT NULL", a):
        if datetime.now(timezone.utc) - datetime.fromisoformat(r["submitted_at"]) > timedelta(days=plats.get(r["platform_id"], {}).get("sla_days", 7)): overdue += 1
    acks = db.all("SELECT c.created_at, e.acknowledged_at FROM complaints c JOIN external_records e ON e.complaint_id=c.id WHERE " + w + " AND e.acknowledged_at IS NOT NULL", a)
    ack_h = round(sum((datetime.fromisoformat(x["acknowledged_at"]) - datetime.fromisoformat(x["created_at"])).total_seconds() for x in acks) / len(acks) / 3600, 2) if acks else None
    return {"overdue_records": overdue, "avg_hours_to_acknowledgement": ack_h, "total_reported": total, "user_reported": total,
            "ai_analysed": q(" AND c.confidence IS NOT NULL"),
            "officially_submitted_government_confirmed": live_sub,
            "sandbox_test_complaints": q(" AND c.official_basis='sandbox'"),
            "citizen_reported_reference_only": q(" AND c.official_basis='citizen_reported'"),
            "authority_marked_resolved": resolved_auth, "citizen_verified_resolved": verified, "pending": pending, "rejected": rejected,
            "reopened": q(" AND c.status='reopened'"), "emergency_flagged": q(" AND c.emergency=1"),
            "avg_hours_to_verified_resolution": avg,
            "resolution_percent_citizen_verified": round(100 * verified / total, 1) if total else None,
            "by_state": by("state"), "by_city": by("city"), "by_category": by("category"), "by_status": by("status"),
            "disclosure": "Counts are of reports on this platform, not of all issues. Only government-confirmed (live) submissions count as officially submitted. Overdue uses each platform's configured SLA days (not statutory unless the platform publishes them). Cost per verified resolution is not computed (no cost data)."}

def heatmap(db, f, cell=0.01):
    w, a = _where(f)
    rows = db.all("SELECT round(c.lat/%s)*%s la, round(c.lon/%s)*%s lo, count(*) n FROM complaints c WHERE %s GROUP BY la,lo" % (cell, cell, cell, cell, w), a)
    return [{"lat": round(r["la"], 3), "lon": round(r["lo"], 3), "count": r["n"]} for r in rows]

def monthly_report(db, month, fmt="json"):
    f = {"from": month + "-01", "to": month + "-31T23:59:59"}
    s = stats(db, f)
    if fmt != "csv": return s
    buf = io.StringIO(); wr = csv.writer(buf); wr.writerow(["metric", "value"])
    for k, v in s.items():
        if not isinstance(v, (list, dict)): wr.writerow([k, v])
    for k in ("by_state", "by_category"):
        for r in s[k]: wr.writerow(["%s:%s" % (k, r["k"]), r["n"]])
    return buf.getvalue()
