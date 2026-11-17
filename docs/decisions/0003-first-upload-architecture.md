# ADR 0003: First-upload architecture

Date: 2026-11-16 · Status: recommended for the first implementation, not implemented
Owner: engineering lead · Scope: one private file upload

## Three proposals

| Proposal | Local foundation | Main benefit | Cost or limitation |
| --- | --- | --- | --- |
| **A — recommended** | React/TypeScript UI, Django 5.2 LTS, PostgreSQL, private local filesystem | Established identity and transaction primitives; small local operating footprint; explicit storage boundary | We must implement and test crash recovery across database and filesystem |
| B | Same application and database, with local SeaweedFS S3 storage | Exercises an object-storage API from the beginning | Another service and storage lifecycle to operate; S3 compatibility still requires testing against the eventual provider |
| C | React UI, local Supabase Auth/Postgres/Storage, application API where needed | Integrated identity/storage; resumable uploads available | Broader local container stack and policy surface; eventual migration must account for Auth and Storage semantics |

These options use free software on existing hardware. This is not a promise that future hosted infrastructure or the current Figma plan will remain free.

## Recommendation

Start with A. Use Django's existing session authentication and CSRF protection, a custom user model with a stable UUID from the first migration, and PostgreSQL from the first workflow. Seed the first local user with a management command; never bypass authorization for development. Use the latest supported security patch of the selected LTS at implementation time and lock dependencies then.

Use a single application deployment, not microservices. React serves the interaction; Django owns identity, authorization, validation, upload finalization, and private downloads. A narrow BlobStore interface separates storage operations from domain rules. A Django maintenance command handles expired attempts and orphan cleanup; v1 needs no queue broker.

Proposed defaults: one active upload per account, 100 MiB per file, 1 GiB total storage, whole-file retry. These are deliberate first-workflow limits, not scaling claims. Do not build sharing, search, folders, previews, or background synchronization.

## Future migration

Keep UUIDs, owner relationships, opaque blob keys, and checksums stable. Move PostgreSQL to managed PostgreSQL and implement a real object-storage adapter when deployment is needed. Run the same storage contract tests against the destination. Rehearse a quiesced copy, checksum reconciliation, and rollback before cutover. Add multiple app instances and workers only after removing local-storage dependence and measuring workload constraints.

Tens of thousands of registered users is not a capacity specification. Before public hosting, define concurrent transfers, file sizes, bandwidth, storage growth, availability and recovery targets; then load-test the complete system.

## Evidence

- [Django authentication](https://docs.djangoproject.com/en/5.2/topics/auth/default/) and [upload handling](https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/) provide existing foundations; they do not supply our complete finalization protocol.
- [PostgreSQL locking](https://www.postgresql.org/docs/current/explicit-locking.html) supports serialized quota/ownership changes without holding locks while streaming bytes.
- [SeaweedFS](https://github.com/seaweedfs/seaweedfs) supplies an S3-compatible storage option.
- [Supabase local development](https://supabase.com/docs/guides/local-development) and [resumable storage uploads](https://supabase.com/docs/guides/storage/uploads/resumable-uploads) support proposal C's capabilities and explain its local stack.

Recommendation is our judgment based on these capabilities and the local, single-outcome scope. See [protocol](../architecture/first-upload.md), [API](../architecture/api.md), and [runbook plan](../architecture/operations.md).
