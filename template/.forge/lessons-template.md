# Lessons: purpose and shape

A project's lessons are the mistakes it has paid for and the rule each produced, kept in two places that point at each other:

- a one-line rule under the project's own lessons heading in `CLAUDE.md`, loaded on every turn, so kept short;
- a section of the same name in `docs/agents/lessons.md` with the history and a worked example, read only when the rule applies, so the rule can be checked, sharpened or retired later.

Every one-liner has a matching section, and every section a one-liner.

## Shape of an entry

The one-liner is the rule in one sentence, bolded name first, with no history.
The section has a heading matching that name, a dated worked example of the failure, the rule it produced, and where it is enforced (a guard, a checklist item, or review only).
A lesson that proves to be an instance of a wider pattern is generalised, keeping its worked example as evidence.

## The seed

`docs/agents/lessons.md` is created once, at generation, with three generic lessons, then grows with the project's own incidents; it is project-owned and `copier update` never touches it.
The seed lessons:

- **Concurrent sessions in one checkout**: give each agent session its own `git worktree` (`scripts/worktree_setup.py` makes this one call); a shared `HEAD` and index silently cross-contaminate two sessions' work.
- **Off-the-shelf first**: before hand-rolling more than about 20 lines of generic infrastructure (process lifecycle, locking, retries, caching, validation, auth), find the library.
- **Don't switch branches under a running test run**: no branch switch, stash or checkout in a worktree while a background test run is still executing there, because a module collected after the switch can fail spuriously.

## When to add a lesson

Add one when a mistake cost real rework, is likely to recur, and no existing rule or checklist item covers it.
A pattern the post-merge review catches more than once usually belongs in the self-review checklist instead; a lesson is for what no checklist can mechanise.
