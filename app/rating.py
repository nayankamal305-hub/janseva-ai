"""JANSEVA Rating: citizens rate how well PUBLIC OFFICES solve problems. Entities are public roles taken only from official datasets
(sansad.in MPs, pgportal ministry / state nodal offices). No private data, no invented officials. MLAs and district collectors have no official
machine-readable dataset yet, so they are NOT listed (never guessed). Ratings are opinions of logged-in citizens, not official performance data."""
import re, time
from .service import load_data
MAX_COMMENT = 500; REPORT_HIDE = 3; DAY_LIMIT = 15
# abusive / personal-attack screening: blocks obvious slurs and personal contact data; moderation + reports handle the rest
BAD = re.compile(r"\b(madarchod|bhosdi\w*|chutiy\w*|bc|mc|randi|harami|saala|kutta|kamina|bastard|fuck\w*|bitch|slut|idiot|corrupt thief)\b", re.I)
PII = re.compile(r"(\+?\d[\d\s-]{8,}\d|[\w.+-]+@[\w-]+\.[\w.]+|https?://)", re.I)
def _now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def entities():
    out = []
    for m in load_data("representatives_parliament.json"):
        out.append({"key": "mp:%s:%s" % (m["house"][:2].lower(), m["name"].lower().replace(" ", "-")), "type": "MP (%s)" % m["house"], "title": "%s, %s" % (m["name"], m["constituency"] or m["state"]), "state": m["state"], "party": m.get("party"), "source_url": m["source_url"], "last_verified": m["last_verified"]})
    for a in load_data("authorities_central_nodal.json"):
        out.append({"key": "ministry:" + a["name"].lower().replace(" ", "-"), "type": "Ministry / Department (PG office)", "title": a["name"], "state": None, "source_url": a["source_url"], "last_verified": a["last_verified"]})
    for a in load_data("authorities_state_nodal.json"):
        out.append({"key": "state-pg:" + a["name"].lower().replace(" ", "-"), "type": "State/UT grievance cell", "title": a["name"], "state": a["name"], "source_url": a["source_url"], "last_verified": a["last_verified"]})
    for d in load_data("igod_districts.json"):
        if d.get("website"):
            out.append({"key": "district:%s:%s" % ((d["state"] or "").lower().replace(" ", "-"), d["title"].lower().replace(" ", "-")), "type": "District administration (partial: official district site only)", "title": "%s district administration, %s" % (d["title"], d["state"]), "state": d["state"], "source_url": d["website"], "last_verified": d["last_verified"]})
    return out
_IDX = {}
def lookup(key):
    if not _IDX: _IDX.update({e["key"]: e for e in entities()})
    return _IDX.get(key)
def search(db, q="", typ="", state="", sort="rating", limit=40):
    q = (q or "").lower(); res = []
    stats = {r["entity_key"]: r for r in db.all("SELECT entity_key, COUNT(*) n, ROUND(AVG(stars),2) avg FROM rating_reviews WHERE status='visible' GROUP BY entity_key")}
    for e in entities():
        if q and q not in e["title"].lower() and q not in (e.get("party") or "").lower(): continue
        if typ and not e["type"].lower().startswith(typ.lower()): continue
        if state and (e.get("state") or "").lower() != state.lower(): continue
        s = stats.get(e["key"]); e = dict(e, count=s["n"] if s else 0, avg=s["avg"] if s else None); res.append(e)
    res.sort(key=lambda e: (-(e["count"] > 0), -(e["avg"] or 0), -e["count"], e["title"]) if sort == "rating" else (e["title"],))
    return res[:limit]
def detail(db, key, uid=None):
    e = lookup(key)
    if not e: return None
    s = db.one("SELECT COUNT(*) n, ROUND(AVG(stars),2) avg FROM rating_reviews WHERE entity_key=? AND status='visible'", (key,))
    dist = {r["stars"]: r["n"] for r in db.all("SELECT stars, COUNT(*) n FROM rating_reviews WHERE entity_key=? AND status='visible' GROUP BY stars", (key,))}
    revs = db.all("SELECT r.id, r.stars, r.comment, r.created_at, (SELECT COUNT(*) FROM rating_likes l WHERE l.review_id=r.id) likes, (r.user_id=?) mine FROM rating_reviews r WHERE entity_key=? AND status='visible' AND comment IS NOT NULL AND comment!='' ORDER BY likes DESC, r.id DESC LIMIT 50", (uid or -1, key))
    mine = db.one("SELECT stars, comment FROM rating_reviews WHERE entity_key=? AND user_id=?", (key, uid)) if uid else None
    return {"entity": e, "count": s["n"], "avg": s["avg"], "distribution": {i: dist.get(i, 0) for i in range(1, 6)}, "reviews": revs, "mine": dict(mine) if mine else None,
            "disclaimer": "Citizen opinions about public work only. Not official performance data. Reviews are anonymous to the public."}
def rate(db, uid, key, stars, comment=""):
    if not lookup(key): return {"ok": False, "error": "unknown office"}
    try: stars = int(stars)
    except Exception: return {"ok": False, "error": "stars must be 1-5"}
    if not 1 <= stars <= 5: return {"ok": False, "error": "stars must be 1-5"}
    comment = (comment or "").strip()
    if len(comment) > MAX_COMMENT: return {"ok": False, "error": "comment too long (max %d)" % MAX_COMMENT}
    if comment and (BAD.search(comment)): return {"ok": False, "error": "Please keep comments civil and about public work."}
    if comment and PII.search(comment): return {"ok": False, "error": "Do not include phone numbers, emails or links."}
    n = db.one("SELECT COUNT(*) n FROM rating_reviews WHERE user_id=? AND updated_at>=?", (uid, time.strftime("%Y-%m-%dT00:00:00")))["n"]
    if n >= DAY_LIMIT: return {"ok": False, "error": "Daily rating limit reached."}
    old = db.one("SELECT id, status FROM rating_reviews WHERE entity_key=? AND user_id=?", (key, uid))
    if old:
        if old["status"] == "removed": return {"ok": False, "error": "Your review was removed by moderation."}
        db.run("UPDATE rating_reviews SET stars=?, comment=?, updated_at=? WHERE id=?", (stars, comment, _now(), old["id"])); return {"ok": True, "updated": True}
    db.run("INSERT INTO rating_reviews(entity_key,user_id,stars,comment,created_at,updated_at) VALUES(?,?,?,?,?,?)", (key, uid, stars, comment, _now(), _now())); return {"ok": True, "updated": False}
def like(db, uid, rid):
    r = db.one("SELECT user_id FROM rating_reviews WHERE id=? AND status='visible'", (rid,))
    if not r: return {"ok": False, "error": "not found"}
    if r["user_id"] == uid: return {"ok": False, "error": "cannot like your own review"}
    db.run("INSERT OR IGNORE INTO rating_likes VALUES(?,?)", (rid, uid)); return {"ok": True}
def report(db, uid, rid, reason=""):
    if not db.one("SELECT id FROM rating_reviews WHERE id=?", (rid,)): return {"ok": False, "error": "not found"}
    db.run("INSERT OR IGNORE INTO rating_reports VALUES(?,?,?,?)", (rid, uid, (reason or "")[:200], _now()))
    n = db.one("SELECT COUNT(*) n FROM rating_reports WHERE review_id=?", (rid,))["n"]
    if n >= REPORT_HIDE: db.run("UPDATE rating_reviews SET status='hidden' WHERE id=? AND status='visible'", (rid,))
    return {"ok": True, "hidden": n >= REPORT_HIDE}
def moderation_queue(db): return db.all("SELECT r.id, r.entity_key, r.stars, r.comment, r.status, (SELECT COUNT(*) FROM rating_reports x WHERE x.review_id=r.id) reports FROM rating_reviews r WHERE status='hidden' OR EXISTS(SELECT 1 FROM rating_reports x WHERE x.review_id=r.id) ORDER BY r.id DESC LIMIT 100")
def moderate(db, rid, action):
    st = {"restore": "visible", "remove": "removed", "hide": "hidden"}.get(action)
    if not st: return {"ok": False, "error": "action must be restore/remove/hide"}
    db.run("UPDATE rating_reviews SET status=? WHERE id=?", (st, rid))
    if st == "visible": db.run("DELETE FROM rating_reports WHERE review_id=?", (rid,))
    return {"ok": True}
