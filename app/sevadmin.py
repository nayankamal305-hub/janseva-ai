"""Phase 6 (Seva Setu India): super-admin control centre.

Every function takes an already-authenticated admin row (from accounts.admin_by_token);
server.py enforces the seva.admin permission before calling anything here.
Nothing here touches official government status - operators do that via sevop with
the same evidence rules.
"""
import json
from .db import now
from . import accounts, roles

SETTINGS_KEYS = ("brand_name", "brand_short", "wa_number", "support_text",
                 "data_retention_days", "whatsapp_status")
EDITABLE_ROLES = [r for r in roles.ROLES]


def _actor(admin):
    return "admin:%s" % (admin.get("name") or admin.get("id"))


# ---- analytics / overview
def overview(db):
    by_status = {r["status"]: r["c"] for r in db.all("SELECT status, COUNT(*) c FROM applications GROUP BY status")}
    return {
        "citizens": db.one("SELECT COUNT(*) c FROM users")["c"],
        "applications": db.one("SELECT COUNT(*) c FROM applications")["c"],
        "applications_by_status": by_status,
        "pending_applications": sum(c for s, c in by_status.items() if s not in ("closed", "resolved_verified")),
        "documents": db.one("SELECT COUNT(*) c FROM seva_documents WHERE deleted=0")["c"],
        "complaints": db.one("SELECT COUNT(*) c FROM complaints")["c"],
        "staff": db.one("SELECT COUNT(*) c FROM admin_users WHERE token IS NOT NULL")["c"],
        "verified_submissions": db.one("SELECT COUNT(*) c FROM government_submissions WHERE verified=1 AND ack_no IS NOT NULL AND ack_no<>''")["c"],
        "schemes": db.one("SELECT COUNT(*) c FROM schemes WHERE active=1")["c"],
    }


# ---- citizens
def list_citizens(db, q=""):
    q = (q or "").strip()
    like = "%" + q + "%"
    if q:
        rows = db.all(
            "SELECT u.id, u.phone, u.name, u.created_at, p.state, p.district, f.flag, f.reason"
            " FROM users u LEFT JOIN citizen_profiles p ON p.user_id=u.id"
            " LEFT JOIN citizen_flags f ON f.user_id=u.id"
            " WHERE u.phone LIKE ? OR u.name LIKE ? ORDER BY u.id DESC LIMIT 100", (like, like))
    else:
        rows = db.all(
            "SELECT u.id, u.phone, u.name, u.created_at, p.state, p.district, f.flag, f.reason"
            " FROM users u LEFT JOIN citizen_profiles p ON p.user_id=u.id"
            " LEFT JOIN citizen_flags f ON f.user_id=u.id ORDER BY u.id DESC LIMIT 100")
    return rows


def flag_citizen(db, user_id, flag, reason, admin):
    u = db.one("SELECT id FROM users WHERE id=?", (user_id,))
    if not u: return None
    if flag == "clear":
        db.run("DELETE FROM citizen_flags WHERE user_id=?", (user_id,))
        db.audit(_actor(admin), "citizen_flag_cleared", "user:%s" % user_id)
        return {"id": user_id, "flag": None}
    if flag != "suspended": return {}
    db.run("DELETE FROM citizen_flags WHERE user_id=?", (user_id,))
    db.run("INSERT INTO citizen_flags(user_id,flag,reason,created_by,created_at) VALUES(?,?,?,?,?)",
           (user_id, "suspended", (reason or "")[:300], _actor(admin), now()))
    db.audit(_actor(admin), "citizen_suspended", "user:%s %s" % (user_id, (reason or "")[:120]))
    return {"id": user_id, "flag": "suspended", "reason": reason}


def is_suspended(db, user_id):
    return bool(db.one("SELECT 1 x FROM citizen_flags WHERE user_id=? AND flag='suspended'", (user_id,)))


# ---- staff (operators and other admin roles)
def list_staff(db):
    rows = db.all("SELECT id,name,role,scope_state,scope_city,department,created_at,(token IS NOT NULL) active FROM admin_users ORDER BY id DESC")
    return rows


def create_staff(db, name, role, admin, scope_state=None, scope_city=None, department=None):
    name = (name or "").strip()[:80]
    if not name or role not in EDITABLE_ROLES: return None
    tok = accounts.create_admin(db, name, role, scope_state, scope_city, department)
    db.audit(_actor(admin), "staff_created", "%s (%s)" % (name, role))
    return {"name": name, "role": role, "token": tok}


def disable_staff(db, staff_id, admin):
    row = db.one("SELECT id,name,role,token FROM admin_users WHERE id=?", (staff_id,))
    if not row: return None
    if row["role"] == "super_admin":
        # A stored super-admin token can only be disabled by the env super token (id 0),
        # never by another stored admin - prevents lockout by mistake.
        if admin.get("id") != 0: return {}
    if row["id"] == admin.get("id"): return {}
    db.run("UPDATE admin_users SET token=NULL WHERE id=?", (staff_id,))
    db.audit(_actor(admin), "staff_disabled", "%s (%s)" % (row["name"], row["role"]))
    return {"id": staff_id, "disabled": True}


# ---- catalog: categories, services, schemes
def catalog_full(db):
    cats = db.all("SELECT * FROM service_categories ORDER BY sort, id")
    svcs = db.all("SELECT * FROM services ORDER BY id DESC")
    schemes = db.all("SELECT * FROM schemes ORDER BY id DESC")
    return {"categories": cats, "services": svcs, "schemes": schemes}


def upsert_category(db, d, admin):
    cid = (d.get("id") or "").strip()[:40]
    name = (d.get("name") or "").strip()[:120]
    if not cid or not name or not cid.replace("-", "").isalnum(): return None
    blurb = (d.get("blurb") or "").strip()[:300]
    icon = (d.get("icon") or "").strip()[:40] or "file"
    sort = int(d.get("sort") or 0)
    names = json.dumps({"en": name})
    existing = db.one("SELECT id FROM service_categories WHERE id=?", (cid,))
    if existing:
        old = db.one("SELECT names FROM service_categories WHERE id=?", (cid,))
        try: nm = json.loads(old["names"] or "{}")
        except Exception: nm = {}
        nm["en"] = name
        db.run("UPDATE service_categories SET names=?, blurb=?, icon=?, sort=? WHERE id=?",
               (json.dumps(nm), blurb, icon, sort, cid))
        db.audit(_actor(admin), "category_updated", cid)
    else:
        db.run("INSERT INTO service_categories(id,icon,names,blurb,links,online,docs,complaint,verified,sort) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (cid, icon, names, blurb, "[]", "[]", "[]", 0, now()[:10], sort))
        db.audit(_actor(admin), "category_created", cid)
    return {"id": cid, "created": not existing}


def upsert_service(db, d, admin):
    name = (d.get("name") or "").strip()[:160]
    cat = (d.get("category_id") or "").strip()[:40]
    if not name or not db.one("SELECT id FROM service_categories WHERE id=?", (cat,)):
        return None
    dept = (d.get("dept") or "").strip()[:120]
    state = (d.get("state") or "").strip()[:60]
    link = (d.get("link") or "").strip()[:300]
    sid = d.get("id")
    if sid:
        row = db.one("SELECT id,data FROM services WHERE id=?", (int(sid),))
        if not row: return None
        try: data = json.loads(row["data"] or "{}")
        except Exception: data = {}
        if link: data["link"] = link
        db.run("UPDATE services SET name=?, dept=?, state=?, data=?, verified=? WHERE id=?",
               (name, dept, state, json.dumps(data), now()[:10], int(sid)))
        db.audit(_actor(admin), "service_updated", "%s" % sid)
        return {"id": int(sid), "created": False}
    cur = db.run("INSERT INTO services(category_id,name,dept,state,data,verified) VALUES(?,?,?,?,?,?)",
                 (cat, name, dept, state, json.dumps({"link": link} if link else {}), now()[:10]))
    db.audit(_actor(admin), "service_created", name)
    return {"id": cur, "created": True}


def upsert_scheme(db, d, admin):
    slug = (d.get("slug") or "").strip()[:60]
    name = (d.get("name") or "").strip()[:160]
    if not slug or not name: return None
    benefit = (d.get("benefit") or "").strip()[:300]
    link = (d.get("link") or "").strip()[:300]
    source = (d.get("source") or "").strip()[:300]
    state = (d.get("state") or "").strip()[:60]
    active = 1 if d.get("active", True) else 0
    existing = db.one("SELECT id FROM schemes WHERE slug=?", (slug,))
    if existing:
        db.run("UPDATE schemes SET name=?, benefit=?, link=?, source=?, state=?, active=?, last_verified=? WHERE slug=?",
               (name, benefit, link, source, state, active, now()[:10], slug))
        db.audit(_actor(admin), "scheme_updated", slug)
        return {"id": existing["id"], "created": False}
    cur = db.run("INSERT INTO schemes(slug,name,names,benefit,eligibility,docs,link,source,last_verified,state,active) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 (slug, name, json.dumps({"en": name}), benefit, "[]", "[]", link, source, now()[:10], state, active))
    db.audit(_actor(admin), "scheme_created", slug)
    return {"id": cur, "created": True}


# ---- translations
def list_translations(db):
    return db.all("SELECT id,key,lang,text,status,updated_at FROM seva_translations ORDER BY key, lang LIMIT 500")


def upsert_translation(db, d, admin):
    key = (d.get("key") or "").strip()[:80]
    lang = (d.get("lang") or "").strip()[:8]
    text = (d.get("text") or "").strip()[:2000]
    status = (d.get("status") or "approved").strip()[:20]
    if not key or not lang or not text: return None
    existing = db.one("SELECT id FROM seva_translations WHERE key=? AND lang=?", (key, lang))
    if existing:
        db.run("UPDATE seva_translations SET text=?, status=?, updated_at=? WHERE id=?", (text, status, now(), existing["id"]))
        tid = existing["id"]
    else:
        tid = db.run("INSERT INTO seva_translations(key,lang,text,status,updated_at) VALUES(?,?,?,?,?)",
                     (key, lang, text, status, now()))
    db.audit(_actor(admin), "translation_saved", "%s:%s" % (key, lang))
    return {"id": tid, "updated": bool(existing)}


# ---- audit
def audit_recent(db, limit=100):
    limit = max(1, min(int(limit or 100), 300))
    return db.all("SELECT id,ts,actor,action,detail FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


# ---- settings / brand / WhatsApp config
def get_settings(db):
    return {r["key"]: r["value"] for r in db.all("SELECT key,value FROM settings")}


def set_settings(db, d, admin):
    saved = {}
    for k in SETTINGS_KEYS:
        if k not in d: continue
        v = ("" if d[k] is None else str(d[k])).strip()[:500]
        if k == "wa_number":
            v = "".join(ch for ch in v if ch.isdigit())[:15]
        db.run("DELETE FROM settings WHERE key=?", (k,))
        db.run("INSERT INTO settings(key,value,updated_at,updated_by) VALUES(?,?,?,?)", (k, v, now(), _actor(admin)))
        saved[k] = v
    if saved:
        db.audit(_actor(admin), "settings_updated", ",".join(sorted(saved)))
    return saved


def public_config(db, env):
    s = get_settings(db)
    import os
    return {
        "brand_name": s.get("brand_name") or env.get("SEVA_BRAND_NAME") or os.environ.get("SEVA_BRAND_NAME", "Seva Setu India"),
        "brand_short": s.get("brand_short") or env.get("SEVA_SHORT_NAME") or os.environ.get("SEVA_SHORT_NAME", "Seva Setu"),
        "wa_number": s.get("wa_number") or env.get("SEVA_WA_NUMBER") or os.environ.get("SEVA_WA_NUMBER", "917033167496"),
        "whatsapp_status": s.get("whatsapp_status") or "manual",
    }
