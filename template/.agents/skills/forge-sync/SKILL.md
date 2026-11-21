---
name: forge-sync
description: "Pull the latest TheForge process rules and skills into this project with copier update, resolving conflicts against the local overrides log. Use when the owner asks to sync, update or upgrade the forge, or when a TheForge release note says a change should be pulled."
disable-model-invocation: true
---

# Forge sync

This project was generated from TheForge, and its forge-owned files (`.forge/`, `.agents/skills/`, and the generated reference docs) follow upstream through Copier (`.forge/forge-overrides.md`).
This skill, TheForge's own, is the one way they are updated.

## Before you start

1. Run this skill only when the owner has asked for a sync, either by a direct request or by releasing a held sync ticket.
   Record the old `_commit` now.
2. Use the held sync ticket Main Health keeps (`.agents/skills/watch-main-ci/SKILL.md`, "Forge drift check") when one exists; otherwise file one.
   The sync PR closes it.
3. Work in a fresh worktree off `origin/main`, the same as any ticket (`implement-with-merge` step 1), with a clean `git status`.
   Copier refuses to update a dirty tree, and a sync mixed with other edits can't be reviewed.
4. Read `docs/forge-overrides.md` in full.
   Each entry is a forge-owned file this project changed on purpose, so a conflict on it is expected.
   List each open upstream candidate (an entry's offered part whose `Upstream candidate` value begins with "yes" with neither a `proposed` nor a `declined` marker) for "Surface and record upstream candidates" below.
   An entry already saying its change came back upstream isn't a candidate: list it in the PR body for removal under the entry shape's removal rule.
5. Read `.copier-answers.yml` and note `_commit` (the TheForge version this project is on) and every standing tracker number (each key ending `_tracker` or `_epic`); the sync must not lose them.
6. Run `python3 scripts/check_forge_drift.py`.
   Its result line goes into the PR body under "Drift before this sync".
7. Copy the project's current `docs/software-development-lifecycle.md` (e.g. to a temp path outside the worktree) before `copier update` touches it.
   "Hold SDLC wording changes for the owner" below diffs against this pre-sync copy, not a render of the old upstream template, because only it carries wording the owner approved and amended locally (`docs/forge-overrides.md`).

## Check what `--trust` would run, before running it

```
python3 scripts/check_forge_sync_trust_diff.py
```

`--trust` runs upstream's `copier.yml` tasks and any executable files it ships, while Copier's conflict resolution merges everything else (`.claude/` hooks, the pre-commit config, `scripts/`) as plain text, with nothing singling out executable code for review.
This read-only script diffs the current `_commit` against the ref the update will sync to (by default the latest release tag, or upstream's HEAD when there is none, as `copier update` picks; pass `--new <ref>` when the update uses `--vcs-ref <ref>`), and exits non-zero, printing the diff, when `copier.yml` or any of those executable paths changed, naming a new or changed `_migrations`/`_jinja_extensions` key.

Read every line of a non-zero exit: a real finding is a stop, not a PR-body note, and the update waits until you are satisfied the change is safe to execute, the bar "Review and merge" sets for the sync PR.

Paste the script's last stdout line (`Trust diff: <old>..<new> clean`, or `Trust diff: <old>..<new> changed: <paths>`) into the sync PR body verbatim, except that after a non-zero exit you rewrite `changed: ...` to `reviewed: <paths> — <why it is safe to execute>` once you have actually read the diff and are satisfied it is safe.
`review-gate-check.yml` runs `scripts/check_forge_sync_trust_record.py` on every PR that changes `.copier-answers.yml`'s `_commit`, checking the line's range matches that change and its result is `clean` or a non-blank `reviewed: ...`, never a bare `changed: ...`.

## Run the update

```
pip install "copier==<the version pinned in the project's dev requirements>"
copier update --trust --defaults --skip-tasks --conflict inline
```

`--skip-tasks` stops the bootstrap task from running again; it creates labels and trackers only on the first generation.
`--defaults` is required in a non-interactive session, where Copier would otherwise re-ask every question and die with `EOFError`; with it, every answer keeps its `.copier-answers.yml` value unless this sync's instructions change one.
`--conflict inline` writes conflict markers into the files rather than separate `.rej` files, so every conflict shows up in the diff.
With no `--vcs-ref`, Copier syncs to the latest release tag, or upstream's HEAD when no tag exists, the same ref the trust diff and drift check target.
To sync elsewhere, pass `--vcs-ref <ref>` (a release, or `main` for unreleased commits), and the same ref to `check_forge_sync_trust_diff.py --new <ref>`; it must be newer than the project's `_commit`.
After syncing past the latest tag, keep passing `--vcs-ref main` (or a commit) until a newer tag exists, because Copier refuses to step back to an older tag ("Downgrades are not supported").

Copier never touches the project-owned files under `_skip_if_exists` (`CLAUDE.md`, `CONTEXT.md`, `docs/principles.md` and the rest).

## Entrypoint migration

Run this section when `CLAUDE.md` has no `@.forge/entrypoint.md` line and still has `@.forge/` import lines: the project predates the single-entrypoint convention, and `copier update` alone can't move a `_skip_if_exists` file to the new shape.

1. Render the template at the **old** `_commit` with the project's answers file:

   ```
   copier copy --trust --defaults --skip-tasks --vcs-ref <old _commit> --data-file .copier-answers.yml <_src_path> <tmp>
   ```

   Take `<tmp>/CLAUDE.md` and `<tmp>/AGENTS.md` as the old render.
2. Find the forge-authored block's **positional span** in the project's `CLAUDE.md`: the contiguous run of lines starting at the preamble's second sentence and ending at the reference-files sentence (covering, in order, the preamble's second and third sentences, the "Rule strengths" section with its heading, the "Forge rules" heading, the `@.forge/` lines, and the reference-files sentence).
   Match this span **positionally**, line by line against the old render's block, never by searching the file for text equal to a block line: a blank line, a repeated "Rule strengths" heading or a quoted rule-strength sentence elsewhere in the file is outside the span and never deleted, however identical.
   Delete only lines inside the span that are byte-identical, position for position, to the old render's block, and collapse blank lines only inside the span.
   Insert the new seed's `instructing-agents.md` pointer sentence and `@.forge/entrypoint.md` in the span's place, where the "Forge rules" heading was.
3. Keep every other line, including any line inside that span that differs from the old render, and every line outside the span regardless of its text.
   List each kept line from inside the span in the PR body under "Migration: kept lines" for the owner to decide.
4. Do the same for `AGENTS.md`: find the positional span covering its step 1 and step 2 lines, delete only what matches the old render position for position inside that span, and insert the new seed's equivalent step 1 and step 2 lines (the `instructing-agents.md` pointer and `@.forge/entrypoint.md` reference, in `AGENTS.md`'s own wording) in the span's place, the same as step 2 does for `CLAUDE.md`.
5. Run `python3 scripts/check_forge_entrypoint.py`; it must pass.

**Worked example.** The block's last line is the reference-files sentence, and three lines later, outside the span, the project's "Our conventions" section quotes the same sentence.
A set-membership match would delete both; the positional match deletes only the one inside the span.

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

`copier update` may have added, removed or reworded a `- **SDLC-NNN**: ...` statement in `docs/software-development-lifecycle.md` (including adding, removing or moving its `*(desirable)*` marker, which SDLC-002 treats as a meaning change).
Only the owner approves that (`.forge/process-and-evidence.md`, "Process changes follow the lifecycle doc"), so it never rides this sync PR, even on a clean merge.

`review-gate-check.yml` runs `scripts/check_sdlc_wording_hold.py` on every PR whose `.copier-answers.yml` `_commit` changes, whatever its body or changed-file list says, because a conflict resolved to the project's side can leave the file unchanged although upstream changed statements.
It recomputes what upstream changed (`check_sdlc_wording_changes.py`'s `account()`) and fails the PR when a statement upstream changed between the two `_commit`s still differs from its pre-sync text, when the body's "SDLC upstream changes" line (step 1) is missing or doesn't match, or when the "SDLC wording held" line ("Review and merge") is missing or blank.

1. Run `python3 scripts/check_sdlc_wording_changes.py --template <clone> --old <old _commit> --new <new _commit> <pre-sync copy> docs/software-development-lifecycle.md`, where `<clone>` is the full `git clone` of `.copier-answers.yml`'s `_src_path` step 2 also uses, and `<pre-sync copy>` is the copy from "Before you start" step 7, **never** a render of the old upstream template, which would report every owner-approved local amendment as "changed" and have step 3 silently revert it.
   Its first line, `SDLC upstream changes: <old>..<new> held: <ids or "none">; current: <ids or "none">`, is the account to hold: `held` statements carry into steps 2–4, and `current` ones already match upstream's new wording, so need no revert.
   Paste that line into the sync PR body verbatim (see "Review and merge").
2. Before editing anything, copy each reported statement's exact lines verbatim from the synced file as `copier update` wrote them; the script's printed text joins continuation lines and normalizes whitespace, so it is for comparison only, not a safe source for the second PR below.
   Then find the other synced text that depends on them: run `python3 scripts/check_held_sdlc_prose.py --template <clone> --old <old _commit> --new <new _commit> --base <pre-sync commit> <each reported SDLC-NNN>`, where `<clone>` is a full (not shallow) `git clone` of `.copier-answers.yml`'s `_src_path` into a temporary directory.
   It finds every upstream commit that changed a reported statement and prints each line of that commit's other files that the sync brought in or took out; copy each printed line as the synced file now has it, verbatim, the same way.
   It matches whole lines only, so also read each file it names, and each other file those commits touched, for reworded dependent text.
3. Edit the synced `docs/software-development-lifecycle.md` back to each reported statement's exact old text (deleting a line the pre-sync copy lacked, and re-inserting one it had at its ascending `SDLC-NNN` position), so this sync PR carries none of it; everything else upstream changed in that file (new prose, a typo fix, a reordering, a new non-statement section) flows through as normal.
   Re-run the check to confirm it reports nothing.
   Revert each dependent line step 2 found back to its pre-sync text the same way, then re-run `check_held_sdlc_prose.py` to confirm it reports nothing, or say in the PR body why each line it still prints doesn't depend on the held wording.
   Log everything this step reverted, statements and dependent lines, as one `docs/forge-overrides.md` entry naming the step 4 ticket, so a later sync's conflict resolution keeps the hold instead of taking upstream's version (`.forge/forge-overrides.md`).
   A conflict hunk touching a held statement is never resolved by picking a side: hold it per this section; both `check_sdlc_wording_changes.py` and `check_sdlc_wording_hold.py` refuse on an unresolved conflict marker.
4. If anything was held, open a second branch off the pre-sync commit and apply just the held statements' new lines, verbatim as step 2 captured them, not the script's output.
   File one short ticket for it and open the branch as its own lifecycle-doc PR (`.forge/process-and-evidence.md`, "Process changes follow the lifecycle doc").
   Link the two PRs to each other in both bodies: this sync PR does not merge the statement wording; only the owner's approval on that second PR does.
   The ticket lists the held statement numbers and, one line per file, each dependent line step 3 reverted, verbatim as step 2 captured it, plus any other synced forge-owned text whose meaning depends on held wording; it is a record for that thread, not for the owner to read.
   If this sync PR merges before that second PR, rebase the second PR onto the new `main` once it does, since its base otherwise goes stale.
5. Ask the owner once, in one self-contained request, whether to accept the held statements: a decision card where the harness offers one, otherwise one comment on the lifecycle-doc PR addressed to the owner.
   The request links the lifecycle-doc PR's diff and quotes every held statement's new text in full, verbatim from step 2, beside its old text (or marked new or removed), so the owner can decide from the request alone (`.forge/feature-pipeline.md`, "Every approval request links to the wording it asks about").
   It offers two answers, "Accept all" and "Hold", and leaves the ticket's dependent-file list out.
6. On "Accept all", record the owner's answer in the lifecycle-doc PR body in the form `.forge/process-and-evidence.md`, "Evidence: where each record lives", gives, then merge that PR as "Process changes follow the lifecycle doc" says.
   Merge exactly the text step 2 captured, which is what the owner approved, without re-fetching upstream, re-rendering the template, or diffing against upstream's current state first, even if it has moved; a later upstream change is the next sync's to hold.
   Once both it and this sync PR have merged, open one more PR off the new `main` that applies the dependent lines the ticket lists, verbatim, and removes the step 3 override entry, citing the merged lifecycle-doc PR; it is ordinary forge-owned text, so it merges once its review gate is clear.
   On "Hold", record the owner's answer on the ticket and leave the ticket and the PR open and unmerged until the owner says otherwise.

## Walk the integrator steps

A TheForge release can ask the integrator for more than conflict resolution (create a label, answer a new Copier question, re-paste a snippet, rewrite a file to a new shape, create a secret), recorded only in `docs/release-notes.md`'s "For integrators" section, which `--defaults --conflict inline` never shows.

1. Run `python3 scripts/check_integrator_steps.py --template <clone> --old <old _commit> --new <new _commit>`, against the same clone "Hold SDLC wording changes for the owner" step 2 uses (a full, not shallow, clone of `.copier-answers.yml`'s `_src_path`).
   Its first line, `Integrator steps: <old>..<new> N: <ids or "none">`, is the list to walk; each following line, `- #<id> (<version>): <summary>`, is one item from a release the range crosses, oldest first, taken from the release's `docs/release-notes/<version>.integrator-steps.json` sidecar or, for an older release without one, from each "For integrators" bullet ending `(#N)`.
2. For each item, do what it asks in this sync branch, or say in the sync PR why it doesn't apply (the project doesn't use the feature, does it another way, or an earlier sync in this range already did it).
   An item needing its own ticket (a non-mechanical rewrite, an owner-only decision) gets one, tracked there and linked from the sync PR.
3. Paste `check_integrator_steps.py`'s own first line into the sync PR body under "Integrator steps" (see "Review and merge"), then one line per item underneath it: `#<id>: <what was done, why it doesn't apply, or the ticket it's tracked under>`.

`review-gate-check.yml` re-runs `check_integrator_steps.py --pr-body` on every PR whose `.copier-answers.yml` `_commit` changes, failing it when an item in the range has no `#<id>` after the body's "Integrator steps" marker; "none" passes with nothing further.

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
- `check_sdlc_wording_changes.py --template`'s first line from step 1 above, verbatim, under "SDLC upstream changes" — `check_sdlc_wording_hold.py` recomputes it and fails the PR if this line is missing or doesn't match;
- `check_integrator_steps.py`'s own first line from "Walk the integrator steps" step 1, verbatim, under "Integrator steps", followed by one line per item saying what was done, why it doesn't apply, or the ticket it's tracked under — `check_integrator_steps.py --pr-body` re-checks every `#<id>` is present and fails the PR otherwise;
- every line added to or removed from `.forge/entrypoint.md`'s imports, under "Entrypoint import changes", or "none";
- "Migration: kept lines", or "not needed";
- every conflict and how it was resolved, and every override entry it removed;
- every SDLC statement held out, under "SDLC wording held", linking the separate lifecycle-doc PR it was moved to and the owner's accept/hold request (step 5 of that section), or "none";
- every dependent line reverted with them, by file, under "Dependent lines held", and why each line `check_held_sdlc_prose.py` still prints doesn't depend on the held wording, or "none";
- "Upstream candidates" (see "Surface and record upstream candidates" below), or "none".

If the coordinator or build-thread brief changed upstream, the harness's project-level copies of those texts change in the same session (`.forge/orchestration.md`, "The coordinator-core snippet is not a source of rules").

Once the PR is open and the candidates below have been asked, report the sync back to the owner before asking for review ("Report the sync back to the owner" below).

## Surface and record upstream candidates

Right after the sync PR opens, ask the owner about every open candidate from "Before you start" step 4 together, one question each, by decision card where the harness offers one, otherwise one comment on the sync PR addressed to the owner: "Offer `<file>`'s `<part>` upstream to TheForge?", linking the entry at the sync branch.
Options:

- **Propose this as a back-port patch.** Post a ticket on `.copier-answers.yml`'s `_src_path` only when it is a hosted repository whose visibility is private and on which this session can create issues (check, for GitHub, with `gh repo view <owner/repo> --json visibility,viewerPermission` or the harness's equivalent).
  Otherwise, including when the check can't answer or filing fails (auth, network, rate limit), draft the ticket in the sync PR body and never post it.
  Either way the ticket (or draft) holds the entry, the project's diff of that file against the upstream render, the project's `_commit`, and a link to the sync PR.
  Then write a `proposed` marker on the entry: `yes — proposed as <ticket link or "drafted in <sync PR link>">, <date>`.
- **Decline.** Write a `declined` marker: `no — declined by owner, <date>`.
- **Not yet.** Change nothing; the candidate stays open and is asked again at the next sync.

An entry's `Upstream candidate` value is always one of four: `yes, rewritten generically` (open, unanswered), `yes — proposed as ..., <date>` (written here, on "Propose"), `no, project-specific` (never a candidate), or `no — declined by owner, <date>` (written here, on "Decline").
Marker edits are commits on this sync PR.
The PR body's "Upstream candidates" line lists each question and the owner's answer in the approval-record form (`.forge/process-and-evidence.md`), or "none" when "Before you start" step 4 found no open candidates.
This sync PR does not wait on the questions: one still unanswered at merge is recorded as "Not yet", asked again next time.
`docs/forge-overrides.md` is missing, or has no `Upstream candidate` lines: no questions, "Upstream candidates: none".

## Report the sync back to the owner

The owner isn't watching the sync step by step, and the PR body is a mechanical record, not a report to them.
Once the sync PR is open and the candidates asked, post one short summary where the sync was asked for (the owner's project thread or chat, never the PR body alone), before asking the owner to review and merge.

At minimum, cover:

- **What got updated.** `_commit` before -> after, "Synced ref" (the same value as the PR body's own line), and a plain-language list of what actually changed for this project: new or changed skills, `.forge/` files, and generated docs, not a diff stat.
- **Current forge overrides.** Every live entry of `docs/forge-overrides.md` as it stands after this sync, not only those it touched: file, what's overridden, and why.
- **The sync PR link**, for anyone who wants the full detail.

Also fold in, condensed from what the steps above already produced:

- **Time/effort.** Roughly where the sync's time went (for example "most of it was resolving conflicts in `<file>`", "the SDLC wording hold", or "the trust-diff review").
- **Conflicts resolved.** Which files had conflict markers and how each was resolved (kept the project's override, took upstream, or needed an override-entry decision).
- **Skipped or held back.** Anything intentionally not synced: SDLC statements held for the owner with the lifecycle-doc PR link, project-owned or `_skip_if_exists` files, and declined upstream candidates.
- **Upstream candidates.** Each candidate question asked this sync and its answer (proposed, declined, or not yet).
- **Needs the owner's attention.** Any SDLC wording still awaiting accept or hold, a `needs-decision` ticket filed for an upstream policy this project's lifecycle doc doesn't yet justify, or a drift/trust-diff finding that needed manual review before running `--trust`.

Keep it short: a reader who wants the full detail follows the PR link.
