# Architecture decision records

One record per significant decision, numbered sequentially: `0001-<slug>.md`, `0002-<slug>.md`, and so on.
The format, and the test for when a decision deserves a record (hard to reverse, surprising without context, the result of a real trade-off), are in `.agents/skills/domain-modeling/ADR-FORMAT.md`.

An ADR is a record, so unlike the rest of `docs/` it narrates the context and the alternatives that led to its decision.
Other documents cite an ADR by its number instead of repeating its reasoning.
A review finding rejected for a load-bearing reason is recorded here too, so a later pass does not raise it again (SDLC-087).

ADRs are drafted as text in the stage 3 design comment and land as files with the stage 5 design doc (`.forge/feature-pipeline.md`).
To change a decision, write a new ADR that supersedes the old one, and mark the old one's status `superseded by ADR-NNNN`; never rewrite an accepted record's decision in place.

A `research` findings file that informed an ADR is committed next to it as `docs/adr/NNNN-<slug>.research.md`, with the ADR's "Considered Options" summarising and linking it; findings that informed no ADR instead go next to the design doc as `docs/design/<slug>.research-<topic>.md`. Findings are never left only in a comment or on a throwaway branch.

No decisions recorded yet.
