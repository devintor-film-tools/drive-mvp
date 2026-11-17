# Engineering foundation

Date: 2026-11-16
Status: architecture proposal A recommended; application not implemented
Owner: engineering lead

## Prepared technical package

- [Three architecture proposals and recommendation](decisions/0003-first-upload-architecture.md)
- [Boundaries, data model, lifecycle, integrity and security](architecture/first-upload.md)
- [HTTP API and recovery contract](architecture/api.md)
- [Local setup, backup/restore and migration requirements](architecture/operations.md)
- [Interface behavior and accessibility specification](design-first-upload.md)

Explanatory system, data model, lifecycle and sequence diagrams are in FigJam; exact nodes are listed in the [design index](design-index.md). These specifications are proposed. Database migrations, executable API schemas and operational scripts will be created and validated with the first implementation.

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

Update affected contracts and diagram references in the same code review as the change. Record owner, status, and last verified revision. Keep decision history; mark superseded decisions rather than rewriting history. Link the reviewed Figma/FigJam artifact revision from implementation changes using the active workspace links in the design index. Preserve existing Drive baseline links as historical references. Engineering contracts remain authoritative in Git; FigJam diagrams explain those contracts and must be updated when their sources change.
