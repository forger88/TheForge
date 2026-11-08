# ADR-0010: Main Health TheForge watches drift and the post-merge review; its no-CI scope is interim

**Status:** accepted

## Context

Every other repository this project works in has its own dedicated Main
Health thread, watching that repository's CI and orchestrating its
post-merge review. TheForgeStaging has neither: its post-merge review is
currently orchestrated on its behalf by another repository's Main Health thread (a
temporary carve-out), and it has no GitHub Actions workflows of its own
to watch (`.github/` holds only `pull_request_template.md`;
`docs/security/threat-model.md` §1 states this explicitly). A
conventional "watch CI" Main Health role does not apply to this
repository as it stands.

## Decision

TheForgeStaging has its own dedicated, permanent Main Health TheForge
thread (one already watches it in practice; this decision makes it the
standing owner of the work below), matching the one-Main-Health-thread-per-repository pattern every
other repository in this project already uses. Its scope:

1. **Forge-drift-on-itself**, once ADR-0009's self-render gives
   TheForgeStaging its own `.copier-answers.yml`: a daily run of the same
   `check_forge_drift.py` logic every consumer's Main Health already
   runs, except here it reports how far TheForgeStaging's own rendered
   root is behind `template/` on its own `main`.
2. **This repository's own post-merge review**, moved from that other repository's
   Main Health thread to Main Health TheForge. The post-merge review tracker, watermark and
   procedure (root `CLAUDE.md`, "This repository's own post-merge
   review") are unchanged; only who orchestrates each pass changes.
3. **A local green-build stand-in**, since there is no CI to watch: a
   `pre-commit run --all-files` on `main`'s head each time the post-merge
   review routine fires (which includes the `check-render` hook),
   reported the way a consumer's Main Health reports a red CI run.
4. **A pending-note backstop**: because Main Health TheForge notices
   every merge to `main` itself through its own polling, it can post any
   pending-review note a merging thread forgot, rather than relying on
   each thread to remember. Backfilled the same way as any other pending
   note — as a comment on the tracker, never an edit to its body.

Cadence is unchanged from the existing post-merge-review cadence (before
each public-repository snapshot; otherwise roughly every ten merges or
every two to three days) — Main Health TheForge becomes the standing
owner of that cadence instead of "whichever thread notices."

This scope is interim. Once ADR-0009's self-retrofit has landed, TheForge
carries the same workflows, scripts and skills as every consumer, and
Main Health TheForge runs the standard `watch-main-ci` skill unchanged:
its forge drift check covers item 1, its Routine 2 replaces item 3 once
TheForge's own stage 0 writes `scripts/local-full-suite.sh`, and the
scheduled CI dispatch applies once the owner sets up that routine for
this repository.

## Alternatives rejected

- **Fold this permanently into another repository's Main Health thread.** Rejected at
  stage 2: it breaks the one-Main-Health-per-repository pattern,
  and that thread's own repository consumes the template, so it would
  end up reviewing the same template its own
  repository consumes.
- **Give TheForge bespoke GitHub Actions workflows now, so a
  conventional "watch CI" role applies unchanged.** Rejected: inventing
  CI only to give Main Health something conventional to watch is scope
  creep. TheForge gets CI the same way a consumer does, from the
  workflows ADR-0009's self-render brings in, and no other way.

## Consequences

- TheForgeStaging's post-merge review tracker changes which thread
  orchestrates it; the tracker, watermark and procedure themselves are
  unchanged.
- Until the self-retrofit lands, a local `pre-commit`/render-check
  stand-in is this repository's only automated signal that `main` is
  healthy. After it, TheForge has the consumer CI workflows (the per-PR
  `review-gate-check` workflow only if the owner chooses to take it), and
  no Main Health special case remains.
