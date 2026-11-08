# Testing tools

The per-language tools behind the techniques in `.agents/skills/tdd/tests.md`.
The skill stays language-neutral; this file says what this project uses.
Fill the table in at stage 0, once the project's languages are settled, and keep it current.

| Technique | Language 1 (set at stage 0) | Language 2 (if any) | Installed |
|---|---|---|---|
| Unit and integration test runner | | | |
| Coverage | | | |
| Property-based tests | for example Hypothesis (Python), fast-check (TypeScript) | | No: add to dev dependencies, pinned, the first time a ticket needs it |
| Mutation testing | for example mutmut (Python), Stryker (TypeScript) | | No: installed per run, at a pinned version, after the owner says yes (`post-merge-review` step 5a) |

Mutation testing is an audit, not a gate: run it on one module at a time, never as part of a ticket's standing checks (`.forge/ci-and-checks.md`, "A ticket's own checks").
The periodic tautological-test sample lives in `.agents/skills/post-merge-review/SKILL.md` step 5a; this file only names the tools and versions it uses.
Don't confuse this tool-driven, gated sample with **guard-removal verification** (`.agents/skills/tdd/SKILL.md`): that's the routine, ungated, per-guard "comment it out, watch the test go red" check every build thread already does every ticket, not an instance of mutation testing.

Tag a test that proves a requirement with the requirement's ID, in the form `docs/agents/requirement-coverage.md` sets for each language.
