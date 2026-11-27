import json, os, secrets, sys, time, hashlib, urllib.parse
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .service import Service
from .connectors.mock_gov import MockSwachhata
from . import accounts, public, assistant, roles
from .db import ROOT, now

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
UPLOADS = os.environ.get("JANSEVA_UPLOADS", os.path.join(ROOT, "uploads"))
ADMIN_TOKEN = os.environ.get("JANSEVA_ADMIN_TOKEN") or secrets.token_urlsafe(16)
MAX_UPLOAD = 5 * 1024 * 1024
MAGIC = {b"\xff\xd8\xff": ("jpg", "image/jpeg"), b"\x89PNG": ("png", "image/png")}

def make_handler(svc, admin_token, rate=120):
    hits = defaultdict(deque)
    dev_otp = os.environ.get("JANSEVA_DEV_OTP") == "1"
    require_otp = os.environ.get("JANSEVA_REQUIRE_OTP") == "1"
    os.makedirs(UPLOADS, exist_ok=True)
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, code, body, ctype="application/json", extra=None):
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items(): self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)
        def _json(self, code, obj): self._send(code, json.dumps(obj, default=str).encode())
        def _raw(self):
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(min(n, MAX_UPLOAD + 1))
        def _body(self):
            try: return json.loads(self._raw() or b"{}")
            except Exception: return {}
        def _tok(self): return (self.headers.get("Authorization") or "").replace("Bearer ", "").strip()
        def _user(self): return svc.user_by_token(self._tok())
        def _adm(self): return accounts.admin_by_token(svc.db, self._tok(), admin_token)
        def _limited(self):
            k = self._tok() or self.client_address[0]; q = hits[k]; t = time.time()
            while q and q[0] < t - 60: q.popleft()
            q.append(t); return len(q) > rate
        def _owned(self, user, cid):
            c = svc.get(cid)
            if not c: return None
            if user and c["user_id"] == user["id"]: return c
            a = self._adm()
            return c if a and roles.can(a["role"], "complaints.view") and roles.in_scope(a, c) else None
        def _q(self): return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
        def do_GET(self):
            if self._limited(): return self._json(429, {"error": "rate limit"})
            path = urllib.parse.urlparse(self.path).path; q = self._q()
            if path in ("/", "/index.html"):
                return self._send(200, open(os.path.join(STATIC, "index.html"), "rb").read(), "text/html; charset=utf-8")
            if path == "/manifest.json": return self._send(200, json.dumps({"name": "JANSEVA AI", "short_name": "JANSEVA", "start_url": "/", "display": "standalone", "background_color": "#f6f8fc", "theme_color": "#0b2a6b", "icons": []}).encode(), "application/manifest+json")
            if path == "/sw.js": return self._send(200, b"const C='jansevaai-v4';self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.add('/')))});self.addEventListener('activate',e=>e.waitUntil(clients.claim()));self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.pathname.startsWith('/api/'))return;e.respondWith(fetch(e.request).then(r=>{const k=r.clone();caches.open(C).then(c=>c.put(e.request,k));return r}).catch(()=>caches.match(e.request).then(m=>m||caches.match('/'))))});", "application/javascript")
            if path == "/api/health": return self._json(200, {"ok": True, "version": "0.3", "time": now()})
            if path.startswith("/static/"):
                rel = os.path.normpath(path[len("/static/"):]).lstrip("/")
                f = os.path.join(STATIC, rel)
                if ".." not in rel and os.path.isfile(f):
                    ct = {"css": "text/css", "js": "application/javascript", "woff2": "font/woff2", "png": "image/png", "svg": "image/svg+xml"}.get(f.rsplit(".", 1)[-1], "application/octet-stream")
                    return self._send(200, open(f, "rb").read(), ct, {"Cache-Control": "public, max-age=86400"})
                return self._json(404, {"error": "not found"})
            if path.startswith("/uploads/"):
                f = os.path.join(UPLOADS, os.path.basename(path))
                if os.path.exists(f): return self._send(200, open(f, "rb").read(), "image/jpeg" if f.endswith("jpg") else "image/png")
                return self._json(404, {"error": "not found"})
            if path == "/api/platforms": return self._json(200, svc.db.platforms())
            if path == "/api/emergency": return self._json(200, {"number": "112", "note": "Call 112 for immediate danger. JANSEVA is a complaint tool, not an emergency dispatch service.", "source": "India national emergency number"})
            if path == "/api/public/feed": return self._json(200, public.feed(svc.db, q, int(q.get("limit", 50))))
            if path == "/api/public/stats": return self._json(200, public.stats(svc.db, q))
            if path == "/api/public/heatmap": return self._json(200, public.heatmap(svc.db, q))
            if path == "/api/public/report":
                m = q.get("month") or now()[:7]
                if q.get("format") == "csv": return self._send(200, public.monthly_report(svc.db, m, "csv").encode(), "text/csv", {"Content-Disposition": "attachment; filename=jansevaai-%s.csv" % m})
                return self._json(200, public.monthly_report(svc.db, m))
            if path == "/api/authorities": return self._json(200, svc.db.all("SELECT * FROM authorities WHERE verified=1"))
            if path == "/api/representatives": return self._json(200, svc.db.all("SELECT id,name,office,constituency,state,public_contact,profile_url,last_verified FROM representatives WHERE verified=1"))
            if path == "/api/assistant": return self._json(200, assistant.answer(q.get("q", ""), q.get("lang", "en")))
            u = self._user()
            if path == "/api/complaints":
                return self._json(200, svc.list_for(u["id"])) if u else self._json(401, {"error": "login"})
            if path.startswith("/api/complaints/"):
                parts = path.split("/"); cid = int(parts[3]); c = self._owned(u, cid)
                if not c: return self._json(404, {"error": "not found"})
                if len(parts) > 4 and parts[4] == "route": return self._json(200, svc.route(cid))
                if len(parts) > 4 and parts[4] == "letter":
                    us = svc.db.one("SELECT name FROM users WHERE id=?", (c["user_id"],)); return self._json(200, {"letter": accounts.letter(c, us["name"], [])})
                return self._json(200, svc.detail(cid))
            if path.startswith("/api/admin/"):
                a = self._adm()
                if not a: return self._json(403, {"error": "admin only"})
                p = path[len("/api/admin/"):]
                if p == "me": return self._json(200, {"role": a["role"], "scope_state": a.get("scope_state")})
                if p == "complaints" and roles.can(a["role"], "complaints.view"):
                    rows = [c for c in svc.db.all("SELECT id,code,category,status,state,city,severity,emergency,official_basis,needs_human,created_at FROM complaints ORDER BY id DESC LIMIT 500") if roles.in_scope(a, c)]
                    return self._json(200, rows)   # no citizen identity fields at all
                if p == "verification-queue" and (roles.can(a["role"], "verification.review") or a["role"] == "super_admin"):
                    return self._json(200, svc.db.all("SELECT id,code,category,confidence,needs_human,status,city FROM complaints WHERE needs_human=1 OR status='awaiting_citizen_confirmation' OR (confidence IS NOT NULL AND confidence<0.6)"))
                if p == "report" and roles.can(a["role"], "reports.view"):
                    m = q.get("month") or now()[:7]
                    return self._send(200, public.monthly_report(svc.db, m, "csv").encode(), "text/csv") if q.get("format") == "csv" else self._json(200, public.monthly_report(svc.db, m))
                if a["role"] != "super_admin": return self._json(403, {"error": "insufficient role"})
                if p == "control-center": return self._json(200, svc.control_center())
                if p == "analytics": return self._json(200, svc.analytics())
                if p == "escalations": return self._json(200, svc.escalations())
                if p == "escalation-policy": return self._json(200, svc.db.all("SELECT * FROM escalation_policy"))
                if p == "audit": return self._json(200, svc.db.all("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100"))
                if p == "integration-log": return self._json(200, svc.db.all("SELECT * FROM integration_log ORDER BY id DESC LIMIT 100"))
                if p == "notifications": return self._json(200, svc.db.all("SELECT * FROM notifications ORDER BY id DESC LIMIT 100"))
                if p == "admins": return self._json(200, svc.db.all("SELECT id,name,role,scope_state,scope_city,department FROM admin_users"))
                if p == "duplicates": return self._json(200, svc.db.all("SELECT g.id, g.category, g.parent_complaint_id, (SELECT count(*) FROM complaints c WHERE c.duplicate_group=g.id) members FROM duplicate_groups g"))
                if p == "health": return self._json(200, {"db": "ok", "integrations": svc.control_center()["modes"]})
            self._json(404, {"error": "not found"})
        def do_POST(self):
            if self._limited(): return self._json(429, {"error": "rate limit"})
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/upload":
                if not self._user(): return self._json(401, {"error": "login"})
                data = self._raw()
                if len(data) > MAX_UPLOAD: return self._json(413, {"error": "file too large (max 5 MB)"})
                kind = next((v for k, v in MAGIC.items() if data.startswith(k)), None)
                if not kind: return self._json(415, {"error": "only real JPEG or PNG images are accepted"})
                name = hashlib.sha256(data).hexdigest()[:32] + "." + kind[0]
                open(os.path.join(UPLOADS, name), "wb").write(data)
                return self._json(200, {"url": "/uploads/" + name, "note": "No malware scan or EXIF check in this build"})
            d = self._body()
            if path == "/api/otp/request": return self._json(200, accounts.otp_request(svc.db, d.get("phone", ""), dev_otp)) if len(d.get("phone", "")) >= 10 else self._json(422, {"error": "valid phone required"})
            if path == "/api/otp/verify":
                u = accounts.otp_verify(svc, d.get("phone", ""), d.get("code", ""), d.get("name", ""))
                return self._json(200, {"token": u["token"], "name": u["name"]}) if u else self._json(401, {"error": "invalid or expired code"})
            if path == "/api/register":
                if require_otp: return self._json(403, {"error": "OTP login required"})
                if not d.get("phone") or len(d["phone"]) < 10: return self._json(422, {"error": "valid phone required"})
                u = svc.register(d["phone"], d.get("name", "")); return self._json(200, {"token": u["token"], "name": u["name"]})
            if path == "/api/assistant": return self._json(200, assistant.answer(d.get("q", ""), d.get("lang", "en")))
            if path.startswith("/api/admin/"):
                a = self._adm()
                if not a: return self._json(403, {"error": "admin only"})
                p = path[len("/api/admin/"):]
                if p.startswith("complaints/") and p.endswith("/approve-photo") and roles.can(a["role"], "photos.approve"):
                    cid = int(p.split("/")[1]); svc.db.run("UPDATE complaints SET photo_public_ok=? WHERE id=?", (int(bool(d.get("ok"))), cid))
                    svc.db.audit("admin:%s" % a["name"], "photo_public", "%s %s (faces/plates must be checked manually: auto-blur not implemented)" % (cid, d.get("ok"))); return self._json(200, {"ok": True})
                if p.startswith("complaints/") and p.endswith("/reroute") and roles.can(a["role"], "complaints.reroute"):
                    cid = int(p.split("/")[1]); c = svc.get(cid)
                    if not c or not roles.in_scope(a, c): return self._json(404, {"error": "not found"})
                    upd = {k: d[k] for k in ("category", "asset_owner", "city", "state") if d.get(k)}
                    for k, v in upd.items(): svc.db.run("UPDATE complaints SET %s=?,needs_human=0 WHERE id=?" % k, (v.lower() if k in ("city", "state") else v, cid))
                    svc.db.audit("admin:%s" % a["name"], "reroute", "%s %s" % (cid, upd)); svc.db.timeline(cid, "admin", "rerouted", "Routing data corrected by %s" % a["role"]); return self._json(200, {"ok": True, "routing": svc.route(cid)})
                if p == "authorities" and roles.can(a["role"], "authorities.edit"):
                    if a["role"] == "state_admin" and (d.get("state") or "").lower() != (a.get("scope_state") or "").lower(): return self._json(403, {"error": "outside your state"})
                    if d.get("verified") and not d.get("source_url"): return self._json(422, {"error": "a verified entry needs an official source_url"})
                    i = svc.db.run("INSERT INTO authorities(name,type,state,district,city,categories,grievance_url,grievance_email,helpline,verified,last_verified,source_url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                   (d.get("name"), d.get("type"), d.get("state"), d.get("district"), d.get("city"), d.get("categories"), d.get("grievance_url"), d.get("grievance_email"), d.get("helpline"), int(bool(d.get("verified"))), now()[:10] if d.get("verified") else None, d.get("source_url")))
                    svc.db.audit("admin:%s" % a["name"], "authority_added", str(i)); return self._json(200, {"ok": True, "id": i})
                if a["role"] != "super_admin": return self._json(403, {"error": "insufficient role"})
                if p == "platforms": return self._json(200, svc.add_platform(d, "admin"))
                if p == "sync": return self._json(200, svc.sync())
                if p == "run-escalation": return self._json(200, svc.run_escalation())
                if p == "admins":
                    if d.get("role") not in roles.ROLES: return self._json(422, {"error": "unknown role"})
                    return self._json(200, {"token": accounts.create_admin(svc.db, d.get("name", ""), d["role"], d.get("scope_state"), d.get("scope_city"), d.get("department")), "note": "shown once"})
                if p == "representatives":
                    if d.get("verified") and not d.get("source_url"): return self._json(422, {"error": "a verified entry needs an official source_url"})
                    i = svc.db.run("INSERT INTO representatives(name,office,constituency,state,city,public_contact,profile_url,verified,last_verified,source_url) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                   (d.get("name"), d.get("office"), d.get("constituency"), d.get("state"), d.get("city"), d.get("public_contact"), d.get("profile_url"), int(bool(d.get("verified"))), now()[:10] if d.get("verified") else None, d.get("source_url")))
                    return self._json(200, {"ok": True, "id": i})
                if p == "escalation-policy":
                    svc.db.run("UPDATE escalation_policy SET name=?,description=?,after_days_factor=? WHERE level=?", (d.get("name"), d.get("description"), d.get("after_days_factor", 1.0), d.get("level"))); return self._json(200, {"ok": True})
            u = self._user()
            if not u: return self._json(401, {"error": "login"})
            if path == "/api/account/delete": accounts.delete_account(svc.db, u["id"]); return self._json(200, {"ok": True})
            if path == "/api/complaints": return self._json(200, svc.create_complaint(u, d))
            if path.startswith("/api/complaints/"):
                parts = path.split("/"); cid = int(parts[3]); act = parts[4] if len(parts) > 4 else ""
                c = svc.get(cid)
                if act == "support":   # community: any logged-in citizen may support / report still-exists
                    if not c: return self._json(404, {"error": "not found"})
                    svc.db.run("INSERT OR IGNORE INTO supports(complaint_id,user_id,kind,ts) VALUES(?,?,?,?)", (cid, u["id"], d.get("kind", "support") if d.get("kind") in ("support", "still_exists") else "support", now())); return self._json(200, {"ok": True})
                if not self._owned(u, cid) or (c and c["user_id"] != u["id"]): return self._json(404, {"error": "not found"})
                if act == "submit":
                    svc.db.run("UPDATE complaints SET consent_submit=?,consent_share_personal=?,notify_representative=? WHERE id=?",
                               (int(bool(d.get("consent_submit"))), int(bool(d.get("consent_share_personal"))), int(bool(d.get("notify_representative"))), cid))
                    svc.db.audit("user:%s" % u["id"], "consent", "submit=%s share_personal=%s rep=%s v1" % (d.get("consent_submit"), d.get("consent_share_personal"), d.get("notify_representative")))
                    return self._json(200, svc.submit(cid))
                if act == "confirm": return self._json(200, svc.confirm_category(cid, d.get("category"), u["id"]))
                if act == "reference": return self._json(200, svc.record_reference(cid, d.get("platform_id"), d.get("ref", "").strip(), u["id"]))
                if act == "sync": return self._json(200, svc.sync(cid))
                if act == "verify": svc.citizen_verify(cid, bool(d.get("ok")), u["id"], d.get("after_photo"), d.get("note", "")); return self._json(200, {"ok": True})
            self._json(404, {"error": "not found"})
    return H

def main():
    port = int(os.environ.get("PORT", "8080"))
    mock = None; base = os.environ.get("SWACHHATA_SANDBOX_URL")
    if not base and os.environ.get("SWACHHATA_LIVE") != "1":
        mock = MockSwachhata(); base = mock.url
    svc = Service(sandbox_base=base)
    if os.environ.get("JANSEVA_SEED_DEMO") == "1":
        from .seed import seed
        seed(svc)
    print("JANSEVA AI on :%d  admin token: %s  swachhata mode: %s" % (port, ADMIN_TOKEN, svc.connectors()["swachhata"].mode()), flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), make_handler(svc, ADMIN_TOKEN)).serve_forever()

if __name__ == "__main__":
    main()
