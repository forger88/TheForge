<!--
This is the forge-shipped template (template/.github/pull_request_template.md.jinja),
rendered here the same way a generated project gets it, with one override:
a `Neutrality:` line, for the project-neutrality checks every PR to this
repository goes through (CLAUDE.md, "TheForge stays project-neutral"),
which no consuming project needs. `Requirements:`/`Process:` apply here
too now that CLAUDE.md imports the forge entrypoint; `Requirements:`
reads `none (internal)` until this repository's own stage 0 gives it a
requirements specification to cite (docs/forge-overrides.md,
"`.github/pull_request_template.md`").
-->

Before: <what a reader sees on main today>

After: <what a reader sees with this change>

<one sentence on what the change does, when that is not obvious>

How: <a short paragraph>

Ticket: <issue number(s) this PR is backed by, e.g. `Closes #<n>` or `Refs #<n>, #<n>`; every PR merging to main needs at least one>

Requirements: <FR-/NF- IDs this change implements, restores or affects, or `none (internal)` until this repository has a requirements specification>

Process: <for a change to CLAUDE.md, a `.forge/` file, the harness project instructions, a skill, `docs/agents/` or the lifecycle doc: the numbered `SDLC-` statement(s) that justify and direct any policy it introduces or changes, plus any others it affects, or `none` only when it introduces no policy; for any other change, `n/a`>

Release note: <the ticket's release-note labels, re-checked against this diff; then one bullet per release-notes entry, each starting with `Enhancement / <area>:`, `Bug fix / <area>:`, `Integrator:` or `Breaking:` (several when the PR adds or fixes several things), or `none` for `release:internal`; each bullet ends with the issue number it traces to in parentheses, or the epic's number for a bullet that folds into a feature; see `docs/agents/triage-labels.md`, "Release-note labels">

Evidence: <the command that went red before the change and green after, pasted with its result; for a guard test, the run with the guard removed; for a fix to a finding or bug, the other members of its class this PR checked, by name, and the source that list came from (the code that handles the cases, or the list, schema or specification that defines them), not only the finding's own examples>

Tests: <the scoped test commands run, with pass/fail counts; coverage: `<module>: baseline <pct> → branch <pct>`, one entry per touched module, or `n/a — no code touched`>

Guides: <the user guide (user-visible change) and the operator guide (configuration or operational change) updated in this PR, or `none`>

Neutrality: <mechanical scan result (`pre-commit run --all-files`), naming whether the denylist hook scanned real terms or reported skipping (a reviewer can't tell "checked clean" from "checked nothing" otherwise), and the fresh context-free reviewer's read-through result (findings resolved or explained, or "none raised")>

Door: <one-way or two-way>. Blast radius: <one word, then a line if it needs one>

Review: Standards: <performer, tier[, model], clean-context> — <what the axis found and how it was addressed, or `n/a (light gate: <reason>)`>. Spec: <performer, tier[, model], clean-context> — <same, against the design doc slice or the issue>. Self-review: <performer, tier, clean-context or the builder's own> — <parts covered; found/addressed>.
