"""Common connector interface. Every government platform is one Connector subclass."""
from dataclasses import dataclass, field

LEVELS = {1: "Full API", 2: "Partial API", 3: "Official guided submission", 4: "Verified email", 5: "Manual assistance"}

@dataclass
class Result:
    ok: bool
    status: str                 # submitted | guided_ready | failed | unauthorized | expired | timeout | rejected | duplicate | queued_sandbox
    external_ref: str = None    # ONLY set when the government system returned it
    method: str = ""
    mode: str = "pending"       # live | sandbox | pending
    message: str = ""
    evidence: dict = field(default_factory=dict)
    http_code: int = None
    guide: dict = None          # for level 3-5: text, link, steps

@dataclass
class StatusResult:
    ok: bool
    status: str = None          # open | assigned | resolved | rejected | unknown
    update: str = ""
    department: str = ""
    raw: dict = field(default_factory=dict)

class Connector:
    id = "base"
    def __init__(self, platform: dict, env=None, transport=None):
        self.p = platform
        self.env = env if env is not None else {}
        self.transport = transport

    @property
    def level(self): return self.p["level"]

    # -- capability checks -------------------------------------------------
    def supported_categories(self): return self.p.get("categories", [])
    def check_jurisdiction(self, c: dict):
        j = self.p.get("jurisdiction", {})
        sc = j.get("scope")
        if sc == "city" and (c.get("city") or "").lower() not in j.get("cities", []):
            return False, "city not covered by this platform"
        if sc == "state" and j.get("states") and (c.get("state") or "").lower() not in j["states"]:
            return False, "state not covered by this platform"
        if j.get("asset_owner") and c.get("asset_owner") != j["asset_owner"]:
            return False, "asset owner is not %s" % j["asset_owner"]
        return True, "ok"
    def check_eligibility(self, c: dict, user: dict):
        return True, "ok"
    def validate(self, c: dict):
        errs = []
        if c.get("lat") is None or c.get("lon") is None or not (6 <= c["lat"] <= 38 and 68 <= c["lon"] <= 98):
            errs.append("invalid or non-Indian location")
        if not c.get("description"): errs.append("description missing")
        return errs
    # -- operations --------------------------------------------------------
    def submit(self, c, user) -> Result: raise NotImplementedError
    def track(self, ref) -> StatusResult: return StatusResult(False, message="tracking not supported") if False else StatusResult(False)
    def appeal(self, ref, reason) -> Result:
        return Result(False, "failed", message="appeal not supported by this platform")
    def comments(self, ref): return []
    def mode(self): return "pending"

def complaint_text(c, user_name=""):
    loc = ", ".join(x for x in [c.get("address"), c.get("city"), c.get("state"), c.get("pincode")] if x)
    return ("Subject: %s\n\nI wish to report the following public issue.\n\n%s\n\nLocation: %s\nGPS: %s, %s\n"
            "Reported via Seva Setu India, complaint %s.\nPhoto: %s\n\nKindly look into this and share the action taken.\n%s"
            % (c.get("title") or c.get("category"), c.get("description"), loc, c.get("lat"), c.get("lon"),
               c.get("code"), c.get("photo_url") or "attached", user_name))
