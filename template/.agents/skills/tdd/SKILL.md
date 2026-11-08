---
name: tdd
description: Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests.
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/engineering/tdd/SKILL.md @ 321658273c (2026-08-19), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

# Test-Driven Development

TDD is the red → green loop. This skill is the reference that makes that loop produce tests worth keeping: what a good test is, where tests go, the anti-patterns, and the rules of the loop. Every section applies on every cycle: consult them before and during the loop, not after.

When exploring the codebase, read `CONTEXT.md` (if it exists) so test names and interface vocabulary match the project's domain language, and respect ADRs in the area you're touching.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification: "user can checkout with valid cart" tells you exactly what capability exists, and it survives refactors because it doesn't care about internal structure.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Seams: where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside. Tests live at seams, never against internals.

**Test only at pre-agreed seams.** Before writing any test, write down the seams under test and confirm them with the user. No test is written at an unconfirmed seam. You can't test everything, so agreeing the seams up front is how testing effort lands on the critical paths and complex logic instead of every edge case.

Ask: "What's the public interface, and which seams should we test?"

When the shape of that interface is itself in question (how deep the module is, where the seam belongs, what the interface should expose), `codebase-design` lives only under `.agents/skills/`, so read `.agents/skills/codebase-design/SKILL.md` directly (it may not be available through the harness's skill listing) for the vocabulary. It is the shared source of the module, interface, depth, seam, adapter, leverage and locality terms, and it is a reference to consult, not a session to run.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`, a snapshot derived by hand the same way, a constant asserted equal to itself), so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth: a known-good literal, a worked example, the spec.
- **Guard-removal-blind**: a test for a security guard, permission check, or other invariant that stays green even if the guard it's supposed to prove is deleted or neutered — because the test hits a branch the guard doesn't gate, asserts a response shape the real code never produces, or reimplements the guarded logic itself instead of driving the real path. Distinct from Tautological (that's about the assertion being unfalsifiable by construction; this is about the test not actually exercising the thing it claims to). The red phase of the loop already catches this for a test written test-first in the normal way — you saw it fail before the guard existed. It has to be checked deliberately whenever a test is written or reviewed for an *existing* guard instead: see "Guard-removal verification" below.
- **Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior: you test the _shape_ of things rather than user-facing behavior, the tests go insensitive to real changes, and you commit to test structure before understanding the implementation. Work in **vertical slices** instead: one test → one implementation → repeat, each test a **tracer bullet** that responds to what the last cycle taught you.

## Guard-removal verification

For any test asserting a security guard, permission check, or other invariant — whether it's new or you're touching/reviewing an existing one — prove it can actually fail, not just that it currently passes: briefly comment out or neuter the guard, re-run the test, confirm it goes red, then restore the guard. This is the same discipline red-before-green already gives a freshly-written test for free; this step exists because a guard test written or reviewed outside that fresh red→green cycle (the common case for an existing guard) never gets it automatically. See the MoSCoW "Must" section of `.agents/skills/code-review/SKILL.md` ("Triaging findings (MoSCoW)") for when this is a required step, not optional polish.

**Re-run this per ticket, not once per session.** Nothing else in this skill, or in `implement`/`implement-with-merge`, re-triggers TDD discipline partway through a long session — it's easy to treat "we did TDD" as an established fact from earlier in the thread and stop applying it. Guard-removal-blind tests cluster in PRs that land well into a long, many-ticket session, rarely in a short or early one. Re-read this skill (or at least this section) at the start of each new ticket in a long-running thread, the same way you'd re-confirm seams rather than assume yesterday's still apply.

**A schema mutation check (dropping or altering a real constraint to prove a guard test goes red) never runs against a shared database.** A harness's permission settings may refuse such a change to a shared resource outright, and even where it's allowed, it risks a concurrent sibling thread's test run. Run it against a private, disposable database scoped to that one thread (a throwaway database created and dropped for just this check), never a shared development or test instance.

## Rules of the loop

- **Red before green.** Write the failing test first, then only enough code to pass it. Don't anticipate future tests or add speculative features.
- **One slice at a time.** One seam, one test, one minimal implementation per cycle.
- **Refactoring is not part of the loop.** It belongs to the review stage (see the `code-review` skill), not the red → green implementation cycle.
