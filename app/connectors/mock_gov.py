"""Mock Swachhata server implementing the documented contract. access_key controls failure modes:
demo123 ok | expired403 | bad401 | slow (timeout) | fail500 | noack (201 without id) | dup (409)."""
import json, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class MockSwachhata:
    def __init__(self):
        self.complaints = {}; self.n = 28597596; self.lock = threading.Lock()
        outer = self
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def _send(self, code, obj):
                b = json.dumps(obj).encode(); self.send_response(code)
                self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
                self.end_headers(); self.wfile.write(b)
            def _q(self): return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
            def _auth(self, q):
                k = q.get("access_key")
                if k == "expired403": self._send(403, {"httpCode": 403, "message": "access key expired"}); return False
                if k not in ("demo123", "slow", "fail500", "noack", "dup"): self._send(401, {"httpCode": 401, "message": "invalid credentials"}); return False
                return True
            def do_POST(self):
                q = self._q()
                if not self.path.startswith("/sbm/v1/post-complaint"): return self._send(404, {})
                if not self._auth(q): return
                k = q["access_key"]
                if k == "slow": time.sleep(5)
                if k == "fail500": return self._send(500, {"message": "server error"})
                if k == "dup": return self._send(409, {"message": "duplicate complaint"})
                if k == "noack": return self._send(201, {"httpCode": 201, "message": "Complaint saved successfully"})
                for need in ("mobileNumber", "categoryId", "complaintLatitude", "complaintLongitude", "fullName", "deviceOs", "file"):
                    if need not in q: return self._send(422, {"message": "missing " + need})
                with outer.lock:
                    outer.n += 1; gid = "W03000C%d" % outer.n
                    outer.complaints[outer.n] = {"complaint_id": outer.n, "generic_id": gid, "status": 1, "categoryId": q["categoryId"], "comment": ""}
                self._send(201, {"httpCode": 201, "code": 2001, "message": "Complaint saved successfully", "complaint": {"generic_id": gid}})
            def do_GET(self):
                q = self._q()
                if not self.path.startswith("/sbm/v1/getComplaints"): return self._send(404, {})
                if not self._auth(q): return
                items = [v for v in outer.complaints.values() if str(v["complaint_id"]) == q.get("complaintId", str(v["complaint_id"]))]
                self._send(200, {"httpCode": 200, "complaints": items})
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
    def set_status(self, complaint_id, status, comment=""):
        with self.lock:
            self.complaints[complaint_id]["status"] = status; self.complaints[complaint_id]["comment"] = comment
    def stop(self): self.srv.shutdown()
