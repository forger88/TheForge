# Triage labels

Instructions here are duplicated, pithily, into `coordinator-core.md` for agent harness that cannot load and handle this instructions file directly.
TheForge's coordinator-core ADR records why that file exists and the constraints that must survive every edit to it.
A change here updates `.forge/coordinator-core.md` in the same change.
TheForge's `lock` check fails until the core section citing this one is re-read and the lock refreshed.

The skills speak in terms of canonical triage roles.
This file maps those roles to the label strings used in this repo's tracker, and defines every other label the process relies on.
`scripts/bootstrap.py` created all of them when the repo was generated; a label added later is added here in the same change.

## State roles

| Canonical role | Label in our tracker | Meaning |
|---|---|---|
| `needs-triage` | `needs-triage` | The owner or a triage pass needs to evaluate this issue |
| `needs-info` | `needs-info` | Waiting on the reporter for more information |
| `needs-grilling` | `needs-grilling` | Accepted as real work, but needs a feature-pipeline stage 2 grilling session before it can carry a ready label; see below |
| `ready-for-agent` (upstream skills) | `ready-for-build` / `ready-for-structure` | Fully specified and ready for an agent; split into two labels, see below |
| `ready-for-feature-design` | `ready-for-feature-design` | A feature tracker whose stage 2 grilling is done and whose stage 3 high-level design hasn't started; see below |
| `ready-for-human` | `ready-for-human` | Requires human implementation |
| `wontfix` | `wontfix` | Will not be actioned |

Category roles are `bug` and `enhancement`.
Every triaged issue carries exactly one category role and one state role.
When a skill mentions a role (for example "apply the agent-ready triage label"), use the corresponding label string from this table.

## `ready-for-build` and `ready-for-structure`

A single "ready" label says only that the behaviour is specified; it says nothing about whether the ticket's structure (which module to extend, which sibling shape to mirror, what seam to add) has been decided.
A build thread left to make its own structural calls makes some of them badly, for example returning a result shape that doesn't match its siblings in the same family.
These two labels separate the two questions:

| Label | Meaning |
|---|---|
| `ready-for-build` | Behaviour specified **and** structure decided. A build can start now. |
| `ready-for-structure` | Behaviour specified, but the ticket needs a design-exit pass first (`implement-with-merge` step 0a) before a build starts. |

`ready-for-structure` renames the label previously called `ready-for-design`, to free that name for the unrelated feature-tracker meaning below (see "`ready-for-feature-design`" and "Retired labels").

**Routing criteria**, applied at `triage` step 5 and `to-tickets`' publish step.
Route a ticket to `ready-for-structure` if any of these apply:

1. The change touches at least one existing module with real branching logic: new code lands inside or alongside existing logic, not as a standalone new file.
2. It adds, renames, or changes the meaning of a field in a data shape (a dict, a database row, an API body, a message) that is built or read independently elsewhere.
3. It needs a new seam or adapter, for example to isolate a raw third-party interface, or to add a new protocol or port.
4. Two or more structurally different implementations would look the same from outside, especially where nearby code shows this has broken before (a hazard note).
5. It touches the security surface:
   - a new or changed endpoint, command, message type or other input path;
   - an authentication, authorisation or permission check;
   - secrets or credentials;
   - a new external call or trust boundary;
   - data newly stored, logged, exported or shown to another user;
   - file handling;
   - a control `docs/security/threat-model.md` or another `docs/security/` doc names.

Otherwise the ticket goes straight to `ready-for-build` (a localised fix or a purely additive new module).
**On any doubt, route to `ready-for-structure`**: a spurious design pass is cheap, and the structural debt a wrong guess leaves behind is not.

These same five criteria are reused by feature-pipeline stage 3's own single-ticket discernment (`.forge/feature-pipeline.md`, "Stage 3 discernment for a whole feature in one ticket, low drift risk"): a stage 3 thread may skip stages 5 and 8 for a whole feature, with no owner decision card, when none of these five apply to it and the whole feature fits in one ticket end to end.
That discernment is whole-feature-only, and distinct from the carve-out below: the carve-out applies to a build slice of an already-approved stage-5 design doc, never to a feature that skips stage 5 and gets no design doc at all.

**Carve-out for a build slice of an already-approved stage-5 design.** A ticket that is a build slice of an already-approved detailed design doc (feature pipeline stage 5) defaults to `ready-for-build` regardless of whether criteria 1-5 above would otherwise match its subject matter: the design doc's module map, interfaces and per-slice threat-model delta already did what a design-exit pass exists to produce. The carve-out is narrow, and it is not a route to `ready-for-structure`: if a slice's own design-doc section left the specific structural or security question a criterion raises open or ambiguous, the ticket is not sent to a design-exit pass for nested design inside the one ticket. Send it back to stage 5 instead — amend the design doc to decide the open question, and re-slice the ticket from the corrected doc if the answer changes its shape.

A ticket carrying `ready-for-structure` moves to `ready-for-build` once its design-exit pass (`implement-with-merge` step 0a, run by a design-tier sub-agent; `.forge/orchestration.md`) has written a **Structure guidance** section into the ticket.
That section binds the build the same way a design-doc slice does, unless the PR records a deviation.

## `ready-for-feature-design`

`ready-for-feature-design` marks a feature's own tracker issue once its stage 2 grilling session has settled its use cases and constraints, but before stage 3's high-level design has started.
It is a **state role**, mutually exclusive with the repo's other state roles (`needs-triage`, `needs-info`, `needs-grilling`, `ready-for-build`, `ready-for-structure`, `ready-for-human`, `wontfix`) — the same shape as `needs-grilling` — never the ticket-level "structure not decided" meaning `ready-for-structure` carries.
It is unrelated to `ready-for-structure` despite the similar name; the two were deliberately kept apart (not folded back into one name) because a consuming project can have open tickets carrying the old `ready-for-design` name in the ticket-level sense, and reusing that name for the tracker meaning would quietly misroute them after a sync.

**Who sets it**: `grill-me`'s stage 2 exit, in its feature-pipeline branch only (`grill-me`'s generic, non-pipeline use sets no label).

**While it's on**: the tracker is routed to a one-off design-tier stage 3 thread, never to a build thread.
It is **never** auto-queued by the coordinator's default-queue rule (which triggers only on `ready-for-build` or `ready-for-structure`), never labelled `queued`, and never handed to a build thread.
`queue-sweep` check 5 does not flag it as "not queued"; a dedicated check instead lists every open `ready-for-feature-design` tracker with no stage 3 design comment yet, with its age (`queue-sweep`, "Open `ready-for-feature-design` trackers awaiting stage 3").

**Closing it**: the stage 3 design thread removes it the moment it starts work on the tracker, before posting the stage 3 design comment.
Removing it with no stage 3 thread actually starting is a labelling bug, the same class `needs-grilling`'s own closing rule guards against.

### Mechanical label sync after design-type work (Default)

Flipping `ready-for-structure` to `ready-for-build` is a one-obviously-correct-answer task once the design that satisfies the gate has actually been written: there is a label to move and a result to verify, and no judgement left to exercise.
Leaving that flip to the same thread that just finished the design — already deep into that work and about to move on — is how this label is actually found to sit stale on a ticket once its design is done.
A stale `ready-for-feature-design` on a feature's own tracker issue also contaminated `queue-sweep` check 5 ("ready tickets not handed out and not in the queue") before check 5 was scoped to exclude it; the dedicated age listing above is what now watches a tracker sitting unnoticed between stages 2 and 3.

So whichever thread finishes design-type work that satisfies this label's gate does not apply the result itself from memory.
It starts a short-lived **mechanical-tier** sub-agent (`.forge/orchestration.md`, "Capability tiers"), telling it the issue number and the **intended label** (what the spawning thread has just decided this issue's state label should be — `ready-for-build` at every flip-type call site below, whichever of `ready-for-build`/`ready-for-structure` `to-tickets`' own routing criteria chose for that ticket, `ready-for-feature-design` at grilling's stage 2 exit, or no label at all at stage 3's start), and the sub-agent:

1. reads the issue's current state label;
2. if it does not already match the intended label (or, for a removal, if the label to remove is still present), removes the one that's wrong and adds the intended one (or just removes it, for a bare removal); if it already matches, reports back unchanged — this is not an error;
3. reads the issue's labels again to confirm the result actually landed;
4. reports the before/after state to the spawning thread, which records it in the same edit as that stage's own closing action (the design comment, the design-doc PR merge, the Structure guidance section, or the publish step's own report).

Most of the call sites below always intend `ready-for-build` on a ticket (the gate they satisfy is specifically "design is now done," so a mismatch there is always `ready-for-structure` wrongly left on).
`to-tickets`' publish step is different: it intends whichever label its own routing criteria chose per ticket, which is deliberately `ready-for-structure` for some tickets, so its sub-agent call is a same-recipe **verification** of a routing decision, never a blanket flip to `ready-for-build`.
The two feature-tracker call sites (grilling's stage 2 exit, and stage 3's start) are a different pair again: they apply and then remove `ready-for-feature-design`, never `ready-for-structure`, on the feature's own tracker issue rather than a ticket.

This fires at every point one of these labels' gate is satisfied, not only at `implement-with-merge` step 0a:

| Call site | Intended label | What satisfies the gate |
|---|---|---|
| `implement-with-merge` step 0a | Always `ready-for-build` | The design-exit pass's Structure guidance section (`.forge/feature-pipeline.md` has no line for this one; it is this skill's own step) |
| `grill-me` stage 2 exit, feature-pipeline branch | Always `ready-for-feature-design`, applied to the feature's own tracker issue | The grilling session's use cases and constraints are recorded on the tracker (`needs-grilling` removed in the same edit) |
| Feature-pipeline stage 3, at start | Always: remove `ready-for-feature-design` from the tracker, with no replacement label | The stage 3 design thread starting work on the tracker, before it posts the stage 3 design comment |
| Feature-pipeline stage 3, single-ticket discernment | Always `ready-for-build`, applied to the tracker (now also the build ticket, with no `ready-for-structure` step in between: its own stage 3 comment already is the design-exit) | The high-level design comment, when stage 3 invokes its own single-ticket, low-drift discernment (checklist items 5 and 9 skipped and ticked as such; checklist item 8, the post-merge review pass, still gets filed by `feature-pipeline` job (b) fired directly) |
| `to-tickets` publish step | Whichever the routing criteria chose for that ticket, `ready-for-build` or `ready-for-structure` | Each slice ticket already gets the right label at filing; the sub-agent here re-reads every newly filed ticket to confirm it, rather than trusting the filing write uncorroborated |

Stage 5 (the full multi-slice path) sets no label itself: by the time its design doc merges, the tracker's `ready-for-feature-design` was already removed at stage 3's start, and the tracker gets no ready label of its own again until `to-tickets` labels the child tickets it files at stage 6 (the tracker stays an `epic`, never itself a build ticket, outside the single-ticket-discernment row above).

## `needs-decision`

`needs-decision` marks a ticket that no thread may work on until the owner has decided the open question it's blocked on.
It's a hard block a build thread checks for before picking up a ticket, orthogonal to every other label here.
It stacks with a state label and with a deferral label (`hanging`, `future`, `deferred-arch-finding`) rather than replacing any of them, because the ticket's other labels still describe what it is once the question is resolved.

**Who sets it**: whoever raises the open question: a triage pass, a build thread that hits a decision it can't make itself, a review pass's triage, a design that accepts a non-security risk (SDLC-107), or the owner directly.

**While it's on**: the ticket stays open and no thread starts or continues work on it, however ready its other labels say it is.
`queue-sweep` check 9 lists every open `needs-decision` ticket with its age, so the full list surfaces under "awaiting the owner" in progress reports.
There's no staleness threshold or escalation on the label itself.

**Closing it**: the ticket stays blocked until the owner comments on it with a decision.
A thread then records the outcome, quoting or summarising the owner's decision in a comment, and removes the label, either closing the ticket (the decision was to drop it) or leaving it with whatever label now reflects the decision (back to `ready-for-build`, `hanging` for an accepted risk, or `wontfix`).
Removing the label without that recorded outcome is a labelling bug.

## `needs-grilling`

`needs-grilling` marks a ticket that's accepted as real work but isn't yet fleshed out enough to carry a ready label: its use cases, scope, or domain terms haven't been settled, so writing an agent brief or starting a design pass would mean guessing.
It names the specific next step the ticket needs — a feature-pipeline stage 2 grilling session (`grill-me`, `.agents/skills/grilling/SKILL.md`) — rather than the generic "maintainer needs to evaluate this" that `needs-triage` says.

It's a **state role**, mutually exclusive with the repo's other state roles (`needs-triage`, `needs-info`, `ready-for-build`, `ready-for-structure`, `ready-for-feature-design`, `ready-for-human`, `wontfix`) — unlike `needs-decision`, which stacks beside a state role instead of replacing one.

**Who sets it**: `triage` step 4, when a request needs grilling but the current pass can't run it to completion; the coordinator, when it notices a swept-in ticket's use cases aren't settled before it would otherwise get queued; or a build or design thread that discovers mid-ticket that the premise needs a grilling session before the work can continue.
Applying it also means posting a note on the ticket recording what's established so far and what the grilling session still needs to settle.

**While it's on**: the ticket carries no ready label, so it never matches the coordinator's default-queue rule (which triggers only on `ready-for-build` or `ready-for-structure`) and is never swept to `queued` on the strength of a ready label it doesn't actually have.
`queue-sweep` check 4 lists it as a valid state label (so a `needs-grilling` ticket isn't flagged as unlabelled), and check 9 lists every open `needs-grilling` ticket with its age, the same shape as its `needs-decision` listing.
The coordinator routes a `needs-grilling` ticket to a grilling thread, never to a build thread.

**Closing it**: the grilling thread, once its session's use cases and constraints are recorded on the issue (and any settled term written into `CONTEXT.md` inline, per `grilling`'s own glossary step), removes `needs-grilling` and applies `ready-for-feature-design` directly (`grill-me`'s own exit step, feature-pipeline branch): grilling always moves a ticket into stage 3 high-level design next, never straight to a build, whether the ticket is a standalone request or a tracked feature's own issue.
Removing the label without that grilling session having actually happened is a labelling bug, the same class `needs-decision`'s own closing rule guards against above.

## Queue labels

A ticket the coordinator accepts is labelled `queued`; a build thread swaps that for `in-flight` when it starts the ticket, and removes `in-flight` when the ticket merges or closes.
The queue is therefore readable from the tracker alone: `queue-sweep` check 10 reads both labels, and a feature's epic holds the rest.
Neither label replaces a state label, so a queued ticket still carries `ready-for-build` or `ready-for-structure`. (`ready-for-feature-design` is never queued — see that label's own section above.)

| Label | Means | Set by | Removed by |
|---|---|---|---|
| `queued` | Accepted by the coordinator, not yet started. | The coordinator, at acceptance. | The build thread, when it starts the ticket. |
| `in-flight` | A build thread has started the ticket and has not yet merged or closed it. | The build thread, at start. | The build thread, at merge or close. |

## `main-health`

`main-health` marks a ticket whose work belongs to the Main Health thread rather than a build thread: post-merge review passes, local full-suite work and CI-drift work.
It is a routing mark, not a state role, so the rule that a ticket carries exactly one state role is unchanged; it sits beside the state role.

| Label | Means | Set by | Removed by |
|---|---|---|---|
| `main-health` | The work belongs to the Main Health thread, not a build thread. | Triage, when the ticket is Main Health work; whoever files a review-pass ticket. | Never removed while the ticket is open. |

**Routing**: the coordinator hands a `main-health` ticket to the Main Health thread and never to a build thread.
`ready-for-build` and `ready-for-structure` route a ticket to a build thread; `ready-for-feature-design` routes a tracker to a one-off stage 3 design thread instead.
A move between routing labels is always a replacement, never a bare removal; removing one of the three with nothing in its place is a labelling bug.

**Gap check**: `queue-sweep` check 5 flags any open review-pass ticket (a title starting `Post-merge review pass`, a title naming full-suite or CI-drift work, or a `Route: Main Health` line in the body) that lacks `main-health`.

## `epic`

`epic` marks a parent issue whose sub-issues are the work: a feature's tracker, a remediation bundle's parent, or a standing tracker.
An epic has no closing PR, so it is closed by hand when its sub-issues complete, except for the standing trackers and for a feature tracker short of its own closing checks (`.forge/tickets-and-branches.md`; `.agents/skills/feature-pipeline/SKILL.md`, "Closing the tracker").

## Release-note labels

Separate from the state roles, every ticket carries release-note labels.
They decide what the release notes say about the work, so that judgement is made when the ticket is filed instead of at release time.

| Label | Meaning |
|---|---|
| `release:user` | A user would notice it: a new capability, a changed behaviour, or a fixed symptom. |
| `release:integrator` | It changes something an operator or integrator must know to deploy or depend on this project: a configuration key or environment variable, an interface, an endpoint, a migration, an operational behaviour. |
| `release:internal` | Nobody outside the repo would notice: refactors, tests, CI, docs, agent skills, a fix to a bug no user could reach. Counted in the release notes, never listed. |
| `breaking` | Added alongside `release:integrator` when an integrator must act on upgrade: a removed or renamed key, a changed contract, a one-way migration. |

A ticket carries `release:user`, `release:integrator` or both, or `release:internal` alone; `breaking` goes with `release:integrator`.

**Who sets them, and when:**

1. **At filing** (`triage`, `to-tickets`, or anyone filing a ticket by hand): pick the labels from what the ticket intends.
2. **Before merge** (`implement`, `implement-with-merge`): re-check the labels against the actual diff, because what a ticket turns out to be can change during the work.
   Fix the labels if they are wrong, and fill the PR's `Release note:` field to match, each bullet ending with its issue number.
   This re-check is an acceptance criterion on every ticket: a PR does not merge until it is done.
3. **At release**: read the labels and the field.

**The `Release note:` field** in `.github/pull_request_template.md` holds the entries the release notes will use.
A PR that adds or fixes several things gives several entries, which may land in different sections.
Write one bullet per entry, each starting with where it goes:

```markdown
Release note:
- Enhancement / Exports: Added **CSV export** of the overdue-invoice report. (#<n>)
- Bug fix / Exports: Large exports silently stopped at the first thousand rows. (#<n>)
- Integrator: New setting `exports.max_rows` (default 50000). (#<n>)
- Breaking: `exports.dir` became `exports.output_dir`; rename it in deployment configuration. (#<n>)
```

Each bullet ends with the issue number it traces to, in parentheses: the ticket's own number, or the epic's number for a bullet that folds into a feature.
A bullet without one is an exception the release notes list, not a number they guess.

- **Enhancement / \<area\>** and **Bug fix / \<area\>** are user entries (`release:user`), with the area taken from the project's list of user-facing areas (stage 0 writes this list into `CLAUDE.md`'s "This project's own rules" section).
  Write what now exists with the key feature in bold, or the bug as it was, in the past tense.
- **Integrator** and **Breaking** are integrator entries (`release:integrator`, plus `breaking`), naming the key, interface or endpoint and what an integrator must do.
- A PR labelled `release:internal` writes `Release note: none`.

Every entry kind needs its label, and every label needs at least one entry.

## Parking labels

Three labels park an issue instead of queuing it for a build: `hanging`, `future` and `deferred-arch-finding`.
Each has its own owner, its own parent epic, and its own treatment in the release notes.

When the owner asks for a ticket and doesn't say which of now, `hanging` or `future` it is, any thread asks before filing it (`.forge/tickets-and-branches.md`, "Ask which state a requested ticket goes into").

| Label | Means | Set by | Parent epic | Revisit trigger | In the release notes |
|---|---|---|---|---|---|
| `hanging` | A real, agreed gap that is deliberately not being worked: an accepted risk, or deferred until a named point in time. An accepted risk carries its `Risk:` line and the owner's recorded decision (SDLC-107). | The owner only. | #342 | The hanging epic's revisit cadence, plus any `Revisit: YYYY-MM-DD` date or condition recorded in the issue itself. | Each open issue a user or integrator could hit becomes a **Known issues** entry. |
| `future` | An owner-raised or grilling-produced idea, not yet scheduled or scoped. Applied only when the owner says the idea is deferred; if their words don't say so or are unclear, ask whether it is for now or deferred before filing (SDLC-020). | The owner, or a grilling thread. | #341 | None. It moves only when the owner starts the feature pipeline on it, which removes the label and detaches it from the epic. | Left out. |
| `deferred-arch-finding` | Provenance and status in one label: the issue was produced by a stage 8 architecture pass, a post-merge review run, or a builder's out-of-scope gap, and is not actioned right now. | A review pass's triage, or a builder's weak out-of-scope gap. Never set on an issue the owner raised directly. | #343 | None recorded; it is parked on priority, not on design. | The open ones make **one summary count line** in Known issues. Once an issue is actioned the label is removed entirely. |

`future` is for ideas the owner raises or grilling produces: a candidate that needs its own scoping pass before implementation.
It is a different population from the code-level findings an automated review pass defers (a stage 8 finding that is weak — neither Strong, worth an ADR, nor worth exploring as an open question — or a post-merge review or out-of-scope finding the owner parks after it is raised as an open question), which carry `deferred-arch-finding` under the architecture-findings epic instead and never carry `future`.
Keeping them apart keeps the deferred-ideas epic to ideas the owner actually raised.

## Retired labels

When a label is retired, list it here with what replaced it, so `queue-sweep` check 4 can flag it if it reappears on an open issue.

| Retired label | Replaced by |
|---|---|
| `ready-for-design` | `ready-for-structure` for the ticket-level meaning (behaviour specified, structure not decided); `ready-for-feature-design` for the feature-tracker meaning (stage 2 grilling done, stage 3 design not started). The old name is not given either new meaning, so a consuming project's open tickets still carrying `ready-for-design` from before this split don't quietly misroute after a sync. |
