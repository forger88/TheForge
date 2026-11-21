---
name: requirements-spec
description: Sets the form of docs/requirements/requirements-specification.md, and rewrites or updates it from the current code, docs and tests, marking each requirement's real-world status. Use for any edit to that file (a status, Notes, Evidence, Known gaps or Traceability change, or a closing step), or when asked to refresh, audit or rewrite it, or check it against current main.
---

# Requirements specification

## What this produces

One file, updated in place: `docs/requirements/requirements-specification.md`; never a second, differently-named spec file.

The document is **slim and readable**: short tables of one-line requirements, each with a status, saying what the project must do and whether it does it now.
It is not a design description: the architecture description, subsystem design docs, `docs/design/` and the ADRs carry the how and the why.

This skill sets the specification's form (SDLC-119; `.forge/agent-skills-and-reference.md`, "Artefacts and the skills that govern them") for every edit to the file, not only a full rewrite.
The spec's own "Conventions" section restates these rules and may add the project's own choices, such as its ID blocks, but never contradicts them; where the two disagree, this skill wins and the Conventions section is fixed in a ticketed docs PR.

### Structure

TheForge seeds six sections; keep them, in this order:

1. **Conventions**: IDs, wording, statuses, evidence, and what happens when a change would break a requirement.
2. **Scope**: what the project is for and who uses it, in two or three sentences, then a short bulleted list of what is in scope.
   Where an external dependency (an identity provider, a model provider, a host application, a third-party API) does part of a job, add a delegation table: one row per capability (or capability flag) with something delegated, giving what the user gets, what this project is responsible for, and what is delegated.
3. **Functional requirements**: one subsection per feature area.
4. **Non-functional requirements**: one subsection per quality area the project needs (security, reliability, concurrency, performance, observability, deployment, accessibility, privacy).
5. **Known gaps**: one table of every requirement not fully Satisfied, with what is missing and its tracking issue; no narrative.
6. **Traceability**: one row per area, giving its requirement range and the test files that exercise it (`docs/agents/requirement-coverage.md` says when a per-requirement map generated from test markers replaces it).

A larger project can add sections in a ticketed docs PR, keeping the six above: external interfaces pointing at the architecture description's protocol sections; data requirements (what the project stores and never stores); constraints, assumptions and out of scope (what the project itself does not do, not what this document leaves out).

### Requirement tables

```
| ID | Requirement | Status | Notes |
|---|---|---|---|
| FR-001 | The system shall authenticate every non-public request. | Satisfied | |
```

- **IDs** are `FR-NNN` (functional) or `NF-NNN` (non-functional), grouped by area in blocks the Conventions section sets.
  An ID is never reused, and a removed requirement's ID stays retired, because PRs, tickets and test markers cite IDs and a reused one silently re-points every old citation.
- **Requirement**: one atomic, testable "shall" sentence stating the **effect** the system must have, not the mechanism.
  No implementation detail, file names, library or algorithm choice, internal step, history or rationale: those belong in the architecture description, a design doc or an ADR, cited from Notes.

  | How (wrong) | Effect (right) |
  |---|---|
  | The system shall use a Redis-backed sliding-window counter to reject a request once a client exceeds 100 requests per minute. | The system shall reject a client's request once it exceeds 100 requests per minute. |

  A test can check the effect wording without reading the implementation; the mechanism wording would force a wording change, and an owner approval, on a later swap of store or algorithm that leaves the contract untouched.
- **Status**: `Satisfied`, `Partially Satisfied` or `Not yet Satisfied`, as the Conventions section defines them; any status other than Satisfied has a Known gaps row with a tracking issue.
- **Notes**: a pointer only (the Known gaps row, a tracking issue, an ADR ID), never prose.
- **Evidence** only for critical behaviours (authorization, approval boundaries, isolation, fail-closed paths), new and existing alike.
  It is a short paragraph after the table: the bold label `**Evidence:**` or `**Evidence (<requirement IDs>):**`, then backticked repo-relative paths, comma-separated, of the files of any kind that implement or prove the behaviour (code, tests, ADRs, design docs, the user or operator guide).
  File level only: no symbol, function, line or test name, no issue or PR number, no date, no history and no "How:" or other prose; how a file does it belongs in the architecture description or a design doc, which Evidence may name.
  `scripts/check_requirements_evidence.py` (the `requirements-evidence` pre-commit hook) checks this shape and that every path exists.
  Test markers and the traceability table cover everything else.

  Example:

  > **Evidence (FR-001):** `src/auth/middleware.py`, `tests/test_auth_middleware.py`, `docs/adr/0003-session-tokens.md`

### What never goes in the document

- How a requirement used to be satisfied, earlier passes, "new findings from this pass", or superseded wording (`.forge/docs-describe-current-state.md`).
- Requirements for retired subsystems: retire them (their IDs stay retired) rather than keeping dead rows.
- References to prototypes, spikes or proof-of-concept code.
- Caveats that something awaits consultation or approval from an external party: decisions recorded in this repo are authoritative.

## Wording versus status

Only the owner changes a requirement's wording (`.forge/requirements-driven-changes.md`).
A requirement this skill finds missing, mis-worded or obsolete is a proposed wording change, not an edit:

- **Status, Notes, Known gaps and Traceability updates** that only record what the code does now need no owner approval and merge once their review gate is clear; the specification is a full-gate file (`.forge/review-gate.md`), so that gate is the full gate.
- **A new, reworded or removed requirement** goes into its own spec-only PR that the owner approves, the request linking to the PR's diff and quoting the wording inline.
  Wording the owner approves while a ticket is captured stays quoted in that ticket until the owner says to start; the spec-only PR then cites it (`.forge/tickets-and-branches.md`, "A ticket request is capture only").

So a full rewrite usually produces two PRs: the status-only one, and a spec-only one carrying every proposed wording change for approval.

## Verification discipline

- Read the actual current code for every requirement; don't infer behaviour from a name, a comment or the document's previous version.
- Don't assume symmetry: check create, update and delete paths separately.
- Cross-reference both ways: every requirement to its code, and every shipped feature to a requirement.
- If reading the code doesn't settle a status, keep reading (or delegate a focused check) until it does; don't publish an "ambiguous" status.
- Check every file the document names exists: the Evidence hook checks Evidence paths; check Notes and Traceability paths by hand.
- Keep working notes outside the document.

## Gathering context

1. Read the existing spec in full.
2. Read `CONTEXT.md`, the architecture description (especially its open gaps), any subsystem design docs, and the ADRs for each area.
3. If the project has capability or feature flags, read the current list where they are defined (the shipped config defaults and the code that reads them), on every run; never trust a list copied into this skill or an earlier spec.
4. For each area, read the implementing code end to end (the entry point or handler, any UI component or store, and the tests).

## Finishing

- Update the Known gaps and Traceability tables to match the requirement tables.
- Update any document index the project keeps (a docs index or the README's docs list) if the spec's row there changed.
- Run the project's documentation consistency checks (its docs lint, link checker, or requirement-ID citation check), and grep the repo for every ID you retired (`grep -rnE '\b(FR|NF)-[0-9]+\b'`) so no citation points at a retired requirement without saying so.
