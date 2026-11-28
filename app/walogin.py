"""Free WhatsApp login (user-initiated). The user sends 'Seva Setu LOGIN <code>' to Seva Setu's WhatsApp Business number; Meta's webhook delivers it with the
sender's verified WhatsApp number. User-to-business messages are never charged. Seva Setu sends NOTHING back by default (WA_REPLY=1 enables a reply, which is a
service message: first 1,000/month per number free, then paid). Enabled only when WA_NUMBER, WA_VERIFY_TOKEN and WA_APP_SECRET are set."""
import hashlib, hmac, json, re, secrets
from datetime import datetime, timedelta, timezone
from .db import now

def enabled(env): return bool(env.get("WA_NUMBER") and env.get("WA_VERIFY_TOKEN") and env.get("WA_APP_SECRET"))
def _h(x): return hashlib.sha256(x.encode()).hexdigest()

def start(db, env):
    wid = secrets.token_urlsafe(12); code = secrets.token_hex(3).upper(); poll = secrets.token_urlsafe(16)
    db.run("DELETE FROM wa_login WHERE expires < ?", (now(),))
    db.run("INSERT INTO wa_login(id,code,poll_hash,created,expires) VALUES(?,?,?,?,?)", (wid, code, _h(poll), now(), (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()))
    text = "Seva Setu LOGIN " + code
    return {"id": wid, "poll": poll, "code": code, "expires_in": 600, "link": "https://wa.me/%s?text=%s" % (re.sub(r"\D", "", env["WA_NUMBER"]), text.replace(" ", "%20"))}

def verify_challenge(env, q):
    if q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), env.get("WA_VERIFY_TOKEN", "")): return q.get("hub.challenge", "")
    return None

def signature_ok(env, raw, header):
    sec = env.get("WA_APP_SECRET", "")
    if not sec or not header or not header.startswith("sha256="): return False
    return hmac.compare_digest(header[7:], hmac.new(sec.encode(), raw, hashlib.sha256).hexdigest())

def handle_webhook(db, payload):
    """Returns list of verified phones. The sender number comes from Meta's signed payload, never from message text."""
    done = []
    for e in payload.get("entry", []):
        for ch in e.get("changes", []):
            for m in (ch.get("value") or {}).get("messages", []) or []:
                if m.get("type") != "text": continue
                mt = re.search(r"SEVA SETU\s+LOGIN\s+([A-F0-9]{6})", (m.get("text") or {}).get("body", "").upper())
                frm = re.sub(r"\D", "", m.get("from", ""))
                if not mt or len(frm) < 10: continue
                r = db.one("SELECT * FROM wa_login WHERE code=? AND phone IS NULL", (mt.group(1),))
                if not r or r["expires"] < now(): continue
                db.run("UPDATE wa_login SET phone=?, verified_at=? WHERE id=?", (frm[-10:], now(), r["id"])); db.audit("system", "wa_login_verified", frm[-4:]); done.append(frm[-10:])
    return done

def poll(svc, wid, poll_secret):
    r = svc.db.one("SELECT * FROM wa_login WHERE id=?", (wid,))
    if not r or not hmac.compare_digest(r["poll_hash"], _h(poll_secret or "")): return {"status": "invalid"}
    if r["expires"] < now(): return {"status": "expired"}
    if not r["phone"]: return {"status": "waiting"}
    if r["token_taken"]: return {"status": "used"}
    svc.db.run("UPDATE wa_login SET token_taken=1 WHERE id=?", (wid,))
    u = svc.register(r["phone"], ""); return {"status": "ok", "token": u["token"], "name": u["name"]}
