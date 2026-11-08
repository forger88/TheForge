# Main Health: operating patterns

The Main Health thread watches `main` so that no merged regression goes unnoticed for long.
Its procedure lives in `.agents/skills/watch-main-ci/SKILL.md`; this file states what it watches, how often, and when it escalates.

## What it watches

- **The scheduled CI pass.** CI workflows run on manual dispatch only, to keep CI minutes down.
  The Main Health thread dispatches the full check pass on `main` on a fixed schedule (twice a day by default), and only when something has merged since the last pass.
- **A local full-suite stand-in.** Between dispatched passes, a regression on `main` has no CI signal, so the thread runs the full suite locally on its own schedule and records the result as a comment on the local full-suite evidence tracker, with a per-check commit status and an aggregate status posted too wherever the environment's token is allowed to write them (some sandboxed GitHub proxies refuse that write outright; the tracker comment is the record every environment can produce).
  This is a workaround for unaffordable CI minutes, not a destination: if CI becomes cheap enough to run more often, dispatch it more often and shrink the stand-in.
- **The post-merge review pass** (`.forge/post-merge-review.md`), which it orchestrates and delegates to review-tier sub-agents.
- **The queue sweep** (`.agents/skills/queue-sweep/SKILL.md`), a daily report-only check for work that fell between threads.

## A verified branch

A `green` branch tracks the newest commit a full pass has actually verified.
It moves only forward, by an ordinary non-force push, after a clean pass.
Anyone who needs a correctness-verified point to pin to, rather than the tip of `main` during a red period, uses `green`, and a release tags `green` by default.

## Escalation

- A red `main` is reported on the PR that caused it, with the failing check, the actual error, and whether the failure is inside that PR's own diff.
- The report is also surfaced directly to whoever is watching the thread, because a broken `main` outranks most background work.
- The thread never pushes to `main` directly; a fix it is confident in goes through a small PR, and otherwise the report is the deliverable.
- A failure that looks infrastructural (a run that billed nothing and produced no logs) gets one re-run, and no more.
- A timeout is a failure to profile, not a limit to raise; raising a timeout needs the owner's explicit sign-off each time.
- A dependency-audit failure is a finding, not a flake: it gets a version-bump ticket or a reasoned, tracked exception, never a re-run.
- Before investigating a failure, the thread builds one local command that goes red on it (`.forge/bug-fixing.md`).

## Patterns worth recording

The thread keeps a project-owned, append-only notes file of patterns that recur across rotations (a class of bug the post-merge review keeps catching, a flake that turns out to be real, a gate whose trigger is narrower than what it enforces).
A one-off finding belongs in a run's archive comment instead.
When a note leads to a stronger self-review check, file the ticket and link it from the note.

Three patterns recur in most projects and are worth knowing from the start.
Review sub-agents and a local full-suite run must never share a worktree, because one agent's guard-removal probe or checkout can corrupt another's run.
A guard test that cannot fail tends to appear late in long build sessions, which is why build threads re-read the test-driven development skill's guard-removal section at the start of every ticket.
A fresh sandbox usually lacks the project's pinned document-build tools, so the document-consistency and render checks fail there for an environmental reason, not a regression.
The thread installs the pinned versions once, into a user-owned directory, with checksum verification, before treating such a failure as a finding.

## Rotation

The Main Health thread is long-running, because its environment is the most expensive to rebuild, and rotates at a pass boundary rather than on a fixed count.
Its handover note carries only mutable state (heads, watermark, schedule ids, known failures); any procedure note or lesson lands in the repo before the handover is written.
