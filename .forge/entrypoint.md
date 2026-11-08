The process rules this project shares with every TheForge project live in the `.forge/` files imported below.
The procedures they point at live under `.agents/skills/`.
Put this project's own rules in `CLAUDE.md`, after these imports, never inside a `.forge/` file (`.forge/forge-overrides.md`).
This file is forge-owned and synced like every other `.forge/` file: `CLAUDE.md` must keep its `@.forge/entrypoint.md` line, and the `forge-entrypoint` hook refuses a commit that drops it.

@.forge/never-default.md
@.forge/tickets-and-branches.md
@.forge/feature-pipeline.md
@.forge/review-gate.md
@.forge/self-review.md
@.forge/post-merge-review.md
@.forge/code-shape-rules.md
@.forge/ci-and-checks.md
@.forge/orchestration.md
@.forge/process-and-evidence.md
@.forge/requirements-driven-changes.md
@.forge/bug-fixing.md
@.forge/prototypes.md
@.forge/docs-describe-current-state.md
@.forge/decisions-log.md
@.forge/agent-skills-and-reference.md
@.forge/forge-overrides.md

Reference files the rules point into, read when they apply rather than on every turn: `.forge/coordinator-core.md` (the coordinator's own pithy rule copy, loaded only by the coordinator), `.forge/model-tiers.md`, `.forge/main-health-patterns.md`, `.forge/review-architecture-rationale.md`, `.forge/lessons-template.md`.
