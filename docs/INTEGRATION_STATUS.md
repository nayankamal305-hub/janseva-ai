# Government integration status (2026-11-27)
No platform is LIVE in this build. Sources are official pages only; "not verified" means no official API document was found.
| Platform | Level | State | Needed to go live |
|---|---|---|---|
| Swachhata | 1 | adapter built from official doc, sandbox mock only | ULB-issued vendor_name + access_key (email support@sbmurban.org with ULB ID/name/state/contact/purpose), then SWACHHATA_LIVE=1 and a real contract test |
| CPGRAMS | 3 | guided (login + OTP by citizen) | authorised API access from DARPG (NextGen CPGRAMS uses Jan Parichay) |
| Rail Madad, NCH, AirSewa | 3 | guided | official API partnership |
| UMANG | 5 | fallback | n/a (no universal grievance API) |
| PMC, NHAI, PWD, DISCOM, state portals, district collector, Jal Board, hospital, school, PCB, transport | 3/5 | unverified directory entries, guided | admin verifies the official URL/API and sets approval_status |
| Department email | 4 | sandbox outbox | verified official grievance email + SMTP |
Authorities and representatives directories start EMPTY. Entries can only be marked verified with an official source_url; nothing is pre-filled from memory.
