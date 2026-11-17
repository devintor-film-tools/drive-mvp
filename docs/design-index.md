# Visual workspace and artifact index

Date: 2026-11-16
Owner: design lead

Figma Design and FigJam are the canonical visual workspace under [ADR 0002](decisions/0002-figma-visual-workspace.md). File creation, native spec read/write, and FigJam diagram editing are verified on the existing student plan. No subscription changes were made.

## Active visual files

| File | Current contents | Status |
| --- | --- | --- |
| [Drive MVP — Design](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl) | Fourteen editable frames, seven prototype flows, shared components/variables, native interaction specification | Detailed proposal prepared; representative visual checks; runtime/usability validation pending |
| [Drive MVP — Flows & Architecture](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw) | First-upload flow; system, ownership, lifecycle and finalization diagrams; three architecture proposals | Proposed architecture, visually reviewed; not implemented or load-tested |

### Revision 2 references — 2026-11-16

These are live node references, not immutable Figma version snapshots. No implementation commit exists yet.

- [Open the first-upload prototype](https://www.figma.com/proto/klWl6EK6EdRbKDtcwN7VIl?node-id=8-2&starting-point-node-id=8%3A2)
- [Screen workspace](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl?node-id=2-67): empty 8:2; menu 8:28; picker handoff 8:257; uploading 8:300; finishing 8:361; complete 8:395; interrupted 8:444; list unavailable 8:487; size limit 8:518; narrow 8:561; dismissed completion 10:202; uncertain outcome 12:321; reselect 12:341; loading 12:399.
- [Native interaction specification](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl?node-id=13-253); technical counterpart [design-first-upload.md](design-first-upload.md).
- [Components and foundations](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl?node-id=2-68): navigation, file row, five upload-status variants, semantic color/spacing/radius variables and typography. Imported Material 3 primitives underpin the composed UI.
- [System diagram](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw?node-id=9-144), [data model](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw?node-id=9-176), [lifecycle](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw?node-id=9-219), [sequence](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw?node-id=8-70).
- [Three architecture proposals](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw?node-id=11-222); authoritative technical decision [ADR 0003](decisions/0003-first-upload-architecture.md).
- Git source diagrams: [system](architecture/system.mmd), [model](architecture/model.mmd), [lifecycle](architecture/lifecycle.mmd), [sequence](architecture/upload-sequence.mmd). FigJam explains the same contracts with native editable layouts.
- Known limitations: Roboto substitutes for Google Sans; scope is intentionally reduced; no verified pixel-exact claim. Native picker/progress are simulated. Sign-in and resource-limit layouts still need their implementation pass. No real-user or accessibility conformance test has been performed.

### Revision 1 references — retained history

- Design brief: file klWl6EK6EdRbKDtcwN7VIl, native spec node 2:2; accepted direction, detailed design pending.
- Design pages: 0:1 (brief), 2:67 (first upload), 2:68 (components/validation).
- Upload flow: file w2beScsVpURt5pnTR6SEFw, section 2:70; 13 shapes and 14 connectors. Main interaction accepted; detailed recovery rules proposed.
- Architecture scope notes: same FigJam file, native spec node 2:71.
- No implementation commit exists yet. Workspace setup is not application validation.

Git owns detailed engineering specifications and executable contracts. Figma/FigJam own visual explanations. Link visuals to their technical source and reviewed implementation revision.

## Existing Drive artifacts retained

The baseline remains accessible as historical context. Nothing has been moved or deleted. Personal Google Drive will hold periodic reviewed exports; the old folder names below describe the original setup.

- [Project design folder](https://drive.google.com/drive/folders/1veuxNQ5YGJ8-4HmB7wMyQY79N4vV9Qac)
- [Design baseline, revision 1](https://drive.google.com/file/d/107tEmilYjmj6xJFMWpQDxcm3zWPZjVHz/view?usp=drivesdk)
- [References and proposals](https://drive.google.com/drive/folders/1_ByIO3QP-2TutG2iEdiO-dbNjcD22TWs)
- [Flows and mockups](https://drive.google.com/drive/folders/1iQO6GWQKRyyPqrv1b5YenhUltoUcfWvj)
- [Reviewed exports and validation](https://drive.google.com/drive/folders/1Pnx86VnStthY8KqOxFV6cYfHD9cV0W-Y)

The archived baseline is an HTML artifact, not a native Google Doc. Its original working-directory instructions are historical; ADR 0002 and the active Figma brief supersede them. Reviewed design exports will be added as design work is completed.

For each future reviewed artifact, record its file URL, frame/node where applicable, revision/date, status (proposed/accepted/implemented), and implementation commit when applicable. Keep reviewed exports immutable in Drive and name replacements with new revisions. Do not duplicate canonical design files in Git.
