# ADR-0008: Retrofitting an existing project uses a real `copier copy` against the live repo, never a synthesized answers file

**Status:** accepted

## Context

TheForge was designed around `copier copy` generating a brand-new, empty project (ADR-0001).
It had no story for a repository that already exists independently of the template, with its own `CLAUDE.md`, skills, labels, CI and docs layout (the issue "How well does TheForge apply to an existing project, not just a fresh `copier copy`?").
Real consuming projects are already blocked on this decision, with their own conversion tickets waiting on it.

Copier has no built-in "adopt" mode.
The only path its own documentation and community practice validate is running `copier copy` for real against the live, populated directory, resolving the collisions it raises under human review at that time, and letting Copier itself write the resulting `.copier-answers.yml` from that run.
Hand-writing `.copier-answers.yml` to make `copier update` think a project was already generated is explicitly unsupported: it desyncs the three-way diff `copier update` relies on and produces unpredictable results on the next sync.

The root README already documents the mechanism at a human-reader level: a real `copier copy --trust --overwrite` run against an existing checkout, under "Adopting it into an existing repository". This ADR is the decision record behind that mechanism, and `template/.agents/skills/retrofit-existing-project/SKILL.md` (`docs/design/retrofit-existing-project.md`) is the full agent-run procedure built on it.

## Decision

Retrofitting TheForge onto an existing project always runs a real `copier copy --trust --overwrite <ref> <target-repo-root>` directly against the target's existing checkout, never a hand-synthesized `.copier-answers.yml`.

`CLAUDE.md` and `AGENTS.md` are the one exception: both are already present (they are listed under `_skip_if_exists`), so Copier leaves their content untouched by construction.
They get an explicit, hand-tailored rewrite instead — mapping every existing rule onto a forge file, a logged departure, or the project's own remaining content — never a Copier-driven overwrite, and never `forge-sync`'s positional-span entrypoint migration (ADR-0006), which assumes a prior forge-rendered `CLAUDE.md` to diff against. A retrofit target has never been a forge consumer, so no such prior render exists.

Every other colliding file (skills, CI workflows, pre-commit hooks, docs) goes through Copier's own collision handling, replaced with the forge version by default; a departure from that default is upstreamed to TheForge or logged in `docs/forge-overrides.md`, never silently dropped.

GitHub labels and the five standing tracker issues are not files, so Copier's own collision handling never sees them. They are reconciled separately: the target's existing standing-tracker issues are retitled to the exact titles `bootstrap.py`'s `ensure_trackers` searches for, before the copy runs, so its existing title-match reuse records the real issue numbers instead of creating duplicates.

## Alternatives rejected

- **Hand-synthesizing `.copier-answers.yml`.** Rejected outright: unsupported by Copier itself, and it desyncs every later `copier update`.
- **A separate "partial adoption" path for picking individual pieces.** Rejected: cherry-picking pieces of TheForge by hand is the adopting project's own business, not something TheForge documents or automates. Full retrofit — becoming an ongoing `copier update`-tracked consumer — is the only supported path.
- **Reconciling GitHub labels and trackers by hand, issue by issue, rather than by retitling for reuse.** Rejected: `bootstrap.py`'s `ensure_trackers` already reuses a tracker found by exact title and never edits one (existing behaviour, not new). Retitling first is less work than writing new reconciliation logic and reuses a control that already has its own guard tests.

## Consequences

- `copier.yml`'s `_tasks` (`bootstrap.py --from-copier`; a condensed-copy generator ran here until ADR-0012 retired it) run with write access to a populated, real repository with real collaborators and open work, not an empty scratch directory — a materially larger blast radius than ordinary generation. `docs/security/threat-model.md`'s new boundary B8 and its STRIDE rows record the delta; the retitle-before-copy precondition and a post-run duplicate check are this ADR's answer to it.
- The resulting diff is large enough, for a project with years of accumulated process, that it lands as several sequenced PRs rather than one (the retrofit skill's own landing order: forge import first, skills second, CI/labels/docs third), each through the target's own full review gate.
- A retrofitted project's `docs/security/threat-model.md` lands as the forge's empty skeleton, same as any newly generated project's; turning it into a real document is the project's own stage-0 `security-docs` bootstrap work, not part of this retrofit.
