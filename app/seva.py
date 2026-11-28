"""Seva Setu India - Phase 2 domain layer: profiles, applications, consents, catalog seeds.
Honesty rule enforced here: official statuses (submitted_to_portal and beyond) require a
verified government_submissions row - the platform never claims government registration
without a real acknowledgement number."""
import json, os, secrets, string
from .db import now

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATUSES = ["request_received", "documents_pending", "documents_received", "under_verification",
            "form_preparation", "awaiting_citizen_approval", "ready_for_submission",
            "submitted_to_portal", "government_processing", "additional_info_required",
            "approved", "rejected", "completed"]
# These mean "the government has it" - never set them without a verified submission record.
OFFICIAL_STATUSES = {"submitted_to_portal", "government_processing", "approved", "rejected", "completed"}

SCHEMES_SEED = [
 {"slug": "pm-kisan", "name": "PM-KISAN Samman Nidhi", "names": {"hi": "पीएम-किसान सम्मान निधि"},
  "benefit": "Eligible farmer families get Rs 6,000 per year in three instalments.",
  "eligibility": {"occupation": ["farmer"], "note": "Landholding farmer families; some categories excluded (e.g. income tax payers)."},
  "docs": ["Aadhaar", "Bank account", "Land records"], "link": "https://pmkisan.gov.in",
  "source": "pmkisan.gov.in", "last_verified": "2026-11-28", "state": "all"},
 {"slug": "pmjay", "name": "Ayushman Bharat PM-JAY", "names": {"hi": "आयुष्मान भारत पीएम-जे"},
  "benefit": "Health cover up to Rs 5 lakh per family per year for hospitalisation.",
  "eligibility": {"note": "Families in the SECC/entitled beneficiary list; check on the portal."},
  "docs": ["Aadhaar", "Ration card", "Mobile number"], "link": "https://pmjay.gov.in",
  "source": "pmjay.gov.in", "last_verified": "2026-11-28", "state": "all"},
 {"slug": "nsap-ignoaps", "name": "Indira Gandhi Old Age Pension (NSAP)", "names": {"hi": "इंदिरा गांधी वृद्धावस्था पेंशन"},
  "benefit": "Monthly pension for eligible elderly citizens (BPL).",
  "eligibility": {"age_min": 60, "note": "BPL household, age 60+ (amount varies by age band and state)."},
  "docs": ["Aadhaar", "Age proof", "Bank/post office account"], "link": "https://nsap.nic.in",
  "source": "nsap.nic.in", "last_verified": "2026-11-28", "state": "all"},
 {"slug": "nsp-scholarships", "name": "National Scholarship Portal schemes", "names": {"hi": "राष्ट्रीय छात्रवृत्ति योजनाएं"},
  "benefit": "Central scholarship schemes for students (pre/post matric and more).",
  "eligibility": {"occupation": ["student"], "note": "Varies by scheme: income ceiling and category rules apply."},
  "docs": ["Aadhaar", "Income certificate", "Marksheet", "Bank account"], "link": "https://scholarships.gov.in",
  "source": "scholarships.gov.in", "last_verified": "2026-11-28", "state": "all"},
 {"slug": "eshram", "name": "e-Shram (unorganised workers)", "names": {"hi": "ई-श्रम कार्ड"},
  "benefit": "National database of unorganised workers; gateway to social-security schemes.",
  "eligibility": {"age_min": 16, "age_max": 59, "note": "Unorganised/informal workers."},
  "docs": ["Aadhaar", "Bank account", "Mobile linked to Aadhaar"], "link": "https://eshram.gov.in",
  "source": "eshram.gov.in", "last_verified": "2026-11-28", "state": "all"},
 {"slug": "udyam", "name": "Udyam Registration (MSME)", "names": {"hi": "उद्यम पंजीकरण"},
  "benefit": "Free official MSME registration; access to MSME schemes.",
  "eligibility": {"occupation": ["business"], "note": "Micro, small and medium enterprises."},
  "docs": ["Aadhaar", "PAN", "Business details"], "link": "https://udyamregistration.gov.in",
  "source": "udyamregistration.gov.in", "last_verified": "2026-11-28", "state": "all"}]

STATES_SEED = [("AP","Andhra Pradesh"),("AR","Arunachal Pradesh"),("AS","Assam"),("BR","Bihar"),("CG","Chhattisgarh"),
 ("GA","Goa"),("GJ","Gujarat"),("HR","Haryana"),("HP","Himachal Pradesh"),("JH","Jharkhand"),("KA","Karnataka"),
 ("KL","Kerala"),("MP","Madhya Pradesh"),("MH","Maharashtra"),("MN","Manipur"),("ML","Meghalaya"),("MZ","Mizoram"),
 ("NL","Nagaland"),("OD","Odisha"),("PB","Punjab"),("RJ","Rajasthan"),("SK","Sikkim"),("TN","Tamil Nadu"),
 ("TS","Telangana"),("TR","Tripura"),("UP","Uttar Pradesh"),("UK","Uttarakhand"),("WB","West Bengal"),
 ("AN","Andaman and Nicobar Islands"),("CH","Chandigarh"),("DH","Dadra and Nagar Haveli and Daman and Diu"),
 ("DL","Delhi"),("JK","Jammu and Kashmir"),("LA","Ladakh"),("LD","Lakshadweep"),("PY","Puducherry")]

def seed(db):
    """Idempotent seed of verified catalog data (not demo data - every link carries a verification date)."""
    if not db.one("SELECT id FROM service_categories LIMIT 1"):
        for c in json.load(open(os.path.join(ROOT, "data", "seva_catalog.json"), encoding="utf-8")):
            db.run("INSERT OR IGNORE INTO service_categories(id,icon,names,blurb,links,online,docs,complaint,verified,sort) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (c["id"], c["icon"], json.dumps(c["names"], ensure_ascii=False), json.dumps(c["blurb"], ensure_ascii=False),
                    json.dumps(c["links"], ensure_ascii=False), c["online"], json.dumps(c["docs"], ensure_ascii=False),
                    1 if c.get("complaint") else 0, c["verified"], c["sort"]))
    if not db.one("SELECT id FROM schemes LIMIT 1"):
        for s in SCHEMES_SEED:
            sid = db.run("INSERT INTO schemes(slug,name,names,benefit,eligibility,docs,link,source,last_verified,state) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (s["slug"], s["name"], json.dumps(s["names"], ensure_ascii=False), s["benefit"],
                          json.dumps(s["eligibility"]), json.dumps(s["docs"]), s["link"], s["source"], s["last_verified"], s["state"]))
            for f, rule in s["eligibility"].items():
                db.run("INSERT INTO scheme_eligibility(scheme_id,field,rule) VALUES(?,?,?)", (sid, f, json.dumps(rule)))
    if not db.one("SELECT code FROM seva_states LIMIT 1"):
        for code, name in STATES_SEED:
            db.run("INSERT OR IGNORE INTO seva_states(code,name) VALUES(?,?)", (code, name))

def _dec(row, *fields):
    if row:
        for f in fields:
            if isinstance(row.get(f), str):
                try: row[f] = json.loads(row[f])
                except Exception: pass
    return row

def catalog(db):
    cats = [_dec(c, "names", "blurb", "links", "docs") for c in db.all("SELECT * FROM service_categories ORDER BY sort")]
    schemes = [_dec(s, "names", "eligibility", "docs") for s in db.all("SELECT * FROM schemes WHERE active=1")]
    return {"categories": cats, "schemes": schemes}

# ---- profiles
def get_profile(db, user_id):
    p = db.one("SELECT * FROM citizen_profiles WHERE user_id=?", (user_id,))
    return _dec(p, "a11y") or {}

def upsert_profile(db, user_id, d):
    allowed = {k: d[k] for k in ("preferred_lang", "state", "district", "block", "address", "pincode", "age_group", "occupation") if k in d}
    if "a11y" in d: allowed["a11y"] = json.dumps(d["a11y"])
    if not allowed: return get_profile(db, user_id)
    if db.one("SELECT user_id FROM citizen_profiles WHERE user_id=?", (user_id,)):
        sets = ", ".join("%s=?" % k for k in allowed)
        db.run("UPDATE citizen_profiles SET %s, updated_at=? WHERE user_id=?" % sets, tuple(allowed.values()) + (now(), user_id))
    else:
        cols = ", ".join(["user_id"] + list(allowed)) + ", created_at, updated_at"
        db.run("INSERT INTO citizen_profiles(%s) VALUES(%s)" % (cols, ",".join(["?"] * (len(allowed) + 3))),
               tuple([user_id] + list(allowed.values()) + [now(), now()]))
    db.audit("citizen:%s" % user_id, "profile_updated", ",".join(sorted(allowed)))
    return get_profile(db, user_id)

# ---- applications
def new_ref(db):
    while True:
        ref = "SSI-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        if not db.one("SELECT id FROM applications WHERE ref_no=?", (ref,)): return ref

def create_application(db, user, category_id, title="", service_id=None):
    cat = db.one("SELECT id FROM service_categories WHERE id=?", (category_id,))
    if not cat: return {"ok": False, "error": "unknown category"}
    ref = new_ref(db)
    aid = db.run("INSERT INTO applications(ref_no,user_id,category_id,service_id,title,status,next_action,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                 (ref, user["id"], category_id, service_id, (title or "")[:200], "request_received", "documents_pending", now(), now()))
    db.run("INSERT INTO application_status_history(application_id,status,note,actor,ts) VALUES(?,?,?,?,?)",
           (aid, "request_received", "Application created by citizen", "citizen:%s" % user["id"], now()))
    db.audit("citizen:%s" % user["id"], "application_created", ref)
    return {"ok": True, "ref_no": ref, "id": aid, "status": "request_received"}

def get_application(db, ref, user_id=None):
    a = db.one("SELECT * FROM applications WHERE ref_no=?", (ref,))
    if not a or (user_id is not None and a["user_id"] != user_id): return None
    a["history"] = db.all("SELECT status,note,actor,ts FROM application_status_history WHERE application_id=? ORDER BY id", (a["id"],))
    a["documents"] = db.all("SELECT label,status FROM application_documents WHERE application_id=?", (a["id"],))
    a["submissions"] = db.all("SELECT portal,method,ack_no,verified,ts FROM government_submissions WHERE application_id=?", (a["id"],))
    return a

def list_applications(db, user_id):
    return db.all("SELECT ref_no,category_id,title,status,next_action,created_at,updated_at FROM applications WHERE user_id=? ORDER BY id DESC", (user_id,))

def set_status(db, app_id, status, actor, note=""):
    if status not in STATUSES: return {"ok": False, "error": "unknown status"}
    a = db.one("SELECT * FROM applications WHERE id=?", (app_id,))
    if not a: return {"ok": False, "error": "not found"}
    if status in OFFICIAL_STATUSES:
        sub = db.one("SELECT id FROM government_submissions WHERE application_id=? AND verified=1 AND ack_no IS NOT NULL AND ack_no<>''", (app_id,))
        if not sub:
            return {"ok": False, "error": "official status needs a verified government submission with acknowledgement number"}
    db.run("UPDATE applications SET status=?, updated_at=? WHERE id=?", (status, now(), app_id))
    db.run("INSERT INTO application_status_history(application_id,status,note,actor,ts) VALUES(?,?,?,?,?)",
           (app_id, status, note, actor, now()))
    db.audit(actor, "application_status", "%s->%s" % (a["ref_no"], status))
    return {"ok": True, "status": status}

def add_submission(db, app_id, portal, method, ack_no, submitted_by, receipt_url="", verified=0):
    sid = db.run("INSERT INTO government_submissions(application_id,portal,method,ack_no,receipt_url,submitted_by,verified,ts) VALUES(?,?,?,?,?,?,?,?)",
                 (app_id, portal, method, ack_no, receipt_url, submitted_by, 1 if verified else 0, now()))
    if ack_no:
        db.run("UPDATE applications SET official_ack_no=?, updated_at=? WHERE id=?", (ack_no, now(), app_id))
    return sid

# ---- consents
def record_consent(db, user_id, scope, granted, application_id=None, text_version="v1"):
    cid = db.run("INSERT INTO consent_records(user_id,application_id,scope,granted,text_version,ts) VALUES(?,?,?,?,?,?)",
                 (user_id, application_id, scope, 1 if granted else 0, text_version, now()))
    db.audit("citizen:%s" % user_id, "consent_%s" % ("granted" if granted else "denied"), scope)
    return cid

def consents(db, user_id):
    return db.all("SELECT id,scope,granted,text_version,ts,revoked_at,application_id FROM consent_records WHERE user_id=? ORDER BY id DESC", (user_id,))
