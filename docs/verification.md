# First-workflow verification

Status: local automated acceptance passes; human usability and screen-reader review pending
Owner: engineering lead, with design review

## File-actions acceptance — 2026-11-17

The original upload gate passed in `run-ro484rat` before feature implementation. The expanded suite passed in `run-r7_t4ebg` and the final rerun `run-13alt54i` under `~/Library/Application Support/Drive MVP Verification/` (report and logs retained privately outside Git). This supersedes the earlier runtime-blocked notes below; they remain historical evidence.

- PASS: four frontend recovery tests and production TypeScript/Vite build; ten backup integrity unit tests.
- PASS: migration drift check and 23 Django/PostgreSQL tests, including owner isolation, CSRF, invalid names, unchanged identity/content/quota, stale revisions and trash/restore.
- PASS: 82 HTTP acceptance assertions and seven real Chromium browser tests. New browser coverage verifies exact download bytes/name, keyboard menu/dialog operation, rename, trash/reload/restore, narrow layout, invalid names, download failure, stale-tab conflicts and a committed trash update with a lost response.
- PASS: application/database restart and backup/isolated restore. Ten files, including a retained trashed fixture, preserve metadata across both; backup verification checks all committed blob bytes.
- REVIEWED: desktop rename and narrow navigation browser screenshots; editable R3 Figma action/rename/trash compositions. These are not a pixel-exact or accessibility conformance claim.
- NOT RUN: human usability, screen-reader review, multi-browser acceptance, power-loss testing.

The pre-commit review rerun `run-sf0lppmv` also passes the full suite. Desktop rename and narrow Trash screenshots were reviewed again. The run reports record the base Git revision and dirty-tree state before the file-actions commit. Test credentials, uploaded fixtures, screenshots and backup data remain outside Git. See [file-actions contract](workflows/file-actions.md).

## Local setup evidence — 2026-11-17

The user-run verification at `run-kkx0d79p` installed the dependencies and design assets. Its saved report/log confirms PASS for the frontend build/recovery tests, ten backup tests, PostgreSQL initialization and migration drift, all eighteen backend tests, 82 real HTTP assertions, and four Chromium browser tests. Desktop and narrow screenshots were saved from the actual running application.

The run stopped during restart persistence: the launcher's plain socket bind probe reported a port conflict after a clean stop. Waitress uses SO_REUSEADDR, but the probe did not, so recently closed connections could cause a false conflict. The redundant probe has been removed; the actual server bind/readiness remains authoritative. Setup now reuses installed prerequisites instead of downloading them again when available. This fix passes syntax/static checks; the restart and backup/restore gates still need the corrected user-run verification. The coding sandbox continues to reject socket binding with EPERM.

The normal user account/data directory was not initialized because setup correctly stopped before those remaining gates. No live application URL is claimed yet.

## Implementation evidence — 2026-11-16

- PASS: React/TypeScript production build; four recovery-policy unit tests.
- PASS: ten backup-manifest/integrity unit tests; backend and tooling syntax compilation; shell syntax and Git whitespace checks.
- AUTHORED, NOT RUN: eighteen Django/PostgreSQL tests, independent HTTP acceptance and four real-browser tests, schema drift, full app/database restart, backup and isolated restore.
- BLOCKED: package/Figma-asset downloads fail DNS in this sandbox; local server bind was rejected with EPERM. There is no real-browser or running-app success evidence. SVG/font assets are not yet available locally.
- Prepared `Set Up Drive.command` to install, verify in disposable databases and then launch. `scripts/verify.py` writes a per-run report with exact Git revision and dirty-tree status; it stops on the first failing gate.
- No production-readiness, capacity, power-loss durability, human usability or screen-reader conformance claim is made.

## Design artifact evidence — 2026-11-16

- Fourteen editable frames prepared with shared Material 3 instances and local semantic variables; desktop and narrow-screen layouts.
- Representative screenshots inspected for empty/menu/uploading/completed/recovery/narrow layouts. Corrected New icon, progress paint, failure copy and unknown-outcome state. Prototype navigation targets are checked structurally; this is not a human usability or browser interaction test.
- Seven prototype starting points separate the primary path from recovery cases. Structural inspection found 35 navigation references with no missing destination nodes. Upload timings are simulated. Native picker is a handoff illustration.
- Native design/architecture specs read back after publication. System, data model, lifecycle and sequence diagrams prepared in the existing FigJam file.
- Architecture, API, integrity/security and operations specifications are in Git. The statements in this design-artifact subsection describe the preceding design pass; implementation evidence is recorded above.
- Exact nodes and known fidelity limitations: [design index](design-index.md) and [design specification](design-first-upload.md).

## Original application checklist — historical

Automated results above supersede the original unchecked execution status below. Human usability and screen-reader checks remain pending.

- [ ] First-time user discovers New → File upload without coaching.
- [ ] Menu and picker path works with keyboard; cancellation restores focus.
- [ ] Progress is truthful; completion waits for durable finalization.
- [ ] Download/integrity probe matches the original file checksum.
- [ ] File persists after refresh and local service restart.
- [ ] Another fixture identity cannot list, read, overwrite, or finalize the owner's file.
- [ ] Double submission and retries do not duplicate effects or quota charges.
- [ ] Lost connection and service failure between bytes and metadata have safe recovery.
- [ ] File-size and storage limits are enforced by the server.
- [ ] Failed list load is distinct from an empty drive.
- [ ] Screen-reader status and focus behavior are reviewed.
- [ ] Database plus file contents restore successfully into a clean local environment.
- [ ] Provider migration is rehearsed before any actual hosting migration.

For each executed check, record date, implementation commit, environment, test/evidence link, and result. Unchecked items are not verified. Never mark the whole workflow complete from a successful happy-path demo alone.
