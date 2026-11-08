# Lessons: purpose and shape

A project's lessons are the mistakes it has paid for, and the rule each one produced.
They live in two places that point at each other:

- a one-line rule in the agent instructions, under the project's own "Lessons" heading in `CLAUDE.md`, loaded on every turn;
- a section of the same name in `docs/agents/lessons.md`, holding the history and a worked example, read only when the rule applies to the change in hand.

The one-liner is short because it costs context on every turn.
The section is where the evidence lives, so the rule can be checked, sharpened or retired later.
Every one-line lesson has a matching section, and every section has a one-liner.

## Shape of an entry

The one-liner states the rule in a sentence, bolded name first, with no history.
The section in `docs/agents/lessons.md` has a heading matching the one-liner's name, a dated worked example of the failure, the rule it produced, and where the rule is enforced (a guard, a checklist item, or review only).
A lesson that turns out to be an instance of a wider pattern is generalised, and its worked example kept as evidence.

## The seed

`docs/agents/lessons.md` is created once, at generation, with three generic seed lessons, and is project-owned from then on.
It grows with the project's own incidents; `copier update` never touches it.
The seed lessons are generic enough to state directly:

- **Concurrent sessions in one checkout**: give each agent session its own `git worktree`; a shared `HEAD` and index silently cross-contaminate two sessions' work.
- **Off-the-shelf first**: before hand-rolling more than about 20 lines of generic infrastructure (process lifecycle, locking, retries, caching, validation, auth), find the library.
- **Don't switch branches under a running test run**: no branch switch, stash or checkout in a worktree while a background test run is still executing there, because a module collected after the switch can fail spuriously.

## When to add a lesson

Add a lesson when a mistake cost real rework and is likely to recur, and when no existing rule or checklist item already covers it.
A pattern the post-merge review catches more than once usually belongs in the self-review checklist instead; a lesson is for what no checklist can mechanise.
