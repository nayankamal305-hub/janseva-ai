"""Concerned local body (municipal corporation / municipality / nagar panchayat / cantonment) for a complaint location.
Source: MoHUA PMAY-Urban list of ULBs (data/ulbs_official.json). The list has NO contact details, so this module names the body and
its type with the source; it never invents an email or website. Rural (gram panchayat) areas are not in the list."""
import re
from .service import load_data
_PRI = {"Municipal Corporation": 0, "Municipality / Municipal Council": 1, "Nagar Panchayat / Town Panchayat": 2, "Cantonment Board": 3}
_IDX = {}
def _n(s): return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", re.sub(r"\((m|u|s|ct|cb|n|ct\)|[a-z]{1,3})\)", "", (s or "").lower()))).strip()
def _st(s): return re.sub(r"[^a-z]", "", (s or "").lower().replace("&", "and").replace("keralam", "kerala"))
def _build():
    for r in load_data("ulbs_official.json"):
        _IDX.setdefault((_st(r["state"]), _n(r["name"])), []).append(r)
def find(city, state):
    """Return {'status': 'matched'|'ambiguous'|'not_found', 'bodies': [...]}. Never guesses between several bodies."""
    if not _IDX: _build()
    k = (_st(state), _n(city))
    hits = _IDX.get(k, []) if k[1] else []
    if not hits and k[1]:
        hits = [r for (s, n), rs in _IDX.items() if s == k[0] and (n.startswith(k[1] + " ") or n.endswith(" " + k[1])) for r in rs] if len(k[1]) >= 4 else []
    if not hits: return {"status": "not_found", "bodies": [], "note": "City not in the official ULB list for this state. It may be a rural area (gram panchayat) or the OSM city name differs. Rural bodies are not loaded yet."}
    if hits and all(h["ulb_type"] == "Cantonment Board" for h in hits) and len(k[1]) >= 4:
        hits = hits + [r for (s_, n), rs in _IDX.items() if s_ == k[0] and k[1] in n for r in rs if r not in hits]
    hits = sorted(hits, key=lambda r: _PRI.get(r["ulb_type"], 9))
    top = [r for r in hits if _PRI.get(r["ulb_type"], 9) == _PRI.get(hits[0]["ulb_type"], 9) and not r["name"].lower().endswith("(cb)")]
    if len(top) == 1: return {"status": "matched", "bodies": [top[0]] + [h for h in hits if h is not top[0]][:2], "note": ""}
    return {"status": "ambiguous", "bodies": hits[:6], "note": "More than one body matches this name. Citizen must confirm."}
