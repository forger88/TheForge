---
name: process-map-setup
description: "Offer, once per project, to set up the process map and skills-index generation mechanism (process_map.py, process-map.yaml, docs/process-map.md, docs/agents/skills-index.md). Invoked explicitly by a stage-0 thread, per .forge/feature-pipeline.md's \"Stage 0: project inception\" section -- not matched from a loose description."
disable-model-invocation: true
---

# process-map-setup

A project does not get the working process map (`process_map.py`, a `docs/tools/process-map.yaml` source file, the generated `docs/process-map.md` and `docs/agents/skills-index.md`) just because `process_map.py` is forge-synced into the project's `docs/tools/`, where it arrives present but unwired. It gets the map only when a stage-0 thread runs this skill and the owner says yes. This mirrors the `doc-build-setup` skill's own stage-0 offer: ask once, record a skip plainly, and leave a trigger for a later thread to ask again if the project turns out to need it after all.

`docs/process-map.md` carries its graph as a fenced ```` ```d2 ```` code block, not a separately pre-rendered image: the project's own doc-build pipeline (`doc-build-setup`) renders it into an image the same way it renders every other diagram in a built document, so `process_map.py` itself never invokes `d2` and this skill adds `docs/process-map.md` to the project's doc-build manifest in the same step. A project that has skipped `doc-build-setup` still gets a readable Markdown file with the D2 source visible as text; it just has no rendered image until it opts into that pipeline too.

## 1. Ask

Ask the owner once whether to set up the process map and skills-index mechanism. If a stage-0 interview (the same conversation that runs `impeccable`'s and `doc-build-setup`'s own setup questions) is already in progress, ask this in the same turn, right after those questions, rather than opening a second round.

A project's own `docs/tools/process-map.yaml` existing on `main`, or an earlier run of this skill's own record (below), means stage 0 has already happened; don't ask again on a later stage-0-shaped thread without checking the project's history first (`grep -rl "process-map-setup" docs/ CLAUDE.md 2>/dev/null`, or a skip note under "On skip" below).

## 2. On yes

1. Confirm `docs/tools/process_map.py` is present in the project -- forge-sync already placed it, so this step wires it in; it neither copies nor authors it. Its own guard tests don't forge-sync (they're byte-identical everywhere and never project-specific, so they run once, in TheForge itself); nothing here depends on them being present. It needs pyyaml; add `pyyaml==6.0.2` to `docs/tools/requirements.txt` if that file does not already pin it (the `process-map` pre-commit hook below installs it into its own isolated venv via `additional_dependencies`, so no project-wide install is required just to run `check` on every commit).
2. Write the project's own first `docs/tools/process-map.yaml`. Ship it as a real, working seed, not an empty skeleton: enumerate every file under `.agents/skills/*/SKILL.md`, `docs/agents/*.md` and `.github/workflows/*.yml`/`.github/workflows/*.yaml` the project actually has, plus `CLAUDE.md`/`AGENTS.md`, `.pre-commit-config.yaml`, `docs/principles.md`, `CONTEXT.md` and any other guard or settings file this project's own rules name, and give each one a node with a short `purpose` and at least one `edge` tracing why it exists (see `process_map.py`'s own module docstring for the exact schema `problems()` checks: `layers`, `groups`, `nodes`, `edges`; `discretionary: true` on a skill with no policy link). Use this project's own `.forge/*.md` rule files and skill frontmatter descriptions as the source for each node's `purpose` and for which rule file is each guard's or tracker's why-edge.
3. Run `python3 docs/tools/process_map.py build` and `python3 docs/tools/process_map.py index` to produce `docs/process-map.md` (its graph as a fenced ```` ```d2 ```` block, no separate rendering step or `d2` binary needed here) and `docs/agents/skills-index.md`. Run `python3 docs/tools/process_map.py check` once more to confirm a clean result before moving on.
4. If this project has run `doc-build-setup`, add `docs/process-map.md` to its doc-build manifest so the fenced `d2` block renders into an image when the project's documents are built; otherwise skip this sub-step, and offer `doc-build-setup` again later per that skill's own re-offer trigger.
5. Add a pre-commit hook to `.pre-commit-config.yaml`, `language: python` with `additional_dependencies: [pyyaml==6.0.2]` (not `language: system`, unlike this project's other hooks, precisely so pyyaml needs no project-wide install) and `pass_filenames: false` (it ignores the paths pre-commit would otherwise append, since it runs a single fixed subcommand that rejects extra positional arguments):
   - `process-map`, `entry: python3 docs/tools/process_map.py check`, `always_run: true` -- `check` re-derives every node and edge from the current tree on each run, including a brand-new process file this hook's own `files:` trigger has not been told about yet and a deletion pre-commit would otherwise exclude by filename, so it always runs rather than being filtered to a changed-files subset.

   There is no matching `-tests` hook: `docs/tools/tests/` doesn't forge-sync (its guard tests are byte-identical everywhere and never project-specific, so they run once, in TheForge itself); a project gets no local copy of `test_process_map.py` to discover.
6. Append a line to `.agents/skills/writing-for-agents/SKILL.md` or wherever this project records "a new skill/agent-doc/workflow/guard file updates the YAML and regenerates" (see `.forge/agent-skills-and-reference.md`'s "Process files are nodes on the process map" section) if it is not already there from an earlier run of this skill.
7. Record the acceptance in the same place a skip would be recorded (below), so a later stage-0 thread can tell it already ran.

## 3. On skip

Say so plainly -- don't silently drop the offer and don't ask again on this thread. Record the skip in `CLAUDE.md` or `docs/decisions-log.md` (whichever this project already uses for stage-0 setup-offer records; follow `doc-build-setup`'s and `impeccable`'s own skip convention if one exists) as one line: the offer was made, the owner skipped it, and the date.

Name the re-offer trigger for later threads to watch for: the first time the project's skill or agent-doc count grows past a handful, or a thread has to `ls .agents/skills/` by hand more than once in a session to find or audit one. A stage-8 architecture-pass thread, or a thread editing `.forge/agent-skills-and-reference.md`, hitting that trigger re-offers this skill rather than hand-maintaining a growing list with no mechanical check.
