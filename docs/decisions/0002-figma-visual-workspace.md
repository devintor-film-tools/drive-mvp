# ADR 0002: Figma visual workspace

Date: 2026-11-16
Status: accepted by user; execution pending Figma connection and free-access verification
Owners: design and engineering leads
Supersedes: ADR 0001's selection of Google Drive as the primary design workspace

## Decision

Use Figma Design for interface proposals, mockups, components, and prototypes. Use FigJam for user flows and explanatory architecture diagrams. Keep executable specifications, API contracts, migrations, technical decisions, tests, and runbooks in Git/GitHub. Retain the existing personal Drive baseline as a historical artifact and use Drive for periodic reviewed exports.

Alternatives presented: Figma as the shared visual workspace, or local/Git authoring with Drive artifact storage. The user selected Figma.

## Boundaries

This does not change the local-only application runtime or zero-spend constraint. Do not purchase seats, enable paid features, or treat trial/beta availability as a permanent free entitlement. Verify the connected account's capabilities before establishing an automated editing workflow.

Do not migrate or remove existing Drive artifacts before new Figma artifacts can be created, read back, and linked. Avoid maintaining competing editable versions: Figma will own visuals once migration is verified; Git will own engineering contracts. Reviewed design/diagram revisions link to implementation commits. The diagrams are explanatory views of the engineering contracts, not competing specifications.

## Execution status

- Figma plugin installation is now confirmed by plugin discovery.
- Figma tools are not available in the current conversation; account authorization and file access cannot yet be verified.
- Account/plan eligibility, read/write capabilities, and file creation remain unverified.
- No Figma or FigJam files have been created.
- No existing Drive artifacts have been moved or deleted.

## Initial organization

1. Drive MVP — Design: brief and references; selected first-upload screens and component states; prototype and validation annotations.
2. Drive MVP — Flows & Architecture: user flow; proposed system boundaries; data relationships; upload states and sequence; recovery paths.

Organize with sections inside these two files and avoid unnecessary additional files. Detailed architecture remains proposed until evaluated. Use artifact URLs and exact frame/node or revision references in the design index when available.

## Evidence checked

- https://help.figma.com/hc/en-us/articles/13838684089751-Starter-plan-overview
- https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/

Starter's file allowance fits this initial organization. Direct agent canvas editing has plan/access conditions and beta pricing limitations; the account-level free workflow still requires verification.
