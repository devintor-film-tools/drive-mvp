# Drive MVP

Working project name. Independent file storage with a Google Drive interaction reference.

Status: local upload, download, rename, trash and restore are implemented. The 2026-11-17 automated suite passes 23 backend tests, 82 HTTP assertions, seven browser tests, frontend/backup unit checks, restart persistence and backup/restore including trash. Human usability and screen-reader review remain pending. See the dated [verification evidence](docs/verification.md).

[Open the clickable first-upload prototype](https://www.figma.com/proto/klWl6EK6EdRbKDtcwN7VIl?node-id=8-2&starting-point-node-id=8%3A2) · [Architecture board](https://www.figma.com/board/w2beScsVpURt5pnTR6SEFw)

## Run on this Mac

Open **Set Up Drive.command** in Finder, or run this one command in Terminal:

```sh
open "/Users/dtorres/projects/drive-mvp/Set Up Drive.command"
```

The launcher installs missing local prerequisites with the existing Homebrew installation, downloads the reviewed icons/font, installs locked frontend dependencies, builds the interface, and runs the full acceptance suite in isolated disposable databases. Only if those gates pass does it prompt for your local username/password and open the app. No cloud runtime, paid service or public signup is involved. The first run requires network access for packages/assets; the running app uses only local services.

Subsequent launches: **Start Drive.command**. Independent verification: **Verify Drive.command**. Use Ctrl-C in the app terminal to stop the app; `python3 scripts/local.py stop-db` stops this project's isolated database after the app stops. Credentials and uploads live under `~/Library/Application Support/Drive MVP`, outside Git. Do not put that directory in the repository.

The setup launcher intentionally stops on a failing gate. It is not a substitute for reviewing the saved evidence. See [local operation instructions](docs/architecture/operations.md), [implementation review](docs/implementation-review.md) and [verification checklist](docs/verification.md).

## Implemented scope

Local session sign-in; My Drive → New → File upload; native single-file picker; transport progress and separate final confirmation; safe retry/reconciliation; private persistent metadata and blob storage; file limits/quota; failure states; narrow layout. File-row Actions now supports download, rename and move to trash; Trash supports restore. Trashed files retain their contents and still count toward storage. There is no automatic expiry or permanent deletion. See the [file-actions specification](docs/workflows/file-actions.md).

`backend/` contains Django/PostgreSQL models, migrations, storage and APIs. `frontend/` contains the Figma-derived React interface and downloaded local icons/font. `scripts/` manages local services and backup/restore. `tests/` contains independent HTTP/browser acceptance suites. The launcher refuses to start with missing assets.

## Accepted constraints

- Host the entire application locally on existing hardware; no paid services or cloud runtime.
- Use GitHub for source version control. Default to a private repository.
- Use Figma Design and FigJam as the visual workspace; keep personal Google Drive for archived baselines and periodic exports. Figma workspace creation and editing are verified on the existing student plan; see the design index.
- Build one complete user outcome at a time, proving its guarantees before expanding.
- Present 2–3 researched proposals for material new decisions, with a recommendation.
- Selected first experience: My Drive → + New → File upload → native picker → progress → stored file.

## Working documents

- [Download, rename, trash and restore](docs/workflows/file-actions.md)
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
