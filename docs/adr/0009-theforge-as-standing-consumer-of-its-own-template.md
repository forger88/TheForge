# ADR-0009: TheForge is a standing consumer of its own template

**Status:** accepted

## Context

TheForgeStaging's own root `CLAUDE.md`, `AGENTS.md` and process skills carry
hand-maintained copies of rules and procedures that `template/` already
ships to every consumer. Because the root copies are not rendered from
`template/`, they silently drift from what TheForge actually ships: a
`.forge/` rule file added under `template/` never loads for TheForge
itself, and a prose change to a shipped skill never reaches TheForge's
own copy. This is the problem the issue "Give TheForge a way to properly review and maintain itself" exists to close.

TheForgeStaging has never rendered itself: it has no `.copier-answers.yml`,
no root `.forge/` directory, and no root `.agents/skills/` directory. Its
root `CLAUDE.md` is still in the pre-ADR-0006 shape: it inlines TheForge's
own meta-rules directly rather than importing `@.forge/entrypoint.md`.

## Decision

TheForgeStaging renders `template/` onto its own root through a
self-referential Copier operation: `_src_path` is this same repository's
HTTPS URL (never a local path or `.`), and the source and destination
commits differ. A scratch-clone spike at that issue's stage 3 review confirmed
that Copier's `_subdirectory`/`_skip_if_exists`/`--conflict inline`
machinery behaves correctly in this configuration, on both `copy` and a
following `update`, and touches nothing outside the rendered paths.

TheForgeStaging's root has never been rendered, so its first self-render
is a retrofit (ADR-0008), run with `retrofit-existing-project` on
TheForge itself: a real `copier copy --trust --overwrite` against the
live checkout, a hand-rewritten `CLAUDE.md` and `AGENTS.md`, and
collision triage for every other file the render overwrites. It is never
`forge-sync`'s positional entrypoint migration (ADR-0006), which needs a
prior forge render that does not exist here. Every TheForge-specific
meta-rule (project-neutrality, the raw-clone tripwire, commit-identity,
back-porting, this repository's own threat model and post-merge review,
"Contributing to `template/`", the agent-tagging waiver) survives as
project-owned content after the `@.forge/entrypoint.md` import line. Every
later self-sync is ordinary `forge-sync`.

`template/.agents/skills/*` then render onto TheForgeStaging's own root
`.agents/skills/` exactly as for any consumer. The temporary carve-out
that has TheForge borrow another consuming project's `feature-pipeline`, `grill-me` and
review skills is retired in the same change: TheForge runs its own
shipped skills directly from then on.

No colliding file is specially cased. The first render overwrites five
existing root files (`.pre-commit-config.yaml`, `.claude/hooks/session-start.sh`,
`.claude/settings.json`, `.github/pull_request_template.md`, `.gitignore`);
each takes the forge version, with every line TheForge keeps on top
recorded as a `docs/forge-overrides.md` entry, and every later self-sync
resolves conflicts on them through the existing override mechanism. For
`.pre-commit-config.yaml` that entry names every TheForge meta-guard hook,
none of which may be absent from `main` at any point.

Self-sync never touches `copier.yml`, `template/` itself, root
`scripts/*.sh`, or `.theforge-denylist*`: those stay forge-source, kept
out of every render by `_subdirectory: template`, exactly as today.

Self-sync stays deliberately triggered, never automatic on merge: a
merged `template/` change only becomes TheForge's own active governance
on the next explicit self-sync (reusing the sync-mechanism issue's already-settled
principle). No `--trust` Copier run against TheForgeStaging's own root —
neither the first retrofit `copier copy` nor any later `copier update` —
happens until the issue "forge-sync: check upstream copier.yml and executable files before copier update --trust runs them" (checking upstream `copier.yml` and executable files before
`copier update --trust` runs them) is closed or substantially mitigated.
Self-sync tracks `main` HEAD, the same as every other consumer, and is
not additionally gated on release tagging existing first
(owner decision, 2026-10-27, on the stage 3 decision card).

## Alternatives rejected

- **Route self-sync through the planned public repository instead of
  staging-onto-itself.** Rejected at stage 2: this would make
  TheForge's own governance uplift depend on the still-undecided,
  `hanging` private-to-public transfer mechanism, which is out of scope
  for the self-governance issue to resolve.
- **Hand-port `template/` changes into TheForge's own root on an ad hoc
  basis.** This is the status quo the self-governance issue exists to end: nothing
  guarantees a port happens, and nothing catches when one is missed.
- **Build a bespoke, non-Copier sync mechanism just for TheForge's own
  root.** Rejected: it would reinvent what `forge-sync` already does
  correctly for every other consumer, doubling the surface that needs
  maintaining and testing.
- **Run `forge-sync`'s entrypoint migration on the root.** Rejected at
  the stage 3 review: that procedure deletes only lines matching a prior
  forge render, which TheForge's root never had, so it would remove
  nothing; ADR-0008 already decides that a never-rendered repository is
  retrofitted.
- **Special-case `.pre-commit-config.yaml` as project-owned
  (`_skip_if_exists`), like `CLAUDE.md`.** Rejected: that would freeze
  TheForge's own pre-commit hooks against every future generic
  improvement `template/` ships, reproducing the exact drift problem
  this ADR exists to close, one file later.

## Consequences

- The first self-render re-uses the existing B8 (Retrofit) trust
  boundary and later self-syncs re-use B5 (Sync), reflexively, rather
  than opening a new one; `docs/design/theforge-self-governance.md`
  carries the threat-model delta.
- The drift check counts only commits that touch what a render reads
  (upstream's `_subdirectory` and `copier.yml`); a whole-repository count
  would never reach zero for a self-consumer, since each sync PR's own
  merge follows `_commit`.
- TheForge then carries what every consumer carries, including the
  shipped lifecycle document (its statements as the template seeds
  them) and the four standing trackers it lacks today, and owes a
  stage 0 of its own. Whether it also takes the per-PR
  `review-gate-check` workflow, which spends Actions minutes, is the
  owner's decision on the self-governance issue.
- Every future `template/` process improvement reaches TheForge's own
  operating rules through the same reviewed sync path a consumer uses,
  closing the drift this ADR exists to close.
- Self-sync against TheForgeStaging's own root runs with whatever
  credential the triggering session holds — the highest privilege this
  repository has. That pre-run-check issue's closure is a precondition of turning self-sync
  on, not a parallel-track improvement.
- A harness without recursive `@`-import resolution must open
  `.forge/entrypoint.md` and then each file it lists, the same residual
  ADR-0006 already records.
