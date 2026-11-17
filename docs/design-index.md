# Visual workspace and artifact index

Date: 2026-11-16
Owner: design lead

Figma Design and FigJam are the canonical visual workspace under [ADR 0002](decisions/0002-figma-visual-workspace.md). File creation, native spec read/write, and FigJam diagram editing are verified on the existing student plan. No subscription changes were made.

## Active visual files

| File | Current contents | Status |
| --- | --- | --- |
| [Drive MVP — Design](https://www.figma.com/design/klWl6EK6EdRbKDtcwN7VIl) | Accepted brief, references, first-upload requirements; pages reserved for screens and components/validation | Created and brief verified; mockups/prototype pending |
| [Drive MVP — Flows & Architecture](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw) | Editable first-upload flow with cancellation/recovery, architecture scope notes, cross-links | Created and visually checked; technical architecture pending |

### Revision 1 references

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
