# Engineering principles

The standing rules every design and code change in this project has to respect, each with why it holds and what enforces it.
A principle is wider than one decision (that's an ADR in `docs/adr/`) and isn't vocabulary (that's `CONTEXT.md`).
Strength markers follow the **Never** / **Default** convention in `.forge/never-default.md`.
A new, reworded or removed principle lands only once the owner has approved its exact wording; `.agents/skills/domain-modeling/` maintains this file, in the shape its `PRINCIPLES-FORMAT.md` sets.

## Public-ready at all times (Never)

**Principle:** Every file committed to TheForgeStaging's working tree must be safe to copy, byte for byte, into the public TheForge repository at any moment — nothing here may depend on a later redaction pass before publishing.

**Why:** the publish scan is a backstop, not a guarantee: a term the denylist doesn't list still reaches the public repository, so the tree has to be safe when it is committed.

**Enforcement:** `scripts/check-denylist.sh`/`check-no-issue-refs.sh` pre-commit hooks and `scripts/check-denylist-not-shipped.sh`, plus review (`code-review` Standards axis, the fresh-reviewer read-through) for what no grep can catch.

## TheForge governs itself, on a lag (Default)

**Principle:** TheForge holds its own commits to the same process discipline it donates to downstream repos, propagated to itself only when the owner invokes a sync — never automatically.

**Why:** ADR-0009 settled TheForge as a standing consumer of its own template rather than an exempt maintainer-only tree; the lag is deliberate, since syncing automatically would turn every template commit into an uncontrolled propagation to every downstream repo.

**Enforcement:** ADR-0009/ADR-0010 are the decisions; this repository's own post-merge review routine and tracked forge-sync cadence are the mechanism; review only beyond that.

## Structured for easy downstream updates (Default)

**Principle:** Every forge-owned file is structured so a downstream project's own update absorbs new TheForge content with the least possible manual conflict resolution, and never touches content that project owns.

**Why:** a rewrapped paragraph conflicts a downstream project even when nothing substantive changed, and project-owned content isn't the forge's to overwrite in the first place.

**Enforcement:** ADR-0002 (project/forge separation) and ADR-0006 (single entrypoint) are the decisions; `scripts/check_one_sentence_per_line.py` and `_skip_if_exists` are the mechanism; review only beyond that.

## Opinionated about its own utilities, agnostic about what they build (Default)

**Principle:** TheForge may be opinionated about the tech stack behind its own tooling, but the process it ships makes no assumption about the language, framework or stack of the project it's applied to.

**Why:** `test_command`, `lint_command`, `setup_command` and the size caps are answers a project supplies, not something hardcoded; a forge that only worked for one stack would stop being a donation and become a rewrite demand.

**Enforcement:** Review only — a skill or guard that assumes a specific downstream language or tool, rather than reading it from the project's own answers, is a finding.

## Agnostic to the agentic harness, as far as the owner can test (Default)

**Principle:** Every forge-owned rule, skill and process file is written to work under any agentic harness that can read it, not just Claude Code, to the extent the owner is actually able to verify that.

**Why:** tying TheForge to one agentic coding vendor would narrow who it's useful to; the goal is to stay as broadly useful as practical across vendors.

**Enforcement:** Review only — a rule or skill phrased in Claude-Code-specific terms without a documented fallback is a finding; `.forge/model-tiers.md`'s "Other harnesses" section is where each tested harness's model mapping is recorded.

## Don't repeat yourself, wherever practical (Default)

**Principle:** Where the same rule, fact or behaviour would otherwise have to be written and kept in sync in more than one place across TheForge's own files, it's stated once and the other place points at it, rather than duplicating it.

**Why:** a duplicated statement drifts the moment one copy is edited without the other.

**Enforcement:** Review only (`code-review` Standards axis) — a change that writes the same rule, fact or behaviour in two independent places with neither deriving from nor pointing at the other is a finding; a mechanical guard is added for a specific recurring shape only once one has actually recurred, the same escalation path `.forge/code-shape-rules.md` uses for "Adopt the abstraction early, then stay on it".

## Efficient with model costs (Default)

**Principle:** Coordinators and agents are to be efficient with respect to model costs, by using (and being instructed to use) models that are no more capable than necessary for the task, and by ensuring instructions and skills are no more verbose than necessary to ensure clear direction.

**Why:** model capability and instruction length are both paid for on every run; a more capable model than the task needs, or a longer instruction than clear direction needs, multiplies that cost across every thread and every reader.

**Enforcement:** Review only (`code-review` Standards axis); `.forge/model-tiers.md` is the mapping from task to the least capable sufficient tier.

## Release-note labels reflect what a consumer must act on (Default)

**Principle:** A change a consumer must act on after syncing is labelled release:integrator.

**Why:** two separate post-merge review findings (a re-paste file, new Copier questions, a new label `forge-sync` will not create) recorded integrator-facing changes as `release:internal`, which would have silently hidden them from the next consumer's release notes.

**Enforcement:** Review only (`code-review` Standards axis); `docs/agents/triage-labels.md`'s "Release-note labels" table is the operative label definitions and the pre-merge re-check step this principle backs.
