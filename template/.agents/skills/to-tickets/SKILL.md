---
name: to-tickets
description: Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking edges, published to the configured tracker (edges as text in one file per ticket locally, or native blocking links on a real tracker).
disable-model-invocation: true
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/engineering/to-tickets/SKILL.md @ 321658273c (2026-08-19), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

# To Tickets

Break a plan, spec, or conversation into a set of **tickets**: tracer-bullet vertical slices, each declaring the tickets that **block** it.

The issue tracker and triage label vocabulary are in `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`. If either is missing, tell the user to run stage 0 (`.forge/feature-pipeline.md`).

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a reference (a spec path, an issue number or URL) as an argument, fetch it and read its full body and comments.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code. Ticket titles and descriptions should use the project's domain glossary vocabulary, and respect ADRs in the area you're touching.

Look for opportunities to prefactor the code to make the implementation easier. "Make the change easy, then make the easy change."

Before drafting a ticket, search the codebase and the tracker for an existing implementation of the behaviour by domain concept, not by the request's wording, and say in the ticket where you looked. A ticket for work that already shipped costs a thread the time to rediscover that it shipped, so the check is part of drafting, not of the build.

### 3. Draft vertical slices

Break the work into **tracer bullet** tickets.

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is demoable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Any prefactoring should be done first

</vertical-slice-rules>

Give each ticket its **blocking edges**: the other tickets that must complete before it can start. A ticket with no blockers can start immediately.

Write each ticket's acceptance criteria and "done"/"checks before merge" language as "run the tests near the change; coverage of the touched modules must not drop" — never as a CI/Actions dispatch, a full-suite run, or a review beyond the standing self-review gate (see `.forge/ci-and-checks.md`, "A ticket's own checks": a Default, overridable only by an explicit line on that specific ticket when the work genuinely needs it, e.g. a migration that can only be validated against a real harness).

A ticket that fixes a finding or bug also asks, in its acceptance criteria, for the fix PR's `Evidence:` line to list by name the other members of the finding's class it checked, and the source that list came from (the code that handles the cases, or the list, schema or specification that defines them), not only the examples the ticket names.

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change (rename a column, retype a shared symbol) whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand–contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket; green is promised only there.

### 3a. Cross-check the design doc's module map and build-vs-buy rows

This step runs only when the source is a feature-pipeline stage-5 design doc. For any other source (an ad hoc plan, a conversation, a whole-feature-in-one-ticket breakdown with no design doc), write "n/a, not a design doc" and move on to step 4.

Walk the design doc's module map and build-vs-buy table and build a claims table, one line per row, in the form `row → claiming slice(s), or ORPHAN`:

- **Module-map rows: mechanical.** A row is claimed when its path appears in at least one slice section's file scope or "What to build"/behaviour text. Match the path verbatim after normalising each side: strip a leading `template/`, strip a `.jinja` suffix, and ignore backticks. A slice may also claim a row through a directory or glob in its file scope that covers the path. A bare mention in another slice's "out of scope" or "Blocked by" text does not count.
- **Build-vs-buy rows: judgement.** A row is claimed when a slice's "What to build", behaviour, interface or file scope states the work that puts the row's *choice* into effect: the install, the wiring, the flag, the env var, the call. Naming the library in passing does not count. A row whose choice needs no build work of its own (a library adopted entirely inside a module some slice already builds, or carried forward unchanged) is recorded as "claimed via Slice N's `<module>`" or "no build work: `<reason>`" — it is never left blank.
- **Named-hook column (secondary).** If a module-map row's named hook appears in no slice's interface, add a note to the table; this is not an orphan and does not block filing.

On any orphan, stop before step 5 publishes anything. Report the orphans to the thread that ran stage 6 (normally the design thread itself); if that thread is gone, report to the coordinator, who briefs a design thread. The design thread resolves each orphan with a stage-5 doc amendment: add the work to a slice's scope, add a slice, or delete the row as no longer intended. Never guess an orphan into a slice. This is the same "send it back to stage 5" rule as the carve-out in step 5 below.

Once there are no orphans, post the claims table as one comment on the feature issue before publishing anything in step 5 — it is the evidence this check ran, and stage 8 reads it.

Step 4's stage-6 skip (the "skip this step" note for a design doc's own slices) does not skip this step: run 3a even when step 4 itself is skipped.

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each ticket, show:

- **Title**: short descriptive name
- **Blocked by**: which other tickets (if any) must complete first
- **What it delivers**: the end-to-end behaviour this ticket makes work

When this runs against a design doc at feature-pipeline stage 6 (by default as a sub-agent of the design thread that wrote the doc), skip this step: the slices are the doc's own (one slice, one ticket), and the owner's "ticket it" was the go-ahead.

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the blocking edges correct: does each ticket only depend on tickets that genuinely gate it?
- Should any tickets be merged or split further?

Iterate until the user approves the breakdown.

### 5. Publish the tickets to the configured tracker

Publishing tickets is capture only (`.forge/tickets-and-branches.md`, "A ticket request is capture only"): put agreed content, including owner-approved requirements wording, in the tickets and change nothing in the repo until the owner says to start.

Publish the approved tickets. **How** depends on the tracker `docs/agents/issue-tracker.md` describes; the tickets are the same either way, only the shape of the blocking edges changes:

- **Local files** → write one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in dependency order (blockers first). Each file's "Blocked by" lists the numbers/titles it depends on. Use the per-ticket file template below: one ticket per file, never a single combined file.
- **A real issue tracker (GitHub, Linear, …)** → publish one issue per ticket in dependency order (blockers first) so each ticket's blocking edges can reference real identifiers. Use the platform's native blocking / sub-issue relationship where it has one; otherwise set each ticket's "Blocked by" to the blocking issues. Apply `ready-for-build` or `ready-for-structure` (unless instructed otherwise) by these routing criteria — route to `ready-for-structure` if any apply, otherwise `ready-for-build`:
  1. The ticket's change touches at least one existing module with real branching logic: new code lands inside or alongside existing logic, not as a standalone new file.
  2. It adds, renames, or changes the meaning of a field in a data shape (a dict, a DB row, an API body, a message) that is built or read independently elsewhere.
  3. It needs a new seam or adapter — for example to isolate a raw third-party interface, or add a new Protocol or port.
  4. Two or more structurally different implementations would look the same from outside, especially where nearby code or the design doc shows this has broken before (a hazard note).
  5. It touches the security surface: a new or changed endpoint, command, message type or other input path; an authentication, authorisation or permission check; secrets or credentials; a new external call or trust boundary; data newly stored, logged, exported or shown to another user; file handling; or a control `docs/security/threat-model.md` or another `docs/security/` doc names.

  On any doubt, route to `ready-for-structure`: a spurious design pass is cheap, and the structural debt a wrong guess leaves behind is not.

  **Carve-out for a build slice of an already-approved stage-5 design.** A ticket that is a build slice of an already-approved detailed design doc (feature pipeline stage 5) defaults to `ready-for-build` regardless of whether criteria 1-5 above would otherwise match its subject matter: the design doc already did what a design-exit pass exists to produce. The carve-out is narrow, and it is not a route to `ready-for-structure`: if a slice's own design-doc section left the specific structural or security question a criterion raises open or ambiguous, send the ticket back to stage 5 instead of routing it to a design-exit pass for nested design inside the one ticket — amend the design doc to decide the open question, and re-slice the ticket from the corrected doc if the answer changes its shape (`docs/agents/triage-labels.md`, "Routing criteria").

  Either way the tickets are agent-grabbable by construction (`ready-for-structure` tickets pick up their design-exit pass via `implement-with-merge` step 0a, `docs/agents/triage-labels.md`). Also apply release-note labels to each ticket (`release:user` and/or `release:integrator`, or `release:internal` alone, plus `breaking` when it applies; `docs/agents/triage-labels.md`, "Release-note labels"), chosen from what the ticket delivers, not from the feature as a whole: a feature's backend slice may be `release:internal` while its UI slice is `release:user`.

  On a real issue tracker, once every ticket is filed, start a mechanical-tier sub-agent to re-read every newly filed ticket's labels back and confirm each carries the one state label this step just decided for it, rather than trusting the filing write uncorroborated (`docs/agents/triage-labels.md`, "Mechanical label sync after design-type work"); fix any mismatch it reports before moving on. Local files need no such check: writing the file and the label into it is the same action.

Work the **frontier**: any ticket whose blockers are all done. For a purely linear chain that means top to bottom.

Do NOT close or modify any parent issue.

If this ticket-and-queue is stage 6 of a feature's pipeline (`.forge/feature-pipeline.md`: the source was a design doc produced by that pipeline's stage 5, not an ad hoc plan), read `.agents/skills/feature-pipeline/SKILL.md` and follow job (b) right after publishing the build slices above, so the post-merge review pass and architecture-pass tickets get filed in the same pass as the build slices, not forgotten until a later catch-up.
That job ticks one checklist line on the feature's own tracker issue (which is this ticket set's parent when the source was a design doc); that single edit is the explicit exception to "do not modify any parent issue" above.
That rule protects the parent from being resolved or rewritten out from under its children, not from `feature-pipeline`'s own checklist line on it.
`feature-pipeline` lives under `.agents/skills/`, so it may not be available through the harness's skill listing: read it directly; there's no tool invocation for it.

<local-ticket-template>

# <NN>: <Ticket title>

**What to build:** the end-to-end behaviour this ticket makes work, from the user's perspective, not a layer-by-layer implementation list.

**Blocked by:** the numbers/titles of the tickets that gate this one, or "None (can start immediately)".

**Request-trace:** the request this ticket serves, only when it isn't already evident from this ticket's own "Blocked by" or parent and a real request actually exists to record (`.forge/tickets-and-branches.md`): the parent ticket, a link to the owner's direction, or the standing policy's statement ID. Omit this line entirely otherwise — never fill it with a guess.

**Status:** ready-for-build (or ready-for-structure — see the routing criteria above)

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
- [ ] Before merge, the release-note labels are re-checked against the diff and the PR's `Release note:` field is filled to match, each bullet ending with its issue number.

</local-ticket-template>

<issue-template>

## Parent

A reference to the parent issue on the tracker (if the source was an existing issue, otherwise omit this section).

## Request-trace

Only when the request isn't already evident from this ticket's "## Parent"/"Blocked by" section and a real request exists to record (`.forge/tickets-and-branches.md`): the parent ticket, a link to the owner's direction, or the standing policy's statement ID. Omit this whole section otherwise.

## What to build

The end-to-end behaviour this ticket makes work, from the user's perspective, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Before merge, the release-note labels are re-checked against the diff and the PR's `Release note:` field is filled to match, each bullet ending with its issue number.

## Blocked by

- A reference to each blocking ticket, or "None (can start immediately)".

</issue-template>

In either form, avoid specific file paths or code snippets: they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it and note briefly that it came from a prototype. Trim to the decision-rich parts, not a working demo, just the important bits.
