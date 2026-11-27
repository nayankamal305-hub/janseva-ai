"""Level 4: only for verified official grievance emails. Sandbox writes to the outbox table; a real SMTP send needs
SMTP_* env and email_verified=true on the platform. Delivery is not a registration."""
from .base import Connector, Result, complaint_text
class EmailConnector(Connector):
    id = "email"
    def mode(self): return "live" if (self.env.get("SMTP_HOST") and self.p.get("email_verified")) else "sandbox"
    def submit(self, c, user):
        if self.mode() == "live":
            return Result(False, "failed", method="email", mode="live", message="SMTP sending not enabled in this build")
        return Result(True, "queued_sandbox", None, "email", "sandbox", "queued in sandbox outbox, nothing sent",
                      {"to": self.p.get("email_target"), "body": complaint_text(c, user.get("name", ""))})
