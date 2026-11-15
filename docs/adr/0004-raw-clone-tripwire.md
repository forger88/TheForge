# ADR-0004: A pre-commit tripwire catches a raw copy of TheForge used as a project

**Status:** accepted (amended 2026-11-08: the answers-file exemption is removed — see "Amendment" below)

## Context

TheForge only works as intended when a project starts from `copier copy` (ADR-0001): that is what fills in the Jinja placeholders and puts forge-owned material where a generated project expects it (ADR-0002).

GitHub offers two easy ways to end up with TheForge's files without that step: the "Use this template" button that TheForge's own repository setting enables, and a clone whose remote is later repointed at a new, unrelated repository.
Both hand someone a tree that still has `copier.yml`, `template/`, and TheForge's own maintainer-only files (this ADR among them) sitting at the root, as if they were the project's own files.
Nothing in that tree says so out loud: the owner's first commit into it looks like ordinary progress, right up until they notice half their instructions describe a template repository instead of their project.
A plain, unmodified clone of TheForge itself is not one of these misuse cases: its remote still names `forger88/TheForge`, which is also exactly how a maintainer works on TheForge's own code (see the Decision section below), so the hook must not refuse it.

## Decision

A local pre-commit hook, `scripts/check-not-raw-clone.sh`, refuses any commit into a working tree that has `copier.yml` and `template/` at its root — the combination a real Copier render never produces, since `_subdirectory: template` means a render only ever contains what is under `template/` (as amended 2026-11-08, see "Amendment" below: an earlier version of this check also exempted a tree carrying `.copier-answers.yml`).

The one legitimate tree with that combination is TheForge's own working copy, including a contributor's fork.
The hook tells that apart by remote: if any configured remote names `forger88/TheForge`, or the private staging repository `forger88/TheForgeStaging`, the hook passes; a contributor who forked TheForge keeps that working by adding an `upstream` remote pointing at it, which is already how a fork works with its origin project.
Anything else — a clone whose remote was repointed to a new repository, a "Use this template" copy (fresh git history, a different remote), or a zip extracted and re-initialised as its own repository — fails loudly, printing the `copier copy` command to run instead and pointing at the README.

## Alternatives rejected

- **A GitHub Action on push.** Workflows in this repository are manual-dispatch only by convention, and a generated project inherits that same convention; an on-push check here would be the one exception, and would still miss the zip-download case, which never touches GitHub at all.
- **A runtime check inside `template/` itself.** Anything under `template/` ships to every generated project (ADR-0002), so a check placed there would run against real projects too — exactly the thing ADR-0002 exists to prevent leaking.
- **Detecting the raw copy by file content alone (no remote check).** TheForge's own working copy and a raw copy elsewhere are byte-identical right after cloning; content alone cannot tell them apart, only where the clone's remote points can.

## Amendment (2026-11-08)

The original Decision also exempted a tree carrying `.copier-answers.yml`, reasoning that a real render never leaves `copier.yml`/`template/` at the root alongside an answers file, so an answers file on disk meant Copier itself had already run.
ADR-0009 broke that reasoning: TheForgeStaging now commits its own root `.copier-answers.yml` from a genuine self-render, so a raw copy of this repository's root is byte-identical to the real thing, answers file included.
`scripts/publish_snapshot.py` carries that same committed answers file into the public `forger88/TheForge` snapshot, so a "Use this template" copy of the public repository — ADR-0004's main misuse case — passed the exemption too.
The answers-file exemption is removed; the remote check is now the hook's only signal, as the "Alternatives rejected" entry above already argued it has to be.

## Consequences

- The hook only fires once pre-commit is installed and a commit is attempted; a raw copy nobody ever commits into, or that never becomes a git repository at all (a zip extracted and edited in place), passes underneath it. A cloud agent session opened on a clone of TheForge or TheForgeStaging installs pre-commit automatically via this repository's own root `.claude/hooks/session-start.sh` (distinct from `template/.claude/`'s copy, which only ships to a generated project, ADR-0002), and `CLAUDE.md` already forbids bypassing the hook with `--no-verify`, so this is the same residual gap every other pre-commit guard in this repository already accepts.
- A render from `copier copy` is never affected: it never has `copier.yml` or `template/` at its root in the first place, so the hook's first check exits before looking at remotes at all.
- A maintainer who clones TheForge without ever naming `forger88/TheForge` in a remote (for example, a purely local experiment) sees the same loud failure as a misuse case and adds the remote, which is a one-line fix and the correct nudge either way.
