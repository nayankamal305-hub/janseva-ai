from app.db import guard_test_database_url as _g; _g()
# Phase 5 (Seva Setu India): operator console - queue, honest status advance, consent-gated document access.
import os, sys, json, tempfile, unittest, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer
from app.db import DB
from app.service import Service
from app.server import make_handler
import app.server as server_mod  # UPLOADS is read dynamically: other suites may repoint the constant
from app import seva, sevdoc, accounts

PDF = b"%PDF-1.4 op test " + b"z" * 64

class Op(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.svc = Service(DB(os.path.join(cls.dir, "o.db")), env={})
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.svc, "", 600))
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True); cls.th.start()
        cls.cit = cls.svc.register("9111111111", "Asha")
        cls.op_tok = accounts.create_admin(cls.svc.db, "Ops One", "seva_operator")
        cls.viewer_tok = accounts.create_admin(cls.svc.db, "Viewer", "public_viewer")
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, method="GET", body=None, tok=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), method=method)
        if tok: req.add_header("Authorization", "Bearer " + tok)
        data = None
        if body is not None:
            data = json.dumps(body).encode() if not isinstance(body, bytes) else body
            req.add_header("Content-Type", "application/json")
        try:
            r = urllib.request.urlopen(req, data, timeout=10)
            raw = r.read()
            try: return r.status, json.loads(raw.decode())
            except Exception: return r.status, raw
        except urllib.error.HTTPError as e:
            raw = e.read()
            try: return e.code, json.loads(raw.decode())
            except Exception: return e.code, raw

    def _make_app_with_doc(self):
        a = seva.create_application(self.svc.db, self.cit, "income-certificate", "Op test app")
        r = sevdoc.save_document(self.svc.db, os.environ, server_mod.UPLOADS, self.cit, "proof.pdf", PDF, "income_proof")
        sevdoc.attach_document(self.svc.db, seva.get_application(self.svc.db, a["ref_no"], self.cit["id"]), r["id"], self.cit)
        key = "doc-%s.pdf" % __import__("hashlib").sha256(PDF).hexdigest()[:32]
        self.addCleanup(lambda: os.path.isfile(os.path.join(server_mod.UPLOADS, key)) and os.remove(os.path.join(server_mod.UPLOADS, key)))
        return a["ref_no"], r["id"]

    def test_access_control(self):
        st, _ = self.call("/api/op/applications", tok=self.cit["token"])
        self.assertEqual(st, 403)  # citizen token is not an operator
        st, _ = self.call("/api/op/applications", tok=self.viewer_tok)
        self.assertEqual(st, 403)  # admin without seva.operate
        st, _ = self.call("/api/op/applications")
        self.assertEqual(st, 403)
        st, r = self.call("/api/op/applications", tok=self.op_tok)
        self.assertEqual(st, 200); self.assertIn("items", r)

    def test_queue_detail_masking(self):
        ref, did = self._make_app_with_doc()
        st, q = self.call("/api/op/applications", tok=self.op_tok)
        row = [x for x in q["items"] if x["ref_no"] == ref][0]
        self.assertNotEqual(row["citizen_phone"], "9111111111")
        self.assertTrue(row["citizen_phone"].endswith("1111"))
        st, det = self.call("/api/op/applications/" + ref, tok=self.op_tok)
        self.assertEqual(st, 200)
        self.assertEqual(det["application"]["status"], "documents_received")
        self.assertEqual(len(det["documents"]), 1)
        self.assertIsNone(det["consent"])

    def test_status_and_submission_honesty(self):
        ref, did = self._make_app_with_doc()
        # official status without verified submission -> rejected
        st, r = self.call("/api/op/applications/%s/status" % ref, "POST", {"status": "submitted_to_portal"}, self.op_tok)
        self.assertEqual(st, 422)
        # submission claimed verified but no ack -> stored unverified
        st, r = self.call("/api/op/applications/%s/submissions" % ref, "POST", {"portal": "serviceplus.gov.in", "method": "guided", "ack_no": "", "verified": True}, self.op_tok)
        self.assertTrue(r["ok"]); self.assertEqual(r["verified"], 0)
        st, r = self.call("/api/op/applications/%s/status" % ref, "POST", {"status": "submitted_to_portal"}, self.op_tok)
        self.assertEqual(st, 422)  # still no verified ack
        # real ack -> verified -> official status allowed
        st, r = self.call("/api/op/applications/%s/submissions" % ref, "POST", {"portal": "serviceplus.gov.in", "method": "guided", "ack_no": "MH-2026-998877", "verified": True}, self.op_tok)
        self.assertEqual(r["verified"], 1)
        st, r = self.call("/api/op/applications/%s/status" % ref, "POST", {"status": "submitted_to_portal", "note": "ack MH-2026-998877"}, self.op_tok)
        self.assertTrue(r["ok"])
        # internal statuses always fine
        st, r = self.call("/api/op/applications/%s/status" % ref, "POST", {"status": "under_verification"}, self.op_tok)
        self.assertTrue(r["ok"])
        # citizen sees notifications for these events
        st, n = self.call("/api/seva/notifications", tok=self.cit["token"])
        kinds = [x["kind"] for x in n["items"]]
        self.assertIn("status_update", kinds); self.assertIn("submission_recorded", kinds)

    def test_consent_gated_document_access(self):
        ref, did = self._make_app_with_doc()
        # no consent -> operator blocked
        st, r = self.call("/api/op/documents/%d/file?app=%s" % (did, ref), tok=self.op_tok)
        self.assertEqual(st, 403)
        # operator asks, citizen gets a notification
        st, r = self.call("/api/op/applications/%s/request-docs" % ref, "POST", {}, self.op_tok)
        self.assertTrue(r["ok"])
        st, n = self.call("/api/seva/notifications", tok=self.cit["token"])
        self.assertIn("consent_request", [x["kind"] for x in n["items"]])
        # citizen denies -> still blocked
        st, r = self.call("/api/seva/consents", "POST", {"scope": "operator_document_access", "granted": False, "application_ref": ref}, self.cit["token"])
        st, _ = self.call("/api/op/documents/%d/file?app=%s" % (did, ref), tok=self.op_tok)
        self.assertEqual(st, 403)
        # citizen grants -> operator can open, logged with consent id
        st, r = self.call("/api/seva/consents", "POST", {"scope": "operator_document_access", "granted": True, "application_ref": ref}, self.cit["token"])
        cid = r["id"]
        st, body = self.call("/api/op/documents/%d/file?app=%s" % (did, ref), tok=self.op_tok)
        self.assertEqual(st, 200); self.assertEqual(body, PDF)
        log = self.svc.db.one("SELECT actor,consent_id FROM document_access_logs WHERE document_id=? ORDER BY id DESC LIMIT 1", (did,))
        self.assertTrue(log["actor"].startswith("operator:")); self.assertEqual(log["consent_id"], cid)
        # citizen revokes -> blocked again
        st, r = self.call("/api/seva/consents/%d/revoke" % cid, "POST", {}, self.cit["token"])
        self.assertTrue(r["ok"])
        st, _ = self.call("/api/op/documents/%d/file?app=%s" % (did, ref), tok=self.op_tok)
        self.assertEqual(st, 403)

    def test_cannot_open_doc_from_other_application(self):
        ref1, did1 = self._make_app_with_doc()
        ref2, did2 = self._make_app_with_doc()
        self.call("/api/seva/consents", "POST", {"scope": "operator_document_access", "granted": True, "application_ref": ref1}, self.cit["token"])
        # consent covers ref1 only: did2 is attached to ref2
        st, _ = self.call("/api/op/documents/%d/file?app=%s" % (did2, ref1), tok=self.op_tok)
        self.assertIn(st, (403, 404))

if __name__ == "__main__":
    unittest.main()
