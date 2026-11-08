# Code-shape rules backed by guards (Default)

These are the standing code-shape rules.
Each is backed by a mechanical guard where one is possible, and by the code review's Standards axis where it is not.
A rule that names a guard lands in the same PR as its guard: never point at a guard that is not on `main` yet.
Where a rule uses an allowlist or baseline file, that file is captured against the commit it was seeded from and may only shrink.
A PR that removes a violation lowers or removes its entry in the same PR, never leaving it slack.

**Each project picks its own tools.**
The guards below are described by what they enforce, not by a tool, because different stacks use different tools.
At stage 0 (`.forge/feature-pipeline.md`) the project chooses its equivalents (a ruff- or eslint-style linter, a vulture- or knip-style dead-code finder, a coverage tool, a size measurement) and wires each into `.pre-commit-config.yaml` and the guard scripts under `scripts/`.
Until it does, the shipped guard scripts are stubs that say so.

## Code comments say what the code can't

Write a comment only when deleting it would let a competent reader make a mistake.
Four kinds earn their place:

1. **Invariant**: what this code keeps true, led by the requirement or ADR ID when one is the reason.
2. **Guard reason**: why a check exists, or why it sits where it does.
3. **Hazard note**: a coupling to code the reader has no reason to open, such as "if you change this, also change X" or "must run before Y".
   This is the one place a little history belongs: the past failure, in a clause, as evidence for the hazard.
4. **Interface contract**: on a module, class or public function, what it promises callers that the signature does not say (units, ownership, error modes, concurrency).

Implementation comments say why, never what.
Restating the code, narrating history (which review found it, the chain of earlier fixes), design rationale beyond a line, and a TODO without a tracking issue are not comments.
History belongs in the commit, PR and issue, where `git blame` reaches it; design rationale belongs in the design doc or ADR, linked by ID.

Default to one or two lines: most invariants, guard reasons and contracts say everything they need to in that much.
A comment earns more lines only when the hazard, guard reason or contract itself is genuinely multi-part — several call sites to touch, several failure modes, or a sequencing constraint that doesn't fit in one clause — and even then it stays a list of short clauses, one per part, not a narrative paragraph.
Length earned by restating the code, walking through how the change was made, or defending the change is not this exception; that belongs in the commit, PR or ADR instead.

A docstring is a one-line summary, plus contract lines only when they are not obvious.
A module docstring names the module's responsibility in a few lines and links its design-doc section rather than restating it.
Do not rewrite comments in code your change does not touch, but tidy a history block into this shape when your change does touch it.

An agent reads every comment in a file it edits.
Narration costs context on every read, anchors the agent on behaviour the code no longer has, and gets copied into the next change.

## Module and function size cap

Keep a module under 1500 lines and a function under 100 code lines (blank lines, comments and docstrings excluded; a nested function counts toward its parent).
The same caps apply to every language in the repo.
A file or function already over a cap when the cap landed is tracked in a shrink-only allowlist; new code never gets a new entry.
Modules that grow past the point anyone can safely change them in one sitting are expensive to split later.

The guard is `scripts/check_module_size.py` against `scripts/module_size_allowlist.json`, run as a pre-commit hook; each project points it at its own language's function boundaries at stage 0.
Both caps render from the `max_module_lines` and `max_function_code_lines` answers in `.copier-answers.yml`, so a cap changes by changing its answer (for example `copier update --trust --defaults --skip-tasks --vcs-ref <_commit> --data max_function_code_lines=<n>`, with `_commit` from `.copier-answers.yml` so the TheForge version does not move), which moves this rule and the guard together.
`--defaults` is required in a non-interactive session, the same reason the coverage-floor `copier update` command needs it: without it Copier re-asks every other question and dies with `EOFError` on a session with no TTY to answer them.
Vendored skill files under `.agents/skills/` are third-party code the project does not split, so the guard skips them.

## Adopt the abstraction early, then stay on it

For any generic concern, adopt a mature library rather than hand-rolling one.
Data access, provider calls, scheduling, retries, parsing, auth and caching are typical examples, but the rule is not limited to them.
Decide at design time: the design doc names the library chosen and the alternatives rejected, and the architecture description lists every adopted abstraction.

Once a library is adopted, code goes through it.
A bypass (raw SQL beside the ORM, a raw HTTP call beside the SDK client) is a deliberate decision, allowed when performance or functionality needs it, with a one-line comment at the site and an ADR when it spans more than one call site.
An unexplained bypass is a review finding.
Each concern lives in the module that owns it, and other code calls that module rather than the library.

The build-versus-buy record lives in the design doc's slice, in the ticket's Structure guidance for a design-exit ticket, or in the PR body when neither exists.
When that record depended on `research`'s findings, it also gets an ADR, per `.forge/feature-pipeline.md`'s stage 5 build-versus-buy bullet — a second case for an ADR here, beside the bypass-spanning-call-sites case above.
Before hand-rolling more than about 20 lines of generic infrastructure (process lifecycle, locking, retries, caching, validation, auth), find the library.
Fixing the same class of bug twice in one hand-rolled helper is the signal you should have.

The guard is review only (the Standards axis).
A mechanical import-boundary guard is added for a specific library only once a bypass of it has actually recurred in review, and is recorded in the ADR that adopted the library.

## A safety-critical process step needs a tested mechanism, not just reviewed prose

When a step in a forge-owned script or skill is safety- or security-critical — getting it wrong deletes the wrong lines, disables a guard, or ships an unreviewed change — build it as a scripted, tested function, not hand-performed prose that only a human or an agent follows by reading instructions.
A post-hoc shape check on the result is not a substitute: it catches some wrong outcomes, not a wrong procedure.
Give each such mechanism its own guard test, following this repository's own guard-test convention (it goes red when the check it verifies is removed or weakened).

This doesn't require full automation of a step whose core decision is a genuine judgement call (e.g. merging conflicting free-text content).
Such a step may stay human/agent-reviewed — but the mechanical part of it (deciding what's safe to handle automatically) still needs to be scripted and tested, and the boundary between "handled automatically" and "flagged for review" needs its own test for completeness, so nothing falls through unflagged.

The guard is review only, via this file's own Standards axis.
A mechanical guard is added for a specific mechanism once a violation of it has actually recurred, the same convention as "Adopt the abstraction early, then stay on it" above.

## Dead code

A function, method, attribute, class or variable that nothing reaches any more is removed, not kept in case it is needed later.
A comment or docstring describing behaviour the code no longer has is the same problem.
Findings already present when the guard lands are seeded into a baseline and fixed as separate tracked work.

The guard is `scripts/check_dead_code.py`, which runs the project's chosen dead-code finder and compares its findings with the shrink-only `scripts/dead_code_baseline.json`.
A count that drops without its entry being lowered fails, the same as a new finding.
A finder exit code outside the finder's own success codes also fails, so a crashed finder never reads as a clean run.
Names a framework calls by convention (route handlers, hooks, entry points) go in the finder's own configuration, not in the baseline.

## No goldens or snapshots

Agents do not write golden-file or snapshot tests (`.agents/skills/tdd/tests.md`, "Golden and snapshot tests").
A regenerated golden asserts the implementation back to itself, and nobody has time to review that diff when it goes red.
When exact text really is the requirement (a user-facing message, a wire format another system parses), write it in the test as a short literal.

The guard is the `no-snapshot-assertions` pre-commit hook (`scripts/check_no_snapshots.py`), which bans the common snapshot-assertion APIs; a project extends its pattern list for its own stack.

## Pinned dependencies (Never)

Every third-party dependency is consumed at a recorded exact version or digest, never a floating tag or range.
That covers direct and development libraries, container images (shipped base, CI service, devcontainer base), CI actions, devcontainer features, package-manager dependencies, pre-commit hook dependencies and vendored files.
Transitive dependencies are locked too, through the stack's lock file.
A version or digest move is its own ticketed PR, reviewed like code, never bundled into an unrelated change.
Language runtimes and the package manager's own self-upgrade are toolchain, held at a minor version rather than pinned exactly.

A rebuild from a release tag must get exactly what was tested; a floating tag can change between builds with no record.
The guard is `scripts/check_pins.py`, which the `pinned-dependencies` pre-commit hook runs on every commit, because a commit that only deletes a lock file passes no file a trigger could match.
It ships as a stub that says it is not running, and stage 0 fills in the checks that fail on any unpinned manifest line, missing lock file, image reference without a digest, or action reference without a full commit SHA.
