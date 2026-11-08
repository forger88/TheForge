---
name: feature-pipeline
description: Track a feature through this repo's nine-item pipeline checklist (`.forge/feature-pipeline.md`) on its tracker issue, and make sure ticket-and-queue files the two follow-up tickets the pipeline requires but to-tickets alone doesn't know about. Called by grill-me at stage 2 and by to-tickets at stage 6; fire it directly when starting or queueing a feature outside those two paths; checks stage 0 (project inception) has run before starting a feature.
---

# Feature pipeline

The feature pipeline (`.forge/feature-pipeline.md`) is prose until something enforces it, and prose alone lets a stage be skipped by whichever thread forgets it.
The stage most often skipped is the post-merge review pass a feature needs once it is built: left to memory, a feature can merge dozens of PRs before anyone triggers it.
This skill is the enforcement: a checklist on the feature issue that makes every stage visible, and two tickets filed alongside the build slices so the post-merge review pass and the architecture pass show up in the queue like any other work.

It has two call sites:

- `grill-me` (stage 2's entry point) calls job (a) before handing off to `grilling`.
- `to-tickets` (stage 6) calls job (b) as part of its publish step, right after the build slices are published.

Call it directly only when starting or queueing a feature outside those two paths.

## Stage 0: project inception (once per repo)

Stage 0 runs once per repo, not per feature, so it has no line on the checklist below.
Its record is `docs/principles.md` on `origin/main` holding at least one owner-confirmed principle beyond the forge-seeded one (the generated skeleton's "No principles recorded yet" heading means stage 0 has not run).

**Check, at the start of job (a):** if stage 0 has not run, don't start the feature's checklist yet.
Put a decision card to the owner, "Run stage 0 (project inception) before this feature?", with two options: "Run stage 0 now" (recommended) and "Start the feature without it".
Carry on only after the owner answers.

**Running it:** first confirm the issue tracker, triage labels and domain-doc layout are in place (`docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `docs/agents/domain.md`; the bootstrap script created the labels and standing trackers).
Offer to run the `impeccable` skill's setup to capture product context; ask the owner once whether to run it now or skip it, and if skipped say so plainly and offer it again the first time a feature introduces or changes a UI.
Offer to run the `process-map-setup` skill's setup too, the same ask-once/skip-and-say-so way, to set up the process map and skills-index generation mechanism.
Offer stack-specific skills too, once per matching stack: a small table of stack → skills, today one row, TypeScript → `setup-ts-deep-modules` and `migrate-to-shoehorn`, asked the same ask-once/skip-and-say-so way as the `impeccable` offer.
On opt-in, write a "TypeScript conventions" rule into `CLAUDE.md` naming both skills (new TypeScript packages are wired through `setup-ts-deep-modules`; test files needing `as`-free fixtures use `migrate-to-shoehorn`), and seed each skill's `docs/tools/process-map.yaml` entry without `discretionary: true`, with a why edge pointing at that rule, then regenerate `docs/process-map.md` and `docs/agents/skills-index.md` with `process_map.py build` and `process_map.py index`, and run `process_map.py check` to confirm (mirroring `process-map-setup`'s own step 3; this needs `process-map-setup` to have already run, so if it was skipped, write the `CLAUDE.md` rule now and note on the skip record that the process-map entries are owed once that skill runs).
On decline, both skills stay `discretionary: true`, same as today.
A later stack adds its own row to the table, not new prose.
Then run `grill-me` → `grilling` with the owner, covering the six topics `.forge/feature-pipeline.md`'s stage 0 lists, plus the project's choice of real tools for the generic guards.
For each principle whose exact wording the owner approves, `domain-modeling`'s "Record a principle once the owner approves its wording" writes it into `docs/principles.md`.
File a ticket and land the file in one docs PR that quotes the owner's approval of that wording.

## Job (a): starting the pipeline

First, the stage 0 check above.

**Un-park the feature.** If the issue is still parented under the deferred-ideas epic #341 or still carries the `future` label (the shape every stage 1 idea starts in), detach it from that epic and remove `future` in this same job, before adding the checklist.
The owner saying to start the pipeline is what ends the parked-idea state; a feature mid-build must never still read as a deferred idea.
Leave every other label (release-note labels, `needs-triage`, and so on) untouched; this only clears the parking signal.

Add a nine-item checklist to the feature's tracker issue body.

Check first: if the issue already has a `## Feature pipeline` section whose nine lines name all nine items in order (match on the item names, "Idea" through "Architecture pass", not on exact text), never duplicate it on a second call.
Don't treat it as frozen either: stages 3-5, 7, 8 and 9 each have their own completion-tick call site (below), but a feature whose work predates that wiring, or whose thread didn't follow it, can still drift, and a later call is often the only thing that catches a stage up.
So reconcile it in place: check off any line whose stage is now known complete from the issue's own content or linked tickets.
Stage 7 is done only once every terminal build slice (same definition as job (b)'s blocker rule) is merged *and* the design-doc reconciliation follow-up PR that merge triggers has landed (`implement-with-merge` step 3, `.forge/feature-pipeline.md` stage 7); a closed post-merge review pass ticket means item 8 is done; item 9 is done only once the stage 8 architecture-pass ticket and every Strong-finding and `needs-decision` ticket it filed are themselves resolved (closed, or a `needs-decision` ticket the owner parked, with the decision recorded on it and the ticket detached from the tracker), not merely once the triage was posted or the pass ticket alone closed; and so on.
Preserve every other line's checkbox state, structure and trailing annotation (job (b)'s `(skipped — single-slice design)` suffix, or progress notes a retrofit added) exactly as found, and never un-check a stage already marked done.

When there's no existing section at all, check off every stage already known to be done.
For stage 2 specifically, "already known to be done" means both halves of stage 2's requirement: the issue carries the recorded use cases and constraints, and any term the interview settled, or that collided with an existing one, was reconciled into `CONTEXT.md`.
An issue with grilling notes but no glossary work for a term that needed it is not stage-2-complete; leave item 2 unchecked rather than inferring it from the notes alone.

```markdown
## Feature pipeline

- [ ] 1. Idea
- [ ] 2. Grilling for use cases
- [ ] 3. High-level design
- [ ] 4. Requirements approval
- [ ] 5. Detailed design
- [ ] 6. Ticket it and queue it
- [ ] 7. Build
- [ ] 8. Post-merge review pass
- [ ] 9. Architecture pass
```

This checklist expands the pipeline's stages 1-8 into nine items (stage 0 is per repo and has no line here).
Items 1-7 match stages 1-7 by name and number.
Item 8 ("Post-merge review pass") gives its own line to the trigger stage 7 describes only inline, because it's the stage most often silently skipped, and stage 8 ("Architecture pass") becomes item 9 to make room for it.
Tick a stage off as the issue reaches it.

## Job (b): ticket-and-queue

After `to-tickets` publishes a feature's build slices (stage 6), file two more tickets on the same tracker, in dependency order after every **terminal** build slice: a slice nothing else in this feature's graph blocks on.
`to-tickets` allows parallel branches, so a feature can have more than one terminal slice; find all of them (any slice no other slice in this feature lists as a blocker) rather than assuming a single "last" one.
Blocking on only one lets the post-merge review pass start while a sibling branch is still open.

Before creating either ticket, search for one already titled exactly `Post-merge review pass for <feature>` or `Stage 8 architecture pass for <feature>`.
Search both among the feature's existing children (sub-issues of the tracker issue, or, for a flat ticket set with no tracker issue yet, issues referencing it) and repo-wide by exact title.
The repo-wide search matters because creating an issue and attaching it as a sub-issue are two separate operations: a failure between them leaves a ticket the child-only search would miss.
A retry after any partial failure, or a second direct or retrofit run of this job, must not create a duplicate: reuse a matching ticket, attach it as a child if it isn't already, and repair its "Blocked by" edges and body if they're stale.

1. **`Post-merge review pass for <feature>`**, blocked by every terminal build slice.
   Body: a one-line pointer to run the post-merge review procedure (`.agents/skills/post-merge-review/SKILL.md`) over every PR this feature merged, scoped to this feature instead of the whole backlog.
   Note in the body **Route: Main Health thread**, and label it `main-health` (this pass is review-tier judgement orchestrated by Main Health, not a slice build).
   Note in the body that whoever closes this ticket ticks checklist item 8 on the feature's tracker issue as part of the same close; the instruction travels with the ticket because no fixed skill owns running this pass.
   Closing this ticket requires the pass's findings to be *filed* per the bundling rule (`.forge/post-merge-review.md`, "Findings"), not fixed.
   Note in the body that closing the tracker itself is a separate, later gate ("Closing the tracker" below) that waits on the Must findings' fix PRs actually merging.
2. **`Stage 8 architecture pass for <feature>`**, blocked by the post-merge review pass ticket above.
   Body: run `improve-codebase-architecture` scoped to the files the feature's design doc's slices named or touched, never the whole codebase, including a check against the `impeccable` skill for drift from stage 3 and 5's UI check for any user interface in that scope.
   Then triage every finding per `.forge/feature-pipeline.md`'s stage 8: Strong → fix now; rejected with a load-bearing reason → ADR; a finding worth exploring → a `needs-decision` ticket; everything else → a `deferred-arch-finding` issue under the architecture-findings epic #343.
   Post the triage on the feature issue, including the same-shape "is there a principle here?" check.
   Note in the body **Route: a fresh design-tier thread, briefed with the design doc** (design-tier judgement on code that's already merged, not a slice build).
   Note in the body: every Strong-finding ticket and every `needs-decision` ticket this triage files is added as a sub-issue of the feature's own tracker issue, in the same action that files it; a `deferred-arch-finding` ticket is not, since it is deliberately parked rather than to-be-actioned.
   Closing this ticket requires the triage to be posted and every finding from it filed (as a sub-issue where the note above says to); it does not wait on any of those filed tickets' own fixes to merge.
   Note in the body: tick checklist item 9 on the feature issue only once this ticket and every Strong-finding and `needs-decision` ticket it filed are themselves resolved (closed, or a `needs-decision` ticket the owner parked, with the decision recorded on it and the ticket detached from the tracker), never when this ticket closes on its own and never when the triage is merely posted.
   Whoever resolves the last of those tickets ticks item 9, after checking the others are resolved too.
   Note that closing the tracker is a separate, later gate that also waits on any open "is there a principle here?" question this pass raised.

Both tickets get the `ready-for-build` label (they're process steps, not code changes the design-routing criteria apply to) and the standing brief rules (scoped tests, no CI or full suite) like any other ticket.

Tick checklist item 6 on the feature issue once the build slices and every follow-up ticket this job actually files for this feature are filed.
A single-slice feature's item 6 is not blocked on a ticket this job intentionally never creates.
This one edit to the feature's own tracker issue is the explicit exception to `to-tickets`' "do not close or modify any parent issue" rule: that rule protects the parent from being resolved or rewritten out from under its children, not from this skill's checklist line.

For a feature whose design doc has exactly one slice: file the post-merge review pass ticket as usual (that gate has no exception) and skip only the architecture-pass ticket.
Record the skip on the feature issue by marking item 9 `[x] 9. Architecture pass (skipped — single-slice design)` rather than leaving it unchecked indefinitely.

The tickets this job files, and every build slice `to-tickets` publishes, are the feature's queue.
They stay sub-issues of the feature's tracker issue until closed, and the coordinator labels each `queued` when it accepts it (`.forge/coordinator-core.md`, "The label state machine").

## Closing the tracker

The feature's tracker reaching 100% of its sub-issues closed (every build slice, the post-merge review pass ticket and the architecture-pass ticket) is not by itself the signal to close it.
Before closing it, also confirm:

- checklist items 8 and 9 are both ticked (the passes actually ran, not just that their tickets closed for some other reason);
- every Must finding the post-merge review pass filed, and every Strong finding the architecture pass fixed now, has its fix PR merged, not merely filed as a ticket;
- any owner-facing open question either pass raised (a themed-bundle decision card, an "is there a principle here?" question) has been answered.

A themed Should bundle still open, or a `deferred-arch-finding` ticket either pass filed, does **not** block closing the tracker; those are deliberately parked backlog.
When closing the tracker with any of those still open, say so in the closing comment and name the tickets, so they don't lose their provenance once the feature issue that produced them is closed.

## Stages 3-5, 7, 8 and 9: completion-tick call sites

This skill has exactly two call sites, but the other stages don't route through it, because none of them has a dedicated skill.
Each one's completion tick is wired into whichever instructions a thread already follows to do that stage's work:

- **Stages 3-5** (high-level design, requirements approval, detailed design): `.forge/feature-pipeline.md` is these stages' own instructions.
  Its stage 3, 4 and 5 sections each tick the matching item as part of posting the design comment, merging the spec-only PR and merging the design-doc PR.
  Whenever the design introduces or changes a user interface, stages 3 and 5 also check it against the `impeccable` skill; this skill's own job is only the checklist.
  Stage 3, at its start, removes the feature issue's `ready-for-feature-design` label, with no replacement, via the mechanical-tier sub-agent `docs/agents/triage-labels.md`'s "Mechanical label sync after design-type work" describes, rather than the design thread flipping it inline from memory; when stage 3's own single-ticket discernment then makes the feature issue the build ticket, that same pass applies `ready-for-build` to it directly, the same way.
  Every owner-approval request at stage 3 or 4 links directly to the comment or PR diff holding the exact wording and quotes or summarises it inline (`.forge/feature-pipeline.md`, "Every approval request links to the wording it asks about").
- **Stage 7** (build): `implement-with-merge`'s step 3 opens a small follow-up PR, which ticks item 7, once the slice it just merged is terminal and every other terminal slice of the feature is already merged.
  Ticking on the first terminal slice to merge, before its siblings land, is the mistake this rule prevents.
- **Item 8** (post-merge review pass): the ticket job (b) files carries its own instruction to tick item 8 as part of closing it.
- **Item 9** (architecture pass): the ticket job (b) files carries the matching instruction to tick item 9 once it and every Strong-finding and `needs-decision` ticket it filed are resolved (closed, or a `needs-decision` ticket the owner parked, with the decision recorded on it and the ticket detached from the tracker), not when the triage is posted and not when the pass ticket alone closes.

Job (a)'s reconciliation logic stays as a backstop: a feature whose thread didn't follow the instruction above still gets caught and reconciled the next time job (a) runs against it.
Don't take a clean checklist as proof a stage's own instruction was followed rather than backfilled.

## Retrofitting an in-flight feature

A feature already past stage 6 when this skill was adopted didn't get either job automatically.
Retrofit it once: add the checklist (job (a)) backfilled up to its current stage, including the un-park step if the issue still sits under the deferred-ideas epic with a `future` label.
Then run job (b) against its already-filed build slices to file the two missing tickets, blocked by every terminal slice among them.
If the build is already done, block on the merged slices' issues all the same, so the blocking edge stays in the record even though it's already satisfied.
