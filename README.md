# JANSEVA AI: unified grievance integration engine

One citizen report, routed to the right official channels, tracked in one place. Full-stack Python app (stdlib only, SQLite), web UI, admin Control Center, connector framework, tests, Docker.

> **Honest status.** This build has NO live government credentials. Nothing is sent to a real government system. Records are labelled `live`, `sandbox` or `guided`. Sandbox references come from a local mock server and are never official acknowledgements.
> v0.3 merges the original JANSEVA master prompt (citizen app, AI analysis, routing, escalation, public dashboard, before/after verification, roles, assistant, emergency, privacy) with the unified connector engine. Stack deviation: Python stdlib + SQLite + vanilla JS PWA instead of Next.js/FastAPI/Postgres+PostGIS/Redis/Expo, so it runs on free hosts with no installs. The schema and API are plain and portable to Postgres/FastAPI later.

## Run
```
python -m app.server            # http://localhost:8080 ; admin token printed at start
python -m unittest discover -s tests -v    # 48 tests
```
Docs: docs/INTEGRATION_STATUS.md, docs/SECURITY.md, docs/DEPLOY.md, docs/API.md, .env.example.

## Feature status (honest)
| Area | Status |
|---|---|
| OTP login, roles, scoped admin, audit, consent, account deletion, rate limit, upload checks | built and tested (no SMS provider) |
| Report flow: photo upload, GPS, AI analysis, category confirmation, routing explanation, consent, submit | built; AI is a text-only rules engine (no vision model, needs a model key) |
| Routing: ULB lookup, road owner asked not guessed, jurisdiction check, four separate authority fields from a verified directory, human verification queue | built; directories start empty, nothing invented |
| Connectors L1-L5, Swachhata adapter, registry, Control Center | built; sandbox only |
| 14-status lifecycle, Authority Marked Resolved vs Citizen Verified Resolved, after-photo, reopen, appeal route | built and tested |
| Duplicate grouping by location+category, merge without second gov complaint, community support | built (geo only; no image similarity) |
| Public dashboard, feed, heatmap, filters, monthly CSV, privacy rules | built (state/city level; no ward/district polygons, overdue and cost metrics not computed) |
| Escalation: 7 configurable levels, official appeal vs reminder | built (no sending of reminders; deadlines are configured, not statutory) |
| Assistant (EN/HI) and letter generator | rule-based, not an LLM, no other languages yet |
| Emergency: 112 notice and emergency flag | built |
| Android APK | workflow written, build NOT yet verified |
| Voice input/TTS, offline drafts, FCM push, email/SMS delivery, face blur, image similarity, PostGIS, all-India authority and representative data, live deployment | NOT done |

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

