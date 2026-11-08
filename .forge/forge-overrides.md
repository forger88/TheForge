# Forge-owned, seeded and project-owned files

Every file TheForge ships belongs to one of three classes, and Copier treats them differently.

**Project-owned** files are created once and never touched by a sync: `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `docs/principles.md`, `docs/decisions-log.md`, `docs/forge-overrides.md`, `docs/agents/lessons.md`, `docs/agents/operational-constants.md`, the threat model and the requirements specification.
The rest of the `_skip_if_exists` list in `copier.yml` (for example `docs/tools/document-build.json`) is project-owned too.

**Seeded** files are listed under "Seeded files" below.
TheForge ships a starting version and the project then maintains it as data.
`copier update` three-way merges a seeded file, so an upstream structural change still arrives.
A local edit to a seeded file is expected and is not logged in `docs/forge-overrides.md`.
On a sync conflict in a seeded file, the project's entries win and upstream's structural changes are kept alongside them.

**Forge-owned** files are every other file TheForge ships, outside the project-owned and seeded lists.
That covers `.forge/`, the skills under `.agents/skills/`, `instructing-agents.md`, `scripts/project_init_checklist.md`, the generated reference docs under `docs/agents/`, and the guard-bearing configuration: `scripts/*.py`, `.pre-commit-config.yaml`, the workflows, `.devcontainer/devcontainer.json` and `.claude/`.
They come from TheForge and are kept in sync with it by `copier update`, which the `forge-sync` skill wraps.

## Seeded files

These files are seeded.
They are pure data, so a project edits them as part of normal work.
- `scripts/coverage_baseline.json`
- `scripts/dead_code_baseline.json`
- `scripts/module_size_allowlist.json`
- `.gitignore`

A `.gitignore` edit that hides a guard's file from the repository is still a review finding.
A new baseline or allowlist file joins this list in the same change that adds it.
A file that carries or enables a guard, such as a hook or workflow definition, never joins it, so a weakening edit stays visible in the override log.

## Project rules go in project-owned files

A rule that is specific to this project goes in `CLAUDE.md`, under its own project section, or in a project-owned doc it points at.
Never inline it into a `.forge/` file.

## Editing a forge-owned file

Sometimes a project genuinely needs to change a forge-owned file: to tighten a rule, adapt a skill to its stack, or fix a mistake before upstream does.
That is allowed, and every such edit is recorded in `docs/forge-overrides.md` in the same PR.
The entry names the file, what changed, why, and whether the change should go upstream to TheForge.

The log is what makes the next sync predictable.
`forge-sync` reads it before running `copier update`, so a conflict on a logged file is expected and resolved in the project's favour unless upstream now covers the same need.
An unlogged edit to a forge-owned file is a review finding.

## Keep forge files one sentence per line

Forge-owned rule files are written one sentence per line, so a three-way merge conflicts on the sentence that changed rather than on a whole re-wrapped paragraph.
A local edit keeps that shape; `scripts/check_one_sentence_per_line.py` checks it in the pre-commit hook.

## Sending a refinement upstream

A local refinement that would help every project should go to TheForge first and then come back through `forge-sync`.
Rewrite it generically, with no project names, issue numbers, paths, vocabulary or incident-shaped examples, before proposing it.
Once the upstream change has synced back, remove its entry from `docs/forge-overrides.md`.
