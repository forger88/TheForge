# Agents working on TheForge

This file is for TheForge itself (this repository, the template source); a generated project gets its own copy, rendered from `template/AGENTS.md.jinja`.
It points agent harnesses other than Claude Code at the same instructions `CLAUDE.md` loads.
It is project-owned, like `CLAUDE.md`.

Read, in this order, before starting any work:

1. `CLAUDE.md`, the canonical source, for this repository's own rules.
2. `.forge/entrypoint.md`, and every file it imports (its lines starting with `@.forge/`).
   A harness that does not resolve `@` imports opens each of those files itself, since they are the forge-owned process rules and are not optional.
3. `docs/adr/` for this repository's own decisions; this repository has no `docs/software-development-lifecycle.md` of its own yet.

Skills are procedures under `.agents/skills/<name>/SKILL.md`.
When a rule names a skill, read and follow that file; when the owner names a skill your harness does not list, look for it under `.agents/skills/` before saying it does not exist.

Reference docs live under `docs/agents/`; read them when a rule or skill points there.

Capability tiers (design-tier, review-tier, build-tier, mechanical-tier) are mapped to models in `.forge/model-tiers.md`.

Before pushing a change under `template/` or `copier.yml`, run `scripts/check-render.sh`.
