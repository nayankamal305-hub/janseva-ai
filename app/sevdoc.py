"""Seva Setu India - Phase 4: citizen document vault.
Documents are private: bytes are served ONLY through the authenticated /api/seva/documents/<id>/file
endpoint (never the public /uploads route), ownership-checked per request, and every read is logged
in document_access_logs. Deletes are soft (row kept for audit; storage object remains but unreachable).
No malware scan in this build - honest note returned on upload."""
import hashlib, os
from .db import now
from . import storage

MAX_DOC = 5 * 1024 * 1024
DOC_MAGIC = [(b"\xff\xd8\xff", "jpg", "image/jpeg"), (b"\x89PNG", "png", "image/png"), (b"%PDF", "pdf", "application/pdf")]
DOC_KINDS = ["aadhaar", "pan", "ration_card", "voter_id", "driving_licence", "passport", "land_record",
             "income_proof", "caste_certificate", "birth_certificate", "bank_passbook", "photo", "other"]

def _store(env, uploads_root):
    return storage.from_env(env, uploads_root)

def save_document(db, env, uploads_root, user, filename, data, label=""):
    if not data: return {"ok": False, "error": "empty file"}
    if len(data) > MAX_DOC: return {"ok": False, "error": "file too large (max 5 MB)"}
    kind = next(((ext, mime) for magic, ext, mime in DOC_MAGIC if data.startswith(magic)), None)
    if not kind: return {"ok": False, "error": "only real JPEG, PNG or PDF files are accepted"}
    ext, mime = kind
    digest = hashlib.sha256(data).hexdigest()
    name = "doc-%s.%s" % (digest[:32], ext)
    try:
        _store(env, uploads_root).put(name, data, mime)
    except Exception:
        return {"ok": False, "error": "document storage unavailable, try again"}
    label = (label or "").strip()[:60] or "other"
    if label not in DOC_KINDS: label = "other"
    fn = (filename or "").strip()[:120] or ("document." + ext)
    did = db.run("INSERT INTO seva_documents(user_id,kind,filename,mime,size,storage_key,sha256,created_at,deleted) VALUES(?,?,?,?,?,?,?,?,0)",
                 (user["id"], label, fn, mime, len(data), name, digest, now()))
    db.run("INSERT INTO document_access_logs(document_id,actor,actor_role,action,consent_id,ts) VALUES(?,?,?,?,NULL,?)",
           (did, "citizen:%s" % user["id"], "citizen", "upload", now()))
    db.audit("citizen:%s" % user["id"], "document_uploaded", "%s:%s" % (label, fn))
    return {"ok": True, "id": did, "kind": label, "filename": fn, "mime": mime, "size": len(data),
            "note": "Stored privately - only you (and operators you consent to) can open it. No malware scan in this build."}

def list_documents(db, user_id):
    return db.all("SELECT id,kind,filename,mime,size,created_at FROM seva_documents WHERE user_id=? AND deleted=0 ORDER BY id DESC", (user_id,))

def get_document(db, doc_id, user_id):
    return db.one("SELECT * FROM seva_documents WHERE id=? AND user_id=? AND deleted=0", (doc_id, user_id))

def read_document(db, env, uploads_root, row, actor):
    got = _store(env, uploads_root).get(row["storage_key"])
    if not got: return None
    db.run("INSERT INTO document_access_logs(document_id,actor,actor_role,action,consent_id,ts) VALUES(?,?,?,?,NULL,?)",
           (row["id"], actor, actor.split(":")[0] if ":" in actor else "citizen", "view", now()))
    return got[0], row["mime"], row["filename"]

def delete_document(db, doc_id, user_id):
    row = get_document(db, doc_id, user_id)
    if not row: return False
    db.run("UPDATE seva_documents SET deleted=1 WHERE id=?", (doc_id,))
    db.run("DELETE FROM application_documents WHERE document_id=?", (doc_id,))
    db.run("INSERT INTO document_access_logs(document_id,actor,actor_role,action,consent_id,ts) VALUES(?,?,?,?,NULL,?)",
           (doc_id, "citizen:%s" % user_id, "citizen", "delete", now()))
    db.audit("citizen:%s" % user_id, "document_deleted", row["filename"])
    return True

def attach_document(db, app_row, doc_id, user, label=""):
    """Attach a vault document to one of the citizen's own applications. Auto-advances the honest
    internal status to documents_received (a Seva Setu status, not a government one)."""
    from . import seva
    doc = get_document(db, doc_id, user["id"])
    if not doc: return {"ok": False, "error": "document not found"}
    if db.one("SELECT id FROM application_documents WHERE application_id=? AND document_id=?", (app_row["id"], doc_id)):
        return {"ok": False, "error": "already attached"}
    db.run("INSERT INTO application_documents(application_id,document_id,label,status) VALUES(?,?,?,?)",
           (app_row["id"], doc_id, (label or doc["kind"])[:60], "received"))
    if app_row["status"] in ("request_received", "documents_pending"):
        seva.set_status(db, app_row["id"], "documents_received", "citizen:%s" % user["id"], "document attached")
    db.audit("citizen:%s" % user["id"], "document_attached", "%s->%s" % (doc["filename"], app_row["ref_no"]))
    return {"ok": True}
