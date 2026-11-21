---
name: process-map-setup
description: "Offer, once per project, to set up the process map and skills-index generation mechanism (process_map.py, process-map.yaml, docs/process-map.md, docs/agents/skills-index.md). Invoked explicitly by a stage-0 thread, per .forge/feature-pipeline.md's \"Stage 0: project inception\" section -- not matched from a loose description."
disable-model-invocation: true
---

# process-map-setup

Forge-sync places `process_map.py` in the project's `docs/tools/` unwired; a project gets a working process map (a `docs/tools/process-map.yaml` source, the generated `docs/process-map.md` and `docs/agents/skills-index.md`) only when a stage-0 thread runs this skill and the owner says yes.
Like `doc-build-setup`'s stage-0 offer: ask once, record a skip plainly, and leave a trigger for a later thread to ask again.

`docs/process-map.md` carries its graph as a fenced ```` ```d2 ```` block, not a pre-rendered image: the doc-build pipeline (`doc-build-setup`) renders it like any other diagram, so `process_map.py` never invokes `d2`.
A project that skipped `doc-build-setup` still gets readable Markdown with the D2 source visible as text, but no image until it opts in.

## 1. Ask

Ask the owner once whether to set up the process map and skills index; if a stage-0 interview is in progress, ask in the same turn, right after `impeccable`'s and `doc-build-setup`'s setup questions, rather than opening a second round.

A `docs/tools/process-map.yaml` on `main`, or this skill's own record (below), means stage 0 has already happened; on a later stage-0-shaped thread, check the project's history (`grep -rl "process-map-setup" docs/ CLAUDE.md 2>/dev/null`, or a skip note under "On skip") before asking again.

## 2. On yes

1. Confirm forge-sync placed `docs/tools/process_map.py`; this step wires it in, never copies or authors it.
   Its guard tests don't forge-sync (they are byte-identical everywhere, so they run once, in TheForge itself), and nothing here depends on them.
   It needs pyyaml: add `pyyaml==6.0.2` to `docs/tools/requirements.txt` if not already pinned (the hook below installs it in its own venv, so no project-wide install is needed for `check`).
2. Write the project's first `docs/tools/process-map.yaml` as a real, working seed, not an empty skeleton.
   Give a node, with a short `purpose` and at least one `edge` tracing why it exists, to every `.agents/skills/*/SKILL.md`, `docs/agents/*.md` and `.github/workflows/*.yml`/`*.yaml` the project has, plus `CLAUDE.md`/`AGENTS.md`, `.pre-commit-config.yaml`, `docs/principles.md`, `CONTEXT.md` and any other guard or settings file the project's rules name.
   `process_map.py`'s module docstring gives the schema `problems()` checks (`layers`, `groups`, `nodes`, `edges`; `discretionary: true` on a skill with no policy link).
   Take each `purpose`, and which rule file is each guard's or tracker's why-edge, from the project's `.forge/*.md` files and skill frontmatter descriptions.
3. Run `python3 docs/tools/process_map.py build` and `python3 docs/tools/process_map.py index` to produce `docs/process-map.md` and `docs/agents/skills-index.md` (no `d2` binary needed), then `python3 docs/tools/process_map.py check` to confirm a clean result.
4. If the project has run `doc-build-setup`, add `docs/process-map.md` to its doc-build manifest so the `d2` block renders; otherwise skip this, and re-offer `doc-build-setup` later per `doc-build-setup`'s own re-offer trigger.
5. Add a `process-map` pre-commit hook to `.pre-commit-config.yaml`, `entry: python3 docs/tools/process_map.py check`, with:
   - `language: python` and `additional_dependencies: [pyyaml==6.0.2]`, unlike the project's other `language: system` hooks, so pyyaml needs no project-wide install;
   - `pass_filenames: false`, because its single fixed subcommand rejects extra arguments;
   - `always_run: true`, because `check` re-derives every node and edge from the current tree, including a new process file its `files:` trigger doesn't know yet and a deletion pre-commit would exclude by filename.

   There is no `-tests` hook: `docs/tools/tests/` doesn't forge-sync, so a project has no local `test_process_map.py`.
6. If not already there from an earlier run, add a line to `.agents/skills/writing-for-agents/SKILL.md`, or wherever the project records it, that a new skill, agent doc, workflow or guard file updates the YAML and regenerates (`.forge/agent-skills-and-reference.md`, "Process files are nodes on the process map").
7. Record the acceptance where a skip would be recorded (below), so a later stage-0 thread can tell it ran.

## 3. On skip

Say so plainly, and don't ask again on this thread.
Record one line, in `CLAUDE.md` or `docs/decisions-log.md` (whichever the project already uses for stage-0 setup-offer records, following `doc-build-setup`'s and `impeccable`'s skip convention if one exists): the offer was made, the owner skipped it, and the date.

Name the re-offer trigger in the skip record, for later threads to watch for: the first time the project's skill or agent-doc count grows past a handful, or a thread has to `ls .agents/skills/` by hand more than once in a session to find or audit one.
A stage-8 architecture-pass thread, or a thread editing `.forge/agent-skills-and-reference.md`, hitting it re-offers this skill rather than hand-maintaining a growing list.
