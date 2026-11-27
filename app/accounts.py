import hashlib, hmac, os, random, re, secrets
from datetime import datetime, timedelta, timezone
from .db import now

def hs(x): return hashlib.sha256(x.encode()).hexdigest()

def norm_ident(x):
    x = (x or "").strip()
    if "@" in x:
        x = x.lower()
        return x if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", x) else None
    d = re.sub(r"\D", "", x)[-10:]
    return d if len(d) == 10 else None

def otp_request(db, phone, dev=False):
    code = "%06d" % random.SystemRandom().randrange(10**6)
    db.run("INSERT OR REPLACE INTO otps(phone,code_hash,expires,attempts) VALUES(?,?,?,0)", (phone, hs(phone + code), (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()))
    db.audit("system", "otp_issued", phone[-4:])
    # Email OTP is real when SMTP_* is configured. No SMS provider is wired in (DLT rules). Code is returned ONLY in dev mode (JANSEVA_DEV_OTP=1).
    if "@" in phone:
        from . import mailer
        r = mailer.send(phone, "Your JANSEVA AI login code", "Your JANSEVA AI login code is %s. It expires in 5 minutes. If you did not ask for it, ignore this email." % code)
        if r["sent"]: return {"sent": True, "channel": "email"}
        return {"sent": False, "channel": "email", "note": "Email sending not configured on this server", **({"dev_code": code} if dev else {})}
    return {"sent": False, "channel": "sms", "note": "SMS OTP needs a DLT-registered provider; use email login", **({"dev_code": code} if dev else {})}

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

# ---- password login (v3.12). Hash: scrypt (stdlib, memory-hard, random 16-byte salt per user). OTP is only for first signup and password reset.
_SC = (2 ** 14, 8, 1)
MAX_FAILS, LOCK_MIN = 5, 15

def pw_hash(pw):
    salt = os.urandom(16); n, r, p = _SC
    h = hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (n, r, p, salt.hex(), h.hex())

def pw_check(pw, stored):
    try:
        alg, n, r, p, salt, h = (stored or "").split("$")
        if alg != "scrypt": return False
        x = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(x.hex(), h)
    except Exception:
        return False

_DUMMY = None
def pw_policy(pw):
    pw = pw or ""
    if len(pw) < 8: return "Password must be at least 8 characters."
    if len(pw) > 128: return "Password is too long (max 128)."
    if pw.lower() in ("password", "12345678", "123456789", "qwertyui", "password1"): return "That password is too common."
    return None

def _lock_state(db, key):
    r = db.one("SELECT * FROM login_attempts WHERE key=?", (key,))
    if r and r["locked_until"] and datetime.fromisoformat(r["locked_until"]) > datetime.now(timezone.utc): return r
    return None

def _fail(db, key):
    r = db.one("SELECT * FROM login_attempts WHERE key=?", (key,)); f = (r["fails"] if r else 0) + 1
    lock = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_MIN)).isoformat() if f >= MAX_FAILS else None
    db.run("INSERT OR REPLACE INTO login_attempts(key,fails,locked_until,updated_at) VALUES(?,?,?,?)", (key, 0 if lock else f, lock, now()))

def set_password(svc, user_id, pw):
    svc.db.run("UPDATE users SET pw_hash=?, pw_set_at=?, token=? WHERE id=?", (pw_hash(pw), now(), secrets.token_urlsafe(24), user_id))  # new token: old sessions end when the password changes
    svc.db.audit("user:%d" % user_id, "password_set", "")

def password_login(svc, ident, pw, ip=""):
    """Returns (user|None, status). status: ok | locked | bad. Same answer for unknown user and wrong password (no account enumeration)."""
    global _DUMMY
    db = svc.db; keys = ["u:" + (ident or ""), "ip:" + (ip or "?")]
    if not ident or any(_lock_state(db, k) for k in keys): return None, "locked" if ident else "bad"
    u = db.one("SELECT * FROM users WHERE phone=? AND COALESCE(deleted,0)=0", (ident,))
    if _DUMMY is None: _DUMMY = pw_hash("dummy-password")
    ok = pw_check(pw or "", u["pw_hash"] if u and u.get("pw_hash") else _DUMMY)
    if u and u.get("pw_hash") and ok:
        db.run("DELETE FROM login_attempts WHERE key=?", (keys[0],)); return u, "ok"
    for k in keys: _fail(db, k)
    return None, "bad"

def password_signup_or_reset(svc, ident, code, pw, name="", reset=False, ip=""):
    """OTP proves control of the email/phone once; then the password is set. Returns (user|None, error|None)."""
    e = pw_policy(pw)
    if e: return None, e
    u = otp_verify(svc, ident, code, name)
    if not u: return None, "invalid or expired code"
    set_password(svc, u["id"], pw)
    svc.db.run("DELETE FROM login_attempts WHERE key IN (?,?)", ("u:" + ident, "ip:" + (ip or "?")))
    return svc.db.one("SELECT * FROM users WHERE id=?", (u["id"],)), None
