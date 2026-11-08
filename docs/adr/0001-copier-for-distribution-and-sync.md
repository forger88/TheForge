# ADR-0001: Copier for distribution and sync

**Status:** accepted

## Context

TheForge exists to hand a battle-tested agent engineering process to brand-new repositories.
Handing it over once is the easy half.
The process keeps improving: a rule gets sharper, a skill gains a checklist item, a guard catches a new leak shape.
A forge-derived project has to absorb those upstream changes without its owner re-diffing every file by hand, while keeping the local refinements it has made on purpose.

So the distribution mechanism needs four things: templating (project name, repository, commands and tracker numbers differ per project), a creation command, an update command that performs a real three-way merge between the version a project was generated from, the new upstream version and the project's local edits, and a recorded base for that merge.

## Decision

TheForge is a [Copier](https://copier.readthedocs.io/) template.

- `copier copy` creates a project from `template/`, asking the questions in `copier.yml`.
- Copier records the template release and the answers in the generated project's `.copier-answers.yml`; that recorded release is the base of every later three-way merge.
- `copier update`, wrapped by the generated project's `forge-sync` skill, brings a project up to a newer TheForge release, leaving conflict markers only where upstream and the project changed the same lines.
- A single post-creation task (`scripts/bootstrap.py`) does the GitHub-side setup Copier cannot express as files: labels and the standing tracker issues.

## Alternatives rejected

- **Cookiecutter.** Templating only.
  It has no update or sync story, so every upstream improvement would be a manual re-diff in every project, which is exactly the problem.
- **cruft.** Adds updates on top of Cookiecutter, but applies a straight diff/patch against the project rather than a three-way merge, so its conflict handling is weaker, and it has a smaller community than Copier.
- **git subtree or submodule.** Entangles the forge's git history with each project's, gives no templating or variable substitution (every project would carry the same literal text), and a submodule cannot be edited locally without forking it.

## Consequences

- Generating a project needs `--trust`, because the template runs a post-creation task.
  The task is one short, readable script, and it skips its GitHub steps when no token is set.
- Merge quality depends on how upstream files are written.
  ADR-0002 (forge-owned versus project-owned separation) and the one-sentence-per-line rule for forge-owned rule files exist to keep `copier update` conflicts small and local.
- Standing tracker numbers are only known after the bootstrap task runs, so templated text refers to them through computed variables that fall back to "see `.copier-answers.yml`" until the numbers are recorded.
- TheForge's releases are git tags; a project pins to a release, not to `main`.
