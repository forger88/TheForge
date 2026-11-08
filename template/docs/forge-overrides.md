# Forge overrides

Every local edit to a forge-owned file is recorded here, in the same PR as the edit (`.forge/forge-overrides.md`).
A forge-owned file is any file TheForge ships outside the project-owned and seeded lists in that file: for example anything under `.forge/` or `.agents/skills/`, the generated reference docs under `docs/agents/`, `scripts/*.py`, the workflows, `.pre-commit-config.yaml` and `.devcontainer/devcontainer.json`.
Edits to a seeded file (the baselines, allowlists and other data files `.forge/forge-overrides.md` lists under "Seeded files") are not logged here.
`forge-sync` reads this file before every `copier update`, so a conflict on a logged file is expected and resolved in the project's favour unless upstream now covers the same need.
An unlogged edit to a forge-owned file is a review finding.

This file is project-owned: TheForge created it once and a sync never touches it.

## Entry shape

```md
### <path of the forge-owned file>

**Changed:** <which sentences or section, and to what>

**Why:** <the project need, citing the ticket>

**Upstream candidate:** <yes, rewritten generically | yes — proposed as <ticket link or "drafted in <sync PR link>">, <date> | no, project-specific | no — declined by owner, <date>>
```

Remove an entry once the change has gone upstream and come back through `forge-sync`, or once the local edit is reverted.

## Overrides

None yet.
