---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel sub-agents and reports them side by side, then triages findings MoSCoW. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to \"review since X\"."
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/engineering/code-review/SKILL.md @ 13ea86f0b0 (2026-10-06), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the originating issue / spec, and would a reader who knows the spec and design docs be unsurprised by it (SDLC-115)?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

The issue tracker should have been described to you in `docs/agents/issue-tracker.md`. If it is missing, tell the user to run stage 0 (`.forge/feature-pipeline.md`).

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point (a commit SHA, branch name, tag, `main`, `HEAD~5`, etc.). If they didn't specify one, ask for it.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside two parallel sub-agents.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. Issue references in the commit messages or PR body (`#<n>`, `Closes #<n>`, and the like), fetched via the workflow in `docs/agents/issue-tracker.md`. When that issue points at a slice of a design doc under `docs/design/`, the spec is that slice section (its invariants, interface, guard test and file scope), and the issue only adds the brief rules. When the issue carries a **Structure guidance** section from a design-exit pass, that section is part of the spec too.
2. A path the user passed as an argument.
3. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

### 3. Identify the standards sources

Anything in the repo that documents how code should be written: `CLAUDE.md` and the `.forge/` files it imports through `.forge/entrypoint.md` (especially `.forge/code-shape-rules.md`), and any `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

The standards sources always include `docs/principles.md`. It's read on every review, not only when a search turns it up. A diff that breaks a principle is a documented-standard finding citing the principle by its heading. Breaking a **Never** principle is a hard violation. Breaking a **Default** principle is a hard violation unless the PR body records the departure (`.forge/never-default.md`).

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

On top of the smell baseline, the Standards axis also always checks for **guard-removal-blind tests**: for any new or touched test that asserts a security guard, permission check, or other invariant, would it still pass if that guard were deleted or neutered? This isn't a code smell (it's about the test's own ability to fail, not the production code's shape), so it's reported separately from the smell list, but it's checked with the same always-on weight. See `.agents/skills/tdd/SKILL.md`'s "Guard-removal verification" section for what checking this means in practice (comment out the guard, confirm the test goes red, restore it); the Standards sub-agent actually does this for each guard test in the diff, not just eyeballs whether it looks like it would fail.

The Standards axis also always checks two things no mechanical guard can see (`.forge/code-shape-rules.md`, "Adopt the abstraction early, then stay on it"): **build vs buy**, a new module implementing more than about 20 lines of generic infrastructure (process lifecycle, locking, retries, caching, validation, auth, parsing a known format) without a build-vs-buy line recording the library considered and why it was rejected; and **an unexplained bypass of an adopted abstraction**, such as raw SQL beside the ORM, a raw HTTP call beside an adopted SDK client, or a second concrete thing standing in for an external system at the same abstraction level as an existing adapter (a second HTTP client wrapper, a second ORM session helper, a second queue client), with no one-line comment at the site (and, when it spans more than one call site, no ADR). Each import or raw call is legal on its own; only the missing reason, or the duplication across call sites, makes it a finding. Both are judgement calls, reported the same way as a baseline smell.

The Standards axis also always checks **new comments** against `.forge/code-shape-rules.md`, "Code comments say what the code can't": every comment or docstring the diff adds should be one of four kinds, an **invariant** (what the code keeps true, led by its requirement or ADR ID when one is the reason), a **guard reason** (why a check exists or sits where it does), a **hazard note** (a coupling to code the reader has no reason to open, with at most a clause of history as evidence), or an **interface contract** (what a module, class or public function promises beyond its signature). A comment that restates the code, narrates history, carries design rationale beyond a line, or is a TODO with no tracking issue is a finding. It's a judgement call, reported like a baseline smell; comments in code the diff doesn't touch are out of scope.

When the diff touches `.forge/coordinator-core.md` or `docs/agents/coordinator-core-snippet.md`, the Standards axis also checks it against the constraints in TheForge's coordinator-core ADR, which records them verbatim: in particular the two no guard test can see (that the core holds only what the coordinator must personally act on, and that every source it duplicates carries the forward-reference sentence).
A diff that breaks a constraint is a finding unless it supersedes that ADR.

When the diff touches a path the artefact map lists (`.forge/agent-skills-and-reference.md`, "Artefacts and the skills that govern them", plus any rows the project's `CLAUDE.md` adds), that path's governing skill is a standards source too (SDLC-119). The Standards axis checks each changed mapped file against the form rules its row names, and against the file's own Conventions section where it has one. A Conventions line that contradicts the skill is itself the finding. A skill the map does not name is not a standard.

When the diff names a domain concept (in an issue title, a variable or symbol, a comment, or a test name), the Standards axis also checks it against `CONTEXT.md` (`docs/agents/domain.md`, "Use the glossary's vocabulary"): drifting to a synonym the glossary already rules out, or using a defined term to mean something else, is a finding; a concept the glossary doesn't define yet is a finding only if the diff invents it silently rather than naming the gap explicitly (in the PR body or a comment). A diff that names no domain concept has nothing to check here.

### 3a. Process changes

When the diff touches `CLAUDE.md`, `.forge/`, `.agents/skills/`, `docs/agents/` or project-instruction text, it changes process, and the Spec axis also reviews it against `docs/software-development-lifecycle.md`, the originating authority for process (`.forge/process-and-evidence.md`, "Process changes follow the lifecycle doc"). The numbered `SDLC-` statements the diff touches are the spec for that part of the review, and the diff is also tested against the policy-traceability rule: a new or changed policy with an engineering-management effect (quality assurance, configuration management, security risk management and the like) that no numbered statement explicitly justifies and directs is a finding, because it needs the SDLC document itself to change first, with the owner's approval. The document's prose is context, not direction. Raise any doubt as a `needs-decision` ticket. A PR that lands owner-approved SDLC wording self-merges only if its diff is verbatim that wording and the approval is quoted in the PR.

### 4. Spawn both sub-agents in parallel

**Standards sub-agent prompt** should include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, always including `docs/principles.md`, **plus the smell baseline from step 3** pasted in full (the sub-agent has no other access to it).
- The guard-removal-blind check above, since it's not part of the smell baseline pasted in.
- The build-vs-buy and adopted-abstraction-bypass checks above, since the mechanical guards can't see either.
- The new-comments check above (with the four kinds), since the sub-agent has no other access to it.
- For each changed file the artefact map lists (step 3): its governing skill's path and the form-rule sections the row names (the sub-agent reads them itself).
- The brief: "Report, per file/hunk where relevant, (a) every place the diff violates a documented standard or a principle in `docs/principles.md`: cite it (file + the rule or principle heading); (b) any baseline smell you spot: name it and quote the hunk; (c) for every new or touched test asserting a security guard, permission check, or other invariant, whether it actually goes red when that guard is removed or neutered — verify this directly (don't just inspect), and report any that don't as a Must-severity finding, distinct from (a)/(b); (d) any new module hand-rolling more than ~20 lines of generic infrastructure with no build-vs-buy line, and any unexplained bypass of an adopted abstraction with no one-line comment at the site or, spanning more than one call site, no ADR; (e) any comment or docstring the diff adds that fits none of the four kinds, quoting it; and (f) for every changed file the artefact map lists, every place the change breaks its governing skill's form rules: cite the skill path and section, and quote the hunk. Distinguish hard violations from judgement calls: documented-standard breaches, guard-removal-blind tests and (f) can be hard findings, but baseline smells, build-vs-buy, adopted-abstraction bypasses and comment kinds are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. State which model you are actually running on and your sub-agent id, first line, so the aggregate can record who performed this review. Under 400 words."

**Spec sub-agent prompt** should include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The path to `docs/requirements/requirements-specification.md` and the PR's `Requirements:` line, if any.
- When step 3a applies, the path to `docs/software-development-lifecycle.md` and the PR's `Process:` line.
- When the diff fixes a finding or bug, the PR's `Evidence:` line (or the builder's planned text for it), which lists the other members of the fixed finding's class the PR checked and the source that list came from. The builder draws that text up before this review runs.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong; (d) any requirement in the requirements specification, cited or not, whose statement the diff would make untrue, and any cited requirement whose status or known-gaps row the diff should have updated but didn't; (e) when the spec is a design doc slice or a Structure guidance section, any way the diff deviates from it (a different interface, a moved hook, a dropped guard test, a placeholder left for a later slice) that the diff does not also record there: an unrecorded deviation is a finding whatever the code's merits, because the doc is the record of what was built; (f) when a lifecycle doc is supplied, every `SDLC-` statement the diff touches, cited or not, whether the diff keeps it true, any place the diff appears to disagree with a statement or might alter its meaning (a possible conflict for the owner to decide, never one to resolve yourself), any policy with an engineering-management effect that the diff introduces or changes without a numbered statement that explicitly justifies and directs it (report doubt as an open question for a `needs-decision` ticket), and a `Process:` line that is missing or names the wrong statements; (g) when the diff fixes a finding or bug, whether the `Evidence:` line lists the other members of the fixed finding's class by name and cites the source the list came from (the code that handles the cases, or the list, schema or specification that defines them): check the list against that source and against the diff, and report a missing list, a list drawn only from the finding's own examples, or a listed member the diff does not actually handle; (h) any region of new behaviour that a reader who knows the requirements, ADRs and design docs could not trace, even indirectly, to one of them or to a recorded decision (SDLC-115): report it, with the trace the PR should add, usually a citation in the PR or the design doc, rarely a new doc. Never ask for behaviour documented in detail. Quote the spec, requirement or statement line for each finding. State which model you are actually running on and your sub-agent id, first line, so the aggregate can record who performed this review. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Aggregate

Each sub-agent's own report names its id and the model it actually ran on. Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned, each still carrying its sub-agent's id and model. Do **not** merge or rerank findings, because the two axes are deliberately separate (see _Why two axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

Carry both axes' performer (`sub-agent <id> of <session link>`), tier (the calling thread's own tier, build-tier for an ordinary implementation PR) and reported model back into the PR's `Review:` line when this runs as part of `implement-with-merge` step 2.

## Triaging findings (MoSCoW)

A finding's own severity label (Critical/High/Medium/Low, or anything else the source attaches) doesn't map cleanly to whether it's worth a push. Classify every finding (from either axis above, from the mandatory self-review step that runs after both, `.agents/skills/self-review/SKILL.md`, or from the post-merge review) against MoSCoW instead, and **only push fixes for Must and Should**; Could and Won't get a one-line reply explaining the call, not a code change:

- **Must**: a reachable correctness, security, or data-loss bug, reachable *today*, in code already wired into the running app. Exploit it and it's a Must: a leaked secret, a race that drops a message, a crash on a real input. Verify by reproducing it (write the failing input, watch it fail) before fixing, the same as any other bug report.
  **When the finding is about a security guard, permission check, or other invariant a test claims to cover (including a fix you're writing a new test for, or an existing test the finding points at), "verify" also means proving the test itself fails when the guard is removed or neutered, not just that it currently passes.** A test that can't fail this way usually hits an unreached branch, asserts the wrong target, or duplicates the guarded logic instead of driving the real path. Concretely: briefly comment out or neuter the guard, re-run the test, confirm it goes red, then restore the guard. This is a required verification step for any Must involving a guard or invariant, the same as reproducing the bug is, not optional polish.
- **Should**: a real gap that degrades cleanly rather than corrupting anything: an uncaught exception type that surfaces a raw traceback instead of the module's own error type, a documented test-plan claim that isn't actually covered. Worth fixing, lower stakes than a Must.
- **Could**: everything about code not yet reachable or not yet relied on: bounds or validation on a field nothing reads yet, a stricter contract on a value that's already harmless by construction (a committed local-development placeholder, not a real secret), a test-coverage nit on behaviour already covered by a different assertion path, "wire this into startup" when the PR's stated scope is an additive expand step. Defensible to defer to a follow-up; reply saying so.
- **Won't**: the finding is simply wrong, or asks to widen the PR beyond its stated scope. Reply with why, don't push anything.

When in doubt between Should and Could, ask: does skipping this leave the *currently shipped* behaviour wrong, or only leave a not-yet-exercised code path less defensive than it could be? The former is a Should; the latter is a Could.

**A forward reference to a planned-but-unwritten artefact is a Won't, whatever severity it's reported with, unless a mechanical check validates that kind of reference.** The feature pipeline deliberately writes requirement wording, a status line or a comment that names a design doc or ticket before that artefact exists (requirements approval at stage 4 precedes the detailed design doc at stage 5). If the finding names a design doc or ticket that is coming, reply once pointing at that text and the pipeline stage that will produce it, resolve the thread, and don't push a change for it. If the project has a doc-consistency check that rejects a specific kind of reference (for example a numbered `ADR-NNNN` citation with no matching file), a finding of that kind inside the files the check covers is real, not a forward reference: drop the premature reference or write the artefact.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other. See `.forge/review-architecture-rationale.md` for why this split, and the separate self-review step that runs after both axes, aren't combined to save a pass.
