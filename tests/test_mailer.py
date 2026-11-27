from app.db import guard_test_database_url as _g; _g()
import unittest
from unittest import mock
from app import mailer
B = {"EMAIL_PROVIDER": "brevo", "BREVO_API_KEY": "k", "MAIL_FROM": "JANSEVA AI <a@b.com>"}
class M(unittest.TestCase):
    def test_provider_choice(self):
        self.assertEqual(mailer.provider(B), "brevo"); self.assertIsNone(mailer.provider({"EMAIL_PROVIDER": "brevo", "MAIL_FROM": "a@b.com"}))
        self.assertEqual(mailer.provider({"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": "r", "MAIL_FROM": "a@b.com"}), "resend")
        self.assertEqual(mailer.provider({"SMTP_HOST": "h", "SMTP_USER": "u", "SMTP_PASS": "p", "SMTP_FROM": "a@b.com"}), "smtp"); self.assertIsNone(mailer.provider({}))
    def test_brevo_payload(self):
        with mock.patch.object(mailer, "_post", return_value={"sent": True}) as p:
            self.assertTrue(mailer.send("x@y.gov.in", "S", "Body", "a+JSV-AB12CD@b.com", B)["sent"])
        url, hdr, body = p.call_args[0]
        self.assertEqual(url, "https://api.brevo.com/v3/smtp/email"); self.assertEqual(hdr["api-key"], "k")
        self.assertEqual(body["sender"], {"name": "JANSEVA AI", "email": "a@b.com"}); self.assertEqual(body["to"], [{"email": "x@y.gov.in"}]); self.assertEqual(body["replyTo"]["email"], "a+JSV-AB12CD@b.com")
    def test_resend_payload(self):
        e = {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": "r", "MAIL_FROM": "a@b.com"}
        with mock.patch.object(mailer, "_post", return_value={"sent": True}) as p: mailer.send("x@y.com", "S", "B", "r@b.com", e)
        url, hdr, body = p.call_args[0]
        self.assertEqual(url, "https://api.resend.com/emails"); self.assertEqual(hdr["Authorization"], "Bearer r"); self.assertEqual(body["reply_to"], "r@b.com")
    def test_api_failure_not_sent(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("u", 401, "x", {}, None)):
            r = mailer.send("x@y.com", "S", "B", None, B)
        self.assertFalse(r["sent"]); self.assertIn("401", r["reason"]); self.assertNotIn("k", r["reason"].replace("API error", ""))
if __name__ == "__main__": unittest.main()
