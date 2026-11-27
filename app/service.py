import json, math, os, secrets
from datetime import datetime, timedelta, timezone
from .db import DB, now
from .router import classify, plan, lookup_ulb, infer_asset_owner
from . import ai
from .connectors.base import complaint_text
from .connectors.swachhata import SwachhataConnector
from .connectors.guided import GuidedConnector
from .connectors.email import EmailConnector

TERMINAL = {"resolved", "rejected"}

import json as _json
_DD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_CACHE = {}
def load_data(name):
    if name in _CACHE: return _CACHE[name]
    try: _CACHE[name] = _json.load(open(os.path.join(_DD, name))); return _CACHE[name]
    except Exception: return []

class Service:
    def __init__(self, db: DB = None, env=None, sandbox_base=None):
        self.db = db or DB()
        self.env = dict(os.environ) if env is None else env
        self.sandbox_base = sandbox_base
    # connectors are built per call so registry edits apply immediately
    def connectors(self):
        out = {}
        for p in self.db.platforms():
            k = p.get("connector")
            if k == "swachhata": out[p["id"]] = SwachhataConnector(p, self.env, sandbox_base=self.sandbox_base)
            elif k == "email": out[p["id"]] = EmailConnector(p, self.env)
            else: out[p["id"]] = GuidedConnector(p, self.env)
        return out

    # ---- users ----------------------------------------------------------
    def register(self, phone, name):
        u = self.db.one("SELECT * FROM users WHERE phone=?", (phone,))
        if u: return u
        tok = secrets.token_urlsafe(24)
        self.db.run("INSERT INTO users(phone,name,token,created_at) VALUES(?,?,?,?)", (phone, name, tok, now()))
        self.db.audit("system", "user_registered", phone[-4:])
        return self.db.one("SELECT * FROM users WHERE phone=?", (phone,))
    def user_by_token(self, tok):
        """Session token with 30-day sliding expiry. Tokens issued before expiry existed get an expiry on first use."""
        if not tok: return None
        u = self.db.one("SELECT * FROM users WHERE token=?", (tok,))
        if not u: return None
        from datetime import datetime, timedelta, timezone
        n = datetime.now(timezone.utc); exp = u.get("token_exp")
        if exp and datetime.fromisoformat(exp) < n: return None
        if not exp or datetime.fromisoformat(exp) - n < timedelta(days=29):
            self.db.run("UPDATE users SET token_exp=? WHERE id=?", ((n + timedelta(days=30)).isoformat(), u["id"]))
        return u

    # ---- complaints -----------------------------------------------------
    def create_complaint(self, user, d):
        errs = []
        if not d.get("description"): errs.append("description required")
        if d.get("lat") is None or d.get("lon") is None: errs.append("GPS location required")
        elif not (6 <= float(d["lat"]) <= 38 and 68 <= float(d["lon"]) <= 98): errs.append("location outside India")
        if errs: return {"ok": False, "errors": errs}
        an = ai.analyze(d.get("title"), d["description"], d.get("photo_url"))
        user_cat = d.get("category")
        try:   # the citizen may confirm/edit the severity of an AI draft; a rule-detected emergency is never lowered
            us = int(d.get("severity")); an = dict(an, severity=max(1, min(5, us)) if not an.get("emergency") else max(an["severity"], us), safety_risk="high" if us >= 4 else "medium" if us == 3 else "low") if 1 <= us <= 5 else an
        except (TypeError, ValueError): pass
        cat = user_cat or an["category"]
        low_conf = (not user_cat) and an["confidence"] < 0.6
        # Never block filing: many people can report different issues from the same place. Similar nearby reports are only a hint.
        similar = self.similar_nearby(cat, float(d["lat"]), float(d["lon"]))
        city = (d.get("city") or "").strip()
        pin = str(d.get("pincode") or "")
        pt = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "pincodes.json")))["prefixes"].get(pin[:3])
        if not city and pt: city = pt[0]; d["state"] = d.get("state") or pt[1]
        n = self.db.one("SELECT count(*) n FROM complaints")["n"] + 1
        code = "JS-%s-%06d" % (datetime.now().year, n)
        status = "awaiting_citizen_confirmation" if low_conf else "ready_for_submission"
        cid = self.db.run("""INSERT INTO complaints(code,user_id,title,description,category,lat,lon,address,city,state,district,ward,pincode,photo_url,asset_owner,
            status,consent_submit,consent_share_personal,notify_representative,created_at,updated_at,anonymous,severity,confidence,safety_risk,emergency,lang,phash)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (code, user["id"], d.get("title"), d["description"], cat, float(d["lat"]), float(d["lon"]), d.get("address"), city.lower(),
             (d.get("state") or "").lower(), d.get("district"), d.get("ward"), d.get("pincode"), d.get("photo_url"), d.get("asset_owner"), status,
             int(bool(d.get("consent_submit"))), int(bool(d.get("consent_share_personal"))), int(bool(d.get("notify_representative"))), now(), now(),
             int(bool(d.get("anonymous"))), an["severity"], an["confidence"], an["safety_risk"], int(an["emergency"]), d.get("lang") or "en", (d.get("phash") or None)))
        self.db.run("INSERT INTO ai_analysis(complaint_id,ts,engine,category,confidence,severity,safety_risk,emergency,suggested_department,notes) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (cid, now(), an["engine"], an["category"], an["confidence"], an["severity"], an["safety_risk"], int(an["emergency"]), an["suggested_department"], an["notes"]))
        self.db.timeline(cid, "jansevaai", "created", "Complaint reported (category '%s')" % cat)
        self.db.timeline(cid, "jansevaai", "ai_analysed", "AI analysis (%s): %s, confidence %.1f, severity %d, safety risk %s%s" % (an["engine"], an["category"], an["confidence"], an["severity"], an["safety_risk"], "; EMERGENCY flag" if an["emergency"] else ""))
        if low_conf: self.db.timeline(cid, "jansevaai", "needs_confirmation", "Low confidence: citizen must confirm or choose the category")
        # community duplicate grouping (other citizens, same place and category)
        grp = None; prob = None
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        for r in self.db.all("SELECT * FROM complaints WHERE id!=? AND status!='cancelled' AND created_at>=?", (cid, recent)):
            dm = self.dist_m(float(d["lat"]), float(d["lon"]), r["lat"], r["lon"])
            ham = self.hamming(d.get("phash"), r["phash"])
            same_place_cat = dm <= 100 and r["category"] == cat
            img_match = ham is not None and ham <= 10 and dm <= 300
            if same_place_cat or img_match:
                prob = 0.95 if (same_place_cat and img_match) else 0.8 if img_match else 0.6
                grp = r["duplicate_group"]
                if not grp:
                    grp = self.db.run("INSERT INTO duplicate_groups(parent_complaint_id,lat,lon,category,created_at) VALUES(?,?,?,?,?)", (r["id"], r["lat"], r["lon"], cat, now()))
                    self.db.run("UPDATE complaints SET duplicate_group=? WHERE id=?", (grp, r["id"]))
                self.db.run("UPDATE complaints SET duplicate_group=?,duplicate_probability=? WHERE id=?", (grp, prob, cid))
                self.db.timeline(cid, "jansevaai", "duplicate_grouped", "Grouped with %s (%s). Your own reference is kept." % (r["code"], "image and place match" if img_match else "same place and category"))
                self.db.run("INSERT OR IGNORE INTO supports(complaint_id,user_id,kind,ts) VALUES(?,?,?,?)", (r["id"], user["id"], "support", now()))
                break
        self.db.audit("user:%s" % user["id"], "complaint_created", code)
        out = {"ok": True, "id": cid, "code": code, "category": cat, "status": status, "ai": an, "duplicate_group": grp, "duplicate_probability": prob, "similar_nearby": [x for x in similar if x["id"] != cid]}
        if an["emergency"]: out["emergency_notice"] = "Immediate danger: call 112 now. JANSEVA is not an emergency dispatch service."
        return out

    def confirm_category(self, cid, category, user_id):
        c = self.get(cid)
        self.db.run("UPDATE complaints SET category=?,status='ready_for_submission',updated_at=? WHERE id=?", (category, now(), cid))
        self.db.timeline(cid, "citizen", "confirmed", "Citizen confirmed category '%s'" % category)
        self.db.audit("user:%s" % user_id, "category_confirmed", c["code"]); return {"ok": True}

    @staticmethod
    def hamming(a, b):
        """Perceptual-hash distance. Hashes are computed in the browser (64-bit dHash, 16 hex chars). None if either is missing or malformed."""
        try:
            if not a or not b or len(a) != 16 or len(b) != 16: return None
            return bin(int(a, 16) ^ int(b, 16)).count("1")
        except ValueError: return None

    def similar_nearby(self, cat, lat, lon, radius=250, days=30, limit=3):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(); out = []
        for r in self.db.all("SELECT id,code,status,lat,lon FROM complaints WHERE category=? AND created_at>=? AND status NOT IN ('cancelled','rejected') ORDER BY id DESC LIMIT 400", (cat, cutoff)):
            m = self.dist_m(lat, lon, r["lat"], r["lon"])
            if m <= radius: out.append({"id": r["id"], "code": r["code"], "status": r["status"], "distance_m": int(m)})
        return sorted(out, key=lambda x: x["distance_m"])[:limit]
    def find_duplicate(self, uid, cat, lat, lon):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        for r in self.db.all("SELECT * FROM complaints WHERE user_id=? AND category=? AND created_at>=? AND status!='cancelled'", (uid, cat, cutoff)):
            if self.dist_m(lat, lon, r["lat"], r["lon"]) <= 100: return r
        return None
    @staticmethod
    def dist_m(a, b, c, d):
        R = 6371000; p1, p2 = math.radians(a), math.radians(c)
        x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
        return 2 * R * math.asin(math.sqrt(x))

    def get(self, cid): return self.db.one("SELECT * FROM complaints WHERE id=?", (cid,))

    def route(self, cid):
        c = self.get(cid); u = self.db.one("SELECT * FROM users WHERE id=?", (c["user_id"],))
        return plan(c, self.db.platforms(), self.connectors(), u)

    def submit(self, cid):
        c = self.get(cid); u = self.db.one("SELECT * FROM users WHERE id=?", (c["user_id"],))
        if not c["consent_submit"]:
            return {"ok": False, "error": "citizen consent to submit is required"}
        if c["status"] == "awaiting_citizen_confirmation":
            return {"ok": False, "error": "citizen must confirm the category first"}
        if c["duplicate_group"]:
            g = self.db.one("SELECT parent_complaint_id FROM duplicate_groups WHERE id=?", (c["duplicate_group"],))
            if g and g["parent_complaint_id"] != cid and self.db.one("SELECT id FROM external_records WHERE complaint_id=?", (g["parent_complaint_id"],)):
                pc = self.get(g["parent_complaint_id"])
                self.db.timeline(cid, "jansevaai", "merged", "Merged into %s which is already filed; no duplicate government complaint was created. Updates are mirrored." % pc["code"])
                return {"ok": True, "merged_into": pc["code"], "results": []}
        r = self.route(cid)
        if r["needs"]:
            self.db.run("UPDATE complaints SET needs_human=1 WHERE id=?", (cid,))
            return {"ok": False, "needs": r["needs"]}
        if not r["targets"]:
            self.db.run("UPDATE complaints SET needs_human=1 WHERE id=?", (cid,))
            self.db.timeline(cid, "jansevaai", "needs_verification", "No verified official channel matches. Sent to the human verification queue instead of an arbitrary authority.")
            return {"ok": False, "needs": ["No matching verified channel. A verification officer must review."]}
        conns = self.connectors(); results = []
        ulb = r["context"]["ulb"]
        cc = dict(c)
        if ulb: cc["ulb_id"] = ulb["ulb_id"]; cc["ulb_swachhata"] = ulb["swachhata_onboarded"]
        if r["context"]["asset_owner"]: cc["asset_owner"] = r["context"]["asset_owner"]
        self.db.timeline(cid, "jansevaai", "routed", "Routed to: %s. Not used: %s" % (
            ", ".join(t["platform_id"] for t in r["targets"]) or "none",
            "; ".join("%s (%s)" % x for x in r["rejected"][:6])))
        for t in r["targets"]:
            p = self.db.platform(t["platform_id"]); conn = conns[t["platform_id"]]
            if t["notify_only"]: continue
            if self.db.one("SELECT id FROM external_records WHERE complaint_id=? AND platform_id=?", (cid, p["id"])): continue  # no duplicate gov complaint
            if t["validation_errors"]:
                results.append({"platform": p["id"], "status": "invalid", "errors": t["validation_errors"]})
                self.db.timeline(cid, p["id"], "validation_failed", "; ".join(t["validation_errors"]))
                continue
            if p["level"] <= 2 and c["anonymous"]:
                results.append({"platform": p["id"], "status": "blocked", "errors": ["official submission needs identity; this report is anonymous"]}); continue
            if p["level"] <= 2 and not c["consent_share_personal"]:
                results.append({"platform": p["id"], "status": "blocked", "errors": ["explicit consent to share personal details required"]}); continue
            res = conn.submit(cc, u)
            self.db.ilog(p["id"], cid, "submit", res.ok, res.http_code, res.message)
            results.append(self._store(cid, p, conn, res))
        # authority notifications (separate workflow)
        for t in r["targets"]:
            if t["notify_only"]: results.append(self._notify(cid, cc, u, self.db.platform(t["platform_id"]), conns[t["platform_id"]]))
        if c["notify_representative"]:
            self.db.run("INSERT INTO notifications(complaint_id,ts,audience,channel,target,status,body) VALUES(?,?,?,?,?,?,?)",
                        (cid, now(), "elected_representative", "email", "(verified public contact required)", "not_sent_no_verified_contact", "citizen opted in"))
        self.db.run("UPDATE complaints SET routing_json=?,needs_human=0,updated_at=? WHERE id=?", (json.dumps(self.four_roles(cc, r)), now(), cid))
        self.refresh_parent(cid)
        return {"ok": True, "results": results, "routing": r}

    def four_roles(self, c, r):
        """Separate fields: operational authority, grievance redressal, elected representative, escalation authority. Only from the verified directory."""
        def pick(types):
            for a in self.db.all("SELECT * FROM authorities WHERE verified=1"):
                if a["type"] in types and (not a["city"] or a["city"].lower() == (c.get("city") or "")) and (not a["state"] or a["state"].lower() == (c.get("state") or "")):
                    if not a["categories"] or c["category"] in a["categories"].split(","): return {"id": a["id"], "name": a["name"], "last_verified": a["last_verified"]}
            return None
        rep = self.db.one("SELECT id,name,office,last_verified FROM representatives WHERE verified=1 AND (city IS NULL OR lower(city)=?) AND (state IS NULL OR lower(state)=?) LIMIT 1", (c.get("city") or "", c.get("state") or ""))
        explain = "Routed by category '%s' and location '%s'; channels: %s." % (c["category"], c.get("city") or "unknown", ", ".join(t["platform_id"] for t in r["targets"]))
        return {"operational_authority": pick(["operational"]), "grievance_authority": pick(["grievance"]), "elected_representative": rep,
                "escalation_authority": pick(["escalation"]), "explanation": explain,
                "note": "null means no verified directory entry exists yet; nothing is guessed"}

    def _store(self, cid, p, conn, res):
        status = res.status
        sub = now() if res.status in ("submitted", "queued_sandbox") else None
        ack = now() if res.external_ref else None
        guide = res.guide
        update = res.message
        if guide: update = "Ready for official submission. Not yet registered."
        if res.status in ("submitted", "guided_ready", "queued_sandbox"):
            eid = self.db.run("""INSERT OR REPLACE INTO external_records(complaint_id,platform_id,department,level,mode,method,external_ref,status,latest_update,tracking_url,
                submitted_at,acknowledged_at,last_sync_at,evidence,reference_source,terminal) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                (cid, p["id"], p["department"], p["level"], res.mode, res.method, res.external_ref,
                 "pending_citizen_submission" if guide else ("sandbox_queued" if res.status == "queued_sandbox" else "open"), update, p.get("url"),
                 sub, ack, None, json.dumps(res.evidence if not guide else {"guide": guide}), "government_response" if res.external_ref else "none"))
            tag = {"live": "LIVE", "sandbox": "SANDBOX", "guided": "GUIDED"}.get(res.mode, res.mode)
            self.db.timeline(cid, p["id"], "submitted" if res.external_ref else "prepared",
                             "[%s] %s: %s" % (tag, p["name"], ("official ref " + res.external_ref) if res.external_ref else update), eid)
            return {"platform": p["id"], "status": res.status, "external_ref": res.external_ref, "mode": res.mode, "guide": guide}
        self.db.timeline(cid, p["id"], "failed", "%s: %s (%s)" % (p["name"], res.status, res.message))
        return {"platform": p["id"], "status": res.status, "error": res.message}

    def _notify(self, cid, c, u, p, conn):
        res = conn.submit(c, u)
        self.db.run("INSERT INTO notifications(complaint_id,ts,audience,channel,target,status,body) VALUES(?,?,?,?,?,?,?)",
                    (cid, now(), "responsible_department", "email", p.get("email_target"), res.status, res.evidence.get("body", "")))
        self.db.timeline(cid, "jansevaai", "authority_notified", "Department notified (%s). This is a notification, not a government registration." % res.status)
        return {"platform": p["id"], "status": res.status, "note": "notification only"}

    def email_authority(self, cid, to_email, authority_name, user):
        """Send the citizen's consented complaint by email from the JANSEVA mailbox. Delivery is NOT registration: status stays 'sent_unacknowledged'."""
        from . import mailer
        from .connectors.base import complaint_text
        c = self.db.one("SELECT * FROM complaints WHERE id=?", (cid,))
        if not c or not c["consent_submit"]: return {"ok": False, "error": "citizen consent for submission is required first"}
        if not to_email or "@" not in to_email: return {"ok": False, "error": "no verified email target"}
        known = {x.get("email") for f in ("authorities_central_nodal.json", "authorities_state_nodal.json") for x in load_data(f)}
        row = self.db.one("SELECT 1 AS x FROM authorities WHERE grievance_email=? AND verified=1", (to_email,))
        if to_email not in known and not row: return {"ok": False, "error": "target email is not in the official directory"}
        name = user.get("name", "") if c["consent_share_personal"] and not c["anonymous"] else ""
        base = self.env.get("PUBLIC_BASE_URL", "")
        body = complaint_text(c, name) + ("\nPhoto: %s%s\n" % (base, c["photo_url"]) if c["photo_url"] and base else "") + "\nTracking ID: %s (please keep this ID in replies)\n" % c["code"]
        reply_to = None
        if mailer.configured(self.env):
            fa = mailer.from_address(self.env).split("<")[-1].strip(" >"); lo, _, dom = fa.partition("@"); reply_to = "%s+%s@%s" % (lo, c["code"], dom)
        r = mailer.send(to_email, "[%s] Public grievance: %s" % (c["code"], c["title"]), body, reply_to, self.env)
        st = "sent_unacknowledged" if r["sent"] else "not_sent_smtp_unconfigured"
        self.db.run("INSERT INTO notifications(complaint_id,ts,audience,channel,target,status,body) VALUES(?,?,?,?,?,?,?)", (cid, now(), "authority:" + authority_name, "email", to_email, st, body))
        self.db.timeline(cid, "jansevaai", "email_sent" if r["sent"] else "email_not_sent", ("Emailed %s at %s with your consent. This is delivery, not a registration; an official reply is needed." % (authority_name, to_email)) if r["sent"] else "Email not sent: %s" % r.get("reason"))
        return {"ok": r["sent"], "status": st, "note": "delivery is not registration"}

    def ingest_replies(self):
        """Parse replies from the JANSEVA mailbox. Records them in the timeline; NEVER auto-marks resolved."""
        from . import mailer
        n = 0
        for m in mailer.poll_inbox(self.env):
            if "error" in m: return {"error": m["error"]}
            c = self.db.one("SELECT id FROM complaints WHERE upper(code)=?", (m["code"],))
            if not c: continue
            if self.db.one("SELECT 1 AS x FROM timeline WHERE complaint_id=? AND kind='authority_reply' AND message LIKE ?", (c["id"], "%" + m["imap_id"] + "%")): continue
            self.db.timeline(c["id"], "authority_email", "authority_reply", "Reply received from %s (mail #%s): %s" % (m["from"], m["imap_id"], m["snippet"][:300]))
            n += 1
        return {"ingested": n}

    def record_reference(self, cid, platform_id, ref, user_id):
        """Citizen reports the number the official portal gave them. Stored as citizen-reported, unverified."""
        rec = self.db.one("SELECT * FROM external_records WHERE complaint_id=? AND platform_id=?", (cid, platform_id))
        if not rec or rec["level"] < 3: return {"ok": False, "error": "no guided record for this platform"}
        self.db.run("UPDATE external_records SET external_ref=?,status='open',latest_update='Reference entered by citizen (unverified)',reference_source='citizen_reported',acknowledged_at=?,submitted_at=? WHERE id=?",
                    (ref, now(), now(), rec["id"]))
        self.db.timeline(cid, "citizen", "reference_added", "%s reference %s entered by citizen (not verified with the government)" % (platform_id, ref), rec["id"])
        self.db.audit("user:%s" % user_id, "reference_entered", "%s %s" % (cid, platform_id))
        self.refresh_parent(cid); return {"ok": True}

    def portal_status(self, cid, platform_id, status, note, user_id):
        rec = self.db.one("SELECT * FROM external_records WHERE complaint_id=? AND platform_id=?", (cid, platform_id))
        if not rec or not rec["external_ref"] or rec["level"] < 3: return {"ok": False, "error": "add the portal reference first"}
        if status not in ("in progress", "reply received", "closed on portal", "rejected on portal"): return {"ok": False, "error": "unknown status"}
        msg = "Citizen-reported status on %s portal: %s%s (not verified with the government)" % (platform_id, status, (" - " + note[:300]) if note else "")
        self.db.run("UPDATE external_records SET latest_update=? WHERE id=?", (msg, rec["id"]))
        self.db.timeline(cid, "citizen", "portal_status", msg, rec["id"]); self.db.audit("user:%s" % user_id, "portal_status", "%s %s" % (cid, platform_id))
        return {"ok": True, "note": "Closing on the portal does not mark it resolved. Verify the fix on the spot."}

    # ---- status sync -----------------------------------------------------
    def sync(self, cid=None):
        recs = self.db.all("SELECT * FROM external_records WHERE terminal=0 AND external_ref IS NOT NULL AND reference_source='government_response'" + (" AND complaint_id=%d" % cid if cid else ""))
        conns = self.connectors(); out = []
        for r in recs:
            st = conns[r["platform_id"]].track(r["external_ref"])
            self.db.ilog(r["platform_id"], r["complaint_id"], "track", st.ok, None, st.update)
            if not st.ok:
                out.append({"record": r["id"], "ok": False}); continue
            changed = st.status != r["status"] or (st.update or "") != (r["latest_update"] or "")
            self.db.run("UPDATE external_records SET status=?,latest_update=?,last_sync_at=?,terminal=? WHERE id=?",
                        (st.status, st.update or r["latest_update"], now(), 1 if st.status in TERMINAL else 0, r["id"]))
            if changed:
                self.db.timeline(r["complaint_id"], r["platform_id"], "status", "%s: %s %s" % (st.department or r["department"], st.status, st.update or ""), r["id"])
                self.db.run("INSERT INTO notifications(complaint_id,ts,audience,channel,target,status,body) VALUES(?,?,?,?,?,?,?)",
                            (r["complaint_id"], now(), "citizen", "in_app", "owner", "queued", "Update from %s: %s" % (r["platform_id"], st.status)))
            self.refresh_parent(r["complaint_id"]); out.append({"record": r["id"], "ok": True, "status": st.status})
        return out

    def refresh_parent(self, cid):
        """Lifecycle: 'Authority Marked Resolved' and 'Citizen Verified Resolved' are separate. A closure alone never means resolved for the citizen."""
        c = self.get(cid)
        recs = self.db.all("SELECT * FROM external_records WHERE complaint_id=?", (cid,))
        if not recs: return
        with_ref = [r for r in recs if r["external_ref"]]
        official = [r for r in recs if r["level"] <= 3 or r["external_ref"]]
        pend = [r for r in official if r["status"] not in ("resolved",)]
        states = {r["status"] for r in official}
        basis = "none"
        if any(r["mode"] == "live" and r["reference_source"] == "government_response" for r in recs): basis = "government_confirmed"
        elif any(r["reference_source"] == "citizen_reported" for r in recs): basis = "citizen_reported"
        elif any(r["mode"] == "sandbox" and r["external_ref"] for r in recs): basis = "sandbox"
        if official and all(r["status"] == "rejected" for r in official): st = "rejected"
        elif not pend and c["citizen_verified"]: st = "citizen_verified_resolved"
        elif not pend and c["reopened"]: st = "reopened"
        elif not pend: st = "authority_marked_resolved"
        else:
            if c["reopened"]: self.db.run("UPDATE complaints SET reopened=0 WHERE id=?", (cid,))
            if "assigned" in states: st = "assigned"
            elif any(r["status"] == "resolved" for r in official): st = "in_progress"
            elif with_ref: st = "acknowledged"
            else: st = "ready_for_submission"
            if self.db.one("SELECT id FROM escalation_records WHERE complaint_id=?", (cid,)) and st not in ("ready_for_submission",): st = "escalated"
        self.db.run("UPDATE complaints SET status=?,official_basis=?,updated_at=? WHERE id=?", (st, basis, now(), cid))

    def citizen_verify(self, cid, ok, user_id, after_photo=None, note=""):
        """Before/after: citizen confirms or rejects the authority's closure. Rejection reopens and shows the appeal route."""
        if after_photo: self.db.run("UPDATE complaints SET after_photo_url=? WHERE id=?", (after_photo, cid))
        self.db.run("UPDATE complaints SET citizen_verified=?,reopened=? WHERE id=?", (1 if ok else 0, 0 if ok else 1, cid))
        self.db.run("INSERT INTO verifications(complaint_id,ts,kind,photo_url,note,user_id) VALUES(?,?,?,?,?,?)", (cid, now(), "confirmed" if ok else "rejected", after_photo, note, user_id))
        self.db.timeline(cid, "citizen", "verification", "Citizen %s the resolution%s" % ("verified" if ok else "rejected", " (after photo attached)" if after_photo else ""))
        if not ok:
            for r in self.db.all("SELECT platform_id FROM external_records WHERE complaint_id=?", (cid,)):
                p = self.db.platform(r["platform_id"])
                if p.get("supports_appeal"): self.db.timeline(cid, "jansevaai", "appeal_route", "Official appeal route available on %s. Use the platform's own appeal." % p["name"])
        self.db.audit("user:%s" % user_id, "verify", str(cid)); self.refresh_parent(cid)

    # ---- escalation ------------------------------------------------------
    def escalations(self, as_of=None):
        as_of = as_of or datetime.now(timezone.utc); out = []
        for r in self.db.all("SELECT * FROM external_records WHERE terminal=0 AND external_ref IS NOT NULL"):
            p = self.db.platform(r["platform_id"]); sla = p.get("sla_days", 7)
            sub = datetime.fromisoformat(r["submitted_at"])
            if as_of - sub < timedelta(days=sla): continue
            if p.get("supports_appeal"):
                a = {"action": "official_appeal", "note": "Use the platform's own appeal mechanism; preserve ref %s" % r["external_ref"]}
            else:
                a = {"action": "reminder_only", "note": "Platform has no verified appeal route. A reminder is NOT an official appeal. Next authority to approach must be confirmed by admin."}
            out.append({"complaint_id": r["complaint_id"], "platform": r["platform_id"], "ref": r["external_ref"], "overdue_days": (as_of - sub).days - sla, **a})
        return out
    def run_escalation(self, as_of=None):
        res = self.escalations(as_of)
        for e in res:
            exists = self.db.one("SELECT id FROM escalation_records WHERE complaint_id=? AND platform_id=?", (e["complaint_id"], e["platform"]))
            if not exists:
                prev = self.db.one("SELECT count(*) n FROM escalation_records WHERE complaint_id=?", (e["complaint_id"],))["n"]
                lvl = min(7, 2 + prev)
                pol = self.db.one("SELECT name FROM escalation_policy WHERE level=?", (lvl,))
                self.db.run("INSERT INTO escalation_records(complaint_id,ts,level,platform_id,action,note) VALUES(?,?,?,?,?,?)", (e["complaint_id"], now(), lvl, e["platform"], e["action"], e["note"]))
                self.db.timeline(e["complaint_id"], "jansevaai", "escalation", "Level %d (%s): %s overdue by %d days. %s Deadline is a configured reminder, not a statutory one unless the platform publishes it." % (lvl, pol["name"] if pol else "", e["platform"], e["overdue_days"], e["note"]))
                self.refresh_parent(e["complaint_id"])
        return res

    # ---- views -----------------------------------------------------------
    def detail(self, cid):
        c = self.get(cid)
        ex = self.db.all("SELECT * FROM external_records WHERE complaint_id=?", (cid,))
        for r in ex:
            r["evidence"] = json.loads(r["evidence"] or "{}")
        return {"complaint": c, "external_records": ex, "timeline": self.db.all("SELECT * FROM timeline WHERE complaint_id=? ORDER BY id", (cid,)),
                "notifications": self.db.all("SELECT * FROM notifications WHERE complaint_id=? ORDER BY id", (cid,))}
    def list_for(self, uid): return self.db.all("SELECT * FROM complaints WHERE user_id=? ORDER BY id DESC", (uid,))

    def control_center(self):
        pl = self.db.platforms(); conns = self.connectors()
        by_level = {}
        for p in pl: by_level.setdefault(p["level"], 0); by_level[p["level"]] += 1
        modes = {}
        for p in pl:
            m = conns[p["id"]].mode(); modes[m] = modes.get(m, 0) + 1
        logs = self.db.all("SELECT ok, count(*) n FROM integration_log WHERE action='submit' GROUP BY ok")
        fails = self.db.all("SELECT * FROM integration_log WHERE ok=0 ORDER BY id DESC LIMIT 20")
        return {"total_platforms": len(pl), "full_api": by_level.get(1, 0), "partial_api": by_level.get(2, 0),
                "guided_or_manual": sum(v for k, v in by_level.items() if k >= 3),
                "awaiting_authorization": [p["id"] for p in pl if p.get("approval_status") in ("awaiting_ulb_credentials",)],
                "live_connected": [p["id"] for p in pl if conns[p["id"]].mode() == "live"],
                "sandbox": [p["id"] for p in pl if conns[p["id"]].mode() == "sandbox"],
                "modes": modes,
                "submissions_ok": sum(l["n"] for l in logs if l["ok"]), "submissions_failed": sum(l["n"] for l in logs if not l["ok"]),
                "pending_acknowledgements": self.db.one("SELECT count(*) n FROM external_records WHERE external_ref IS NULL")["n"],
                "sync_failures": self.db.one("SELECT count(*) n FROM integration_log WHERE action='track' AND ok=0")["n"],
                "credential_problems": self.db.all("SELECT platform_id, http_code, ts FROM integration_log WHERE http_code IN (401,403) ORDER BY id DESC LIMIT 10"),
                "recent_errors": fails}
    def analytics(self):
        uniq = self.db.one("SELECT count(*) n FROM complaints WHERE status NOT IN ('draft')")["n"]
        per = self.db.all("SELECT platform_id, count(*) n, sum(CASE WHEN external_ref IS NOT NULL AND reference_source='government_response' THEN 1 ELSE 0 END) acked, "
                          "sum(CASE WHEN status='resolved' THEN 1 ELSE 0 END) resolved, mode FROM external_records GROUP BY platform_id, mode")
        return {"unique_citizen_complaints": uniq, "external_records_total": sum(p["n"] for p in per), "per_platform": per,
                "official_resolved": self.db.one("SELECT count(*) n FROM complaints WHERE status IN ('authority_marked_resolved','citizen_verified_resolved')")["n"],
                "citizen_verified": self.db.one("SELECT count(*) n FROM complaints WHERE citizen_verified=1")["n"],
                "note": "Sandbox and guided records are listed by mode and are not official government acknowledgements."}

    def add_platform(self, p, actor):
        need = ["id", "name", "level", "connector", "categories", "jurisdiction"]
        miss = [k for k in need if k not in p]
        if miss: return {"ok": False, "error": "missing " + ",".join(miss)}
        if p["level"] not in (1, 2, 3, 4, 5): return {"ok": False, "error": "level must be 1-5"}
        if p["level"] <= 2 and p.get("approval_status") != "approved": p["approval_status"] = "awaiting_ulb_credentials"
        p.setdefault("department", ""); p.setdefault("last_verified", now()[:10])
        self.db.add_platform(p); self.db.audit(actor, "platform_added", p["id"]); return {"ok": True}
