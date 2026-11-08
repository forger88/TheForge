# ADR-0006: A generated project's CLAUDE.md imports one forge-owned entrypoint, and existing projects migrate in a reviewed sync

**Status:** accepted

## Context

`copier.yml` lists `CLAUDE.md` and `AGENTS.md` under `_skip_if_exists`, so Copier writes them once at generation and never touches them again (ADR-0002 keeps project-owned files out of every sync).
The generated `CLAUDE.md` used to carry forge-authored content directly: a hardcoded list of `@.forge/*.md` imports, a reference-files sentence, a framing preamble, and an inlined copy of the rule-strength framework that `.forge/never-default.md` already states.
Because the file is frozen, none of that forge-authored content follows TheForge after generation.
A new `.forge/` rule file never loads in an existing project, and a change to the inlined prose never arrives.
The design on the issue "How do repos started from TheForge receive later TheForge changes?" settles how later TheForge changes reach an existing project by hardening `copier update` through `forge-sync`, and needs `CLAUDE.md` out of the way of that.

## Decision

A generated `CLAUDE.md` holds no forge-authored rule text beyond one line, `@.forge/entrypoint.md`.
`.forge/entrypoint.md` is forge-owned and synced like every other `.forge/` file.
It carries the framing sentences, every always-loaded `@.forge/` import, and the reference-files sentence.
The rule-strength framework is delivered by `.forge/never-default.md`, which the entrypoint imports first, and is not copied into the entrypoint.
`AGENTS.md` points at the entrypoint rather than repeating its import list.

A project generated before this change is migrated once, by hand, inside the owner-requested `forge-sync` PR.
The migration deletes only lines that are byte-identical to the old template's render, and it keeps and lists every other line for the owner.
It is never a Copier `_migrations` entry.

A pre-commit guard refuses a `CLAUDE.md` that has lost its entrypoint line, because losing it silently disables every forge rule.

## Alternatives rejected

- **Remove `CLAUDE.md` from `_skip_if_exists` and let Copier merge it.** The file is mostly the project's own rules, so every sync would raise three-way conflicts on content TheForge does not own, and that is exactly the leak and overwrite risk ADR-0002 exists to prevent.
- **Fold the import list into `.forge/never-default.md`.** That would overload one rule file with a second job, and a later edit to the rule-strength framework would then also move which files load.
- **Migrate existing projects with a Copier `_migrations` entry.** Copier runs migrations during `copier update --trust` even under `--skip-tasks`, with no review before they execute. That adds the unsafe-feature exposure the threat model already lists as a gap for `forge-sync`, and does it on a file the project owns.
- **Leave `CLAUDE.md` as it is and document the manual edit.** Every new forge rule file would then depend on each owner noticing a release note, which is the silent staleness this decision exists to end.

## Consequences

- A sync can now change which forge rule files an existing project loads, not just what they say. That raises the stakes of the review a consumer gives a sync PR, and the `forge-sync` PR body lists every import-line change to the entrypoint so the reviewer sees it.
- Rule files load two levels deep (`CLAUDE.md`, then the entrypoint, then each rule file). Claude Code resolves that, but a harness that does not resolve `@` imports must open the entrypoint and then each file it lists, which `AGENTS.md` says in so many words. The residual risk is recorded in the issue "Harnesses without recursive @-imports may load only .forge/entrypoint.md, not the rule files it imports".
- The migration is the first step in TheForge's process that edits a `_skip_if_exists` file. Its byte-identical deletion rule and the full review gate on the sync PR are what keep project-owned content safe.
