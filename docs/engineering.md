# Engineering foundation

Date: 2026-11-16
Status: requirements only; implementation architecture not yet selected
Owner: engineering lead

## Required artifacts for the first workflow

1. System diagram: browser, application, identity, database, storage; distinguish trust and process boundaries.
2. Data model: ownership, file metadata, upload sessions, constraints, lifecycle; schema migrations are authoritative.
3. Sequence diagram: authorization, upload, verification, metadata finalization, response; include failure windows.
4. State diagram: permitted upload transitions and recovery after interruption.
5. API schemas: validation, errors, retry keys, authorization, concurrency, and capability semantics.
6. Security model: cross-user access, unsafe filenames, quota enforcement, secret handling, direct object access.
7. Runbook: reproducible local setup, persistent data paths outside Git, start/stop, backup, restore, and migration rehearsal.

Create and maintain these at the depth needed for the first workflow. Avoid speculative service decomposition.

## Migration contract

Preserve application IDs and ownership; do not store provider URLs as file identity. Keep provider-specific storage operations behind a narrow module. Test adapters against actual provider behavior when introduced. Database export is not a backup of object bytes. Port authentication explicitly; a provider change may require reauthentication.

## Operational boundaries

No cloud application runtime, public tunnel, paid subscription, or usage-billed service. Runtime listeners should default to loopback. GitHub and Google Drive are development-artifact services, not application dependencies. No automated GitHub workflows are configured initially.

## Documentation maintenance

Update affected contracts and diagrams in the same code review as the change. Record owner, status, and last verified revision. Keep decision history; mark superseded decisions rather than rewriting history. Link the reviewed Drive artifact revision from implementation changes.
