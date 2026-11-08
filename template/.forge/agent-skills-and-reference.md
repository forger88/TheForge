# Agent skills and reference docs

## Finding a skill

This project's skills live under `.agents/skills/<name>/SKILL.md`.
They are a project-local format that a harness's own skill listing may not surface.
If the owner names a skill (by name, as a `/command`, or descriptively, such as "the implement skill") that is not in the harness's listing, check `.agents/skills/` before saying you cannot find it.
Then read the matching `SKILL.md` and follow it; there is no tool invocation for these.

`.agents/skills/self-review/SKILL.md` and the other skills marked `disable-model-invocation: true` are reference material or owner-invoked procedures: read them when a rule points there.

The full skill set, including `impeccable` (UI review), `improve-codebase-architecture` (the stage 8 pass), `prototype` and `release-notes`, ships with the template rather than being installed from upstream later.
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

## Writing for agents

A change to a skill, `CLAUDE.md`, `AGENTS.md` or a `.forge/` file follows `.agents/skills/writing-for-agents/SKILL.md`.

## Third-party files are credited in the same PR (Default)

Any third-party file taken into the repo (a skill, a vendored script, a font, a data file) is credited in `.agents/skills/THIRD_PARTY.md` with its licence text alongside, in the PR that adds it.
