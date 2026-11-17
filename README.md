# Drive MVP

Working project name. Independent file storage with a Google Drive interaction reference.

Status: documentation scaffold only. No application or local services have been implemented or started.

## Accepted constraints

- Host the entire application locally on existing hardware; no paid services or cloud runtime.
- Use GitHub for source version control. Default to a private repository.
- Keep canonical design artifacts in the user's personal Google Drive.
- Build one complete user outcome at a time, proving its guarantees before expanding.
- Present 2–3 researched proposals for material new decisions, with a recommendation.
- Selected first experience: My Drive → + New → File upload → native picker → progress → stored file.

## Working documents

- [First upload workflow](docs/workflows/first-upload.md)
- [Engineering foundation](docs/engineering.md)
- [Environment and artifact decision](docs/decisions/0001-local-runtime-and-artifact-ownership.md)
- [Verification checklist](docs/verification.md)
- [Design artifact index](docs/design-index.md)

GitHub publication is pending: the connected GitHub tool lacks repository creation, and the local CLI could not resolve api.github.com. A local commit is not a remote backup.

Uploaded user files, database volumes, backups, secrets, and design working copies must stay out of Git. GitHub stores source and technical documentation only.
