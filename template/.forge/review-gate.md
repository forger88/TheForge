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
This exists because real self-merges have cited review-gate wording that didn't hold up — a drafting-time misjudgment about which gate applied or whether an exemption existed, not an ambiguous rule.
The check is a backstop on the builder's own gate choice above, not a redefinition of it: when the two disagree, this file's rule is what the check is implementing, and a check that disagrees with it is the bug.

## Skills are used, never substituted

If the harness does not hand you a skill named here, find it yourself under `.agents/skills/` and read its `SKILL.md`.
Never skip a gate step silently, and never merge a full-gate change on an inline read of the diff in place of the directed review skills.
Every skill the process directs to be used is used.
Failing to find a skill you were told to use is a hard stop: do not proceed, substitute your own version, or skip it; ask the coordinator, who escalates to the owner if it cannot be resolved.

## A clean-context review needs a sub-agent that really ran

A clean-context sub-agent is one the builder actually starts for that axis, with the harness's sub-agent tool (an Agent or Task tool, or its equivalent).
A thread with no such tool cannot run the full gate's Standards and Spec axes, and that is a hard stop of the same kind as a missing skill: say so on the PR or ticket and ask the coordinator, who escalates to the owner, rather than reviewing the diff yourself in their place.
A `Review:` entry never calls an axis clean-context, or names a sub-agent for it, unless one was actually started for that axis.
A review the builder did itself is recorded as the builder's own, for example `builder's own, no sub-agent tool available`, and a full-gate PR whose axes did not run in real sub-agents does not merge until a session that can start them runs them.

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
