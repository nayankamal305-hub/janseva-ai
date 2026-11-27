"""Problem-density map data. REAL complaint counts only, aggregated by state and district.
Each complaint's own coordinates are placed into the LGD state/district polygon (point-in-polygon on the simplified boundary
files in app/static/geo; sources and licence in docs/GEO_SOURCES.md). Complaints without usable coordinates are counted as 'unlocated',
never guessed. Counts only: no names, phones, addresses or exact points leave the server."""
import json, os
from . import public
_GEO = {}
_CACHE = {}

def _load(kind):
    if kind not in _GEO:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "geo", "india_%s.geojson" % kind)
        feats = []
        for f in json.load(open(p))["features"]:
            g = f["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            bb = [min(x for p in polys for x, y in p[0]), min(y for p in polys for x, y in p[0]), max(x for p in polys for x, y in p[0]), max(y for p in polys for x, y in p[0])]
            feats.append((f["properties"], bb, polys))
        _GEO[kind] = feats
    return _GEO[kind]

def _in_ring(x, y, ring):
    c = False; j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]; xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
        j = i
    return c

def locate(lat, lon, kind):
    for props, bb, polys in _load(kind):
        if bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]:
            for poly in polys:
                if _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, h) for h in poly[1:]): return props
    return None

def _place(lat, lon):
    k = (round(lat, 3), round(lon, 3))
    if k not in _CACHE:
        s = locate(lat, lon, "states"); d = locate(lat, lon, "districts") if s else None
        _CACHE[k] = (s["lgd"] if s else None, d["lgd"] if d else None)
    return _CACHE[k]

def density(db, f):
    w, a = public._where(f)
    rows = db.all("SELECT c.lat, c.lon FROM complaints c WHERE " + w, a)
    states, dists, unlocated = {}, {}, 0
    for r in rows:
        try:
            lat, lon = float(r["lat"]), float(r["lon"])
        except (TypeError, ValueError): unlocated += 1; continue
        s, d = _place(lat, lon)
        if s is None: unlocated += 1; continue
        states[str(s)] = states.get(str(s), 0) + 1
        if d is not None: dists[str(d)] = dists.get(str(d), 0) + 1
    total = len(rows)
    return {"total": total, "located": total - unlocated, "unlocated": unlocated, "states": states, "districts": dists,
            "basis": "Real complaint counts on this server (user-reported, includes sandbox test records). Placed by the complaint's own coordinates.",
            "empty": total == 0}
