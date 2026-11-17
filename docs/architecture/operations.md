# Local operation and migration plan

Date: 2026-11-16 · Status: local scripts implemented; full runtime rehearsal pending
Owner: engineering lead

## Implemented commands

On this Mac, open `Set Up Drive.command`. It runs the prerequisites installer, npm's locked install, and `scripts/verify.py`, then launches local-account setup only after the automated gates pass. It requires network access for packages/assets and permission to run local servers. The coding sandbox currently denies both, so this route must run from the user's Terminal.

`Start Drive.command` handles subsequent starts. The app binds 127.0.0.1:8000; its separate project-owned PostgreSQL 18 cluster binds 127.0.0.1:55432. No Homebrew service is registered. Ctrl-C stops the owned app process. Stop its database separately with `python3 scripts/local.py stop-db`. The normal app uses a non-superuser database role; only setup, isolated tests and backups use the cluster administrator.

Configuration is generated as mode-0600 `local.json` under mode-0700 `~/Library/Application Support/Drive MVP`. It holds random DB passwords and the Django signing secret. `DRIVE_LOCAL_HOME` can select another external data directory; the scripts reject paths inside Git. Python 3.12–3.14 is selected by the Mac launchers; the existing machine has 3.14.2. Database binaries can be supplied with `DRIVE_PG_BIN`.

Direct commands from the repository:

```sh
python3 scripts/local.py setup
python3 scripts/local.py start --open-browser
python3 scripts/local.py status
python3 scripts/local.py test
python3 scripts/local.py manage reconcile_uploads --cleanup
```

The backend test command uses a disposable Django test database. Full `Verify Drive.command` uses an entirely separate cluster, data directory, random fixture credentials and ports. It runs schema-drift checks, backend tests, real HTTP/browser acceptance, database/app restart integrity, backup and restore. Reports include source revision/dirty-tree status and live under `~/Library/Application Support/Drive MVP Verification/run-*/report.json`; logs and browser artifacts are alongside them. Verification data is retained for inspection and never committed.

## Backup commands

Stop the app before maintenance. Backups acquire the same exclusive maintenance lock as setup; a running launcher holds a shared lock. Backup additionally rejects live app DB connections, locks application tables against writes, exports a PostgreSQL snapshot, and copies only committed File blobs with checksum verification.

```sh
.venv/bin/python scripts/backup.py create --destination /absolute/path/outside-git/backup-001
.venv/bin/python scripts/backup.py verify /absolute/path/outside-git/backup-001
.venv/bin/python scripts/backup.py restore /absolute/path/outside-git/backup-001 --destination /absolute/new/restore-directory
```

Restore refuses existing destinations. It creates an isolated cluster on default port 55433, restores database/schema, checks file metadata/checksums and quota accounting, invalidates old sessions and leaves the restored cluster stopped. The command prints the exact launch command for that separate environment. Checksum verification alone does not prove database restoration; the full verification harness must pass the restore and authenticated-read gates.

Ten backup-integrity unit tests pass. A real backup/restore has not run in the restricted session. Backups contain user data and password hashes; their private filesystem permissions do not replace encryption or protection against physical disk loss.

## Local setup deliverable

The implemented launchers provide setup/start and preflight missing dependencies/assets, data location and app-port conflicts. Do not claim reproducibility until setup runs from a clean checkout. Docker is not required. Frontend dependencies have a complete npm lock; backend requirements currently pin direct dependencies, and a fully resolved hash lock remains a release gate after dependency installation.

The local launcher supplies environment variables directly from the external private configuration; no checked-in or generated `.env` is required. Backend environment variables are `DATABASE_URL`, `DRIVE_DATA_DIR` and `DRIVE_SECRET_KEY`; direct callers must provide them securely. Runtime data has separate Postgres, HTTP-temporary, staging, object and backup directories. Paths come from configuration, not hardcoded usernames. Versioned migrations initialize schema; account passwords are read through a secure prompt and never command arguments.

The start command launches local app/database dependencies, runs a readiness check, and prints a single browser link. The stop command drains or explicitly terminates upload attempts and closes services cleanly. The application detects stale leases on startup; maintenance is also runnable manually. Health checks distinguish API liveness, DB readiness, and writable storage. No app data enters GitHub.

## Backup and restore gate

Pause new writes, drain/reconcile in-flight uploads, create a consistent PostgreSQL dump and copy all referenced immutable blobs with a checksum manifest, then resume. Record schema version and application revision. Encrypt backups where appropriate for the local threat model; do not store secrets alongside an unprotected backup. Restore into a separate clean data directory, compare owner/file counts and all referenced checksums, authenticate, list and fetch a fixture file. A dump without bytes is incomplete. A backup on the same disk does not protect against loss of that disk.

## Migration rehearsal

1. Implement destination BlobStore and run contract tests against that actual service.
2. Provision a test destination; preserve database primary keys, owner relationships and object keys.
3. Quiesce writes, copy DB and objects, compare manifest/checksums and quotas, run authorization and retrieval checks.
4. Switch configuration only after validation. Keep source read-only until acceptance.
5. Roll back by pointing to the original snapshot only before destination writes resume. After new writes, reconcile them explicitly; do not pretend an old snapshot is a lossless rollback.

Before any public launch: add production TLS/cookie configuration, credential recovery, monitoring, backup retention and restore targets, abuse/resource controls, deployment rollback and measured load targets. These are launch gates, not extra first-upload product features.

## File-actions upgrade — 2026-11-17

The complete local acceptance suite now passes, including restart and backup/restore; earlier pending/environment statements above are historical. Stop the app, run `.venv/bin/python scripts/local.py manage migrate --noinput`, run `npm --prefix frontend run build`, then open `Start Drive.command`. Migration 0004 adds nullable trash timestamps and revision counters without moving or deleting uploaded contents. Backups retain active and trashed files.

The app port comes from `app_port` in the private external `local.json` (default 8000). If another service owns that port, choose an available local port in that configuration while Drive is stopped. A 200 response at `/` is insufficient readiness evidence: verify `/api/health` returns Drive's `{"status":"ok"}` and `/` returns the frontend HTML, not another service's health JSON.
