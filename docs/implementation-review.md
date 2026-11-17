# First-upload implementation review

Date: 2026-11-16 · Owner: independent quality/security review
Status: original review retained below; local automated acceptance now passes (2026-11-17). See [current evidence](verification.md) and [file-actions extension](workflows/file-actions.md). Human review remains pending.

## Review scope

One authenticated user uploads one private file. Review includes another fixture identity to verify isolation, real PostgreSQL concurrency, content integrity and recovery. It does not establish public-hosting capacity, zero defects, power-loss durability or accessibility conformance.

## Early review findings

- CSRF bootstrap must work on the unauthenticated session response; sign-in must remain CSRF-protected.
- A lost upload-initiation response is ambiguous too. Preserve its idempotency key and reconcile; do not mint a new key automatically.
- A failed or expired writer must never finalize or fail a newer attempt. Check its generation under the same lock order used by quota and recovery.
- Never retain a previous account's filename/content after an account switch. Browser persistence should hold opaque identifiers scoped to the owner.
- The storage loop's elapsed-time check cannot interrupt a blocked socket read. The selected HTTP server also needs a finite read timeout.
- The UI must distinguish failed list loading from an empty drive and distinguish bytes sent from saved contents.

These points were sent to implementation owners before integration. Code review also found invalid Unicode filenames producing server errors, a successful-login throttle deletion race, and known quota/device errors becoming indefinite “checking” states. Implementation owners corrected these paths. They still require execution against PostgreSQL and a browser before being marked verified.

## Automated acceptance artifacts

- `tests/api_acceptance.py`: independent HTTP exercise with two disposable identities; authentication/CSRF, unsafe metadata, idempotency, per-owner concurrency, exact download/checksum, owner isolation, interrupted-length retry, spent attempts, logout.
- `tests/first-upload.spec.cjs`: browser keyboard menu/focus, real file picker upload, exact retrieval, dismiss/refresh, lost successful PUT response, failed list recovery and narrow layout.
- `tests/playwright.config.ts`: local Chromium configuration, one worker, artifacts outside Git.
- `scripts/backup.py`: consistent PostgreSQL snapshot plus referenced blobs, checksum verification, and restoration into a new isolated local cluster. `tests/test_backup.py` verifies corruption/path/no-overwrite guards independently of PostgreSQL.

Both suites require disposable test accounts and a disposable local database/data directory. They create test files. Credentials are supplied through `DRIVE_TEST_USER_A`, `DRIVE_TEST_PASSWORD_A`, `DRIVE_TEST_USER_B`, `DRIVE_TEST_PASSWORD_B`; `DRIVE_TEST_BASE_URL` defaults to `http://127.0.0.1:8000`. Browser tests use account B. No production credentials are embedded in tests.

Commands after the test instance is running:

```sh
python3 tests/api_acceptance.py
npm --prefix frontend run test:e2e
```

## Evidence ledger

| Check | Result | Evidence |
| --- | --- | --- |
| API acceptance script syntax | PASS | `python3 -m py_compile tests/api_acceptance.py` |
| Browser test syntax | PASS | `node --check tests/first-upload.spec.cjs` |
| Backup integrity guards | PASS | Ten tests via `python3 -m unittest discover -s tests -p 'test_backup.py' -v` |
| Real HTTP acceptance | Pending | Requires running disposable test instance |
| Browser acceptance | Blocked | Local preview bind on 127.0.0.1:8014 rejected with `PermissionError: [Errno 1] Operation not permitted`; no preview server started |
| Backend fault/concurrency tests | Pending | Implementation owner supplies results |
| Restart persistence and backup restore | Pending | Integration owner supplies results |
| Human usability and screen-reader review | Pending | Cannot infer from automated checks |

Only executed checks belong in the pass column. A mocked transport failure may exercise browser recovery against a real successful server write; it does not simulate all OS/process failure modes.

## Backup and restore commands

With the app stopped, use `.venv/bin/python scripts/backup.py create --destination <new-directory-outside-git>`. This requires no active uploads or application database sessions, holds the launcher's exclusive maintenance lock, locks tables against writes, and exports the same PostgreSQL snapshot used for its file manifest. A completed backup publishes its manifest last; partial output must not be treated as a backup.

`.venv/bin/python scripts/backup.py verify <backup-directory>` checks dump and blob checksums; it does not prove the dump can be restored. `.venv/bin/python scripts/backup.py restore <backup-directory> --destination <new-local-home> --pg-port 55433 --app-port 8001` creates an isolated cluster, restores metadata/bytes, verifies identities/checksums/quota accounting, invalidates old sessions, and stops the restored cluster. It never replaces the original directory. Actual creation/restoration has not yet run here.
