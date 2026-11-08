---
name: requirements-spec
description: Rewrite or update this project's living requirements specification (docs/requirements/requirements-specification.md) by reversing requirements out of the current code, docs, and tests, and marking each one's real-world status. Use when asked to refresh, audit, or rewrite the requirements spec, or to check it against current main.
---

# Requirements specification

## What this produces

One file, updated in place: `docs/requirements/requirements-specification.md`.
Never create a second, differently-named spec file.

The document is **slim and readable**: short tables of one-line
requirements, each with a status. It states what the project must do and
whether it does it now. It is not a design description: the architecture
description, any subsystem design docs, the design docs under
`docs/design/` and the ADRs carry the how and the why.

The spec's own "Conventions" section is authoritative for IDs, wording and
statuses; this skill follows it and never contradicts it. If the two
disagree, the spec wins and this skill's copy is the thing to fix.

### Structure

The template seeds six sections; keep them, in this order:

1. **Conventions**: IDs, wording, statuses, evidence, and what happens
   when a change would break a requirement.
2. **Scope**: what the project is for and who uses it, in two or three
   sentences, then a short bulleted list of what is in scope. Where an
   external dependency (an identity provider, a model provider, a host
   application, a third-party API) does part of a job, a delegation table
   belongs here: one row per capability (or capability flag, if the
   project has them), with what the user gets, what this project is
   responsible for, and what is delegated. Capabilities with nothing
   delegated don't need a row.
3. **Functional requirements**: one subsection per feature area.
4. **Non-functional requirements**: one subsection per quality area
   (security, reliability, concurrency, performance, observability,
   deployment, accessibility, privacy), as the project needs them.
5. **Known gaps**: one table of every requirement not fully Satisfied,
   with what is missing and its tracking issue. No narrative.
6. **Traceability**: one row per area: requirement range and the test
   files that exercise it (`docs/agents/requirement-coverage.md` says when
   a per-requirement map generated from test markers replaces it).

A project that grows past this can add sections (external interfaces
pointing at the architecture description's protocol sections; data
requirements: what the project stores and what it never stores;
constraints, assumptions and out of scope, where "out of scope" means
what the project itself does not do, not what this document leaves out).
Add them in a ticketed docs PR, and keep the six above.

### Requirement tables

```
| ID | Requirement | Status | Notes |
|---|---|---|---|
| FR-001 | The system shall authenticate every non-public request. | Satisfied | |
```

- **IDs** are `FR-NNN` (functional) or `NF-NNN` (non-functional),
  grouped by area in blocks the spec's Conventions section sets. An ID is
  never reused, and a removed requirement's ID stays retired, because
  PRs, tickets and test markers cite IDs and a reused one silently
  re-points every old citation.
- **Requirement**: one atomic, testable "shall" sentence. No
  implementation detail, file names, history or rationale.
- **Status**: `Satisfied`, `Partially Satisfied` or `Not yet Satisfied`,
  as the spec's Conventions section defines them. A status other than
  Satisfied has its row in Known gaps with a tracking issue.
- **Notes**: a pointer only (the Known gaps row, a tracking issue, an
  ADR ID), never prose.
- **Evidence** only for critical behaviours (authorization, approval
  boundaries, isolation, fail-closed paths): a short bold "Evidence"
  paragraph after the table naming the code and tests. Everything else
  is covered by the test markers and the traceability table.

### What never goes in the document

- How a requirement used to be satisfied, earlier passes, "new findings
  from this pass", or superseded wording (`.forge/docs-describe-current-state.md`).
- Requirements for retired subsystems. Retire them (their IDs stay
  retired) rather than keeping dead rows.
- References to prototypes, spikes or proof-of-concept code.
- Caveats that something awaits consultation or approval from an
  external party. Decisions recorded in this repo are authoritative.

## Wording versus status

Only the owner changes the wording of a requirement
(`.forge/requirements-driven-changes.md`). This skill may find that a
requirement is missing, mis-worded or obsolete; that finding is a
proposed wording change, not an edit:

- **Status, Notes, Known gaps and Traceability updates** that only record
  what the code does now self-merge like any other docs PR.
- **A new, reworded or removed requirement** goes into its own spec-only
  PR that the owner approves, with the request linking to the PR's diff
  and quoting the wording inline. Wording the owner approves while a
  ticket is being captured stays in that ticket, quoted, until the owner
  says to start; the spec-only PR then cites it
  (`.forge/tickets-and-branches.md`, "A ticket request is capture only").

A full rewrite therefore usually produces two PRs: the status-only one,
and a spec-only one carrying every proposed wording change for approval.

## Verification discipline

- Read the actual current code for every requirement. Don't infer
  behaviour from a name, a comment, or what the previous version of the
  document said.
- Don't assume symmetry: check create, update and delete paths
  separately.
- Cross-reference both ways: every requirement to its code, and every
  shipped feature to a requirement.
- If you can't settle a status by reading the code, keep reading (or
  delegate a focused check) until you can. Don't publish an
  "ambiguous" status.
- Check every file, test and symbol the document names exists.
- Keep working notes outside the document.

## Gathering context

1. Read the existing spec in full.
2. Read `CONTEXT.md`, the architecture description (especially its open
   gaps), any subsystem design docs, and the ADRs for each area.
3. If the project has capability or feature flags, read where they are
   defined (the shipped config defaults and the code that reads them) for
   the current list. Re-read it on every run; never trust a list copied
   into this skill or a previous version of the spec.
4. For each area, read the implementing code end to end (the entry point
   or handler, any UI component or store, and the tests).

## Finishing

- Update the Known gaps table and the Traceability table to match the
  requirement tables.
- Update any document index the project keeps (a docs index or the
  README's docs list) if the spec's row there changed.
- Run whatever documentation consistency checks the project has (its
  docs lint, link checker, or a requirement-ID citation check), and grep
  the repo for every ID you retired
  (`grep -rnE '\b(FR|NF)-[0-9]+\b'`) so no citation points at a retired
  requirement without saying so.
