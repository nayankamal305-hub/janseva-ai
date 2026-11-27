"""Swachhata adapter built from the official Integrate_With_Swachhata_App_V2.2.pdf.
Endpoints used (documented): POST {base}/sbm/v1/post-complaint, GET {base}/sbm/v1/getComplaints.
Live mode needs env SWACHHATA_VENDOR_NAME / SWACHHATA_ACCESS_KEY issued per ULB.
No credentials -> sandbox against the local mock server. Sandbox never produces official references."""
import json, socket, urllib.parse, urllib.request, urllib.error
from .base import Connector, Result, StatusResult

CATEGORY_MAP = {  # doc category list -> categoryId
    "dead_animal": 1, "dustbin": 2, "garbage": 3, "garbage_vehicle": 4, "sweeping": 5,
    "toilet_electricity": 6, "toilet_water": 7, "toilet_blockage": 8, "toilet": 9,
    "open_manhole": 10, "drainage": 11, "sewage_overflow": 11, "stagnant_water": 12, "septage": 13,
    "debris": 14, "garbage_burning": 15, "open_defecation": 16, "septic_overflow": 26,
    "urination_spot": 27, "dirty_spot": 28, "unsafe_manhole": 29, "sanitation": 28}
STATUS_MAP = {1: "open", 3: "assigned", 4: "resolved", 6: "rejected"}
LIVE_BASE = "https://api.swachh.city"

class SwachhataConnector(Connector):
    id = "swachhata"
    def __init__(self, platform, env=None, transport=None, sandbox_base=None):
        super().__init__(platform, env, transport)
        self.sandbox_base = sandbox_base
    def creds(self):
        return self.env.get("SWACHHATA_VENDOR_NAME"), self.env.get("SWACHHATA_ACCESS_KEY")
    def mode(self):
        v, k = self.creds()
        if v and k and self.env.get("SWACHHATA_LIVE") == "1": return "live"
        return "sandbox" if self.sandbox_base else "pending"
    def base(self):
        return LIVE_BASE if self.mode() == "live" else self.sandbox_base
    def category_id(self, c):
        return CATEGORY_MAP.get(c.get("sub_category") or c.get("category"))
    def check_jurisdiction(self, c):
        if not c.get("ulb_id"): return False, "location is not in an identified ULB"
        if not c.get("ulb_swachhata"): return False, "ULB not onboarded on Swachhata"
        return True, "ok"
    def validate(self, c):
        errs = super().validate(c)
        if not c.get("photo_url"): errs.append("photo required by Swachhata (file URL)")
        if self.category_id(c) is None: errs.append("category not in Swachhata category list")
        return errs
    def _call(self, method, path, params, timeout=3):
        url = self.base() + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try: body = json.loads(e.read() or b"{}")
            except Exception: body = {}
            return e.code, body
        except (socket.timeout, TimeoutError):
            return 0, {"error": "timeout"}
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)): return 0, {"error": "timeout"}
            return -1, {"error": str(e.reason)}
    def submit(self, c, user):
        if self.mode() == "pending":
            return Result(False, "failed", method="api", mode="pending", message="no credentials and no sandbox configured")
        v, k = self.creds()
        params = dict(vendor_name=v or "demo", access_key=k or "demo123", mobileNumber=user["phone"][-10:],
                      categoryId=self.category_id(c), complaintLatitude=c["lat"], complaintLongitude=c["lon"],
                      complaintLocation=c.get("address") or c.get("city"), complaintLandmark=c.get("landmark") or c.get("address") or "NA",
                      fullName=user.get("name") or "Citizen", userLatitude=c["lat"], userLongitude=c["lon"],
                      userLocation=c.get("address") or c.get("city"), deviceOs="external", file=c["photo_url"])
        code, body = self._call("POST", "/sbm/v1/post-complaint", params)
        mode = self.mode()
        ev = {"http_code": code, "response": body}
        if code in (200, 201) and body.get("complaint", {}).get("generic_id"):
            return Result(True, "submitted", body["complaint"]["generic_id"], "api", mode, body.get("message", ""), ev, code)
        if code == 0: return Result(False, "timeout", method="api", mode=mode, message="API timeout", evidence=ev, http_code=0)
        if code == 401: return Result(False, "unauthorized", method="api", mode=mode, message="credentials rejected", evidence=ev, http_code=code)
        if code == 403: return Result(False, "expired", method="api", mode=mode, message="credentials expired", evidence=ev, http_code=code)
        if code == 409: return Result(False, "duplicate", method="api", mode=mode, message="duplicate reported by platform", evidence=ev, http_code=code)
        if code == 201 or code == 200:   # success code but no reference: never claim registration
            return Result(False, "failed", method="api", mode=mode, message="no acknowledgement id returned", evidence=ev, http_code=code)
        return Result(False, "failed", method="api", mode=mode, message=str(body.get("message", "API error")), evidence=ev, http_code=code)
    def track(self, ref):
        v, k = self.creds()
        cid = "".join(ch for ch in ref.split("C", 1)[-1] if ch.isdigit()) if "C" in ref else ref
        code, body = self._call("GET", "/sbm/v1/getComplaints", dict(vendor_name=v or "demo", access_key=k or "demo123", complaintId=cid))
        if code != 200: return StatusResult(False, update="status call failed (%s)" % code)
        items = body.get("complaints") or body.get("data") or []
        if not items: return StatusResult(False, update="no record returned")
        it = items[0]
        st = STATUS_MAP.get(int(it.get("status", 0)), "unknown")
        return StatusResult(True, st, it.get("comment") or it.get("remarks") or "", it.get("department", "ULB"), it)
