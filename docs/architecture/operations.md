# Local operation and migration plan

Date: 2026-11-16 · Status: requirements; commands/scripts not implemented
Owner: engineering lead

## Local setup deliverable

Implementation must provide one documented setup command, one start command, and a preflight that checks installed versions, available ports, writable data directories, and disk headroom. Recommend an installation path after detecting this machine's existing tools; do not require paid services or assume Docker Desktop licensing. Do not claim reproducibility until setup runs from a clean checkout.

Keep configuration in a documented `.env.example`; real secrets in an ignored local file. Runtime data should live under an explicit user-owned directory outside Git, with separate Postgres, staging, object and backup directories. Paths come from configuration, not hardcoded usernames. Restrict filesystem access to the local user. Lock dependencies, use versioned migrations, and seed credentials through a secure prompt.

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
