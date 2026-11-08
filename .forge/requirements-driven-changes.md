# Requirements-driven changes

`docs/requirements/requirements-specification.md` is the contract for what this project does.
Every change is traced to it, and only the owner changes the wording of a requirement.

Requirements are numbered `FR-NNN` (functional) and `NF-NNN` (non-functional), each with one "shall" statement and a status: Satisfied, Partially Satisfied or Not yet Satisfied.
The specification also keeps a known-gaps table and a traceability matrix.

Approval applies to requirement wording, not to the file.
The owner approves a PR touching the specification only when it changes the wording of a "shall" statement: a new, reworded or removed requirement.
A PR that touches the file without touching any requirement's wording (a stale cross-reference, a typo, a status change, reformatting) self-merges like any other docs PR.

## 1. Every PR names its requirements

The PR body follows `.github/pull_request_template.md`, whose `Requirements:` line lists the requirement IDs the change implements, restores or affects, for example `FR-001, NF-004`.
Internal work with no behaviour a requirement describes (refactors, CI, tooling, docs) says `Requirements: none (internal)`.
Tickets from `to-tickets` and `triage` carry the IDs too.

The template's other evidence lines are filled in on every PR, because with self-merge as the gate they are the only record of those facts.
`Evidence:` is the command that went red then green, and for a guard test the run with the guard removed.
For a fix to a finding or bug, `Evidence:` also lists, by name, the other members of the class the fix checked, and the source that list came from (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line").
`Tests:` is the scoped test commands run and whether coverage of the touched modules held.
`Door:` is one-way or two-way, with the blast radius.
`Review:` is who reviewed, at which tier.

## 2. A requirement change is its own PR, and the owner approves it once

If the work needs a new, reworded or removed requirement, open a spec-only PR for that first, once the work has started.
Wording approved while capturing a ticket waits in the ticket until the owner starts the work (`.forge/tickets-and-branches.md`, "A ticket request is capture only").
Ask the owner to approve its wording, with the request linking to the PR's diff and quoting or summarising the wording inline (`.forge/feature-pipeline.md`, "Every approval request links to the wording it asks about").
Once the owner's explicit approval of that linked wording is recorded on the PR, merge it (`.forge/process-and-evidence.md`, "What needs the owner's approval before a merge").

The one exception: a spec-only PR whose wording is verified identical to wording the owner already explicitly approved on the originating issue may merge without a second approval, citing the approval comment it matches verbatim.

Once the spec-only PR merges, the agent that opened it posts the merge's pending post-merge-review note on the tracker, in the form `.agents/skills/post-merge-review/SKILL.md`, "Pending reviews", gives.

The implementation PR does not merge until every requirement it cites exists on `main` with the wording it implements.
A bug fix that restores an existing requirement, or a status change that only records what the code now does, needs no approval: update the status in the same PR.

## 3. A change never silently breaks a requirement

Before merging, check the diff against every requirement it touches, not just the ones it cites; the code review's Spec axis does this.
If the change would make a Satisfied requirement untrue, do not merge it as is.
Either fix the change, get the owner's approval for a requirement change, or file an issue for the break and downgrade the requirement's status in the same PR.
A requirement that becomes satisfied gets its status and known-gaps row updated in the same PR.

## Tests carry requirement IDs

A test that proves a requirement carries the requirement's ID as a machine-readable marker, so the requirement-to-test map can be generated rather than maintained by hand.
`docs/agents/requirement-coverage.md` describes the convention.
