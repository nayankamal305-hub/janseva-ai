import json, os, secrets, sys, time, hashlib, urllib.parse
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .service import Service
from .connectors.mock_gov import MockSwachhata
from . import accounts, public, assistant, roles, storage, density
from .db import ROOT, now

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
UPLOADS = os.environ.get("JANSEVA_UPLOADS", os.path.join(ROOT, "uploads"))
ADMIN_TOKEN = os.environ.get("JANSEVA_ADMIN_TOKEN") or secrets.token_urlsafe(16)
MAX_UPLOAD = 5 * 1024 * 1024
MAGIC = {b"\xff\xd8\xff": ("jpg", "image/jpeg"), b"\x89PNG": ("png", "image/png")}

_GZ = {}
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
        def _ip(self):
            xff = self.headers.get("X-Forwarded-For", "")
            if xff: return xff.split(",")[0].strip()
            return self.client_address[0]
        def _tok(self): return (self.headers.get("Authorization") or "").replace("Bearer ", "").strip()
        def _user(self): return svc.user_by_token(self._tok())
        def _adm(self): return accounts.admin_by_token(svc.db, self._tok(), admin_token)
        def _limited(self):
            k = self._tok() or self._ip(); q = hits[k]; t = time.time()
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
            if path == "/sw.js": return self._send(200, "const C='jansevaai-v31';\nself.addEventListener('install',e=>{self.skipWaiting()});\nself.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>clients.claim())));\nself.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==location.origin||u.pathname.startsWith('/api/')||u.pathname==='/sw.js')return;\ne.respondWith(fetch(e.request).then(r=>{if(r&&r.ok&&r.status===200){const k=r.clone();caches.open(C).then(c=>c.put(e.request,k)).catch(()=>{});return r}\nreturn caches.match(e.request).then(m=>m||r)}).catch(()=>caches.match(e.request).then(m=>m||caches.match('/'))))});".encode(), "application/javascript")
            if path == "/api/health": return self._json(200, {"ok": True, "version": "0.3", "time": now(), "db": "postgres" if getattr(svc.db, "pg", False) else "sqlite", "photo_storage": storage.from_env(os.environ, UPLOADS).kind})
            if path.startswith("/static/"):
                rel = os.path.normpath(path[len("/static/"):]).lstrip("/")
                f = os.path.join(STATIC, rel)
                if ".." not in rel and os.path.isfile(f):
                    ct = {"css": "text/css", "js": "application/javascript", "woff2": "font/woff2", "geojson": "application/geo+json", "json": "application/json", "png": "image/png", "svg": "image/svg+xml"}.get(f.rsplit(".", 1)[-1], "application/octet-stream")
                    raw = open(f, "rb").read(); hd = {"Cache-Control": "public, max-age=86400"}
                    if f.endswith(".geojson") and "gzip" in (self.headers.get("Accept-Encoding") or ""):
                        import gzip; raw = _GZ.get(f) or _GZ.setdefault(f, gzip.compress(raw, 6)); hd["Content-Encoding"] = "gzip"
                    return self._send(200, raw, ct, hd)
                return self._json(404, {"error": "not found"})
            if path.startswith("/uploads/"):
                try: got = storage.from_env(os.environ, UPLOADS).get(os.path.basename(path))
                except Exception: return self._json(502, {"error": "photo storage unavailable"})
                if got: return self._send(200, got[0], got[1], {"Cache-Control": "public, max-age=86400"})
                return self._json(404, {"error": "not found"})
            if path == "/api/platforms": return self._json(200, svc.db.platforms())
            if path == "/api/emergency": return self._json(200, {"number": "112", "note": "Call 112 for immediate danger. JANSEVA is a complaint tool, not an emergency dispatch service.", "source": "India national emergency number"})
            if path == "/api/wa/webhook":
                from . import walogin
                ch = walogin.verify_challenge(os.environ, q) if walogin.enabled(os.environ) else None
                return self._send(200, ch.encode(), "text/plain") if ch is not None else self._json(403, {"error": "forbidden"})
            if path == "/api/wa/poll":
                from . import walogin
                return self._json(200, walogin.poll(svc, q.get("id", ""), q.get("poll", ""))) if walogin.enabled(os.environ) else self._json(503, {"error": "WhatsApp login not configured"})
            if path == "/api/config": 
                from . import walogin, mailer
                return self._json(200, {"whatsapp_login": walogin.enabled(os.environ), "email_login": mailer.configured() or dev_otp})
            if path == "/api/directory/nodal":
                from .service import load_data
                k = q.get("scope", "state"); rows = load_data("authorities_central_nodal.json" if k == "central" else "authorities_state_nodal.json")
                t = q.get("q", "").lower(); items = [r for r in rows if t in r["name"].lower()]; return self._json(200, {"count": len(items), "items": items, "source": "https://pgportal.gov.in/Home/NodalPgOfficers", "note": "Official nodal public grievance officers. Whether an email accepts citizen complaints is unverified."})
            if path in ("/api/directory/search", "/api/directory/districts", "/api/directory/states"):
                from .service import load_data
                st = q.get("state", "").lower(); t = q.get("q", "").lower(); cat = q.get("category", "")
                if path.endswith("states"): rows = [r for r in load_data("igod_state_ut.json") if r["type"] == "SPORT"]
                elif path.endswith("districts"): rows = [r for r in load_data("igod_districts.json") if not st or st in (r["state"] or "").lower()]
                else:
                    src = {"union": "igod_union.json", "legislature": "igod_legislature.json", "apex": "igod_apex.json"}.get(q.get("scope", "state"), "igod_state_ut.json")
                    rows = [r for r in load_data(src) if (not st or st in (r["state"] or "").lower()) and (not cat or cat in r["categories_heuristic"])]
                if t: rows = [r for r in rows if t in r["title"].lower()]
                return self._json(200, {"count": len(rows), "items": rows[:int(q.get("limit", 100))], "source": "https://www.india.gov.in/directory/web-directory", "note": "IGOD (National Portal of India) listing. Websites only; no emails or phones are invented. 'categories_heuristic' is keyword-based, not official."})
            if path == "/api/directory/for":
                from .service import load_data
                st = q.get("state", "").lower(); city = q.get("city", "").lower(); cat = q.get("category", "")
                cm = {"garbage": "municipal", "drainage": "municipal", "toilet": "municipal", "road": "pwd_roads", "water": "water_board", "electricity": "electricity_discom", "police": "police"}.get(cat, cat)
                S = [r for r in load_data("igod_state_ut.json") if st and st in (r["state"] or "").lower()]
                dist = [r for r in load_data("igod_districts.json") if st and st in (r["state"] or "").lower() and city and (city in r["title"].lower() or r["title"].lower() in city)]
                nod = [r for r in load_data("authorities_state_nodal.json") if st and st in r["name"].lower()]
                return self._json(200, {"state_portal": next((r for r in S if r["type"] == "SPORT"), None), "district_site": dist[:2], "state_nodal_grievance_officer": nod[:1],
                                         "bodies": [r for r in S if cm and cm in r["categories_heuristic"] and r["type"] != "SPORT"][:15], "note": "Guided links from official directories. Category match is a keyword guess; nothing is auto-submitted."})
            if path == "/api/directory/utility-contacts":
                from .service import load_data
                st = q.get("state", "").lower(); cat = q.get("category", "")
                rows = [r for r in load_data("utility_contacts.json") if (not st or st in (r["state"] or "").lower()) and (not cat or cat in r["categories_heuristic"]) and (q.get("with_email") != "1" or r["emails_published_on_official_page"])]
                return self._json(200, {"count": len(rows), "items": rows[:100], "note": "Emails are only those the body publishes on its own official site (page named in found_on). Whether they accept citizen complaints is unverified."})
            if path == "/api/rating/search":
                from . import rating
                return self._json(200, {"items": rating.search(svc.db, q.get("q", ""), q.get("type", ""), q.get("state", ""), q.get("sort", "rating"))})
            if path == "/api/rating/entity":
                from . import rating
                uu = self._user(); d = rating.detail(svc.db, q.get("key", ""), uu["id"] if uu else None)
                return self._json(200, d) if d else self._json(404, {"error": "not found"})
            if path == "/api/admin/rating-queue":
                from . import rating
                a = self._adm()
                return self._json(200, {"items": rating.moderation_queue(svc.db)}) if a and roles.can(a["role"], "photos.approve") else self._json(403, {"error": "moderator only"})
            if path == "/api/directory/handles":
                st = (q.get("state") or "").lower(); t = (q.get("q") or "").lower()
                rows = [h for h in load_data("state_handle_sites.json") if (not st or (h["state"] or "").lower() == st) and (not t or t in h["title"].lower() or t in h["handle"].lower())]
                return self._json(200, {"count": len(rows), "items": rows[:200], "note": "Each handle is linked from the listed official site. Blue tick and follower count are not checked."})
            if path == "/api/coverage": return self._json(200, {"items": load_data("coverage.json"), "note": "reach% = official sites our crawler could open; low reach means unknown, not absent."})
            if path == "/api/directory/constituencies":
                st = (q.get("state") or "").lower()
                return self._json(200, {"items": sorted({m["constituency"] for m in load_data("representatives_parliament.json") if m["house"] == "Lok Sabha" and m.get("constituency") and (not st or st in (m["state"] or "").lower())})})
            if path == "/api/companies": return self._json(200, {"items": load_data("companies.json")})
            if path == "/api/directory/mps":
                from .service import load_data
                t = q.get("q", "").lower(); st = q.get("state", "").lower()
                rows = [r for r in load_data("representatives_parliament.json") if (not t or t in r["name"].lower() or t in (r.get("constituency") or "").lower()) and (not st or st in (r.get("state") or "").lower())]
                return self._json(200, {"count": len(rows), "items": rows[:200], "source": "https://sansad.in"})
            if path == "/api/public/feed": return self._json(200, public.feed(svc.db, q, int(q.get("limit", 50))))
            if path == "/api/public/similar":
                try: la, lo = float(q.get("lat")), float(q.get("lon"))
                except Exception: return self._json(400, {"error": "lat/lon needed"})
                import math
                out = []
                for r in svc.db.all("SELECT id,code,category,title,city,status,lat,lon,created_at FROM complaints WHERE status NOT IN ('citizen_verified_resolved','closed','rejected') AND lat IS NOT NULL ORDER BY id DESC LIMIT 600"):
                    dy = (r["lat"] - la) * 111320; dx = (r["lon"] - lo) * 111320 * math.cos(math.radians(la)); dist = math.hypot(dx, dy)
                    if dist <= 250 and (not q.get("category") or r["category"] == q["category"] or not r["category"]):
                        out.append({"id": r["id"], "code": r["code"], "category": r["category"], "title": (r["title"] or "")[:80], "status": r["status"], "distance_m": int(dist), "reported": r["created_at"][:10]})
                out.sort(key=lambda x: x["distance_m"]); return self._json(200, {"items": out[:5]})
            if path == "/api/public/overview":
                from . import rating
                from collections import Counter
                es = rating.entities(); c = Counter(e["type"].split(" (")[0].split(" /")[0] for e in es)
                mst = sorted({e["state"] for e in es if e["type"] == "MLA"})
                st = public.stats(svc.db, q)
                return self._json(200, {"stats": st, "directory": dict(c), "mla_states": mst, "languages": 17, "note": "Counts come from this server's database and official lists. Sandbox build: not government data."})
            if path == "/api/public/stats": return self._json(200, public.stats(svc.db, q))
            if path == "/api/public/density": return self._json(200, density.density(svc.db, q))
            if path == "/api/public/heatmap": return self._json(200, public.heatmap(svc.db, q))
            if path == "/api/public/report":
                m = q.get("month") or now()[:7]
                if q.get("format") == "csv": return self._send(200, public.monthly_report(svc.db, m, "csv").encode(), "text/csv", {"Content-Disposition": "attachment; filename=jansevaai-%s.csv" % m})
                return self._json(200, public.monthly_report(svc.db, m))
            if path == "/api/authorities": return self._json(200, svc.db.all("SELECT * FROM authorities WHERE verified=1"))
            if path == "/api/representatives": return self._json(200, svc.db.all("SELECT id,name,office,constituency,state,public_contact,profile_url,last_verified FROM representatives WHERE verified=1"))
            if path == "/api/admin/inbound-poll":
                a = self._adm()
                return self._json(200, svc.ingest_replies()) if a and a["role"] == "super_admin" else self._json(403, {"error": "super admin only"})
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
                dd = svc.detail(cid)
                dd["dispatches"] = svc.db.all("SELECT level,kind,target_name,source_url,status,sent_at,due_at FROM dispatches WHERE complaint_id=? ORDER BY level,id", (cid,))
                dd["x_queue"] = svc.db.one("SELECT status,tweet_url,posted_at FROM x_queue WHERE complaint_id=?", (cid,))
                return self._json(200, dd)
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
            if path.startswith("/api/rating/") or path.startswith("/api/admin/rating-"):
                from . import rating
                d = self._body() if hasattr(self, "_body") else {}
                if path.startswith("/api/admin/rating-"):
                    a = self._adm()
                    if not (a and roles.can(a["role"], "photos.approve")): return self._json(403, {"error": "moderator only"})
                    return self._json(200, rating.moderate(svc.db, int(d.get("id", 0)), d.get("action", "")))
                uu = self._user()
                if not uu: return self._json(401, {"error": "login"})
                if path == "/api/rating/rate": return self._json(200, rating.rate(svc.db, uu["id"], d.get("key", ""), d.get("stars"), d.get("comment", "")))
                if path == "/api/rating/like": return self._json(200, rating.like(svc.db, uu["id"], int(d.get("id", 0))))
                if path == "/api/rating/report": return self._json(200, rating.report(svc.db, uu["id"], int(d.get("id", 0)), d.get("reason", "")))
            if path == "/api/admin/dispatch-run":
                a = self._adm()
                from . import dispatch
                return self._json(200, dispatch.tick(svc)) if a and a["role"] == "super_admin" else self._json(403, {"error": "super admin only"})
            if path.startswith("/api/poster/x/"):
                from . import social
                tok = os.environ.get("X_POSTER_TOKEN", "")
                if not tok or self.headers.get("Authorization", "") != "Bearer " + tok: return self._json(403, {"error": "poster token required"})
                if path.endswith("/pending"): return self._json(200, social.next_pending(svc))
                d = self._body()
                if path.endswith("/posted"): return self._json(200, social.mark(svc, int(d.get("id", 0)), True, d.get("url", "")))
                if path.endswith("/failed"): return self._json(200, social.mark(svc, int(d.get("id", 0)), False, error=d.get("error", "")))
            if path == "/api/upload":
                if not self._user(): return self._json(401, {"error": "login"})
                data = self._raw()
                if len(data) > MAX_UPLOAD: return self._json(413, {"error": "file too large (max 5 MB)"})
                kind = next((v for k, v in MAGIC.items() if data.startswith(k)), None)
                if not kind: return self._json(415, {"error": "only real JPEG or PNG images are accepted"})
                name = hashlib.sha256(data).hexdigest()[:32] + "." + kind[0]
                try: storage.from_env(os.environ, UPLOADS).put(name, data, "image/jpeg" if kind[0] == "jpg" else "image/png")
                except Exception: return self._json(502, {"error": "photo storage unavailable, try again"})
                return self._json(200, {"url": "/uploads/" + name, "note": "No malware scan or EXIF check in this build"})
            if path == "/api/wa/webhook":
                from . import walogin
                raw = self._raw()
                if not walogin.enabled(os.environ) or not walogin.signature_ok(os.environ, raw, self.headers.get("X-Hub-Signature-256")): return self._json(403, {"error": "bad signature"})
                try: walogin.handle_webhook(svc.db, json.loads(raw or b"{}"))
                except Exception: pass
                return self._json(200, {"ok": True})
            if path == "/api/wa/start":
                from . import walogin
                return self._json(200, walogin.start(svc.db, os.environ)) if walogin.enabled(os.environ) else self._json(503, {"error": "WhatsApp login not configured"})
            d = self._body()
            if path == "/api/auth/login":
                ident = accounts.norm_ident(d.get("email") or d.get("phone"))
                u, st = accounts.password_login(svc, ident, d.get("password", ""), self._ip())
                if u: return self._json(200, {"token": u["token"], "name": u["name"]})
                return self._json(429 if st == "locked" else 401, {"error": "Too many wrong attempts. Try again in 15 minutes or reset your password." if st == "locked" else "Wrong email/phone or password. New here, or forgot it? Use the OTP option."})
            if path in ("/api/auth/signup", "/api/auth/reset"):
                ident = accounts.norm_ident(d.get("email") or d.get("phone"))
                if not ident: return self._json(422, {"error": "valid email or 10-digit phone required"})
                u, err = accounts.password_signup_or_reset(svc, ident, d.get("code", ""), d.get("password", ""), d.get("name", ""), path.endswith("reset"))
                return self._json(200, {"token": u["token"], "name": u["name"]}) if u else self._json(401 if "code" in err else 422, {"error": err})
            if path == "/api/otp/request":
                ident = accounts.norm_ident(d.get("phone") or d.get("email")); 
                return self._json(200, accounts.otp_request(svc.db, ident, dev_otp)) if ident else self._json(422, {"error": "valid email or 10-digit phone required"})
            if path == "/api/otp/verify":
                u = accounts.otp_verify(svc, accounts.norm_ident(d.get("phone") or d.get("email")) or "", d.get("code", ""), d.get("name", ""))
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
                    svc.db.run("UPDATE complaints SET consent_email=?,reply_to_user=?,constituency=?,company=?,consent_x=%d WHERE id=?" % int(bool(d.get("consent_x"))), (int(bool(d.get("consent_email"))), int(bool(d.get("reply_to_user"))), (d.get("constituency") or None), (d.get("company") or None), cid))
                    svc.db.audit("user:%s" % u["id"], "consent", "submit=%s share_personal=%s rep=%s email_authorities=%s v2" % (d.get("consent_submit"), d.get("consent_share_personal"), d.get("notify_representative"), d.get("consent_email")))
                    res = svc.submit(cid)
                    if d.get("consent_x"):
                        from . import social
                        res["x_queue"] = social.enqueue(svc, cid)
                    if d.get("consent_email"):
                        from . import dispatch
                        try: res["email_dispatch"] = dispatch.plan(svc, cid); res["email_dispatch"]["send"] = dispatch.send_due(svc, cid)
                        except Exception as ex: res["email_dispatch"] = {"ok": False, "error": type(ex).__name__}
                    return self._json(200, res)
                if act == "dispatches": return self._json(200, {"items": svc.db.all("SELECT level,kind,target_name,target_email,source_url,source_date,tier,status,due_at,sent_at FROM dispatches WHERE complaint_id=? ORDER BY level,id", (cid,))})
                if act == "x-status": return self._json(200, {"item": svc.db.one("SELECT status,tweet_url,text,posted_at FROM x_queue WHERE complaint_id=?", (cid,))})
                if act == "tweet-draft":
                    from . import social
                    return self._json(200, social.draft(svc, cid))
                if act == "confirm": return self._json(200, svc.confirm_category(cid, d.get("category"), u["id"]))
                if act == "reference": return self._json(200, svc.record_reference(cid, d.get("platform_id"), d.get("ref", "").strip(), u["id"]))
                if act == "email-authority": return self._json(200, svc.email_authority(cid, d.get("email", ""), d.get("authority", ""), u))
                if act == "portal-status": return self._json(200, svc.portal_status(cid, d.get("platform_id"), d.get("status", ""), d.get("note", ""), u["id"]))
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
    if os.environ.get("JANSEVA_AUTO_DISPATCH", "1") == "1":
        import threading, time
        from . import dispatch
        def loop():
            while True:
                time.sleep(3600)
                try: dispatch.tick(svc)
                except Exception: pass
        threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", port), make_handler(svc, ADMIN_TOKEN)).serve_forever()

if __name__ == "__main__":
    main()
