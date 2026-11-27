import json, math, os, secrets
from datetime import datetime, timedelta, timezone
from .db import DB, now
from .router import classify, plan, lookup_ulb, infer_asset_owner
from .connectors.base import complaint_text
from .connectors.swachhata import SwachhataConnector
from .connectors.guided import GuidedConnector
from .connectors.email import EmailConnector

TERMINAL = {"resolved", "rejected"}

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
    def user_by_token(self, tok): return self.db.one("SELECT * FROM users WHERE token=?", (tok,)) if tok else None

    # ---- complaints -----------------------------------------------------
    def create_complaint(self, user, d):
        errs = []
        if not d.get("description"): errs.append("description required")
        if d.get("lat") is None or d.get("lon") is None: errs.append("GPS location required")
        elif not (6 <= float(d["lat"]) <= 38 and 68 <= float(d["lon"]) <= 98): errs.append("location outside India")
        if errs: return {"ok": False, "errors": errs}
        cat = d.get("category") or classify((d.get("title") or "") + " " + d["description"])
        dup = self.find_duplicate(user["id"], cat, float(d["lat"]), float(d["lon"]))
        if dup: return {"ok": False, "errors": ["duplicate of %s (same category within 100 m in 7 days)" % dup["code"]], "duplicate_of": dup["code"]}
        city = (d.get("city") or "").strip()
        n = self.db.one("SELECT count(*) n FROM complaints")["n"] + 1
        code = "JS-%s-%06d" % (datetime.now().year, n)
        asset = d.get("asset_owner")
        cid = self.db.run("""INSERT INTO complaints(code,user_id,title,description,category,lat,lon,address,city,state,district,ward,pincode,photo_url,asset_owner,
            status,consent_submit,consent_share_personal,notify_representative,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (code, user["id"], d.get("title"), d["description"], cat, float(d["lat"]), float(d["lon"]), d.get("address"), city.lower(),
             (d.get("state") or "").lower(), d.get("district"), d.get("ward"), d.get("pincode"), d.get("photo_url"), asset, "created",
             int(bool(d.get("consent_submit"))), int(bool(d.get("consent_share_personal"))), int(bool(d.get("notify_representative"))), now(), now()))
        self.db.timeline(cid, "jansevaai", "created", "Complaint created in category '%s'" % cat)
        self.db.audit("user:%s" % user["id"], "complaint_created", code)
        return {"ok": True, "id": cid, "code": code, "category": cat}

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
        r = self.route(cid)
        if r["needs"]: return {"ok": False, "needs": r["needs"]}
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
        self.db.run("UPDATE complaints SET status='submitted',updated_at=? WHERE id=?", (now(), cid))
        self.refresh_parent(cid)
        return {"ok": True, "results": results, "routing": r}

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

    def record_reference(self, cid, platform_id, ref, user_id):
        """Citizen reports the number the official portal gave them. Stored as citizen-reported, unverified."""
        rec = self.db.one("SELECT * FROM external_records WHERE complaint_id=? AND platform_id=?", (cid, platform_id))
        if not rec or rec["level"] < 3: return {"ok": False, "error": "no guided record for this platform"}
        self.db.run("UPDATE external_records SET external_ref=?,status='open',latest_update='Reference entered by citizen (unverified)',reference_source='citizen_reported',acknowledged_at=?,submitted_at=? WHERE id=?",
                    (ref, now(), now(), rec["id"]))
        self.db.timeline(cid, "citizen", "reference_added", "%s reference %s entered by citizen (not verified with the government)" % (platform_id, ref), rec["id"])
        self.db.audit("user:%s" % user_id, "reference_entered", "%s %s" % (cid, platform_id))
        self.refresh_parent(cid); return {"ok": True}

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
        """Parent is 'official_resolved' only when ALL official records are resolved. Citizen verification is separate."""
        c = self.get(cid)
        recs = [r for r in self.db.all("SELECT * FROM external_records WHERE complaint_id=?", (cid,)) if r["level"] <= 3 or r["external_ref"]]
        if not recs: return
        pend = [r for r in recs if r["status"] != "resolved"]
        if c["citizen_verified"] and not pend: st = "resolved_verified"
        elif not pend: st = "official_resolved"
        elif any(r["status"] == "resolved" for r in recs): st = "partially_resolved"
        else: st = "submitted"
        self.db.run("UPDATE complaints SET status=?,updated_at=? WHERE id=?", (st, now(), cid))

    def citizen_verify(self, cid, ok, user_id):
        self.db.run("UPDATE complaints SET citizen_verified=? WHERE id=?", (1 if ok else 0, cid))
        self.db.timeline(cid, "citizen", "verification", "Citizen %s the resolution" % ("verified" if ok else "rejected"))
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
            exists = self.db.one("SELECT id FROM timeline WHERE complaint_id=? AND kind='escalation' AND message LIKE ?", (e["complaint_id"], "%" + e["platform"] + "%"))
            if not exists:
                self.db.timeline(e["complaint_id"], "jansevaai", "escalation", "%s overdue by %d days. %s" % (e["platform"], e["overdue_days"], e["note"]))
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
        uniq = self.db.one("SELECT count(*) n FROM complaints WHERE status!='draft'")["n"]
        per = self.db.all("SELECT platform_id, count(*) n, sum(CASE WHEN external_ref IS NOT NULL AND reference_source='government_response' THEN 1 ELSE 0 END) acked, "
                          "sum(CASE WHEN status='resolved' THEN 1 ELSE 0 END) resolved, mode FROM external_records GROUP BY platform_id, mode")
        return {"unique_citizen_complaints": uniq, "external_records_total": sum(p["n"] for p in per), "per_platform": per,
                "official_resolved": self.db.one("SELECT count(*) n FROM complaints WHERE status IN ('official_resolved','resolved_verified')")["n"],
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
