# Agent skills and reference docs

## Finding a skill

This project's skills live under `.agents/skills/<name>/SKILL.md`.
They are a project-local format that a harness's own skill listing may not surface.
If the owner names a skill (by name, as a `/command`, or descriptively, such as "the implement skill") that is not in the harness's listing, check `.agents/skills/` before saying you cannot find it.
Then read the matching `SKILL.md` and follow it; there is no tool invocation for these.

`.agents/skills/self-review/SKILL.md` and the other skills marked `disable-model-invocation: true` are reference material or owner-invoked procedures: read them when a rule points there.

The full skill set, including `impeccable` (UI review), `improve-codebase-architecture` (the stage 8 pass), `prototype` and `release-notes`, ships with TheForge rather than being installed from upstream later.
`skills-lock.json` records the pinned upstream source for each skill taken from elsewhere; `THIRD_PARTY.md` carries the matching licence credit.
A rule that names a skill and finds it missing is a hard stop, as for any other skill (`.forge/review-gate.md`).

## Process files are nodes on the process map

If this project has run the `process-map-setup` skill's stage-0 setup (`docs/tools/process-map.yaml` exists), adding, renaming or removing a skill, an agent doc under `docs/agents/`, a workflow, or a guard file listed in that YAML updates that file's node and its how-why edges in the same PR.
Then `python3 docs/tools/process_map.py build` rewrites `docs/process-map.md` (needs pyyaml; its graph is a fenced `d2` block the project's doc-build pipeline renders, not a file this command renders itself), and `python3 docs/tools/process_map.py index` rewrites `docs/agents/skills-index.md`.
The `process-map` pre-commit hook fails when the generated files disagree with the source.
The mechanism's own guard tests don't forge-sync, so they run only in TheForge itself.
A skill with no policy link is marked `discretionary: true`; it does not need an edge.
If the project has not run `process-map-setup`, this section does not apply yet; a thread that keeps needing to `ls .agents/skills/` by hand to find or audit a skill is the trigger that skill names for offering it.

## Reference docs are not skills

`docs/agents/*.md` (`issue-tracker.md`, `triage-labels.md`, `domain.md`, `testing-tools.md`, `requirement-coverage.md`, `operational-constants.md`, `build-thread-setup.md`, `lessons.md`, `coordinator-core-snippet.md`) is reference material that the rules and skills point into by path.
None of it has a `SKILL.md` or is invokable; read it when pointed there.

## Issue tracker and labels

Issues live in the project's GitHub repository; use the `gh` command-line tool (`docs/agents/issue-tracker.md`).
The canonical labels are `needs-triage`, `needs-info`, `needs-grilling`, `ready-for-structure`, `ready-for-feature-design`, `ready-for-build`, `ready-for-human`, `wontfix` and `needs-decision`, plus the parking, queue, routing and release-note labels in `docs/agents/triage-labels.md`.
`needs-decision` marks a ticket no thread may work on until the owner has decided, whatever its other labels say.

## Domain docs

The project uses a single-context layout: `CONTEXT.md` at the repo root, `docs/adr/` and `docs/principles.md` (`docs/agents/domain.md`).
Read `docs/principles.md` before any design decision; `code-review`'s Standards axis and the design-exit pass check against it, and a principle lands there, verbatim, only once the owner approves its exact wording; a rewording or removal needs the same approval (SDLC-068).

## Artefacts and the skills that govern them (Default)

A skill that sets the form or content of an artefact is that artefact's standard (SDLC-119).
Every change to a path below follows its governing skill, whatever the change is for, a closing-step status edit included.
The code review's Standards axis checks the change against the skill's form rules (`.agents/skills/code-review/SKILL.md`); on the light gate the self-review does, and the post-merge review checks again after merge (`.forge/self-review.md`, `.forge/post-merge-review.md`).
Only the skills this table names are standards; a procedural skill, one that says how to run a task rather than what an artefact looks like, is not.
A document's own Conventions section restates its governing skill and may add this project's own choices, such as its ID blocks, but never contradicts it; where they disagree, the skill wins and the document is the thing to fix.
"The artefact map" means this table together with any row a project's own `CLAUDE.md` adds under its own project section (below); every reference elsewhere to the artefact map, in the code review, the self-review and the post-merge review, covers both.

| Artefact | Governing skill | Form rules |
|---|---|---|
| `docs/requirements/requirements-specification.md` | `requirements-spec` | "What this produces" |
| `CONTEXT.md`, `CONTEXT-MAP.md` (any context document) | `domain-modeling` | `CONTEXT-FORMAT.md` |
| `docs/principles.md` | `domain-modeling` | `PRINCIPLES-FORMAT.md` |
| `docs/adr/*.md` | `domain-modeling` | `ADR-FORMAT.md` |
| `docs/security/**` | `security-docs` | the mode the change runs in (bootstrap, delta, reconcile) |
| `docs/release-notes.md` | `release-notes` | "Section shape" |
| A skill's files under `.agents/skills/`, `CLAUDE.md`, `AGENTS.md`, `.forge/*.md` | `writing-for-agents` | the whole skill; `SKILL-MECHANICS.md` for a skill's frontmatter |

No skill governs the PR body: `.github/pull_request_template.md`'s own convention is this artefact's standard instead, not by a skill (owner decision, 2026-11-14); `scripts/check_review_gate.py` mechanically checks only its `Review:` field against the review gate, and the rest of the template is enforced by the review gate's own judgement call, outside this mechanism.
A project's own test files are a governed artefact too, mapped by glob rather than by a fixed path, since test paths and conventions vary per project and per stack.
A project adds a row, or maps its own test-file glob(s) (for example `**/*.test.ts`, `tests/**/test_*.py`) to `tdd`'s `tests.md` as the form rules, for an artefact of its own under its own project section in `CLAUDE.md`, never in this file (`.forge/forge-overrides.md`).

## Third-party files are credited in the same PR (Default)

Any third-party file taken into the repo (a skill, a vendored script, a font, a data file) is credited in `.agents/skills/THIRD_PARTY.md` with its licence text alongside, in the PR that adds it.
