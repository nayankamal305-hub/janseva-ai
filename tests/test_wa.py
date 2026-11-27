import hashlib, hmac, json, os, subprocess, sys, time, unittest, urllib.request as u, urllib.error
class WA(unittest.TestCase):
    def test_flow(self):
        db = "/tmp/wa_t.db"
        if os.path.exists(db): os.remove(db)
        env = dict(os.environ, PORT="8095", JANSEVA_DB=db, WA_NUMBER="919999900000", WA_VERIFY_TOKEN="vt", WA_APP_SECRET="sec", JANSEVA_ADMIN_TOKEN="a")
        p = subprocess.Popen([sys.executable, "-m", "app.server"], env=env, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(2)
        def call(m, path, d=None, hdr=None, raw=None):
            body = raw if raw is not None else (json.dumps(d).encode() if d is not None else None)
            r = u.Request("http://localhost:8095" + path, method=m, data=body, headers=hdr or {})
            try: return json.loads(u.urlopen(r).read() or b"{}")
            except urllib.error.HTTPError as e: return {"http": e.code}
        try:
            s = call("POST", "/api/wa/start", {}); self.assertIn("wa.me/919999900000", s["link"])
            self.assertEqual(call("GET", "/api/wa/poll?id=%s&poll=%s" % (s["id"], s["poll"]))["status"], "waiting")
            payload = json.dumps({"entry": [{"changes": [{"value": {"messages": [{"type": "text", "from": "919876543210", "text": {"body": "JANSEVA LOGIN " + s["code"]}}]}}]}]}).encode()
            self.assertEqual(call("POST", "/api/wa/webhook", raw=payload, hdr={"X-Hub-Signature-256": "sha256=bad"}).get("http"), 403)
            self.assertEqual(call("GET", "/api/wa/poll?id=%s&poll=%s" % (s["id"], s["poll"]))["status"], "waiting")
            sig = "sha256=" + hmac.new(b"sec", payload, hashlib.sha256).hexdigest()
            self.assertTrue(call("POST", "/api/wa/webhook", raw=payload, hdr={"X-Hub-Signature-256": sig})["ok"])
            self.assertEqual(call("GET", "/api/wa/poll?id=%s&poll=wrong" % s["id"])["status"], "invalid")
            r = call("GET", "/api/wa/poll?id=%s&poll=%s" % (s["id"], s["poll"])); self.assertEqual(r["status"], "ok"); self.assertTrue(r["token"])
            self.assertEqual(call("GET", "/api/wa/poll?id=%s&poll=%s" % (s["id"], s["poll"]))["status"], "used")
        finally: p.kill()
if __name__ == "__main__": unittest.main()
