# First-workflow verification

Status: not executed; application does not exist yet
Owner: engineering lead, with design review

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
