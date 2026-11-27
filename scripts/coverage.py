"""Per state/UT coverage: what data exists in the app and what is missing. Writes data/coverage.json and docs/COVERAGE.md"""
import json, collections, os
D = lambda f: json.load(open("data/" + f))
STATES = sorted({r["state"] for r in D("igod_state_ut.json") if r.get("state")})
cs = D("crawl_status.json"); sites = D("state_handle_sites.json"); mps = D("representatives_parliament.json"); nod = D("authorities_state_nodal.json"); dist = D("igod_districts.json")
cov = []
for s in STATES:
    c = [x for x in cs if x["state"] == s]; hs = [x for x in sites if x["state"] == s]
    reach = sum(x["reached"] for x in c)
    dsites = [x for x in hs if x["type"] == "E042"]; pol = [x for x in hs if "police" in x["handle"].lower()]
    nd = [n for n in nod if s.lower().split(" and ")[0] in n["name"].lower() or n["name"].lower() in s.lower()]
    cov.append({"state": s, "official_sites_listed": len(c), "sites_reached": reach, "reach_pct": round(100 * reach / len(c)) if c else 0, "districts_in_directory": sum(1 for d in dist if d["state"] == s),
                "handles_total": len({x["handle"].lower() for x in hs}), "district_admin_handles": len(dsites), "police_handles": len(pol), "mps": sum(1 for m in mps if m["state"] == s), "state_nodal_pg_officer": bool(nd)})
json.dump(cov, open("data/coverage.json", "w"), indent=1)
L = ["# Coverage per state/UT (crawl of 2026-11-27)", "", "reach% = official gov.in/nic.in sites our server could open (others geo-block or timed out, so handles there are unknown, not absent).", "",
     "| State/UT | sites | reach% | districts | handles | DM handles | police | MPs | PG officer |", "|---|---|---|---|---|---|---|---|---|"]
for r in cov: L.append("| %s | %d | %d | %d | %d | %d | %d | %d | %s |" % (r["state"], r["official_sites_listed"], r["reach_pct"], r["districts_in_directory"], r["handles_total"], r["district_admin_handles"], r["police_handles"], r["mps"], "yes" if r["state_nodal_pg_officer"] else "NO"))
low = [r["state"] for r in cov if r["reach_pct"] < 40]
L += ["", "Low reach (<40%): " + ", ".join(low), "", "Not available from any official machine-readable source: MLA contacts/handles, collector emails, ward/councillor data, pincode-to-constituency map.", "Next: slow Internet Archive snapshots of unreachable official pages (scripts/crawl_archive.py, rate limited), LGD CSV (CAPTCHA, needs the owner)."]
os.makedirs("docs", exist_ok=True); open("docs/COVERAGE.md", "w").write("\n".join(L) + "\n"); print("\n".join(L[:50]))
