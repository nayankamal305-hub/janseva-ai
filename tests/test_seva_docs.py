from app.db import guard_test_database_url as _g; _g()
# Phase 4 (Seva Setu India): private document vault - upload, ownership, access logs, attach, honest status.
import os, sys, json, tempfile, unittest, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer
from app.db import DB
from app.service import Service
from app.server import make_handler
from app import sevdoc, seva

PDF = b"%PDF-1.4 minimal test payload " + b"x" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"y" * 64
TXT = b"this is not a real document"

class Docs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.uploads = os.path.join(cls.dir, "up")
        os.environ["JANSEVA_UPLOADS"] = cls.uploads
        cls.svc = Service(DB(os.path.join(cls.dir, "d.db")), env={})
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.svc, "", 600))
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True); cls.th.start()
        cls.u1 = cls.svc.register("9111111111", "Asha")
        cls.u2 = cls.svc.register("9222222222", "Bala")
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); os.environ.pop("JANSEVA_UPLOADS", None)

    def raw(self, path, method, data=None, tok=None, headers=None, ctype="application/json"):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), method=method, data=data)
        if tok: req.add_header("Authorization", "Bearer " + tok)
        if data is not None: req.add_header("Content-Type", ctype)
        for k, v in (headers or {}).items(): req.add_header(k, v)
        try:
            r = urllib.request.urlopen(req, timeout=10)
            body = r.read()
            try: return r.status, json.loads(body.decode())
            except Exception: return r.status, body
        except urllib.error.HTTPError as e:
            body = e.read()
            try: return e.code, json.loads(body.decode())
            except Exception: return e.code, body

    def test_upload_list_open_delete(self):
        st, r = self.raw("/api/seva/documents", "POST", PDF, self.u1["token"], {"X-Doc-Name": "aadhaar.pdf", "X-Doc-Label": "aadhaar"}, "application/pdf")
        self.assertEqual(st, 200); self.assertTrue(r["ok"]); self.assertEqual(r["kind"], "aadhaar")
        did = r["id"]
        st, l = self.raw("/api/seva/documents", tok=self.u1["token"], method="GET")
        names = [x["filename"] for x in l["items"]]
        self.assertIn("aadhaar.pdf", names)
        self.assertIn("aadhaar", l["kinds"])
        # owner can open, bytes match, mime correct
        st, body = self.raw("/api/seva/documents/%d/file" % did, tok=self.u1["token"], method="GET")
        self.assertEqual(st, 200); self.assertEqual(body, PDF)
        # other citizen gets 404 (not even existence leaks); logged out gets 401
        st, _ = self.raw("/api/seva/documents/%d/file" % did, tok=self.u2["token"], method="GET")
        self.assertEqual(st, 404)
        st, _ = self.raw("/api/seva/documents/%d/file" % did, method="GET")
        self.assertEqual(st, 401)
        # access was logged
        logs = self.svc.db.all("SELECT action FROM document_access_logs WHERE document_id=?", (did,))
        self.assertIn("upload", [x["action"] for x in logs]); self.assertIn("view", [x["action"] for x in logs])
        # doc-* files must NOT be reachable through the public /uploads route
        key = self.svc.db.one("SELECT storage_key FROM seva_documents WHERE id=?", (did,))["storage_key"]
        st, _ = self.raw("/uploads/" + key, method="GET")
        self.assertEqual(st, 404)
        # delete: owner only
        st, r = self.raw("/api/seva/documents/%d/delete" % did, "POST", b"{}", self.u2["token"])
        self.assertEqual(st, 404)
        st, r = self.raw("/api/seva/documents/%d/delete" % did, "POST", b"{}", self.u1["token"])
        self.assertTrue(r["ok"])
        st, l = self.raw("/api/seva/documents", tok=self.u1["token"], method="GET")
        self.assertNotIn("aadhaar.pdf", [x["filename"] for x in l["items"]])
        st, _ = self.raw("/api/seva/documents/%d/file" % did, tok=self.u1["token"], method="GET")
        self.assertEqual(st, 404)

    def test_bad_files_rejected(self):
        st, r = self.raw("/api/seva/documents", "POST", TXT, self.u1["token"], {"X-Doc-Name": "notes.txt"}, "text/plain")
        self.assertEqual(st, 422)
        st, r = self.raw("/api/seva/documents", "POST", b"", self.u1["token"], {"X-Doc-Name": "x.pdf"}, "application/pdf")
        self.assertEqual(st, 422)
        big = b"%PDF" + b"0" * (5 * 1024 * 1024 + 10)
        st, r = self.raw("/api/seva/documents", "POST", big, self.u1["token"], {"X-Doc-Name": "big.pdf"}, "application/pdf")
        self.assertEqual(st, 422)

    def test_attach_advances_status_honestly(self):
        st, r = self.raw("/api/seva/documents", "POST", PNG, self.u1["token"], {"X-Doc-Name": "photo.png", "X-Doc-Label": "photo"}, "image/png")
        did = r["id"]
        a = seva.create_application(self.svc.db, self.u1, "income-certificate", "Test attach")
        st, r = self.raw("/api/seva/applications/%s/documents" % a["ref_no"], "POST", json.dumps({"document_id": did}).encode(), self.u1["token"])
        self.assertTrue(r["ok"])
        got = seva.get_application(self.svc.db, a["ref_no"], self.u1["id"])
        self.assertEqual(got["status"], "documents_received")  # internal Seva Setu status only
        self.assertEqual(got["documents"][0]["document_id"], did)
        # cannot attach twice
        st, r = self.raw("/api/seva/applications/%s/documents" % a["ref_no"], "POST", json.dumps({"document_id": did}).encode(), self.u1["token"])
        self.assertEqual(st, 422)
        # other citizen cannot attach a document they do not own to their own application
        a2 = seva.create_application(self.svc.db, self.u2, "ration-card", "Bala app")
        st, r = self.raw("/api/seva/applications/%s/documents" % a2["ref_no"], "POST", json.dumps({"document_id": did}).encode(), self.u2["token"])
        self.assertEqual(st, 422)
        # and cannot touch someone else's application
        st, r = self.raw("/api/seva/applications/%s/documents" % a["ref_no"], "POST", json.dumps({"document_id": did}).encode(), self.u2["token"])
        self.assertEqual(st, 404)

if __name__ == "__main__":
    unittest.main()
