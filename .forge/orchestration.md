# Agent orchestration and capability tiers

Instructions here are duplicated, pithily, into `coordinator-core.md` for agent harness that cannot load and handle this instructions file directly.
TheForge's coordinator-core ADR records why that file exists and the constraints that must survive every edit to it.
A change here updates `.forge/coordinator-core.md` in the same change.
TheForge's `lock` check fails until the core section citing this one is re-read and the lock refreshed.

## Roles

**The owner** decides what the project does and how it is built: product scope, requirement wording, the principles, the wording of the lifecycle document, what is parked, and when a release happens.
Agents propose; the owner decides, and the decision is recorded where the process says.

**The coordinator** is the agent session that talks with the owner, keeps the work queue, starts and briefs threads, hands out tickets and reports progress.
It arranges for work to be done; it does not build, design, ticket or review itself.
A session acting as coordinator reads `.forge/coordinator-core.md` and `.agents/skills/build-thread-brief/SKILL.md` in full before its first action, and again after a context compaction — the core's "Start-of-session self-check" is the authoritative procedure for this.
The harness's project-level instructions carry the coordinator-core snippet, which tells the coordinator to load that file, never a substitute for reading it.

**Threads** are agent sessions that each do one kind of work.
A build thread implements tickets, a design thread writes designs and runs architecture passes, the Main Health thread watches `main` and orchestrates the post-merge review, and short-lived threads run triage or interviews.
These are roles, not individuals, and the sessions that fill them are rotated regularly, because a long session's accumulated context costs tokens on every turn.
Every rule, lesson and procedure lives in the repo, so a fresh session in any role is briefed with the same instructions and loses nothing.

A harness with only one session can still run this process: the one session plays each role in turn, and says so when a step asks for a separate thread or sub-agent it cannot start.

## The coordinator-core snippet is not a source of rules

The coordinator's own rules are authoritative in `.forge/coordinator-core.md`; the coordinator skill holds only look-up procedures.
The harness's project-level instructions carry a short snippet that tells the coordinator to load that file; the snippet is not a source of rules (SDLC-113).
The core file is held in the repository, is checked against a size limit, ends with a codeword and carries a mid-file check word, both of which the coordinator confirms only from its own whole read so a truncated or unread copy is detected, and a mechanical check fails whenever a source rule it condenses changes without the core being re-reviewed in the same change (`.forge/coordinator-core.md`, "Start-of-session self-check").
A re-paste, or any other update of the project instructions, replaces only the sections the coordinator owns: the owner's own scope section and the coordinator-notes zone are carried through verbatim (SDLC-118; `.forge/coordinator-core.md`, "Project instructions").
`queue-sweep` check 7 audits the live project instructions against the repository's snippet.

## Capability tiers

Work is matched to the judgement it needs, not to a model name, so the rules work in any agent harness.
`.forge/model-tiers.md` maps each tier to a model.

- **design-tier**: design decisions, security reasoning, module-level contracts, and judging whether a seam across several merged slices is shallow.
  These are calls where a wrong answer is expensive and there is no cheap way to re-check it later.
  It covers high-level and detailed design, architecture passes, design-exit passes, and all three modes of the `security-docs` skill.
- **review-tier**: reviewing a batch of already-merged code for bugs a per-PR review structurally cannot see.
  It needs more judgement than building a slice and less than originating a design, and it covers the post-merge review's reviewer sub-agents.
- **build-tier**: executing a scoped, already-designed piece of work.
  It covers implementing one slice at a time with scoped tests, self-review and merge, plus triage, ticketing, coordination and the Main Health thread.
- **mechanical-tier**: tasks with one obviously correct answer and no design judgement, such as a rename, a sweep for a known pattern, or a lookup.
  It covers mechanical sub-tasks delegated out of a build-tier thread, and every read-only sweep or audit.

The tier belongs to the piece of work, not to the thread that orchestrates it.
A build-tier thread that needs design-tier or review-tier work done hands that work to a sub-agent at the right tier rather than doing it itself.
`.forge/feature-pipeline.md`, "Which capability tier runs which stage", maps each stage to its tier.

Design, build and independent review are kept in separate hands where the harness allows it.
The builder reviews its own work at merge, starting clean-context sub-agents for part of it; the post-merge review and the architecture pass are never run by the agent whose work they cover.
A builder that cannot start those sub-agents asks the thread that started it to start them on its behalf, and that thread never reviews the diff itself, nor merges a PR whose gate steps are not recorded on it (`.forge/review-gate.md`, "A builder with no sub-agent tool asks its parent for the review").

## Tier gate

Every skill or stage that needs design-tier or review-tier opens with this gate, worded once here and reused verbatim at each of those entry points, before any other work:

> Before any other work, check the model actually serving this turn against what `.forge/model-tiers.md` maps this tier to.
> In Claude Code on the web, for example, call `get_session` with no id and read `session_context.model` and `external_metadata.last_served_model`; another harness has its own equivalent of "what model is actually running this turn."
> If it is below the mapped model, do no other work on this ticket or stage: report to the coordinator and the owner that this thread must be restarted on the right model, and stop there.
> A thread cannot switch its own model, which is why the gate stops and reports rather than continuing or switching itself.
> Running on a model above the mapped one is not a problem: note it in one line and proceed.

A thread already confirmed on the right tier for the current session (for example, a design thread that has already cleared this gate once this session) does not re-run it for every stage in the same unbroken session; it re-runs at the start of a fresh thread or sub-agent.

## Scheduling defaults

- At most 3 concurrent build threads; the owner may raise or lower this temporarily.
  The limit counts build threads only — Main Health, design, grill, review-pass, sweep and research threads never consume a slot.
- A build thread blocked only on an external party it cannot resolve itself — the owner's decision, an unresolved `needs-decision`, or an unmerged dependency — releases its slot while it waits, so another thread can use it; this does not count against the limit.
  This exemption is narrow: waiting on its own CI run, a test run, or a review of its own PR is not this kind of block, and the thread keeps its slot while it waits on those.
  Releasing the slot never means going quiet: a blocked thread keeps answering the owner's and the coordinator's questions and doing whatever discovery or drafting the blocker needs — that conversation is not slotted work and never needs a slot.
  It does no further implementation on the ticket until the blocker clears.
  Once the blocker clears, the thread (or its follow-on) waits for a free slot like any other queued thread; it never preempts a thread already running.
  A freed slot is itself the trigger to fill it: in the same check that notices the release, hand it to the next queued ticket — don't wait for the thread to come back, or for the next 30-minute check, to notice an idle slot.
- One ticket at a time per thread, handed out by the coordinator; a thread never picks its own next ticket.
- After every completed build, the build thread posts its completion together with "Tell me or my follow-on thread what's next on the queue", so the coordinator is woken to hand out the next ticket.
- Bug fixes go ahead of feature work.
- The queue is held in the tracker, not in anyone's memory: accepted work is labelled `queued`, and a build thread swaps that for `in-flight` when it starts (`docs/agents/triage-labels.md`, "Queue labels").
- Low-risk mechanical work may run at mechanical-tier in one extra concurrent slot.
- Progress reports give times in the owner's timezone (UTC), labelled as such.

## Don't manually trigger CI runs

No agent manually triggers or re-runs a CI workflow unless the owner explicitly says to.
The Main Health thread's scheduled full pass, dispatched only when `main` has moved, and its single re-run of a failure that looks infrastructural, are the only standing exceptions (`.forge/ci-and-checks.md`).
