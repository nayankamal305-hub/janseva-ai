"""Outbound/inbound email using any free SMTP/IMAP account (Brevo free: 300 mails/day; Gmail app password: ~500/day).
Nothing is sent unless SMTP_HOST/SMTP_USER/SMTP_PASS/SMTP_FROM are set. Never fakes a send."""
import os, re, smtplib, imaplib, email as _email, ssl
from email.message import EmailMessage
from email.utils import parseaddr

def configured(env=os.environ): return bool(env.get("SMTP_HOST") and env.get("SMTP_USER") and env.get("SMTP_PASS") and env.get("SMTP_FROM"))

def send(to, subject, body, reply_to=None, env=os.environ):
    if not configured(env): return {"sent": False, "reason": "SMTP not configured"}
    m = EmailMessage(); m["From"] = env["SMTP_FROM"]; m["To"] = to; m["Subject"] = subject
    if reply_to: m["Reply-To"] = reply_to
    m["X-Mailer"] = "JANSEVA AI"; m.set_content(body)
    try:
        port = int(env.get("SMTP_PORT", "587"))
        with smtplib.SMTP(env["SMTP_HOST"], port, timeout=20) as s:
            if env.get("SMTP_STARTTLS", "1") != "0":
                s.starttls(context=ssl.create_default_context()); s.login(env["SMTP_USER"], env["SMTP_PASS"]); s.send_message(m)
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "reason": "smtp error: %s" % type(e).__name__}

CODE_RE = re.compile(r"JSV-[A-Z0-9]{4,}", re.I)
def tracking_code(subject, to_header="", body=""):
    for t in (subject or "", to_header or "", (body or "")[:2000]):
        m = CODE_RE.search(t)
        if m: return m.group(0).upper()
    return None

def poll_inbox(env=os.environ, limit=30):
    """Read-only-ish IMAP poll of the JANSEVA reply mailbox. Returns parsed replies; caller records them as timeline events."""
    if not (env.get("IMAP_HOST") and env.get("SMTP_USER") and env.get("SMTP_PASS")): return []
    out = []
    try:
        M = imaplib.IMAP4_SSL(env["IMAP_HOST"]); M.login(env["SMTP_USER"], env["SMTP_PASS"]); M.select("INBOX")
        typ, ids = M.search(None, "UNSEEN")
        for i in (ids[0].split() or [])[-limit:]:
            typ, d = M.fetch(i, "(BODY.PEEK[])"); msg = _email.message_from_bytes(d[0][1])
            body = ""
            for p in msg.walk():
                if p.get_content_type() == "text/plain": body = p.get_payload(decode=True).decode("utf-8", "ignore"); break
            code = tracking_code(msg.get("Subject"), msg.get("To", "") + " " + msg.get("Delivered-To", ""), body)
            if code: out.append({"code": code, "from": parseaddr(msg.get("From", ""))[1], "subject": msg.get("Subject", ""), "snippet": body.strip()[:600], "imap_id": i.decode()})
        M.logout()
    except Exception as e:
        return [{"error": type(e).__name__}]
    return out
