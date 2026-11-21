---
name: doc-build-setup
description: "Offer, once per project, to set up the manifest-driven document/diagram build pipeline (document_build.py, render_diagrams.py, document-build.json). Invoked explicitly by a stage-0 thread, per .forge/feature-pipeline.md's \"Stage 0: project inception\" section -- not matched from a loose description."
disable-model-invocation: true
---

# doc-build-setup

A project does not get the working document/diagram build pipeline (`document_build.py`, `render_diagrams.py`, the `document-build.json` manifest) just because its scripts are forge-synced into the project's `docs/tools/`, where they arrive present but unwired. It gets it only when a stage-0 thread runs this skill and the owner says yes. This mirrors the `impeccable` skill's own stage-0 offer: ask once, record a skip plainly, and leave a trigger for a later thread to ask again if the project turns out to need it after all.

## 1. Ask

Ask the owner once whether to set up the document/diagram build pipeline. If a stage-0 interview (the same conversation that runs `impeccable`'s own setup question) is already in progress, ask this in the same turn, right after that question, rather than opening a second round.

A project's own `docs/principles.md` holding at least one owner-confirmed principle beyond the forge-seeded ones on `main`, or an earlier run of this skill's own record (below), means stage 0 has already happened; don't ask again on a later stage-0-shaped thread without checking the project's history first (`grep -rl "doc-build-setup" docs/ CLAUDE.md 2>/dev/null`, or a skip note under "On skip" below).

## 2. On yes

1. Confirm the diagram-rendering, document-build and cross-document-consistency scripts and their requirements file are already in the project (`docs/tools/render_diagrams.py`, `docs/tools/document_build.py`, `docs/tools/check_document_consistency.py`, `docs/tools/requirements.txt`) -- forge-sync placed them, so this step wires them in; it neither copies nor authors them. Their own guard tests don't forge-sync (they're byte-identical everywhere and never project-specific, so they run once, in TheForge itself); nothing here depends on them being present. Confirm `.github/workflows/documentation.yml` is present the same way: it is `workflow_dispatch`-only, and reads this project's own `docs/tools/document-build.json` for its pinned toolchain versions, so it needs no project-specific editing before it can run.
2. Write the project's own first `docs/tools/document-build.json`. Ship it as a real, working example manifest, not an empty skeleton: the required `schema_version` (2) and `documents` list with one entry the project actually has (its README, its architecture description, or whatever `.md` source is available), an optional `repository_root` only if it isn't the manifest's own directory, and a `toolchain` block giving each tool's `command` and pinned `version` actually installed in this environment (`pandoc`, `d2`, `weasyprint`, and `mmdc` only if the project's own sources use `mermaid` fenced blocks) plus a bare `font` string the environment's `fc-match` can resolve.
3. Fill in `docs/development/documentation-build.md`, which the project was generated with from the forge seed, with the toolchain versions step 2 pinned.
4. Append two steps to the project's local full-suite script (`watch-main-ci`'s Per-repo values, "Local full-suite script"), the doc build and then the consistency check, each only if not already present. First, the doc-build step: a full render (`python3 docs/tools/document_build.py`), not `--check` -- the local full-suite run needs the real signal, not a cheap validation-only pass, even though it costs every run the whole doc toolchain install. If the script already has a doc-build step from an earlier run of this skill, leave it alone and say so instead of duplicating it. Second, right after it, the consistency step: if the script does not already run `check_document_consistency.py`, append a step that runs `python3 docs/tools/check_document_consistency.py --also 'docs/adr/*.md'` -- the manifest's own `documents` list plus the project's ADRs, the same two document sets step 5 below scopes the pre-commit hook to.
5. Add a pre-commit hook to `.pre-commit-config.yaml`, `language: system` (not an isolated `additional_dependencies` venv: the checker's D2 check genuinely needs `render_diagrams`'s own toolchain, which this project already installs project-wide via `docs/tools/requirements.txt`) and `pass_filenames: false` (the command always checks the whole document set, never a per-file subset):
   - `doc-consistency`, `entry: python3 docs/tools/check_document_consistency.py --also 'docs/adr/*.md'`, triggered by `docs/tools/document-build.json`, the requirements specification, anything under `docs/adr/`, the checker's own source, and `render_diagrams.py` -- not `always_run`, since spinning up pandoc/d2 on every commit regardless of what changed is too slow for this hook's own trigger scope (unlike `process-map`'s cheap, always-run `check`). A manifest entry added outside these paths needs a matching addition to this hook's `files:` regex in the same change, or the hook stops covering it.

   There is no matching `-tests` hook: `docs/tools/tests/` doesn't forge-sync (its guard tests are byte-identical everywhere and never project-specific, so they run once, in TheForge itself); a project gets no local copy to discover.
6. Record the acceptance in the same place a skip would be recorded (below), so a later stage-0 thread can tell it already ran.

## 3. On skip

Say so plainly -- don't silently drop the offer and don't ask again on this thread. Record the skip in `CLAUDE.md` or `docs/decisions-log.md` (whichever this project already uses for stage-0 setup-offer records; follow the `impeccable` skip's own convention if one exists) as one line: the offer was made, the owner skipped it, and the date.

Name the re-offer trigger for later threads to watch for: the first time a design doc or the project's architecture description needs a diagram or a built document it can't yet render. A stage-3/5 design thread hitting that trigger re-offers this skill rather than hand-rolling a one-off render step.

The seeded guide, `docs/development/documentation-build.md`, carries the agent-facing "how to add a document to the manifest" note -- keep the seeded note and fill in the versions at step 3 above rather than rewriting it by hand, so the note never drifts between what this skill ships and what a project's own copy says.
