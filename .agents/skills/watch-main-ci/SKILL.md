---
name: watch-main-ci
description: "The full Main Health routine for this repo: the post-merge review pass, the local full-suite stand-in check, their shared setup, reading the scheduled CI pass, and the rotation/handover protocol between Main Health threads. Use when asked to watch, monitor, or babysit main's CI health, or when running or handing over the Main Health thread."
disable-model-invocation: true
---

# Main Health

## Per-repo values

The procedure below reads these values instead of naming files directly.
Change a row here (and record it in `docs/forge-overrides.md`) when the project's own setup differs.

| Value | This repo |
|---|---|
| Repo | `forger88/TheForgeStaging` |
| Post-merge review tracker issue | #60 |
| Local full-suite evidence tracker issue | #344 |
| Post-merge review procedure | `.agents/skills/post-merge-review/SKILL.md` |
| Queue-sweep procedure | `.agents/skills/queue-sweep/SKILL.md` |
| Forge drift check | `scripts/check_forge_drift.py` |
| Build-thread setup recipe | `docs/agents/build-thread-setup.md` |
| Local full-suite script | `scripts/local-full-suite.sh` (project-owned; not generated, see "Routine 2"; the `local_full_suite_script` answer) |
| Local full-suite publish switch | `LOCAL_FULL_SUITE_PUBLISH` (the `local_full_suite_publish_var` answer) |
| Shared setup command | `pip install pre-commit==4.3.0 && pre-commit install --install-hooks` |
| Full test suite command | `python3 -m unittest discover -s scripts -p 'test_*.py' && python3 -m unittest discover -s template/scripts -p 'test_*.py'` |
| Dispatched CI workflows (scheduled pass) | every check workflow under `.github/workflows/`; list them here by name once stage 0 settles them |
| Working folder for mutable state | the harness's shared project folder |
| Held sync ticket's trusted author | `forger88` — correct only when this repo is owned by a user, since a GitHub issue is always authored by a user account and never by an organisation. If `forger88` names an organisation, change this row to the actual account Main Health and `forge-sync` authenticate and post as, and record the override in `docs/forge-overrides.md` |

The two local full-suite rows above change through their own answers (`.forge/ci-and-checks.md` names the `copier update` command), not by editing the row.
Only the script's name, its publish switch, and the status-context prefix derived from the script's basename vary per project this way.
Routine 2's mechanics below are a fixed forge contract, not a per-project answer: the exclusive lock with `--is-running` and its overlap exit code, the `SKIP` list, both markers, and `last-verified.txt`.
A project whose stand-in genuinely works differently (no lock, a differently-shaped baseline file, and the like) either converges its script on this contract or keeps a mechanics-only entry in `docs/forge-overrides.md`.

This is the complete routine for the Main Health thread: not just reading CI, but the two scheduled checks that stand in for it, the setup they share, which tier runs which part, and how one thread hands off to the next.

It's written to the repo rather than kept only as project instructions or a working file, so the routine survives losing either of those.
Read this file first on every rotation; don't rely on remembering it from an earlier thread's context.
`.forge/main-health-patterns.md` says what this thread watches and when it escalates; this file says how.

## Why two routines exist

This repo runs no CI on pull requests or on push to `main`: every check workflow under `.github/workflows/` is manual-dispatch only, to keep CI minutes down (`.forge/ci-and-checks.md`, "Don't manually trigger CI runs").
The full check pass is dispatched on `main` on the owner's schedule (twice a day by default), and only when something has merged since the last pass.
So between dispatches, a regression on `main` has no CI signal at all.

**Dispatching the real workflows is always the preferred signal.**
The local full-suite script (Routine 2 below) exists only because CI runners are not affordable to run more often than the scheduled dispatch: it's a local stand-in for that missing signal, not a replacement for real CI.
If CI usage becomes cheap enough to run more often (a plan change, a self-hosted runner, anything that changes the cost calculus), dispatch real CI more often and retire or shrink this script's role accordingly.
Treat the stand-in as the workaround it is, not the destination.
Nothing here changes the "Don't manually trigger CI runs" rule: this thread still never dispatches or re-runs a workflow outside the two named exceptions there.

The other routine, the **post-merge review pass**, is not a stand-in for anything.
It catches a different class of bug (cross-PR, migration, resource-exhaustion-under-execution) that even a fully staffed per-PR CI and review setup wouldn't catch, because it reviews what several merged PRs did *together*.
It runs on its own merit regardless of CI affordability.

## Shared setup: pay the environment cost once per thread

Both routines need the same environment: the project's dependencies, any local services the full suite needs (a database, a message broker, a browser for end-to-end tests), and the pre-commit hook.
Set it up once when the thread starts, not once per routine firing:

```
pip install pre-commit==4.3.0 && pre-commit install --install-hooks
```

Make the setup idempotent, so re-running it on a later firing just confirms everything is still there (see `docs/agents/build-thread-setup.md` for the per-scope detail if something's missing).
Keep the worktree the thread was started in; don't re-clone or re-fetch into a fresh worktree per firing.
Both routines read `origin/main` directly, and `git fetch origin main` in place is enough.

## Operational safety rules

Both routines, and every review sub-agent either one dispatches, follow `.agents/skills/post-merge-review/SKILL.md`'s "Operational safety rules" section.
Those rules are written once there rather than duplicated here; read them before running either routine, not just before a post-merge review pass.

## Routine 1: the post-merge review pass

**Cadence**: every 4 hours, skipping the firing entirely if nothing has merged to `main` (or to any upstream repo this project's tracker says the pass also covers) since the watermark.
Schedule it with the harness's recurring-trigger tool, bound to this session (for example cron `0 2,6,10,14,18,22 * * *`), and have the fired prompt check the watermark before doing anything else.
A no-op firing costs nothing but shouldn't run the setup or spin up reviewers.
The hours are offset from Routine 2's passes so the two seldom meet; when they do, the overlap rule under Routine 2 decides which yields.
Every 5th pass also includes `post-merge-review`'s step 5a (the tautological-test sample), which itself follows the overlap rule and never runs without the owner's yes on that pass's decision card.

**Procedure**: `.agents/skills/post-merge-review/SKILL.md` has the full procedure: the watermark format, the surviving-lines file set, batching by subsystem, the grading rules, the **security axis** (STRIDE against `docs/security/threat-model.md` and the rest of `docs/security/`, with no change to this routine's cadence), the capability-tier split, the filing and bundling rules, and the operational safety rules.
Read it before running a pass; don't rely on a summary of it going stale here.
The tracker issue #60 holds the pending notes (one comment per merged PR), the watermark and the run log (SDLC-095), never the procedure: a tracking issue's body is the wrong place for text that changes more often than the skill that enforces it, and issue bodies have a size limit.

**The same firing also runs `queue-sweep`** (`.agents/skills/queue-sweep/SKILL.md`): specifically the first firing of each day (02:00 UTC in the example cron), so no separate trigger or state file is needed to pick which firing runs it.
Unlike the post-merge review pass, `queue-sweep` runs every time that hour comes around, with no watermark-based skip: its gaps build up from comments and label changes as well as merges, so a firing with nothing merged still has something to find.
It's tracker API reads only, with no test load, so it needs no environment setup and the Routine 2 overlap rule below doesn't apply to it.
Reports land under the working folder, in `queue-sweep/`.

### Forge drift check

**The same first daily firing also runs the forge drift check**, as its own step, separate from `queue-sweep`: `queue-sweep` doesn't call it.
It is API and git only, with no test load, so it needs no environment setup and stays outside the Routine 2 overlap rule below.
`behind` counts only commits that touch the upstream's template subdirectory or its Copier config file (`render_pathspec` in `check_forge_drift.py`), not every commit, so a commit that changes only this repository's own ADRs or design docs never moves it.
`behind` is counted against the ref a default sync would target (the `target=` field: the latest release tag, or HEAD when upstream has no tag), and `unreleased=<n>`, shown only when tags exist, counts commits past that tag for information and never as drift.

1. Run `python3 scripts/check_forge_drift.py`.
2. **Exit 3 (`entrypoint=missing`):** report it to the owner immediately as a Must, "the forge rules are not loading".
   Do this whatever the drift result, and before the steps below.
3. **Behind (`behind=<n>` with `n > 0` on the result line, whatever the exit code, so a missing entrypoint does not suppress the ticket).**
   Look for an open issue whose title starts with `Sync forge-owned files to TheForge ` **and whose author is the held sync ticket's trusted author** (the per-repo value above) — the one identity Main Health and `forge-sync` ever file or act on this ticket under, which another account cannot forge regardless of what label or body text it gives a look-alike issue.
   - If it carries `needs-decision`, retitle it to the new short upstream SHA and replace its body with the new result.
   - If it exists without `needs-decision`, the owner has released it and a sync is under way: leave it alone and only mention the drift in the report, since it is now the running sync's backing ticket.
   - If there is none from that author, create it: title `Sync forge-owned files to TheForge <short upstream sha>`, label `needs-decision` and only that, body the result line, the subject list (ending "…and N more" when `behind` exceeds the listed subjects), and the sentence "Held until the owner says to sync; then run `.agents/skills/forge-sync/SKILL.md` against this ticket."
     A title-matching issue from a different author is never retitled, never treated as released, and never counted as "none" above: it doesn't block filing or updating the real ticket. Mention it once in the daily report as a possible forged look-alike.
   - Never label it `queued`, and never run `forge-sync`.
4. **Current (exit 0):** nothing to do.
5. **Unknown (exit 2):** mention the error once in the daily report; file nothing.

## Routine 2: the local full-suite stand-in check

**The script is project-owned and not generated.**
If the project has not yet written `scripts/local-full-suite.sh`, this routine is an open gap: record it on the post-merge review tracker #60 and run only Routine 1 and the scheduled CI pass.
Lead that note with its own marker, `<!-- local-full-suite-script-missing -->`, distinct from both the pending-note and archive-comment markers on the same tracker, so `queue-sweep` check 11(a) never mistakes it for either when it classifies that tracker's comments.
The script runs every check that can run in the agent's sandbox (lint, type checks, the pin guard, migrations, the full test suite with its coverage floor, end-to-end tests against local services) as named steps, and it does the following itself:

- derives its pre-commit-backed steps directly from `.pre-commit-config.yaml`'s own hook ids (one step per hook, skipping only the ones meaningless on a checkout of `main`, such as a branch-name check) rather than hand-copying a second step list, so a hook added to the pre-commit config needs no matching edit here to also run against `main`;
- holds an exclusive lock for its whole run (for example `flock` on a file at one fixed path, inside a directory the script creates private to its user and refuses when another account owns it or could write to it), exits with a distinct code (75 by convention) if a second run starts, and offers `--is-running` (exit 0 means running);
- accepts a `SKIP` list of step names for a resumed or partial run;
- **on a full run (`SKIP` empty), and only when an explicit publish switch is set** (for example `LOCAL_FULL_SUITE_PUBLISH=1`), **posts one comment on the local full-suite evidence tracker #344**: a single-line marker `<!-- local-full-suite-evidence sha=<sha> finished=<ISO8601 UTC> aggregate=pass|fail -->` (`pass` only when every step in the run passed) followed by a human-readable per-step table.
  This comment is the run's canonical evidence (SDLC-099) in every environment this routine targets, including a sandbox whose GitHub proxy refuses commit-status writes, and it is required to succeed: log `ISSUE-POST-FAILED` and treat it as a bug in the script, never as a reason to discard the run's actual result;
- **also attempts a commit status per step it ran** (`local-full-suite/<step>`, success or failure, a description like `PASS 312s`) plus one aggregate `local-full-suite` status, all on the run's HEAD sha, as a best-effort secondary record, with publishing gated by the same switch as the tracker comment.
  Some agent environments refuse commit-status writes outright even when they can otherwise reach the hosting platform; that refusal is expected there, not a bug — log `STATUS-POST-REFUSED` and carry on.
  A status post that fails for any other reason logs `STATUS-POST-FAILED` instead, which *is* worth investigating, since the tracker comment above already proves the run and its publish switch both worked;
- on a fully clean run with publishing on, first re-checks that the run's sha is still `origin/main`'s current head (a fresh `git fetch origin main && git rev-parse origin/main`, not the value read when the run started, since a long full-suite run can take long enough for `main` to move): if it no longer matches, skips the push and logs `GREEN-PUSH-SKIPPED-STALE` — `main` moved during the run, so a clean result for an older sha isn't evidence to push over whatever is newer and still unverified, and this is not a failure of any kind.
  Otherwise fast-forwards `refs/heads/green` to that commit with a plain non-force push (`git push origin <sha>:refs/heads/green`).
  This push doesn't depend on whether the statuses posted; it only needs `git push`.
  A rejection the remote itself makes because of the ref's own state (a non-fast-forward rejection) or a platform policy that applies regardless (such as GitHub's GH007 private-email-address block, where it applies) is logged as `GREEN-PUSH-REFUSED`, never a script bug: `green` is stuck and needs the recovery below, not a code fix.
  A rejection for bad or expired credentials (the push authenticates as a principal with no write access, or a token error) is logged as `GREEN-PUSH-FAILED`: that's an environment misconfiguration to fix, not a stuck ref.
  Any other push failure (the git command erroring locally, a network failure, and the like) is also logged as `GREEN-PUSH-FAILED`, a bug in the script worth investigating, as before.

**Cadence**: on a schedule (twice daily by default, interleaved with the dispatched-CI cadence so the two signals alternate), skipping the firing if `origin/main`'s head hasn't moved since the commit recorded in `last-verified.txt` in the working folder's `main-health/` directory.
Schedule it with the harness's recurring-trigger tool, and have the fired prompt do the skip check (`git fetch origin main && git rev-parse origin/main` compared against `last-verified.txt`) before running anything.

**Overlap rule**: the two routines never run at the same time, because the combined load makes timing-sensitive tests time out.
A full-suite firing that finds Routine 1's review sub-agents still running waits for their completion notifications before starting (no sleep or poll loop).
A Routine 1 firing that finds the full suite running is skipped; its watermark check picks the same commits up at the next firing.
The script's own lock enforces the full-suite side, and a Routine 1 firing checks `scripts/local-full-suite.sh --is-running` before it starts.

**Running it**:

```
LOCAL_FULL_SUITE_PUBLISH=1 scripts/local-full-suite.sh <worktree> <log-dir>
```

The publish switch is what turns on the real tracker-comment and commit-status posts and the `green` push.
This routine's own invocation is the one place that sets it; nothing else should, including a manual run you're using to debug the script itself.
The script in the repo is the canonical copy; don't maintain a second copy in the working folder or anywhere else.

**Known measurement quirks**: keep the running list in the Main Health patterns notes file (`.forge/main-health-patterns.md`, "Patterns worth recording"), not here.
Two belong in every project's list from the start.
Run the full suite the same way real CI runs it (the same parallelism, the same environment variables), or a pass here doesn't mean a pass there.
Don't run review sub-agents concurrently with a full-suite pass.

**A dependency-audit step failure is a finding, not a flake.**
An audit step (a full-tree vulnerability audit of the pinned dependencies) can go red with no merge behind it at all, purely because a new advisory was published against a pin already here.
Until it's cleared, it holds back the `green` push the same as any other step's failure.
Don't re-run it.
Instead, read the audit's own output for which package and advisory, then either file a version-bump ticket (bug-first, since this is a live vulnerability) when a fix exists, or add a reasoned, tracked entry to the project's advisory-ignore list (via a normal ticket and PR, same review gate as any other change) when none does yet.
Report it the same way any other red step is reported; don't spend the one allowed re-run on it.

**Every full run (`SKIP` empty) posts its own evidence (SDLC-099, SDLC-103)** to the local full-suite evidence tracker #344, needing no separate action here.
A resumed or partial run (`SKIP` non-empty) attempts per-step commit statuses for the steps it reran, but posts no tracker comment and no aggregate status: there's nothing to aggregate over a run that didn't exercise every check, and a partial run is not the record `queue-sweep`'s overdue check is looking for.
Treat an `ISSUE-POST-FAILED`, `STATUS-POST-FAILED` or `GREEN-PUSH-FAILED` line in the script's log as a bug in the script to investigate, never a reason to treat the run's actual result as unproven, and never a reason to force-push.
`STATUS-POST-REFUSED` is expected wherever the environment's GitHub proxy blocks commit-status writes and needs no action: the tracker comment is already the run's evidence there.
`GREEN-PUSH-SKIPPED-STALE` needs no action either: it means `origin/main` moved during the run, not that anything failed.
`GREEN-PUSH-REFUSED` is neither of those: it means `green` is stuck at its current value and no later push will fast-forward past it on its own.
Report it and follow "Recovery when the green push is refused" below rather than treating it as a script bug or retrying the push.

**Recovery when the green push is refused.** A `GREEN-PUSH-REFUSED` line means the remote itself declined a plain non-force push, for one of two reasons: `refs/heads/green` already points somewhere that isn't an ancestor of the sha being pushed (a true non-fast-forward), which this routine's refusal to force-push leaves permanently stuck — no later `main` commit can fast-forward past it either — or a platform policy blocked the push outright regardless of ancestry (such as GitHub's GH007 private-email-address block, where it applies).
Report it to the owner rather than resolving it yourself: ask them to delete `refs/heads/green` in the GitHub web UI.
Once it's gone, recreate it from a freshly verified `origin/main` head through the REST API's create-ref call (`gh api repos/<owner>/<repo>/git/refs -f ref=refs/heads/green -f sha=<verified head sha>`), after confirming that sha both equals `origin/main`'s current head and was the sha of a run that actually passed clean.
A REST ref update with `force=false` (`gh api --method PATCH repos/<owner>/<repo>/git/refs/heads/green -f sha=<sha>`) is also fast-forward-only, the same as the plain push that just failed, so it can stand in for the delete-and-recreate step only for a policy-block refusal, not for a true non-fast-forward: the ref's own ancestry problem is exactly what made the first push fail, and replaying the same fast-forward-only operation through a different transport fails the same way.
Where it does apply, and where the environment's token and proxy allow a ref write (some agent proxies refuse ref writes outright, which is why the web-UI delete is the fallback that always works), it saves the delete step.

**On a clean pass**: update `last-verified.txt` to the commit SHA that just passed.
**On a failure**: leave `last-verified.txt` where it was, so the next firing retries from the same baseline, not a newer unverified one.
Treat it the same as a dispatched-CI failure, using the steps under "Reading the scheduled CI pass" below: find the culprit commit and PR, rule out infrastructure noise, root-cause it, and report.

**When a real CI run is available**: a green dispatched run of the full check pass on `origin/main`'s current head is strictly stronger evidence than a local pass against the same commit.
It also sets `last-verified.txt` to that head, and Routine 2's own firing is skipped for that commit (its skip check already compares against the file).
Fast-forward `refs/heads/green` to that head by hand after confirming the run is green (`git push origin <head>:refs/heads/green`, no `--force`), since the dispatched workflow doesn't push it.
This doesn't change anything about *triggering* real CI; it only says what to do with a green result once one lands.

## Reading the scheduled CI pass

When the owner's scheduled full-pass routine does fire real CI workflows, read the result this way.

1. **List recent runs on `main`.**
   Re-check the dispatched-workflow list in "Per-repo values" against `.github/workflows/` itself; it can grow.
   A lint workflow is manual-dispatch only and not part of the scheduled pass (the pre-commit hook is the real lint gate).
   Workflows that need resources the sandbox lacks, or that make paid external calls, are out of scope for this skill.
   For each in-scope workflow, get the most recent completed run on branch `main` (through the hosting platform's API or its MCP tools: list workflow runs filtered to branch `main` and status `completed`, one per page).
   A workflow the last pass didn't dispatch may not have run recently at all; absence isn't failure, so only check ones that *have* a recent run.
   Verify the tool names against the live toolset at the start of a rotation, since they can be renamed.
2. **Any failed conclusion?**
   If every latest run succeeded (or there's nothing new since the last check), stop here.
   - **2a. A timeout is a real failure to profile, not a limit to raise.**
     Profile first (find the hotspot, fix or justify it) before proposing a new limit.
     Raising a timeout without profiling needs the owner's explicit sign-off each time, and timing out again after a limit was already raised once means profile again, not ask for more.
3. **Rule out infrastructure noise before treating it as a real break.**
   Check the run's billable time and whether its job logs have actual content; a run that billed about nothing with no logs is a runner-provisioning blip.
   If it's infrastructure noise, re-run the failed jobs once, and if the re-run is still infrastructure-shaped, note it and stop.
4. **Find the commit and the PR that merged it.**
   The failing run's head SHA is the `main` commit to blame; get its message, or for a squash merge resolve it to its PR with `scripts/detect_pr_for_commit.py forger88/TheForgeStaging <sha>` (a `merge_commit_sha` lookup) rather than searching merged PRs by title or timestamp, which misses a PR merged under a custom squash title.
   - **4a. A red loop before a hypothesis.**
     Follow `diagnosing-bugs` Phase 1: one command, run locally, that goes red on the reported symptom, before any theory about the cause.
5. **Idempotency.**
   Before investigating further, check the culprit PR's comments for a marker containing this run's id (`<!-- watch-main-ci:run-<run_id> -->`); if present, stop.
6. **Investigate root cause.**
   Pull the failing job's logs (failed jobs only).
   Check whether the failure is inside the diff the culprit PR actually touched; a failure elsewhere is more likely pre-existing flakiness surfacing for the first time than something that PR broke.
   Re-run once before concluding "flaky" from a single unreproduced failure.
7. **Report.**
   Post one comment on the culprit PR: which check failed, the actual error, whether it's inside or outside that PR's own diff, and a proposed fix only if it's a small, confident, low-risk one-liner.
   Include the `<!-- watch-main-ci:run-<run_id> -->` marker.
   Never push directly to `main` to fix a break; open a small ticketed PR if you're confident in a fix, otherwise the report is the deliverable.
8. **Also surface it to whoever is watching this session directly**: a broken `main` is higher-priority than most things a background loop stays quiet about.

## State: what lives where, and why

| What | Where | Why there |
|---|---|---|
| This routine's procedure | `.agents/skills/watch-main-ci/SKILL.md` (this file) | Survives a rotation and survives losing the project instructions. |
| The local full-suite script | `scripts/local-full-suite.sh` | Code, not state, belongs in the repo. |
| A full-suite run's per-check results | A comment on the local full-suite evidence tracker #344 (the canonical record, `<!-- local-full-suite-evidence sha=... finished=... aggregate=... -->` plus a per-step table), plus best-effort commit statuses on the run's HEAD sha (`local-full-suite/<step>`, aggregate `local-full-suite`) wherever the environment allows posting them | Posted by the script itself (SDLC-099); the tracker comment is durable and world-readable in every environment this routine targets, including a sandbox whose GitHub proxy refuses commit-status writes, so it needs no separate working-folder file. |
| Cross-rotation lessons and patterns | The Main Health patterns notes file named in `.forge/main-health-patterns.md` | Append-only, read on every rotation. |
| The post-merge review's pending notes, watermark and run log | The tracker issue #60 | Already durable; don't duplicate it elsewhere. |
| `last-verified.txt`, this rotation's `handover.md`, per-run repros | The working folder's `main-health/` directory | Mutable, rotation-scoped working state, fine to lose and rebuild (a fresh full-suite pass regenerates `last-verified.txt`; `handover.md` is rewritten every rotation). Never the only copy of a procedure or a lesson that should outlive a rotation. |
| Build-thread setup recipe | `docs/agents/build-thread-setup.md` | Code-adjacent reference, not mutable run state. |
| Post-merge review procedure | `.agents/skills/post-merge-review/SKILL.md` | Code-adjacent reference; the tracker holds the pending notes, watermark and run log, never the procedure. |
| Queue-sweep procedure and reports | `.agents/skills/queue-sweep/SKILL.md` (procedure); the working folder's `queue-sweep/` directory (per-run reports from standing firings) | A standing firing's report is run-scoped output, fine to lose and regenerate on the next sweep. A pre-release firing's report also goes on the release ticket (SDLC-101), and that copy is durable. |
| Scheduled firings themselves | The harness's trigger list | Not file-based; recreated by the new thread at rotation (below), since a trigger can't be read out of the repo; only its *parameters* (cadence, skip logic, prompt) are documented here so they can be recreated correctly. |

### Scheduled passes and their evidence (SDLC-103)

This mirrors the table of the same name in `.forge/process-and-evidence.md`, kept here too because this is the file a rotation actually reads for routine state.
The two hosting-platform-record rows are what `queue-sweep` check 11 reads to decide whether a pass is overdue.

| Scheduled pass | Evidence when it runs | Absence check |
|---|---|---|
| Post-merge review pass | Archive comment (marked `<!-- post-merge-review-archive covered=... -->`), run log row on the tracker #60 | `queue-sweep` check 11(a): oldest pending note not covered by any marked archive's `covered` list more than 3 days old, or a PR merged since the latest marked archive more than 3 days old with no new archive since |
| 5a mutation sample | "5a: not due" or "no owner answer" in the archive comment | None; a skipped firing correctly leaves no record |
| Scheduled CI dispatch | CI runs on the hosting platform | None needed; the runs are the record |
| Local full-suite run (twice daily) | A marked comment on the local full-suite evidence tracker #344 (the canonical record); per-step and aggregate commit statuses too wherever the environment allows posting them | `queue-sweep` check 11(b): no marked comment on the tracker in the last 24 hours while `main`'s head has moved since the last one |
| Standing queue-sweep (daily) | None; not a scheduled assurance pass, and its reports stay in the working folder | None |
| Threat-model reconcile, pre-release | "Last reconciled @ `<sha>`" line in `docs/security/threat-model.md` | None |

## Starting this thread

Before anything else, call the harness's recurring-trigger tool for both Routine 1 and Routine 2, using the cadence and skip logic documented above, bound to this session.
This applies identically whether this is a brand-new Main Health thread with no predecessor or a thread rotating in from a handover: don't wait to read "Rotation and handover" below, and don't infer that trigger creation is only a hand-off step because that's the section it also appears in.
A fresh trigger bound to this session is normal either way; its id won't match any predecessor's.

## Rotation and handover

**Default trigger**: the Main Health thread rotates at a pass boundary (after a completed post-merge review run or a completed full-suite pass), not on a fixed run count or context percentage.
The build-thread rotation rule in `.forge/coordinator-core.md` (4 tickets or about 50% context) is specifically for build threads and does not apply here.
This is a **Default** (`.forge/never-default.md`): the coordinator or the owner can call for a different point when the work genuinely needs it (for example mid-investigation of a real break), but say so explicitly rather than silently drifting past it.
Rotating after more than one post-merge review run per thread (rather than every run) is deliberate: a thread that's seen several runs can spot a pattern across them and turn it into a self-review recommendation, which a thread that only ever sees one run can't do.

**`handover.md` carries state only.**
It is a rotation-scoped snapshot of mutable facts (heads, watermarks, trigger ids, known failures, open items), never a place a procedure note, a lesson, or anything meant to outlive this rotation gets written for the first time.
Any such note belongs in this skill, the Main Health patterns notes file, `.agents/skills/diagnosing-bugs/SKILL.md`, or `CLAUDE.md`'s project-owned sections, whichever fits, **landed in the repo before the handover is written**.
A `handover.md` that carries a procedure note instead of (or in addition to) a repo edit is not state-only, and the incoming thread treats that as a gap to close, not a quirk to tolerate.

**When you are the outgoing thread**:

1. Land every procedure note or lesson from this rotation in the repo first (a small ticketed doc or skill PR; `Requirements: none (internal)`).
   Do this before step 2, not after, so the handover file never becomes the only record of something that should survive past this rotation.
2. Write `handover.md` in the working folder's `main-health/` directory, replacing its previous contents, with these sections (keep the same headings so the next thread's read is mechanical):
   - **State at handover**: `origin/main` head, the post-merge review watermark (date, run number, commit), `last-verified.txt`'s value and whether it's current or stale, and the archive issue currently in use.
   - **Routines**: the triggers' ids, their cron expressions, and their skip conditions, as actually configured; copy from the harness's trigger list, don't recall from memory.
     Note that the first daily firing of Routine 1's trigger also runs `queue-sweep`.
   - **Known failures and flakes**: anything currently red or flaky on `main`, with the tickets tracking each.
   - **In-flight and open items**: open post-merge review sub-issues, any open decision the owner hasn't answered yet.
   - **Repo PRs landed this rotation**: a one-line list of the PRs from step 1 above, so the incoming thread can verify they're actually on `main` rather than taking the claim on faith.
3. Tell the incoming thread (once it exists) to disable your triggers once it confirms its own are running; don't disable them yourself first and leave a gap where neither thread is watching.

**When you are the incoming thread**:

1. Read this file, `.agents/skills/post-merge-review/SKILL.md`, the tracker issue #60's body, the Main Health patterns notes file, and the outgoing thread's `handover.md`, in that order.
2. **Check that the outgoing thread actually landed its procedure notes in the repo**, not just listed them in `handover.md`: diff the PRs it names against what's actually on `origin/main`.
   If a note only exists in the handover file, land it in the repo yourself before relying on it, and treat the gap as a finding (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line") rather than a one-off to quietly patch.
3. Set up the shared environment ("Shared setup" above).
4. Arm both routines' triggers per "Starting this thread" above, if you haven't already.
5. Run a fresh full-suite pass (once the script exists) to get a current `last-verified.txt` rather than trusting a handover that might be stale by the time you start.
6. Confirm the old thread's triggers are disabled once yours are confirmed running; ask the coordinator to do it if you can't reach the old thread directly.
7. Reply in this thread that you're live, with the watermark and verified-commit state you inherited.

This routine is driven by the scheduled triggers above, bound to this session, not by an external interval wrapper around the thread.
