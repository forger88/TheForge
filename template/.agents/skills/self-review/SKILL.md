---
name: self-review
description: "Mandatory self-review step run after /code-review's Standards and Spec axes finish, on every PR in this repo. Checks what neither axis is scoped to: every other caller/builder of what the diff touches, reuse over recreation, both sides of any cap or threshold the diff introduces, whether a fix for a named finding covers the finding's whole class, whether a gate the diff widens still runs on everything it now enforces, whether a guard the diff moves still protects what its old position did, whether every comment the diff adds earns its place, whether a renamed/deleted/renumbered thing still has stale prose citations elsewhere, and the repeat-offender patterns the post-merge review has added (such as a stated guarantee with nothing enforcing it, or a predictable path under a shared writable directory)."
disable-model-invocation: true
---

# Self-review: every other caller or builder, reuse over recreation, both sides of a new cap, a fix's whole class, a gate that runs on what it enforces, a guard that still protects what moved past it, a comment that earns its place, and no stale prose citation of a renamed thing

**This is its own mandatory step, run after `/code-review`'s Standards and Spec axes finish, not a restatement of anything they already check.**
Nothing in `/code-review`'s own instructions (the Standards axis's conventions and smell-baseline check, or the Spec axis's acceptance-criteria check) narrows, satisfies or substitutes for this step.
Both axes can come back clean and this step still finds a break, because it checks something neither axis is scoped to look at: every *other* place in the codebase that already depends on what this diff touches.
Skipping it because `/code-review` "already looked" is the exact gap this rule exists to close.
It runs on every PR, with nothing that relaxes it.
`implement-with-merge` runs it mechanically as its own step right after `/code-review` returns; a PR's `Review:` line records who did it, at which tier, and what it covered.
For why this stays its own pass instead of folding into Standards and Spec, see `.forge/review-architecture-rationale.md`.

**Its checklist grows.** When the post-merge review (`post-merge-review`) notices a repeat offender, that pattern is added to the checklist below, so the next PR is checked for it before merge.

## The shapes this step exists to catch

A per-PR review reliably checks a diff against its own ticket, and just as reliably misses the bug a later review catches: a new path that collides with an existing one the diff never mentions.
Each part below targets one recurring shape:

- **A new path that breaks an existing one.** A new export option is added to a report screen, and an older bulk-export path that shares the same formatter silently starts producing the new layout for callers that never asked for it.
  Neither a style violation nor a missed acceptance criterion; an existing path the new code didn't know it had to keep working.
- **Another builder of the same data shape.** Three report generators each format a money amount with their own rounding code instead of calling the one formatter that already exists, and one rounds half-down.
  No shared function was called with a missed branch, so tracing callers would never find it; "caller" alone does not cover this shape.
- **The untested side of a cap.** A retry limit gets a test for the case where every attempt fails, and nothing tests the success-on-first-attempt case, which the change quietly made sleep before returning.
- **A fix that matches the finding's wording, not its class.** A review flags one enum value a validation function mishandles; the fix patches that value and leaves a sibling value with the identical bug.
  A guard test can hide this too, if it passes whether or not the fix is present.
- **A gate narrower than what it enforces.** A type checker's include list grows to cover new directories while the pre-commit hook that runs it still only triggers on the old ones, so new type errors land on `main` and fail someone else's unrelated commit.
  The change that widened the scope is the one least likely to be checked against it, because the config file itself is outside the trigger.
- **A guard moved with no finding naming it.** An incidental refactor moves a cache lookup ahead of the permission check that used to guard it, and nothing re-tests the scenario the check protected, because no finding asked for it.
- **A stale prose citation.** A doc heading, a skill path, a step number or a section title is renamed, deleted or renumbered, and other files still cite the old one; nothing mechanical catches it.

Parts 1-5 look at the code a diff changes; part 6 looks at whether the checks meant to catch that diff can run on it at all.
Part 7 re-tests a guard a diff moved without a finding asking it to; part 8 holds the diff's own comments to the comment rule; part 9 re-greps every prose citation of a thing the diff renamed, deleted or renumbered.

## The nine parts

Before calling a self-review done, run all nine parts, then every repeat-offender pattern below them:

1. For every function or message type the diff adds a new branch or path to: list every *other* caller, branch or state that already uses that same function or renders that same message, and check each one by name against the new code.
2. For every data shape the diff adds, renames, or changes the meaning of a field in (a dict's keys, a database row, an API response body, a message payload): list every *other* place in the codebase that independently builds or reads that same shape, not just call sites of one shared function, and check each one by name for whether it now disagrees with the diff.
3. Before writing new logic, check whether something already in the codebase does it (or most of it) and reuse or extend that instead of writing a parallel version.
   Re-deriving logic an existing module already has is how two versions come to disagree; calling the existing one makes disagreement impossible.
   A diff that writes new code for something an existing function, module or shared type already does is itself a finding, whether or not the two versions happen to agree today.
4. When the diff adds or changes a cap, threshold or limit (a budget, a rate, a size check, a timeout, a retry count): test both sides of it, the condition it was written to catch *and* the case where the old behaviour was already correct and must stay unchanged.
   A guard test for the triggering case alone is not proof the new logic is a no-op everywhere else.
5. When the diff fixes a named finding: list every other case of the same class (other enum values, branches, call sites; grep for the pattern) and check each against the fix.
   Name each one on the PR's `Evidence:` line, with the source the list came from (the code that handles the cases, or the list, schema or specification that defines them), not only the finding's own examples.
   On the full gate the builder drew this list up before the code review ran; re-check it here, and if this adds a member, run a fresh Spec sub-agent on the updated planned `Evidence:` text before the PR opens and record it as a second Spec entry on the `Review:` line.
   Revert the fix and confirm the guard test goes red.
   For a new hook, middleware or helper the fix introduces, grep for every other consumer that could reach it on a different path.
6. When the diff widens what a gate enforces (a pre-commit hook's config, a lint or type-checker include list, a CI job's path filter, a guard test's allowlist) or adds a file to the set a gate covers: check that the gate still *runs* on everything it now enforces.
   The trigger scope must be a superset of the enforcement scope, and the config file that defines the enforcement scope must itself be inside the trigger scope.
   A gate that cannot run on the file it would fail on is not a gate.
7. When the diff moves or reorders an existing guard (a permission or membership check, a validation, an early return, a lock, or a step whose position in a sequence matters), even as part of an unrelated refactor: identify the scenario the original position protected against, and re-run it against the new position.
   A test that already covers it counts only if it goes red when you put the guard back in a wrong position.
   If no hazard note (`.forge/code-shape-rules.md`, "Code comments say what the code can't", kind 3) marks the ordering, add one at the guard's new position.
8. For every comment or docstring the diff adds or rewrites: check it against the four kinds in `.forge/code-shape-rules.md` (invariant, guard reason, hazard note, interface contract).
   Cut any that fits none, and cut narrative history down to a hazard note's one clause, or move it to the commit or PR.
9. For every named thing the diff renames, deletes or renumbers that other files cite by that name or number in prose (a doc heading, a skill file path, a step number, a section title): grep the whole repo (docs, skills, `CLAUDE.md`, `.forge/`, test files) for every citation of the old name or number, and update each one in this same PR.
   A match inside a worked-example quote or a code comment still counts; don't skip one because it's "just an example."

Don't read the new branch in isolation and assume the rest are unaffected.
Treat the diff as a suspect ("this probably broke an existing path, disagrees with another builder of the same shape, mishandles the side of a new cap it doesn't mention, answers a finding's wording without covering its class, widens a gate past what that gate can run on, moves a guard without re-running what it protected, adds a comment that fits none of the four kinds, or leaves a stale prose citation of something it renamed, deleted or renumbered") rather than giving it the benefit of the doubt.
That is the same posture `code-review`'s Spec axis takes toward silent requirement breaks, and it is "fix the class of bug, not just the flagged line" (`.forge/review-gate.md`) run before the fact instead of after.

## Repeat-offender patterns

Each pattern here is a defect the post-merge review found again after earlier runs had already found it (`.forge/post-merge-review.md`, "A repeat offender becomes a self-review pattern").

- **A stated guarantee has its enforcement.** For every comment, docstring or doc sentence the diff adds or rewrites that says something always or never holds (a check is made, a bound applies, a value never leaves the process), check that the sentence names the check or test that enforces it, and that the check exists on this branch.
  If nothing enforces it, enforce it in this PR or reword the sentence to what the code actually does.
  Also grep for existing statements the diff makes untrue, such as a docstring elsewhere still promising a check the diff removes.
- **A fixed path under a shared writable directory is private and checked.** For every file, directory, lock or socket the diff creates or opens at a predictable path under a directory other accounts can write (`/tmp`, `/var/tmp`, a shared cache), check that it lives in a directory the code creates with mode 700 and refuses when that directory is a symlink, owned by another user or writable by others, and that a file inside it is refused when it is a symlink.
  A predictable path there lets another account pre-create it, hold its lock, or plant a symlink that a privileged write follows.
- **A class claimed closed is enumerated from its source.** When the diff says it closes a whole class (every enum value, every route a router serves, every key a parser accepts), list the members from the authority that defines them (the code that handles the cases, or the list, schema or specification that defines them) on the PR's `Evidence:` line, not from the finding's examples, and test each one.
  A fix built from the finding's examples alone declares the class closed and misses the member nobody named.

## Concurrency and lifecycle checklist (triggered)

Many post-merge review findings are concurrency or lifecycle bugs that no local or CI check can reach: a pool force-closed on teardown, a cached list of connected users gone stale, a lookup failure aborting a fire-and-forget path, a slot or lock leaked on an exit path.
This is a review checklist, not a test harness.

Run it, in addition to the nine parts above, whenever the diff touches connections, pools, background tasks, sockets, locks, slots or claims, or per-session or per-connection cached state, or adds an await between a user's action and its effect in a client (a confirmation, a request):

1. **Teardown:** for each connection, pool, task or subscription the diff creates, what it does on shutdown, cancellation and error, and who closes it.
2. **Fire-and-forget failure:** does a failing lookup or exception in a background path abort work it shouldn't, or vanish silently?
3. **Stale cached state:** state cached per connection or per session that a membership, permission or ownership change can make stale; who invalidates it?
4. **Release on every exit:** each slot, claim, lock or counter the diff takes is released on every path out (return, raise, cancel, timeout).
5. **Ordering under concurrency:** two requests interleaving at each `await` the diff adds.
6. **Operation state across an identity switch:** for each such await, what happens if the user, account, workspace or other identity the operation started in changes while it's pending?
   The pending step must be cancelled, or its result dropped, never applied to the new context.

## Security delta checklist (triggered)

Run this whenever the ticket's Structure guidance carries a **Security** part (`implement-with-merge` step 0a) or the design doc's slice carries a **Threat-model delta** section (`.forge/feature-pipeline.md`, stage 5).
The two triggers land their doc edit at different points, so check the right one:

- **A design-exit Structure guidance's Security part** (step 0a): the ticket has no slice concept, so its security-doc delta is a closing step of *this* PR, like any other step 0 closing step; there is no later merge for it to wait for.
- **A design-doc slice's Threat-model delta**: it is folded into `docs/security/threat-model.md` only by the small follow-up PR the terminal-slice merge triggers (`implement-with-merge` step 3), never a direct write to `main`, because the two facts that gate it (this slice is terminal, every other terminal slice already merged) aren't knowable until after the PR has merged.
  A slice PR of any kind, terminal or not, carries its proposed delta only in the design doc's own section and never touches the threat model file itself; don't flag the threat model as missing from a slice PR.

1. **The named security docs are actually edited in this PR, but only when this PR is a design-exit ticket's PR.**
   Confirm each doc the delta names is edited, not left for later.
   A missing edit is itself a self-review finding, the same severity as a missing design-doc status line.
   Never apply this check to a design-doc slice PR.
2. **Every named control's guard test goes red with the control removed.**
   For each control the Security part or Threat-model delta lists, find its guard test and verify it directly: remove or neuter the control, re-run, confirm red, restore it.
   Don't credit a guard test as real coverage because it reads plausibly.
   This applies to every PR that introduces the control, whether or not it also updates the threat model file; record which controls were verified this way on the PR's `Evidence:` line.
3. **"Security: none" is checked, not trusted.**
   If the Structure guidance or slice says "Security: none", re-read its one-line reason against the diff as actually built; a ticket whose scope grew during implementation can leave a stale "none" behind.

## Domain glossary checklist (triggered)

Run this whenever the diff's issue, PR body, code, comments or test names use a domain concept: a noun `CONTEXT.md` would define, not a purely technical one.
Checking vocabulary against `CONTEXT.md` is a habit any skill already has (`docs/agents/domain.md`); this checklist makes sure a collision or a gap actually gets surfaced instead of staying an unwritten note.

1. **The term matches the glossary.** For every domain concept the diff names, check it against `CONTEXT.md`'s definition and the `_Avoid_` synonyms it rules out.
   A mismatch is a finding: either the diff drifts to a synonym the glossary already rejected, or it uses the glossary's term to mean something else.
2. **A concept missing from the glossary is surfaced, not assumed.** If the diff needs a domain concept `CONTEXT.md` doesn't define yet, don't silently coin or skip it.
   Name it explicitly in the PR body or this self-review's `Review:` entry (`docs/agents/domain.md`, "Use the glossary's vocabulary"), so a reviewer or `/domain-modeling` can decide whether it's a real gap or invented language to reconsider.

## Mutually-dependent file pairs checklist (triggered)

Two files can each describe the same rule, list or contract and claim to match the other, then drift apart the moment one is edited alone: neither `/code-review`'s Standards or Spec axis is scoped to notice, because each reads the diff against a document, not against the diff's other half.

Run this whenever the diff touches one file of a pair below, or a pair a generated project has named in a project-owned doc of its own (`CLAUDE.md`, under its own project section, can point at it):

These paths are as a generated project has them (what this skill actually ships into); in this repository itself they carry the `template/` prefix and, for a `.jinja` source, lose that suffix once rendered -- for example `.agents/skills/coordinator/SKILL.md` is `template/.agents/skills/coordinator/SKILL.md.jinja` here.

- `.forge/coordinator-core.md` ↔ `.agents/skills/queue-sweep/SKILL.md`: both describe the default-queue rule and must list the same hold reasons.
- `instructing-agents.md` ↔ `scripts/project_init_checklist.md`: `instructing-agents.md` points at the checklist file as the one copy of the project-initiation list; a change to either must keep that pointer accurate.
- `.forge/self-review.md` ↔ this file: the condensed file's "Triggered checklists" list must name exactly the checklists this file actually has, in the same order, with no action inlined into the condensed bullet that isn't also here.

1. **Read the other file as it stands on `main`, not from memory.** A pair drifts exactly because someone trusted what the other file used to say.
2. **Reconcile it in the same PR.** Update the other file's half of the shared rule, list or pointer to match, or confirm in the PR body that no change is needed and why.
3. **A pair with no update needed still gets a line on the PR's `Evidence:` or self-review entry** naming which file was checked and that it still agrees, so the check is a recorded fact, not an assumed one.

This template-level list can only name pairs TheForge itself ships. A project names its own pairs in a project-owned doc (`.forge/forge-overrides.md`, "Project rules go in project-owned files"), never in this file, which a forge sync would overwrite.

## Scope generalization checklist (triggered)

Run this whenever the diff turns one of the owner's specific, one-off instructions into standing skill or instruction wording usable by future tickets, rather than applying that instruction only to the ticket it was given for (`.forge/tickets-and-branches.md`, "A scope check-in before generalizing an instruction").

1. **Decide which this diff is.** For each new or reworded rule the diff adds to a skill, `CLAUDE.md` or a `.forge/` file: decide whether it applies an already-standing rule, or generalizes a single owner instance the owner gave for one ticket into a new one. On any doubt, treat it as the latter.
2. **Check the ticket's `Request-trace:` line covers the generalization, not just the instance.** A request that is genuine for the one-off instance does not, by itself, cover turning it into a standing rule (SDLC-014's scope clause); the generalization needs its own request before it merges.
3. **Confirm the owner's plain yes/no check-in is recorded.** The ticket or the PR body records the owner's answer to "do you want this process change folded into the repository's instruction set?" (or words to that effect), in the owner's own words — a scope confirmation, not a wording-approval quote.
4. A diff that generalizes an instruction with no recorded check-in is a finding: it does not merge until the owner has answered, or the generalization is narrowed back to the one ticket it was asked for.
