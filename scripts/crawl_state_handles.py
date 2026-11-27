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
def work(r):
    try:
        h = urllib.request.urlopen(urllib.request.Request(r["website"], headers={"User-Agent": "Mozilla/5.0 JansevaBot (public data research)"}), timeout=8, context=ctx).read(1500000).decode("utf-8", "ignore")
    except Exception: return None
    hs = []
    for m in H.finditer(h):
        if m.group(1).lower() not in [x.lower() for x in hs]: hs.append(m.group(1))
    return {"title": r["title"], "state": r.get("state"), "type": r.get("type"), "website": r["website"], "x_handles": hs[:3], "found_on": r["website"], "last_verified": time.strftime("%Y-%m-%d")} if hs else None
start, n = int(sys.argv[1]), int(sys.argv[2]); out = []; t0 = time.time()
with cf.ThreadPoolExecutor(150) as ex:
    for x in ex.map(work, rows[start:start + n]):
        if x: out.append(x)
json.dump(out, open("/tmp/sh_%d.json" % start, "w"), ensure_ascii=False); print("chunk", start, len(out), int(time.time() - t0), "s", flush=True)
