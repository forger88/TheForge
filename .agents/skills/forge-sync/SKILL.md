---
name: forge-sync
description: "Pull the latest TheForge process rules and skills into this project with copier update, resolving conflicts against the local overrides log. Use when the owner asks to sync, update or upgrade the forge, or when a TheForge release note says a change should be pulled."
disable-model-invocation: true
---

# Forge sync

This project was generated from TheForge, and its forge-owned files (`.forge/`, `.agents/skills/`, and the generated reference docs) follow upstream through Copier (`.forge/forge-overrides.md`).
This skill is the one way they are updated.
It is TheForge's own skill, not a third-party one.

## Before you start

1. Run this skill only when the owner has asked for a sync, either by a direct request or by releasing a held sync ticket.
   Record the old `_commit` now.
2. Use the held sync ticket Main Health keeps (`.agents/skills/watch-main-ci/SKILL.md`, "Forge drift check") when one exists; otherwise file one.
   The sync PR closes it.
3. Work in a fresh worktree off `origin/main`, the same as any ticket (`implement-with-merge` step 1), with a clean `git status`.
   Copier refuses to update a dirty tree, and a sync mixed with other edits can't be reviewed.
4. Read `docs/forge-overrides.md` in full.
   Every entry there is a forge-owned file this project changed on purpose; a conflict on one of those files is expected.
   While reading it, list each open upstream candidate: an offered part of an entry whose `Upstream candidate` value begins with "yes" and carries neither a `proposed` nor a `declined` marker.
   An entry whose text already says the change has come back upstream isn't a candidate; list it in the PR body instead, for removal under the entry shape's own removal rule.
   "Surface and record upstream candidates" below asks about each open candidate once the sync PR exists.
5. Read `.copier-answers.yml` and note `_commit` (the TheForge version this project is on) and every standing tracker number (each key ending `_tracker` or `_epic`); the sync must not lose them.
6. Run `python3 scripts/check_forge_drift.py`.
   Its result line goes into the PR body under "Drift before this sync".
7. Copy the project's own current `docs/software-development-lifecycle.md` aside (e.g. to a temp path outside the worktree) before `copier update` touches it.
   This pre-sync copy, not a render of the old upstream template, is what "Hold SDLC wording changes for the owner" below diffs the synced file against: it's the only copy that still carries any wording the owner has locally approved and amended (`docs/forge-overrides.md`), which an old-upstream render never would.

## Check what `--trust` would run, before running it

```
python3 scripts/check_forge_sync_trust_diff.py
```

The `--trust` flag below runs upstream's `copier.yml` tasks and any executable files it ships, and `copier update`'s own conflict resolution treats everything else, including `.claude/` hooks, the pre-commit config and `scripts/`, as plain text to merge, with nothing that singles out a change to code that executes for its own review. This script diffs the project's current `_commit` against the ref the update below would sync to (by default the latest release tag, or upstream's HEAD when it has none, the same ref `copier update` picks; pass `--new <ref>` when the update will use `--vcs-ref <ref>`) and exits non-zero, printing the diff, when `copier.yml` or any of those executable paths changed — naming a new or changed `_migrations`/`_jinja_extensions` key in `copier.yml` by name. It is read-only and never runs Copier or the diff it finds.

Read every line of a non-zero exit before continuing. A real finding here is a stop, not a note for the PR body: don't run the update until you've reviewed what changed and are satisfied it's safe to execute, the same bar "Review and merge" below sets for the sync PR itself.

A mechanical check backs this step up too: paste the script's own last stdout line — `Trust diff: <old>..<new> clean`, or `Trust diff: <old>..<new> changed: <paths>` — into the sync PR body verbatim once it exists. On a non-zero exit, don't paste `changed: ...` as-is: rewrite it to `reviewed: <paths> — <why it is safe to execute>` once you've actually read the diff above and are satisfied. `review-gate-check.yml` runs `scripts/check_forge_sync_trust_record.py` on every PR whose `.copier-answers.yml` changes `_commit`, re-checking that this line's range matches the PR's actual `_commit` change and that its result is `clean` or a non-blank `reviewed: ...`, never a bare `changed: ...` — so skipping this step, or pasting its output without reviewing it, no longer ships silently.

## Run the update

```
pip install "copier==<the version pinned in the project's dev requirements>"
copier update --trust --defaults --skip-tasks --conflict inline
```

`--skip-tasks` stops the bootstrap task from running again; it creates labels and trackers only on the first generation.
`--defaults` is required in a non-interactive session: without it Copier re-asks every question, and with no TTY to answer them it dies with `EOFError` instead of updating anything; with it, every answer keeps its previous value from `.copier-answers.yml` unless this sync's own instructions change one.
`--conflict inline` writes conflict markers into the files rather than separate `.rej` files, so every conflict shows up in the diff.
With no `--vcs-ref`, Copier syncs to the latest release tag, or to upstream's HEAD when no tag exists, and the trust diff above and the drift check target that same ref.
Pass `--vcs-ref <ref>` (a specific release, or `main` to take unreleased commits) to sync somewhere else; pass the same ref to `check_forge_sync_trust_diff.py --new <ref>` above.
After syncing past the latest tag, keep passing `--vcs-ref main` (or a commit) until a newer tag exists, because Copier refuses to step back to an older tag ("Downgrades are not supported"), whether by a default update or by an explicit `--vcs-ref <older tag>`.
Any `--vcs-ref <ref>` must be newer than the project's `_commit`.

Copier never touches the project-owned files it lists under `_skip_if_exists`, so `CLAUDE.md`, `CONTEXT.md`, `docs/principles.md` and the other project-owned files stay exactly as they were.

## Entrypoint migration

Run this section when `CLAUDE.md` has no `@.forge/entrypoint.md` line and still has `@.forge/` import lines: the project predates the single-entrypoint convention, and `copier update` alone can't move a `_skip_if_exists` file to the new shape.

1. Render the template at the **old** `_commit` with the project's answers file:

   ```
   copier copy --trust --defaults --skip-tasks --vcs-ref <old _commit> --data-file .copier-answers.yml <_src_path> <tmp>
   ```

   Take `<tmp>/CLAUDE.md` and `<tmp>/AGENTS.md` as the old render.
2. Find the forge-authored block's **positional span** in the project's `CLAUDE.md`: the contiguous run of lines starting at the preamble's second sentence and ending at the reference-files sentence (covering, in order, the preamble's second and third sentences, the "Rule strengths" section with its heading, the "Forge rules" heading, the `@.forge/` lines, and the reference-files sentence).
   Match this span **positionally**, line by line in sequence against the old render's own block, never by searching the whole file for text that merely equals a line in the block: a blank line, a repeated "Rule strengths" heading, or a rule-strength sentence the project happens to quote elsewhere in the file is outside this span and is never a candidate for deletion, however identical its text.
   Delete only the lines inside that span that are byte-identical, position for position, to the old render's block.
   Blank-line collapsing applies only inside this span, never to a blank line elsewhere in the file.
   Insert the new seed's `instructing-agents.md` pointer sentence and `@.forge/entrypoint.md` in the span's place, where the "Forge rules" heading was.
3. Keep every other line, including any line inside that span that differs from the old render, and every line outside the span regardless of its text.
   List each kept line from inside the span in the PR body under "Migration: kept lines" for the owner to decide.
4. Do the same for `AGENTS.md`: find the positional span covering its step 1 and step 2 lines, delete only what matches the old render position for position inside that span, and insert the new seed's equivalent step 1 and step 2 lines (the `instructing-agents.md` pointer and `@.forge/entrypoint.md` reference, in `AGENTS.md`'s own wording) in the span's place, the same as step 2 does for `CLAUDE.md`.
5. Run `python3 scripts/check_forge_entrypoint.py`; it must pass.

**Worked example of the distinction.** Say the old render's block's last line is the reference-files sentence, and three lines later, outside the span entirely, the project's own "Our conventions" section happens to quote that exact same sentence verbatim.
A set-membership match ("delete every line that appears in the block, wherever it occurs") would delete both occurrences; the positional match above deletes only the one inside the span and leaves the quoted copy in "Our conventions" untouched, because that line's position in the file is outside the span being matched.

## Resolve each conflict

For every file with conflict markers:

- **The file has an entry in `docs/forge-overrides.md`.**
  Keep the project's version of the sentences the entry names, and take upstream's version of every other sentence.
  If upstream now covers the same need the override was written for, take upstream's version, delete the override entry, and say so in the PR.
- **The file is seeded** (listed under "Seeded files" in `.forge/forge-overrides.md`).
  Local edits to it are expected and are never logged.
  Keep the project's entries, and take upstream's version of every structural change (a new key, a renamed field) alongside them.
- **The file has no entry.**
  The local change was never logged, which is itself a finding (`.forge/forge-overrides.md`, "Editing a forge-owned file").
  Take upstream's version unless the owner says otherwise, and file a ticket for the missing override record if the local change was deliberate.

Then check the merged files still pass `scripts/check_one_sentence_per_line.py`, and re-read every hunk near the conflicts: a clean auto-merge can still duplicate a list item or a heading.
Run `pre-commit run --all-files` so every guard sees the synced files.

## Hold SDLC wording changes for the owner

`copier update` may have just changed `docs/software-development-lifecycle.md`'s own statement wording alongside everything else in the file: added, removed or reworded a `- **SDLC-NNN**: ...` line (including adding, removing or moving its `*(desirable)*` marker, which SDLC-002 treats as a meaning change too). Only the owner approves that (`.forge/process-and-evidence.md`, "Process changes follow the lifecycle doc"), so it never rides this sync PR, even on a clean merge with no conflict markers.

This step is no longer only procedural: `review-gate-check.yml` runs `scripts/check_sdlc_wording_hold.py` on every PR whose body carries this skill's "Drift before this sync" marker and that touches `docs/software-development-lifecycle.md`. It re-diffs the file between this PR's base and head and fails the PR if any statement still differs from its pre-sync text, or if the PR body's "SDLC wording held" line (below, under "Review and merge") is missing or blank — so skipping this section, or writing "none" without actually checking, no longer ships silently.

1. Run `python3 scripts/check_sdlc_wording_changes.py <pre-sync copy> docs/software-development-lifecycle.md`, against the project's own pre-sync copy saved under "Before you start" step 7 — **never** a render of the old upstream template. The old upstream render is what the project's file looked like before any of this project's own owner-approved local amendments; comparing against it instead of the project's actual pre-sync file would report every such amendment as "changed" and, at step 3 below, silently revert it to the old upstream wording rather than leaving it alone.
2. Before editing anything, for each statement reported, copy its exact lines as `copier update` just wrote them from the synced file verbatim: the script's own printed text is for comparison only (it joins continuation lines onto one line and normalizes whitespace) and is not a safe source to carry into the second PR below.
   Then find the other synced text that depends on them: run `python3 scripts/check_held_sdlc_prose.py --template <clone> --old <old _commit> --new <new _commit> --base <pre-sync commit> <each reported SDLC-NNN>`, where `<clone>` is a full (not shallow) `git clone` of `.copier-answers.yml`'s `_src_path` into a temporary directory.
   It finds every upstream commit that changed a reported statement and prints each line of that commit's other files that the sync brought in or took out; copy each printed line as the synced file now has it, verbatim, the same way.
   It matches whole lines only, so also read each file it names, and each other file those commits touched, for reworded dependent text.
3. Edit the synced `docs/software-development-lifecycle.md` in this branch back to each reported statement's exact old text (delete the line entirely if the pre-sync copy had none; if the pre-sync copy had a statement the new one lacks, insert it at the position matching the surrounding statements' ascending `SDLC-NNN` order), so this sync PR carries none of it. Everything else upstream changed in that file (new prose, a typo fix, a reordering, a new non-statement section) still flows through this sync PR as normal; re-run the check once after editing to confirm it now reports nothing.
   Revert each dependent line step 2 found back to its pre-sync text the same way, then re-run `check_held_sdlc_prose.py` to confirm it reports nothing, or say in the PR body why each line it still prints doesn't depend on the held wording.
   Log everything this step reverted, statements and dependent lines, as one `docs/forge-overrides.md` entry naming the step 4 ticket, so a later sync's conflict resolution keeps the hold instead of taking upstream's version (`.forge/forge-overrides.md`).
4. If anything was held, open a second branch off the pre-sync commit and apply just the held statements' new lines, verbatim as step 2 captured them, not the script's output.
   File one short ticket for it and open the branch as its own lifecycle-doc PR (`.forge/process-and-evidence.md`, "Process changes follow the lifecycle doc").
   Link the two PRs to each other in both bodies: this sync PR does not merge the statement wording; only the owner's approval on that second PR does.
   The ticket lists the held statement numbers and, one line per file, each dependent line step 3 reverted, verbatim as step 2 captured it, plus any other synced forge-owned text whose meaning depends on held wording; it is a record for that thread, not something the owner is asked to read.
   If this sync PR merges before that second PR, rebase the second PR onto the new `main` once it does, since its base otherwise goes stale.
5. Ask the owner once, in one self-contained request, whether to accept the held statements: a decision card where the harness offers one, otherwise one comment on the lifecycle-doc PR addressed to the owner.
   The request links the lifecycle-doc PR's diff and quotes every held statement's new text in full, verbatim from step 2, beside its old text (or marked new or removed), so the owner can decide from the request alone (`.forge/feature-pipeline.md`, "Every approval request links to the wording it asks about").
   It offers two answers, "Accept all" and "Hold", and leaves the ticket's dependent-file list out.
6. On "Accept all", record the owner's answer in the lifecycle-doc PR body in the form `.forge/process-and-evidence.md`, "Evidence: where each record lives", gives, then merge that PR as "Process changes follow the lifecycle doc" says.
   Merge it carrying exactly the text step 2 captured, which is what the owner approved: do not re-fetch upstream, re-render the template, or diff against upstream's current state first, even if upstream has moved since; a later upstream change is the next sync's to hold.
   Once both it and this sync PR have merged, open one more PR off the new `main` that applies the dependent lines the ticket lists, verbatim, and removes the step 3 override entry, citing the merged lifecycle-doc PR; it is ordinary forge-owned text, so it merges once its review gate is clear.
   On "Hold", record the owner's answer on the ticket and leave the ticket and the PR open and unmerged until the owner says otherwise.

## Check the result

1. Render the template at the **new** `_commit` with the project's answers file, the same `copier copy … --data-file` command as the migration above but with the new ref, into a temporary directory.
   Run `diff -rq <render> . --exclude=.git`.
   Every "differ" or "Only in" line must trace to a `docs/forge-overrides.md` entry, a seeded file, a `_skip_if_exists` file, a project-owned file the template never ships, or a statement or dependent line held out above (confirm each such line is in fact one of the held statements or dependent lines from "Hold SDLC wording changes for the owner", not a silent reversion of the hold).
   List any that do not, and resolve them before the PR opens.
2. Run `python3 scripts/check_sync_duplicates.py --base <pre-sync commit> --render <render dir>`.
   Fix every reported line, or explain it in the PR body if it is a deliberate duplicate.
3. Run `pre-commit run --all-files`, which includes `forge-entrypoint`.

## Review and merge

A forge sync changes process text, so it gets the full review gate (`.forge/review-gate.md`), and its `Process:` line names the `SDLC-` statements the upstream change touches.
If the upstream change introduces a policy that this project's `docs/software-development-lifecycle.md` does not justify, don't merge that part: flag it to the owner as a `needs-decision` ticket (`.forge/process-and-evidence.md`, "Process changes follow the lifecycle doc").

The PR body lists:

- `_commit` before and after;
- "Synced ref": `Synced ref: latest tag <tag>`, or `Synced ref: <ref> (not the latest tag): <why>`;
- the drift check's result line from step 6 of "Before you start", under "Drift before this sync";
- the trust diff's record line from "Check what `--trust` would run, before running it", under "Trust diff";
- every line added to or removed from `.forge/entrypoint.md`'s imports, under "Entrypoint import changes", or "none";
- "Migration: kept lines", or "not needed";
- every conflict and how it was resolved, and every override entry it removed;
- every SDLC statement held out, under "SDLC wording held", linking the separate lifecycle-doc PR it was moved to and the owner's accept/hold request (step 5 of that section), or "none";
- every dependent line reverted with them, by file, under "Dependent lines held", and why each line `check_held_sdlc_prose.py` still prints doesn't depend on the held wording, or "none";
- "Upstream candidates" (see "Surface and record upstream candidates" below), or "none".

If the coordinator or build-thread brief changed upstream, the harness's project-level copies of those texts change in the same session (`.forge/orchestration.md`, "The coordinator-core snippet is not a source of rules").

## Surface and record upstream candidates

Right after the sync PR opens, ask the owner once per open candidate from "Before you start" step 4.
Use a decision card where the harness offers one, otherwise one comment on the sync PR addressed to the owner, the same fallback "Hold SDLC wording changes for the owner" above uses.
The question is "Offer `<file>`'s `<part>` upstream to TheForge?", linking the entry at the sync branch.
A project with many open candidates gets that many questions at once.
Options:

- **Propose this as a back-port patch.** Post a ticket on `.copier-answers.yml`'s `_src_path` only when it is a hosted repository whose visibility is private and on which this session can create issues (check, for GitHub, with `gh repo view <owner/repo> --json visibility,viewerPermission` or the harness's equivalent).
  In every other case, including when the check can't answer, or filing fails (auth, network, rate limit), draft the ticket in the sync PR body instead and never post it.
  Either way the ticket (or draft) holds the entry, the project's diff of that file against the upstream render, the project's `_commit`, and a link to the sync PR.
  Then write a `proposed` marker on the entry: `yes — proposed as <ticket link or "drafted in <sync PR link>">, <date>`.
- **Decline.** Write a `declined` marker: `no — declined by owner, <date>`.
- **Not yet.** Change nothing; the candidate stays open and is asked again at the next sync.

An entry's `Upstream candidate` value is always one of four: `yes, rewritten generically` (open, unanswered), `yes — proposed as ..., <date>` (written here, on "Propose"), `no, project-specific` (never a candidate), or `no — declined by owner, <date>` (written here, on "Decline").
Marker edits are commits on this sync PR.
The PR body's "Upstream candidates" line lists each question and the owner's answer in the approval-record form (`.forge/process-and-evidence.md`), or "none" when "Before you start" step 4 found no open candidates.
This sync PR does not wait on the questions: one still unanswered at merge is recorded as "Not yet", asked again next time.
`docs/forge-overrides.md` is missing, or has no `Upstream candidate` lines: no questions, "Upstream candidates: none".
