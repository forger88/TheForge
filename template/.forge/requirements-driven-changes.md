# Requirements-driven changes

`docs/requirements/requirements-specification.md` is the contract for what this project does: every change is traced to it, and only the owner changes a requirement's wording.

Requirements are numbered `FR-NNN` (functional) and `NF-NNN` (non-functional), each with one "shall" statement and a status: Satisfied, Partially Satisfied or Not yet Satisfied.
The specification also keeps a known-gaps table and a traceability matrix.

Approval applies to requirement wording, not to the file.
The owner approves a PR touching the specification only when it changes a "shall" statement's wording: a new, reworded or removed requirement.
Any other change to the file (a stale cross-reference, a typo, a status change, reformatting) needs no owner approval and merges once its review gate is clear; the specification is a full-gate file (`.forge/review-gate.md`), so that gate is the full gate, whatever the edit inside it reads like.

Every edit to the specification, including a status, Notes, Evidence, known-gaps or traceability change made as a closing step, follows `.agents/skills/requirements-spec/SKILL.md`, which sets the document's form (SDLC-119).
The `requirements-evidence` pre-commit hook (`scripts/check_requirements_evidence.py`) checks its Evidence paragraphs.

## 1. Every PR names its requirements

The PR body follows `.github/pull_request_template.md`, whose `Requirements:` line lists the IDs the change implements, restores or affects (for example `FR-001, NF-004`), or `none (internal)` for work no requirement describes (refactors, CI, tooling, docs).
Tickets from `to-tickets` and `triage` carry the IDs too.

With self-merge as the gate, the template's evidence lines are the only record of these facts, so every PR fills them:
`Evidence:` is the command that went red then green, and for a guard test the run with the guard removed; for a fix to a finding or bug, it also names the other members of the class checked and the source of that list (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line").
`Tests:` is the scoped test commands run and whether coverage of the touched modules held.
`Door:` is one-way or two-way, with the blast radius.
`Review:` is who reviewed, at which tier.

## 2. A requirement change is its own PR, and the owner approves it once

Work that needs a new, reworded or removed requirement first opens a spec-only PR for it, once the work has started; wording approved while capturing a ticket waits in the ticket until the owner starts the work (`.forge/tickets-and-branches.md`, "A ticket request is capture only").
Ask the owner to approve its wording, linking to the PR's diff and quoting or summarising the wording inline (`.forge/feature-pipeline.md`, "Every approval request links to the wording it asks about").
Once the owner's explicit approval of that linked wording is recorded on the PR, merge it (`.forge/process-and-evidence.md`, "What needs the owner's approval before a merge").

The one exception: a spec-only PR whose wording is verified identical to wording the owner already explicitly approved on the originating issue may merge without a second approval, citing the approval comment it matches verbatim.

Once the spec-only PR merges, the agent that opened it posts the merge's pending post-merge-review note on the tracker, in the form `.agents/skills/post-merge-review/SKILL.md`, "Pending reviews", gives.

The implementation PR does not merge until every requirement it cites exists on `main` with the wording it implements.
A bug fix restoring an existing requirement, or a status change recording what the code now does, needs no approval: update the status in the same PR.

## 3. A change never silently breaks a requirement

Before merging, check the diff against every requirement it touches, not just those it cites; the code review's Spec axis does this.
A change that would make a Satisfied requirement untrue does not merge as is: fix the change, get the owner's approval for a requirement change, or file an issue for the break and downgrade the status in the same PR.
A requirement that becomes satisfied gets its status and known-gaps row updated in the same PR.

## Tests carry requirement IDs

A test that proves a requirement carries its ID as a machine-readable marker, so the requirement-to-test map is generated, not hand-maintained (`docs/agents/requirement-coverage.md`).
