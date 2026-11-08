# TheForge

TheForge is a [Copier](https://copier.readthedocs.io/) template that gives a brand-new repository a complete, opinionated engineering process for software built mostly by AI agents, with a human owner directing them.

What a generated project gets:

- **Ticket-first development.** Nothing merges to `main` without a ticket, every branch is cut fresh from `main`, and every PR records what it was checked against.
- **A feature pipeline.** Idea, grilling interview, high-level design, requirements approval, detailed design, ticketing, build, post-merge review and architecture pass, each stage leaving a record the next stage points at.
- **A self-review gate.** Two clean-context review axes (Standards and Spec) followed by a mandatory self-review checklist that looks at every *other* place a diff could break.
- **A post-merge review pass.** A higher-tier second review of everything merged since a watermark, including a STRIDE security axis.
- **Security docs that stay current.** A threat-model skeleton plus a `security-docs` skill with bootstrap, delta and reconcile modes.
- **Capability tiers.** Work is matched to the judgement it needs (design-tier, review-tier, build-tier, mechanical-tier), not to a model name, so the process runs on any agent harness.
- **A software development lifecycle document** with numbered `SDLC-NNN` statements the owner controls, and the skills, rules and reference docs that implement it.
- **Mechanical guards** shipped as pre-commit hooks: branch names, module and function size caps, a dead-code ratchet, a no-snapshot-test ban and a one-sentence-per-line check for the forge-owned rule files.

## Using it

You need Python 3.10+ and Copier 9 or later (`pipx install copier`).

```bash
copier copy --trust gh:forger88/TheForge my-new-project
```

`--trust` is required because the template runs one post-creation task, `scripts/bootstrap.py`, which creates the project's GitHub labels and five standing tracker issues.
Read that script before trusting it; it is one short file.
It needs a `GITHUB_TOKEN` scoped to issues and labels on the one new repository only. It skips its GitHub steps cleanly (printing what to do later) when no token is set, and prints a warning and exits cleanly, without touching the generated project, when a token is set but is refused or the repository does not exist yet.
Run it again at any time with `python3 scripts/bootstrap.py` (add `--dry-run` to see what it would do).

To pull later improvements from TheForge into a generated project, use the generated project's `forge-sync` skill, which wraps `copier update`.
TheForge's own release notes are in [`docs/release-notes.md`](docs/release-notes.md), with one section per release; each tag's message carries that section. The `release-notes` skill, shipped to generated projects under `template/.agents/skills/release-notes/`, describes how such notes are written.

**Did you get here by GitHub's "Use this template" button, or a clone whose remote no longer names `forger88/TheForge`, instead of `copier copy`?** Stop: this repository is the template, not a project to edit directly. Delete it and run the `copier copy` command above instead. If you try to commit into it as-is, a pre-commit guard will refuse and print the same instruction (ADR-0004). A plain, unmodified `git clone` of TheForge itself isn't caught by that guard — its remote still names `forger88/TheForge`, which is also how a maintainer legitimately works on TheForge's own code (see `CLAUDE.md`); cloud sessions here install the guard automatically via `.claude/hooks/session-start.sh`, and everyone else runs `pre-commit install --install-hooks` once per clone.

## Adopting it into an existing repository

TheForge isn't only for a brand-new repository. It can also be adopted into one that already has its own files, history and conventions — run the same command, with the existing checkout as the destination, directly against the live working tree instead of an empty directory:

```bash
cd my-existing-project
copier copy --trust --overwrite gh:forger88/TheForge .
```

`--overwrite` skips the per-file "this already exists, overwrite?" prompt Copier would otherwise ask for every colliding file; it still asks the template's real questions, so answer them for the project actually being adopted rather than taking Copier's defaults.

There's no shortcut around this: Copier has no separate "adopt" mode, and hand-writing the resulting `.copier-answers.yml` instead of letting this run produce it is unsupported by Copier itself and breaks the diff a later `copier update` relies on.

`copier.yml`'s `_skip_if_exists` list protects a project's own project-owned files — `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `docs/principles.md`, `docs/decisions-log.md`, `docs/forge-overrides.md`, `docs/agents/lessons.md`, `docs/agents/operational-constants.md`, `docs/security/threat-model.md`, `docs/requirements/requirements-specification.md`, `docs/adr/README.md`, `docs/tools/document-build.json` and `docs/development/documentation-build.md` — by writing each only if it's missing and never touching it again once it exists.
`CLAUDE.md` and `AGENTS.md` are the one case that still needs hand attention afterwards: since they're already present, Copier leaves their existing content as-is rather than merging anything into it, so rewrite each by hand to end with the forge entry point import and keep only what's genuinely specific to that project — everything the imported forge files already say can come out.

Every other file the template ships (skills, CI workflows, pre-commit hooks, the rest of `docs/`) is overwritten outright: `--overwrite` means a file that already exists and differs from what the template would generate is replaced with no prompt and no conflict markers, the same as a brand-new file. Run this on a fresh branch so the only review is afterwards, with `git diff` against the branch's starting point, deciding file by file whether to keep the forge version `copier copy` just wrote or `git restore` a deliberate local difference it overwrote. For a repository with a lot of existing process, that resulting diff is usually easier to land as several smaller, sequenced pull requests than as one. `--trust` also runs `scripts/bootstrap.py --from-copier` against the existing repository as part of this same command, not only on a brand-new one. The full procedure behind this section — every precondition, reconciling the project's own existing tracker issues so bootstrap reuses them instead of creating duplicates, and the sequenced-landing order — is `template/.agents/skills/retrofit-existing-project/SKILL.md`. Once it's in, keep pulling later improvements the same way a freshly generated project does — see "Where to start in a generated project" below for the skill that does this.

## Where to start in a generated project

`template/instructing-agents.md` ships into every generated project as `instructing-agents.md` at its own root; read it there first once you've generated or adopted a project.
It explains how to drive the agents, how work is requested and parked, and what the agents will ask of you. It points at `scripts/project_init_checklist.md` for the repository settings Copier cannot set for you.
From there, that project's own `CLAUDE.md` is the entry point for its day-to-day rules, and `docs/agents/skills-index.md` is the generated, one-line-per-entry index of every skill and reference doc it ships with — use it to find the skill for a given task rather than browsing `.agents/skills/` by hand.
`forge-sync` is the skill that pulls later TheForge improvements into an already-generated or newly adopted project, wrapping `copier update`.

## Layout of this repository

| Path | What it is |
|---|---|
| `copier.yml` | The Copier questions and settings. Content is rendered from `template/`. |
| `template/` | Everything a generated project receives. |
| `template/instructing-agents.md` | The first-time reader's guide to a generated project; lands at that project's own root, forge-owned (refreshed by `copier update`). |
| `docs/adr/` | TheForge's own architecture decisions (not the generated project's). |
| `docs/release-notes.md` | TheForge's own release notes, one section per release, committed ahead of each tag. |
| `CLAUDE.md`, `AGENTS.md` | Instructions for agents working on TheForge itself. |
| `scripts/` | TheForge's own contribution guards. |

## Credits

Most of the skills that make this semi-automatic agentic process work are adapted from [Matt Pocock's skills](https://github.com/mattpocock/skills) (MIT).
The UI-review skill a generated project installs is [`impeccable`](https://github.com/pbakaus/impeccable) (Apache 2.0).
See [`THIRD_PARTY.md`](THIRD_PARTY.md).

TheForge itself is MIT licensed; see [`LICENSE`](LICENSE).
