# Self-review is its own mandatory step (Never)

Every PR gets a self-review after `/code-review`'s Standards and Spec axes finish, checking what neither axis is scoped to: every other place in the codebase that already depends on what the diff touches.
It runs on every PR, after `/code-review` on the full gate and alone on the light gate (`.forge/review-gate.md`), and nothing relaxes it.
`implement-with-merge` runs it mechanically as its own step right after `/code-review` returns, and the PR's `Review:` line records who did it, at which tier, and what it covered.

The procedure, the reasoning behind each part and the triggered checklists live in `.agents/skills/self-review/SKILL.md`; read it before the first self-review on a PR, as with `.agents/skills/code-review/SKILL.md` for the MoSCoW table.

## Why it is separate

Standards and Spec compare a diff against a document (the repo's conventions, or the ticket and requirements), and both can come back clean while the diff breaks an existing path it never mentions.
Self-review asks a structurally different question: what else in the repo depends on what this diff touched?
`.forge/review-architecture-rationale.md` explains why the passes are not combined.

## The nine parts

1. **Other callers.** For every function or message type the diff adds a new branch or path to, list every other caller, branch or state already using it, and check each by name against the new code.
2. **Other builders of the same shape.** For every data shape the diff adds, renames or changes a field's meaning in, list every other place that independently builds or reads it, not just one shared function's call sites, and check each by name.
3. **Reuse over recreation.** Before writing new logic, reuse or extend whatever already does it, or most of it.
   A diff re-deriving what an existing function computes is a finding whether or not the two agree today.
4. **Both sides of a cap.** For a cap, threshold or limit the diff adds or changes, test the condition it catches and the case where the old behaviour was already correct and must stay unchanged.
5. **A fix covers its whole class.** For a fix to a named finding, list every other case of its class (other enum values, branches, call sites) and check each against the fix.
   Name each on the PR's `Evidence:` line with the list's source (the code that handles the cases, or the list, schema or specification defining them), not only the finding's own examples.
   On the full gate the builder drew this list up before the code review; re-check it here, and if this adds a member, run a fresh Spec sub-agent on the updated planned `Evidence:` text before the PR opens, recorded as a second Spec entry on the `Review:` line.
   Revert the fix and confirm the guard test goes red.
   For a new hook, middleware or helper, grep for every other consumer that could reach it on a different path.
6. **A gate runs on what it enforces.** When the diff widens what a gate enforces (a hook's config, a lint or type-checker include list, a CI path filter, a guard's allowlist), the trigger scope stays a superset of the enforcement scope, and the file defining the enforcement scope is itself inside the trigger.
7. **A moved guard still protects.** When the diff moves or reorders a guard (a permission check, a validation, an early return, a lock, or any position-sensitive step), re-run the scenario its original position protected against at the new position, and add a hazard note there if none marks the ordering.
8. **Comments earn their place.** Every comment or docstring the diff adds or rewrites is one of the four kinds in `.forge/code-shape-rules.md`, "Code comments say what the code can't", or is cut.
9. **No stale prose citations.** For every named thing the diff renames, deletes or renumbers that other files cite in prose (a doc heading, a skill path, a step number, a section title), grep the whole repo for the old name or number and update every citation in this PR.

Treat the diff as a suspect, not innocent until proven otherwise: this is "fix the class of bug, not just the flagged line" (`.forge/review-gate.md`) run before the fact.

## Triggered checklists

The skill also carries seven checklists that run only when triggered:

- **Concurrency and lifecycle**, when the diff touches connections, pools, background tasks, sockets, locks, slots or claims, cached per-session state, or adds an await between a user's action and its effect.
- **Security delta**, when the ticket carries a design-exit Security part or the design-doc slice a threat-model delta.
- **Domain glossary**, when the diff names a domain concept `CONTEXT.md` would define.
- **Mutually-dependent file pairs**, when the diff touches one file of a pair the skill names, or one a project names in its own project-owned doc.
- **Scope generalization**, when the diff turns a one-off owner instruction into standing skill or instruction wording for future tickets.
- **Governed artefacts**, when the diff touches a path the artefact map lists, on the light gate, or on the full gate for a mapped file the Standards axis missed.
- **Sync-impact category**, before a diff is recorded `release:internal` or `Release note: none`.

## The checklist grows

A repeat offender the post-merge review notices is added to the skill's "Repeat-offender patterns" section, which runs on every PR after the nine parts, so the next PR is checked for it before merge (`.forge/post-merge-review.md`, "A repeat offender becomes a self-review pattern").
