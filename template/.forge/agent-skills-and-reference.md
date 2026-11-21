# Agent skills and reference docs

## Finding a skill

This project's skills live under `.agents/skills/<name>/SKILL.md`, a project-local format a harness's own skill listing may not surface.
If the owner names a skill (by name, as a `/command`, or descriptively, such as "the implement skill") that the harness does not list, check `.agents/skills/` before saying you cannot find it, then read the matching `SKILL.md` and follow it; there is no tool invocation for these.

`.agents/skills/self-review/SKILL.md` and the other skills marked `disable-model-invocation: true` are reference material or owner-invoked procedures, read when a rule points there.

The full skill set, including `impeccable` (UI review), `improve-codebase-architecture` (the stage 8 pass), `prototype` and `release-notes`, ships with TheForge rather than being installed from upstream later.
`skills-lock.json` records the pinned upstream source of each skill taken from elsewhere, and `THIRD_PARTY.md` its licence credit.
A rule that names a skill and finds it missing is a hard stop, as for any other skill (`.forge/review-gate.md`).

## Process files are nodes on the process map

Once this project has run `process-map-setup`'s stage-0 setup (`docs/tools/process-map.yaml` exists), adding, renaming or removing a skill, an agent doc under `docs/agents/`, a workflow, or a guard file listed in that YAML updates its node and how-why edges in the same PR.
Then `python3 docs/tools/process_map.py build` rewrites `docs/process-map.md` (needs pyyaml; its graph is a fenced `d2` block the doc-build pipeline renders, not this command), and `python3 docs/tools/process_map.py index` rewrites `docs/agents/skills-index.md`.
The `process-map` pre-commit hook fails when the generated files disagree with the source; the mechanism's own guard tests don't forge-sync, so they run only in TheForge itself.
A skill with no policy link is marked `discretionary: true` and needs no edge.
Before that setup, this section does not apply; a thread that keeps having to `ls .agents/skills/` by hand to find or audit a skill is the trigger `process-map-setup` names for offering it.

## Reference docs are not skills

`docs/agents/*.md` (`issue-tracker.md`, `triage-labels.md`, `domain.md`, `testing-tools.md`, `requirement-coverage.md`, `operational-constants.md`, `build-thread-setup.md`, `lessons.md`, `coordinator-core-snippet.md`) is reference material the rules and skills point into by path, with no `SKILL.md` and nothing to invoke; read it when pointed there.

## Issue tracker and labels

Issues live in the project's GitHub repository; use the `gh` command-line tool (`docs/agents/issue-tracker.md`).
The canonical labels are `needs-triage`, `needs-info`, `needs-grilling`, `ready-for-structure`, `ready-for-feature-design`, `ready-for-build`, `ready-for-human`, `wontfix` and `needs-decision`, plus the parking, queue, routing and release-note labels in `docs/agents/triage-labels.md`.
`needs-decision` marks a ticket no thread may work on until the owner has decided, whatever its other labels say.

## Domain docs

The project uses a single-context layout: `CONTEXT.md` at the repo root, `docs/adr/` and `docs/principles.md` (`docs/agents/domain.md`).
Read `docs/principles.md` before any design decision; `code-review`'s Standards axis and the design-exit pass check against it.
A principle lands there, verbatim, only once the owner approves its exact wording, and a rewording or removal needs the same approval (SDLC-068).

## Artefacts and the skills that govern them (Default)

A skill that sets an artefact's form or content is that artefact's standard (SDLC-119), and every change to a path below follows it, whatever the change is for, a closing-step status edit included.
The code review's Standards axis checks the change against the skill's form rules (`.agents/skills/code-review/SKILL.md`); on the light gate the self-review does, and the post-merge review checks again after merge (`.forge/self-review.md`, `.forge/post-merge-review.md`).
Only the skills this table names are standards; a procedural skill, saying how to run a task rather than what an artefact looks like, is not.
A document's own Conventions section restates its governing skill and may add this project's own choices, such as its ID blocks, but never contradicts it; where they disagree, the skill wins and the document is fixed.
"The artefact map" means this table plus any row a project's `CLAUDE.md` adds under its own project section (below); every reference to it, in the code review, self-review and post-merge review, covers both.

| Artefact | Governing skill | Form rules |
|---|---|---|
| `docs/requirements/requirements-specification.md` | `requirements-spec` | "What this produces" |
| `CONTEXT.md`, `CONTEXT-MAP.md` (any context document) | `domain-modeling` | `CONTEXT-FORMAT.md` |
| `docs/principles.md` | `domain-modeling` | `PRINCIPLES-FORMAT.md` |
| `docs/adr/*.md` | `domain-modeling` | `ADR-FORMAT.md` |
| `docs/security/**` | `security-docs` | the mode the change runs in (bootstrap, delta, reconcile) |
| `docs/release-notes.md` | `release-notes` | "Section shape" |
| A skill's files under `.agents/skills/`, `CLAUDE.md`, `AGENTS.md`, `.forge/*.md` | `writing-for-agents` | the whole skill; `SKILL-MECHANICS.md` for a skill's frontmatter |

No skill governs the PR body: `.github/pull_request_template.md`'s own convention is its standard (owner decision, 2026-11-14); `scripts/check_review_gate.py` mechanically checks only its `Review:` field, and the review gate's judgement enforces the rest, outside this mechanism.
A project's own test files are a governed artefact too, mapped by glob rather than fixed path, since test paths and conventions vary by project and stack.
A project adds a row, or maps its test-file glob(s) (for example `**/*.test.ts`, `tests/**/test_*.py`) to `tdd`'s `tests.md` as the form rules, for an artefact of its own, under its own project section in `CLAUDE.md`, never in this file (`.forge/forge-overrides.md`).

## Third-party files are credited in the same PR (Default)

Any third-party file taken into the repo (a skill, a vendored script, a font, a data file) is credited in `.agents/skills/THIRD_PARTY.md` with its licence text alongside, in the PR that adds it.
