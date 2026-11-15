# Instructing the agents in a TheForge project

This guide is for you if you have just generated a project from TheForge and want to know how to work with it.
It covers what the process expects of you, how to ask for work, and points you at the repository settings you have to set by hand.

## What this was designed for

TheForge's process was designed for an agent harness that supports a **coordinator** session talking with you, which starts and briefs separate **agent threads** (a build thread, a design thread, a Main Health thread that watches `main`), each of which can start short-lived **sub-agents** for focused work such as a clean-context review.
Claude Projects is one example of a harness with that shape; the convention generalises to any harness where one session can start and brief others.

It also works from a single thread or a single terminal session.
In that case one agent plays every role in turn: it coordinates, designs, builds and reviews, and the process's records (tickets, design comments, PR fields, review records) are what keep those roles honest.
You lose some parallelism and some independence between reviewers, and you gain simplicity.
Where a skill says "start a sub-agent", a single-session harness that cannot do that should say so plainly rather than silently doing the work inline.

The rules live in the generated project itself:

- `CLAUDE.md` (or `AGENTS.md` for other harnesses) is short and project-owned, and imports the forge-owned rule files under `.forge/` through one line, `@.forge/entrypoint.md`.
- `.agents/skills/` holds the skills the rules point at: the procedures the agents follow.
- `docs/software-development-lifecycle.md` is the authority above both: numbered `SDLC-NNN` statements that only you, the owner, can change.

This guide and `scripts/project_init_checklist.md` are themselves forge-owned (`.forge/forge-overrides.md`), so a forge sync refreshes them. Log any local edit to either the same way as any other forge-owned file.

## Initiating the project

Start with **stage 0, project inception**, before any feature work.
Ask the coordinator (or your single session) to "run stage 0".
It will:

1. confirm the issue tracker, triage labels and domain-doc layout are in place (the bootstrap script has done most of this; see `scripts/project_init_checklist.md`);
2. offer to run the `impeccable` skill's setup, which captures durable product context for UI work, and accept a "not now";
3. run a **grilling interview** with you (`grill-me`), a round of numbered questions at a time, each with a recommended answer, drawing out the principles every later feature must respect: what in your domain will change underneath you, which external systems you trust and how far, which frameworks you build on rather than write, size and complexity budgets, your test philosophy and your security posture;
4. write each principle you confirm into `docs/principles.md`, with why it holds and what enforces it, in one ticketed docs PR that quotes your confirmation.

`docs/principles.md` holding at least one owner-confirmed principle beyond the forge-seeded one on `main` is the record that stage 0 has run.
Stage 0 is also when the project chooses its real tools for the generic guards (its linter, its dead-code tool, its size-cap measurement) and replaces the placeholder commands the template shipped with.

If one coordinator serves several of your repositories, add a line reading `Lead repo: <owner>/<name>` to your scope section, naming which one.
The coordinator takes the project's instructions snippet from that repository's checkout, so without the line it has to ask you which one before it can update or audit anything.

## Asking for work

You can ask in two ways.

- **Ask for a ticket.** "File a ticket for X." The agent writes everything agreed into the ticket: the problem, your own words, any decisions, any wording you approved.
  A ticket request is capture only: nothing is committed or opened as a PR until you say the work should start.
- **Ask for the work itself.** "Fix X" or "Build Y." The agents still create a ticket first, then work against it.

Either way, **nothing merges to `main` without a ticket**.
That is a Never rule: no agent can waive it on its own judgement.
If it is unclear whether you wanted a ticket or the change itself, the agent asks.

### Two paths to a build: direct or the feature pipeline

The direct path is for work whose shape is already clear: a bug, or a change confined to a few files with simple constraints.
Its strength is speed and cost: one build thread takes it from ticket to merge, with a short structure check first when it touches existing logic, and it asks little of your time.
The feature pipeline is for new capability whose use cases, constraints or design need drawing out first.
Its strength is getting the thing right before code exists: it interviews you, has the design and requirement wording reviewed before any build, splits the work into slices that can build in parallel, and finishes with reviews that catch drift across the whole feature, at the cost of more of your time and more agent effort.

Say which you want:

- **Direct path:** "Just fix X", "Build X directly", "Ticket X for a direct build".
- **Feature pipeline:** "Take X through the feature pipeline", "Start the pipeline on X", "Grill me on X".

When you don't say, the agent picks one and records `Path: direct|pipeline — <one-line reason>` on the ticket; this is not a new question to you.
On entry to either path, a soft sanity check may propose moving the ticket to the other one — staying on the current path is always the default, and a move happens only if you agree, asked once and recorded on the ticket (`Path check: <stayed|moved> <path> — owner, <date>`) so it isn't asked again.
A slice ticket, a finding filed by a review or architecture pass, and a Main Health ticket are exempt: they're already the output of a path.

## Checking on progress

At any time, post "progress report" in a coordinator thread to get an update covering everything since the last time a report was requested.
The mechanics live in `.forge/coordinator-core.md`, "Progress reports".

## Keeping the project current

TheForge keeps changing after your project is generated: new rules, fixed skills, tightened guards.
Your project follows those changes only when you ask for a sync; nothing pulls them in on its own.

- **What a sync changes, and what it never touches.** A sync (`forge-sync`, run by `copier update`) updates only the forge-owned files: `.forge/`, `.agents/skills/`, the generated reference docs, and the scripts, pre-commit hooks and workflows TheForge ships.
  It also three-way merges the seeded data files (the baselines, allowlists and similar listed under "Seeded files" in `.forge/forge-overrides.md`), keeping your entries.
  It never touches a project-owned file — `CLAUDE.md`, `CONTEXT.md`, `docs/principles.md`, and the other files listed under `_skip_if_exists` — so nothing you or your agents wrote into those gets silently rewritten.
- **The daily drift report and the held sync ticket.** Once a day, Main Health checks, read-only, how far behind TheForge your project is, with no sync and no Copier run.
  When it finds you're behind, it keeps exactly one open issue titled `Sync forge-owned files to TheForge <sha>`, labelled `needs-decision`, so it stays off the build queue until you say go; only an issue Main Health itself opened counts, so a look-alike someone else opens can't be mistaken for it.
  If the check instead finds your project's `CLAUDE.md` has lost its `@.forge/entrypoint.md` line — which would silently disable every forge rule, including the review gate — it reports that to you the same day, as a Must, whatever the drift result.
- **How to ask for a sync.** Tell the coordinator "sync the forge," or release the held sync ticket if one is open: comment your decision on it, and whichever thread sees that comment removes its `needs-decision` label and routes it to `forge-sync`, never the ordinary build queue.
  Either way, nothing syncs until you ask.
- **What the sync PR shows you.** The PR names the TheForge version before and after, every conflict and how `docs/forge-overrides.md` decided it, every line added to or removed from your entrypoint's imports, and any line a one-time migration kept from your project's own `CLAUDE.md` or `AGENTS.md` for you to confirm.
- **Why `CLAUDE.md` keeps its one-line `@.forge/entrypoint.md` import.** That line is how every forge rule, including the review gate that would catch a change to this line, reaches your agents.
  The `forge-entrypoint` hook refuses a commit that drops it, so losing it takes an explicit, reviewed act, not a slip.

## The three dispositions of a ticket

When you ask for a ticket and do not say when it should happen, the agent asks which of three dispositions it gets.
The parking labels behind them are described in `docs/agents/triage-labels.md`, "Parking labels".

- **Now** (or "today"): the ticket is queued and takes the path (direct or feature pipeline) you named, or the one the agent picked and recorded, subject to the soft path sanity check above.
  A bug fix goes ahead of feature work and is built straight off its ticket from a red reproduction loop.
  A feature on the pipeline path starts from whichever stage it has reached.
  A small, already-clear change on the direct path is triaged and built.
- **Hanging**: a real, agreed gap that is deliberately not being worked on now because it is deferred until a named point.
  An accepted risk (one you decide to live with rather than fix) is parked the same way under its own label, `deferred-accepted-risk`.
  Only you can park something this way.
  Hanging and accepted-risk items a user could hit are reported as known issues in the release notes, so they are never silently forgotten.
- **Future**: an idea worth keeping, not yet scheduled or scoped.
  It waits under the deferred-ideas epic until you ask for its scoping pass, at which point it enters the feature pipeline.

There is a fourth parked population you will see but never create yourself: **deferred architecture findings**, filed by the review passes when a finding is a genuine open design question rather than a quick fix.

## Expect a lot of questions

The agents will ask you a lot, and that is by design.
Expect, at least:

- product questions during design, one at a time or in batches as suits you, often as a decision card with a recommended option;
- explicit sign-off of **requirements wording**: a new, reworded or removed requirement in `docs/requirements/requirements-specification.md` lands only in its own PR, after you approve the exact wording, and every such request links to the text and quotes it;
- explicit sign-off of any change to an **SDLC statement's wording or meaning**, which lands first as its own PR to the lifecycle document;
- explicit sign-off of **principle wording**: a new, reworded or removed principle in `docs/principles.md` lands only after you approve its exact wording;
- which disposition a new ticket gets, and whether a new idea is for now or deferred;
- whether to accept a risk the design leaves open;
- go-aheads for anything costly or irreversible, such as dispatching CI outside its schedule, running a mutation-testing audit, or raising a timeout.

Nothing else needs your sign-off before it merges, unless you ask for it on a particular change: design docs, ADRs, guides and skill edits merge once their review gate is clear.

Practical experience with this process is clear on one point: **it is not hands-off**.
A competent human engineer still needs to stay closely involved: reading designs before approving them, spot-checking merged work, noticing when an agent has drifted from the rules or is confidently wrong, and turning what goes wrong into new rules and lessons.
The process makes agents far more reliable and leaves an auditable record, but the judgement that keeps them on track is yours.

## Credit

Most of the instructions that make this semi-automatic agentic coding framework possible come from [Matt Pocock's skills](https://github.com/mattpocock/skills), used under the MIT licence.
The grilling interview, domain modelling, deep-module design vocabulary, test-driven development, bug diagnosis, two-axis code review, ticket slicing and triage all build on his work.
The UI-review skill is [`impeccable`](https://github.com/pbakaus/impeccable), used under the Apache License 2.0.
See the generated project's `NOTICE.md` and `.agents/skills/THIRD_PARTY.md`.

## Project initiation checklist

Copier writes files and the bootstrap script (`scripts/bootstrap.py`) creates labels and tracker issues.
Neither can change your repository's settings or your harness's configuration.
Work through `scripts/project_init_checklist.md` once, right after generating the project; it is the one copy of the list.
