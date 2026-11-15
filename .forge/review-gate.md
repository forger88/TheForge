# The review gate is self-review (Never)

The merge gate is the builder's own review of the diff, proportionate to the change.
No review by another thread or a human is required before merge; the post-merge review is the independent second review (`.forge/post-merge-review.md`).

## Full gate and light gate

The **full gate** is the default.
It is `/code-review`'s two axes, **Standards** and **Spec**, each run by a clean-context sub-agent the builder starts and each reading the actual diff, followed by the mandatory self-review step (`.forge/self-review.md`).
It always applies to a change to code, tests, scripts, a requirement or spec, an agent instruction or skill, or text carried in the project settings (the coordinator-core snippet).

The **light gate** is the self-review step alone.
It applies only to a change that meets every one of these conditions: it is a prose-only doc edit, it changes no rule, requirement or behaviour, and it touches no text carried in the project settings (the coordinator-core snippet).
A change that does not clearly meet every light-gate condition, including one that seems to meet some conditions of each gate, gets the full gate.

`.agents/skills/build-thread-brief/SKILL.md`, "Review gate", is the one copy of this split, kept current there.

## An exemption must be quotable, or it does not exist

An exemption from Standards/Spec review or from the mandatory self-review step applies only if this exact file states it, in those words.
A thread that cannot quote the sentence granting an exemption does not have one, whatever tier, SDLC statement, or prior practice it cites instead.
This is a clarification of the rule above, not a new one: the full gate and the light gate are the only two paths through this gate, and nothing else shortcuts either axis.

## A mechanical check backs up the gate choice, never the other way round

`scripts/check_review_gate.py`, run by the always-on `review-gate-check` PR check, reads a PR's `Review:` field and its changed-file list and fails unless the field clears the gate those files actually require.
It recognizes exactly the full-gate and light-gate shapes above and no others: a `Review:` line citing some other exemption still fails unless it independently satisfies one of them, so an invented exemption fails closed instead of needing to be anticipated by name.
It also fails any Standards or Spec entry containing `builder's own` or `no sub-agent tool`, the wording below prescribes for an axis the builder reviewed itself, so that axis cannot clear the full gate; a real sub-agent's entry never uses either phrase, even to negate it.
It also fails a Standards or Spec entry, other than the light gate's `n/a`, that starts with `awaiting` or does not record `clean-context` (or `clean sub-agent`), so an axis still waiting for its reviewer, or reviewed only in chat, cannot clear the full gate.
It cannot tell whether a recorded review really ran; that is the merger's check below and the post-merge review's.
This exists because real self-merges have cited review-gate wording that didn't hold up — a drafting-time misjudgment about which gate applied or whether an exemption existed, not an ambiguous rule.
The check is a backstop on the builder's own gate choice above, not a redefinition of it: when the two disagree, this file's rule is what the check is implementing, and a check that disagrees with it is the bug.

## Skills are used, never substituted

If the harness does not hand you a skill named here, find it yourself under `.agents/skills/` and read its `SKILL.md`.
Never skip a gate step silently, and never merge a full-gate change on an inline read of the diff in place of the directed review skills.
Every skill the process directs to be used is used.
Failing to find a skill you were told to use is a hard stop: do not proceed, substitute your own version, or skip it; ask the coordinator, who escalates to the owner if it cannot be resolved.

## A clean-context review needs a sub-agent that really ran

A clean-context sub-agent is one actually started for that axis, by the builder or on its behalf by the thread that started it, with the harness's sub-agent tool (an Agent or Task tool, or its equivalent), or a fresh thread started for that axis alone.
A builder with no such tool cannot run the full gate's Standards and Spec axes itself, and that is a hard stop of the same kind as a missing skill: it says so on the PR and hands the axes to the thread that started it (next section), never reviewing the diff itself in their place.
A `Review:` entry never calls an axis clean-context, or names a sub-agent for it, unless one was actually started for that axis.
A review the builder did itself is recorded as the builder's own, for example `builder's own, no sub-agent tool available`, and a full-gate PR whose axes did not run in real sub-agents does not merge until a session that can start them runs them.

## A builder with no sub-agent tool asks its parent for the review

A builder's parent is the thread that started it: the build thread that dispatched it as a sub-agent, or the coordinator that started it as a thread.
A builder that cannot start a clean-context sub-agent for the Standards or Spec axis does not merge, and does not hand its PR on to be merged, until that axis has run.
It opens its PR unmerged, writes each axis it could not run on the `Review:` line as `awaiting independent review, requested from <its parent>`, and asks its parent, in its hand-back or a message, for an independent review of that axis, naming the PR, the ticket or design-doc slice that is its spec, and the planned `Evidence:` list.
The parent then starts one clean-context reviewer per axis, a fresh sub-agent or, where it has no sub-agent tool, a fresh one-off thread, each briefed with that axis's prompt from `.agents/skills/code-review/SKILL.md` and with no history of the build.
The parent never reviews the diff itself in a reviewer's place, and never merges, or lets anyone merge, before those reviews have run.
A parent that cannot start a reviewer asks its own parent in the same way; the coordinator, at the top of that chain, escalates to the owner.
Must and Should findings are fixed before merge, by the builder if it can still be reached, otherwise by the parent or a build-tier sub-agent it starts, and the mandatory self-review step then runs on the final diff, after the axes (`.forge/self-review.md`).
Each review is recorded on the PR's `Review:` line before merge, the normal way: its performer (`sub-agent <id> of <session link>`, or the review thread's link), its tier, `clean-context`, what it found and how each finding was addressed.
A review recorded only in chat, a progress post or the merge message does not count.
Whoever merges a PR built by another thread or sub-agent, a parent merging its builder's PR included, owns that PR's gate: before merging, it re-reads the PR's current `Review:` line, confirms Standards, Spec and self-review each record a review that actually ran, runs any step that is missing rather than merging past it, and runs `scripts/check_review_gate.py` on the PR's current body and changed-file list.
A thread that hands builds to sub-agents with no sub-agent tool of their own briefs each one to stop after its tests and hand back for review, rather than finding the gap at merge time.

## Triage findings by MoSCoW

Classify every finding Must, Should, Could or Won't, using the table in `.agents/skills/code-review/SKILL.md`, "Triaging findings (MoSCoW)".
Push fixes only for Must and Should; a Could or Won't gets a one-line reply on the PR explaining the call.
A Must about a guard or invariant is verified by showing its test goes red with the guard removed.
A deferred or out-of-scope gap gets an explicitly filed follow-up issue referenced in the PR body: a `needs-decision` ticket for the owner, or a `deferred-arch-finding` when it is weak, never a ticket queued for building on its own (SDLC-116).

The PR's description records what each axis and the self-review found and how each finding was addressed, and its `Review:` line records who performed each review and at which tier.

## Fix the class of bug, not just the flagged line

Any finding (a review comment, a self-review, a test failure) that is an instance of a pattern is fixed everywhere the pattern occurs.
Grep the whole relevant tree, test files included, before calling the fix done.
A PR that fixes a finding or bug lists the class's members from the authority that defines them (the code that handles the cases, or the list, schema or specification that defines them), not only from the finding's examples, and names each one checked on its `Evidence:` line with that source.
The builder draws the list up before the code review runs, so the Spec axis can check it; if self-review adds a member afterwards, a fresh Spec sub-agent checks the updated list before the PR opens.
Then re-read the fix, hunting for the same shape nearby and for the new edge case the fix itself introduces.

## Who merges

Whether a PR merges autonomously once it clears this gate depends on which skill was invoked: `implement` builds and reviews and leaves the merge to a human, while `implement-with-merge` builds, reviews and merges.
