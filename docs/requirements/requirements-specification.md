# TheForge requirements specification

The contract for what TheForge does.
Every change is traced to it: each PR's `Requirements:` line names the IDs it implements, restores or affects (`.forge/requirements-driven-changes.md`).
Only the owner approves a new, reworded or removed requirement, in its own spec-only PR (SDLC-081); statuses follow the code and change in the PR that changes the behaviour.

## 1. Conventions

- **IDs.** Functional requirements are `FR-NNN`; non-functional requirements are `NF-NNN`.
  Group them by area in blocks of a hundred (for example `FR-001`..`FR-099` for the first area, `NF-101`..`NF-199` for performance).
  An ID is never reused; a removed requirement's ID stays retired.
- **Wording.** One "shall" per requirement, short, testable, and stating the effect the system must have, not the mechanism that produces it; implementation detail (a library, an algorithm, an internal step) belongs in the architecture description, a design doc, or an ADR, cited from Notes. For example, write "the system shall reject a client's request once it exceeds 100 requests per minute," not "the system shall use a Redis-backed sliding-window counter to reject a request once a client exceeds 100 requests per minute."
- **Status.** Every requirement carries exactly one status:
  - **Satisfied**: the code does what the requirement says, and a marked test proves it.
  - **Partially Satisfied**: some of it holds; the gap is in §5 with a tracking issue.
  - **Not yet Satisfied**: none of it holds yet; the gap is in §5 with a tracking issue.
- **Evidence.** Only for critical behaviours (authorization, approval boundaries, isolation, fail-closed paths): a short `**Evidence:**` or `**Evidence (<IDs>):**` paragraph after the table, naming the repo-relative files (of any kind) that implement or prove it, file level only, no symbol, line, issue or date (`.agents/skills/requirements-spec/SKILL.md`, SDLC-119).
  `scripts/check_requirements_evidence.py` (the `requirements-evidence` pre-commit hook) checks the shape and that every path exists.
  Tests that prove a requirement also carry its ID as a marker regardless of whether it has an Evidence paragraph (`docs/agents/requirement-coverage.md`).
- **Breaking a requirement.** A PR that would make a Satisfied requirement untrue is fixed, or the requirement is downgraded with a tracking issue in the same PR (SDLC-082); only a wording change needs the owner.

## 2. Scope

<What this project is for and who uses it, in two or three sentences; written once stage 0 and the first grilling interview have settled it.>

## 3. Functional requirements

> **TEMPLATE EXAMPLE TO DELETE.** Delete this example block when the first real requirement lands.
>
> | ID | Requirement | Status | Notes |
> |---|---|---|---|
> | `FR-001` | The system shall let a signed-in user export their overdue invoices as a CSV file. | Not yet Satisfied | §5, tracking #<n> |

| ID | Requirement | Status | Notes |
|---|---|---|---|

## 4. Non-functional requirements

| ID | Requirement | Status | Notes |
|---|---|---|---|

## 5. Known gaps

Every requirement not yet Satisfied, with what is missing and its tracking issue.

| Requirement | Gap | Tracking |
|---|---|---|

## 6. Traceability

A coarse map from each requirement area to the test files that exercise it; the per-requirement map is generated from test markers once there are enough requirements to need one (`docs/agents/requirement-coverage.md`).

| Area | IDs | Test files |
|---|---|---|
