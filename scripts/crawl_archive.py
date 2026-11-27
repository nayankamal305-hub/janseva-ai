"""Second pass for official sites our server cannot reach (geo/WAF blocks): read the Internet Archive snapshot of the SAME official page and keep handles linked there.
Evidence stored: official URL + archive snapshot URL + snapshot date. Marked evidence='archive_snapshot'. Nothing guessed."""
import json, glob, re, sys, time, urllib.request, concurrent.futures as cf
H = re.compile(r"https?://(?:www\.|mobile\.)?(?:twitter|x)\.com/(?!intent|share|home|i/|search|hashtag|widgets)([A-Za-z0-9_]{2,15})(?=[/?\"'<>\s#&]|$)")
BAD = {"login", "share", "intent", "home", "i", "hashtag", "search", "explore", "widgets", "privacy", "tos", "settings", "about", "status", "en", "hi", "tweet"}
new = []
for f in sorted(glob.glob("/tmp/sh2_*.json")): new += json.load(open(f))
STATES = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
todo = [o for o in new if not o["reached"] and (not STATES or o["state"] in STATES)]
start, n, budget = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
def work(o):
    try:
        a = json.load(urllib.request.urlopen("https://archive.org/wayback/available?url=" + o["website"], timeout=20)).get("archived_snapshots", {}).get("closest")
        if not a: return dict(o, archive="nosnap")
        u = a["url"].replace("http://", "https://")
        h = None
        for k in range(3):
            try: h = urllib.request.urlopen(u, timeout=25).read(1500000).decode("utf-8", "ignore"); break
            except Exception: time.sleep(2 + 3 * k)
        if h is None: return dict(o, archive="err")
        hs = []
        for m in H.finditer(re.sub(r"https?://web\.archive\.org/web/\d+\w*/", "", h)):
            if m.group(1).lower() not in BAD and m.group(1).lower() not in [x.lower() for x in hs]: hs.append(m.group(1))
        return dict(o, archive="ok", snapshot=u, snapshot_date=a["timestamp"][:8], x_handles=hs[:3])
    except Exception as e: return dict(o, archive="err")
ex = cf.ThreadPoolExecutor(5); fs = [ex.submit(work, o) for o in todo[start:start + n]]; out = []
t0 = time.time()
for f in fs:
    try: out.append(f.result(timeout=max(0.1, budget - (time.time() - t0))))
    except Exception: pass
json.dump(out, open("/tmp/arch_%s_%d.json" % ((STATES and "x" or "a"), start), "w"), ensure_ascii=False)
print("todo", len(todo), "chunk", start, "done", len(out), "snap_ok", sum(1 for o in out if o.get("archive") == "ok"), "with_handles", sum(1 for o in out if o.get("x_handles")), flush=True)
import os; os._exit(0)
