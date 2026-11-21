# Capability tiers to models, per harness

This file's instructions are duplicated, pithily, into `coordinator-core.md` for a harness that cannot load this file directly.
TheForge's coordinator-core ADR records why that file exists and what must survive every edit to it.
A change here updates `.forge/coordinator-core.md` in the same change.
TheForge's `lock` check fails until the core section citing this one is re-read and the lock refreshed.

The instructions and skills name four harness-neutral capability tiers (design-tier, review-tier, build-tier, mechanical-tier), defined by the judgement each needs (`.forge/orchestration.md`).
This file says which model a harness runs for each tier, and is the only file in the repo allowed to name a model, apart from `.forge/coordinator-core.md`'s duplicate of this mapping, so changing a model is a one-file change.

A project that changes this mapping records the edit in `docs/forge-overrides.md` (`.forge/forge-overrides.md`).

## Default mapping

| Tier | Example model class | Why |
|---|---|---|
| design-tier | The provider's strongest available reasoning model | Design, security reasoning and module contracts are where a wrong call is expensive and hard to catch later. |
| review-tier | The provider's strongest available reasoning model | Reviewing merged code across several PRs needs strong judgement; kept as a separate tier because it may map to a different model later. |
| build-tier | A capable mid-tier model | Scoped work against a design that already carries the hard decisions. |
| mechanical-tier | A fast, inexpensive small model | One obviously correct answer per task. |

For Claude, that is the newest Opus for design-tier and review-tier, Sonnet for build-tier, and Haiku for mechanical-tier, referred to by alias so the mapping follows new releases.

## Rules that follow from the tiers

- `security-docs` runs at design-tier in all three modes: a threat model written by a tier not doing the security reasoning is decoration.
- A sub-agent reports the model it actually ran on, from its own system-prompt self-report; a tier alias is not trusted silently.
  A "current session" query (such as Claude Code's `get_session` with no id) run inside a dispatched sub-agent reports the *orchestrating* session's model, so it cannot stand in for the self-report, and a mismatch between the two is noted, not acted on (owner decision; first built on by post-merge-review's reviewer gate, `.agents/skills/post-merge-review/SKILL.md` step 4).
- design-tier and review-tier may resolve to the same model and stay distinct tiers, because the two kinds of work are judged differently.

## Other harnesses

Add a section in the same table shape when this repo's instructions run under another harness.
