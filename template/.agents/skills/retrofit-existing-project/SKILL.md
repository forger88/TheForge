---
name: retrofit-existing-project
description: "Bring an existing, independently-evolved repository onto TheForge as a full, ongoing copier-update-tracked consumer: a real copier copy run against the live checkout, a hand-rewritten CLAUDE.md/AGENTS.md, collision triage for everything else, and standing-tracker reconciliation. Use once, when a repository that already has its own files, history and conventions is adopting TheForge for the first time — never for a repository that is already a forge consumer, which uses forge-sync instead."
disable-model-invocation: true
---

# Retrofitting an existing project

This is the full procedure behind the root README's "Adopting it into an existing repository" section, which gives a human the one-paragraph version.
It suits a repository with its own independently-converged process (its own skills, CI, labels, docs layout) and one with none; it assumes neither.
Whoever does the retrofit reads it directly out of a TheForge checkout; the target needs no part of TheForge beforehand.

**Full retrofit only.** The target always ends as an ongoing `copier update`-tracked consumer, like any freshly generated project; there is no "pick individual pieces" mode, and adopting part of TheForge by hand is the target's own business (ADR-0008).

**If the target is already a forge consumer** (it has a `.copier-answers.yml`, or `CLAUDE.md` already has `@.forge/` import lines), stop: that is `forge-sync`'s job, and Phase 0's guard script refuses to proceed.

## Phase 0: preconditions

1. Run `python3 scripts/check_retrofit_preconditions.py --root <target-repo-root>` from a TheForge checkout (it ships at `template/scripts/check_retrofit_preconditions.py`; the target doesn't have it yet), and continue only on exit 0.
   It checks, offline, that the target has no `.copier-answers.yml`, that `CLAUDE.md` has no line matching `^@\.forge/`, and that `git status --porcelain` is empty.
2. Confirm by hand that no open pull request on the target touches a path this template ships (`.forge/`, `.agents/skills/`, any CI workflow file, `.pre-commit-config.yaml`, any `docs/` path the template seeds): Phase 2's one-shot diff cannot detect a collision with in-flight work.
3. Work on a fresh branch cut from the target's `main`, per its own branching conventions (usually a descriptively-named branch, never a session-title-shaped one).

## Phase 1: reconcile trackers and labels before copying

`template/scripts/bootstrap.py`'s `ensure_trackers` reuses a tracker issue it finds by **exact title match** and never edits one; `ensure_labels` only creates labels named in its `LABELS` table and never touches an existing label under another name.
Nothing below changes `bootstrap.py`.

1. Read `bootstrap.py`'s `TRACKERS` table for the five answer keys and the exact title each searches for.
2. For each key, check whether the target already has an issue in that role under its own title (a project with its own process usually has something playing each role).
3. Where one exists, rename it through the hosting platform's issue edit to the exact title from step 1, so Phase 2 reuses it.
4. Where none exists, do nothing; `ensure_trackers` creates it fresh.
5. Labels need no step: the target's own labels are never touched.

## Phase 2: the real `copier copy`

Run it against the target's live, populated checkout: never a scratch directory, and never by hand-writing `.copier-answers.yml` afterward (ADR-0008; Copier's documentation calls that unsupported, and it desyncs every later `copier update`):

```bash
cd <target-repo-root>
copier copy --trust --overwrite <ref> .
```

`--overwrite` skips the per-file overwrite prompt; answer Copier's real questions from what is already true of the target, never from Copier's defaults:

| Question | Answer from |
|---|---|
| `project_name`, `repo_owner`, `repo_name` | the target's existing remote and its own name |
| `owner_timezone` | the project owner's own timezone |
| `setup_command`, `test_command`, `lint_command` | the target's existing scripts and documented commands |
| `coverage_floor`, `max_module_lines`, `max_function_code_lines` | the target's existing coverage and size-cap rules, as they stand today |
| `working_folder` | wherever the target's agents already keep mutable working state |

`<ref>` is a commit SHA on this repository's `main` until TheForge tags releases; re-pin to a tag later with an ordinary `forge-sync`.

The same command fires `copier.yml`'s `_tasks`, `bootstrap.py --from-copier`, which creates or reuses labels and trackers per Phase 1; nothing else needs running by hand.

Copier does not touch the harness's project-level instructions, which live outside the repository: paste the text between the markers in `docs/agents/coordinator-core-snippet.md` into them, after the owner's scope section and an empty `## Coordinator notes` zone, then start the coordinator session.

## Phase 3: hand-rewrite CLAUDE.md and AGENTS.md

Both files are under `copier.yml`'s `_skip_if_exists` and already exist on the target, so Phase 2 leaves them untouched: this is the one step Copier cannot do for a retrofit.

Read the target's `CLAUDE.md` in full, and decide exactly one of these for each rule:

- **Already covered by an imported `.forge/` file**: drop it; the `@.forge/entrypoint.md` import now carries it.
- **Covered by a `.forge/` file with a substantive difference** (a different rule, not different wording): a justified-departure call; either upstream the difference to TheForge first, or log it in `docs/forge-overrides.md` (`.forge/forge-overrides.md`, "Editing a forge-owned file") and restore the local wording on top of the forge version; never drop it silently.
- **Genuinely project-specific** (domain vocabulary, integration details, operational constants, project lessons): keep it in the project-owned section after `@.forge/entrypoint.md`.

The result is the `@.forge/entrypoint.md` import followed only by the project-owned section.
Do the same for the much shorter `AGENTS.md`.

This is **never** `forge-sync`'s "Entrypoint migration" positional-span procedure (ADR-0006), which diffs against a prior forge-rendered `CLAUDE.md` a retrofit target never had: it is a full hand audit, one rule at a time.

Record the rule-by-rule mapping in the landing PR's body (Phase 5).

## Phase 4: collision triage for everything else

Triage every other file the template collides with (skills, CI workflows, pre-commit hooks, the rest of `docs/`), and only those, never the whole project:

- **Default: take the forge version**, the expected outcome for most collisions.
- **A substantive departure, not just wording**: upstream it to TheForge, or log it in `docs/forge-overrides.md` and keep the local version on top; never drop it silently.
- **A project-owned skill or doc with no forge analog**: leave it exactly as it is, permanently; TheForge never claims what it doesn't ship.

Record the departure audit in the landing PR body (Phase 5).

## Phase 5: verify the reconciliation, then land as sequenced PRs

1. Confirm each tracker field in the target's `.copier-answers.yml` resolved to the issue renamed in Phase 1, not a fresh duplicate.
   A tracker Phase 1 missed shows up as a visible duplicate: fix it (retitle the real one, close the duplicate) before any PR opens.
2. Land the one-shot diff as sequenced pull requests, not one, in this order: the `.forge/` tree with the `CLAUDE.md`/`AGENTS.md` entrypoint import; then skills; then CI workflows, labels and the rest of `docs/`.
   The first PR's body carries Phase 3's full rule-by-rule mapping; each later one carries Phase 4's departure audit for the files it covers.
3. Each PR clears the target's own full review gate before merging.

Explicit follow-on work this skill does **not** do: turning the target's fresh `docs/security/threat-model.md` skeleton into a real document through its own stage-0 `security-docs` bootstrap mode.
Name it as a separate follow-up at handoff, so it is neither absorbed into a build ticket nor dropped.

## Phase 6: verify with a real sync

Once the last landing PR merges, run `forge-sync`'s procedure as a dry run against the pinned ref: `copier update --trust --skip-tasks --conflict inline`.
No unexpected diff should appear: every "differ" or "Only in" line traces to a `docs/forge-overrides.md` entry, a `_skip_if_exists` file, or a project-owned file the template never ships, which proves the retrofit produced an ordinary, syncable consumer.
