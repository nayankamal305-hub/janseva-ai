# JANSEVA v2.0 self-audit against Kamal's requirements (2026-11-27)
DONE = built and tested in code. PARTIAL = built, with a stated limit. MISSING = not built. "Needs keys" = code done, runs only once env keys exist.

| # | Requirement | Status | Note |
|---|---|---|---|
| 1 | Complaint reaches every accountable authority | PARTIAL | Email ladder L1 guided body, L2 state PG officer (all 36 states/UTs tested), L3 central ministry PG officer, L4 MP (typed constituency). Needs keys (Brevo). No MLA/collector/dept-head emails exist officially. |
| 2 | Email with photos, user's name, reply-to, tracking ID | DONE (needs keys) | Mock-tested; not live-tested with Brevo. |
| 3 | Reminders + escalation ladder | NOT SENDING | 7/15 day timers are configured and rows queued, but JANSEVA sends no email (citizen sends from own mail). Reminders are not promised in the UI. |
| 4 | Private companies via official grievance email | PARTIAL | 6 companies with published email. Zomato, Ola, PhonePe, Paytm, MakeMyTrip, IRCTC: none found. |
| 5 | X tag with consent, official handles only | PARTIAL | Queue, poster API, caps, spacing, validation done. Poster not run by me; X automation-rule suspension risk. 866 handles; coverage uneven (see docs/COVERAGE.md). No MP/MLA handles from official data. |
| 6 | Post-on-X fallback | DONE | |
| 7 | JANSEVA Rating | DONE | MPs, ministries, state cells. MLAs/collectors not listed (no official dataset). |
| 8 | CPGRAMS-like umbrella flow | PARTIAL | Guided filing with copy-text + reference + citizen-reported status. Auto login/fill NOT built (CAPTCHA/OTP, unmapped selectors). |
| 9 | Email OTP login, WhatsApp login | DONE (needs keys) | |
| 10 | Full India data, all states/UTs | PARTIAL | IGOD 6,049 entries, 784 districts, 36/36 states have PG officer; handle crawl reached ~47% of 4,559 official sites. Rajasthan, Assam, Mizoram, Tripura, Gujarat, AP, Odisha, WB, Karnataka low (geo-block/WAF/timeouts). Archive-snapshot pass started, NOT finished (archive rate-limits). |
| 11 | Nearby-duplicate prompt, 3-step filing, timeline | DONE | |
| 12 | Premium UI | PARTIAL | Navy+saffron, mobile-first; no new screenshots this round; native review of translations pending. |
| 13 | Gemini AI classification | PARTIAL | Code done; live call never tested; key must be in Render env. |
| 14 | Fix upstream JS scope bug, boot last, versioned script, JS lint/smoke test | DONE | IIFE closes at end, boot runs last, app.js?v=12, sw cache v12, tests/js/smoke.js + tests/test_js.py. NOTE: GitHub agent repo commit 343b6ab not available to me, so I did my own fix; please diff/rebase. |
| 15 | Yes answers: 22-language UI | MISSING | 9 shipped languages only. |
| 16 | Yes answers: low-data mode | MISSING | PWA manifest + service worker exist; no data-saver mode. |
| 17 | Yes answers: pincode/GPS MP auto-detect | MISSING | Needs an official boundary dataset. |
| 18 | Yes answers: MLAs/collectors partial rating | MISSING | |
| 19 | Postgres port (SQLite resets on Render free) | MISSING | Needs external Postgres. |
| 20 | Coverage report per state/UT | DONE | docs/COVERAGE.md, /api/coverage. |

## Update v2.1
- 22-language UI: PARTIAL. Now 17 UI languages (en, hi, mr, bn, ta, te, gu, kn + ml, or, pa, ur, as, ne, sa, mai, kok). Core labels only, machine translated, banner says "not reviewed". Still missing of the 22 scheduled: Bodo, Dogri, Kashmiri, Manipuri, Santali, Sindhi.
- Low-data mode: DONE (Lite button, also auto on save-data/2g): no map tiles, photos at 50% quality, no animation. PWA manifest + service worker unchanged.
- Header fits 390 px phones; nav label fixed. Screenshots: ui13_*.png.
- MP auto-detect from pincode/GPS: NOT built (no official boundary data). MLA/collector partial rating: NOT built.
- X daily cap 4.

## Update v2.4
- Rating now also lists ~780 district administration offices (official district site as source; no officer names, partial). MLAs still not listed (no official dataset).
- MP selection: constituency picker (datalist from sansad.in, filtered by state). Auto-detect from pincode/GPS still NOT built (no official boundary data).
- 6 languages (Bodo, Dogri, Kashmiri, Manipuri, Santali, Sindhi) NOT added: I cannot translate them reliably, need native translators.

## v2.5 MLA rating
- Added MLA entities from official state portal tables: Bihar 243, Telangana 119, Uttarakhand 70, Nagaland 60 (fetched 2026-11-27, source URL per row). See data/mla_coverage.json.
- Not covered: all other states. Tried and failed: Rajasthan, Tamil Nadu (unreachable), Goa (503), Haryana (404), Delhi (PDF), Puducherry (script page), ECI results (script-rendered). Not yet attempted: remaining states.
- Pages may lag by-elections; no mobile numbers imported.

## v2.6 MLA all states + public landing + mobile error fix
- MLAs: 4101 sitting MLAs, all 31 states/UTs, from India Vote Kar MLA Register (CC BY 4.0, attribution: India Vote Kar, https://www.indiavotekar.com/datasets/mla-register/), 22 vacant seats not listed. Bihar/Telangana/Uttarakhand/Nagaland cross-checked with official portal tables. Details: data/mla_coverage.json. By-election lag possible. No MLA phone/email imported.
- Public landing page for logged-out users (stats, how it works, sample flow, rating preview). Logged-in home unchanged.
- Mobile ERROR hardening: see docs/MOBILE_ERROR_RCA.md.

## v2.8 login fix + local bodies
- Login bug: stale token in storage (server DB reset) made openLogin() go to My Complaints and the sheet never opened. Fixed: any 401 clears the session; openLogin() validates a stored token first; boot validates it. tests/js/login.js covers logged-out, stale token, blocked storage, valid token (the stale-token case fails on the old app.js).
- Local bodies: data/ulbs_official.json = 5,156 ULBs (332 municipal corporations, municipalities, nagar/town panchayats, cantonment boards) from MoHUA PMAY-Urban list. No contacts in that list. 9 rows dropped (names unreadable in PDF). 4,447 "planning authority" rows skipped.
- Rating directory now has Local bodies + state departments/boards/discoms (utility_contacts, official-site sourced).
- Routing: route preview shows the concerned local body by city+state (matched / ambiguous / not found). It is guided, not auto-sent, as no official email is on file.
- Gram panchayats NOT loaded (LGD download is CAPTCHA; ~2.6 lakh rows).

## v2.9 ULB sites/emails + dark mode
- data/ulb_contacts.json: 136 municipal corporations with an official gov.in/nic.in website found (60 are the ULB's own site, rest are district-site listings or state CDMA portal pages, flagged by website_kind). 11 have a published email read from the official homepage/contact page (found_on per email). Method: web search, then homepage + up to 2 contact pages, robots.txt respected. accepts_citizen_complaints stays "unverified".
- Dispatch L1 for garbage/drainage/toilet (and municipal roads) now uses the matched city ULB's published email first (consent rules unchanged).
- Caveat: the PMAY list's "Municipal Corporation" type includes many census-town units (e.g. in Tamil Nadu), so 331 is not the count of real corporations. Type is shown as listed.
- Dark mode fixes for Nearby and My Complaints.

## v3.0 Kerala municipalities
- Source: Kerala LSGD directory of local body websites (https://lsgkerala.gov.in/en/website/web), fetched 2026-11-27. Each municipality homepage read once; emails are as printed there (mostly secretary mailboxes, some gmail). 70 more ULBs added to data/ulb_contacts.json (206 total).
- 17 Kerala municipality sites not matched to the PMAY list by name or no email; skipped, not guessed. 34 gram panchayat/block emails were found on the same directory but NOT imported (rural bodies are not routed yet).

## v3.1 District-portal municipality directories (MP, TN, UP, Karnataka, Telangana)
- District NIC portals publish a "Municipalities" page with each ULB's email. Domain guesses ({district}.nic.in / .gov.in / state subdomain) were accepted only if the page loaded and was an official government district page. Names matched to the PMAY list within the same state and district only.
- 29 entries whose email did not resemble the body name (source-side mix-ups, e.g. Chidambaram listed with another town's address) and personal-looking gmail ids were dropped. Districts not reached: those renamed or without a standard page (Telangana 10/31, UP 40/75, TN 24/38, Karnataka 15/31, MP 38/55 found).
- Emails are as the official page prints them; accepts_citizen_complaints stays "unverified".

## v3.2 more district portals
- Same method for Punjab, Rajasthan, Gujarat, Maharashtra, Bihar, Odisha, WB, Chhattisgarh, Uttarakhand, HP, Haryana, Jharkhand, Assam. Few standard district pages found (Odisha 0/30, Rajasthan 1/50, HP 1/10); those states need their own urban-department portals. +39 emails, 60 entries dropped by the name-resemblance filter.

## v3.3 Maharashtra deep dive
- Official source 1: Maharashtra DMA contact PDF https://www.ulbdataportal.in/uploads/Contacts_ULB.pdf (407 councils/nagar panchayats with email, Marathi). Names are garbled in text extraction, so rows were matched to the PMAY list by email-name similarity >= 0.95, unique match only: 221 new rows + 12 existing rows updated. Unmatched (~125) are not guessed (renamed towns, spelling gaps, duplicate names like Karanja/Kalamb).
- Official source 2: Urban Development Dept corporation directory (website column) https://urban.maharashtra.gov.in/organization/... used for 27 corporation websites; homepage + contact pages read (robots respected). Only corporation-looking emails kept (Malegaon, Sangli-Miraj, Chh. Sambhajinagar, Panvel); personal-looking gmail ids and placeholder example.com were dropped. Many corporation sites (Thane, KDMC, Nashik, PCMC, Pune, Kolhapur, Akola, Ahmednagar) did not load from here.
- UI: route preview now handles bodies with an email but no website.

## v3.5
- Problem-density map (state, then district on tap). Real counts only, placed by each complaint's own coordinates; unlocated counted separately; SAMPLE toggle labelled; honest empty state. Boundaries: LGD via bharatlas (see docs/GEO_SOURCES.md). Saffron ramp, dark mode ramp.
- Contacts: +17 UP Nagar Nigam (https://localbodies.up.nic.in/listnn.htm), Patna Municipal Commissioner email (https://betastate.bihar.gov.in/urban/KeyContacts).
- Skipped: Gujarat district-page emails (misaligned with body names), Odisha (0/30 pages loaded), Rajasthan (1/50), HP (1/10).
- Not verified: Nearby and Dashboard mounts were wired in code but not screenshot-checked; lite mode not checked.

## v3.6
- Rajasthan: 212 ULB Raj-mail IDs from the LSG Department official list (https://department.rajasthan.gov.in/pages/sm/department-page/371474/2380, fetched 2026-11-27), each matched uniquely by name to the MoHUA list. 91 rows in the department list did not match (new ULBs or spelling differences) and are NOT imported; no fuzzy guessing. These are department-published official mail IDs, used only per-complaint with consent.

## v3.7
- West Bengal: municipality emails from the UD&MA Department list https://udma.wb.gov.in/Main/urban_local_bodies (fetched 2026-11-27; emails are published as [at]/[dot] and decoded). Listed against the chairperson/municipality; unique name match to MoHUA list only. Unmatched rows are not imported.
- Bihar: https://biharsulm.in/index.php/sulm/executive_Officers lists officers and phones but no emails, so nothing imported.
- Jharkhand: 32 ULB emails from https://udhd.jharkhand.gov.in/Other/ULBInformation.aspx (UD&HD official page, fetched 2026-11-27); 11 rows unmatched/ambiguous to MoHUA list, not imported.
- Chhattisgarh: 118 ULB emails from the UAD contact report https://uad.cg.gov.in/ContactUAD/ContactUsEnglishReportPage.aspx (fetched 2026-11-27); 75 unmatched/ambiguous, not imported. Emails are as published (some are gmail/rediffmail addresses the department lists for the CMO).
- Found but not imported yet: Assam DMA contact PDF (messy multi-line table), Uttarakhand UDD list (names only, no emails), Odisha HUD directory (officials only).
- Assam: 48 ULB emails from the DMA Assam contact list PDF https://dma.assam.gov.in/sites/default/files/swf_utility_folder/departments/dma_medhassu_in_oid_5/do_u_want_2_know/Contact%20list%20of%20ULBs.pdf (fetched 2026-11-27); 26 rows unmatched/duplicates, not imported (e.g. GMC, abbreviations M.B./T.C.).
- Himachal Pradesh: emails from https://ud.hp.gov.in/municipalities-at-a-glance/contact-details-of-ulbs ; Tripura: https://tulm.tripura.gov.in/ulb-details (both fetched 2026-11-27, unique name match to MoHUA list; unmatched rows not imported). J&K HUDD, Nagaland, Manipur, South Goa pages checked: no emails published.

## v3.12 password login
- Email/mobile + password login (scrypt, 16-byte random salt per user, stdlib). OTP only for first signup and Forgot password; OTP-only login kept as an optional tab. Endpoints: POST /api/auth/signup, /api/auth/reset (OTP code + new password), /api/auth/login. Min 8 chars, common-password blocklist.
- Rate limit: 5 wrong attempts per account or per IP locks for 15 minutes (table login_attempts, migration 008). Unknown user and wrong password give the same answer; a dummy hash check keeps timing similar. A successful reset unlocks the account.
- Existing users have no password until they use Forgot password / Create account with OTP once; their OTP login still works.
- Known limits: the session token is still the existing per-user token (no expiry/rotation); IP rate limit uses the socket address, so behind a proxy (Render) it sees the proxy IP unless X-Forwarded-For is handled: please check, the per-account limit still works.
- Small db.py changes: login_attempts conflict key; test guard also accepts local unix-socket Postgres (host=/path).

## v3.13 desktop layout
- At 760px and wider the page uses the full window: content centred and capped at 1480px, hero and top bar full-bleed (was a 1040px column that looked cut on laptops). Mobile layout unchanged. Checked at 1366x768 and 1920x1080 (home, dashboard, report). Login sheet: Send OTP now sits above the main button.

## v3.14
- Logo (original J mark: white J, saffron dot, navy gradient; no state emblem) in app/static/brand/: favicon.ico, 16/32 png, svg, apple-touch (180), PWA 192/512 + maskable, og.png 1200x630. Wired in index.html, /favicon.ico, /apple-touch-icon.png, manifest. og:image gets an absolute URL from PUBLIC_URL or the request Host/X-Forwarded-Proto. scripts/make_brand.py regenerates the PNGs.
- Visual polish (CSS only): softer shadows, card hover, saffron accent on stat tiles, icon chips on card titles, focus rings, staggered fade-in, floating hero ring, blurred bottom nav, shimmer skeletons. Respects prefers-reduced-motion and lite mode.
- Fixes: client IP for rate limiting is proxy-aware when TRUST_PROXY=1 (set it on Render); password reset/signup rotates the session token so old sessions end.
- v3.14.1 session expiry: tokens expire after 30 days of inactivity (sliding; migration 009 users.token_exp). Real login keeps a still-valid token (other devices stay signed in) and rotates only when expired; password reset/signup always rotates. Tokens issued before this get an expiry on first use. Admin tokens are separate and unchanged.

## v3.15: filing from the citizen's own email, official-portal handoffs, mobile fit
- Complaint emails are no longer sent from the server by default (`JANSEVA_SERVER_EMAIL=1` re-enables the old behaviour). A server cannot send as a user's own Gmail/Yahoo address (SPF/DKIM/DMARC), so the app opens Gmail web, Outlook web or the mail app with To/Subject/body filled, and the citizen presses Send. OTP emails still come from the server.
- `GET /api/complaints/<id>/filing` returns the letter, the verified official email targets (each with source URL and date) with compose links, and portal handoff packs (CPGRAMS, Swachhata, Meri Panchayat for rural, plus city/state portals from data/platforms.json). `GET .../letter-html` is a printable official-style letter (Save as PDF). `POST .../filing-mark` records "I sent it" or "I filed it" with a citizen-typed registration number. These are stored in `filing_records` (migration 010) as citizen-entered and never as "registered".
- No portal is auto-submitted. CPGRAMS (pgportal.gov.in) has no public submit API, needs the citizen's own login and security code, and does not accept email. Swachhata is app + mobile OTP; its integration API is for official city apps only. Meri Panchayat is an app with login and in-app geo-tagged photo.
- Letter includes the citizen's name/contact only if they allowed sharing, and only the details the account actually holds.
- Mobile: appbar overflowed at 360px (page width became 378). Fixed; checked home/report/mine/nearby/dash/rating/dir/assist/pub at 360 (scrollWidth == 360).

## v3.16: one-screen filing
Portal research: no documented URL-prefill for CPGRAMS, Swachhata or Meri Panchayat; CPGRAMS needs a registered login (https://pgportal.gov.in/Home/LodgeGrievance). So the screen shows the best official portal for the complaint first (copy full text, open official site, native Share, field-by-field copy, citizen-entered registration number), other portals and own-email below, and `GET /api/portal-guide` + "Which portal for what" lists the official link per complaint type. No bookmarklet/auto-fill (untestable without a real login, breaks on portal change, not available on most phones). QR hand-off to phone not built.
- v3.16 add-on: 'Email officers + your MP in one tap' (officers in To, citizen-chosen Lok Sabha MP in Cc, official sansad.in email with source). MLA emails: none in a verified source, so none listed. Post on X / public map / rating shortcuts in the same screen.

## v3.17
Filing is never blocked by the old same-user/same-category/100 m/7-day duplicate check (it returned an error). create_complaint now returns optional similar_nearby (same category, 250 m, 30 days, any user) and the UI shows 'Support it'. The only other limiter is the per-token API rate limit (120 requests/min).

## v3.18: AI quick report
`app/llm.py`: speak/type -> draft (title, description, category, severity, language, road owner, department from our fixed map) via free-tier Gemini (GEMINI_API_KEY) or Groq (GROQ_API_KEY), tried in that order. Falls back to the rule classifier (now with Hinglish/Hindi keywords) on no key, 429/5xx (60 s cooldown), timeout, bad JSON or unknown category. Output is validated, URLs/emails/phones stripped, injected extra fields dropped, rule-detected emergencies never lowered, 30 drafts/user/day (AI_DRAFT_DAILY). The citizen confirms with two explicit ticks; nothing is registered otherwise. Photo goes to the AI only if ticked. Voice = browser Web Speech API (Chrome/Edge send audio to Google; unsupported on some browsers, typing always works). Place: GPS + OpenStreetMap Nominatim reverse geocode in the browser. Untested against live Gemini/Groq (no key available in build); tested with mocked transports.

## v3.19
submit no longer reports a saved complaint as failed: when routing needs more info (road owner unknown, or no verified channel) the API returns ok:true, waiting:true with the needs text; UI shows 'Saved. One detail left' with owner buttons. submit accepts asset_owner. AI card asks road owner.

## v3.20
aiConfirm kept the AI category before clearing it (was posting category:null to /confirm); confirm_category rejects null/empty/unknown; /api/directory/constituencies import fix.

## v3.21: wording matches verified behaviour
Status vocabulary: Saved in JANSEVA -> Ready to send / open official portal -> Sent by you (self-reported) / Filed by you (number typed by you) -> Registered only with a real authority reference. UI no longer promises official email/portal/X sending or 7/15-day reminders. X posting is off unless JANSEVA_X_AUTOPOST=1. Acceptance: tests/test_nosend.py (all consents ticked, no email sent, no X queued, nothing registered, wording scan).
