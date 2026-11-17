# First-workflow verification

Status: design artifact checks executed; application verification not executed
Owner: engineering lead, with design review

## Design artifact evidence — 2026-11-16

- Fourteen editable frames prepared with shared Material 3 instances and local semantic variables; desktop and narrow-screen layouts.
- Representative screenshots inspected for empty/menu/uploading/completed/recovery/narrow layouts. Corrected New icon, progress paint, failure copy and unknown-outcome state. Prototype navigation targets are checked structurally; this is not a human usability or browser interaction test.
- Seven prototype starting points separate the primary path from recovery cases. Structural inspection found 35 navigation references with no missing destination nodes. Upload timings are simulated. Native picker is a handoff illustration.
- Native design/architecture specs read back after publication. System, data model, lifecycle and sequence diagrams prepared in the existing FigJam file.
- Architecture, API, integrity/security and operations specifications are in Git. No application code, operational scripts or fault tests exist yet.
- Exact nodes and known fidelity limitations: [design index](design-index.md) and [design specification](design-first-upload.md).

## Application gate — all pending

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
