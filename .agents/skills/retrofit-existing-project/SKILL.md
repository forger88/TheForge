---
name: retrofit-existing-project
description: "Bring an existing, independently-evolved repository onto TheForge as a full, ongoing copier-update-tracked consumer: a real copier copy run against the live checkout, a hand-rewritten CLAUDE.md/AGENTS.md, collision triage for everything else, and standing-tracker reconciliation. Use once, when a repository that already has its own files, history and conventions is adopting TheForge for the first time — never for a repository that is already a forge consumer, which uses forge-sync instead."
disable-model-invocation: true
---

# Retrofitting an existing project

This is the full procedure behind the root README's "Adopting it into an existing repository" section: that section gives a human reader the one-paragraph version, this skill is what an agent actually runs. It covers a repository that has its own, independently-converged process already (its own skills, CI, labels, docs layout) and, equally, one with no prior forge-equivalent process at all — both are legitimate targets, and this procedure doesn't assume either shape going in.

It is read directly out of a TheForge checkout by whoever is doing the retrofit. The target repository does not need to already have this skill, or any part of TheForge, before the retrofit starts.

**Full retrofit only.** This skill always ends with the target as an ongoing `copier update`-tracked consumer, the same relationship any freshly generated project has. There is no "pick individual pieces" mode: adopting only part of TheForge by hand is the target project's own business, not something this skill does or documents (ADR-0008).

**If the target is already a forge consumer** (it has a `.copier-answers.yml`, or `CLAUDE.md` already has `@.forge/` import lines), stop — this is `forge-sync`'s job, not this skill's. Phase 0's guard script refuses to proceed in that case.

## Phase 0: preconditions

1. Run `python3 scripts/check_retrofit_preconditions.py --root <target-repo-root>` (the script ships at `template/scripts/check_retrofit_preconditions.py`; copy or reference it directly from a TheForge checkout, since the target doesn't have it yet). It must exit 0 before continuing. It checks, offline:
   - the target has no `.copier-answers.yml`;
   - `CLAUDE.md` has no line matching `^@\.forge/`;
   - `git status --porcelain` in the target is empty.
2. Confirm, by hand, that no open pull request on the target touches a path this template ships (`.forge/`, `.agents/skills/`, any CI workflow file, `.pre-commit-config.yaml`, any `docs/` path the template seeds). The one-shot diff in Phase 2 has no way to detect a collision with in-flight work; this check is what stands in for it.
3. Work on a fresh branch cut from the target's own `main`, per that project's own branching conventions (most repos built on this process require a descriptively-named branch taken fresh off `main`, never a session-title-shaped one).

## Phase 1: reconcile trackers and labels before copying

`template/scripts/bootstrap.py`'s `ensure_trackers` reuses a tracker issue it finds by **exact title match** and never edits one it finds; `ensure_labels` only ever creates a label named in its own `LABELS` table and never touches an existing label under a different name. Both already have this behaviour — nothing below changes `bootstrap.py` itself.

1. Look up `bootstrap.py`'s `TRACKERS` table (`template/scripts/bootstrap.py`) for the five answer keys and the exact title each one searches for.
2. For each key, check whether the target already has an issue serving that same role, under whatever title its own history gave it (a project with its own prior process typically already has something playing each of these roles, even if none of them share TheForge's exact wording).
3. Where one exists, rename it (via the hosting platform's own issue-edit, not a file change) to the exact title from step 1, so title-match reuse engages when Phase 2 runs.
4. Where none exists, do nothing for that key; `ensure_trackers` creates it fresh, the same as for a brand-new project.
5. `ensure_labels` needs no equivalent step: the target's own existing labels, under their own names, are never touched.

## Phase 2: the real `copier copy`

Run, directly against the target's live, populated checkout — never a scratch directory, and never by hand-writing `.copier-answers.yml` afterward (ADR-0008; Copier's own documentation calls that unsupported and it desyncs every later `copier update`):

```bash
cd <target-repo-root>
copier copy --trust --overwrite <ref> .
```

`--overwrite` skips the per-file "this already exists, overwrite?" prompt; Copier still asks its real questions, which get answered from what is already true of the target project, never from Copier's own defaults:

| Question | Answer from |
|---|---|
| `project_name`, `repo_owner`, `repo_name` | the target's existing remote and its own name |
| `owner_timezone` | the project owner's own timezone |
| `setup_command`, `test_command`, `lint_command` | the target's existing scripts and documented commands |
| `coverage_floor`, `max_module_lines`, `max_function_code_lines` | the target's existing coverage and size-cap rules, as they stand today |
| `working_folder` | wherever the target's agents already keep mutable working state |

`<ref>` is a commit SHA on this repository's `main` until TheForge starts tagging releases; re-pin to a tag later with an ordinary `forge-sync` once one exists.

This one command also fires `copier.yml`'s `_tasks`: `bootstrap.py --from-copier` (creates or reuses labels and trackers, per Phase 1's reconciliation). Nothing further needs to be run by hand to get that.

The harness's project-level instructions live outside the repository, so Copier does not touch them: paste the text between the markers in `docs/agents/coordinator-core-snippet.md` into them, after the owner's scope section and an empty `## Coordinator notes` zone, then start the coordinator session.

## Phase 3: hand-rewrite CLAUDE.md and AGENTS.md

Both files are listed under `copier.yml`'s `_skip_if_exists`, and both already exist on the target, so Phase 2 leaves their content completely untouched — this is the one step Copier cannot do for a retrofit.

Read the target's existing `CLAUDE.md` in full. For every rule in it, decide exactly one of:

- **Already covered by an imported `.forge/` file.** Drop it from `CLAUDE.md`; the `@.forge/entrypoint.md` import now carries it.
- **Covered by a `.forge/` file, but with a substantive difference** (not just different wording — a different actual rule). This is a justified-departure call: either upstream the difference to TheForge first, or keep it as a logged refinement in `docs/forge-overrides.md` (`.forge/forge-overrides.md`'s own "Editing a forge-owned file" convention), restoring the local wording on top of the forge version. Never drop it silently.
- **Genuinely project-specific** (domain vocabulary, integration details, operational constants, project lessons). Keep it, in the file's own project-owned section, after `@.forge/entrypoint.md`.

The result ends with the `@.forge/entrypoint.md` import, followed only by the project-owned section. Do the same read-and-map for `AGENTS.md`, which is far shorter.

This is **never** `forge-sync`'s "Entrypoint migration" positional-span procedure (ADR-0006): that procedure diffs against a prior forge-rendered `CLAUDE.md` that a retrofit target, having never been a forge consumer, does not have. This is a full hand audit, one rule at a time, not a mechanical diff.

Record the full rule-by-rule mapping in the landing PR's body (Phase 5).

## Phase 4: collision triage for everything else

Every other file the template collides with (skills, CI workflows, pre-commit hooks, the rest of `docs/`) is bounded to files the template actually contains — never the whole project. For each:

- **Default: take the forge version.** This is the expected outcome for most collisions.
- **A diff that is a substantive departure, not just wording.** Upstream it to TheForge, or log it in `docs/forge-overrides.md` and keep the local version on top of the forge one. Never drop it silently.
- **A project-owned skill or doc with no forge analog at all.** Leave it exactly as it is, permanently. TheForge never claims ownership of something it doesn't ship.

Record the departure audit in the landing PR body (Phase 5).

## Phase 5: verify the reconciliation, then land as sequenced PRs

1. Read the target's `.copier-answers.yml` tracker fields and confirm each resolved to the issue renamed in Phase 1, not a freshly created duplicate. A tracker Phase 1 missed shows up here as a visible duplicate — fix it (retitle the real one, close the accidental duplicate) before any PR opens, never after.
2. Split the one-shot diff into several sequenced pull requests rather than landing it as one, in this order: the `.forge/` tree and the `CLAUDE.md`/`AGENTS.md` entrypoint import first; skills second; CI workflows, labels and the rest of `docs/` third. Each PR carries, in its body:
   - for the first PR, Phase 3's full rule-by-rule mapping;
   - for the others, Phase 4's departure audit for the files it covers.
3. Each PR clears the target's own full review gate before merging.

As explicit follow-on work this skill does **not** itself do: the target's fresh `docs/security/threat-model.md` skeleton (written by Phase 2, same as any newly generated project's) becomes a real document through that project's own stage-0 `security-docs` bootstrap mode. Name this as a separate, explicit follow-up when handing the retrofit off — don't let it be silently absorbed into a build ticket or silently dropped.

## Phase 6: verify with a real sync

Once the last landing PR has merged, run `forge-sync`'s own procedure as a dry run against the pinned ref: `copier update --trust --skip-tasks --conflict inline`. No unexpected diff should appear — every "differ" or "Only in" line should trace to a `docs/forge-overrides.md` entry, a `_skip_if_exists` file, or a project-owned file the template never ships. This is the concrete proof that the retrofit actually produced an ordinary, syncable consumer.
