# Requirement test evidence

Which test proves which requirement in `docs/requirements/requirements-specification.md` is recorded in the tests themselves, by a marker carrying the requirement's ID.
This file holds the tagging convention, and what a marker and a passing test can't carry on their own: mutation-verification notes, genuine coverage gaps and why forcing a tag there would misrepresent coverage, standing exclusions, and pointers to evidence that lives outside the test suites (a performance baseline, a load harness).

## Tagging convention

A test written specifically to prove a requirement (or to fix a finding tied to one) carries the requirement's ID as a machine-readable marker.
Choose one marker form per language at stage 0 and record it here, for example:

- **Python with pytest**: a registered marker, `@pytest.mark.requirement("FR-001")`, variadic so one test can prove several requirements, as a decorator or a module-level `pytestmark`.
  Validate it at collection time, so a mistyped or retired ID fails collection immediately.
- **JavaScript or TypeScript**: a `// @requirement FR-001 FR-002` pragma comment directly above the `it(...)` or `test(...)` call.

Tag the *specific* tests that would fail if the requirement's behaviour regressed, not every test in the file.

Once more than a handful of requirements exist, generate the requirement-to-test map from the markers rather than writing it by hand, and keep the count of untagged requirements as a shrink-only ratchet: a PR may lower it, never raise it.
Until then, this is an open gap to record on the requirements specification's known-gaps table.

## Standing exclusions

Some requirements are deliberately left untagged because the genuine proof lives somewhere this repo's own test suite structurally can't reach, not because no test exists.
List each one here with its reason, for example:

- a claim about a container image's build shape, verified by reading the build file rather than by a test;
- behaviour whose mechanism lives in an upstream dependency and is proven by that dependency's own tests;
- a requirement with no code path to violate, because the interface never offers the knob it forbids.

## Mutation-verified guards

Guard tests confirmed to fail when the behaviour they protect is removed: evidence the test's pass or fail status alone doesn't carry.
Record each as the requirement ID, the test, and the removal that turned it red.

None yet.

## Evidence outside the test suites

Pointers to performance baselines, load-test harnesses or manual verification records that back a requirement's status.

None yet.
