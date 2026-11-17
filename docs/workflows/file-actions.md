# Download, rename, trash and restore — revision 3

Date: 2026-11-17. Scope authorized: all three follow-on outcomes, following the automated first-upload gate. Local runtime and private ownership remain unchanged.

## Choices and recommendation

1. **File-row actions menu and rename dialog (implemented):** compact at desktop and narrow widths, with an explicit Actions button. Alternative: inline action buttons, easier to discover but crowding each row. Menu keyboard behavior follows [WAI menu-button guidance](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/); rename uses a native modal dialog with focus restoration, following [WAI dialog guidance](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
2. **Retained trash (implemented):** keep contents and metadata until restored; charge the same quota. Alternative: timed expiry and permanent deletion, which require a distinct retention/destruction outcome. [Google Drive's reference behavior](https://support.google.com/drive/answer/14933051) charges trash toward storage and removes it after 30 days. This local release deliberately has no automatic expiry or permanent delete. Its interface explicitly says files stay until restored.
3. **Revision-checked metadata updates (implemented):** serialize each file update with a row lock and reject stale revisions. Alternative: last-write-wins, simpler but capable of reversing another tab's action. No new infrastructure is needed.

## User outcomes

- **Download:** My Drive → file Actions → Download. Show Preparing download, then a browser-handoff message after receiving complete bytes. A browser download event does not establish that the user saved the file to disk. Keep the workspace visible on failures, with retry via Actions. Browser Blob buffering is bounded by the existing 100 MiB upload limit; native streaming is a future option if limits increase.
- **Rename:** Actions → Rename… → edit full filename → Save. Select the existing name; Cancel/Escape restores trigger focus. Keep input and inline error on validation/conflict failures. Names use the upload validator (1–255 UTF-8 bytes, no path separators/control characters or dot-only names). Duplicate display names remain allowed because identity is a UUID. The extension can be edited; contents are unchanged.
- **Trash:** Actions → Move to trash. Remove the row only after server confirmation; announce that it can be restored from Trash. This reversible action needs no destructive confirmation.
- **Restore:** Trash navigation → file Actions → Restore → My Drive. Preserve ID, name, creation timestamp, blob and checksum. Trash offers restore only; direct downloads of trashed files return 404. Downloads already authorized before a trash update can finish.
- **Recovery:** a lost update response is uncertain, not success or failure. Refresh the list to see committed state. No automatic mutation retry. Repeating an old revision returns a conflict; this cannot reverse a later action. A refresh failure remains a list error, not an empty view.
- **Accessibility:** menu arrows/Home/End/Escape; modal focus containment via native dialog; explicit name labels, status/error announcements; navigation remains available at narrow widths. Automated browser checks do not establish screen-reader conformance.

## Technical contract

`File.trashed_at`: nullable timestamp; `File.revision`: positive integer, initially 1. Migration `0004_file_actions` preserves existing records as active. Blob storage and upload identity are immutable. Storage accounting includes active and trashed files, so restoring cannot exceed quota.

- `GET /api/files?location=drive|trash`: defaults to drive. Same pagination ordering as before. Signed cursors bind owner and location; cursors cannot cross lists.
- `PATCH /api/files/:id`: authenticated, CSRF-protected JSON with exactly `{name, revision}` or `{trashed: boolean, revision}`. Returns the serialized File. Revision mismatch is `409 file_changed`; renaming a trashed file is `409 file_trashed`; absent/foreign file is 404. A no-op at the current revision does not increment it. A real change increments it once, atomically.
- File JSON includes `trashed_at` and `revision`. The original upload's name/idempotency metadata is not changed by rename.
- `GET /api/files/:id/content`: active, owned files only, attachment disposition with current name; existing no-store and content-length behavior retained.
- Backups already include all File records and committed blobs. The verification fingerprint now compares both active and trash metadata across restart and restored backup; backup verification checks every committed blob checksum.

## Visual references

[Figma R3 actions](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl?node-id=19-2743), [rename](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl?node-id=19-2844), [trash](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl?node-id=19-2909).

These are dated, editable live nodes, not immutable version snapshots or user-approved designs. Existing R2 nodes were preserved. R3 uses Roboto, existing local semantic variables, Drive row/navigation instances and imported Material menu/field/button instances. No raster UI layers. Detailed interaction/error contracts live in this versioned specification. Browser screenshots are retained outside Git; Figma is a visual target, not a pixel-exact claim.
