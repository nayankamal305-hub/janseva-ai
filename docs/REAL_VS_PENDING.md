# v0.5: what is real, what is pending (2026-11-27)

## Real today (works with free services, no card)
- Email login with a one-time code. Needs one free SMTP account: Brevo free (300 mails/day) or Gmail app password. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM. Without it, login cannot send codes (test-only JANSEVA_DEV_OTP shows the code on screen; never enable in production).
- Email-to-authority: with the citizen's per-complaint consent, JANSEVA sends the complaint (text, GPS, photo link, tracking ID) from its own mailbox to an email found in the official directory. Target must be in the directory (pgportal nodal officer list or a verified authority). Reply-To uses plus-addressing so replies carry the tracking ID.
- Reply parsing: POST /api/admin/inbound-poll reads the JANSEVA mailbox over IMAP (IMAP_HOST) and adds replies to the complaint timeline. It never marks a complaint resolved.
- Directory (official sources, last verified 2026-11-27):
  - 93 central ministry/department nodal public grievance officers and 37 state/UT nodal officers: https://pgportal.gov.in/Home/NodalPgOfficers and /NodalPgOfficersState
  - 540 sitting Lok Sabha members (https://sansad.in/ls/members) and 244 Rajya Sabha members (https://sansad.in/rs/members) with official sansad emails. Personal phone numbers and home addresses are deliberately not stored.
- v0.6 IGOD directory (National Portal of India, NIC, https://www.india.gov.in/directory/web-directory, verified 2026-11-27): 6,049 state/UT government entries (incl. 36 state/UT portals), 784 district sites (with LGD short names), 4,863 union government entries, 435 legislature and 162 apex-body entries. Websites and contact pages only. Category tags (electricity, water, PWD, municipal, police...) are keyword guesses, labelled heuristic. Endpoints: /api/directory/search|districts|states.
- LGD importer: scripts/import_lgd.py (person downloads the CSV, passes the CAPTCHA).
- Gemini photo classification (server-side key, advisory, fallback to rules).

## Pending authorization or not possible
- SMS OTP: not free in India. Operators require DLT registration (Fast2SMS lists DLT entity registration at Rs 5,900/year; free credit is only a Rs 50 test). Source: https://www.fast2sms.com/help/fast2sms-free-sms/ . Email login is the free route.
- Direct registration on CPGRAMS, Rail Madad, NCH, UMANG: no public citizen API. These stay guided (citizen completes login/OTP/CAPTCHA). The app never bypasses them.
- Swachhata live API: needs ULB-issued credentials.
- A nodal officer email being listed does not prove it accepts citizen complaints (marked unverified). Delivery is shown as "sent, unacknowledged", never as registered.
- Districts/LGD codes: the LGD bulk download is behind a CAPTCHA (not bypassed). A person can download the CSVs from https://lgdirectory.gov.in/downloadDirectory.do and load them. Pincode data: data.gov.in needs a free API key (not available here).
- Contact emails/phones for state PWD, DISCOM, water boards, municipal bodies: IGOD gives websites only, so none are invented; per-body grievance emails need individual verification. MLAs and councillors: not loaded (no single official machine-readable list found).
- Browser-assisted submission by an agent on the citizen's behalf: only with citizen authorization per submission and never past CAPTCHA/OTP (not built).

## WhatsApp login (v0.8, free variant)
User taps "Login with WhatsApp", WhatsApp opens with "JANSEVA LOGIN <code>" to JANSEVA's number, Meta's signed webhook (/api/wa/webhook) delivers it with the sender's number, and the app logs that number in. Off unless WA_NUMBER, WA_VERIFY_TOKEN, WA_APP_SECRET are set. Messages from users to a business are not charged by Meta; JANSEVA sends nothing back, so no per-message cost. Sources: https://developers.facebook.com/docs/whatsapp/pricing ; Mint 2026-10-01; https://adversai.app/guides/whatsapp-business-api-pricing-india-2026

## v1.0 dispatch (email + X)
REAL (needs your env): consented email to PG nodal officers (state L2, central L3) and, only if you type a constituency, your MP (L4); company grievance emails only where officially published (Swiggy, Uber, Amazon, Flipkart, Myntra, BigBasket). Photos attached, your name, reply-to optional. Caps: 3 first emails per complaint, 10 per user/day, global daily cap, dedupe, generic-address blocklist, auto-cancel once resolved. Needs BREVO_API_KEY + MAIL_FROM.
NOT AVAILABLE: MLA, district collector, department-head emails (no official machine-readable source; guided links only). Zomato, Ola, PhonePe, Paytm, MakeMyTrip, IRCTC: no published grievance email found.
X: JANSEVA's own X API posting is paid (~$0.015/post, $0.20 with link), so not built. Citizen gets a prefilled post with official-site-linked handles and posts from their own account. Handles are suggestions, review before posting.
CPGRAMS/Swachhata automation: not shipped (CAPTCHA/OTP are the citizen's; form selectors unmapped). Next: citizen-side userscript after mapping from a logged-in session.
"Sent" never means "registered".
