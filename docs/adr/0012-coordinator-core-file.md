# ADR-0012: One coordinator-core file, loaded by the coordinator alone, replaces the generated condensed copy

**Status:** accepted; supersedes ADR-0011's project-instructions role; constraint 4 superseded by ADR-0013

## Context

The coordinator needs its operating rules at every session start, including in a harness that cannot load the repository's skill files directly.
The harness's project-instruction field is small (16,000 bytes) and is shared with the owner's scope section and standing owner decisions.
Squeezing a generated condensed copy into it lost meaning at every trim, and it carried a second copy of the build-thread brief.
A silently truncated copy is worse than none, because the coordinator acts on half its rules without knowing it.

## Decision

Keep the coordinator's rules in one forge-owned file, `.forge/coordinator-core.md`, that only the coordinator session loads.
The project instructions carry a short snippet, committed in the repository as `docs/agents/coordinator-core-snippet.md`, that tells the coordinator to copy and read that file at every session start and after a context compaction.
Everything else in the project instructions is the owner's: the scope section and the coordinator-notes zone of standing owner decisions.

The constraints below are the owner's.
They must survive every later edit, and changing one means superseding this ADR.

1. One file, `.forge/coordinator-core.md`, forge-owned and donated to every consumer on sync.
2. It holds only what the coordinator must personally act on without looking anything up.
   Build-thread, design-thread and reviewer material stays out.
3. At most 64,000 characters.
4. Trim detection: an instruction at the top, and a codeword marker that appears only on the last line.
   The coordinator reports "Coordinator core instructions re-loaded.
   Proof: codeword <word>" after reading the file, and stops and says so when the marker is missing.
5. Only the coordinator loads it.
   Every other thread keeps reading `CLAUDE.md` and `@.forge/entrypoint.md`.
6. The project-instruction snippet is a repo file and is the source.
   A check fails when the live field drifts from it.
7. The owner's scope section and standing owner decisions stay in the project instructions, and nothing overwrites them.
8. The 30-minute nudge timer is essential.
   With no deferred-wake tool, a helper thread arms it.
   Setup fails loudly.
9. Helper threads with one obvious outcome run at mechanical-tier.
10. The file duplicates its sources on purpose (DRY exemption).
   Every source file carries the forward-reference sentence.

The snippet also carries the owner's sentence for a coordinator that has lost track of the codeword: it reloads the core before doing anything else.

## The guard for each constraint

The tests are in `template/scripts/test_check_coordinator_core.py` (run here directly, by `template-scripts-tests`; it no longer syncs to a generated project); the checks are `scripts/check_coordinator_core.py` subcommands run by pre-commit hooks.

| Constraint | Guard |
|---|---|
| 1 | `ConstraintGuards.test_constraint_1_core_is_synced_through_the_entrypoint` |
| 2 | Review only: "only what the coordinator acts on" is a judgement, not a shape |
| 3 | `shape` (the `coordinator-core` hook); `ShapeTests.test_size_limit_is_inclusive` |
| 4 | `shape`, `rotated`; `ShapeTests` (truncated core, marker not last, missing guard instruction, codeword leaked above the marker) and `RotatedProblemsTests` |
| 5 | `ConstraintGuards.test_constraint_5_snippet_keeps_the_coordinator_only_wording` |
| 6 | `drift`; `DriftTests` |
| 7 | `notes`; `NotesCheck` (a dropped, reworded or missing live zone fails closed) |
| 8 | `ConstraintGuards.test_constraint_8_core_keeps_the_timer_helper_and_fails_loudly_sentences` |
| 9 | `ConstraintGuards.test_constraint_9_core_keeps_the_mechanical_tier_helper_sentence` |
| 10 | Review only: that the file duplicates its sources on purpose is the DRY exemption, a judgement about which duplication is allowed |

The root-only `lock` check guards the core against drift from the shared sources it condenses; it is not one of the constraints' guards and is not shipped to consumers.

Constraints 2 and 10 are review-only, so the code-review Standards axis checks any diff touching the core or the snippet against this ADR.
The bootstrap checklist step that tells a new project to paste the snippet is guarded too (`ConstraintGuards.test_bootstrap_checklist_pastes_the_snippet_not_the_retired_generator`).

## Consequences

- ADR-0011's project-instructions role is superseded: the project instructions are the owner's scope section, the notes zone and the snippet, not text composed from member repositories.
- The condensed generator and the composer were retired once the core became the coordinator skill's authoritative text; the repository holds no generated project-instructions text any more.
- A change to a constraint is deliberate, because it needs a new ADR that supersedes this one.
- The owner's notes are protected by a fail-closed check (`notes`) that the coordinator runs before every write to the project instructions.
