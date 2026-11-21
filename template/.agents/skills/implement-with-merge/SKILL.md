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

   **List every closing step the ticket names, now, before writing any code**: ticket-named bookkeeping already fully known and actionable at implementation time, not contingent on what review turns up, such as a design-doc status line, a parent or tracker issue's checklist tick, a cross-reference note, an ADR amendment, or (**only for a design-exit ticket with a Security part in its Structure guidance, step 0a**) the **security-doc delta** that part calls for.
   Each goes into the *same* implementation PR, written before it opens (step 2), never a follow-up PR after the merge, which would spend a second review and merge cycle on bookkeeping.

   **Two closing steps are standing exceptions, handled only at step 3, not here or in step 2**: the feature-pipeline terminal-slice tick (checklist item 7 plus the design doc's "implemented, reconciled against main @ \<sha\>" status line), and, for a design-doc slice with a **Threat-model delta** section, folding that delta into `docs/security/threat-model.md` (`.forge/feature-pipeline.md`, stage 7).
   Both depend on whether this slice is terminal and every other terminal slice is *already merged*, which is unknowable until this PR merges (a sibling could merge in between, and the post-merge SHA doesn't exist yet).
   A slice's own PR carries its Threat-model delta only as proposed text in the design doc's section, never as an edit to the threat model file.
   Flag any *other* closing step contingent on post-merge state the same way (name it here, and point to where it is resolved) rather than forcing it into this list.

0a. **Design-exit pass, only when the ticket is labelled `ready-for-structure`.**
    The ticket's behaviour is specified but its structure (which module to extend, which sibling shape to mirror, what seam to add) is not: `docs/agents/triage-labels.md`'s routing criteria send here a change touching existing branching logic, an independently read data shape, a new seam or adapter, or a spot where two structurally different implementations would look the same from outside.
    Before any implementation (step 1), spawn a short-lived **design-tier** sub-agent (`.forge/orchestration.md`, "Capability tiers"; `.forge/model-tiers.md`) in a fresh context, not a standing design thread, which would burn tokens on history the pass doesn't need.

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

    Once the Structure guidance is written, the spawning thread starts a separate, short-lived **mechanical-tier** sub-agent, not the design-tier one (which tends to drop it), to do only the label flip: read the ticket's labels, remove `ready-for-structure`, add `ready-for-build`, and read them back to confirm (`docs/agents/triage-labels.md`, "Mechanical label sync after design-type work").

    The spawning thread appends the record line to the Structure guidance section (SDLC-098): `Design-exit pass — sub-agent <id> of <session link> — design-tier — clean`.
    Treat that Structure guidance section exactly like a design-doc slice at step 1 below: it binds the build unless the PR records a deviation and why.
    When the coordinator already ran this pass before queueing (the ticket is `ready-for-build` with its Structure guidance in place), skip to step 1.

1. **Implement, in a dedicated worktree, not the shared checkout.**
   Before any edit, swap the ticket's `queued` label for `in-flight` (`docs/agents/triage-labels.md`, "Queue labels").
   Then create this ticket's own worktree off a freshly fetched `origin/main` with plain `git`: `git fetch origin main && git worktree add ../<branch-name> -b <branch-name> origin/main` (or the single call `python3 scripts/worktree_setup.py <branch-name>`, which does the same fetch-and-add idempotently and also symlinks the project's shared dependency directories, per `scripts/worktree_shared_paths.txt`).
   Don't use a harness's session-level worktree tools, a different mechanism that may stop on a permission prompt.
   Run every remaining step (implementation, tests, review, PR, merge) inside that directory, and remove it with `git worktree remove` (step 3).
   This enforces "one branch per issue, taken fresh off main" (`.forge/tickets-and-branches.md`) and stops a shared checkout's `HEAD` and index cross-contaminating another ticket; inside it, still never branch, stash or check out while a background test run from this ticket is live.

   Then use `/implement` (`.agents/skills/implement/SKILL.md`).
   It runs `/tdd` where applicable, type-checks, and finishes with `/code-review`; don't re-run `/code-review` afterwards.
   For a fix to a finding or bug, draw up the list of the fixed class's other members from its source before `/code-review` runs, and give it to the Spec axis as the planned `Evidence:` text.
   If the harness doesn't hand you `/implement`, `/tdd` or `/code-review`, read its `SKILL.md` under `.agents/skills/`; failing to find one is a hard stop: don't proceed, substitute your own version, or skip it; ask the coordinator, who escalates to the owner if needed (SDLC-112).
   If you have no sub-agent tool to start `/code-review`'s two axes, don't run them yourself: open the PR unmerged, hand them to the thread that started you, and leave step 1a's self-review until they have reported (`.forge/review-gate.md`, "A builder with no sub-agent tool asks its parent for the review"). The sub-agents that thread starts on your behalf stand in for your own; they clear the gate the same way, and no review by another thread beyond them is required before merge.
   When the ticket points at a slice of a design doc under `docs/design/`, that slice section is the spec: its invariants, interface, guard test and file scope.
   A deviation from it is recorded in that section in the same PR (`.forge/feature-pipeline.md`, stage 7); `/code-review`'s Spec axis treats an unrecorded deviation as a finding.

1a. **Self-review (mandatory, separate from `/code-review`, runs after it).**
    Once `/code-review`'s Standards and Spec axes have both reported back, run `.agents/skills/self-review/SKILL.md`'s full nine-part checklist, then its repeat-offender patterns, yourself before opening the PR.
    Neither axis covers it, so a clean result from both is no evidence this step is done (`.forge/self-review.md`).
    Read that skill itself before the first self-review on a PR, as you read `code-review/SKILL.md` for the MoSCoW table; its part 5 includes, when the fixed class gains a member, a fresh Spec sub-agent run on the updated planned `Evidence:` text before the PR opens, recorded as a second Spec entry on the `Review:` line.
    Record on the PR's `Review:` line, in its `Self-review:` entry, that this self-review was done, who did it and at which tier, and what it covered (SDLC-098).
    For example: "Self-review: this thread, build-tier; checked `exports.render_csv`, `exports.render_pdf` and `billing.invoice_total` for the other-caller, data-shape and reuse parts, both sides of the new `max_rows` cap, the two other status values sharing the fixed finding's class, that widening the type-checker include list kept the hook's file pattern a superset, that the reordered permission check still runs before the cache read, that the new comments are invariants or hazard notes, and that no other file still cites the renamed section by its old title; no disagreement, no recreation found."
    The performer is this thread's own session link (or `sub-agent <id> of <session link>` when a sub-agent ran it).
    Name every part the diff could touch: an entry listing only some reads as a complete self-review that found nothing in the rest.

2. **Create the PR.**
   - Before pushing, confirm every item on step 0's closing-steps list is in this commit, **except step 0's two standing exceptions**, left for step 3; a slice PR, terminal included, carries its Threat-model delta only in the design doc's section, never in `docs/security/threat-model.md`.
   - Push the branch and open a PR targeting `main`, with a title and description that relate to the change.
     Fill in `.github/pull_request_template.md`: every line in it is a field, not a suggestion.
   - `Ticket:` names the issue numbers this PR is backed by; `Requirements:` names the IDs (or `none (internal)`), and each cited requirement's status and known-gaps row is updated if the change alters it.
   - `Process:` names the `SDLC-` statements a process change traces to (`.forge/process-and-evidence.md`), or `none`.
   - `Evidence:` names the one command that went red before the change and green after, with its result pasted.
     For a guard test (a security guard, permission check or other invariant) the evidence is the run with the guard removed, so the PR cannot claim a guard test without naming the run that proved it can fail.
     For a fix to a finding or bug, it also lists, by name, the other members of the class drawn up in step 1 and re-checked by step 1a's part 5, and the source that list came from (the code that handles the cases, or the list, schema or specification that defines them), never only the finding's own examples; the Spec axis checks that list.
   - `Tests:` (SDLC-100) names the scoped test commands actually run, with pass and fail counts, plus per-touched-module coverage.
     Run coverage limited to the touched modules once, on this branch, against each module's figure in the coverage-baseline file (`scripts/check_coverage_baseline.py`'s data file), recording `<module>: baseline <pct> → branch <pct>` and raising the entry in the same PR when the branch is higher.
     A drop is a Must unless the PR records an owner-approved exception (SDLC-054); a module with no entry yet adds one at its current percentage, which is not a drop.
     A PR that touches no code says `Tests: n/a — no code touched`.
   - `Release note:` carries the ticket's release-note labels, re-checked against this diff (fix the labels on the issue first if the work changed what it is), and the entries for the release notes.
     Write one bullet per entry, each naming its section (`Enhancement / <area>`, `Bug fix / <area>`, `Integrator`, `Breaking`), in the form `docs/agents/triage-labels.md`'s "Release-note labels" gives, each ending with its issue number in parentheses; or `none` for `release:internal`.
     `/implement` already did the re-check; confirm the field and the issue's labels still agree after any review fixes.
   - `Guides:` says which guide the PR updates in this same PR: the user guide for a change to user-visible behaviour, the operator guide for a change to configuration or operation (SDLC-089), or `none`.
   - `Door:` says whether the change is a one-way door (a migration, a deletion, a cutover step, anything not undone by reverting the PR) or a two-way door, and names the blast radius in a word.
   - `Review:` carries all three records (SDLC-098).
     `/code-review`'s Standards and Spec axes each report their own performer, tier and reported model; for a `ready-for-build` ticket with no design-exit pass, both ran clean-context against this build, so name the performer and record its context as `clean-context`.
     An axis run on your behalf by the thread that started you is recorded the same way, under that reviewer's own performer: it stands in for a sub-agent you would otherwise have started yourself, not a review by another thread, so it satisfies the gate the same way; an axis still waiting for it reads `awaiting independent review, requested from <that thread>` and blocks the merge until replaced.
     `Self-review:` is filled per step 1a.
     On a light-gate PR (`.forge/review-gate.md`), the two axis entries read `n/a (light gate: <reason>)` rather than being left blank, and only when `scripts/check_review_gate.py`'s `is_light_gate_eligible` passes for every changed file: a disqualifying path (the requirements specification, the SDLC document, the principles, the threat model, `CLAUDE.md`, `CONTEXT.md`, `.forge/`, the skills, and the doc's own further list) is never light-gate eligible, whatever the edit inside it reads like.
   - `/code-review`'s Standards and Spec axes plus step 1a's self-review are this repo's full review gate (SDLC-042); there is no further review to request or wait on.
     Classify every finding with the MoSCoW table in `.agents/skills/code-review/SKILL.md` ("Triaging findings (MoSCoW)"), and fix every Must and Should across its whole *class*, not just the flagged line: grep sibling files for the pattern, and self-review adversarially for new edge cases.
     Leave a one-line reply on the PR for anything deferred as Could or Won't.
     Name the PR and its state on the status checklist.

3. **Merge to main.**
   - Once every Must and Should finding from steps 1a and 2 is fixed and checks pass, record the review on the PR before anyone clicks merge: the `Review:` line (or a PR comment, if you can't edit the body) names every performer, tier and context, as step 2 requires.
     When you merge a PR another thread or sub-agent built, including one you started, first re-read its current `Review:` line and run any gate step it does not record as done (`.forge/review-gate.md`, "A builder with no sub-agent tool asks its parent for the review"); this comes before the pre-merge check below, not instead of it.
   - **Immediately before merging**, run `scripts/check_review_gate_premerge.sh <PR_NUMBER>`: it fetches the PR's current body and its full changed-file list fresh from the paginated files-changed endpoint (never a truncated or cached list), runs them against `origin/main`'s own copy of `scripts/check_review_gate.py` (never the PR branch's copy, which a weakened check could have edited), and prints the head SHA to pin the merge to.
     A non-zero exit is a hard stop: fix the PR, or the gate choice, before merging.
   - Merge via the merge button (no force-push), pinned to the head SHA just checked (the merge tool's equivalent of `--match-head-commit`), so a push landing in between fails the merge instead of landing an ungraded head.
   - Nothing edits the merged commit (or a squash merge's host-written commit) afterward: it is the historical record, so get the `Review:` line and the gate check right before merging, not after.
   - **If the PR conflicts with `origin/main`:** merge `origin/main` into the branch (never rebase: rebasing needs a force-push, and this step allows none) and resolve by reading `.agents/skills/resolving-merge-conflicts/SKILL.md`.
     Its "automated checks" step means this ticket's scoped tests (`.forge/ci-and-checks.md`, "A ticket's own checks") plus the pre-commit hook (`.forge/ci-and-checks.md`, "Lint is enforced by the pre-commit hook, not CI"), never a full suite; re-run step 1's same scoped tests before merging.
   - Remove the ticket's `in-flight` label (it has left the queue).
   - Post the merge's pending-review note as a comment on the post-merge review tracker, in the form `.agents/skills/post-merge-review/SKILL.md`, "Pending reviews", gives.
   - Post the completion in your thread together with "Tell me or my follow-on thread what's next on the queue", so the coordinator is woken to hand out the next ticket (`.agents/skills/build-thread-brief/SKILL.md`, "Handover").
   - Remove this ticket's worktree (`git worktree remove ../<branch-name>`, from outside it).
     You may delete the feature branch if you can safely; otherwise leave it for the owner. A skipped delete is not a failure: don't retry it or report it as one.
   - Confirm every step 0 closing step (other than its two exceptions, next bullet) is in the merged PR; one missing is a finding to report (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line"), not something to patch by a follow-up PR as a matter of course.
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

     This follow-up PR is backed by the feature issue (no new ticket), clears the review gate (`.forge/review-gate.md`), and merges through the merge button: **never** a direct `main` write or a raw file-content API call, however mechanical the edit.
     It gets the full gate, because folding threat-model deltas adds threat and control rows, which the light gate does not cover.
     Before pushing, diff the design doc's old and new content with the "implemented, reconciled against main @ \<sha\>" line stripped from each side (matched by its text, not a line number), and refuse to proceed if anything else differs: this catches a bad payload that silently sends wrong content.
     From this point the architecture description, user guide and threat model carry the feature.
     For any ticket that isn't a feature's last terminal slice, this bullet is a no-op.

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
