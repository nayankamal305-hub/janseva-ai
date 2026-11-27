# Mobile pre-login ERROR: findings (2026-11-27)
Tested live https://janseva-ai-n00d.onrender.com in Chrome headless, 390x844 mobile UA: first visit, Hindi + dark + lite stored, slow 3G-like throttle, ?lite=1. No JS exception, no failed request except /favicon.ico 404. The page renders. So the error on Kamal's phone was not reproduced; the exact message/phone/browser is still unknown.
Real defects found and fixed (each is a plausible cause on a phone):
1. app.js read localStorage at start with no guard. When storage is blocked (private mode, in-app browser, storage-blocked setting) this throws SecurityError and the whole app dies. Fixed: safe storage shim with in-memory fallback.
2. Old service worker cached ANY response including 502/503 (Render free cold start page) and could keep serving it, and did not clean old caches. Fixed: sw v20 caches only 200 responses, falls back to cache on error, deletes old caches on activate.
3. Render free spins down after ~15 min idle; first request can take 30-60 s or return a Render error page. This is infrastructure, not code. Mitigation: free uptime pinger on /api/health every 5 min (e.g. UptimeRobot), or upgrade plan.
4. If scripts fail to load/run, nothing told the user. Fixed: red bar "Kuch gadbad hui" with a Refresh button that clears old SW and caches; also fires if the app has not booted within 12 s.
5. favicon 404 (harmless) fixed.
