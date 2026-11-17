# First private file upload

Date: 2026-11-16
Status: selected interaction; detailed specification pending
Owners: design and engineering leads

## Outcome

One authenticated user uploads one file into private storage and understands whether it succeeded.

## Accepted interaction

My Drive → + New → File upload → native single-file picker → upload progress → stored file.

The menu exposes only implemented actions. Cancelling the picker preserves the workspace and restores focus. Uploading, finalizing, completed, and failed are distinguishable. Success is shown only after durable contents and metadata confirmation. Recovery must not duplicate files or storage accounting.

## Guarantees to specify and verify

- Server-side authorization protects metadata and file bytes.
- Stable identity ties a file to its owner.
- Retry and concurrency behavior is explicit.
- Interrupted writes are detectable and recoverable.
- File contents survive service restart and match the original checksum.
- Keyboard operation, focus, and status announcements are specified.
- A failed list request is not represented as an empty drive.

One-user design does not waive isolation testing: use a second fixture identity to test denied access.

## Deferred scope

Sharing, public links, folders, previews, search, editors, offline sync, batch uploads, and user-facing version history.

## Next proposals to prepare

Engineering owns recommending local authentication, storage/database/runtime choices, file limits, resumability, and finalization protocol. Design owns annotated layouts, error copy, keyboard behavior, and prototype validation. Bring concrete researched recommendations rather than asking the user to invent these decisions.

See [design index](../design-index.md) and [verification](../verification.md).
