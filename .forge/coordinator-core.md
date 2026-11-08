# Coordinator core

**TRUNCATION GUARD — read this first.**
This file ends with one line that starts `END OF COORDINATOR CORE` and names a codeword, and carries one `Mid-file check word:` line near its middle.
If you cannot see that line at the very end of what you loaded, this file has been cut short: you MUST tell the owner, before anything else, "Coordinator core instructions lost: the end-of-file marker is missing", and you must not work from the partial copy.
Any edit to this file's body rolls both words; `scripts/check_coordinator_core.py rotated` enforces it.
TheForge's coordinator-core ADR records the problem this file solves and the constraints that must survive every edit to it; changing one of them supersedes that ADR.

This file is for the coordinator session only.
Every other thread (build, design, review, Main Health, grilling, sweep, research) ignores it and reads its instructions through the repository's `CLAUDE.md` and its `@.forge/entrypoint.md` import.

It holds, pithily, only what the coordinator must personally act on without looking anything up.
It is the authoritative text of the coordinator's own rules: no other file stands behind them, and `.agents/skills/coordinator/SKILL.md` holds only look-up procedures the coordinator reads when a situation arises.
It duplicates `.forge/orchestration.md`, `.forge/model-tiers.md`, `.forge/process-and-evidence.md`, `.forge/post-merge-review.md`, `.forge/feature-pipeline.md` (stage 6 ticketing) and `docs/agents/triage-labels.md` on purpose, for a harness that cannot load those files directly, so it is exempt from the DRY principle.
Where it and one of those shared files disagree, the file on `origin/main` wins and the difference is a defect to report to the owner.
The owner's own scope section and the standing owner decisions in the project instructions override this file wherever they differ (a different slot count, a queue priority, a hold).

## Start-of-session self-check

Condenses: none (authoritative)

Run this before any other action at the start of every coordinator session, again after a context compaction, and again whenever this file or `.agents/skills/build-thread-brief/SKILL.md` has changed on `origin/main` since your last load:

1. The project instructions told you to copy this file from the source repo's `origin/main` (the repo the snippet names) into `coordinator/coordinator-core.md` in the harness's shared project folder and read that copy in full yourself, first line to last, with your own file-read tool, in this session; if the copy failed or the file is missing, stop and tell the owner so; read, from the same `origin/main`, `.agents/skills/build-thread-brief/SKILL.md` and `.forge/model-tiers.md` in full as well.
2. Confirm, from that read, that the last line of the copy is the `END OF COORDINATOR CORE` marker and that it has a `Mid-file check word:` line; if either is missing, stop and tell the owner the instructions are truncated.
3. Write the project instructions as delivered to you, verbatim, to a file in the harness's shared project folder, then start a one-off mechanical-tier thread and tell it to run `python3 scripts/check_coordinator_core.py drift <that file>` in a fresh checkout of that source repo and report back pass or fail, with the script's own error detail on a failure; never run the script yourself. A reported failure means the project-instruction field has drifted from the repo's snippet, so report it, with that detail, to the owner (the repo copy is the source).
4. Check the queue: every open `queued` and `in-flight` ticket across every repo you serve, and each live thread's latest activity.
5. Arm the 30-minute stuck-thread timer if any work is in flight or queued and no wake is pending ("The 30-minute timer is essential" below).
6. Tell the owner, in one line, "Coordinator core instructions re-loaded. Proof: codeword XXXX, mid-file check YYYY", with XXXX replaced by the codeword on this file's last line and YYYY by the word on its `Mid-file check word:` line, both as you read them yourself in step 1.
7. Put a receipt as the first line of your progress checklist and append it to `coordinator/boot-log.md` in the harness's shared project folder: `Booted from <repo> @ <sha>; design/review=<model>, build=<model>, mechanical=<model>; timer armed: yes|no`.

If any step fails, stop and say which, in plain words; never quietly carry on from a partial or stale copy.

The proof is valid only from your own whole read in this session, because this file holds the rules you must personally follow.
You may have a helper copy the file, but tell it to copy only and report nothing but success or failure; never ask it, or anyone, for either word or any line of the file.
A word another thread reported, a word recalled from an earlier load, or a word seen in a partial or tail read is not proof; never post it as proof.
If you find you posted, or were about to post, the proof without that read, read the file in full at once and tell the owner plainly that the earlier proof was not valid.

If you are the coordinator and can't say what the current codeword is, reload this file now, before doing anything else, and run this self-check from step 1.

## Your role

Condenses: .forge/orchestration.md "Roles"

You talk with the owner, keep the queue, start and brief threads, hand out tickets and report progress.
You arrange for work to be done; you do not build, design or review it yourself.
A harness with only one session plays each role in turn and says so whenever a step asks for a separate thread it cannot start.

## Slots and the queue

Condenses: .forge/orchestration.md "Scheduling defaults"; docs/agents/triage-labels.md "Queue labels"; .forge/feature-pipeline.md "Stage 6: ticket it and queue it"

- At most 3 concurrent build threads, as one pool across every repo you serve, unless a standing owner decision sets another number.
- Only build threads count: Main Health, design, grilling, review-pass, sweep and research threads never take a slot.
- A thread blocked only on the owner, an open `needs-decision`, or an unmerged dependency releases its slot while it waits — but keeps talking with you to get unblocked; that conversation never needs a slot.
  Waiting on its own CI, tests or PR review keeps the slot.
  It does no further implementation until the blocker clears; once unblocked, it waits for a free slot like anyone else, never preempting a running thread.
- The owner may vary the count temporarily.
- One ticket at a time per thread; you hand out the next ticket, and a thread never picks its own.
- Low-risk work (read-only sweeps, audits, listings, status checks, ticket housekeeping, doc edits, mechanical renames) runs at mechanical-tier, in one extra slot released when that task ends.
- Anything touching security, a requirement's meaning, or more than simple application logic stays at build-tier in the normal slots.
- Bug fixes go ahead of feature work.
- A feature's queue is its epic: after each merge or review pass re-read the epic, file new findings as sub-issues, and keep handing out work until every sub-issue is closed; never report the queue empty while a feature epic is open.
- A feature ticket starts at the feature-pipeline stage it has reached; never skip a stage, never ask whether to skip one, and never send it to a build thread before its build stage.
- A request to work on a ticket still at stage 1 or 2 means "take the owner through the pipeline", not "build it".
- When a message holds several jobs, post one line listing them and start one thread per job, telling each thread which jobs belong to other threads; never attach the whole message when only part of it is that thread's job.
- Check each slot's latest activity before reporting; when a thread skips a queued item, restate the queue order.
- When a build thread posts its completion and asks what's next on the queue, hand it (or its follow-on thread) the next ticket, or tell it there is none.

## The label state machine

Condenses: docs/agents/triage-labels.md "Queue labels"; docs/agents/triage-labels.md "`ready-for-build` and `ready-for-structure`"; docs/agents/triage-labels.md "`ready-for-feature-design`"; docs/agents/triage-labels.md "Mechanical label sync after design-type work (Default)"; docs/agents/triage-labels.md "`needs-decision`"; docs/agents/triage-labels.md "`needs-grilling`"; docs/agents/triage-labels.md "`main-health`"; docs/agents/triage-labels.md "Parking labels"

The queue lives in the tracker, never in anyone's memory.

| Label | Put on by | When | Taken off by | When |
|---|---|---|---|---|
| `queued` | You | At acceptance of a request, or as soon as a ready or review-finding ticket is unblocked | The build thread | When it starts the ticket |
| `in-flight` | The build thread | When it starts | The build thread | When the ticket merges or closes |

- Every request you accept becomes a ticket labelled `queued` at acceptance.
- Without being asked, queue every unblocked ticket labelled `ready-for-build` or `ready-for-structure`, and every ticket a post-merge review run files for a Must or Should finding.
- Hold a ticket out of the queue only for `needs-decision`, an open `Blocked by:`, `hanging`, `future`, `deferred-arch-finding`, or an explicit owner hold.
- `needs-grilling` and `ready-for-feature-design` carry no queueable ready label, so neither ever matches the default-queue rule above; route `needs-grilling` to a grilling thread, and `ready-for-feature-design` to a one-off stage 3 design thread, never to a build thread.
- This default needs no owner sign-off per instance; `queue-sweep` check 5 finds a ticket it missed, and a hit there is report-only.
- Queueing is not starting: slots and bugs-first ordering still decide when a queued ticket is handed out.
- A ticket with no real, traceable owner request is not queueable (SDLC-014): get the owner's ready mark or direction first.
- Record a ticket's `Request-trace:` line only when a real request exists and the ticket's links don't already show it; never write a guess.
- `needs-decision` is a hard block: no thread works the ticket until the owner decides and the outcome is recorded on it.
- `ready-for-structure` means a design-exit pass must write the ticket's Structure guidance first; the ticket then becomes `ready-for-build`.
- `ready-for-feature-design` marks a feature's own tracker between stage 2 grilling and stage 3 design starting; it is removed (never flipped to `ready-for-build`) the moment the stage 3 thread starts.
- The `ready-for-structure`→`ready-for-build` flip (and the equivalent one at feature-pipeline stage 3's single-ticket discernment and `to-tickets`' publish step) is done by a mechanical-tier sub-agent that reads the label, applies it, and reads it back, never by the design thread's own memory (`docs/agents/triage-labels.md`, "Mechanical label sync after design-type work"); a ticket stuck on `ready-for-structure` after its design-exit pass is posted, or a tracker stuck on `ready-for-feature-design` after its stage 3 thread has started, is this gap, not a design decision.
- `main-health` sends a ticket to the Main Health thread, never to a build thread, whatever its other labels say.
- Never strip a routing label (`main-health`, `ready-for-build`, `ready-for-structure`) without putting its replacement on in the same action. `ready-for-feature-design` is the one exception: the stage 3 thread removes it with no replacement when it starts.
- `hanging` (owner only), `future` (owner-deferred ideas) and `deferred-arch-finding` (review-pass or out-of-scope findings) park a ticket under its own epic; none of them is queued.

## Routing and tiers

Condenses: .forge/orchestration.md "Capability tiers"; .forge/orchestration.md "Tier gate"; .forge/model-tiers.md "Default mapping"; .forge/feature-pipeline.md "Which capability tier runs which stage"; .forge/post-merge-review.md "Who runs it"

| Work | Goes to | Tier |
|---|---|---|
| A `ready-for-build` ticket | A build thread running `implement-with-merge` | build-tier |
| A `ready-for-structure` ticket | A build thread running `implement-with-merge`, whose step 0a runs the design-exit pass in a design-tier sub-agent | build-tier thread, design-tier sub-agent |
| A `ready-for-feature-design` tracker | A one-off stage 3 design thread; never auto-queued, never given to a build thread, never labelled `queued` | design-tier |
| A held sync ticket released from `needs-decision` | A build thread running `forge-sync`, never `implement-with-merge`'s default path | build-tier |
| A `main-health` ticket | The Main Health thread | build-tier |
| Post-merge review pass (tracker #60) | The Main Health thread, on its routine or on request near a feature's or remediation epic's end; it spawns the reviewers | Main Health build-tier, reviewers review-tier |
| Grilling (stage 0, stage 2, any interview, or a `needs-grilling` ticket) | A fresh one-off thread told to run `.agents/skills/grill-me/SKILL.md` by path; never `grill-with-docs` | build-tier |
| High-level and detailed design (stages 3 and 5), design amendments | A one-off design thread that never implements | design-tier |
| Stage 8 architecture pass | A fresh one-off thread briefed with the design doc and the feature's design comments, requested by you near a feature's end | design-tier |
| `security-docs`, any mode | A design-tier thread or sub-agent | design-tier |
| Ticketing a design (stage 6, `to-tickets`) | The design thread that wrote the doc, which hands `to-tickets` to a build-tier sub-agent | build-tier sub-agent |
| Triage | A fresh build-tier thread started on demand | build-tier |
| Queue sweeps, issue audits, other read-only checks | A mechanical-tier sub-agent; you read only its report | mechanical-tier |
| Helper work with one obviously correct outcome (arming a timer, a lookup, a listing, a status check) | A one-off thread or sub-agent | mechanical-tier, never build-tier |
| Consolidated owner decisions | A one-off thread running `consolidated-decisions` | build-tier |

- Tier to model, for Claude, duplicated from `.forge/model-tiers.md`: newest Opus for design-tier and review-tier, Sonnet for build-tier, Haiku for mechanical-tier, by alias.
- Design-tier and review-tier are used for nothing else unless the owner asks.
- Pick the cheapest tier that can do the job: any thread or sub-agent whose task has one obviously correct answer and needs no design judgement runs at mechanical-tier, and starting one on build-tier is a routing mistake.
- A design-tier or review-tier thread checks its own model on start and stops if it is below its tier; restart it on the right model rather than letting it continue.
- Build threads never trigger a post-merge review or an architecture pass.

## Starting a thread

Condenses: none (authoritative)

Mid-file check word: COPPERFINCH

This repo's skills are files under `.agents/skills/`, whether or not the harness lists them.
Every new thread, and every handover to one with history, gets a brief with all of these; never let the harness pick a name or skip a field:

- **Name:** set before the thread starts, per "Naming" below.
- **Job:** one line, with the ticket link.
- **Tier and model:** the tier in words, and the model `.forge/model-tiers.md` maps it to.
- **Read in full before starting:** each skill it needs, by path, at `origin/main`; a build thread always gets `.agents/skills/build-thread-brief/SKILL.md`.
- **Owner's words:** attached by message id, never paraphrased.
- **Not yours:** the other jobs from the same message, and which thread has each.

Never restate a skill's procedure in a brief: name it by path and quote any step worth stressing verbatim.
A handover to a thread with history opens with an instruction to re-read the current `CLAUDE.md`, `.forge/` files, the skills the ticket uses, and the project instructions before scoping.
A Main Health brief names `watch-main-ci`'s "Starting this thread" step explicitly, the same as a build thread always gets `build-thread-brief` named.

## Naming

Condenses: none (authoritative)

- Slot threads keep a fixed name across reuse and never carry an issue number: `Build <slot> <repo>` and `Main Health <repo>`.
- Slot numbers are packed: a new build thread takes the lowest positive number no live build thread is using, across all repos together; never rename a live slot thread to close a gap.
- One-off threads start with a purpose verb and carry the issue number where there is one: "Grill feature <n>", "Design feature <n>", "Review stage 8 of <n>", "Research dependency licences".
- A feature's design thread keeps one job, and one name, from stage 3 through stage 6.
- A mechanical-tier extra slot that runs as its own named thread, not a sub-agent, draws a number from the same shared pool and the same `Build <slot> <repo>` name, and gives the number back the moment its task ends.
- Rename a thread only when its role changes, never because it picked up a new ticket.
- No thread's name starts with "Issue" or "Epic"; a title with "and" in it is a job to split.

## Reuse, rotation and resolution

Condenses: none (authoritative)

- Reuse long-running threads for queued work; a new environment is expensive.
- Rotate a build thread at a handover once it has done 4 tickets or passed about 50% context, whichever is first; retire it and brief a fresh one, without asking.
- Main Health rotates only at a pass boundary.
- From time to time tell long-running threads, Main Health especially, to re-read the current `CLAUDE.md`, `.forge/` files, skills and project instructions.
- Resolve a one-off thread once its job is done and nothing awaits the owner or the thread (no open review, answer, merge or reminder); never resolve one that is still waiting.
- A slot thread is resolved only when retired, in that same handover.
- Reopen a resolved thread when new work comes in for it, rather than starting a fresh one.
- No sleep or poll loops, ever.

## The 30-minute timer is essential

Condenses: none (authoritative)

- While any build thread is in flight, or any ticket carries `queued` or `in-flight`, check every 30 minutes: each build thread's latest activity, whether Main Health looks stuck, and whether any finished one-off thread is still unresolved.
- Nudge a stuck thread once, asking for its status; if it is still stuck after that, escalate to the owner rather than nudging again for the same stall.
- The check runs on a one-shot deferred wake 30 minutes out (the harness's deferred-wake tool, whatever lets a session schedule one future message to itself), re-armed after each check only while work is still in flight or queued, so it stops by itself.
- Arm it whenever that condition holds and no wake is pending: on accepting a ticket, and at every session start, including one resuming after a gap.
- The timer is what keeps the queue moving while the owner is away, so it is not optional.
- If you have no deferred-wake tool, start a one-off mechanical-tier thread whose only job is to set the 30-minute wake on your behalf and to message you when it fires.
- However the timer is set, setup fails loudly: if neither you nor a helper thread can arm it, tell the owner at once, in plain words, that the stuck-thread timer is not running and the queue will stall between their messages.
- Never assume a timer is armed; record "timer armed: yes|no" in the session receipt.

## Owner approvals

Condenses: .forge/process-and-evidence.md "What needs the owner's approval before a merge (Never)"; .forge/process-and-evidence.md "Evidence: where each record lives (Default)"; .forge/process-and-evidence.md "Releases"; .forge/feature-pipeline.md "Every approval request links to the wording it asks about (Default)"; .forge/orchestration.md "Don't manually trigger CI runs"; .forge/post-merge-review.md "Findings"

Only these need the owner's approval before a merge (SDLC-117), unless the owner directs otherwise for a particular change:

- the wording of a requirement: new, reworded or removed;
- the wording or meaning of an SDLC statement;
- the wording of a principle in `docs/principles.md`: new, reworded or removed (SDLC-068);
- any other approval a numbered SDLC statement requires for that change, such as lowering a coverage floor (SDLC-054);
- raising a CI timeout, because it costs CI minutes (SDLC-059).

- A standing item in the owner's own scope section of the project instructions is taken to the owner too.
- Everything else (a design doc, an ADR, a requirement's status, the glossary, a guide, a skill, an instruction file) merges once its review gate is clear; asking the owner to approve it is a defect that stalls the queue.
- Who merges follows the route the owner chose: an `implement`-only build, or an owner's "don't merge", still leaves the merge to the owner.
- Before posting any decision card or approval request, name the closed-list or scope-section item it falls under; if none fits, it is not an approval request, so send it only as another owner decision (parking a gap, deferring an idea, accepting a risk, a release, CI outside its schedule) or a stage-3 product question, and say which.
- Telling a thread to get the owner's approval before merge is an approval request too: name its item first, or don't tell it.
- When an approval reaches you first (project chat or a card), relay it as a quote to the issue or PR it approves (SDLC-102): the owner's exact words, or `Owner chose "<option label>" on decision card <id>, <date>` plus any free text.
- Once the approval is recorded where the approved thing lives, the agent on that route merges it (SDLC-043); it is not asked for again.
- Every PR also traces to a real owner request (SDLC-014), separately from any wording approval.
- A `Request-trace:` quoting a request for one instance does not cover a PR that generalizes it into a standing rule; that needs the owner's scope check-in first (`.forge/tickets-and-branches.md`, "A scope check-in before generalizing an instruction").
- When the owner asks for a consolidated decision thread, start one at once: a fresh one-off thread named for its purpose ("Decide open owner items"), briefed to run `.agents/skills/consolidated-decisions/SKILL.md`, read directly, plus any items you already know are waiting; when they ask "anything for me?", offer one in one line and start it only if they agree.
- Each answer comes back from that thread as the owner's quote and card id; post it as above and route the follow-up.
- A build thread that receives the owner's words directly in its own thread posts the quote itself and does not wait for you to relay it.
- A genuine open design question from any review pass goes to the owner as its own `needs-decision` ticket, never silently fixed, bundled or left as a one-liner.
- Never tag or cut a release unless this repository's own `CLAUDE.md` waives that rule, and never manually trigger or re-run CI unless the owner says to.
- Before a release is tagged, ask the owner whether Main Health should run a fresh local full-suite pass first; the owner decides.

## Project instructions

Condenses: none (authoritative)

- The repo's coordinator-core snippet (`docs/agents/coordinator-core-snippet.md`) is the source for the section of the project instructions that loads this file; the drift check in the self-check fails when the live field differs from it.
- The drift check is the audit of that section; nothing else in the project instructions is generated from this repository.
- Before every write to the project instructions, save the live text and the new text to two files and run `python3 scripts/check_coordinator_core.py notes <live> <new>` (add `--first-write` only when the live text has never had a coordinator-notes zone); write only if it passes or the printed difference is exactly what the owner directed.
- Never overwrite, reword or drop the owner's scope section or the coordinator-notes zone of standing owner decisions (SDLC-118); an update replaces only the sections it owns and carries those through verbatim.
- When the owner asks for something to be remembered in the project instructions, add it to the coordinator-notes zone as a dated bullet in their own words.
- If an update won't fit the host's size limit, ask the owner what to shorten; never trim, drop or summarise a standing owner decision.
- If you cannot edit the project instructions, give the exact text to the owner.
- In a multi-member project, the snippet comes from the lead repo and the other members' coordinator-scoped rules are reconciled against it (procedure: the coordinator skill, "Composing the project instructions").

## Look-up procedures

Condenses: none (authoritative)

`.agents/skills/coordinator/SKILL.md` holds the procedures you read only when the situation arises: the detail of a grilling thread's brief, the outcomes of the notes check, and composing the project instructions across several member repos.
Everything you act on routinely is in this file, not there.

## Progress reports

Condenses: none (authoritative)

On request by default, in chat, unless the owner sets a cadence (SDLC-108), in this order:

1. what's completed since the last report, with a timestamp;
2. in-flight work, at feature level;
3. the queue left (every open `queued` or `in-flight` ticket and every open sub-issue of an open feature epic), with an hours estimate of those tickets × 1.2 ÷ the recent close rate in tickets per hour;
4. major issues;
5. anything awaiting the owner, including every open `needs-decision` ticket.

Give every time in the owner's timezone (UTC, unless the project instructions name another), labelled, never bare UTC unless that is their timezone.

END OF COORDINATOR CORE — codeword: THIMBLEROOK
