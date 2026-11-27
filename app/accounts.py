import hashlib, hmac, os, random, secrets
from datetime import datetime, timedelta, timezone
from .db import now

def hs(x): return hashlib.sha256(x.encode()).hexdigest()

def otp_request(db, phone, dev=False):
    code = "%06d" % random.SystemRandom().randrange(10**6)
    db.run("INSERT OR REPLACE INTO otps(phone,code_hash,expires,attempts) VALUES(?,?,?,0)", (phone, hs(phone + code), (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()))
    db.audit("system", "otp_issued", phone[-4:])
    # No SMS provider is wired in. Code is returned ONLY in dev mode (JANSEVA_DEV_OTP=1).
    return {"sent": False, "note": "SMS provider not configured in this build", **({"dev_code": code} if dev else {})}

def otp_verify(svc, phone, code, name=""):
    db = svc.db; r = db.one("SELECT * FROM otps WHERE phone=?", (phone,))
    if not r or r["attempts"] >= 5 or datetime.fromisoformat(r["expires"]) < datetime.now(timezone.utc): return None
    db.run("UPDATE otps SET attempts=attempts+1 WHERE phone=?", (phone,))
    if not hmac.compare_digest(r["code_hash"], hs(phone + code)): return None
    db.run("DELETE FROM otps WHERE phone=?", (phone,))
    return svc.register(phone, name)

def delete_account(db, uid):
    """Anonymise: remove identity, keep complaints (government records exist) without personal link."""
    db.run("UPDATE users SET phone=?,name='',token=?,deleted=1 WHERE id=?", ("deleted-%d" % uid, secrets.token_urlsafe(16), uid))
    db.run("UPDATE complaints SET anonymous=1 WHERE user_id=?", (uid,))
    db.audit("user:%d" % uid, "account_deleted", "anonymised")

def create_admin(db, name, role, scope_state=None, scope_city=None, department=None):
    tok = secrets.token_urlsafe(24)
    db.run("INSERT INTO admin_users(name,token,role,scope_state,scope_city,department,created_at) VALUES(?,?,?,?,?,?,?)", (name, tok, role, scope_state, scope_city, department, now()))
    return tok

def admin_by_token(db, tok, super_token):
    if not tok: return None
    if super_token and hmac.compare_digest(tok, super_token): return {"id": 0, "name": "super", "role": "super_admin", "scope_state": None, "scope_city": None}
    return db.one("SELECT * FROM admin_users WHERE token=?", (tok,))

def letter(c, user_name, platform_names):
    from .connectors.base import complaint_text
    return complaint_text(c, user_name if not c.get("anonymous") else "")
