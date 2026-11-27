# Postgres port plan (free options only). Not implemented yet.

## Why
Render free web service resets its disk on every deploy/restart, so SQLite data and uploaded photos are lost. A hosted Postgres plus object storage fixes both.

## Free options (checked 2026-11-27 on vendor pages)
| Option | Free limit | Catch |
|---|---|---|
| Neon (neon.com) | 1 GB per project, 100 CU-hours per project (neon.com/faqs/free-plan-limits-and-quotas, neon.com/blog/neon-free-plan-1-gb-per-project) | Compute scales to zero, first query after idle is slow. Best fit. |
| Supabase (supabase.com) | Free Postgres | Free projects pause after 7 days of low activity (supabase.com/docs/guides/platform/free-project-pausing). Needs a keep-alive. |
| Render Postgres | Free | Expires 30 days after creation (render.com/changelog/free-postgresql-instances-now-expire-after-30-days-previously-90). Not suitable. |
Recommendation: Neon free for the DB. For photos use free object storage (Cloudflare R2 or Supabase Storage); limits to be verified before choosing.

## Code work (estimate 1 to 2 days)
1. app/db.py is 67 lines and wraps sqlite3. Add a driver switch on DATABASE_URL: psycopg (needs `pip install psycopg[binary]`, the only non-stdlib dependency, added only when DATABASE_URL is set).
2. Placeholders: sqlite uses `?`, Postgres uses `%s`. Convert inside DB wrapper.
3. SQL differences to fix (grep shows ~14 spots): AUTOINCREMENT -> GENERATED ... IDENTITY, INSERT OR IGNORE/REPLACE -> ON CONFLICT, datetime()/strftime() -> to_char/now(), last_insert_rowid -> RETURNING id. Files: dispatch.py, rating.py, service.py, social.py, accounts.py, migrations 005-007.
4. Migrations: keep one .sql per version, with a Postgres dialect variant, applied by a schema_migrations table.
5. Uploads: store blobs in object storage, keep only the key in DB. Serve via signed or proxied URL.
6. Tests: run the same suite twice (SQLite and a throwaway Postgres in CI or local).
7. Data move: none needed yet (sandbox data only).

## Risks
- Neon cold start adds 1 to 3 s on first request after idle.
- Free tiers change; re-check limits at migration time.
- Needs Kamal to create the Neon account and put DATABASE_URL in the Render env (a secret, never in chat or repo).
