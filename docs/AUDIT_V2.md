# JANSEVA v2.0 self-audit against Kamal's requirements (2026-11-27)
DONE = built and tested in code. PARTIAL = built, with a stated limit. MISSING = not built. "Needs keys" = code done, runs only once env keys exist.

| # | Requirement | Status | Note |
|---|---|---|---|
| 1 | Complaint reaches every accountable authority | PARTIAL | Email ladder L1 guided body, L2 state PG officer (all 36 states/UTs tested), L3 central ministry PG officer, L4 MP (typed constituency). Needs keys (Brevo). No MLA/collector/dept-head emails exist officially. |
| 2 | Email with photos, user's name, reply-to, tracking ID | DONE (needs keys) | Mock-tested; not live-tested with Brevo. |
| 3 | Reminders + escalation ladder | DONE | 7/15 day timers, auto-cancel on resolve. Hourly tick. |
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
