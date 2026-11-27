# Deploy and backup
Local: `python -m app.server`. Docker: `docker build -t jansevaai . && docker run -p 8080:8080 -v jansevadata:/data --env-file .env jansevaai`.
Free host: Render free web service via render.yaml (sleeps when idle; disk is ephemeral, so data resets on redeploy; use a persistent disk or move to Postgres for real use).
Backup: copy the SQLite file with `sqlite3 jansevaai.sqlite3 ".backup backup.sqlite3"` and the uploads folder; restore by putting them back. Migrations run automatically (migrations/*.sql, tracked in schema_migrations).
Android: Actions > android-apk > Run workflow with the deployed URL. Debug APK for sideloading, attached to a GitHub Release. Not a Play Store build.
