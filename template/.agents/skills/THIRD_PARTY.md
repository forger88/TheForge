# Third-party skills and licences

This project's agent skills live under `.agents/skills/` and were generated from TheForge (MIT; see `NOTICE.md` at the repository root).
Most of TheForge's skills are adapted from Matt Pocock's public skills repository; the `impeccable` design skill, which the feature pipeline's user-interface checks use, comes from Paul Bakaus's `impeccable` repository and is shipped here verbatim.
Everything else in this directory was written for TheForge.

Licence texts are included verbatim under [`licenses/`](./licenses/):

- [`licenses/MIT-mattpocock-skills.txt`](./licenses/MIT-mattpocock-skills.txt): the MIT licence covering every `mattpocock/skills`-derived skill below.
- [`licenses/APACHE-2.0-impeccable.txt`](./licenses/APACHE-2.0-impeccable.txt): the Apache License 2.0 covering `impeccable`.
- [`licenses/NOTICE-impeccable.md`](./licenses/NOTICE-impeccable.md): `impeccable`'s own upstream NOTICE file, carried forward unmodified per Apache 2.0 section 4(d).
  It records that two of `impeccable`'s reference files are themselves derived from a third party (`ehmo/platform-design-skills`, MIT), a nested attribution reproduced here rather than restated.
- [`licenses/MIT-humanlayer-skills.txt`](./licenses/MIT-humanlayer-skills.txt): the MIT licence (copyright HumanLayer) covering `show-me`, the `humanlayer/skills` skill reproduced inside `pr` (see "Written for TheForge" below).

Every skill below taken from `mattpocock/skills` carries a one-line HTML-comment source note under its own `SKILL.md`'s frontmatter, pointing back to this file.
"Modified" means the copy here has diverged from the upstream commit it was taken from, beyond whitespace; the note in each modified skill's `SKILL.md` says so too.
The copies are pinned, not auto-updated from upstream, so drift behind upstream is expected and not itself actionable.

## `mattpocock/skills` (MIT, https://github.com/mattpocock/skills)

Author: Matt Pocock.
Licence: MIT (see `licenses/MIT-mattpocock-skills.txt`).
Each row's commit is the upstream commit the copy was taken from, or the closest upstream commit TheForge's changes were layered on.

| Skill | Upstream path | Taken from (commit, date) | Modified here? |
|---|---|---|---|
| `ask-matt` | `skills/engineering/ask-matt/SKILL.md` | `4cfa4cd2ae`, 2026-09-17 | Yes: a supporting file (`PHASE-BOUNDARIES.md`) reworded a reference to a specific AI coding tool to stay tool-agnostic; `SKILL.md`'s own body is unchanged |
| `claude-handoff` | `skills/in-progress/claude-handoff/SKILL.md` | `321658273c`, 2026-08-19 | Yes: CLAUDE.md citation repointed to `.forge/agent-skills-and-reference.md`; reworded a UI-component reference |
| `code-review` | `skills/engineering/code-review/SKILL.md` | `13ea86f0b0`, 2026-10-06 | Yes: guard-removal-blind, build-vs-buy, adopted-abstraction-bypass, new-comment and glossary checks in the Standards brief; requirement and lifecycle checks in the Spec brief; the MoSCoW triage table |
| `codebase-design` | `skills/engineering/codebase-design/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `diagnosing-bugs` | `skills/engineering/diagnosing-bugs/SKILL.md` | `321658273c`, 2026-08-19 | Yes: first-parent bisect guidance for mixed merge and squash history |
| `domain-modeling` | `skills/engineering/domain-modeling/SKILL.md` | `321658273c`, 2026-08-19 | Yes: `docs/principles.md` as a third home beside the glossary and ADRs, with `PRINCIPLES-FORMAT.md` |
| `git-guardrails-claude-code` | `skills/misc/git-guardrails-claude-code/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `grill-me` | `skills/productivity/grill-me/SKILL.md` | `fcf0071560`, 2026-08-15 | Yes: feature-pipeline stage 0 and stage 2 integration (start the pipeline, record use cases, resolve glossary terms) |
| `grill-with-docs` | `skills/engineering/grill-with-docs/SKILL.md` | `447ca70872`, 2026-08-15 | Yes: a note routing pipeline interviews to `grill-me` |
| `grilling` | `skills/productivity/grilling/SKILL.md` | `85f83d3fde`, 2026-08-20 | Yes: a read-only check of existing ADRs, glossary and principles before the first round |
| `handoff` | `skills/productivity/handoff/SKILL.md` | `d28dfdc39b`, 2026-08-15 | Yes: CLAUDE.md citation repointed to `.forge/agent-skills-and-reference.md` |
| `implement` | `skills/engineering/implement/SKILL.md` | `386d4ff719`, 2026-07-08 | Yes: a ticket-exists precondition, a per-ticket guard-removal re-read, a release-note label reconciliation step, and an owner-merge pending-note step (opening the PR explicitly, then posting the post-merge-review pending note once a human merges it) |
| `implement-spec` | `skills/in-progress/implement-spec/SKILL.md` | `5b15a47f2d`, 2026-08-21 | No |
| `improve-codebase-architecture` | `skills/engineering/improve-codebase-architecture/SKILL.md` | `321658273c`, 2026-08-19 | Yes: step 4's triage-outcome and record-shape citations repointed to `.forge/feature-pipeline.md` and `.forge/process-and-evidence.md` instead of CLAUDE.md and a hardcoded issue number; `HTML-REPORT.md`'s hex colour changed to an `rgb()` value to clear the issue-reference guard |
| `loop-me` | `skills/in-progress/loop-me/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `migrate-to-shoehorn` | `skills/misc/migrate-to-shoehorn/SKILL.md` | `62f43a1817`, 2026-04-28 | No |
| `pr` | `skills/in-progress/pr/SKILL.md` | `c55ee46073`, 2026-09-18 | No |
| `prototype` | `skills/engineering/prototype/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `research` | `skills/engineering/research/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `resolving-merge-conflicts` | `skills/engineering/resolving-merge-conflicts/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `retro` | `skills/in-progress/retro/SKILL.md` | `0243b6ec4c`, 2026-09-15 | Yes: source-note wording only |
| `scaffold-exercises` | `skills/misc/scaffold-exercises/SKILL.md` | `62f43a1817`, 2026-04-28 | No |
| `setup-matt-pocock-skills` | `skills/engineering/setup-matt-pocock-skills/SKILL.md` | `5c89081d4b`, 2026-08-19 | Yes: notes it runs alongside `scripts/bootstrap.py` rather than replacing or being replaced by it; added a "pulling in an upstream skill by hand" section; keeps an existing `triage-labels.md` rather than recreating one; de-numbered an illustrative tracker reference |
| `setup-pre-commit` | `skills/misc/setup-pre-commit/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `setup-ts-deep-modules` | `skills/in-progress/setup-ts-deep-modules/SKILL.md` | `321658273c`, 2026-08-19 | Yes: source-note wording only |
| `tdd` | `skills/engineering/tdd/SKILL.md` | `321658273c`, 2026-08-19 | Yes: a guard-removal-blind anti-pattern and a guard-removal verification section; golden, snapshot and overspecified test guidance |
| `teach` | `skills/productivity/teach/SKILL.md` | `321658273c`, 2026-08-19 | Yes: reworded a feature-specific example term to stay generic |
| `to-questionnaire` | `skills/productivity/to-questionnaire/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `to-spec` | `skills/engineering/to-spec/SKILL.md` | `5c89081d4b`, 2026-08-19 | Yes: a CLAUDE.md citation repointed to `.forge/tickets-and-branches.md` (upstream already carried the `ready-for-build`/`ready-for-structure` routing and capture-only rule this copy keeps) |
| `to-tickets` | `skills/engineering/to-tickets/SKILL.md` | `321658273c`, 2026-08-19 | Yes: a prior-implementation search, "no CI or full suite" acceptance-criteria phrasing, `ready-for-build`/`ready-for-structure` routing, release-note labels, and feature-pipeline stage 6 integration |
| `triage` | `skills/engineering/triage/SKILL.md` | `321658273c`, 2026-08-19 | Yes: `ready-for-build`/`ready-for-structure` state roles with routing criteria, release-note labels, `main-health` routing, and risk tickets |
| `wait-what` | `skills/productivity/wait-what/SKILL.md` | `5c89081d4b`, 2026-08-19 | No |
| `wayfinder` | `skills/engineering/wayfinder/SKILL.md` | `321658273c`, 2026-08-19 | Yes: de-numbered illustrative issue references |
| `wizard` | `skills/engineering/wizard/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `writing-beats` | `skills/in-progress/writing-beats/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `writing-for-agents` | `skills/productivity/writing-for-agents/SKILL.md` | `321658273c`, 2026-08-19 | No |
| `writing-fragments` | `skills/in-progress/writing-fragments/SKILL.md` | `5c89081d4b`, 2026-08-19 | Yes: reworded a word that collided with the contamination denylist |
| `writing-shape` | `skills/in-progress/writing-shape/SKILL.md` | `5c89081d4b`, 2026-08-19 | No |

`pr`'s "the shape of the change" section carries a nested attribution: it reproduces the `show-me` skill (HumanLayer, `humanlayer/skills`, https://github.com/humanlayer/skills, `plugins/show-me/skills/show-me/SKILL.md`) almost word for word, aimed at a diff instead of a live conversation, recorded in `pr/CREDITS.md` and in that skill's own frontmatter rather than as a code dependency. `show-me` is MIT licensed (copyright HumanLayer); the licence text is included verbatim at [`licenses/MIT-humanlayer-skills.txt`](./licenses/MIT-humanlayer-skills.txt).

## `impeccable` (Apache License 2.0, https://github.com/pbakaus/impeccable)

Author: Paul Bakaus.
Licence: Apache License 2.0 (see `licenses/APACHE-2.0-impeccable.txt`), plus the upstream NOTICE file (`licenses/NOTICE-impeccable.md`).
Pinned at tag `skill-v4.7.0`, commit `aeeb3d8c30b5f95aeeb3e893b0f1a308af8fdb8f` (2026-10-19), as recorded in `skills-lock.json`.
Shipped here unmodified, verbatim, under `.agents/skills/impeccable/`; any redistribution of it must carry its NOTICE file forward.
Because it is kept byte-for-byte, TheForge's own contamination-guard pre-commit hooks (the issue-reference check and the denylist check) exclude this directory — its own upstream issue references and vocabulary are its content, not a leak from TheForge's side (see `.pre-commit-config.yaml`).

## Written for TheForge

These skills are TheForge's own, covered by its MIT licence: `architecture-discovery`, `build-thread-brief`, `consolidated-decisions`, `coordinator`, `feature-pipeline`, `forge-sync`, `implement-with-merge`, `post-merge-review`, `queue-sweep`, `release-notes`, `requirements-spec`, `security-docs`, `self-review` and `watch-main-ci`.

## Adding a third-party file

Any third-party file taken into this project (a skill, a vendored script, a font, a data file) is credited here with its licence text alongside under `licenses/`, in the PR that adds it, not afterwards (SDLC-093).
