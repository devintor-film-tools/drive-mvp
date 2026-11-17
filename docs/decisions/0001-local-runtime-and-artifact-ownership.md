# ADR 0001: Local runtime and artifact ownership

Date: 2026-11-16
Status: partially superseded by ADR 0002 for visual artifacts; local runtime and GitHub decisions remain accepted; repository publication pending
Owner: engineering lead

## Decision

Run all application services locally. Use GitHub for version control and personal Google Drive for design sources, references, prototypes, and reviewed exports. No external application hosting or application data storage is authorized by this decision.

Alternatives considered: local runtime and hosted free tier. The user selected local runtime. A private GitHub repository is the implementation default, not a public publishing decision.

## Consequences

Local software must work without a cloud runtime dependency. Any identity solution must support local testing. Runtime services should bind to loopback by default. Remote collaborators cannot use the running app without a separate access decision. Local availability is not production availability.

The source repository does not back up uploaded contents or the database. A separate local backup and restoration procedure is required before using valuable files. Local backups on the same machine do not protect against loss of the machine.

## Future migration requirements

Use stable application IDs, versioned schema migrations, explicit storage-provider boundaries, and environment-based configuration. Document identity portability and session implications. Rehearse migration with database records and object bytes, verifying ownership, counts, checksums, and access. Define cutover and rollback before moving real data.

Database, storage, authentication, framework, and container-runtime choices remain proposed until evaluated. This decision does not select Supabase or another vendor.
