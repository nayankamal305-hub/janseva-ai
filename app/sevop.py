"""Seva Setu India - Phase 5: operator console backend.
Operators are existing admin_users with the seva.operate permission (super_admin or seva_operator role).
Document access is consent-gated: an operator can open a citizen's document ONLY when the citizen
has granted operator_document_access consent for that specific application and not revoked it.
Every operator document view is logged with the consent id used.
Official statuses still pass through seva.set_status's verified-acknowledgement guard, and a
submission can be marked verified only when it carries a real acknowledgement number."""
from .db import now
from . import seva, sevdoc

def _mask(phone):
    p = (phone or "").strip()
    return ("*" * 6 + p[-4:]) if len(p) >= 10 else p

def queue(db, status=None):
    q = """SELECT a.ref_no, a.category_id, a.title, a.status, a.created_at, a.updated_at,
                  u.name AS citizen_name, u.phone AS citizen_phone
           FROM applications a JOIN users u ON u.id=a.user_id"""
    args = ()
    if status:
        q += " WHERE a.status=?"; args = (status,)
    q += " ORDER BY a.updated_at DESC LIMIT 200"
    rows = db.all(q, args)
    for r in rows: r["citizen_phone"] = _mask(r["citizen_phone"])
    return rows

def detail(db, ref):
    a = seva.get_application(db, ref)
    if not a: return None
    u = db.one("SELECT id,name,phone FROM users WHERE id=?", (a["user_id"],))
    p = seva.get_profile(db, a["user_id"]) or {}
    cons = db.one("""SELECT id,granted,revoked_at,ts FROM consent_records
                     WHERE user_id=? AND application_id=? AND scope='operator_document_access'
                     ORDER BY id DESC LIMIT 1""", (a["user_id"], a["id"]))
    docs = db.all("""SELECT ad.document_id, ad.label, ad.status, d.filename, d.kind, d.mime, d.size
                     FROM application_documents ad JOIN seva_documents d ON d.id=ad.document_id
                     WHERE ad.application_id=? AND d.deleted=0""", (a["id"],))
    return {"application": a, "citizen": {"name": u["name"] if u else "", "phone": _mask(u["phone"] if u else ""),
            "state": p.get("state"), "district": p.get("district"), "preferred_lang": p.get("preferred_lang")},
            "documents": docs, "consent": cons, "statuses": seva.STATUSES}

def _notify(db, user_id, app_id, kind, body):
    db.run("INSERT INTO user_notifications(user_id,application_id,kind,channel,body,status,ts) VALUES(?,?,?,?,'inapp',?,?)",
           (user_id, app_id, kind, body, 'sent', now()))

def advance(db, ref, status, note, admin):
    a = db.one("SELECT * FROM applications WHERE ref_no=?", (ref,))
    if not a: return {"ok": False, "error": "not found"}
    r = seva.set_status(db, a["id"], status, "operator:%s" % admin["id"], note or "")
    if r.get("ok"):
        _notify(db, a["user_id"], a["id"], "status_update", "%s: %s" % (ref, status))
    return r

def record_submission(db, ref, portal, method, ack_no, receipt_url, verified, admin):
    a = db.one("SELECT * FROM applications WHERE ref_no=?", (ref,))
    if not a: return {"ok": False, "error": "not found"}
    ack = (ack_no or "").strip()
    # Honesty: only a real acknowledgement number can be called verified. Anything else stays unverified.
    v = 1 if (verified and ack) else 0
    sid = seva.add_submission(db, a["id"], (portal or "").strip()[:120], (method or "guided")[:40], ack[:120],
                              "operator:%s" % admin["id"], receipt_url=(receipt_url or "").strip()[:300], verified=v)
    _notify(db, a["user_id"], a["id"], "submission_recorded", "%s: submission on %s%s" % (ref, portal, " (verified ack)" if v else ""))
    return {"ok": True, "id": sid, "verified": v}

def request_docs(db, ref, admin):
    a = db.one("SELECT * FROM applications WHERE ref_no=?", (ref,))
    if not a: return {"ok": False, "error": "not found"}
    _notify(db, a["user_id"], a["id"], "consent_request",
            "%s: operator requests your consent to view the documents attached to this application" % ref)
    db.audit("operator:%s" % admin["id"], "consent_requested", ref)
    return {"ok": True}

def active_consent(db, user_id, app_id):
    return db.one("""SELECT id FROM consent_records
                     WHERE user_id=? AND application_id=? AND scope='operator_document_access'
                     AND granted=1 AND revoked_at IS NULL ORDER BY id DESC LIMIT 1""", (user_id, app_id))

def doc_file_with_consent(db, env, uploads_root, doc_id, ref, admin):
    a = db.one("SELECT * FROM applications WHERE ref_no=?", (ref,))
    if not a: return None, "not found"
    if not db.one("SELECT id FROM application_documents WHERE application_id=? AND document_id=?", (a["id"], doc_id)):
        return None, "document not attached to this application"
    cons = active_consent(db, a["user_id"], a["id"])
    if not cons: return None, "citizen has not consented to operator document access for this application"
    row = db.one("SELECT * FROM seva_documents WHERE id=? AND deleted=0", (doc_id,))
    if not row: return None, "not found"
    got = sevdoc.read_document(db, env, uploads_root, row, "operator:%s" % admin["id"], consent_id=cons["id"])
    if not got: return None, "file missing"
    db.audit("operator:%s" % admin["id"], "document_view_consented", "%s doc %s" % (ref, doc_id))
    return got, None

def notifications_for(db, user_id):
    return db.all("SELECT id,application_id,kind,body,status,ts FROM user_notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,))

def revoke_consent(db, consent_id, user_id):
    c = db.one("SELECT * FROM consent_records WHERE id=? AND user_id=?", (consent_id, user_id))
    if not c or c["revoked_at"]: return False
    db.run("UPDATE consent_records SET revoked_at=? WHERE id=?", (now(), consent_id))
    db.audit("citizen:%s" % user_id, "consent_revoked", c["scope"])
    return True
