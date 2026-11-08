---
name: implement-with-merge
description: "Implement a feature or fix end-to-end: build it, open a PR, run self-review using this repo's MoSCoW triage, and merge to main. Use when the user wants full ownership through merge, not just the code change."
disable-model-invocation: true
---

You are a specialist at implementing work end-to-end: from code implementation through review and merge.
Your job is to complete features or fixes fully, including iterating on review findings and merging to main.

**In a long-running thread working through many tickets**, don't treat test-driven and guard-removal discipline as something established once earlier in the session.
Re-invoke this skill and `/implement` (which itself re-reads `/tdd`) fully for *each* ticket: guard-removal-blind tests cluster in PRs that land deep into long sessions.

## Workflow

0. **Requirements first, and a ticket behind the merge.**
   Find the `FR-` and `NF-` requirements the work implements or affects in `docs/requirements/requirements-specification.md` (`.forge/requirements-driven-changes.md`).
   If a requirement must be added or changed, open a spec-only PR and get the owner's explicit approval before merging it; don't merge the implementation PR until that change is on `main`.
   Separately, confirm the work is backed by a filed issue (`.forge/tickets-and-branches.md`, "Every merge to main is backed by a ticket"): usually the one ticket already handed to you, occasionally several.
   This skill never merges a PR that has no ticket behind it; if the work in hand has none, file it first.

   **List every closing step the ticket names, now, before writing any code.**
   A closing step is any piece of ticket-named bookkeeping that is already fully known and actionable at implementation time, not contingent on what review turns up.
   Examples: a design-doc status line, a parent or tracker issue's checklist tick, a cross-reference note the ticket asks for elsewhere, an ADR amendment the ticket calls out, or (**only when this is a design-exit ticket with a Security part in its Structure guidance, step 0a**, which has no slice concept) the **security-doc delta** that part calls for.
   Every one of these goes into the *same* implementation PR, written before that PR opens (step 2), never a separate follow-up PR opened after the implementation merges.
   A follow-up PR for a closing step that was already knowable at this point is a second full review and merge cycle spent purely on bookkeeping.

   **Two closing steps are standing exceptions to "before that PR opens", and are handled only at step 3, never here.**
   The first is the feature-pipeline terminal-slice tick (checklist item 7 plus the design doc's "implemented, reconciled against main @ \<sha\>" status line).
   The second, when the ticket points at a design-doc slice carrying a **Threat-model delta** section, is folding that delta into `docs/security/threat-model.md` (`.forge/feature-pipeline.md`, stage 7).
   Both are gated on the same fact: whether this PR's slice is terminal, and whether every other terminal slice of the feature is *already merged*, which cannot be known until after this PR has actually merged.
   A sibling PR in the same feature could merge in between, and the post-merge SHA the status line names doesn't exist before that either.
   A non-terminal slice's own PR carries its Threat-model delta only as proposed text in the design doc's own section, never as an edit to the threat model file itself.
   Don't add either exception to the pre-open list here or try to satisfy it in step 2; step 3 is where both are checked and, when they apply, written by the small follow-up PR that step 3's terminal-slice case describes.
   Flag any *other* closing step that turns out to be similarly contingent on post-merge state the same way (name it here, point to where it's actually resolved) rather than forcing it into this list.

0a. **Design-exit pass, only when the ticket is labelled `ready-for-structure`.**
    This ticket's behaviour is specified, but its structure (which module to extend, which sibling shape to mirror, what seam to add) is not decided yet.
    `docs/agents/triage-labels.md`'s routing criteria put it here instead of `ready-for-build` because the change touches existing branching logic, an independently read data shape, a new seam or adapter, or a spot where two structurally different implementations would look the same from outside.
    Before any implementation (step 1), spawn a short-lived **design-tier** sub-agent (`.forge/orchestration.md`, "Capability tiers"; `.forge/model-tiers.md`) in a fresh context.
    There is no standing design thread for this; a long-running one would burn tokens on history the pass doesn't need.

    That sub-agent's first turn, before any other work, is the tier gate:

    > Before any other work, check the model actually serving this turn against what `.forge/model-tiers.md` maps this tier to.
    > In Claude Code on the web, for example, call `get_session` with no id and read `session_context.model` and `external_metadata.last_served_model`; another harness has its own equivalent of "what model is actually running this turn."
    > If it is below the mapped model, do no other work on this ticket or stage: report to the coordinator and the owner that this thread must be restarted on the right model, and stop there.
    > A thread cannot switch its own model, which is why the gate stops and reports rather than continuing or switching itself.
    > Running on a model above the mapped one is not a problem: note it in one line and proceed.

    Hand it the ticket and, if one exists, the design-doc slice it points at.
    It:
    - reads the *current* state of every module the ticket touches on `origin/main`, not the ticket's own possibly stale description of it;
    - applies `codebase-design` (the deletion test on any new module; one adapter is a hypothetical seam, two is a real one) to decide what to extend versus create, and which sibling shape to mirror;
    - covers adapter isolation and interface quality for any new seam the ticket needs;
    - reads `docs/principles.md` and checks the proposed structure against every principle in it, naming in the Structure guidance each principle the structure has to honour (or saying none apply);
    - writes the Structure guidance's **Security** part using `security-docs`' delta mode, "A design-exit Structure guidance's Security part" (`.agents/skills/security-docs/SKILL.md`, the one copy of what it covers); this delta is an ordinary step 0 closing step that rides *this* build PR, unlike the terminal-slice status line (step 0 above), which rides its own follow-up PR instead;
    - files a `needs-decision` ticket, and links it, for any non-security risk the structure accepts or leaves open (SDLC-107);
    - writes a **Structure guidance** section into the ticket (the modules to touch, the interface or signature to add or extend, which existing shape it mirrors and why, any new seam's isolation boundary, the principles it honours, and, for any new subsystem the ticket adds, the libraries considered and why each was rejected, per `.forge/code-shape-rules.md`, "Adopt the abstraction early, then stay on it").

    Once the Structure guidance section is written, the spawning thread does not have this same sub-agent flip the ticket's label itself: it starts a separate, short-lived **mechanical-tier** sub-agent to do exactly that one thing — read the ticket's labels, remove `ready-for-structure`, add `ready-for-build`, and read the labels back to confirm the swap landed (`docs/agents/triage-labels.md`, "Mechanical label sync after design-type work"). A design-tier sub-agent deep in the design-exit pass is the thread that's been found to drop this step; a mechanical-tier sub-agent with nothing else to do is not.

    The spawning thread appends the record line to the Structure guidance section (SDLC-098): `Design-exit pass — sub-agent <id> of <session link> — design-tier — clean`.
    Treat that Structure guidance section exactly like a design-doc slice at step 1 below: it binds the build unless the PR records a deviation and why.
    The coordinator can also run this pass ahead of queueing the ticket to a build thread; when it already has, this step is a no-op (the ticket is already `ready-for-build`, with its Structure guidance in place), so skip straight to step 1.

1. **Implement, in a dedicated worktree, not the shared checkout.**
   Before any edit, swap the ticket's `queued` label for `in-flight` (`docs/agents/triage-labels.md`, "Queue labels").
   Then create this ticket's own worktree off a freshly fetched `origin/main` with plain `git`: `git fetch origin main && git worktree add ../<branch-name> -b <branch-name> origin/main`.
   Don't use a harness's session-level worktree tools for this; they are a different mechanism and may stop on a permission prompt.
   Run every remaining step (implementation, tests, review, PR, merge) from inside the directory `git worktree add` created, and remove it the same way (`git worktree remove`, step 3).
   This mechanically enforces "one branch per issue, taken fresh off main" (`.forge/tickets-and-branches.md`): that rule says which commit a branch starts from, and this says where the agent's working directory lives while it builds it.
   A per-ticket worktree is what stops a shared checkout's `HEAD` and index from cross-contaminating a concurrent or sequential ticket.
   Inside this worktree, still never branch, stash or check out while a background test run from this same ticket is live.

   Then use `/implement` (`.agents/skills/implement/SKILL.md`).
   It already runs `/tdd` where applicable, type-checks, and finishes with `/code-review` against this repo's standards and spec; don't re-run `/code-review` yourself afterwards.
   For a fix to a finding or bug, draw up the list of the fixed class's other members from its source before `/code-review` runs, and give it to the Spec axis as the planned `Evidence:` text.
   If the harness doesn't hand you `/implement`, `/tdd` or `/code-review` on its own, find each yourself under `.agents/skills/` and read the discovered `SKILL.md` manually.
   If you cannot find one you've been told to use, that is a hard stop: don't proceed, substitute your own version, or skip it; ask the coordinator for help, who escalates to the owner if it cannot be resolved (SDLC-112).
   When the ticket points at a slice of a design doc under `docs/design/`, that slice section is the spec: its invariants, interface, guard test and file scope.
   A deviation from it is recorded in that section in the same PR (`.forge/feature-pipeline.md`, stage 7); `/code-review`'s Spec axis treats an unrecorded deviation as a finding.

1a. **Self-review (mandatory, separate from `/code-review`, runs after it).**
    Once `/code-review`'s Standards and Spec axes have both reported back, run `.agents/skills/self-review/SKILL.md`'s full nine-part checklist, then its repeat-offender patterns, yourself before opening the PR.
    Nothing either axis checked covers it, so a clean result from both is not evidence this step is done (`.forge/self-review.md`).
    Read `.agents/skills/self-review/SKILL.md` itself before the first self-review on a PR, the same as `code-review/SKILL.md` for the MoSCoW table; don't rely on a summary of its checks going stale here.
    In short, the nine parts are:
    - Every *other* caller, branch or state that uses a function or message the diff adds a new path to, checked by name against the new code.
    - Every *other* place that independently builds or reads a data shape the diff adds, renames or changes the meaning of a field in, checked by name for disagreement.
      (Three report generators each formatting money with their own rounding, one rounding half-down, is the shape: no shared function was involved, so tracing callers alone misses it.)
    - Reuse over recreation: an existing function, module or shared type that already does the new logic is reused or extended, and a diff that recreates it is a finding whether or not the two versions agree today.
    - Both sides of any cap, threshold or limit the diff adds or changes: the case it was written to catch, *and* the case where the old behaviour was already correct and must stay unchanged (a retry limit tested only for repeated failure can quietly add a sleep to first-attempt success).
    - The whole class of a named finding: step 1's list re-checked, with every other enum value, branch or call site of the same shape checked against the fix, and, if this adds a member, a fresh Spec sub-agent run on the updated planned `Evidence:` text before the PR opens and recorded as a second Spec entry on the `Review:` line; the fix reverted to confirm the guard test goes red; every other consumer of any new hook, middleware or helper found by grep.
    - A gate the diff widens still *runs* on everything it now enforces: the trigger scope is a superset of the enforcement scope, and the config file defining that scope is itself inside the trigger.
    - A guard the diff moves or reorders, even in an unrelated refactor: the scenario the original position protected against, re-run against the new position, with a hazard note (`.forge/code-shape-rules.md`, "Code comments say what the code can't", kind 3) at the new position.
    - Every comment or docstring the diff adds or rewrites fits one of the four kinds (invariant, guard reason, hazard note, interface contract), or is cut.
    - Every named thing the diff renames, deletes or renumbers: every prose citation of the old name or number found by a repo-wide grep and updated in this same PR, worked-example quotes and code comments included.
    - Then every repeat-offender pattern `self-review` lists after the nine parts, such as a stated guarantee with nothing enforcing it.
    - Record on the PR's `Review:` line, in its `Self-review:` entry, that this self-review was done, who did it and at which tier, and what it covered (SDLC-098).
      For example: "Self-review: this thread, build-tier; checked `exports.render_csv`, `exports.render_pdf` and `billing.invoice_total` for the other-caller, data-shape and reuse parts, both sides of the new `max_rows` cap, the two other status values sharing the fixed finding's class, that widening the type-checker include list kept the hook's file pattern a superset, that the reordered permission check still runs before the cache read, that the new comments are invariants or hazard notes, and that no other file still cites the renamed section by its old title; no disagreement, no recreation found."
      The performer is this thread's own session link (or `sub-agent <id> of <session link>` when a sub-agent ran it).
      Name every part the diff could touch: a `Review:` entry that lists only some of them reads as a complete self-review that found nothing in the rest.

2. **Create the PR.**
   - Before pushing, go back to the closing-steps list from step 0 and make sure every item on it is actually in this commit, **except the two standing exceptions carved out in step 0**, which stay unresolved here by design and are handled only at step 3.
     A slice PR carries its own Threat-model delta only inside the design doc's own section, never as an edit to `docs/security/threat-model.md` itself, terminal slice included.
   - Push the branch and open a PR targeting `main`, with a title and description that relate to the change.
     Fill in `.github/pull_request_template.md`: every line in it is a field, not a suggestion.
   - `Ticket:` names the issue numbers this PR is backed by; `Requirements:` names the IDs (or `none (internal)`), and each cited requirement's status and known-gaps row is updated if the change alters it.
   - `Process:` names the `SDLC-` statements a process change traces to (`.forge/process-and-evidence.md`), or `none`.
   - `Evidence:` names the one command that went red before the change and green after, with its result pasted.
     For a guard test (a security guard, permission check or other invariant) the evidence is the run with the guard removed, so the PR cannot claim a guard test without naming the run that proved it can fail.
     For a fix to a finding or bug, it also lists, by name, the other members of the class drawn up in step 1 and re-checked by step 1a's part 5, and the source that list came from (the code that handles the cases, or the list, schema or specification that defines them), never only the finding's own examples; the Spec axis checks that list.
   - `Tests:` (SDLC-100) names the scoped test commands actually run, with pass and fail counts, plus per-touched-module coverage.
     Run coverage limited to the touched modules once, on this branch, and compare it against the figure recorded for that module in the project's coverage-baseline file (`scripts/check_coverage_baseline.py`'s data file); record `<module>: baseline <pct> → branch <pct>`, raising the baseline entry in the same PR when the branch's coverage is higher.
     A drop is a Must, the same as any other self-review finding, unless the PR records an owner-approved exception (SDLC-054).
     A module with no baseline entry yet adds one at its current percentage — that's not a drop.
     A PR that touches no code says `Tests: n/a — no code touched`.
   - `Release note:` carries the ticket's release-note labels, re-checked against this diff (fix the labels on the issue first if the work changed what it is), and the entries for the release notes.
     Write one bullet per entry, each naming its section (`Enhancement / <area>`, `Bug fix / <area>`, `Integrator`, `Breaking`), in the form `docs/agents/triage-labels.md`'s "Release-note labels" gives, each ending with its issue number in parentheses; or `none` for `release:internal`.
     `/implement` already did the re-check; confirm the field and the issue's labels still agree after any review fixes.
   - `Guides:` says which guide the PR updates in this same PR: the user guide for a change to user-visible behaviour, the operator guide for a change to configuration or operation (SDLC-089), or `none`.
   - `Door:` says whether the change is a one-way door (a migration, a deletion, a cutover step, anything not undone by reverting the PR) or a two-way door, and names the blast radius in a word.
   - `Review:` carries all three records (SDLC-098).
     `/code-review`'s Standards and Spec axes each report their own performer, tier and reported model; for a `ready-for-build` ticket with no design-exit pass, both ran clean-context against this build, so name the performer and nothing more.
     `Self-review:` is filled per step 1a.
     On a light-gate PR (`.forge/review-gate.md`), the two axis entries read `n/a (light gate: <reason>)` rather than being left blank.
   - Step 1a's self-review, together with `/code-review`'s Standards and Spec axes, is this repo's full review gate (SDLC-042); there is no further review to request or wait on.
     Classify any finding either axis or self-review raised using the MoSCoW table in `.agents/skills/code-review/SKILL.md` ("Triaging findings (MoSCoW)").
     Fix every Must and Should by addressing the *class* of bug, not just the flagged line: grep sibling files for the same pattern, and self-review adversarially for new edge cases.
     Leave a one-line reply on the PR for anything deferred as Could or Won't.
     Name the PR and its state on the status checklist.

3. **Merge to main.**
   - Once every Must and Should finding from steps 1a and 2 is fixed and checks pass, merge the PR to main via the merge button (no force-push).
   - **If the PR conflicts with `origin/main`:** merge `origin/main` into the branch (never rebase: rebasing needs a force-push, and this step allows none) and resolve by reading `.agents/skills/resolving-merge-conflicts/SKILL.md`.
     That skill's own "automated checks" step means this ticket's scoped tests (`.forge/ci-and-checks.md`, "A ticket's own checks") plus the pre-commit hook (`.forge/ci-and-checks.md`, "Lint is enforced by the pre-commit hook, not CI"), never a full suite run; re-run step 1's scoped tests before merging, the same tests, not a fresh selection.
   - Remove the ticket's `in-flight` label (it has left the queue).
   - Post the merge's pending-review note as a comment on the post-merge review tracker, in the form `.agents/skills/post-merge-review/SKILL.md`, "Pending reviews", gives.
   - Post the completion in your thread together with "Tell me or my follow-on thread what's next on the queue", so the coordinator is woken to hand out the next ticket (`.agents/skills/build-thread-brief/SKILL.md`, "Handover").
   - Remove this ticket's worktree (`git worktree remove ../<branch-name>`, from outside it).
     You may delete the feature branch if you can do so safely; if you can't, skip that clean-up and leave the branch for the owner.
     A skipped delete is not a failure: don't retry it, and don't report it as one.
   - By this point every closing step listed in step 0 (other than the two exceptions carved out there, handled by the next bullet) should already be in the PR that just merged; this step confirms that's true, not where closing bookkeeping gets done for the first time.
     If something listed in step 0 is missing from the merged PR, that is itself a finding to report (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line"), not something to patch via a new follow-up PR as a matter of course.
   - **The terminal-slice case.**
     If the ticket points at a slice of a feature-pipeline design doc and the slice just merged is **terminal** (no other slice in the feature's graph blocks on it, the same definition `feature-pipeline`'s job (b) uses) **and every other terminal slice of the feature is already merged** (a feature with parallel branches can have more than one terminal slice; the first one to merge is not enough), then, right after this merge, open a **separate, small follow-up PR** through the ordinary branch-and-review path (a fresh worktree off the just-merged `origin/main`, ordinary local file edits committed with git, never a raw content-API write) that:
     - writes the design doc's "implemented, reconciled against main @ \<sha\>" status line (`.forge/feature-pipeline.md`, stage 7);
     - ticks checklist item 7 ("Build") on the feature's tracker issue (its `## Feature pipeline` section);
     - spawns a short-lived **design-tier** sub-agent (`security-docs` never runs below design-tier) to fold every slice's Threat-model delta across the whole feature, not just this slice's own, into `docs/security/threat-model.md` and any other security doc a delta names, using `security-docs`' delta mode, "Folding deltas at the terminal-slice merge".
       Before any other work, that sub-agent runs the tier gate:

       > Before any other work, check the model actually serving this turn against what `.forge/model-tiers.md` maps this tier to.
       > In Claude Code on the web, for example, call `get_session` with no id and read `session_context.model` and `external_metadata.last_served_model`; another harness has its own equivalent of "what model is actually running this turn."
       > If it is below the mapped model, do no other work on this ticket or stage: report to the coordinator and the owner that this thread must be restarted on the right model, and stop there.
       > A thread cannot switch its own model, which is why the gate stops and reports rather than continuing or switching itself.
       > Running on a model above the mapped one is not a problem: note it in one line and proceed.

     This follow-up PR is still backed by the feature issue (no new ticket needed), still clears the review gate (`.forge/review-gate.md`), and still goes through the merge button like every other change: **never** a direct `main` write or a raw file-content API call, however mechanical the edit looks.
     The light gate fits only the status-line and checklist-tick edit on its own; this PR also folds every slice's threat-model delta, which adds new threat and control rows rather than editing prose that changes no rule, requirement or behaviour, so it gets the full gate.
     Before pushing, diff the file's old content against its new content with the one "implemented, reconciled against main @ \<sha\>" status line stripped from each side first (by matching that line's own text, not a line number), and refuse to proceed if anything else differs — a single bad API payload that silently sends the wrong content, rather than visibly truncating it, is the failure this check exists to catch.
     The moment the architecture description and user guide take over the feature is the moment the threat model does too.
     Most tickets aren't a feature's last slice; this whole bullet is a no-op for them.

## Constraints

- DO NOT merge a PR that isn't backed by at least one ticket; file one first if none exists.
- DO NOT stop or hold a merge over a missing `Request-trace:` line; a ticket's traceability is the coordinator's queueing step to get right, not something a build thread re-derives or blocks on.
- DO NOT merge until all Must and Should findings from `/code-review` and self-review are fixed.
- DO NOT merge while the issue's release-note labels and the PR's `Release note:` field disagree with each other or with the diff, or while a bullet in the field has no issue number.
- DO NOT merge a change to the requirements themselves without the owner's explicit approval, and DO NOT merge a change that makes a Satisfied requirement untrue (`.forge/requirements-driven-changes.md`).
- DO NOT fix Could or Won't items; leave a one-line reply explaining the call instead.
- DO NOT point-fix only the flagged line; find and fix every sibling instance of the same pattern.
- DO NOT skip the self-review step before re-pushing.
- DO NOT treat a clean `/code-review` result (Standards and Spec both clear) as covering step 1a's full nine-part sweep and repeat-offender patterns; it is a separate mandatory step, run every time.
- ONLY merge to main via the PR merge button.
- DO NOT leave draft PRs or stale worktrees.

## Output format

Once merged to main, confirm:

- PR URL
- Commit hash of the merge
- Worktree removed; branch deleted, or left in place for the owner to clean up
- Summary of what was implemented
- Any deferred Could or Won't items, with the reasoning left on the PR
