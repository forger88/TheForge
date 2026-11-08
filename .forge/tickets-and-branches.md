# Tickets and branches

## Every merge to main is backed by a ticket (Never)

Nothing merges to `main` unless a ticket backs it: usually one issue in the project's tracker, occasionally several when the work genuinely spans more than one.
File the ticket first, then do the work against it.
This holds for process, tooling and docs changes as much as for features and fixes.
It adds no gate beyond the existing ones; it only requires the ticket to exist before the PR merges, so a PR's `Ticket:` and `Requirements:` lines always have an issue to point at.

Every merge is also traceable to an owner request (SDLC-014): an evidence-based chain, each link completing "this change is necessary to complete …", that ends at something the owner actually asked for.
That end is a ticket the owner raised and marked ready, an owner direction to start or un-park work, or a standing owner policy such as fixing Must and Should review findings (SDLC-037).
A ticket alone is not a request.
A ticket records the request it serves on a `Request-trace:` line in its body, but only when both hold: the request isn't already evident from the ticket's own structure (a parent or blocking link, a label the owner set directly, a review pass's own provenance already stated in the ticket), and a real request actually exists to record — a parent ticket, a link to the owner's direction, or the standing policy's statement ID.
Don't write a placeholder or a best guess: when neither condition holds, the ticket has no owner request yet, and SDLC-014 already means it doesn't queue or start until one exists.
A ticket filed before this rule predates the field entirely; some of those did have an approved request that was simply never written down, so it's checked once, as a backfill audit, not treated as a standing licence for a ticket filed under this rule to go without one.
Design docs, ADRs and other docs need no citation of their own; their merge commit, PR and ticket carry the chain.

A closing step the ticket names (a design-doc status line, a tracker checklist tick, a cross-reference) is part of that same PR, not a follow-up.
The one exception is a closing step that depends on post-merge state, such as the feature pipeline's terminal-slice tick, which is checked after the merge and written by a small follow-up PR, never a direct write to `main` (`.agents/skills/implement-with-merge/SKILL.md`, steps 0 and 3).

## A scope check-in before generalizing an instruction (Never)

Before a skill or instruction change turns one of the owner's specific, one-off instructions into standing, reusable wording — available to future tickets, not just the one it was given for — the thread asks the owner directly: "do you want this process change folded into the repository's instruction set?" (or words to that effect), and waits for a plain yes or no.
This is not a wording-approval request — the owner is confirming scope, not sign-off on exact text — and is additional to, not a substitute for, "What needs the owner's approval before a merge" (`.forge/process-and-evidence.md`).
SDLC-014 states this directly: a change that generalizes a specific instance into a standing rule or capability goes beyond what the request supports unless the request itself asked for that generalization, and needs its own request before it merges.
A ticket's `Request-trace:` line can quote a genuine owner request and still miss this, because the request was for one instance, not the standing rule a PR wrote from it.
A thread unsure whether its change applies an already-standing rule, or generalizes a single instance into a new one, treats it as the latter and asks: the same conservative instinct behind triage-label routing's "on any doubt, route to `ready-for-structure`" (`docs/agents/triage-labels.md`).
The owner's answer is recorded as a comment on the ticket, in the owner's own words (`.forge/process-and-evidence.md`'s evidence table).

## A ticket request is capture only (Never)

When the owner asks for a ticket of any kind, everything agreed goes into the ticket: the problem, the owner's own words, decisions, and any drafted wording, including requirement wording the owner has approved.
Nothing is committed, pushed or opened as a PR for it until the owner confirms the work should start.
Approving wording during ticket capture approves the wording, not the change; the ticket quotes that approval so the later spec-only PR can cite it.
An explicit instruction to start ("go", "do it now", "open the PR") is the confirmation, and a ticket the coordinator hands out under the normal queueing flow counts as started.
If it is unclear whether the owner wants a ticket or the change itself, ask.

## Ask which state a requested ticket goes into (Never)

When the owner explicitly asks for a ticket and does not say which state it goes into (now, `hanging` or `future`), ask before creating it.
Do not create it first and correct it later, and do not infer the state from the wording.
This applies only where the owner is asking for the ticket.
Tickets an agentic process files (review findings, sweeps, pipeline stages) take their state from the process that files them.
`docs/agents/triage-labels.md`, "Parking labels", defines the states; `hanging` items sit under the hanging epic #342 and `future` items under the deferred-ideas epic #341.

## Choosing a path, and the soft path sanity check on entry (Default)

A ticket takes one of two paths.
The **direct path** is triage straight to `ready-for-build` or `ready-for-structure`, with no grilling and no pipeline.
The **feature pipeline** is `needs-grilling`, then `ready-for-feature-design`, then stages 3 to 8 (`.forge/feature-pipeline.md`).

**Choosing the path**: the owner's words choose it (`instructing-agents.md`'s phrases for each path).
If the owner doesn't say, the agent picks one and records `Path: direct|pipeline — <one-line reason>` in the ticket body.
The owner overrides with one of those phrases at any time; this is not a new question to the owner.

**Soft sanity check on entry to each path**: this is **not** an up-front routing criterion.
Staying on the current path is the default, and the check only *may* propose a move.

- **Entering the direct path** (triage's outcome step, or the coordinator accepting a direct request): if the ticket will obviously change multiple source files, or solves a use case with multiple steps or constraints, propose moving it to the feature pipeline.
- **Entering the pipeline** (`.agents/skills/feature-pipeline/SKILL.md` job (a), before stage 2's interview): if the ticket can obviously be met by a fairly localised change set with straightforward constraints, propose moving it to the direct path.
- A move happens **only if the owner agrees**. Ask once per ticket, as a decision card with a recommendation, and record the answer on the ticket (`Path check: <stayed|moved> <path> — owner, <date>`) so it isn't asked again. With no answer, the ticket stays on its current path.
- **Exempt** (they're already the output of a path): a slice ticket `to-tickets` files at stage 6, a findings ticket filed by a review pass or an architecture pass, and a Main Health ticket.

## Branch names

Name a branch after what the change does, never after the chat or session that produced it.
A session title tells a reviewer nothing and stops being findable once the session ends.
Good names look like `fix-invoice-rounding` or `add-export-retry`; a name like `claude/setup-skills-x7k2qp` is the shape the pre-commit branch check rejects.

An agent that cannot delete a branch safely after its PR merges may skip that cleanup and leave it for the owner.
A skipped delete is not a failure: do not retry it or report it as one.

## One branch per issue, taken fresh off main

When one session addresses a series of separate issues, each issue starts on its own fresh branch cut from the current head of `main`.
Never layer a new issue's commits onto the previous issue's branch or working tree, and never branch off another in-progress feature branch.
Before each new branch, run `git fetch origin main` and branch from `origin/main` (`git checkout -b <branch-name> origin/main`), not from a local `main` that fetch alone does not move.

Use the non-resetting `checkout -b`, never `-B`, which force-resets an existing branch of that name and silently discards its commits.
If the name already exists, let `-b` fail, then look at that branch before deciding whether to delete or reuse it.

Check `git status --short` is empty before checking out the new branch, and commit or stash (`git stash push -u`) anything it shows first.
`checkout -b` carries a dirty working tree into the new branch whenever the changed files do not conflict, so leftover edits silently ride into the next issue's diff.

The only exceptions are a small follow-up fix to a PR still open from the same session, or the owner explicitly asking for work to land on top of another in-progress branch.

Each ticket is built in its own `git worktree` by default, so concurrent or sequential tickets never share a `HEAD` or an index (`.agents/skills/implement-with-merge/SKILL.md`, step 1).

## Closing keywords

A PR that fully implements an issue says `Closes #<n>`; wording like "Implements" leaves the issue open.
Verify the issue's state after merge.

GitHub's closing-keyword scanner ignores quoting and prose.
Any of close, closes, closed, fix, fixes, fixed, resolve, resolves or resolved directly before an issue number, in the PR body or in any commit message that lands on `main`, closes that issue, and editing the PR afterwards fixes nothing.
The check is not limited to the standing trackers: it covers any issue number a PR body or commit message explicitly says the change does not close, since the scanner reads none of a leading "not", a quoted example or markdown bold as negation.
For example, a terminal-slice PR whose body explains that a feature epic stays open by saying "This PR does **not** close #<n>" still closes #<n> the moment it merges, because "close" sits directly before the number.
Rephrase to break the adjacency whenever a standing tracker's number, or any other issue a PR explicitly disclaims closing, sits near one of those words, even inside a quoted example.
A quote of another PR's or commit's text is not exempt from this: when the quoted text itself contains a keyword-adjacent issue reference, the quote must break that adjacency too, never reproduced verbatim with the live reference intact.
When the bad example being reproduced already contains a keyword-adjacent reference, break the adjacency in the quote too, the same way a fresh worked example does, for instance the `#<n>` placeholder style used above.
The standing trackers are the post-merge review tracker #60, the deferred-ideas epic #341, the hanging epic #342, the architecture-findings epic #343 and the local full-suite evidence tracker #344.

## Close epics the moment their sub-issues do

An epic has no closing PR, so whenever a sub-issue closure brings an epic to 100% complete, close the epic in that same pass.
Never close a standing tracker this way: the five trackers above are never closed this way, whether what accumulates on a given one is sub-issues or run comments.
A feature's own tracker closes only after the extra checks in `.forge/feature-pipeline.md`, "Closing the tracker".
