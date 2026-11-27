"""Outbound/inbound email using any free SMTP/IMAP account (Brevo free: 300 mails/day; Gmail app password: ~500/day).
Nothing is sent unless SMTP_HOST/SMTP_USER/SMTP_PASS/SMTP_FROM are set. Never fakes a send."""
import os, re, smtplib, imaplib, email as _email, ssl
from email.message import EmailMessage
from email.utils import parseaddr

import json, urllib.request, urllib.error

def provider(env=os.environ):
    p = (env.get("EMAIL_PROVIDER") or "").lower()
    if p in ("brevo", "resend") and env.get("MAIL_FROM") and env.get("BREVO_API_KEY" if p == "brevo" else "RESEND_API_KEY"): return p
    if env.get("SMTP_HOST") and env.get("SMTP_USER") and env.get("SMTP_PASS") and (env.get("SMTP_FROM") or env.get("MAIL_FROM")): return "smtp"
    return None
def configured(env=os.environ): return provider(env) is not None
def from_address(env=os.environ): return (env.get("MAIL_FROM") or env.get("SMTP_FROM") or "")
def _split(frm):
    m = re.match(r"^\s*(.*?)\s*<([^>]+)>\s*$", frm); return (m.group(1).strip('" '), m.group(2)) if m else ("JANSEVA AI", frm.strip())
def _post(url, headers, body):
    r = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "JANSEVA-AI", **headers})
    try:
        with urllib.request.urlopen(r, timeout=20) as x: return {"sent": 200 <= x.status < 300}
    except urllib.error.HTTPError as e: return {"sent": False, "reason": "%s API error %s" % (url.split("/")[2], e.code)}
    except Exception as e: return {"sent": False, "reason": "email API error: %s" % type(e).__name__}

def send(to, subject, body, reply_to=None, env=os.environ):
    pv = provider(env)
    if not pv: return {"sent": False, "reason": "email not configured"}
    name, addr = _split(from_address(env))
    if pv == "brevo":
        b = {"sender": {"name": name, "email": addr}, "to": [{"email": to}], "subject": subject, "textContent": body}
        if reply_to: b["replyTo"] = {"email": reply_to}
        return _post("https://api.brevo.com/v3/smtp/email", {"api-key": env["BREVO_API_KEY"]}, b)
    if pv == "resend":
        b = {"from": from_address(env), "to": [to], "subject": subject, "text": body}
        if reply_to: b["reply_to"] = reply_to
        return _post("https://api.resend.com/emails", {"Authorization": "Bearer " + env["RESEND_API_KEY"]}, b)
    m = EmailMessage(); m["From"] = from_address(env); m["To"] = to; m["Subject"] = subject
    if reply_to: m["Reply-To"] = reply_to
    m["X-Mailer"] = "JANSEVA AI"; m.set_content(body)
    try:
        port = int(env.get("SMTP_PORT", "587"))
        with smtplib.SMTP(env["SMTP_HOST"], port, timeout=20) as s:
            if env.get("SMTP_STARTTLS", "1") != "0":
                s.starttls(context=ssl.create_default_context()); s.login(env["SMTP_USER"], env["SMTP_PASS"])
            s.send_message(m)
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
    iu = env.get("IMAP_USER") or env.get("SMTP_USER"); ip = env.get("IMAP_PASS") or env.get("SMTP_PASS")
    if not (env.get("IMAP_HOST") and iu and ip): return []
    out = []
    try:
        M = imaplib.IMAP4_SSL(env["IMAP_HOST"]); M.login(iu, ip); M.select("INBOX")
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
