"""Complaint router. Rule-based (keywords EN/HI). An AI vision/LLM classifier can replace classify() later;
the validation steps after it (jurisdiction, asset owner, platform acceptance) stay deterministic."""
import json, os
from .db import ROOT
from .connectors.swachhata import CATEGORY_MAP

KEYWORDS = [
 ("railway", ["train", "railway", "rail ", "station", "pnr", "coach", "रेल", "ट्रेन"]),
 ("consumer", ["refund", "overcharg", "defective", "consumer", "warranty", "fake product", "मोबाइल कंपनी"]),
 ("road", ["pothole", "highway", "bridge", "road damage", "broken road", "गड्ढा", "सड़क", "sadak", "gaddha", "gadda", "khadda", "गड्ढे", "रोड"]),
 ("drainage", ["drain", "sewage", "sewer", "manhole", "नाली", "सीवर", "naali", "nali", "nala ", "gutter", "नाला", "overflow"]),
 ("garbage", ["garbage", "trash", "waste", "dump", "litter", "कचरा", "गंदगी", "kachra", "kooda", "kuda ", "gandagi", "कूड़ा", "कुड़ा", "badbu", "बदबू"]),
 ("toilet", ["toilet", "urinal", "शौचालय", "shauchalay", "sulabh", "bathroom"]),
 ("electricity", ["electric", "power cut", "transformer", "streetlight", "street light", "बिजली", "bijli", "batti", "बत्ती", "light nahi"]),
 ("water", ["water supply", "no water", "pipeline leak", "पानी", "paani", "pani nahi", "tanker", "pipe leak", "नल"]),
 ("pension", ["pension", "epfo", "पेंशन"]),
 ("police", ["police", "fir ", "पुलिस", "thana", "chori", "चोरी", "थाना"]),
]

def classify(text):
    t = (" " + (text or "").lower() + " ")
    for cat, kws in KEYWORDS:
        if any(k in t for k in kws): return cat
    return "general"

def infer_asset_owner(c):
    if c.get("asset_owner"): return c["asset_owner"]
    t = (c.get("description") or "").lower()
    if c.get("category") == "road":
        if " nh" in t or "national highway" in t or "nh-" in t or "nh " in t: return "nhai"
        return None   # unknown: router will ask, never guess
    return "municipal"

def lookup_ulb(city):
    data = json.load(open(os.path.join(ROOT, "data", "ulbs.json")))
    for u in data["ulbs"]:
        if u["city"] == (city or "").lower(): return u
    return None

def plan(complaint, platforms, connectors, user):
    """Return {'targets': [...], 'rejected': [...], 'needs': [...]} with a reason for every decision."""
    c = dict(complaint)
    needs = []
    ulb = lookup_ulb(c.get("city"))
    if ulb: c["ulb_id"] = ulb["ulb_id"]; c["ulb_swachhata"] = ulb["swachhata_onboarded"]
    if c["category"] == "road" and not c.get("asset_owner"):
        owner = infer_asset_owner(c)
        if owner: c["asset_owner"] = owner
        else: needs.append("Who owns this road (municipal / state PWD / NHAI)? Needed before routing.")
    targets, rejected = [], []
    for p in platforms:
        conn = connectors[p["id"]]
        if p.get("fallback_only"): rejected.append((p["id"], "fallback only, no grievance API")); continue
        cats = p.get("categories", [])
        cat = c["category"]
        if cat not in cats:
            rejected.append((p["id"], "category %s not accepted" % cat)); continue
        ok, why = conn.check_jurisdiction(c)
        if not ok: rejected.append((p["id"], "jurisdiction: " + why)); continue
        ok, why = conn.check_eligibility(c, user)
        if not ok: rejected.append((p["id"], "eligibility: " + why)); continue
        errs = conn.validate(c)
        targets.append({"platform_id": p["id"], "level": p["level"], "reason": "category and jurisdiction match", "validation_errors": errs,
                        "notify_only": bool(p.get("notify_only"))})
    # avoid indiscriminate fan-out: central generic portal (CPGRAMS) only when no direct local official channel exists
    FALLBACK = ("cpgrams", "state_grievance", "mh_cm_grievance", "district_collector")
    local_official = [t for t in targets if t["platform_id"] not in FALLBACK and not t["notify_only"]]
    if local_official:
        for t in list(targets):
            if t["platform_id"] in FALLBACK:
                targets.remove(t); rejected.append((t["platform_id"], "a direct, more specific official channel exists; avoiding duplicate government complaint"))
    # Swachhata and municipal guided channel are different owners' systems: only add municipal guided when swachhata is not usable
    if any(t["platform_id"] == "swachhata" and not t["validation_errors"] for t in targets):
        pass
    from . import localbody
    lb = localbody.find(c.get("city"), c.get("state")) if c.get("category") in ("garbage", "drainage", "toilet", "road", "water", "streetlight", "electricity", "general") else None
    if lb and lb.get("bodies"):
        lb = dict(lb); lb["bodies"] = [dict(b, contact=localbody.contact(b)) for b in lb["bodies"]]
    return {"targets": targets, "rejected": rejected, "needs": needs, "local_body": lb, "context": {"ulb": ulb, "asset_owner": c.get("asset_owner")}}
