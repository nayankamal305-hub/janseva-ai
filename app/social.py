"""Public tagging on X without paying for the X API: JANSEVA prepares the post and the CITIZEN publishes it from their own X account via an
intent link (free). Handles come only from links found on official sites (data/social_handles.json, each with the page it was found on).
MP/MLA/collector handles are not available from official machine-readable sources and are never guessed."""
import urllib.parse, re
from .service import load_data
# social_handles_extra.json: operator-verified entries {"title","x_handles":[..],"found_on":url,"last_verified":date,"state"?}; a handle is only added after it is seen on an official page.
KW = {"water": ["water", "jal shakti", "jal"], "road": ["road", "highways", "morth"], "railway": ["railway", "railways"], "electricity": ["power", "electricity"], "consumer": ["consumer"],"police": ["home affairs"],
      "garbage": ["housing and urban"], "drainage": ["housing and urban"], "toilet": ["housing and urban"], "pension": ["pension"]}
GENERIC = {"narendramodi", "jpnadda", "ndtvprofit"}
def draft(svc, cid):
    c = svc.db.one("SELECT * FROM complaints WHERE id=?", (cid,))
    if not c: return {"ok": False, "error": "not found"}
    hs = load_data("social_handles.json") + load_data("social_handles_extra.json"); tags = []; src = []
    for h in hs:
        t = h["title"].lower()
        hit = any(re.search(r"\b"+re.escape(k)+r"\b", t) for k in KW.get(c["category"] or "", [])) or (c["state"] and c["state"].lower() in (h.get("state") or "").lower() and "portal" in t)
        if hit:
            for x in h["x_handles"]:
                if x.lower() not in GENERIC and x not in tags and len(tags) < 3: tags.append(x); src.append({"handle": x, "found_on": h["found_on"], "listed_for": h["title"], "last_verified": h["last_verified"]})
    loc = ", ".join(x for x in (c["city"], c["state"]) if x)
    body = "%s at %s. Unresolved. Tracking %s" % ((c["title"] or "Public issue")[:110], loc, c["code"])
    text = (body + " " + " ".join("@" + t for t in tags) + " #JANSEVA").strip()[:280]
    return {"ok": True, "text": text, "tags": tags, "tag_sources": src, "intent_url": "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(text),
            "note": "Review before posting. You post it from your own X account; JANSEVA does not post for you. Handles are linked on official sites and may belong to a related office. MP/MLA/collector handles are not available from official data and are not guessed."}

# ---------------- consented X tag queue (drained by a separate poster run by the operator) ----------------
import os, re, time, hashlib, json, random
ABUSE = re.compile(r"\b(thief|chor|corrupt|bastard|idiot|fuck\w*|madarchod|chutiy\w*|harami|kutta|shame on|resign)\b", re.I)
X_DAILY_CAP = lambda: int(os.environ.get("X_DAILY_CAP", "6"))
X_MIN_GAP_MIN = lambda: int(os.environ.get("X_MIN_GAP_MIN", "25"))
def _now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def known_handles():
    return {x.lower() for h in load_data("social_handles.json") + load_data("social_handles_extra.json") for x in h["x_handles"]}
def enqueue(svc, cid, text=None):
    """Only after the citizen ticked consent_x for this complaint. Text = facts + official-site handles; never abusive."""
    c = svc.db.one("SELECT * FROM complaints WHERE id=?", (cid,))
    if not c or not c["consent_x"]: return {"ok": False, "error": "no citizen consent for X tagging"}
    if not c["consent_submit"]: return {"ok": False, "error": "complaint not submitted with consent"}
    d = draft(svc, cid); text = (text or d["text"]).strip()
    if len(text) > 280: return {"ok": False, "error": "text over 280 chars"}
    if ABUSE.search(text): return {"ok": False, "error": "text must be factual and civil"}
    hs = re.findall(r"@(\w{1,15})", text); ok = known_handles()
    bad = [h for h in hs if h.lower() not in ok]
    if bad: return {"ok": False, "error": "handles not from official sources: " + ", ".join(bad)}
    if not hs: return {"ok": False, "error": "no official handle found for this complaint; use the Post on X draft instead"}
    h = hashlib.sha256(re.sub(r"\W+", "", text.lower()).encode()).hexdigest()
    if svc.db.one("SELECT id FROM x_queue WHERE complaint_id=? OR text_hash=?", (cid, h)): return {"ok": False, "error": "already queued"}
    svc.db.run("INSERT INTO x_queue(complaint_id,text,handles,text_hash,created_at) VALUES(?,?,?,?,?)", (cid, text, json.dumps(hs), h, _now()))
    return {"ok": True, "status": "queued", "text": text}
def next_pending(svc):
    """Poster asks for work. Returns one item only if daily cap and spacing allow (human-like gap with jitter)."""
    today = time.strftime("%Y-%m-%dT00:00:00")
    n = svc.db.one("SELECT COUNT(*) n FROM x_queue WHERE status IN ('posted','picked') AND COALESCE(posted_at,picked_at)>=?", (today,))["n"]
    if n >= X_DAILY_CAP(): return {"item": None, "reason": "daily cap reached"}
    last = svc.db.one("SELECT MAX(COALESCE(posted_at,picked_at)) t FROM x_queue WHERE status IN ('posted','picked')")["t"]
    if last:
        gap = (time.mktime(time.strptime(_now(), "%Y-%m-%dT%H:%M:%S")) - time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%S"))) / 60
        if gap < X_MIN_GAP_MIN() + random.randint(0, 10): return {"item": None, "reason": "spacing"}
    it = svc.db.one("SELECT id, text, handles, complaint_id FROM x_queue WHERE status='queued' ORDER BY id LIMIT 1")
    if not it: return {"item": None, "reason": "empty"}
    svc.db.run("UPDATE x_queue SET status='picked', picked_at=? WHERE id=?", (_now(), it["id"]))
    return {"item": dict(it), "rules": "Post exactly this text from the JANSEVA account. No edits, no replies, no extra tags. Then POST the tweet URL back."}
def mark(svc, qid, ok, url="", error=""):
    it = svc.db.one("SELECT id FROM x_queue WHERE id=? AND status='picked'", (qid,))
    if not it: return {"ok": False, "error": "item is not in picked state"}
    if ok:
        if not re.fullmatch(r"https://(x|twitter)\.com/\w{1,15}/status/\d{5,25}", url or ""): return {"ok": False, "error": "tweet URL must look like https://x.com/<account>/status/<id>"}
        svc.db.run("UPDATE x_queue SET status='posted', tweet_url=?, posted_at=? WHERE id=?", (url, _now(), qid))
    else: svc.db.run("UPDATE x_queue SET status='failed', error=? WHERE id=?", ((error or "")[:200], qid))
    return {"ok": True}
