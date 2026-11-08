# ADR-0002: Forge-owned and project-owned material are physically separated

**Status:** accepted

## Context

A generated project's agent instructions mix two kinds of material.
Some is the forge's: the process rules, the skills, the reference docs, which every project shares and TheForge keeps improving.
Some is the project's own: its product, its stack, its principles, its lessons, its glossary.

If both kinds live in the same files, every `copier update` (ADR-0001) is a three-way merge across files the project has edited for its own reasons, and an upstream change to one rule conflicts with an unrelated local paragraph in the same file.
After a few updates, owners stop syncing, and the forge-derived project silently forks.

## Decision

Forge-owned material and project-owned material live in different files, joined by import, never by merge.

- Forge rules live under `.forge/` in a generated project, one topic per file, written one sentence per line.
  Forge skills live under `.agents/skills/`.
- `CLAUDE.md` is project-owned.
  It holds a short introduction, the rule-strength framework, one `@.forge/<file>.md` import line per forge rule file, and then the project's own rules.
  It never inlines a forge rule's text.
  `AGENTS.md` points other harnesses at the same files.
- Project-owned seed files (`CLAUDE.md`, `CONTEXT.md`, `docs/principles.md`, `docs/decisions-log.md`, `docs/agents/lessons.md`, the threat model and requirements skeletons) are created once and listed under `_skip_if_exists`, so `copier update` never touches them again.
- When a project does need to change a forge-owned file, it edits it in place and records the edit in its project-owned overrides log (`docs/forge-overrides.md`): which file, what changed, why, and whether the change should go upstream.

## Alternatives rejected

- **One combined `CLAUDE.md`, rendered from the template.** Simplest to read, but every project edit to it turns every later sync into a conflict on the whole file.
- **Forge rules only as skills, no `.forge/` rule files.** Skills are procedures reached through a pointer; standing rules have to be loaded on every turn, which is what an import from `CLAUDE.md` does.
- **No local edits to forge-owned files at all.** Projects legitimately need to adapt a rule, and a ban would just push the adaptation into an unrecorded fork.

## Consequences

- A `copier update` over files the project never touched is a clean fast-forward.
- A conflict, when one happens, is scoped to one topic file and usually one sentence.
- The overrides log tells the next sync which conflicts are expected and why, and tells TheForge's maintainers which refinements are candidates to back-port upstream.
- The harness must support file imports from `CLAUDE.md` (Claude Code does); a harness that does not is pointed at the same files by `AGENTS.md`.
