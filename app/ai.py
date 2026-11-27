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
