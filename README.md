# JANSEVA AI: unified grievance integration engine

One citizen report, routed to the right official channels, tracked in one place. Full-stack Python app (stdlib only, SQLite), web UI, admin Control Center, connector framework, tests, Docker.

> **Honest status.** This build has NO live government credentials. Nothing is sent to a real government system. Records are labelled `live`, `sandbox` or `guided`. Sandbox references come from a local mock server and are never official acknowledgements.
> The "previous JANSEVA AI Master Prompt" features are not included yet (the prompt was not available). The connector layer is built to merge into it.

## Run
```
python -m app.server            # http://localhost:8080 ; admin token printed at start (or set JANSEVA_ADMIN_TOKEN)
python -m unittest discover -s tests -v
docker build -t jansevaai . && docker run -p 8080:8080 jansevaai
```
Free deploy: Render (`render.yaml`, free plan sleeps and SQLite resets on redeploy; use a persistent DB for real use).

## Integration levels (what is real)
| Platform | Level | Status | Source |
|---|---|---|---|
| Swachhata (swachh.city) | 1 | Adapter built from the official doc. Live needs ULB-issued `vendor_name`/`access_key` (email support@sbmurban.org). Sandbox only until then. | https://www.swachh.city/assets/files/Integrate_With_Swachhata_App_V2.2.pdf |
| CPGRAMS | 3 | No public citizen API found. Guided: prefilled text, official portal, citizen enters OTP/login themselves. Email is never used (portal does not accept it). | https://pgportal.gov.in/ |
| Rail Madad | 3 | Guided. | official site |
| National Consumer Helpline | 3 | Guided (Convergence Program is for companies, not citizen apps). | https://consumerhelpline.gov.in/public/convergenceprogram |
| UMANG | 5 | Fallback only, no universal grievance API. | |
| PMC, NHAI, State PWD, DISCOM | 3/5 | Unverified entries, guided. Upgrade only after official API docs are verified. | |
| Department email | 4 | Sandbox outbox only; real send needs a verified official address. | |

Levels: 1 full API, 2 partial API, 3 official guided submission, 4 verified email, 5 manual. Levels 3-5 are never shown as API submissions. Guided references are stored as `citizen_reported` (unverified) and are not synced through any API.

## Architecture
- `app/connectors/base.py`: common interface (categories, jurisdiction, eligibility, validate, submit, track, appeal, comments).
- `app/connectors/swachhata.py`, `guided.py`, `email.py`, `mock_gov.py` (mock server with failure modes: 401, 403, timeout, 500, no-ack, duplicate).
- `data/platforms.json`: registry; admin adds platforms with `POST /api/admin/platforms`, no code change.
- `app/router.py`: classify (EN/HI keywords, swap for a vision/LLM model later), ULB lookup (`data/ulbs.json` is SAMPLE data), asset owner (asks when unknown), per-platform category + jurisdiction + validation, avoids duplicate government complaints.
- `app/service.py`: parent complaint, linked external records, timeline, status sync, escalation, analytics, Control Center.
- `app/server.py`: HTTP API + UI. `migrations/001_init.sql`: schema.

## Rules enforced (and tested)
Consent to submit and separate consent to share personal data; no fake acknowledgement (no id returned = failed); duplicate complaint block (same user, category, 100 m, 7 days); parent resolved only when ALL linked official records are resolved, then citizen verification; escalation uses a platform's real appeal route, otherwise a reminder explicitly marked "not an official appeal"; analytics count unique citizen complaints separately from external records; credentials only from environment variables, never in the DB; every integration call and admin action logged; no CAPTCHA/OTP bypass.

## v0.2 adds
Pincode prefix lookup (sample), Hindi toggle on key UI labels, more registry entries (AirSewa, state portal, district collector, Jal Board, hospital, school, pollution board, transport: all unverified, guided), Android APK workflow `.github/workflows/apk.yml` (wraps the DEPLOYED URL; needs a deployed backend; debug APK, sideload only, build not yet verified).

## Not done yet
Credential vault with encryption at rest (env vars only now), photo AI classification, ward/pincode jurisdiction data, real SMTP, webhooks (none documented by the platforms), the old master-prompt features.
