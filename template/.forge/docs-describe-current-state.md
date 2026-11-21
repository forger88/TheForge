# Docs describe current state, not history

Architecture, requirements and security docs under `docs/` describe how things are now, plus the open gaps, never an evolution story.

No "proposed splits", narratives of resolved gaps, "earlier versions of this doc said X", renumbering history, or language implying a decision awaits an outside party's sign-off.
A decision made in this repo, by an ADR or the owner's direction, is authoritative on its own and stays revisable.
Cite the ADR as a decision's source instead of narrating how it was reached.
Mark an unaddressed gap "Open gap" with a tracking issue, never an apology or bare TODO.

ADR bodies, release notes, the decisions log and archived documents are records, so they do narrate what was decided, changed or retired, and why.

## Why

Picture a document on a service's caching layer that narrated three successive redesigns, rather than the layer as it stands: each reader would have to work through all three to find the current one, with what an integrator needs (what is cached, for how long, how it is invalidated) buried in the third.

## Where things go instead

- Current-system detail: the architecture description at summary level, or a subsystem design doc for detail.
- Engineering principles: `docs/principles.md`.
- A decision's rationale: an ADR.
- Feature design: `docs/design/`.
- Domain vocabulary: `CONTEXT.md`, a pure glossary of a term, a one- or two-sentence definition, and an `_Avoid_:` line where a synonym needs ruling out.
  No file paths, issue history, status notes, configuration keys or UI mechanics.

## A document stays true

A change that makes a document untrue updates that document in the same PR.
