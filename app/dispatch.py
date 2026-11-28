"""Escalation-ladder email dispatch. Targets come ONLY from official-source data files (each row keeps source URL + date).
Nothing here claims an official registration: the best status is 'emailed'. Requires the citizen's explicit email consent per complaint."""
import mimetypes, os
from datetime import datetime, timedelta, timezone
from . import mailer
from .db import now
from .service import load_data

MINISTRY = {"electricity": "Power", "water": "Drinking Water and Sanitation", "road": "Road Transport and Highways", "railway": "Railways, ( Railway Board)", "consumer": "Consumer Affairs",
            "pension": "Pensions and Pensioners Welfare", "police": "Home Affairs", "garbage": "Urban Development", "drainage": "Urban Development", "toilet": "Urban Development"}
UTIL_CAT = {"garbage": "municipal", "drainage": "municipal", "toilet": "municipal", "road": "pwd_roads", "water": "water_board", "electricity": "electricity_discom", "police": "police"}
BLOCK_LOCAL = {"cm", "pm", "pmo", "governor", "president", "minister", "chairman", "chairperson", "mp", "mla", "vc"}
# default ladder timing (days after submission): L1+L2 now, reminder + L3 at day 7, reminder + L4 at day 15
DAYS = {1: 0, 2: 0, 3: 7, 4: 15}
MAX_INITIAL = 3; PER_USER_DAY = 10
TERMINAL = ("citizen_verified_resolved", "resolved", "rejected", "authority_marked_resolved")

def _st(x): return (x or "").lower().replace("&", "and").replace("union territory of", "").replace("national capital territory of", "").replace("nct of", "").replace("keralam", "kerala").replace("chattisgarh", "chhattisgarh").strip()
def _match_state(a, b):
    a, b = _st(a), _st(b)
    return bool(a and b) and (a in b or b in a or a.replace("chattisgarh", "chhattisgarh") in b.replace("chattisgarh", "chhattisgarh"))
def _okmail(e): return bool(e) and "@" in e and e.split("@")[0].lower() not in BLOCK_LOCAL

def ladder(c):
    """Returns list of targets [{level,kind,name,email,source_url,source_date,tier}] for complaint dict c."""
    out = []; cat = c.get("category") or "general"; state = c.get("state") or ""
    if c.get("company"):
        for co in load_data("companies.json"):
            if co["company"].lower() == c["company"].lower():
                for e in co["grievance_emails"][:1]: out.append({"level": 1, "kind": "company_grievance_officer", "name": co["company"] + " grievance contact", "email": e["email"], "source_url": e["found_on"], "source_date": co["last_verified"], "tier": "company page"})
        return out
    uc = UTIL_CAT.get(cat)
    if uc:
        n = 0
        if uc == "municipal" or (cat == "road" and c.get("asset_owner") == "municipal"):
            from . import localbody
            lbr = localbody.find(c.get("city"), state)
            if lbr["status"] == "matched":
                ct = localbody.contact(lbr["bodies"][0])
                for e in (ct or {}).get("emails", [])[:1]:
                    if _okmail(e["email"]): out.append({"level": 1, "kind": "local_body_published_email", "name": lbr["bodies"][0]["name"] + " " + lbr["bodies"][0]["ulb_type"], "email": e["email"], "source_url": e["found_on"], "source_date": ct["last_verified"], "tier": "local body's own official page"}); n += 1
        for r in load_data("utility_contacts.json"):
            if uc in r["categories_heuristic"] and _match_state(r["state"], state):
                for e in r["emails_published_on_official_page"]:
                    if _okmail(e["email"]) and n < 2: out.append({"level": 1, "kind": "body_published_email", "name": r["title"], "email": e["email"], "source_url": e["found_on"], "source_date": r["last_verified"], "tier": "body's own official page"}); n += 1; break
    for r in load_data("authorities_state_nodal.json"):
        if _match_state(r["name"], state) and _okmail(r["email"]):
            out.append({"level": 2, "kind": "state_nodal_pg_officer", "name": "Nodal grievance officer, " + r["name"], "email": r["email"], "source_url": r["source_url"], "source_date": r["last_verified"], "tier": "pgportal.gov.in"}); break
    m = MINISTRY.get(cat)
    if m:
        for r in load_data("authorities_central_nodal.json"):
            if r["name"] == m and _okmail(r["email"]):
                out.append({"level": 3, "kind": "central_nodal_pg_officer", "name": "Nodal grievance officer, " + r["name"], "email": r["email"], "source_url": r["source_url"], "source_date": r["last_verified"], "tier": "pgportal.gov.in"}); break
    if c.get("constituency") and c.get("notify_representative"):
        for r in load_data("representatives_parliament.json"):
            if r["house"] == "Lok Sabha" and (r.get("constituency") or "").lower() == c["constituency"].lower() and _match_state(r["state"], state) and _okmail(r["official_email"]):
                out.append({"level": 4, "kind": "mp_lok_sabha", "name": "MP, " + r["constituency"], "email": r["official_email"], "source_url": r["source_url"], "source_date": r["last_verified"], "tier": "sansad.in"}); break
    return out

def _sent_today(db, user_id=None):
    day = now()[:10]
    if user_id: return db.one("SELECT COUNT(*) AS n FROM dispatches d JOIN complaints c ON c.id=d.complaint_id WHERE d.status='sent' AND d.sent_at>=? AND c.user_id=?", (day, user_id))["n"]
    return db.one("SELECT COUNT(*) AS n FROM dispatches WHERE status='sent' AND sent_at>=?", (day,))["n"]

def plan(svc, cid):
    """Create dispatch rows (idempotent). Returns the targets without sending."""
    c = svc.db.one("SELECT * FROM complaints WHERE id=?", (cid,))
    if not c or not c["consent_submit"] or not c["consent_email"]: return {"ok": False, "error": "citizen consent to email authorities is required"}
    t0 = datetime.now(timezone.utc)
    for t in ladder(dict(c)):
        due = (t0 + timedelta(days=DAYS[t["level"]])).isoformat()
        svc.db.run("INSERT OR IGNORE INTO dispatches(complaint_id,level,kind,target_name,target_email,source_url,source_date,tier,status,due_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (cid, t["level"], t["kind"], t["name"], t["email"], t["source_url"], t["source_date"], t["tier"], "scheduled", due))
    return {"ok": True, "targets": svc.db.all("SELECT level,kind,target_name,target_email,source_url,source_date,tier,status,due_at FROM dispatches WHERE complaint_id=? ORDER BY level", (cid,))}

def _attachments(svc, c):
    out = []
    for key in ("photo_url", "after_photo_url"):
        u = c.get(key) or ""
        if u.startswith("/uploads/"):
            try:
                from . import storage
                got = storage.from_env(os.environ, os.environ.get("JANSEVA_UPLOADS", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"))).get(os.path.basename(u))
                if got and len(got[0]) <= 4_000_000: out.append((os.path.basename(u), got[0], got[1]))
            except Exception: pass
        break
    return out

def _body(c, user, d, reminder):
    from .connectors.base import complaint_text
    name = user.get("name", "") if c["consent_share_personal"] and not c["anonymous"] else ""
    head = ("REMINDER: this grievance is still unresolved. " if reminder else "") + "This public grievance is forwarded by Seva Setu India on behalf of a citizen who consented to it being sent to you.\n\n"
    base = os.environ.get("PUBLIC_BASE_URL", "")
    tail = "\nTracking ID: %s (please keep it in your reply)\nGPS: %s, %s\nPhoto attached where available.%s\nContact source for this address: %s (checked %s)\nIf this reached you in error, please reply and we will not write again.\n" % (
        c["code"], c["lat"], c["lon"], ("\nLink: %s/#track" % base) if base else "", d["source_url"], d["source_date"])
    return head + complaint_text(c, name) + tail

def server_email_on(): return os.environ.get("JANSEVA_SERVER_EMAIL") == "1"

def send_due(svc, cid=None, now_iso=None):
    """Send every scheduled dispatch that is due. Unresolved complaints only. Honors caps. Never raises."""
    if not server_email_on(): return {"sent": 0, "skipped": ["server-sent complaint email is off: the citizen sends from their own email (see /filing)"]}
    now_iso = now_iso or datetime.now(timezone.utc).isoformat(); cap = int(os.environ.get("MAIL_DAILY_CAP", "250")); sent = 0; skipped = []
    q = "SELECT d.*, c.user_id FROM dispatches d JOIN complaints c ON c.id=d.complaint_id WHERE d.status='scheduled' AND d.due_at<=?" + (" AND d.complaint_id=?" if cid else "") + " ORDER BY d.level"
    for d in svc.db.all(q, (now_iso, cid) if cid else (now_iso,)):
        c = svc.db.one("SELECT * FROM complaints WHERE id=?", (d["complaint_id"],)); u = svc.db.one("SELECT * FROM users WHERE id=?", (c["user_id"],)) or {}
        if c["status"] in TERMINAL or not c["consent_email"]: svc.db.run("UPDATE dispatches SET status='cancelled' WHERE id=?", (d["id"],)); continue
        if not mailer.configured(): skipped.append("email not configured"); break
        if _sent_today(svc.db) >= cap: skipped.append("daily cap"); break
        if _sent_today(svc.db, c["user_id"]) >= PER_USER_DAY: skipped.append("per-user cap"); continue
        if d["level"] <= 2 and svc.db.one("SELECT COUNT(*) AS n FROM dispatches WHERE complaint_id=? AND status='sent' AND level<=2", (c["id"],))["n"] >= MAX_INITIAL: continue
        reminder = d["kind"] == "reminder"
        user_mail = u.get("phone") if "@" in (u.get("phone") or "") else None
        reply = user_mail if (c["reply_to_user"] and user_mail) else None
        if not reply and mailer.configured():
            fa = mailer.from_address().split("<")[-1].strip(" >"); lo, _, dom = fa.partition("@"); reply = "%s+%s@%s" % (lo, c["code"], dom)
        who = (u.get("name") or "A citizen") if c["consent_share_personal"] and not c["anonymous"] else "A citizen"
        r = mailer.send(d["target_email"], ("[%s] %sPublic grievance: %s" % (c["code"], "Reminder: " if reminder else "", c["title"])), _body(dict(c), u, d, reminder), reply, os.environ, _attachments(svc, dict(c)), "%s via Seva Setu India" % who)
        svc.db.run("UPDATE dispatches SET status=?, sent_at=?, error=? WHERE id=?", ("sent" if r["sent"] else "failed", now() if r["sent"] else None, None if r["sent"] else r.get("reason"), d["id"]))
        try: svc.db.timeline(c["id"], "jansevaai", "email_" + ("sent" if r["sent"] else "failed"), ("Emailed %s (%s, level %s). Delivery is not a registration." % (d["target_name"], d["target_email"], d["level"])) if r["sent"] else ("Email to %s could not be sent." % d["target_name"]))
        except Exception: pass
        svc.db.timeline(c["id"], "jansevaai", "email_sent" if r["sent"] else "email_failed", ("Emailed %s (level %d) at %s. Source: %s, checked %s. Delivery is not registration; an official reply is needed." % (d["target_name"], d["level"], d["target_email"], d["source_url"], d["source_date"])) if r["sent"] else "Email to %s failed: %s" % (d["target_name"], r.get("reason")))
        sent += 1 if r["sent"] else 0
    return {"sent": sent, "skipped": skipped}

def send_reminders(svc, days=7):
    """Reminder to level-1/2 targets already emailed `days` ago on still-unresolved complaints (once)."""
    cut = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(); n = 0
    for d in svc.db.all("SELECT d.*, c.status AS cs FROM dispatches d JOIN complaints c ON c.id=d.complaint_id WHERE d.status='sent' AND d.level<=2 AND d.sent_at<=?", (cut,)):
        if d["cs"] in TERMINAL or svc.db.one("SELECT 1 AS x FROM dispatches WHERE complaint_id=? AND target_email=? AND kind=?", (d["complaint_id"], d["target_email"], "reminder")): continue
        svc.db.run("INSERT OR IGNORE INTO dispatches(complaint_id,level,kind,target_name,target_email,source_url,source_date,tier,status,due_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (d["complaint_id"], d["level"], "reminder", d["target_name"], d["target_email"], d["source_url"], d["source_date"], d["tier"], "scheduled", now_utc())); n += 1
    return n
def now_utc(): return datetime.now(timezone.utc).isoformat()

def tick(svc):
    r = {"reminders_queued": send_reminders(svc)}; r.update(send_due(svc)); return r
