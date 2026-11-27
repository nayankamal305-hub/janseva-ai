"""Problem analysis. ENGINE = rules-v1: TEXT ONLY keyword scoring. No vision model is wired in (needs a model key);
`analyze()` is the single place to swap in a vision-language model. Never invents facts: low confidence asks the citizen."""
from .router import KEYWORDS

EMERGENCY = ["fallen wire", "live wire", "exposed wire", "exposed electrical", "open manhole", "building collapse", "collapse", "severe flood", "flooding", "sparking", "तार टूट", "खुला मैनहोल"]
SEV5 = ["fallen wire", "live wire", "exposed wire", "open manhole", "collapse", "sparking", "तार टूट", "खुला मैनहोल"]
SEV4 = ["flood", "sewage", "bridge", "no water", "contaminated", "pothole on highway"]
DEPT = {"garbage": "Municipal sanitation", "drainage": "Municipal drainage / sewerage", "toilet": "Municipal sanitation", "road": "Road-owning authority (municipal / PWD / NHAI)",
        "water": "Water supply authority", "electricity": "Electricity distribution company", "railway": "Indian Railways", "consumer": "Consumer affairs",
        "pension": "Pension authority", "police": "Police", "general": "To be determined by citizen / verification officer"}

def analyze(title, description, photo_url=None):
    base = _rules(title, description, photo_url)
    v = _gemini(title, description, photo_url, base) if photo_url else None
    return v or base

def _rules(title, description, photo_url=None):
    t = " %s %s " % ((title or "").lower(), (description or "").lower())
    best, hits = "general", 0
    for cat, kws in KEYWORDS:
        n = sum(1 for k in kws if k in t)
        if n > hits: best, hits = cat, n
    conf = 0.9 if hits >= 2 else 0.7 if hits == 1 else 0.2
    emergency = any(k in t for k in EMERGENCY)
    sev = 5 if any(k in t for k in SEV5) else 4 if any(k in t for k in SEV4) else 3 if best in ("drainage", "road", "water", "electricity") else 2
    risk = "high" if sev >= 4 else "medium" if sev == 3 else "low"
    return {"engine": "rules-v1 (text only, no image model)", "category": best, "confidence": conf, "severity": sev, "safety_risk": risk,
            "emergency": emergency, "suggested_department": DEPT.get(best, DEPT["general"]),
            "notes": "Photo not analysed by a vision model." if photo_url else "No photo attached."}


import os, json, base64, urllib.request
CATS = [c for c, _ in KEYWORDS] + ["general"]

def _gemini(title, description, photo_url, base):
    """Optional vision classification. Key is read server-side from GEMINI_API_KEY only. Any failure -> None (rules fallback).
    Model output is advisory: category must be in our list, confidence capped, and the citizen always confirms."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not photo_url.startswith("data:image/"): return None
    try:
        head, b64 = photo_url.split(",", 1); mime = head[5:].split(";")[0]
        if len(b64) > 6_000_000: return None
        prompt = ("You classify a citizen-reported civic problem photo in India. Reply with JSON only: "
                  '{"category": one of %s, "severity": 1-5, "emergency": true/false, "confidence": 0-1, "note": "one short sentence of what is visible"}. '
                  "Do not identify people or read number plates. Citizen text: %s %s") % (CATS, title or "", description or "")
        body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": mime, "data": b64}}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}}
        model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
        o = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
        cat = o.get("category"); 
        if cat not in CATS: return None
        sev = max(1, min(5, int(o.get("severity", base["severity"])))); conf = min(0.9, max(0.0, float(o.get("confidence", 0.5))))
        emer = bool(o.get("emergency")) or base["emergency"]
        out = dict(base); out.update(engine="gemini-vision (%s) + rules" % model, category=cat, severity=max(sev, base["severity"] if base["emergency"] else sev), confidence=conf,
                  safety_risk="high" if sev >= 4 else "medium" if sev == 3 else "low", emergency=emer,
                  suggested_department=DEPT.get(cat, DEPT["general"]), notes="Vision model suggestion: %s Citizen must confirm." % str(o.get("note", ""))[:200])
        return out
    except Exception:
        return None
