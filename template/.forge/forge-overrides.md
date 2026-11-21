# Forge-owned, seeded and project-owned files

Every file TheForge ships is in one of three classes, which Copier treats differently.

**Project-owned** files are created once and never touched by a sync: `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `docs/principles.md`, `docs/decisions-log.md`, `docs/forge-overrides.md`, `docs/agents/lessons.md`, `docs/agents/operational-constants.md`, the threat model, the requirements specification, and the rest of `copier.yml`'s `_skip_if_exists` list (for example `docs/tools/document-build.json`).

**Seeded** files, listed under "Seeded files" below, start as TheForge's version and are then maintained by the project as data.
`copier update` three-way merges them, so an upstream structural change still arrives; on a conflict, the project's entries win and upstream's structural changes are kept alongside.
A local edit to a seeded file is expected and not logged in `docs/forge-overrides.md`.

**Forge-owned** files are everything else TheForge ships: `.forge/`, the skills under `.agents/skills/`, `instructing-agents.md`, `scripts/project_init_checklist.md`, the generated reference docs under `docs/agents/`, and the guard-bearing configuration (`scripts/*.py`, `.pre-commit-config.yaml`, the workflows, `.devcontainer/devcontainer.json` and `.claude/`).
`copier update`, wrapped by the `forge-sync` skill, keeps them in sync with TheForge.

## Seeded files

These are pure data, which a project edits as part of normal work:
- `scripts/coverage_baseline.json`
- `scripts/dead_code_baseline.json`
- `scripts/module_size_allowlist.json`
- `scripts/requirements_evidence_baseline.json`
- `.gitignore`

A `.gitignore` edit that hides a guard's file from the repository is still a review finding.
A new baseline or allowlist file joins this list in the change that adds it.
A file that carries or enables a guard, such as a hook or workflow definition, never joins it, so a weakening edit stays visible in the override log.

## Project rules go in project-owned files

A project-specific rule goes in `CLAUDE.md`, under its own project section, or a project-owned doc it points at, never inline in a `.forge/` file.

## Editing a forge-owned file

A project may change a forge-owned file when it genuinely needs to (to tighten a rule, adapt a skill to its stack, or fix a mistake before upstream does).
Every such edit is recorded in `docs/forge-overrides.md` in the same PR, naming the file, what changed, why, and whether it should go upstream to TheForge.

`forge-sync` reads that log before `copier update`, so a conflict on a logged file is expected and resolved in the project's favour unless upstream now covers the same need.
An unlogged edit to a forge-owned file is a review finding.

## Keep forge files one sentence per line

Forge-owned rule files are one sentence per line, so a three-way merge conflicts on the changed sentence rather than a re-wrapped paragraph.
A local edit keeps that shape, which `scripts/check_one_sentence_per_line.py` checks in the pre-commit hook.

## Sending a refinement upstream

A local refinement that would help every project goes to TheForge first, rewritten generically (no project names, issue numbers, paths, vocabulary or incident-shaped examples), then comes back through `forge-sync`.
Once it has synced back, remove its entry from `docs/forge-overrides.md`.
