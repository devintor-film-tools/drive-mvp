# ADR 0002: Figma visual workspace

Date: 2026-11-16
Status: accepted; workspace created and current read/write operations verified
Owners: design and engineering leads
Supersedes: ADR 0001's selection of Google Drive as the primary design workspace

## Decision

Use Figma Design for interface proposals, mockups, components, and prototypes. Use FigJam for user flows and explanatory architecture diagrams. Keep executable specifications, API contracts, migrations, technical decisions, tests, and runbooks in Git/GitHub. Retain the existing personal Drive baseline as a historical artifact and use Drive for periodic reviewed exports.

Alternatives presented: Figma as the shared visual workspace, or local/Git authoring with Drive artifact storage. The user selected Figma.

## Boundaries

This does not change the local-only application runtime or zero-spend constraint. Do not purchase seats, enable paid features, or treat trial/beta availability as a permanent free entitlement. Verify the connected account's capabilities before establishing an automated editing workflow.

Do not migrate or remove existing Drive artifacts before new Figma artifacts can be created, read back, and linked. Avoid maintaining competing editable versions: Figma will own visuals once migration is verified; Git will own engineering contracts. Reviewed design/diagram revisions link to implementation commits. The diagrams are explanatory views of the engineering contracts, not competing specifications.

## Execution status

- Account verified: Devin Torres, devintor@usc.edu, Full seat on the existing student plan, Devin Torres's team.
- Created both files in drafts. No paid plan, subscription change, or paid feature purchase was performed.
- Design file: klWl6EK6EdRbKDtcwN7VIl; accepted brief added as native spec 2:2 and content read back successfully.
- FigJam file: w2beScsVpURt5pnTR6SEFw; first-upload flow created as editable shapes/connectors, scope notes added as native spec 2:71, content read back and diagram visually verified.
- Flow section 2:70 contains 13 shapes and 14 connectors. Main path is accepted; detailed recovery behavior remains proposed.
- Figma task session: b6d3083a-99b4-4b88-b43b-2548b10dfb9e. Reuse for follow-up setup checks.
- Existing Google Drive baseline is retained as historical context; nothing was deleted or moved.
- Detailed mockups, prototype, architecture proposals, and application implementation are pending.

## Initial organization

1. Drive MVP — Design: brief and references; selected first-upload screens and component states; prototype and validation annotations.
2. Drive MVP — Flows & Architecture: user flow; proposed system boundaries; data relationships; upload states and sequence; recovery paths.

Organize with sections inside these two files and avoid unnecessary additional files. Detailed architecture remains proposed until evaluated. Use artifact URLs and exact frame/node or revision references in the design index when available.

## Evidence checked

- https://help.figma.com/hc/en-us/articles/13838684089751-Starter-plan-overview
- https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/

The account is on a student plan, not Starter. Creation and the read/write operations needed for this setup succeeded on its existing Full seat. Direct agent editing has beta/access conditions; these successful operations do not establish permanent free availability. Recheck entitlement before relying on new or changed capabilities.
