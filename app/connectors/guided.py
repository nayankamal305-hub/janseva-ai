"""Levels 3 and 5: nothing is submitted. We prepare the official text and the steps, the citizen submits on the
official portal, then enters the reference. Such records are labelled citizen-reported, never 'API submitted'."""
from .base import Connector, Result, StatusResult, complaint_text
class GuidedConnector(Connector):
    id = "guided"
    def mode(self): return "guided"
    def submit(self, c, user):
        guide = {"portal": self.p.get("url"), "steps": self.p.get("steps", []),
                 "complaint_text": complaint_text(c, user.get("name", "")),
                 "email_note": "Do NOT email this to the portal; email is not an official registration." if self.p.get("email_accepted") is False else ""}
        return Result(True, "guided_ready", None, "guided", "guided", "Prepared for official submission by the citizen", {"prepared": True}, None, guide)
    def track(self, ref):
        return StatusResult(False, update="No permitted status API. Check the official portal with your reference.")
