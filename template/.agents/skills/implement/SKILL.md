---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/engineering/implement/SKILL.md @ 386d4ff719 (2026-07-08), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

Implement the work described by the user in the spec or tickets.

**Before starting, confirm there's a ticket.**
The "Every merge to main is backed by a ticket" rule (`.forge/tickets-and-branches.md`) means work that will result in a merge to `main` needs a filed issue first: usually the one already handed to you, occasionally several.
If none exists for the work in hand, file it before writing code, not as an afterthought once the PR is open.
If it has no `Request-trace:` line and no evident request, that's the coordinator's queueing step to fix, not yours: note it in the PR and carry on.

Use `/tdd` (`.agents/skills/tdd/SKILL.md`) where possible, at pre-agreed seams.
In a long-running session covering multiple tickets, re-read `/tdd` (at least its "Guard-removal verification" section) at the start of **each** ticket rather than relying on it having been read earlier in the thread.
Guard-removal-blind tests cluster in PRs that land deep into long sessions, never short or early ones: test discipline decays across a thread's own length, so it is renewed per ticket, not once.

Run type checking regularly, single test files regularly, and the full test suite once at the end.

Once done, use `/code-review` (`.agents/skills/code-review/SKILL.md`) to review the work.
For a fix to a finding or bug, first draw up the list of the fixed class's other members from its source, and give it to the Spec axis as the planned `Evidence:` text.
If the harness doesn't hand you `/tdd` or `/code-review` on its own, find each yourself under `.agents/skills/` and read the discovered `SKILL.md` manually to proceed.
If you cannot find one you've been told to use, that is a hard stop: don't proceed, substitute your own version, or skip it; ask the coordinator for help instead, who escalates to the owner if it cannot be resolved (SDLC-112).

Then re-check the ticket's release-note labels against what the diff actually does, since the work can turn out different from what the ticket intended.
Fix the labels on the issue if they are wrong (add or drop `breaking` too), and write the PR's `Release note:` field to match: one bullet per entry, several when the diff adds or fixes several things, each ending with its issue number (`docs/agents/triage-labels.md`, "Release-note labels").
A ticket with no release-note labels gets them now.
This is an acceptance criterion of every ticket, whether or not the ticket spells it out.

Commit your work to the current branch and open the PR; a human merges it, not you.
Once you see it merged, post the merge's pending post-merge-review note on the tracker, in the form `.agents/skills/post-merge-review/SKILL.md`, "Pending reviews", gives — the same note `implement-with-merge` posts for its own merges, since this skill ends at PR open rather than at merge.
