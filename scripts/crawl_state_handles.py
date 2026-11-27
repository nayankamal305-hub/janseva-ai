"""Crawl official state/UT/district government sites (gov.in / nic.in, from the IGOD directory) and keep X handles the site itself links to.
Proof = the link on the department's own official website (page URL stored). Nothing guessed. Output: data/state_handles.json"""
import json, re, ssl, sys, time, urllib.request, concurrent.futures as cf, collections
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
H = re.compile(r"https?://(?:www\.|mobile\.)?(?:twitter|x)\.com/(?!intent|share|home|i/|search|hashtag|widgets)([A-Za-z0-9_]{2,15})(?=[/?\"'<>\s#&]|$)")
rows = {}
for f in ("igod_state_ut.json", "igod_districts.json"):
    for r in json.load(open("data/" + f)):
        w = r.get("website") or ""
        if re.search(r"(gov\.in|nic\.in)(/|$)", w) and w not in rows: rows[w] = r
rows = list(rows.values()); print(len(rows), "sites", flush=True)
def fetch(u, to):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36", "Accept": "text/html"}), timeout=to, context=ctx).read(1500000).decode("utf-8", "ignore")
def work(r):
    h = None
    for u in (r["website"], re.sub(r"^https://", "http://", r["website"])):
        try: h = fetch(u, 12); break
        except Exception: continue
    if h is None: return {"title": r["title"], "state": r.get("state"), "type": r.get("type"), "website": r["website"], "reached": False, "x_handles": []}
    hs = []
    for m in H.finditer(h):
        if m.group(1).lower() not in [x.lower() for x in hs]: hs.append(m.group(1))
    return {"title": r["title"], "state": r.get("state"), "type": r.get("type"), "website": r["website"], "reached": True, "x_handles": hs[:3], "found_on": r["website"], "last_verified": time.strftime("%Y-%m-%d")}
start, n = int(sys.argv[1]), int(sys.argv[2]); budget = int(sys.argv[3]) if len(sys.argv) > 3 else 85; t0 = time.time()
chunk = rows[start:start + n]; res = {}
ex = cf.ThreadPoolExecutor(300); fs = {ex.submit(work, r): r["website"] for r in chunk}
try:
    for f in cf.as_completed(fs, timeout=budget):
        try: res[fs[f]] = f.result()
        except Exception: pass
except cf.TimeoutError: pass
ex.shutdown(wait=False, cancel_futures=True)
out = [res.get(r["website"]) or {"title": r["title"], "state": r.get("state"), "type": r.get("type"), "website": r["website"], "reached": False, "x_handles": [], "note": "timeout"} for r in chunk]
json.dump(out, open("/tmp/sh2_%d.json" % start, "w"), ensure_ascii=False); print("chunk", start, "reached", sum(1 for o in out if o["reached"]), "handles", sum(1 for o in out if o["x_handles"]), int(time.time() - t0), "s", flush=True)
import os; os._exit(0)
