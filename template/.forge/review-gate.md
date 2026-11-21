# The review gate is self-review (Never)

The merge gate is the builder's own review of the diff, proportionate to the change.
No review by another thread or a human is required before merge; the post-merge review is the independent second review (`.forge/post-merge-review.md`).
A sub-agent a parent thread starts on a builder's behalf, when the builder has no sub-agent tool of its own, stands in for the builder's own sub-agent and is not a review by another thread ("A builder with no sub-agent tool asks its parent for the review," below).

## Full gate and light gate

The **full gate**, the default, is `/code-review`'s **Standards** and **Spec** axes, each run by a clean-context sub-agent the builder starts and each reading the actual diff, followed by the mandatory self-review step (`.forge/self-review.md`).
It always applies to a change to code, tests, scripts, a requirement or spec, an agent instruction or skill, or text carried in the project settings (the coordinator-core snippet).
This always includes any edit to the requirements specification file, status lines and summaries included.
That file needing no owner approval for a non-wording edit (`.forge/requirements-driven-changes.md`) settles the approval question, never the review-gate question.

The **light gate** is the self-review step alone, only for a change meeting every one of these conditions: a prose-only doc edit, changing no rule, requirement or behaviour, and touching no text carried in the project settings (the coordinator-core snippet).
A change that does not clearly meet every light-gate condition, including one that seems to meet some conditions of each gate, gets the full gate.
A changed file that `scripts/check_review_gate.py`'s `is_light_gate_eligible` rejects is never a prose-only doc edit for this purpose, whatever the edit inside it reads like; `DISQUALIFYING_DOC_PATTERNS` in that script is the one list of which paths these are, never restated in prose here.
The gate is chosen by running that check against the PR's changed-file list, not by judging the edit's content.
A pattern in that list that looks wrong is fixed by its own full-gate PR to the list, never argued past when choosing the gate for an unrelated change.

`.agents/skills/build-thread-brief/SKILL.md`, "Review gate", is the one copy of this split, kept current there.

## An exemption must be quotable, or it does not exist

An exemption from Standards/Spec review or the mandatory self-review step applies only if this exact file states it, in those words; a thread that cannot quote the sentence granting one does not have it, whatever tier, SDLC statement or prior practice it cites.
The full and light gates are the only two paths, and nothing else shortcuts either axis.

## A mechanical check backs up the gate choice, never the other way round

`scripts/check_review_gate.py`, run by the always-on `review-gate-check` PR check, reads a PR's `Review:` field and changed-file list and fails unless the field clears the gate those files require.
It recognizes only the full-gate and light-gate shapes above, so a `Review:` line citing any other exemption fails unless it independently satisfies one of them, and an invented exemption fails closed without being anticipated by name.
It fails any Standards or Spec entry containing `builder's own` or `no sub-agent tool`, the wording below for an axis the builder reviewed itself, so that axis cannot clear the full gate; a real sub-agent's entry never uses either phrase, even to negate it.
It also fails a Standards or Spec entry, other than the light gate's `n/a`, that starts with `awaiting` or does not record `clean-context` (or `clean sub-agent`), so an axis still waiting for its reviewer, or reviewed only in chat, cannot clear the full gate.
It cannot tell whether a recorded review really ran; that is the merger's check below, and the post-merge review's.
It exists because real self-merges have cited review-gate wording that didn't hold up, from a drafting-time misjudgment about which gate applied or whether an exemption existed, not an ambiguous rule.
It backs up the builder's gate choice rather than redefining it: this file's rule is what the check implements, and a check *looser* than this rule is the bug.
Where the check is *stricter* than a builder's reading of this file, the full gate applies until a PR changes the check's own list (`A change that does not clearly meet every light-gate condition ... gets the full gate` above).
The merger runs `origin/main`'s own copy of this check against the PR's current body and full changed-file list before merging, per `implement-with-merge` step 3 — the authoritative text of that procedure.
`scripts/check_review_gate_premerge.sh [PR_NUMBER]` does that fetch-and-run once, fresh from GitHub, and prints the head SHA to pin the merge to; a merger who assembles the body and changed-file list by hand instead risks a truncated listing, such as a diff-based name list, silently dropping a disqualifying file.

## Skills are used, never substituted

If the harness does not hand you a skill named here, find it under `.agents/skills/` and read its `SKILL.md`.
Never skip a gate step silently, and never merge a full-gate change on an inline read of the diff in place of the directed review skills.
Every skill the process directs to be used is used.
Failing to find a skill you were told to use is a hard stop: do not proceed, substitute your own version, or skip it; ask the coordinator, who escalates to the owner if it cannot be resolved.

## A clean-context review needs a sub-agent that really ran

A clean-context sub-agent is one actually started for that axis, by the builder or on its behalf by the thread that started it, with the harness's sub-agent tool (an Agent or Task tool, or its equivalent), or a fresh thread started for that axis alone.
A builder with no such tool cannot run the full gate's Standards and Spec axes itself, a hard stop like a missing skill: it says so on the PR and hands the axes to the thread that started it (next section), never reviewing the diff itself in their place.
A `Review:` entry never calls an axis clean-context, or names a sub-agent for it, unless one was actually started for it.
A review the builder did itself is recorded as the builder's own (for example `builder's own, no sub-agent tool available`), and a full-gate PR whose axes did not run in real sub-agents does not merge until a session that can start them runs them.

## A builder with no sub-agent tool asks its parent for the review

A builder's parent is the thread that started it: the build thread that dispatched it as a sub-agent, or the coordinator that started it as a thread.
A builder that cannot start a clean-context sub-agent for an axis neither merges nor hands its PR on to be merged until that axis has run.
It opens its PR unmerged, writes each axis it could not run on the `Review:` line as `awaiting independent review, requested from <its parent>`, and asks its parent, in its hand-back or a message, for an independent review of that axis, naming the PR, the ticket or design-doc slice that is its spec, and the planned `Evidence:` list.
The parent starts one clean-context reviewer per axis (a fresh sub-agent, or where it has no sub-agent tool a fresh one-off thread), briefed with that axis's prompt from `.agents/skills/code-review/SKILL.md` and no history of the build.
The parent never reviews the diff itself in a reviewer's place, and never merges, or lets anyone merge, before those reviews have run.
A parent that cannot start a reviewer asks its own parent the same way; the coordinator, at the top, escalates to the owner.
These parent-started sub-agents stand in for the builder's own: they satisfy the merge gate the same way a builder's own clean-context sub-agents would, and no review by another thread beyond them is required before merge.
Must and Should findings are fixed before merge, by the builder if still reachable, otherwise by the parent or a build-tier sub-agent it starts, and the mandatory self-review then runs on the final diff, after the axes (`.forge/self-review.md`).
Each review is recorded on the PR's `Review:` line before merge: its performer (`sub-agent <id> of <session link>`, or the review thread's link), its tier, `clean-context`, what it found and how each finding was addressed.
A review recorded only in chat, a progress post or the merge message does not count.
Whoever merges a PR another thread or sub-agent built, a parent included, owns its gate: before merging, it re-reads the current `Review:` line, confirms Standards, Spec and self-review each record a review that actually ran, runs any missing step rather than merging past it, and runs `scripts/check_review_gate.py` on the PR's current body and changed-file list.
A thread handing builds to sub-agents with no sub-agent tool briefs each to stop after its tests and hand back for review, rather than finding the gap at merge time.

## Triage findings by MoSCoW

Classify every finding Must, Should, Could or Won't, using `.agents/skills/code-review/SKILL.md`, "Triaging findings (MoSCoW)".
Push fixes only for Must and Should; a Could or Won't gets a one-line reply on the PR explaining the call.
A Must about a guard or invariant is verified by showing its test goes red with the guard removed.
A deferred or out-of-scope gap gets an explicitly filed follow-up issue referenced in the PR body: a `needs-decision` ticket for the owner, or a `deferred-arch-finding` when weak, never a ticket queued for building on its own (SDLC-116).

The PR's description records what each axis and the self-review found and how each finding was addressed, and its `Review:` line who performed each review and at which tier.

## Fix the class of bug, not just the flagged line

Any finding (a review comment, a self-review, a test failure) that is an instance of a pattern is fixed everywhere the pattern occurs: grep the whole relevant tree, tests included, before calling the fix done.
A PR fixing a finding or bug lists the class's members from the authority that defines them (the code that handles the cases, or the list, schema or specification defining them), not only the finding's examples, and names each one checked on its `Evidence:` line with that source.
The builder draws the list up before the code review runs, so the Spec axis can check it; if self-review adds a member, a fresh Spec sub-agent checks the updated list before the PR opens.
Then re-read the fix, hunting for the same shape nearby and for the new edge case the fix itself introduces.

## Who merges

Whether a PR merges autonomously once it clears this gate depends on the skill invoked: `implement` builds and reviews and leaves the merge to a human, while `implement-with-merge` also merges.
