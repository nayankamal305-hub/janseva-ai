import json, os, secrets, sys, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .service import Service
from .connectors.mock_gov import MockSwachhata

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
ADMIN_TOKEN = os.environ.get("JANSEVA_ADMIN_TOKEN") or secrets.token_urlsafe(16)

def make_handler(svc, admin_token):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _json(self, code, obj):
            b = json.dumps(obj, default=str).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            try: return json.loads(self.rfile.read(n) or b"{}")
            except Exception: return {}
        def _tok(self): return (self.headers.get("Authorization") or "").replace("Bearer ", "").strip()
        def _user(self): return svc.user_by_token(self._tok())
        def _admin(self): return self._tok() == admin_token
        def _owned(self, user, cid):
            c = svc.get(cid); return c if c and (user and c["user_id"] == user["id"] or self._admin()) else None
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path in ("/", "/index.html"):
                b = open(os.path.join(STATIC, "index.html"), "rb").read()
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); return self.wfile.write(b)
            if path == "/api/health": return self._json(200, {"ok": True})
            if path == "/api/platforms": return self._json(200, svc.db.platforms())
            u = self._user()
            if path == "/api/complaints":
                return self._json(200, svc.list_for(u["id"])) if u else self._json(401, {"error": "login"})
            if path.startswith("/api/complaints/"):
                parts = path.split("/"); cid = int(parts[3]); c = self._owned(u, cid)
                if not c: return self._json(404, {"error": "not found"})
                if len(parts) > 4 and parts[4] == "route": return self._json(200, svc.route(cid))
                return self._json(200, svc.detail(cid))
            if path.startswith("/api/admin/"):
                if not self._admin(): return self._json(403, {"error": "admin only"})
                if path.endswith("control-center"): return self._json(200, svc.control_center())
                if path.endswith("analytics"): return self._json(200, svc.analytics())
                if path.endswith("escalations"): return self._json(200, svc.escalations())
                if path.endswith("audit"): return self._json(200, svc.db.all("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100"))
                if path.endswith("integration-log"): return self._json(200, svc.db.all("SELECT * FROM integration_log ORDER BY id DESC LIMIT 100"))
            self._json(404, {"error": "not found"})
        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path; d = self._body()
            if path == "/api/register":
                if not d.get("phone") or len(d["phone"]) < 10: return self._json(422, {"error": "valid phone required"})
                u = svc.register(d["phone"], d.get("name", "")); return self._json(200, {"token": u["token"], "name": u["name"]})
            if path.startswith("/api/admin/"):
                if not self._admin(): return self._json(403, {"error": "admin only"})
                if path.endswith("platforms"): return self._json(200, svc.add_platform(d, "admin"))
                if path.endswith("sync"): return self._json(200, svc.sync())
                if path.endswith("run-escalation"): return self._json(200, svc.run_escalation())
            u = self._user()
            if not u: return self._json(401, {"error": "login"})
            if path == "/api/complaints": return self._json(200, svc.create_complaint(u, d))
            if path.startswith("/api/complaints/"):
                parts = path.split("/"); cid = int(parts[3]); act = parts[4] if len(parts) > 4 else ""
                if not self._owned(u, cid): return self._json(404, {"error": "not found"})
                if act == "submit":
                    svc.db.run("UPDATE complaints SET consent_submit=?,consent_share_personal=?,notify_representative=? WHERE id=?",
                               (int(bool(d.get("consent_submit"))), int(bool(d.get("consent_share_personal"))), int(bool(d.get("notify_representative"))), cid))
                    return self._json(200, svc.submit(cid))
                if act == "reference": return self._json(200, svc.record_reference(cid, d.get("platform_id"), d.get("ref", "").strip(), u["id"]))
                if act == "sync": return self._json(200, svc.sync(cid))
                if act == "verify": svc.citizen_verify(cid, bool(d.get("ok")), u["id"]); return self._json(200, {"ok": True})
            self._json(404, {"error": "not found"})
    return H

def main():
    port = int(os.environ.get("PORT", "8080"))
    mock = None; base = os.environ.get("SWACHHATA_SANDBOX_URL")
    if not base and os.environ.get("SWACHHATA_LIVE") != "1":
        mock = MockSwachhata(); base = mock.url
    svc = Service(sandbox_base=base)
    print("JANSEVA AI on :%d  admin token: %s  swachhata mode: %s" % (port, ADMIN_TOKEN, svc.connectors()["swachhata"].mode()), flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), make_handler(svc, ADMIN_TOKEN)).serve_forever()

if __name__ == "__main__":
    main()
