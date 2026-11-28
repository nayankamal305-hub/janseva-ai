ROLES = ["super_admin", "state_admin", "district_admin", "department_admin", "verification_officer", "public_viewer", "seva_operator"]
PERMS = {
 "super_admin": {"*"},
 "seva_operator": {"seva.operate"},
 "state_admin": {"complaints.view", "complaints.reroute", "authorities.edit", "escalation.run", "reports.view"},
 "district_admin": {"complaints.view", "complaints.reroute", "escalation.run", "reports.view"},
 "department_admin": {"complaints.view", "complaints.reroute"},
 "verification_officer": {"complaints.view", "verification.review", "photos.approve"},
 "public_viewer": {"reports.view"},
}
def can(role, perm): return "*" in PERMS.get(role, set()) or perm in PERMS.get(role, set())
def in_scope(admin, c):
    if admin["role"] == "super_admin": return True
    if admin.get("scope_state") and (c.get("state") or "") != admin["scope_state"].lower(): return False
    if admin.get("scope_city") and (c.get("city") or "") != admin["scope_city"].lower(): return False
    return True
