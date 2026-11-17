# First-upload architecture and integrity contract

Date: 2026-11-16 · Status: proposed specification; no runtime exists
Owner: engineering lead · Decision: [ADR 0003](../decisions/0003-first-upload-architecture.md)

## Boundaries

Browser → same-origin Django API → PostgreSQL and private local storage. React assets are served from the application origin in the packaged local build; the development server proxies API requests to avoid a second authentication origin. All runtime listeners bind loopback. Application storage is outside the repository and outside public static/media roots.

Django modules: accounts, files, uploads, storage. Modules share a deployment and database. The BlobStore boundary exposes stage/write, publish immutable object, open/read, inspect, and remove-unreferenced-object operations; it exposes no public provider URL. DB models own identity and authorization. The browser cannot choose a storage path.

## Data model

| Entity | Key fields and constraints |
| --- | --- |
| User | UUID primary key; Django credentials/session integration |
| StorageAccount | user unique FK; used_bytes, reserved_bytes, quota_bytes; nonnegative counters; used + reserved ≤ quota |
| Upload | UUID; owner FK; client_key; display_name; expected_bytes; state; expires_at; unique(owner, client_key) |
| UploadAttempt | UUID; upload FK; server lease generation; lease_until; actual_bytes; sha256; opaque blob_key; state |
| File | UUID; owner FK; upload unique FK; successful_attempt unique FK; display_name; byte_size; sha256; blob_key unique; created_at |

Only committed File rows appear in My Drive. Metadata consistency checks ensure File owner equals Upload owner and the successful attempt belongs to that upload. Enforce these through transaction-scoped writes and integration tests; use composite database constraints where practical in the implementation migration. Never assume separate foreign keys enforce this equality.

One partial unique constraint on Upload.owner for CREATED, RECEIVING, VERIFYING enforces one active upload across tabs/processes. RETRYABLE does not occupy the active slot or retain quota. Filename is a display label, never a path. Separate deliberate uploads with the same name create distinct files; a transport retry cannot.

## State transitions

CREATED → RECEIVING → VERIFYING → COMPLETE.
CREATED/RECEIVING/VERIFYING → RETRYABLE on confirmed failure or expired lease.
RETRYABLE → RECEIVING after a new attempt successfully reserves quota and the active slot.
RETRYABLE → EXPIRED after 24 hours without progress. A stale CREATED session first passes through lease reconciliation to RETRYABLE. COMPLETE and EXPIRED are terminal.

CREATED holds a 120-second initiation lease. RECEIVING/VERIFYING use a 120-second lease renewed at most every 15 seconds while work continues. Time is server-owned. Retry is allowed only after failure/expiry is transactionally confirmed. A browser timeout is not a server state transition. Expired active attempts first become RETRYABLE and release reservation; old attempts are fenced from publication/finalization. Reconciliation must re-read the lease under a row lock before expiring it.

## Protocol and invariants

1. Authenticate and authorize every request. POST creates or returns an upload using a client UUID idempotency key. Validate filename, positive size, 100 MiB limit and quota. Lock StorageAccount and then Upload consistently; reserve the declared bytes and claim the single active slot. Same key with different metadata returns conflict.
2. PUT claims a new client-generated attempt UUID under the same lock order. Stream bytes to an opaque staging object. Count actual bytes and compute SHA-256 incrementally; stop at the declared size or limit. Do not hold a database transaction for the byte transfer. Persist/renew the fenced lease with short transactions. Replayed/concurrent active attempt requests do not start another writer.
3. Verify actual length equals declared length. Flush and fsync the file, publish to a unique immutable object key on the same filesystem, and synchronize the containing directory where supported. Prototype the exact durability operations on the supported OS/filesystem before claiming power-loss durability. `os.fsync` is documented in [Python's OS reference](https://docs.python.org/3/library/os.html#os.fsync).
4. In one short transaction, recheck lease generation, ownership, state and reservation; create the unique File row; move reserved bytes to used bytes; mark Upload/Attempt COMPLETE. Commit only after storage publication succeeds. Readers see either no file or a fully finalized file. PostgreSQL and filesystem do **not** share a transaction.
5. Return File only after commit. If the response is lost, GET upload status returns the existing File. The client reconciles before retrying. An old or expired writer cannot finalize even if its bytes finish arriving later.
6. On confirmed failure, mark RETRYABLE and release the reservation once. A retry rechecks quota/concurrency and uses a new attempt UUID under the same Upload UUID. A completed request always returns its existing result. Expired sessions require a new upload; the UI says so explicitly.

## Crash windows

| Window | Visible result | Recovery |
| --- | --- | --- |
| Before reservation commit | No upload | Retry POST with same client key |
| During staging | No File row | Reconcile lease; retry whole file when eligible |
| After durable publication, before DB commit | No File row; possible orphan blob | Retry creates a new fenced attempt; maintenance removes old unreferenced blob after grace |
| After DB commit, before response | File already saved | GET status returns COMPLETE; no retransmission |
| Stale writer resumes after lease expiry | Its result cannot become visible | Reject finalization by generation/state; later collect orphan |
| Storage loss after success | Integrity incident, not an empty file | Fail read clearly; restore from verified backup; never silently manufacture success |

Cleanup takes the same account/upload locks, checks current lease and File references, and only removes unpublished/unreferenced objects after a 24-hour grace period. Cleanup and finalization must not race: quarantine eligible objects under the guard, then remove; a fenced writer cannot later reference them. Include this race in fault tests. Never delete an object referenced by a File row.

## Security and resource controls

Use Django sessions, HttpOnly cookies, CSRF protection and owner-scoped queries. Secure cookies/TLS become mandatory for any non-loopback deployment. Unauthenticated API calls return JSON 401, not an HTML login page. Other users' object IDs return 404. Reject path separators, control characters, dot-only names and overlong filenames; encode names safely for display/download headers. Do not trust MIME type or browser length. Stream with bounded memory, bounded request time and disk-space headroom. Configure upload buffering/temporary storage deliberately; Django defaults alone are not the resource budget.

Downloads pass through authorization and use attachment disposition and nosniff. There is no public blob route, inline rendering, public signup, or share link. Request logs contain request/upload IDs and outcome codes, not file bytes, cookies, or sensitive filenames. Two fixture identities are mandatory in isolation tests despite the one-user UX scope.

## Scaling boundary

This is a proposed foundation, not a proven scalable implementation. The single-active-upload rule is per owner, not global. Multiple owners may upload concurrently within measured local limits. Horizontal app scaling waits for shared object storage and tested shared sessions. Keep providers behind contracts, but test real destination behavior; interface similarity alone is insufficient.
