# Drive MVP

Working project name. Independent file storage with a Google Drive interaction reference.

Status: detailed first-upload design and architecture proposal prepared. No application or local services have been implemented or started.

[Open the clickable first-upload prototype](https://www.figma.com/proto/klWl6EK6EdRbKDtcwN7VIl?node-id=8-2&starting-point-node-id=8%3A2) · [Architecture board](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw)

## Accepted constraints

- Host the entire application locally on existing hardware; no paid services or cloud runtime.
- Use GitHub for source version control. Default to a private repository.
- Use Figma Design and FigJam as the visual workspace; keep personal Google Drive for archived baselines and periodic exports. Figma workspace creation and editing are verified on the existing student plan; see the design index.
- Build one complete user outcome at a time, proving its guarantees before expanding.
- Present 2–3 researched proposals for material new decisions, with a recommendation.
- Selected first experience: My Drive → + New → File upload → native picker → progress → stored file.

## Working documents

- [First upload workflow](docs/workflows/first-upload.md)
- [Engineering foundation](docs/engineering.md)
- [Three architecture proposals and recommendation](docs/decisions/0003-first-upload-architecture.md)
- [Detailed interaction specification](docs/design-first-upload.md)
- [Environment and artifact decision](docs/decisions/0001-local-runtime-and-artifact-ownership.md)
- [Figma visual workspace decision](docs/decisions/0002-figma-visual-workspace.md)
- [Verification checklist](docs/verification.md)
- [Design artifact index](docs/design-index.md)

GitHub publication is pending: the connected GitHub tool lacks repository creation, and the local CLI could not resolve api.github.com. A local commit is not a remote backup.

Uploaded user files, database volumes, backups, secrets, and design working copies must stay out of Git. GitHub stores source and technical documentation only.
