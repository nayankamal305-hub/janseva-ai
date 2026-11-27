"""Citizen-side filing pack: an official-style complaint letter, compose links that open in the CITIZEN'S OWN mailbox, and guided handoffs to the
official portals. Nothing here is auto-submitted to any government site and nothing is sent from JANSEVA's address.
Honest limits: a server cannot send as someone's own Gmail/Yahoo address (SPF/DKIM), so the citizen presses Send in their own mail app.
CPGRAMS, Swachhata and Meri Panchayat have no public submit API and need the citizen's own login/OTP, so the citizen completes that step.
Registration numbers entered by the citizen are stored as citizen-entered, not verified by JANSEVA."""
import html, json, os, re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from .db import now
from .service import load_data

IST = timezone(timedelta(hours=5, minutes=30))
CAT_LABEL = {"garbage": "Garbage / solid waste", "drainage": "Drainage / sewage", "toilet": "Public toilet", "road": "Road / potholes", "water": "Water supply", "electricity": "Electricity", "streetlight": "Street light",
             "sanitation": "Sanitation", "police": "Police", "encroachment": "Encroachment", "health": "Health", "education": "Education", "general": "General public grievance"}
SWACHHATA_CAT = {"garbage": "Garbage dump", "drainage": "Overflow of sewerage or storm water / Open manholes or drains", "toilet": "Public toilet(s) cleaning / blockage", "sanitation": "Sweeping not done / Dirty spot"}
MUNICIPAL = {"garbage", "drainage", "toilet", "sanitation", "road", "streetlight", "water", "encroachment"}

def _date():
    return datetime.now(IST).strftime("%d %B %Y")

def identity(c, u):
    """Only the citizen's own real details, and only when they agreed to share them."""
    share = bool(c.get("consent_share_personal")) and not c.get("anonymous")
    ident = (u or {}).get("phone") or ""
    return {"share": share, "name": (u or {}).get("name") or "" if share else "",
            "email": ident if share and "@" in ident else "", "mobile": ident if share and "@" not in ident and not ident.startswith("deleted-") else ""}

def location_line(c):
    return ", ".join(x for x in [c.get("address"), c.get("ward"), c.get("city"), c.get("district"), c.get("state"), c.get("pincode")] if x)

def maps_link(c):
    return "https://www.google.com/maps?q=%s,%s" % (c.get("lat"), c.get("lon")) if c.get("lat") is not None else ""

def photo_link(c, base=""):
    p = c.get("photo_url") or ""
    return (base.rstrip("/") + p) if p.startswith("/") and base else p

def subject(c):
    return ("Complaint regarding %s at %s" % ((CAT_LABEL.get(c.get("category")) or c.get("category") or "public issue").lower(), c.get("city") or c.get("state") or "my area")).strip()

def letter_text(c, u, target=None, base="", short=False):
    i = identity(c, u); to = (target or {}).get("target_name") or "The Concerned Authority"
    lines = ["To,", "The %s" % to, "", "Date: %s" % _date(), "", "Subject: %s" % subject(c), "", "Respected Sir/Madam,", "",
             "I am writing to bring the following public issue to your notice and request action.", "",
             "Issue: %s" % (c.get("title") or CAT_LABEL.get(c.get("category")) or "Public issue"), "Details: %s" % (c.get("description") or "").strip(),
             "Location: %s" % (location_line(c) or "as per GPS"), "GPS: %s, %s (%s)" % (c.get("lat"), c.get("lon"), maps_link(c))]
    if c.get("severity"): lines.append("Severity (as assessed by the reporting app, indicative only): %s" % c["severity"])
    pl = photo_link(c, base)
    if pl: lines.append("Photo evidence: %s" % pl)
    lines += ["", "I request you to inspect the location, take the necessary action and inform me of the action taken. I understand the usual time limit for such grievances and will follow up if it is not resolved.", "",
              "I declare that the facts stated above are true to the best of my knowledge.", "", "Yours faithfully,"]
    if i["share"]:
        lines += [i["name"] or "(name)"] + (["Mobile: %s" % i["mobile"]] if i["mobile"] else []) + (["Email: %s" % i["email"]] if i["email"] else []) + (["Address: %s" % location_line(c)] if location_line(c) else [])
    else:
        lines += ["(Name and contact withheld by the citizen on this copy)"]
    lines += ["", "Reference: %s (JANSEVA AI tracking ID; please quote it in your reply)" % c.get("code")]
    t = "\n".join(lines)
    return t if not short else t.replace("\n\n\n", "\n\n")

def letter_html(c, u, target=None, base=""):
    t = letter_text(c, u, target, base)
    body = "".join("<p>%s</p>" % html.escape(p).replace("\n", "<br>") for p in t.split("\n\n"))
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Complaint %s</title>"
            "<style>body{font:15px/1.6 Georgia,'Noto Serif',serif;max-width:760px;margin:24px auto;padding:0 18px;color:#111}h1{font:700 18px/1.3 system-ui,sans-serif;border-bottom:2px solid #0b2a6b;padding-bottom:8px;margin:0 0 16px}"
            "p{margin:0 0 14px}.bar{font:13px system-ui,sans-serif;background:#fff6e8;border:1px solid #f5c98a;border-radius:10px;padding:10px 12px;margin-bottom:16px}button{font:600 14px system-ui;padding:9px 16px;border-radius:10px;border:0;background:#0b2a6b;color:#fff;cursor:pointer}"
            "@media print{.bar{display:none}body{margin:0}}</style></head><body><div class=\"bar\">This is a citizen's complaint letter prepared with JANSEVA AI (not a government site). Print it or Save as PDF and send it with the photo. "
            "<button onclick=\"window.print()\">Print / Save as PDF</button></div><h1>Public grievance: %s</h1>%s</body></html>") % (html.escape(c.get("code") or ""), html.escape(subject(c)), body)

def compose_links(to, subj, body, cc=""):
    q = lambda s: quote(s, safe="@,")
    qq = lambda s: quote(s, safe="")
    m = "mailto:%s?subject=%s&body=%s" % (q(to), qq(subj), qq(body)) + ("&cc=" + q(cc) if cc else "")
    g = "https://mail.google.com/mail/?view=cm&fs=1&to=%s&su=%s&body=%s" % (qq(to), qq(subj), qq(body)) + ("&cc=" + qq(cc) if cc else "")
    o = "https://outlook.live.com/mail/0/deeplink/compose?to=%s&subject=%s&body=%s" % (qq(to), qq(subj), qq(body)) + ("&cc=" + qq(cc) if cc else "")
    return {"mailto": m, "gmail": g, "outlook": o}

def send_all(emails, c, u, base=""):
    """One compose: officers in To, MP (if the citizen chose one) in Cc. Every address is a verified official one with a source."""
    off = [e["email"] for e in emails if e["level"] < 4]; mp = [e["email"] for e in emails if e["level"] >= 4]
    if not (off or mp): return None
    to = ",".join(off or mp); cc = ",".join(mp) if off else ""
    subj = "[%s] %s" % (c["code"], subject(c)); body = letter_text(c, u, {"target_name": "Concerned Authorities"}, base)
    if len(body) > 1500: body = letter_text(dict(c, description=(c.get("description") or "")[:600]), u, {"target_name": "Concerned Authorities"}, base)
    return {"to": off or mp, "cc": mp if off else [], "subject": subj, "body": body, "links": compose_links(to, subj, body, cc)}

def email_options(svc, c, u, base=""):
    out = []
    for d in svc.db.all("SELECT * FROM dispatches WHERE complaint_id=? AND kind<>'reminder' ORDER BY level,id", (c["id"],)):
        full = letter_text(c, u, d, base); short = full if len(full) <= 1500 else letter_text(dict(c, description=(c.get("description") or "")[:600]), u, d, base)
        done = svc.db.one("SELECT created_at FROM filing_records WHERE complaint_id=? AND channel='email' AND target=?", (c["id"], d["target_email"]))
        out.append({"level": d["level"], "name": d["target_name"], "email": d["target_email"], "source_url": d["source_url"], "source_date": d["source_date"], "tier": d["tier"],
                    "subject": "[%s] %s" % (c["code"], subject(c)), "body": full, "links": compose_links(d["target_email"], "[%s] %s" % (c["code"], subject(c)), short), "short_body_used": short != full,
                    "sent_by_citizen_at": done["created_at"] if done else None})
    return out

def portals(svc, c, u, base=""):
    cat = c.get("category") or "general"; full = letter_text(c, u, None, base); i = identity(c, u)
    desc = (c.get("description") or "").strip()
    common = {"title": c.get("title") or subject(c), "description": desc, "location": location_line(c), "gps": "%s, %s" % (c.get("lat"), c.get("lon")), "maps": maps_link(c), "photo": photo_link(c, base)}
    out = []
    out.append({"id": "cpgrams", "name": "CPGRAMS (Centralised Public Grievance Redress and Monitoring System)", "url": "https://pgportal.gov.in/", "register_url": "https://pgportal.gov.in/Registration",
                "who": "Central Government ministries/departments and State Governments. Free.", "needs": "Your own registration and login on the portal (mobile OTP / security code). Email complaints are not accepted by CPGRAMS.",
                "steps": ["Open pgportal.gov.in and click Register / Login. New user: sign up with your name, address, PIN, mobile and email.", "Log in and choose Lodge Public Grievance.",
                          "Pick the ministry/department or State Government concerned, then paste the Subject and Description below.", "Submit. You get a registration number. Save it and enter it here.", "Time limit shown by the portal: about 21 days. Track with View Status."],
                "fields": {"Subject": common["title"], "Grievance description": full[:3800], "Location / address": common["location"]},
                "sources": ["https://pgportal.gov.in/", "https://pgportal.gov.in/Registration"]})
    if cat in SWACHHATA_CAT or cat in ("garbage", "drainage", "toilet", "sanitation"):
        out.append({"id": "swachhata", "name": "Swachhata-MoHUA app (Swachh Bharat Mission - Urban)", "url": "https://www.swachh.city/", "register_url": "https://play.google.com/store/apps/details?id=com.ichangemycity.swachhbharat",
                    "who": "Sanitation and garbage complaints in cities (Urban Local Bodies onboarded on Swachhata). Free.", "needs": "The Swachhata app with your own mobile number and OTP. The platform's API is only for official city apps, not third parties.",
                    "steps": ["Install the Swachhata-MoHUA app (Android/iOS) and log in with your mobile number and the OTP.", "Allow location so the complaint is geo-tagged at the spot.", "Choose the category (suggested below), add the photo and the description.", "Submit. Note the complaint ID and enter it here."],
                    "fields": {"Suggested category": SWACHHATA_CAT.get(cat, "Garbage dump"), "Description": desc[:500], "Location": common["location"]},
                    "sources": ["https://www.swachh.city/", "https://www.swachh.city/assets/files/Integration_FAQ_V2.1.pdf"]})
    from . import localbody
    lb = localbody.find(c.get("city"), c.get("state") or "")
    if lb["status"] == "not_found":
        out.append({"id": "meri_panchayat", "name": "Meri Panchayat app (Ministry of Panchayati Raj)", "url": "https://informatics.nic.in/files/websites/oct-2023/meri-panchayat.php", "register_url": "",
                    "who": "Village (gram panchayat) issues: garbage, cleanliness, street lights, water supply. Free.", "needs": "The Meri Panchayat mobile app and your own login. Complaints carry a geo-tagged photo taken in the app. Users report the complaint feature can be unreliable.",
                    "steps": ["Install the Meri Panchayat app from the Play Store / App Store and log in.", "Choose your gram panchayat and open the complaint option.", "Take the geo-tagged photo in the app and paste the description below.", "Submit and note any complaint number."],
                    "fields": {"Description": desc[:500], "Location": common["location"]}, "sources": ["https://informatics.nic.in/files/websites/oct-2023/meri-panchayat.php"]})
    seen = {p["id"] for p in out}
    try: targets = svc.route(c["id"]).get("targets", [])
    except Exception: targets = []
    P = {p["id"]: p for p in svc.db.platforms()} if hasattr(svc.db, "platforms") else {}
    for t in targets:
        p = P.get(t["platform_id"]) if isinstance(t, dict) else None
        if p and p["id"] not in seen and p.get("url") and p["id"] not in ("dept_email_sandbox",):
            seen.add(p["id"])
            out.append({"id": p["id"], "name": p["name"], "url": p["url"], "register_url": "", "who": "Official portal for your location/category.", "needs": "Check the portal; many need your own login or a security code. " + (p.get("auth") or ""),
                        "steps": ["Open the official portal.", "Log in or register with your own details.", "Paste the subject and description below and add the photo.", "Submit and enter the number you get here."],
                        "fields": {"Subject": common["title"], "Description": desc[:1500], "Location": common["location"]}, "sources": [p["url"]]})
    CENTRAL = {"pension", "central_govt", "passport", "tax", "bank_insurance", "telecom", "service_matters", "police", "health", "education", "general"}
    def rank(o):
        if o["id"] == "cpgrams": return 0 if cat in CENTRAL else 9
        if o["id"] == "swachhata": return 2 if lb["status"] != "not_found" else 8
        if o["id"] == "meri_panchayat": return 1
        return 3
    out.sort(key=rank)
    for n, o in enumerate(out):
        o["best"] = n == 0
        o["copy_all"] = "\n".join("%s: %s" % (k, v) for k, v in o["fields"].items())
        o["why"] = ("Best match for this complaint" if n == 0 else "Also possible")
        r = svc.db.one("SELECT reference, status, created_at FROM filing_records WHERE complaint_id=? AND channel='portal' AND target=?", (c["id"], o["id"]))
        o["filed_by_citizen"] = dict(r) if r else None
    return out

def pack(svc, c, u, base=""):
    return {"complaint": {"code": c["code"], "status": c["status"]}, "letter_subject": subject(c), "identity_shared": identity(c, u)["share"],
            "email_note": "Opens in YOUR own email app or Gmail/Outlook, so it is sent from your own address. JANSEVA never sends complaint emails as you. Attach your photo if you can; the letter also links it.",
            "emails": email_options(svc, c, u, base), "send_all": send_all(email_options(svc, c, u, base), c, u, base), "mp_chosen": bool(c.get("constituency") and c.get("notify_representative")), "state": c.get("state"), "portals": portals(svc, c, u, base),
            "honesty": "Sending an email or filing on a portal is done by you. 'Sent by you' or a number you type here is NOT proof of government registration. Authority-marked and citizen-verified resolution stay separate."}

def mark(svc, c, channel, target, reference=None):
    if channel not in ("email", "portal") or not target: return {"ok": False, "error": "channel and target required"}
    ref = (reference or "").strip()[:80] or None
    if channel == "portal" and not ref: return {"ok": False, "error": "enter the registration/complaint number the portal gave you"}
    st = "sent_by_citizen" if channel == "email" else "filed_by_citizen"
    if svc.db.one("SELECT id FROM filing_records WHERE complaint_id=? AND channel=? AND target=?", (c["id"], channel, target)):
        svc.db.run("UPDATE filing_records SET reference=?, created_at=? WHERE complaint_id=? AND channel=? AND target=?", (ref, now(), c["id"], channel, target))
    else:
        svc.db.run("INSERT INTO filing_records(complaint_id,channel,target,reference,status,created_at) VALUES(?,?,?,?,?,?)", (c["id"], channel, target, ref, st, now()))
    if channel == "email": svc.db.run("UPDATE dispatches SET status='sent_by_citizen', sent_at=? WHERE complaint_id=? AND target_email=? AND status IN ('scheduled','failed')", (now(), c["id"], target))
    msg = ("You marked the complaint as emailed to %s from your own email (self-reported). Delivery or registration is not confirmed." % target) if channel == "email" else \
          ("You entered %s as the %s registration number (citizen-entered, not verified by JANSEVA)." % (ref, target))
    svc.db.timeline(c["id"], "citizen", st, msg); svc.db.audit("user:%s" % c["user_id"], "filing_" + st, "%s %s" % (target, ref or ""))
    return {"ok": True, "status": st}


TYPE_GUIDE = [
 {"type": "Garbage, dustbin, sweeping, dead animal, open drain/sewage, public toilet (city)", "portal": "Swachhata-MoHUA app + your city's municipal corporation grievance page", "url": "https://www.swachh.city/", "needs": "App + mobile OTP"},
 {"type": "Same, but village (gram panchayat area)", "portal": "Meri Panchayat app", "url": "https://meripanchayat.gov.in/homepage", "needs": "App + login"},
 {"type": "Road, pothole, street light, water supply, encroachment (city)", "portal": "Your city municipal corporation / state grievance portal (shown for your city on the filing screen)", "url": "https://pgportal.gov.in/", "needs": "Varies by city; many need login"},
 {"type": "Central government: pension, passport, income tax, bank/insurance, telecom, railways, central services", "portal": "CPGRAMS", "url": "https://pgportal.gov.in/Home/LodgeGrievance", "needs": "Registered account + security code. Register: https://pgportal.gov.in/Registration"},
 {"type": "State government departments (police, health, education, electricity)", "portal": "Your state's grievance portal; CPGRAMS also forwards to State governments", "url": "https://pgportal.gov.in/", "needs": "Login"},
]


def add_mp(svc, c, constituency):
    """Citizen taps 'add my MP': stores the choice (explicit consent for this complaint) and plans the verified Lok Sabha email, if any."""
    from . import dispatch
    from .service import load_data
    rows = [r for r in load_data("representatives_parliament.json") if r["house"] == "Lok Sabha" and (r.get("constituency") or "").lower() == (constituency or "").lower()]
    if not rows: return {"ok": False, "error": "constituency not in the official Lok Sabha list"}
    svc.db.run("UPDATE complaints SET constituency=?, notify_representative=1 WHERE id=?", (rows[0]["constituency"], c["id"]))
    svc.db.audit("user:%s" % c["user_id"], "filing_add_mp", rows[0]["constituency"])
    dispatch.plan(svc, c["id"])
    return {"ok": True, "constituency": rows[0]["constituency"], "name": rows[0]["name"]}
