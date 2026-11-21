---
name: self-review
description: "Mandatory self-review step run after /code-review's Standards and Spec axes finish, on every PR in this repo. Checks what neither axis is scoped to: every other caller/builder of what the diff touches, reuse over recreation, both sides of any cap or threshold the diff introduces, whether a fix for a named finding covers the finding's whole class, whether a gate the diff widens still runs on everything it now enforces, whether a guard the diff moves still protects what its old position did, whether every comment the diff adds earns its place, whether a renamed/deleted/renumbered thing still has stale prose citations elsewhere, and the repeat-offender patterns the post-merge review has added (such as a stated guarantee with nothing enforcing it, or a predictable path under a shared writable directory)."
disable-model-invocation: true
---

# Self-review: every other caller or builder, reuse over recreation, both sides of a new cap, a fix's whole class, a gate that runs on what it enforces, a guard that still protects what moved past it, a comment that earns its place, and no stale prose citation of a renamed thing

**This is its own mandatory step, run after `/code-review`'s Standards and Spec axes finish, on every PR, with nothing that relaxes it.**
Nothing in `/code-review` (the Standards axis's conventions and smell-baseline check, or the Spec axis's acceptance-criteria check) narrows, satisfies or substitutes for it: both axes can come back clean and this step still finds a break, because it checks every *other* place that already depends on what the diff touches.
`implement-with-merge` runs it as its own step right after `/code-review` returns, and the PR's `Review:` line records who did it, at which tier, and what it covered.
`.forge/review-architecture-rationale.md` says why it stays a separate pass.

**Its checklist grows**: a repeat offender the post-merge review (`post-merge-review`) notices is added below, so the next PR is checked for it before merge.

## The shapes this step exists to catch

A per-PR review checks a diff against its ticket and misses the bug a later review catches: a new path colliding with an existing one the diff never mentions.
Each part targets one recurring shape:

- **A new path that breaks an existing one.** A new export option is added to a report screen, and an older bulk-export path that shares the same formatter silently starts producing the new layout for callers that never asked for it.
- **Another builder of the same data shape.** Three report generators each format a money amount with their own rounding code instead of calling the one formatter that already exists, and one rounds half-down.
  No shared function was involved, so tracing callers never finds it.
- **The untested side of a cap.** A retry limit gets a test for the case where every attempt fails, and nothing tests the success-on-first-attempt case, which the change quietly made sleep before returning.
- **A fix that matches the finding's wording, not its class.** A review flags one enum value a validation function mishandles; the fix patches that value and leaves a sibling value with the identical bug.
  A guard test can hide this too, if it passes whether or not the fix is present.
- **A gate narrower than what it enforces.** A type checker's include list grows to cover new directories while the pre-commit hook that runs it still only triggers on the old ones, so new type errors land on `main` and fail someone else's unrelated commit.
- **A guard moved with no finding naming it.** An incidental refactor moves a cache lookup ahead of the permission check that used to guard it, and nothing re-tests the scenario the check protected, because no finding asked for it.
- **A stale prose citation.** A doc heading, a skill path, a step number or a section title is renamed, deleted or renumbered, and other files still cite the old one; nothing mechanical catches it.

## The nine parts

Before calling a self-review done, run all nine parts, then every repeat-offender pattern below them:

1. For every function or message type the diff adds a new branch or path to: list every *other* caller, branch or state that already uses that same function or renders that same message, and check each one by name against the new code.
2. For every data shape the diff adds, renames, or changes the meaning of a field in (a dict's keys, a database row, an API response body, a message payload): list every *other* place in the codebase that independently builds or reads that same shape, not just call sites of one shared function, and check each one by name for whether it now disagrees with the diff.
3. Before writing new logic, check whether something already in the codebase does it (or most of it) and reuse or extend that instead of writing a parallel version.
   Recreating what an existing function, module or shared type already does is a finding whether or not the two versions agree today, because that is how they come to disagree.
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

Don't read the new branch in isolation: treat the diff as a suspect that probably has one of the shapes above, or adds a comment that fits none of the four kinds, rather than giving it the benefit of the doubt.
This is the posture `code-review`'s Spec axis takes toward silent requirement breaks, and "fix the class of bug, not just the flagged line" (`.forge/review-gate.md`) run before the fact.

## Repeat-offender patterns

Each pattern here is a defect the post-merge review found again after earlier runs had already found it (`.forge/post-merge-review.md`, "A repeat offender becomes a self-review pattern").

- **A stated guarantee has its enforcement.** For every comment, docstring or doc sentence the diff adds or rewrites that says something always or never holds (a check is made, a bound applies, a value never leaves the process), check that the sentence names the check or test that enforces it, and that the check exists on this branch.
  If nothing enforces it, enforce it in this PR or reword the sentence to what the code actually does.
  Also grep for existing statements the diff makes untrue, such as a docstring elsewhere still promising a check the diff removes.
- **A fixed path under a shared writable directory is private and checked.** For every file, directory, lock or socket the diff creates or opens at a predictable path under a directory other accounts can write (`/tmp`, `/var/tmp`, a shared cache), check that it lives in a directory the code creates with mode 700 and refuses when that directory is a symlink, owned by another user or writable by others, and that a file inside it is refused when it is a symlink.
  A predictable path there lets another account pre-create it, hold its lock, or plant a symlink that a privileged write follows.
- **A class claimed closed is enumerated from its source.** When the diff says it closes a whole class (every enum value, every route a router serves, every key a parser accepts), list the members from the authority that defines them (the code that handles the cases, or the list, schema or specification that defines them) on the PR's `Evidence:` line, not from the finding's examples, and test each one.
  A fix built from the finding's examples alone declares the class closed and misses the member nobody named.
- **A completeness claim over a sweep or review round is a named list, not a count.** When the PR claims a sweep or review round checked "all N" or "every X" of something with no authoritative list to enumerate from (a window of past PRs, a batch of review rounds, files a search turned up), unlike the "class claimed closed" pattern above, check that the claim names each member checked, not only a total, and that its stated scope visibly matches the class it claims.
  A count alone lets the sweep's scope drift silently, and leaves the next review to re-derive it to find what was missed.
- **The `Review:` line names a clean-context sub-agent for Standards and Spec, never the builder itself.** Before writing the `Review:` field, check each of the Standards and Spec entries names an independent, clean-context sub-agent actually spawned for this review — not `self`, `builder's own`, or any performer that is also this PR's author or carries this thread's own history — unless the PR genuinely qualifies for the light gate (`.forge/review-gate.md`, "Full gate and light gate") and says so in those words.
  `scripts/check_review_gate.py` checks the performer field's shape, not that the independent review actually happened; that judgement is this step's, before the PR opens.
- **A new or widened guard fires on every violation shape it claims to cover, not just the one its fix targeted.** For a diff that adds a guard or widens what an existing one catches, list each distinct way the guarded invariant can be violated, construct each one, and show the guard fires on it — not only the shape the original finding demonstrated. Record each shape checked on the PR's `Evidence:` line, the same as the "class claimed closed" pattern above.
  A guard that catches one shape and misses a sibling (a rate limit checking requests per account but not per IP; a schema check rejecting an unexpected extra field but not a missing required one; an idempotency check catching a key reused within one request but not one replayed after a retry) is a guard test that can't fail, one shape narrower; unlike the "class claimed closed" pattern, this enumerates the guard's violation shapes, not a fix's domain members.

## Concurrency and lifecycle checklist (triggered)

Many post-merge review findings are concurrency or lifecycle bugs no local or CI check reaches (a pool force-closed on teardown, a cached list of connected users gone stale, a lookup failure aborting a fire-and-forget path, a slot or lock leaked on an exit path); this is a review checklist, not a test harness.

Run it, in addition to the nine parts, whenever the diff touches connections, pools, background tasks, sockets, locks, slots or claims, or per-session or per-connection cached state, or adds an await between a user's action and its effect in a client (a confirmation, a request):

1. **Teardown:** for each connection, pool, task or subscription the diff creates, what it does on shutdown, cancellation and error, and who closes it.
2. **Fire-and-forget failure:** does a failing lookup or exception in a background path abort work it shouldn't, or vanish silently?
3. **Stale cached state:** state cached per connection or per session that a membership, permission or ownership change can make stale; who invalidates it?
4. **Release on every exit:** each slot, claim, lock or counter the diff takes is released on every path out (return, raise, cancel, timeout).
5. **Ordering under concurrency:** two requests interleaving at each `await` the diff adds.
6. **Operation state across an identity switch:** for each such await, what happens if the user, account, workspace or other identity the operation started in changes while it's pending?
   The pending step must be cancelled, or its result dropped, never applied to the new context.

## Guard-removal checklist (triggered)

Run this whenever the diff adds or changes a guard made of several rules sharing one test file: a skip list, an exemption list, a threshold, or a fallback path.
A guard test crediting itself from one mutation of one rule, while its test file claims to cover several, can pass the existing guard-removal rule to the letter while most of the rules the file claims to cover were never checked — for example, a rate limiter's test file claims to cover a per-user threshold, a per-IP threshold and a burst-window rule, but only the per-user threshold was ever neutered and shown red.

1. For every new or changed branch or rule the diff adds to the guard, neuter that rule alone, drawn from the guard's own code rather than guessed at from the test file's intent.
2. Show its test go red, then restore the rule.
3. Record each rule checked, and its red result, on the PR's `Evidence:` line.

This is the same discipline `.agents/skills/tdd/SKILL.md`'s "Guard-removal verification" already states; this checklist entry only makes sure self-review actually runs it, rather than restating the procedure here.

## Security delta checklist (triggered)

Run this whenever the ticket's Structure guidance carries a **Security** part (`implement-with-merge` step 0a) or the design doc's slice carries a **Threat-model delta** section (`.forge/feature-pipeline.md`, stage 5).
The two land their doc edit at different points:

- **A design-exit Structure guidance's Security part** (step 0a): its security-doc delta is a closing step of *this* PR.
- **A design-doc slice's Threat-model delta**: only the follow-up PR the terminal-slice merge triggers (`implement-with-merge` step 3) folds it into `docs/security/threat-model.md`, never a direct write to `main`, because whether this slice is terminal and every other terminal slice merged is unknowable before the merge; a slice PR, terminal or not, carries its delta only in the design doc's section, so don't flag the threat model as missing from it.

1. **On a design-exit ticket's PR only (never a slice PR), each security doc the delta names is edited in this PR**; a missing edit is a finding, as severe as a missing design-doc status line.
2. **Every named control's guard test goes red with the control removed.**
   For each control listed, remove or neuter it, re-run its guard test, confirm red, and restore it; don't credit a test because it reads plausibly.
   This applies to every PR introducing the control, whether or not it updates the threat model; record the controls verified on the `Evidence:` line.
3. **"Security: none" is checked, not trusted.**
   If the Structure guidance or slice says "Security: none", re-read its one-line reason against the diff as actually built; a ticket whose scope grew during implementation can leave a stale "none" behind.

## Domain glossary checklist (triggered)

Run this whenever the diff's issue, PR body, code, comments or test names use a domain concept: a noun `CONTEXT.md` would define, not a purely technical one.
It makes sure a vocabulary collision or gap (`docs/agents/domain.md`) is surfaced, not left an unwritten note.

1. **The term matches the glossary.** For every domain concept the diff names, check it against `CONTEXT.md`'s definition and the `_Avoid_` synonyms it rules out.
   A mismatch is a finding: either the diff drifts to a synonym the glossary already rejected, or it uses the glossary's term to mean something else.
2. **A concept missing from the glossary is surfaced, not assumed.** Don't silently coin or skip a domain concept `CONTEXT.md` lacks: name it in the PR body or this self-review's `Review:` entry (`docs/agents/domain.md`, "Use the glossary's vocabulary"), so a reviewer or `/domain-modeling` decides whether it is a real gap or invented language.

## Mutually-dependent file pairs checklist (triggered)

Two files describing the same rule, list or contract drift apart the moment one is edited alone, and neither `/code-review` axis notices, since each reads the diff against a document, not against the pair's other half.

Run this whenever the diff touches one file of a pair below, or a pair the project names in a project-owned doc (such as its `CLAUDE.md` project section).
Paths are as a generated project has them; in TheForge itself they carry the `template/` prefix and, for a `.jinja` source, that suffix (`.agents/skills/coordinator/SKILL.md` is `template/.agents/skills/coordinator/SKILL.md.jinja` there).

- `.forge/coordinator-core.md` ↔ `.agents/skills/queue-sweep/SKILL.md`: both describe the default-queue rule and must list the same hold reasons.
- `instructing-agents.md` ↔ `scripts/project_init_checklist.md`: `instructing-agents.md` points at the checklist file as the one copy of the project-initiation list; a change to either must keep that pointer accurate.
- `.forge/self-review.md` ↔ this file: the condensed file's "Triggered checklists" list must name exactly the checklists this file actually has, in the same order, with no action inlined into the condensed bullet that isn't also here.
- `.forge/agent-skills-and-reference.md`'s artefact-map table ↔ `.agents/skills/code-review/SKILL.md` step 3, this file's "Governed artefact checklist" and `.agents/skills/post-merge-review/SKILL.md`'s "Governed artefacts" grading rule: all four must describe the same mechanism and, between them, cover a project's own `CLAUDE.md`-added rows too.
- `.agents/skills/requirements-spec/SKILL.md`'s "Evidence" bullet ↔ `scripts/check_requirements_evidence.py`: the skill's shape rules (the bold label, the comma-separated backticked paths, file level only) and the checker's actual parsing must describe the same shape.

1. **Read the other file as it stands on `main`, not from memory.** A pair drifts exactly because someone trusted what the other file used to say.
2. **Reconcile it in the same PR.** Update the other file's half of the shared rule, list or pointer to match, or confirm in the PR body that no change is needed and why.
3. **A pair with no update needed still gets a line on the PR's `Evidence:` or self-review entry** naming which file was checked and that it still agrees, so the check is a recorded fact, not an assumed one.

This list names only pairs TheForge ships; a project names its own in a project-owned doc (`.forge/forge-overrides.md`, "Project rules go in project-owned files"), never here, where a forge sync would overwrite them.

## Scope generalization checklist (triggered)

Run this whenever the diff turns one of the owner's specific, one-off instructions into standing skill or instruction wording usable by future tickets, rather than applying that instruction only to the ticket it was given for (`.forge/tickets-and-branches.md`, "A scope check-in before generalizing an instruction").

1. **Decide which this diff is.** For each new or reworded rule in a skill, `CLAUDE.md` or a `.forge/` file, decide whether it applies an already-standing rule or generalizes a one-ticket owner instruction into a new one; on any doubt, treat it as the latter.
2. **Check the ticket's `Request-trace:` covers the generalization, not just the instance.** A genuine one-off request does not cover a standing rule (SDLC-014's scope clause); the generalization needs its own request before it merges.
3. **Confirm the owner's plain yes/no check-in is recorded** on the ticket or PR body, in the owner's own words, answering "do you want this process change folded into the repository's instruction set?" or similar: a scope confirmation, not a wording-approval quote.
4. A diff that generalizes an instruction with no recorded check-in is a finding: it does not merge until the owner has answered, or the generalization is narrowed back to the one ticket it was asked for.

## Governed artefact checklist (triggered)

Run this whenever the diff touches a path the artefact map lists (`.forge/agent-skills-and-reference.md`, "Artefacts and the skills that govern them") and the PR is on the light gate, which has no Standards axis to check it (SDLC-119).
On the full gate the Standards axis already checks it: confirm its `Review:` entry names each mapped file, and run this checklist only for a mapped file it missed.

1. **Read the governing skill's form rules on this branch**, the sections the map row names, not from memory.
2. **Check every changed line of each mapped file against them**, and against the file's own Conventions section if it has one; a Conventions line that contradicts the skill is itself a finding.
3. **Fix any break in this PR** before it merges.
4. **Record it**: the self-review entry on the `Review:` line names each mapped file and its governing skill.

## Sync-impact category checklist (triggered)

Run this whenever the diff is about to be recorded `release:internal` or `Release note: none` in a project shipping process, scaffolding or configuration other repositories pull in on their own schedule (a template, a shared library, a platform, an SDK): a change a downstream repository must act on after updating is `release:integrator` (`docs/agents/triage-labels.md`, "Release-note labels").

Check the diff against all eight categories, not only the one the ticket names, recording on the `Evidence:` line the source searched for each and what was found:

1. **A shipped guard or hook that now reads or checks a file the downstream repository owns or seeds itself** (new enforcement over content the update never rewrites still lands on its next commit).
2. **A new or changed setup-time question** the project's own generator or init step asks. Exclude a derived value nobody is ever asked to answer.
3. **A new label or tracker** a shipped bootstrap or setup step creates.
4. **A new secret, variable or permission** a shipped workflow or settings file reads.
5. **A renamed or deleted shipped file.**
6. **A re-paste snippet** whose content or instructions changed.
7. **Shipped text that now depends on content only a new project's own seed carries**, so the citation or reference dangles for a downstream repository that never gets the seed.
8. **Shipped process or governance wording** that changes what a downstream repository's own review gate requires.

A finding in any category gets at least a `release:integrator` note; one that breaks a downstream repository's next commit without action also gets `breaking`. A category with no finding still gets a line on the `Evidence:` entry naming what was searched and that nothing was found.
