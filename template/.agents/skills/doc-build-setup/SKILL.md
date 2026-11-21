---
name: doc-build-setup
description: "Offer, once per project, to set up the manifest-driven document/diagram build pipeline (document_build.py, render_diagrams.py, document-build.json). Invoked explicitly by a stage-0 thread, per .forge/feature-pipeline.md's \"Stage 0: project inception\" section -- not matched from a loose description."
disable-model-invocation: true
---

# doc-build-setup

Forge-sync places the document/diagram build pipeline's scripts (`document_build.py`, `render_diagrams.py`) in the project's `docs/tools/` unwired; a project gets a working pipeline, with its `document-build.json` manifest, only when a stage-0 thread runs this skill and the owner says yes.
Like `impeccable`'s stage-0 offer: ask once, record a skip plainly, and leave a trigger for a later thread to ask again.

## 1. Ask

Ask the owner once whether to set up the document/diagram build pipeline; if a stage-0 interview is in progress, ask in the same turn, right after `impeccable`'s setup question, rather than opening a second round.

A `docs/principles.md` holding at least one owner-confirmed principle beyond the forge-seeded ones on `main`, or this skill's own record (below), means stage 0 has already happened; on a later stage-0-shaped thread, check the project's history (`grep -rl "doc-build-setup" docs/ CLAUDE.md 2>/dev/null`, or a skip note under "On skip") before asking again.

## 2. On yes

1. Confirm forge-sync placed `docs/tools/render_diagrams.py`, `docs/tools/document_build.py`, `docs/tools/check_document_consistency.py` and `docs/tools/requirements.txt`; this step wires them in, never copies or authors them.
   Their guard tests don't forge-sync (they are byte-identical everywhere, so they run once, in TheForge itself), and nothing here depends on them.
   Confirm `.github/workflows/documentation.yml` is present too: it is `workflow_dispatch`-only and reads its pinned toolchain versions from `docs/tools/document-build.json`, so it needs no project-specific editing.
2. Write the project's first `docs/tools/document-build.json` as a real, working manifest, not an empty skeleton: the required `schema_version` (2) and a `documents` list with one entry the project actually has (its README, its architecture description, or another `.md` source); `repository_root` only if it isn't the manifest's own directory; and a `toolchain` block giving each tool's `command` and the pinned `version` installed in this environment (`pandoc`, `d2`, `weasyprint`, and `mmdc` only if the sources use `mermaid` fenced blocks), plus a bare `font` string `fc-match` can resolve.
3. Fill in the seeded `docs/development/documentation-build.md` with the toolchain versions step 2 pinned, keeping its "how to add a document to the manifest" note rather than rewriting it, so the note never drifts from what this skill ships.
4. Append two steps to the project's local full-suite script (`watch-main-ci`'s Per-repo values, "Local full-suite script"), each only if not already present; if one exists from an earlier run, leave it and say so:
   - the doc build, as a full render (`python3 docs/tools/document_build.py`), not `--check`, because the local full-suite run needs the real signal even though it costs the whole doc toolchain install;
   - right after it, the consistency check, `python3 docs/tools/check_document_consistency.py --also 'docs/adr/*.md'`: the manifest's `documents` plus the project's ADRs, the same sets step 5 scopes the hook to.
5. Add a `doc-consistency` pre-commit hook to `.pre-commit-config.yaml`, `entry: python3 docs/tools/check_document_consistency.py --also 'docs/adr/*.md'`, with:
   - `language: system`, not an isolated `additional_dependencies` venv, because its D2 check needs `render_diagrams`'s toolchain, which `docs/tools/requirements.txt` installs project-wide;
   - `pass_filenames: false`, because it always checks the whole document set;
   - `files:` covering `docs/tools/document-build.json`, the requirements specification, `docs/adr/`, the checker's own source and `render_diagrams.py`, not `always_run`, since running pandoc/d2 on every commit is too slow.

   A manifest entry added outside these paths needs a matching addition to the `files:` regex in the same change, or the hook stops covering it.
   There is no `-tests` hook: `docs/tools/tests/` doesn't forge-sync, so a project has no local copy to run.
6. Record the acceptance where a skip would be recorded (below), so a later stage-0 thread can tell it ran.

## 3. On skip

Say so plainly, and don't ask again on this thread.
Record one line, in `CLAUDE.md` or `docs/decisions-log.md` (whichever the project already uses for stage-0 setup-offer records, following `impeccable`'s skip convention if one exists): the offer was made, the owner skipped it, and the date.

Name the re-offer trigger in the skip record, for later threads to watch for: the first time a design doc or the architecture description needs a diagram or built document it can't yet render.
A stage-3/5 design thread hitting it re-offers this skill rather than hand-rolling a one-off render step.
