# First-upload design specification

Date: 2026-11-16 · Status: proposed detailed design; artifact checks only
Owner: design lead

## Intent and fidelity

Preserve the selected Google Drive interaction: My Drive → + New → File upload → native picker → progress → stored file. The native picker is an OS-owned surface; the prototype handoff explains it rather than pretending the web app owns that dialog. Use only File upload in the New menu. Search, sharing, folders, previews and batch controls are deliberately absent from this first outcome.

The visual proposal uses editable Material 3 instances, semantic variables and Roboto. Google Sans was not available in the connected font set. This is a researched, reduced-scope Drive-like design, not a verified pixel-exact reproduction. Google's current [upload instructions](https://support.google.com/drive/answer/2424368?hl=en) substantiate the interaction. Exact current account-specific Drive styling still needs a reference capture during implementation review.

## States and copy

| State | Visible behavior and recovery |
| --- | --- |
| Loading | Keep My Drive heading and loading status; never flash empty-state copy before the request succeeds |
| Empty | “Your drive is empty”; New remains the single upload entry point |
| Menu | One File upload item; no disabled future features |
| Picker cancel | No upload created; restore focus to New |
| Uploading | Filename, bytes sent and percent; keep tab open; New disabled while this owner has an active transfer |
| Finishing | “Finishing upload”; bytes sent is not yet saved; completion waits for API commit |
| Unknown outcome | “Checking whether your file was saved…”; Check again; no “not saved” claim |
| Complete | One file row and “1 upload complete”; Dismiss removes the panel, keeps the file |
| Confirmed interruption | “Upload interrupted”; server has confirmed no saved File; Retry restarts the whole transfer using the same upload session |
| Retry after refresh | Ask to reselect the original file; no claim that browser file access survived refresh |
| Size limit | “File too large”; maximum 100 MiB; Choose another file opens picker |
| Quota/device full | Distinct “Storage limit reached” / “This device is out of space”; do not retry repeatedly |
| Failed list | “Couldn't load your files”; Retry; existing files are not called an empty drive |
| Session expired | Sign-in required; preserve opaque upload ID and reconcile after sign-in |

Detailed frames cover the primary path and representative failures. Loading, unknown-outcome and reselect states are also included as focused annotated states. Authentication, quota and physical-disk failure are specified contracts; their final layouts must be completed before those implementation paths are declared ready.

## Interaction and accessibility contract

- New is a real button with `aria-haspopup="menu"` and `aria-expanded`; Enter/Space opens and focuses File upload. Escape closes and restores focus. Arrow keys follow the [WAI menu-button pattern](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/).
- File upload invokes one native file input. Do not hijack keyboard behavior of the OS picker. Cancellation and successful selection return focus predictably.
- Expose upload progress with a labeled progressbar. Announce meaningful phase changes through a polite status region; avoid announcing every percentage change. Use assertive alerts for actionable failures. See [WCAG status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html).
- Completion does not steal focus. Announce success and add the file row. Dismiss preserves the row and sends focus to the My Drive heading if the focused panel disappears.
- Preserve visible focus, non-color status labels, sufficient contrast, and usable target sizes. Verify keyboard and screen-reader behavior in running code; a Figma link graph cannot establish accessibility conformance.
- At narrow widths, collapse sidebar, retain My Drive and New, and show filename/size without requiring horizontal scrolling. The narrow-screen frame is a layout proposal, not a complete mobile prototype.

## Prototype limitations and review

Timed transitions between Uploading, Finishing and Complete simulate progress; no bytes are transferred. Failure paths are separate starting points. The sample document and file size are fixtures. The clickable picker handoff is illustrative; production uses the browser/OS dialog. Review discoverability and terminology with a person before marking usability verified.

## Maintenance

Figma owns frames, components, variables and native design notes. Git owns this interaction contract and API behavior. For every implementation change, link exact relevant frames and record the implementation commit plus visual/interaction evidence in the verification ledger. Do not mark all states implemented because one screenshot matches.
