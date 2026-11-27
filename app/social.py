"""Public tagging on X without paying for the X API: JANSEVA prepares the post and the CITIZEN publishes it from their own X account via an
intent link (free). Handles come only from links found on official sites (data/social_handles.json, each with the page it was found on).
MP/MLA/collector handles are not available from official machine-readable sources and are never guessed."""
import urllib.parse
from .service import load_data
KW = {"electricity": ["power"], "water": ["jal shakti", "drinking water"], "road": ["road transport"], "railway": ["railway"], "consumer": ["consumer"], "police": ["home affairs"],
      "garbage": ["housing and urban"], "drainage": ["housing and urban"], "toilet": ["housing and urban"], "pension": ["pension"]}
GENERIC = {"narendramodi", "jpnadda", "ndtvprofit"}
def draft(svc, cid):
    c = svc.db.one("SELECT * FROM complaints WHERE id=?", (cid,))
    if not c: return {"ok": False, "error": "not found"}
    hs = load_data("social_handles.json"); tags = []; src = []
    for h in hs:
        t = h["title"].lower()
        hit = any(k in t for k in KW.get(c["category"] or "", [])) or (c["state"] and c["state"].lower() in (h.get("state") or "").lower() and "portal" in t)
        if hit:
            for x in h["x_handles"]:
                if x.lower() not in GENERIC and x not in tags and len(tags) < 3: tags.append(x); src.append({"handle": x, "found_on": h["found_on"], "listed_for": h["title"], "last_verified": h["last_verified"]})
    loc = ", ".join(x for x in (c["city"], c["state"]) if x)
    body = "%s at %s. Unresolved. Tracking %s" % ((c["title"] or "Public issue")[:110], loc, c["code"])
    text = (body + " " + " ".join("@" + t for t in tags) + " #JANSEVA").strip()[:280]
    return {"ok": True, "text": text, "tags": tags, "tag_sources": src, "intent_url": "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(text),
            "note": "Review before posting. You post it from your own X account; JANSEVA does not post for you. Handles are linked on official sites and may belong to a related office. MP/MLA/collector handles are not available from official data and are not guessed."}
