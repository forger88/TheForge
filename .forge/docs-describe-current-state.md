# Docs describe current state, not history

Architecture, requirements and security docs under `docs/` describe how things are now, plus the open gaps, never an evolution story.

Do not write "proposed splits", a narrative of gaps that were resolved, "earlier versions of this doc said X", renumbering history, or language implying a decision is waiting on sign-off from an outside party.
A decision made in this repo, by an ADR or by the owner's direction, is authoritative on its own, and every decision stays revisable later.
Cite ADRs as the source of a decision instead of narrating how it was reached.
Mark an unaddressed gap as "Open gap" with a tracking issue, never as an apology or a bare TODO.

ADR bodies, release notes, the decisions log and archived documents are the exceptions: each is a record, so it narrates what was decided, changed or retired, and why.

## Why

Picture a document describing a service's caching layer that, over a year, narrated three successive redesigns in order instead of describing the caching layer as it stands today.
A new reader had to read all three to work out which one was current, and the one fact an integrator needed (what is cached, for how long, and how it is invalidated) was buried in the third.
The document doubled in length and stopped being useful to the people it was written for.

## Where things go instead

- Current-system detail goes in the architecture description, at summary level, or in a subsystem design doc for detail.
- Engineering principles go in `docs/principles.md`.
- The rationale for a decision goes in an ADR.
- Feature design goes in `docs/design/`.
- Domain vocabulary goes in `CONTEXT.md`, which is a pure glossary: a term, a one- or two-sentence definition of what it is, and an `_Avoid_:` line where a synonym needs ruling out.
  It carries no file paths, issue history, status notes, configuration keys or UI mechanics.

## A document stays true

A change that makes a document untrue updates that document in the same PR.
