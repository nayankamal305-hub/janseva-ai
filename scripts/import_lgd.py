"""Import an LGD download (CSV) a person fetched from https://lgdirectory.gov.in/downloadDirectory.do (CAPTCHA is solved by the person, never by this app).
Usage: python3 scripts/import_lgd.py districts.csv > data/lgd_districts.json   (also works for states / sub-districts CSVs)
Header names are matched loosely; unknown columns are kept under 'extra'."""
import csv, json, re, sys
def key(h):
    h = re.sub(r"\(.*?\)", "", h).lower(); h = re.sub(r"[^a-z]+", "_", h).strip("_"); return h
rows = []
with open(sys.argv[1], encoding="utf-8-sig", newline="") as f:
    rd = csv.reader(f); hdr = None
    for r in rd:
        if hdr is None:
            if any("code" in c.lower() for c in r) and any("name" in c.lower() for c in r): hdr = [key(c) for c in r]
            continue
        if len(r) < len(hdr) or not any(r): continue
        d = dict(zip(hdr, [c.strip() for c in r]))
        rows.append({**d, "source": "https://lgdirectory.gov.in", "imported_from": sys.argv[1]})
json.dump(rows, sys.stdout, ensure_ascii=False, indent=0); print(len(rows), "rows", file=sys.stderr)
