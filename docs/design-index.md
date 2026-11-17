# Visual workspace and artifact index

Date: 2026-11-16
Owner: design lead

Figma Design and FigJam are the selected visual workspace under [ADR 0002](decisions/0002-figma-visual-workspace.md). Setup is pending: plugin installation is confirmed, but its tools are unavailable in the current conversation; account access and free editing capabilities are unverified, and no Figma files have been created for this project.

## Planned visual files

| File | Contents | Status |
| --- | --- | --- |
| Drive MVP — Design | References, selected screens, components, prototype, validation annotations | Pending connection; URL not available |
| Drive MVP — Flows & Architecture | User journeys, system boundaries, data relationships, upload sequence and states, recovery | Pending connection; URL not available |

Git owns detailed engineering specifications and executable contracts. Figma/FigJam own visual explanations once setup is verified. Link visuals to their technical source and reviewed implementation revision.

## Existing Drive artifacts retained

The baseline remains accessible as historical context. Nothing has been moved or deleted. Personal Google Drive will hold periodic reviewed exports; the old folder names below describe the original setup.

- [Project design folder](https://drive.google.com/drive/folders/1veuxNQ5YGJ8-4HmB7wMyQY79N4vV9Qac)
- [Design baseline, revision 1](https://drive.google.com/file/d/107tEmilYjmj6xJFMWpQDxcm3zWPZjVHz/view?usp=drivesdk)
- [References and proposals](https://drive.google.com/drive/folders/1_ByIO3QP-2TutG2iEdiO-dbNjcD22TWs)
- [Flows and mockups](https://drive.google.com/drive/folders/1iQO6GWQKRyyPqrv1b5YenhUltoUcfWvj)
- [Reviewed exports and validation](https://drive.google.com/drive/folders/1Pnx86VnStthY8KqOxFV6cYfHD9cV0W-Y)

Only the baseline exists initially; mockups, prototype, and validation are pending. The baseline is an HTML artifact, not a native Google Doc.

For each future reviewed artifact, record its file URL, frame/node where applicable, revision/date, status (proposed/accepted/implemented), and implementation commit when applicable. Keep reviewed exports immutable in Drive and name replacements with new revisions. Do not duplicate canonical design files in Git.
