"""Collect emails/phones that an official body PUBLISHES on its own website (home/contact page) for tagged utility bodies.
Only emails on the same registered domain family as the site (or gov.in/nic.in) are kept. Nothing is guessed. Re-runnable."""
import json, re, sys, urllib.request, ssl, concurrent.futures as cf
from urllib.parse import urlparse
CATS = {"electricity_discom", "water_board", "pwd_roads", "municipal"}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
EM = re.compile(r"[A-Za-z0-9._%+\-]+(?:\s?\[at\]\s?|\s?\(at\)\s?|@)[A-Za-z0-9\-]+(?:\s?\[dot\]\s?|\s?\(dot\)\s?|\.)[A-Za-z0-9.\-]*[A-Za-z]", re.I)
def norm(e): return re.sub(r"\s", "", re.sub(r"\[at\]|\(at\)", "@", re.sub(r"\[dot\]|\(dot\)", ".", e, flags=re.I), flags=re.I)).lower().strip(".")
def fetch(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JANSEVA-directory-check"})
        return urllib.request.urlopen(r, timeout=6, context=ctx).read(400000).decode("utf-8", "ignore")
    except Exception: return None
def ok_domain(email, site):
    ed = email.split("@")[-1]; sd = urlparse(site).netloc.lower().replace("www.", "")
    base = ".".join(sd.split(".")[-3:]) if sd.endswith((".gov.in", ".nic.in", ".co.in", ".org.in")) else ".".join(sd.split(".")[-2:])
    return ed.endswith(base) or ed.endswith(("gov.in", "nic.in"))
def work(r):
    found = {}
    for u in [x for x in (r.get("contact_page"), r.get("website")) if x]:
        h = fetch(u)
        if not h: continue
        for m in EM.findall(re.sub(r"<[^>]+>", " ", h)):
            e = norm(m)
            if re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e) and ok_domain(e, r["website"] or u) and not e.endswith((".png", ".jpg")): found.setdefault(e, u)
    return {**{k: r[k] for k in ("title", "state", "website", "categories_heuristic")}, "emails_published_on_official_page": [{"email": e, "found_on": u} for e, u in list(found.items())[:4]],
            "accepts_citizen_complaints": "unverified", "last_verified": "2026-11-27"}
if __name__ == "__main__":
    rows = [r for r in json.load(open("data/igod_state_ut.json")) if CATS & set(r["categories_heuristic"]) and r["website"] and r["type"] != "SPORT"]
    import time; t0 = time.time(); out = []
    ex = cf.ThreadPoolExecutor(32); fs = [ex.submit(work, r) for r in rows]
    for f in fs:
        try: out.append(f.result(timeout=max(0.1, 80 - (time.time() - t0))))
        except Exception: pass
    ex.shutdown(wait=False, cancel_futures=True)
    json.dump(out, open("data/utility_contacts.json", "w"), ensure_ascii=False, indent=0)
    print(len(out), "of", len(rows), "bodies;", sum(1 for o in out if o["emails_published_on_official_page"]), "with a published email", file=sys.stderr)
