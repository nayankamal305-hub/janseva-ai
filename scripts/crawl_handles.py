"""Find X (Twitter) handles that official sites link to from their own pages. Keeps handle + the page it was found on. Nothing guessed."""
import json, re, ssl, sys, time, urllib.request, concurrent.futures as cf
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
H = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent|share|home|i/|search|hashtag)([A-Za-z0-9_]{2,15})(?:[/?\"' ]|$)")
SKIP = {"nhai_official_x"}
def work(r):
    try:
        h = urllib.request.urlopen(urllib.request.Request(r["website"], headers={"User-Agent": "Mozilla/5.0"}), timeout=6, context=ctx).read(600000).decode("utf-8", "ignore")
    except Exception: return None
    hs = []
    for m in H.finditer(h):
        if m.group(1).lower() not in [x.lower() for x in hs]: hs.append(m.group(1))
    return {"title": r["title"], "state": r.get("state"), "website": r["website"], "x_handles": hs[:2], "found_on": r["website"], "last_verified": "2026-11-27"} if hs else None
rows = [r for r in json.load(open("data/igod_union.json")) if r["website"] and r["type"] in ("E002", "E003", "E053")] + [r for r in json.load(open("data/igod_state_ut.json")) if r["type"] == "SPORT" and r["website"]]
t0 = time.time(); out = []; ex = cf.ThreadPoolExecutor(32); fs = [ex.submit(work, r) for r in rows]
for f in fs:
    try:
        x = f.result(timeout=max(0.1, 75 - (time.time() - t0)))
        if x: out.append(x)
    except Exception: pass
ex.shutdown(wait=False, cancel_futures=True)
json.dump(out, open("data/social_handles.json", "w"), indent=1, ensure_ascii=False); print(len(rows), "pages;", len(out), "with an X handle")
for o in out[:12]: print(o["title"][:50], o["x_handles"])
