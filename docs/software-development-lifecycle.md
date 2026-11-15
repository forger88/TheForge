# Software development lifecycle

*Say what you do, do what you say, prove it.* Engineering excellence is
that sentence, kept up. Saying what we do is the job of this document,
the capstone that shapes and constrains the agent instructions and the
skills beneath it: they state, in advance and in plain words, how
software is built here. Doing what we say is the discipline of every
thread that follows them. Proving it is the evidence left in the repo,
the tickets and the PRs: documentation, decision records, reviews and
passing tests, which let anyone check later that the process was
followed, not merely intended.

This document describes how software is built, reviewed, assured and
released in this project. It is written for a new team member, human or
agent, who needs to understand the whole process before working on any
part of it, and it is the authority every other process document answers
to.

It mixes two kinds of text:

- **Prose** explains how things are done and why, and gives an overview
  of each document the process produces.
- **Numbered SDLC statements** (`SDLC-001`, `SDLC-002`, …) are the firm
  process commitments. Each one says what happens and who does it, at the
  level of policy: the effect the process guarantees, not the procedure
  that produces it. A statement marked *(desirable)* is a goal the
  process works towards, not a commitment it can be checked against yet.

The procedures live elsewhere: in the repo's agent instructions, in the
agentic harness's project instructions, in the repo's skills, and in the
agent reference material that the instructions point into. This document
does not name individual procedures, skills, labels or file paths, so any
of them can be renamed, split or moved without touching an SDLC
statement, and a statement can be checked against whatever procedure
currently implements it. The agent instructions say where each document
lives today. Where a procedure says something more detailed, it is
implementing a statement here. Where it disagrees with a statement, this
document wins until the repo owner decides otherwise (SDLC-006).

This document was generated from a shared process template. From the
moment the project adopts it, its statements are the repo owner's, and
they change only as section 1 describes, whatever the template later
says; a template update that would change a statement is a proposal for
the owner to decide, not a change in itself.

## The traditional plans, and where this document answers them

Classical software engineering, as codified in ISO/IEC/IEEE 12207 and
ISO/IEC/IEEE 15288 and in IEEE 1058, starts from a project management
plan: who does what, in what order, with which resources and which
risks. Beneath it sit subordinate plans, each answering one concern a
reviewer or auditor would otherwise have to ask about:

- the **quality assurance plan** (IEEE 730): how the project shows its
  products and its process meet requirements;
- the **configuration management plan** (IEEE 828): how changes are
  controlled and how every released item can be identified and
  reproduced;
- the **verification and validation plan** (IEEE 1012) and its
  **test plans** (ISO/IEC/IEEE 29119): what is checked, how deeply, and
  by whom;
- the **risk management plan** (ISO 16085): how threats to the project
  and the product are found, ranked and decided on;
- the **security plan**, the **supplier or third-party management plan**,
  the **documentation plan** and the **measurement plan**, which many
  organisations fold into the plans above.

This project has no separate document for each. This document, with the
agent instructions and skills beneath it, is the single plan, and each
traditional concern is met by commitments stated here and proved by
evidence in the repo, as the opening says. In broad terms:

- **Project management.** Work flows through a queue of tickets handed
  to agents by a coordinator, within roles with defined authority and
  capability tiers, and the repo owner receives regular reports
  (sections 2 and 3, SDLC-008 to SDLC-023, SDLC-108).
- **Configuration management.** Change is gated: nothing reaches `main`
  without an approved ticket (SDLC-014), each ticket is built on its own
  branch and merged by PR (SDLC-040), and git records who changed what
  and why. Deployment configuration and operational values live in
  version control with the code (SDLC-105). Third-party dependencies are
  held at recorded versions (SDLC-104). Published versions are controlled
  by release tags, decided only by the repo owner, so a release can be
  reproduced exactly (SDLC-074, SDLC-106). Documents are under the same
  control as code (SDLC-080).
- **Quality assurance.** Requirements are the contract and every PR is
  traced to them (SDLC-041, SDLC-081, SDLC-082, SDLC-115). Behaviour is built
  test-first and held to coverage floors that only rise (SDLC-049,
  SDLC-053 to SDLC-056). Every change gets several methodical reviews:
  the builder's own, an independent post-merge review, and an
  architecture pass per feature (SDLC-012, SDLC-042, SDLC-064,
  SDLC-032). Findings are triaged and fixed, not left (SDLC-067,
  SDLC-037).
- **Verification and validation.** Tests prove requirements and carry
  their IDs as markers (SDLC-060 to SDLC-063). Bugs are reproduced
  before they are fixed (SDLC-034). A sampled audit checks that the tests themselves can fail
  (SDLC-058).
- **Risk management.** Security is designed in, reviewed after merge and
  reconciled before each release (SDLC-026, SDLC-065, SDLC-076); known
  gaps are parked only by the owner and surfaced in release notes
  (SDLC-019, SDLC-078); other risks are recorded and decided
  (SDLC-107).
- **Supplier and third-party management.** Mature libraries are adopted
  early and recorded (SDLC-070, SDLC-083); third-party material is
  credited and licensed (SDLC-093); upstream contracts are consumed at
  pinned versions (SDLC-104).
- **Documentation management.** Each document has a role, an owner of
  its wording and a rule for staying current (section 10).
- **Measurement.** Progress, quality and throughput are reported to the
  owner at regular intervals (SDLC-108).

Other project management artefacts, such as project goals, milestones,
schedule, stakeholders and resource allocation, are out of scope for this
SDLC. It occupies the engineering management subset of project
management.

The numbered sections are:

1. Authority and change control
2. Roles
3. Tickets and the queue
4. The lifecycle
5. Building a ticket
6. Test strategy
7. Review and assurance layers
8. Code-shape rules
9. Releases
10. The documents and their roles
11. Evidence
12. Configuration, dependencies and operations

## 1. Authority and change control

The process this repo runs on is carried out by many agents across many
threads, each loading the agent instructions and whichever skills its
work needs. Without a single authority, an edit to one skill can quietly
change policy without the owner seeing it. This document is that
authority, and it treats process the way the requirements specification
treats product behaviour: the wording of a commitment is the owner's, and
every implementing change is reviewed against it.

- **SDLC-001**: This document is the originating authority for how
  this project's software is built, reviewed, assured and released. The repo's
  agent instructions, the agentic harness's project instructions, the
  skills and the agent reference material implement it. They are fit
  for purpose, made available to agents, and kept aligned with this
  document.
- **SDLC-002**: Only the repo owner approves a change to the wording or
  meaning of an SDLC statement. The approval is explicit and against the
  exact wording: the owner's own words in a post or comment, a decision
  card, or the owner merging the PR themselves.
- **SDLC-003**: A process change that would alter an SDLC statement lands
  first as its own PR to this document. Changes to the agent
  instructions, the harness project instructions or a skill that depend
  on it follow once it has merged.
- **SDLC-004**: A change to this document that leaves every SDLC
  statement's meaning unchanged (a typo, a link fix, reformatting, or a
  prose clarification) is self-merged like any other docs PR.
- **SDLC-005**: Changes to the agent instructions, the harness project
  instructions, skills and agent reference material are reviewed against
  this document, the way code is reviewed against the requirements
  specification. Such a change that alters no SDLC statement may self-merge
  as normal.
- **SDLC-006**: When a skill or instruction appears to disagree with this
  document, or a change might alter an SDLC statement's meaning, the agent
  that notices flags it to the repo owner for a decision rather than
  resolving it itself. The threshold for flagging is low, and this
  document wins until the owner decides.
- **SDLC-007**: An SDLC statement's ID is never reused. A removed
  statement's number stays retired.

## 2. Roles

**The repo owner** decides what this project does and how it is built:
product scope, requirement wording, the principles, the wording of this
document, what is parked, and when a release happens. Agents propose; the
owner decides, and the decision is recorded where the process says (an
issue comment, an ADR, a decision card).

**The coordinator** is the agent session that talks with the owner, keeps
the work queue, starts and briefs threads, hands out tickets and reports
progress. It arranges for work to be done; it does not build, design,
ticket or review itself.

**Threads** are agent sessions that each do one kind of work: a build
thread implements tickets, a design thread writes designs and runs
architecture passes, the Main Health thread watches `main` and runs the
post-merge review, and short-lived threads run triage or skill-guided
interviews.

These are roles, not individuals. The sessions that fill them are rotated
regularly, because a session's accumulated context costs tokens on every
turn and a fresh session is cheaper than a long one. The process is
designed so that this rotation loses nothing: every rule, lesson and
procedure is institutionalised in the repo, and a new session in any role
is briefed with consistent instructions for that role. Quality never
depends on a long-running thread remembering the right way to do things.

Agents are matched to work by **capability tier**: a tier is defined by
the judgement a piece of work needs, not by a model name, so the process
works in any harness. Higher tiers do the work where a wrong answer is
expensive and hard to catch later: design, security reasoning, and the
critical reviews (the post-merge review, the architecture pass). Lower
tiers do the volume: building an already-designed slice, triage,
ticketing, watching `main`, and mechanical sub-tasks. The tier belongs to
the piece of work, not to the thread that orchestrates it: a build-tier
thread that runs the post-merge review hands the reviewing itself to
higher-tier sub-agents. The agent instructions define the tiers and which
stage each runs; one reference file maps each tier to a model on this
harness.

Design, build and independent review are kept in separate hands. That the
designer does not build is desirable rather than required: it controls
cost and keeps the high tier on design, and not every harness supports
that many threads. The
builder reviews their own work at merge (section 5), starting clean
sub-agents for part of it; further reviews by other agents follow after
merge, in the post-merge review and the architecture pass, and these are
never run by the agent whose work they cover.

- **SDLC-008**: The repo owner decides product scope, requirement wording,
  principles, the wording of SDLC statements, what is parked as an
  accepted gap, and releases. Agents propose and record; they do not
  decide these.
- **SDLC-009**: The coordinator hands out tickets, one at a time per build
  thread. A thread never picks its own next ticket.
- **SDLC-010**: Each piece of work runs on the capability tier its
  judgement needs: higher tiers for design, security reasoning and the
  critical reviews, lower tiers for build and mechanical work, so token
  spend follows the cost of a wrong answer. The tier applies to the work
  itself, so a lower-tier thread delegates higher-tier work to a sub-agent
  rather than doing it.
- **SDLC-011** *(desirable)*: The agent that designs a feature does not build it.
- **SDLC-012**: No change is reviewed only by the agent that built it.
  Every merged change is also reviewed by agents other than the builder,
  in the post-merge review and the architecture pass.
- **SDLC-013**: Threads are rotated regularly to keep context costs down,
  and every new thread receives consistent instructions tailored to its
  role, so the quality of the work does not depend on which session does
  it.
- **SDLC-113**: Any copy of authoritative process rules carried outside
  the repository for an agent that cannot read them there is held in the
  repository as a file of its own, is checked against a size limit, and
  carries a marker its reader must confirm so a truncated copy is
  detected. A mechanical check fails whenever a source rule it condenses
  changes without the copy being re-reviewed in the same change. A
  scheduled sweep audits the live harness text against the repository's
  copy.
- **SDLC-118**: Notes the coordinator records in a harness's project
  settings at the owner's request are never overwritten or removed when
  those settings are updated; only the owner, or the
  coordinator at the owner's direction, removes or rewords one.

Scheduling preferences that help the queue flow (bug fixes ahead of
feature work, a cap on concurrent build threads, when exactly a thread
hands over) are guidelines in the agent instructions' orchestration
section. The coordinator reads its rules from the coordinator core file
(`.forge/coordinator-core.md`), which the harness's project instructions
tell it to load at the start of each session. The file is the
authoritative text of the coordinator's own rules and condenses the
shared sources the other threads read; it is held in the repository,
checked against a size limit, and ends with a codeword the coordinator
must report so a truncated copy is detected (SDLC-113). The same project
instructions also carry the owner's own scope section and the notes the
coordinator records there at the owner's request; neither is derived
from the repository, and the notes survive every update (SDLC-118).

## 3. Tickets and the queue

All work is tracked as issues: in this repo's issue tracker, or on a
dependency's issue list where that is the right home and the agent has
access. A ticket is the unit of work a build thread takes, and the record
a PR points back to.

**Triage** moves a new issue to one of a small set of states, visible on
the issue, until it is either ready to build or parked. A ready ticket is
routed one of two ways: straight to a build when its behaviour is
specified and its structure is decided, or to a design-exit pass first
when the structure is still open (which module to extend, which sibling
shape to mirror, which seam to add). The design-exit pass decides the
structure and records the decision on the ticket, where it binds the
build the way a design-doc slice does. A label reference document says
which labels carry these states.

Every ticket also records, from the moment it is filed, how the release
notes will treat it: as something a user would notice, something an
integrator must act on, or internal work nobody outside the repo would
see. That classification is re-checked against the actual diff before
merge, so the release notes are decided when the work is fresh rather
than reconstructed at release time.

An issue that is not being built is **parked**, and the parking records
why: an accepted gap the owner has deliberately chosen not to work; an
idea the owner has said is deferred, waiting for its own scoping pass; a deferred architecture finding
from a review pass; or owner-triaged tech-debt that is scheduled work in
the normal queue. Each parked population has an owner, a revisit trigger,
a standing epic that collects it, and a defined treatment in the release
notes, so a parked issue is never simply forgotten.

A ticket can also carry an **open question for the owner** — raised at
any stage, not only the ones below that name open questions explicitly —
that blocks work regardless of the ticket's other state: no thread may
act on it until the owner has decided. This is flagged the same way the
other states are, so the question itself isn't lost in a comment thread,
and the flag comes off only once a thread has recorded the owner's
decision and its outcome. The same label reference document says which
label carries this state.

**Epics** group tickets that together deliver one outcome. A few issues
are standing trackers rather than epics: the post-merge review tracker,
the local full-suite evidence tracker, and the epics that collect each
parked population. They keep accepting children and never close.

A **queue sweep** is a report-only check for work that fell between
threads: review findings with no ticket, feature checklists that drifted,
unlabelled issues, ready tickets never handed out, overdue parked items,
and drift between the agent instructions and the harness project
instructions. It reports; the owner decides what happens to each gap.

- **SDLC-014**: Every merge to `main` is backed by a ticket, filed before
  the PR merges, and is traceable to an owner request. Traceable means an
  evidence-based chain, each link completing "this change is necessary to
  complete …", that ends at something the owner actually asked for: a
  ticket the owner raised and marked ready, an owner direction to start or
  un-park work, or a standing owner policy such as fixing Must and Should
  review findings (SDLC-037). A ticket alone is not a change request. The
  request a ticket serves is recorded no later than when work on it
  starts. This holds for process, tooling and docs changes as well as
  features and fixes. This chain bounds the change's scope, not just its
  existence: a change that generalizes a specific instance into a
  standing rule or capability goes beyond what the request supports
  unless the request itself asked for that generalization, and needs its
  own request before it merges. A thread unsure whether its change
  exceeds its request's scope asks the owner rather than assuming it's
  covered.
- **SDLC-015**: Every open issue shows its state, from newly filed
  through ready to build, or parked with its reason.
- **SDLC-016**: A ticket whose structure is not yet decided goes to a
  design-exit pass before it is built. On any doubt it goes to the design
  pass.
- **SDLC-017**: A ticket that needed a design-exit pass is built only
  after a design-tier agent has recorded the structure decision on it.
- **SDLC-018**: Every ticket records its release-notes classification
  from filing, and the classification is re-checked against the diff
  before its PR merges.
- **SDLC-019**: Only the repo owner parks an issue as an accepted gap.
  Ideas come from the owner or a skill-guided interview. A deferred
  architecture finding comes only from a review pass's triage or a
  builder's out-of-scope gap, never from an issue the owner raised.
- **SDLC-020**: A new idea is parked only when the owner says it is
  deferred. When the owner's words do not say deferred, or are unclear,
  the agent asks whether the idea is for now or deferred before filing
  it, and never assumes.
- **SDLC-021**: An epic is closed when its last sub-issue closes. A
  standing tracker stays open.
- **SDLC-022**: A ticket's own "done" checks are the tests near the change
  and coverage of the touched modules not dropping. A CI dispatch, a full
  suite run or a reviewer beyond the implementer is required only when the
  ticket or the owner says so explicitly.
- **SDLC-023**: A sweep for work that never got queued runs before every
  release and on a standing cadence. It reports gaps; the owner decides
  what happens to each. This governs the sweep's own after-the-fact
  gap-finding only; it does not require the owner's per-instance
  sign-off before the coordinator's own standing default queues a ready
  ticket as it becomes ready.

## 4. The lifecycle

Work reaches `main` by one of two routes. Quick, narrowly scoped work (a
bug fix, a small change whose behaviour and structure are already clear)
is built directly off its one ticket, as section 5 describes. Most work
is a feature, and a feature goes through a multi-stage pipeline
(section 4.2) that produces the design, the requirements, the tickets and
the reviews before and after the build. Both routes start after project
inception (section 4.1), which runs once, before any build work begins,
and sets the principles every later stage checks against. Bug fixes,
prototypes and remediation each have their own short path (sections 4.3
to 4.5).

### 4.1 Project inception (stage 0)

Before any build work begins, a skill-guided interview with the owner
draws out the principles every feature has to respect: what in the domain
will change underneath us, which external systems are trusted and how
far, which frameworks are built on rather than written, size and
complexity budgets, test philosophy and security posture, or any other open question the
interview and its research turn up. Each principle
the owner confirms is written, following a well-defined skill, into a
maintained principles document that every later design decision is
checked against.

- **SDLC-024**: Project inception runs once per repo, before any build
  work, and the principles document on `main` is its record.

### 4.2 The feature pipeline (stages 1 to 8)

Every new feature goes through the same eight stages, each leaving a
record the next stage points at. A well-defined skill is the stage-by-
stage reference, and the feature's own issue carries a checklist of the
stages, so the stages that are conversations rather than tickets are
tracked somewhere.

1. **Idea.** An issue records the problem in the owner's words, with the
   open questions, flagged (section 3) so none is lost before the owner
   resolves it. No design.
2. **Grilling for use cases.** A skill-guided interview with the owner
   records the use cases, the product constraints and any other open
   questions relevant to the idea, as the interview and its research
   determine, on the issue, and settles new terms into the domain
   glossary.
3. **High-level design.** A design-tier thread posts its design as one or more comments:
   facts verified against `main`, the architecture, the decisions, a
   security section, proposed requirement wording, and draft ADRs. Product
   questions go to the owner one at a time or in batches, as suits them.
4. **Requirements approval.** The owner approves the requirements
   specification wording on the issue,
   and a spec-only PR lands it.
5. **Detailed design.** The design-tier thread writes the feature's design
   document and the ADR files: invariants, a module map, a build-vs-buy
   line per new module, a threat-model delta, and one section per
   implementation slice with its interface, seam, guard test, file scope
   and blocking edges.
6. **Ticket it and queue it.** On the owner's word, the coordinator
   arranges for each slice to become a ticket, with the post-merge review
   ticket and the stage 8 architecture pass ticket filed behind them. The
   owner's word schedules the build; it is not a further approval of the
   design, which stages 3 to 5 already settled.
7. **Build.** Each ticket is built as section 5 describes. Once the last
   terminal slice merges, a small follow-up PR reconciles the design doc
   against `main`, and from then on the architecture description, the
   user and operator guides and the security docs carry the feature.
8. **Architecture pass.** Once the post-merge review has covered the
   feature's PRs, a design-tier agent that did not build the feature
   reviews the files it touched as a whole, and triages every finding.

- **SDLC-025**: Every new feature passes through stages 1 to 8 in order,
  and its issue's pipeline checklist records each stage as it completes
  or is skipped. One exception applies at stage 3: the design-tier thread
  may judge, against written criteria, that the whole feature can be
  built as one ticket with low risk of architectural drift. That feature
  skips stages 5 and 8, and its own issue becomes its build ticket.
- **SDLC-026**: The stage 3 design comment includes a security section,
  and the stage 5 design doc carries a threat-model delta.
- **SDLC-027**: The stage 5 design doc names, for every new module, the
  library adopted or the libraries considered and why each was rejected.
- **SDLC-028**: One design-doc slice becomes one ticket, split only along
  a seam the design doc already names.
- **SDLC-029**: When a build deviates from its design doc, the same PR
  updates the design doc and says why.
- **SDLC-030**: When the last terminal slice of a feature merges, a small
  follow-up PR — never the slice's own PR, and never a direct write to
  `main` — marks the design doc reconciled against `main` and carries
  the feature into the architecture description, the user guide and the
  security docs.
- **SDLC-031**: The post-merge review covering a feature's PRs runs before
  that feature's architecture pass.
- **SDLC-032**: Stage 8 is skipped in exactly two cases: the feature was
  exempted at stage 3 under SDLC-025, or its stage 5 design has only one
  slice. Every other feature gets one stage 8 architecture pass, run at
  design-tier by an agent that did not build it and scoped to the files
  its slices touched.
- **SDLC-033**: Every architecture-pass finding gets exactly one outcome:
  fixed now (a Strong finding), recorded as an ADR (rejected for a
  load-bearing reason), raised to the repo owner as an open question (a
  finding worth exploring), or parked as a deferred architecture finding
  (a weak finding).

### 4.3 Bug fixes

A bug is fixed from a **red loop**: first one command, run locally, that
goes red on the reported symptom; then hypotheses; then the fix; then the
same command green. That command is the PR's evidence, and the repro
behind it becomes the regression test.

- **SDLC-034**: A bug fix starts from one local command that goes red on
  the reported symptom, and the fix PR shows the same command green.
- **SDLC-035**: The repro that drove a bug fix becomes a permanent
  regression test in the matching test suite.

### 4.4 Prototypes

A prototype answers a question: a library trial, a spike, a UI variation.
It lives on its own clearly marked prototype branch, the verdict is
recorded on the issue it serves, and the decision lands on `main` while
the code does not. A prototype worth keeping is rebuilt through the
feature pipeline.

- **SDLC-036**: Prototype code lives on a prototype branch and never
  merges to `main`. Its verdict is recorded on the issue it serves.

### 4.5 Remediation

Review passes produce findings, and findings become work. Each finding is
classified by severity (Must, Should, Could, Won't); Musts and Shoulds get
fixed. To keep the queue readable, a post-merge review run files its
findings as one ticket per theme, with Musts kept apart so they are picked
up first. A finding that is really an open design question rather than a
quick fix is flagged to the repo owner, who decides whether to address it
or park it as a deferred architecture finding. Owner-triaged
tech-debt items from external reviews are built through the normal queue.

- **SDLC-037**: Must and Should review findings are fixed. Could and Won't
  findings are recorded in the run's archive and get no ticket.
- **SDLC-038**: A post-merge review run files its Should findings as one
  ticket per theme, and its Must findings in tickets of their own.
- **SDLC-039**: A review finding that needs a design decision beyond the
  finding itself is flagged to the repo owner, who decides whether to
  address it or to park it as its own deferred architecture finding. This
  is one kind of parked finding, whether it came from a post-merge review
  or a stage 8 architecture pass.
- **SDLC-116**: A gap a builder finds outside its ticket's scope is filed
  as a ticket of its own and not queued: the ticket raises it to the repo
  owner as an open question, or parks it as a deferred architecture
  finding when it is weak.

## 5. Building a ticket

A build thread takes one ticket at a time: it re-verifies the ticket
against current `main`, builds it test-first on a fresh branch, reviews
the result, opens a PR and merges it. Every build thread starts from the
same standing brief for its role.

The PR body follows the repo's PR template. Each line exists because
self-merge is the gate and the PR is the only record of what was checked:
**Ticket** names the issue, **Requirements** names the `FR-`/`NF-` IDs
touched, **Process** names the SDLC statements touched (for a change to an
artefact that enacts this process), **Release note**
carries the release-notes entries, **Evidence** pastes the command that
went red and then green, and **Door** says whether the change is one-way
or two-way, and its blast radius. A one-way door is a change that is
hard or impossible to undo, a two-way door one that is easily reversed,
and the blast radius is what else breaks, or who is affected, if the
change turns out to be wrong.

The merge gate is a set of reviews the implementer runs on their own
diff, in two parts. First a **code review** along two axes: **Standards** (does the
diff follow this repo's conventions and principles, and, where it changes
an artefact a skill governs, that skill) and **Spec** (does it
match the ticket and the requirements it touches). Then a **self-review**
of what neither axis is scoped to: every other caller and builder of what
the diff touches, reuse over recreation, both sides of any cap, the whole
class of a fixed finding, gates and guards the diff moves, concurrency
and lifecycle hazards, and whether new comments earn their place; the
list includes but is not limited to these. The self-review looks for
patterns of common error, and its set of patterns grows over time as the
post-merge review notices repeat offenders. No
reviewer beyond the builder's own sub-agents is required before merge;
the post-merge review (section 7) is the independent second review.

- **SDLC-040**: Each ticket is built on its own branch, cut fresh from
  `main` unless the ticket or the owner specifies otherwise, and named
  for what the change does.
- **SDLC-041**: Every PR body follows the PR template, with its Ticket,
  Requirements, Release note, Evidence and Door lines filled in, and its
  Process line too where it changes an artefact that enacts this process.
- **SDLC-042**: The merge gate is the builder's own review of the diff.
  The full gate is the default and applies to every change unless the
  light gate clearly applies. The full gate is a code review on the
  Standards and Spec axes, each run as an independent, clean-context
  review axis, followed by a self-review of every other path the diff touches,
  which the builder may run themselves. For an artefact a skill governs,
  the Standards axis also checks the change against that skill
  (SDLC-119). The light gate, the self-review
  alone, applies only to a change that meets every one of these
  conditions: it is a prose-only documentation edit; it changes no rule,
  requirement or behaviour; and it touches no text carried in the
  project settings' coordinator-core section. A change to code, tests,
  scripts, a requirement or spec, an agent instruction or skill, or text
  carried in that section never gets the light gate. Any change that does
  not clearly meet every light-gate
  condition, including one that appears to meet some conditions of each
  gate or is uncertain, gets the full gate. No full-gate change merges on
  an inline read of the diff in place of the directed review skills. No
  review by another thread is required before merge.
- **SDLC-043**: A build thread self-merges its PR once the merge gate is
  clear and any owner approval the change needs (SDLC-117) is recorded
  (SDLC-102), except where the owner has said to hold it. A recorded
  approval is the owner's own words in a post, a comment or chat,
  including a comment on the PR from the owner's own account, or an
  option the owner chose on a decision card.
- **SDLC-044**: A PR that fully implements a ticket closes it with a
  closing keyword, and the implementer checks the ticket's state after
  merge.
- **SDLC-045**: A closing step a ticket names (a doc cross-reference, an
  ADR amendment) is part of that ticket's PR. A step that depends on
  post-merge state, such as a feature-pipeline terminal-slice's
  design-doc status line, is checked after the merge and written by a
  small follow-up PR instead, never a direct write to `main`.
- **SDLC-046**: A review finding that is an instance of a pattern is fixed
  everywhere the pattern occurs, not only where it was reported.
- **SDLC-047**: Every commit passes the repo's local lint and format
  checks before it is made. No commit bypasses them.
- **SDLC-048**: The patterns the builder's self-review checks for grow
  over time: when the post-merge review notices a repeat offender, the
  pattern is added to the self-review.
- **SDLC-112**: Every skill that the process directs to be used is
  used. A required skill that cannot be found is not skipped and not
  replaced by the builder's own version: the builder stops and asks the
  coordinator for help, who escalates to the owner if it cannot be
  resolved.
- **SDLC-117**: Unless the repo owner directs otherwise for a particular
  change, a change needs the owner's approval before it merges to `main`
  only for: the wording of a requirement (SDLC-081), of an SDLC statement
  (SDLC-002) or of a principle (SDLC-068); and any other approval a
  numbered statement in this document requires for that change. Every
  other change may merge once its merge gate is clear, with no approval
  request; whether the agent or the owner performs the merge follows the
  route the owner chose for the work. This statement governs merging
  changes to the repo, not other agent actions, and relaxes no review a
  change must pass, including the review of process changes against this
  document (SDLC-005).
- **SDLC-119**: Where a skill sets the form or content of an artefact (a
  document, a test), that skill is the artefact's standard.
  Every change to the artefact follows it, and the Standards axis of the
  code review checks the change against it, alongside the repo's
  conventions and principles. A change on the light gate, which has no
  Standards axis, is checked against it in the self-review, and the
  post-merge review checks merged changes against it too (SDLC-064).

## 6. Test strategy

This repo's merge gate is deliberately optimised for ticket throughput: a
PR merges on its builder's own review of the diff plus a focused run of
the tests near the change, not on a full-suite or end-to-end run (SDLC-042,
SDLC-052) — pre-merge testing is partial, not absent. The full suites,
end-to-end included, run afterward, in one batched pass on the Main
Health thread's own schedule, not per PR.

Two independent reasons hold up that trade. First, full and end-to-end
testing is expensive to run; batching it lets one pass cover every PR
merged since the last one, instead of paying that cost on every single
PR. Second, a single PR's review is structurally weaker than a
post-merge review at catching the bugs that only exist once several
changes are present together — cross-PR interactions, migrations, and
resource exhaustion that only shows up under real execution (section 7's
post-merge review exists for exactly that class of bug, which a per-PR
review cannot see no matter how thorough it is). A third, supporting
reason: merging quickly avoids the conflict cost of long-lived branches
piling up against each other.

The price is real, and named here rather than left implicit: once a
change merges, `main` can run red from then until the next batched pass
catches the regression, plus however long the fix then takes. In an
agentic environment that fix is typically fast — the thread diagnosing it
usually still has the change's context fresh, and the fix is usually
itself a small, targeted PR — but the price is both halves, not just the
gap until detection.

The `green` branch is the mitigation: it tracks the newest commit a
batched pass has actually verified, so anyone who needs a
correctness-verified point to pin to, rather than tip-of-`main` during
one of those red periods, has one. Section 9 covers how a release uses
it.

Tests are how this repo knows a change works and keeps working, and with
self-merge as the typical gate they carry most of the assurance. A reference file
names the testing tools per language.

Behaviour is built **test-first**, through the public seam a caller would
use, so tests describe behaviour rather than implementation. A test that
asserts a guard or invariant (a permission check, a limit, a fail-closed
default) is proven by removing the guard and watching the test go red: a
guard test that passes either way protects nothing, and such tests are
easy to write by accident. Golden and snapshot tests are not written,
because regenerating one asserts the implementation back to itself.

A build thread runs **focused tests**: the files near the change, the
guard tests, and the files that reference what changed. The full suites,
including any **end-to-end** suite (the real system driven from outside
against stand-ins for its external dependencies), run on the Main Health
thread's schedule, not per ticket. **Mutation testing** is an audit, not a
gate: the post-merge review periodically samples a few modules, with the
owner's go-ahead, to find tests that kill no mutants.

Each test suite has a **coverage floor**, a minimum enforced by its test
configuration when the full suite runs. The floor is set from a measured
baseline and only moves up. Because the full suites run on the Main
Health thread's schedule rather than per PR, a PR protects coverage
locally: its scoped tests show the touched modules have not dropped.
Each floor lives in its suite's own test configuration, so it applies
identically wherever that suite runs under coverage, in CI and in the
local full-suite stand-in.

CI minutes are kept deliberately low. Every check workflow runs on manual
dispatch only, and only the Main Health thread dispatches them.

- **SDLC-049**: Behaviour is built test-first, through the seam a caller
  uses.
- **SDLC-050**: A test that asserts a guard or invariant is shown to go
  red with the guard removed, and the PR's Evidence line records that run.
- **SDLC-051**: Agents never write golden or snapshot tests.
- **SDLC-052**: A build thread runs the tests near its change. The full
  suites, end to end included, are run after merge by the Main Health
  thread, which confirms everything is green.
- **SDLC-053**: Every test suite has a
  coverage floor, set in that suite's own test configuration and applied
  wherever the full suite runs, in CI and locally.
- **SDLC-054**: A coverage floor only ratchets up. Raising one needs no
  approval; lowering one is a process change that needs the repo owner's
  approval.
- **SDLC-055**: A PR never lowers the coverage of the modules it touches,
  checked locally with the scoped tests before merge.
- **SDLC-056**: A PR that adds code which makes decisions (branches,
  error handling, retries, state transitions) includes tests that exercise
  those paths. Testing them is never left to a follow-up ticket. Code with
  no decisions of its own, such as configuration wiring or a pass-through,
  is exempt.
- **SDLC-057**: A suite without a coverage floor is recorded as an open
  gap with a tracking issue.
- **SDLC-058**: Mutation testing is a sampled audit inside the post-merge
  review, run only with the owner's go-ahead, and never a ticket check.
- **SDLC-059**: CI workflows are dispatched only by the Main Health
  thread, on its own schedule and only when `main` has moved, plus a
  single re-run to confirm a failure that looks infrastructural. No other
  agent dispatches or re-runs CI unless the owner asks, to control CI
  costs. Raising a workflow's timeout needs the owner's explicit approval
  first, for the same cost reason.
- **SDLC-109**: A `green` branch (`refs/heads/green`) exists. It is
  advanced only by an ordinary push — never `--force` — of a commit that
  the Main Health thread's local-full-suite stand-in or a dispatched CI
  run has confirmed passes, so it moves forward only through git's own
  fast-forward-only default push behaviour: never rewritten, never moved
  backward.
- **SDLC-110**: `green` is the pin-point for anyone who needs the newest
  correctness-verified commit instead of tip-of-`main`, insulating them
  from the red periods SDLC-052 and SDLC-059 accept as the cost of merge
  throughput.
- **SDLC-060**: Every test that proves a requirement carries that
  requirement's ID as a machine-readable marker, with the literal ID in a
  comment or docstring accepted as a fallback, so the requirement-to-test
  map for every suite can be derived from the tests.
- **SDLC-061**: The requirement-to-test map covers every suite, end to
  end included, and is generated from the markers, never maintained by
  hand.
- **SDLC-062**: The number of requirements with no marked test only falls:
  a PR that adds or changes a requirement's behaviour marks its tests, and
  existing gaps are backfilled over time.
- **SDLC-063**: Evidence that tests cannot carry, such as manual
  verification, performance baselines and guard-removal records, is kept
  in a short hand-maintained record that refers to requirements by ID,
  alongside the generated map.

## 7. Review and assurance layers

No single review sees everything, so assurance comes in layers, each
catching a class of problem the others structurally cannot.

1. **Self-review at merge**, per PR (section 5): conventions, the
   ticket's acceptance criteria, the requirements touched, and every other
   caller of what changed.
2. **The post-merge review**: higher-tier reviewers, never the builder,
   re-review every PR merged since a watermark, looking for what a per-PR
   review cannot see: cross-PR interactions, migrations, resource
   exhaustion under real execution, and guard tests that cannot fail. Its
   **security axis** reviews every PR through STRIDE against the threat
   model and the other security docs. A standing tracker issue holds its
   pending notes, watermark and run log.
3. **The Main Health thread**: a build-tier thread that dispatches the
   scheduled CI pass, runs the full local suite as a stand-in for
   per-merge CI, reports a red `main`, and orchestrates the post-merge
   review on its own routine, delegating the reviewing itself to
   higher-tier sub-agents.
4. **The stage 8 architecture pass**, per feature (section 4.2): judges
   seams, duplication, drift and other architectural weaknesses across all
   of a feature's slices together.

- **SDLC-064**: Every PR merged to `main` is re-reviewed by the post-merge
  review, on a standing cadence tied to merge volume so that no merged PR
  waits long for its second review.
- **SDLC-065**: The post-merge review includes a security axis that checks
  each PR for new attack surface, weakened or overlooked controls and security-doc
  statements made untrue.
- **SDLC-066**: The Main Health thread watches `main`, orchestrates the
  post-merge review, and reports a red `main` on the PR that caused it. It
  never pushes to `main` directly; a fix it is confident in goes through a
  small PR.
- **SDLC-067**: Review findings, from any layer, are classified Must,
  Should, Could or Won't.

## 8. Code-shape rules

Some standards are cheap to check mechanically and expensive to recover
from once broken, so they are backed by guards where a guard is possible
and by the code review's Standards axis where it isn't. The agent
instructions carry each rule's detail, its evidence and its guard. The
engineering and design principles sit above these rules, and both code
review and design-exit check against them. Some of those principles are
the rules here; others may be recorded at project inception.

The **"adopt the abstraction early, then stay on it"** rule covers
generic concerns such as data access, provider calls, scheduling, retries,
parsing, auth and caching. A mature library is adopted at design time
rather than hand-rolled, and once adopted, code goes through it. A bypass
is allowed when performance or functionality needs it, with a one-line
comment at the site and an ADR when it spans more than one call site. The
architecture description lists every adopted abstraction.

- **SDLC-068**: Every design decision is checked against the engineering
  and design principles. Only the repo owner approves a new, reworded or
  removed principle, explicitly and against its exact wording.
- **SDLC-069**: Modules and functions, in every language the project
  uses, may grow up to the size caps but never past them, and a guard enforces each cap once it
  is reached. Anything already over a cap when the cap was introduced is
  tracked in an allowlist.
- **SDLC-070**: A generic concern uses a mature library adopted at design
  time rather than hand-rolled code. Once adopted, code goes through it,
  and an unexplained bypass is a review finding.
- **SDLC-071**: Code nothing reaches is removed, along with comments that
  describe behaviour the code no longer has.
- **SDLC-072**: A guard's allowlist or baseline of known violations of a
  rule, such as code already over a size cap or dead code already found,
  only shrinks, and a PR that removes a violation lowers its entry in the
  same PR.
- **SDLC-073**: A code comment states only what the code cannot: an
  invariant, a guard reason, a hazard, or an interface contract.

## 9. Releases

A release is a deliberate decision by the owner to give consumers of the
software a stable point to pin to. It is an annotated tag on `main` with its
section in the release notes and a matching GitHub Release. A release
process document is the procedure. The notes are drafted from the PRs
merged since the last tag and their release-notes classifications.

- **SDLC-074**: The repo owner decides when to release, and tags and
  publishes it. Agents draft the notes and the commands and never tag.
- **SDLC-075**: Before a release, the sweep for unqueued work has run and
  the owner has decided each gap it reported.
- **SDLC-076**: Before a release's notes are drafted, the threat model has
  been reconciled against `main` since the previous release.
- **SDLC-077**: Every release's notes list its breaking changes
  explicitly, or say there are none.
- **SDLC-078**: Every release's known issues list each parked accepted
  gap a user or integrator could hit, and each open security gap from the
  threat model.
- **SDLC-111**: A release tags `green`'s current tip by default. The
  owner may instead dispatch CI against, and tag, a newer commit `green`
  hasn't reached yet, when a release needs to include work not yet
  verified.

## 10. The documents and their roles

This section is a map of every document the process produces or depends
on: what it is for, who changes it, and the commitment that keeps it
honest. The agent instructions record where each one lives; this section
deliberately does not, so a document can move without a change here.

Documents describe **how things are now, plus the open gaps**, not how
they came to be. A decision is cited by its ADR rather than narrated, and
an unaddressed gap is marked "Open gap" with a tracking issue.

- **SDLC-079**: Project documents describe the current state and its open
  gaps, never a history of how it was reached. ADRs, release notes, the
  decisions log and archived documents are records by nature and are
  exempt.
- **SDLC-080**: A change that makes a document untrue updates that
  document in the same PR.

### Requirements specification

The contract for what this project does: numbered `FR-` and `NF-`
requirements, each with a status, and a known-gaps table. Every change
traces to it. Its wording belongs to the owner; statuses follow the code.

- **SDLC-081**: Only the repo owner approves a new, reworded or removed
  requirement, and it lands in its own spec-only PR before the
  implementation that depends on it merges.
- **SDLC-082**: A change never silently breaks a requirement. A PR that
  would make a satisfied requirement untrue is fixed, or the requirement's
  status is downgraded with a tracking issue, in the same PR.
- **SDLC-115**: Every region of the code's behaviour is traceable, at
  least indirectly, to a requirement, an ADR, a design document or a
  recorded decision, so a reader of the code who knows those documents is
  not surprised by it. This asks for traceability, not for behaviour
  documented in detail.

### Architecture description

The architecture description says how this project is built at summary
level, for integrators and reviewers: its components, interfaces, data,
security features, deployment and open gaps. A project that outgrows one
document may add a subsystem-level design behind it. It takes over a
feature from its design doc once the feature is built.

- **SDLC-083**: The architecture description lists every adopted
  abstraction: the concern, the library, and the ADR that adopted it.

### Threat model and other security documents

The threat model is this project's STRIDE threat model: its assets, trust
boundaries, threats and controls as they are on `main`, the known gaps,
the risks the owner has accepted, and the commit it was last reconciled
against. Other security documents, where the project keeps them, cover
topics such as authorization policy, data-leakage paths, and backup and
restore. The incident-response runbooks are the procedures operators
follow. These documents are written for whoever assesses this project
for production, and are kept as current as the architecture description.

- **SDLC-084**: The security documents change with the code: a feature's
  threat-model delta is folded in when it is built, and a post-merge
  security finding that is a doc inaccuracy is fixed in the doc.
- **SDLC-085**: A new incident type a feature introduces gets a runbook.

### `CONTEXT.md`

The domain glossary: each term, a short definition of what it is, and
the synonyms to avoid. It is the shared language of issues, designs, code
and conversation. Terms are settled into it as they come up, mostly
during the skill-guided interviews.

- **SDLC-086**: The domain glossary holds only domain terms, and a new
  term is settled into it when it first comes up.

### Engineering and design principles

The principles document holds the principles every design has to
respect, each with its reason and how it is enforced, and with a strength
(Never or Default). They are covered by SDLC-024 and SDLC-068.

### Architecture Decision Records

One record per significant decision: the context, the alternatives
considered, the decision and its consequences. Unlike the other
documents, an ADR is a record, so it narrates how the decision was
reached. Other documents cite ADRs instead of repeating their reasoning.

- **SDLC-087**: A decision a later reader might reopen is recorded as an
  ADR, including a review finding rejected for a load-bearing reason.

### Feature design documents

A feature's detailed design (stage 5), written for the agents that build
it. Tickets point at its slices rather than restating them. It is
reconciled once the feature is built, and is the record of what was built
(SDLC-029, SDLC-030).

### Decisions log

Decisions that produced no code: a finding considered and declined, or an
idea named but not designed. It stops a settled question from being
reopened by someone who cannot see the closed issue.

- **SDLC-088**: Closing an issue as not planned, when it carries a real
  finding or proposal, adds a short entry to the decisions log in the
  same change.

### Release notes

What each release changed, for users and for integrators, newest first.
Entries are written in PRs ahead of time and gathered at release
(section 9).

### User guide and operator guide

The user guide tells users what the system does for them. The operator
guide tells operators how to configure, deploy and run it. Both describe
released behaviour in their readers' terms, and a project with no users
or operators yet records each missing guide as an open gap.

- **SDLC-089**: A change to user-visible behaviour updates the user guide,
  and a change to configuration or operation updates the operator guide,
  in the same PR.

### Operational constants

An inventory of the project's limits, intervals and tuning values, saying
which are deploy-time configuration and which are deliberately hardcoded
invariants.

- **SDLC-090**: A PR that adds or changes a limit, interval or
  tuning value updates the operational constants inventory.

### `lessons.md`

The history and worked example behind each one-line lesson in the agent
instructions: the mistakes this repo has paid for and the rule each one
produced.

- **SDLC-091**: Each lesson in the agent instructions has a matching
  section in the lessons document.

### `model-tiers.md`

Maps each capability tier to a model, per harness. Everything else talks
in tiers, so changing a model is a one-file change.

- **SDLC-092**: The tier-to-model mapping is the only file in the repo
  that names a model for a tier.

### Requirement coverage

Records which tests prove which requirements, at a finer grain than the
specification's traceability matrix. The map is generated from the
requirement markers in the tests, across every suite. A short
hand-maintained record sits beside it for the evidence tests cannot carry,
such as manual verification, performance baselines and guard-removal
records. It is backed by SDLC-060 to SDLC-063.

### PR template

The shape of every PR body (section 5, SDLC-041).

### Licences and `THIRD_PARTY.md`

Some agent skills are taken from third-party repositories.
`THIRD_PARTY.md` credits each one, and the licence texts live alongside
it.

- **SDLC-093**: Every third-party file taken into the repo is credited in
  `THIRD_PARTY.md` with its licence text alongside, in the same PR that
  adds it.

### Stakeholder progress material

Material, such as a slide deck with screenshots or a demo script, that
the owner uses to show progress to stakeholders without a running
instance. Not every project keeps one.

- **SDLC-094**: Where the project keeps stakeholder progress material, a
  change that makes new functionality visible to users updates it in the
  same PR.

### Post-merge review tracker

A standing tracker issue is the record of the post-merge review, both
what it still has to do and what it has done: a pending note for each
merged PR that no run has yet covered, the procedure's watermark, and a
log of each run's coverage and findings.

- **SDLC-095**: The post-merge review tracker references merged PRs
  needing review, as well as the review's current watermark and a log
  entry for every run.

### This document

The authority for process, changed only as section 1 describes.

- **SDLC-096**: Every PR that changes an artefact enacting this process,
  such as the agent instructions, a skill, the agent reference material or
  this document, names on its Process line the SDLC statements it
  implements or affects.

## 11. Evidence

A commitment nobody can check is a hope. This section names the evidence
that backs the process: what each part of it leaves behind, so a later
reader can see that it happened, who did it and what it found.

Much of that evidence already exists: the PR template's Evidence and
Door lines, the post-merge review's run log, the design record on a
ticket, the decision records, the release notes. The statements below
cover the places where the process would otherwise leave no record, or a
record that could be lost.

- **SDLC-097**: Every commitment in this document leaves evidence in the
  repo, the tickets or the PRs, where a later reader can check it. A
  commitment whose evidence nothing records is an open gap with a
  tracking issue.
- **SDLC-098**: Every review of a change leaves a record on the PR or
  ticket that says which review it was, which thread or sub-agent
  performed it (by a unique ID or a link where one exists), and at which
  tier, so a reader can see that different
  agents took different parts of the review.
- **SDLC-099**: Where tests are run locally in place of CI, every full
  run leaves a summary on the code-hosting platform that names the commit it covered and the
  result of each check.
- **SDLC-100**: Every PR records the tests it ran and whether coverage of
  the modules it touched held.
- **SDLC-101**: The outcome of each pre-release sweep, and the owner's
  decision on each gap it found that is not simply a missed ticket (the
  ticket itself records those), are recorded in the tracker, not only in a
  working scratch area.
- **SDLC-102**: Every owner approval this process requires is recorded
  where the approved thing lives, quoting the owner's exact words or
  linking the decision.
- **SDLC-103**: A scheduled assurance pass leaves evidence when it runs,
  and the absence of that evidence is taken as evidence that the pass did
  not run.

## 12. Configuration, dependencies and operations

The traditional configuration management, risk and measurement plans ask
for more than the sections above state. These SDLC statements close
those concerns.

- **SDLC-104**: Every third-party dependency, including libraries,
  container images and upstream dependencies this project vendors or
  pins, is consumed at a recorded, pinned version, and moving to a new
  version is a reviewed change.
- **SDLC-105**: Deployment and environment configuration is kept in
  version control with the code it configures, and a running production system's
  configuration is changed by changing the repo, not by editing in place.
- **SDLC-106**: A release tag identifies exactly the source and the
  dependency versions that were released, so the release can be rebuilt
  and compared with what was published.
- **SDLC-107**: Known risks to the product and the process are recorded
  where they can be seen and reviewed, security risks in the threat model
  and others as tickets, and the repo owner decides each accepted risk.
- **SDLC-108** *(desirable)*: The repo owner receives regular reports of work
  completed, work in flight, the queue remaining and any major issues.
