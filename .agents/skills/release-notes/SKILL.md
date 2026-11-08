---
name: release-notes
description: "Draft the next release's section of docs/release-notes.md from the PRs merged since the last tag, open its PR, then hand over the tag and GitHub Release text. Run by hand before tagging a release."
disable-model-invocation: true
---

# Release notes

`docs/release-notes.md` is the record of what each tagged release
changed, newest release at the top. This skill writes one release's
section, right before that release is tagged, from the PRs merged since
the last tag. Entries may be recorded ahead of time under an `## Unreleased`
section of the file, added only while an entry is waiting (a ticket that needs a note before its release); this
skill reads them, judges them with the PR-derived rows, and moves them
into the release section. The person who invoked the
skill (the repo owner, or the coordinator on their behalf) confirms every
judgement call; the skill drafts and asks (SDLC-074: agents draft the
notes and the commands, and never tag).

Always call this file and its sections **release notes**, never
"changelog": a project's `CONTEXT.md` may already give that word a
domain meaning, and one name avoids the collision either way.

Two readers, in this order:

- **Users** read the plain-language section. They know the product's own
  words (the terms in `CONTEXT.md`), not module names, PR numbers or
  config keys.
- **Integrators** (whoever deploys, operates, embeds or depends on this
  project) read "For integrators": contract, config and operational
  changes, and above all whether anything breaks.

The release procedure around this skill, including tagging, is the
project's release-process document (SDLC section 9; by convention
`docs/development/release-process.md`). Where the project has none yet,
say so to the person, treat it as an open gap, and use the defaults this
skill states (SemVer tag naming in step 5, the contract list the person
confirms in step 5).

## Tracker shorthand

The `gh api` calls below use these shell variables. The epic numbers come
from `.copier-answers.yml`, filled by `scripts/bootstrap.py`:

```bash
R=repos/forger88/TheForgeStaging
PMR=60
HANGING=342
ARCH=343
```

## Ledger

Steps 2 to 6 fill a **ledger**: a scratch table (in the scratchpad, never
committed) with one row per merged PR in the range and these columns:
PR, title, ticket, epic or feature, `Requirements:`, `Door:`, labelled or
legacy (with the release-note labels and the `Release note:` entry; a row
from the running draft has the draft as its source and the issue it
cites in place of the PR), area,
user-visible (yes/no and why), verdict, line. The verdict is one of
*enhancement*, *bug fix*, *integrator*, *internal*, *netted*, or *folded
into #N* (a PR merged into another row's line). The ledger is what makes
every later judgement checkable: each line in the notes traces to rows,
and each left-out PR has a verdict saying why.

## Labelled PRs and legacy PRs

A ticket carries release-note labels (`release:user`,
`release:integrator`, `release:internal`, plus `breaking`) and its PR a
`Release note:` field, re-checked against the diff before merge
(`docs/agents/triage-labels.md`, "Release-note labels"). A project
generated from TheForge has these from its first ticket; a repository
that adopted them later has PRs merged before that which carry neither. A
release range may hold both kinds, so classify each ledger row first:

- **Labelled**: the PR body has a `Release note:` field and its ticket
  release-note labels. Each bullet in the field is one entry, and its
  prefix says where it goes: `Enhancement / <area>`, `Bug fix / <area>`,
  `Integrator` or `Breaking` (`docs/agents/triage-labels.md`,
  "Release-note labels"). One PR can give several entries in different
  sections; give each its own ledger row, keyed by PR and entry. A field
  reading `none` with `release:internal` is one internal row. The entry's
  issue number is the `(#N)` at the end of its bullet: take it from the
  bullet, not from the PR's ticket. A bullet with no number is an exception
  (listed in chat, with the PR number, and never given a guessed one).
  Still run step 3's folding, step 4 (netting) and step 5 (the contract
  diff) over these rows: the field records one PR's view, and only the
  whole range shows a feature built across PRs, a change undone later or
  a contract the field missed. When the labels, the field and the diff
  disagree, the diff wins and the row goes on the "considered and left
  out" list as a disagreement.
- **Legacy**: anything else. Judge it with the full procedure below.

For labelled rows, "considered and left out" (step 7) lists only the
exceptions: rows with labels but no field, bullets with no issue number,
disagreements, and labelled user or integrator rows that were netted or folded. Legacy rows keep the
full list.

## Procedure

0. **Find or file the release ticket, then run the queue sweep.** Search
   open and recently-closed issues for "Release vX.Y.Z" (the version is
   often not known yet at this point — a placeholder title such as
   "Release (pending version)" is fine; step 5 renames it
   to "Release vX.Y.Z" once the version is confirmed there). File one if
   none exists
   (`Requirements: none (internal)`). Then run the queue sweep (unless a
   `queue-sweep` report already exists for today's `origin/main` head —
   `.agents/skills/queue-sweep/SKILL.md`) and post its report as a
   comment on the release ticket (SDLC-075, SDLC-101) — not only to the
   owner in chat, which leaves no durable record. For each gap the sweep
   found that isn't simply a missed ticket (a ticket itself is its own
   record): once the owner decides to queue it, defer it or accept it,
   record that decision as its own follow-up comment on the release
   ticket, quoting the owner's words. Done when every such gap has a
   recorded decision — this step exists so a thread invoking
   `release-notes` directly, rather than through the release-process
   document, can't skip the sweep or its recording.

0b. **Gate on a reconciled threat model** (SDLC-076). Read
    `docs/security/threat-model.md`'s "Last reconciled against `main` @
    `<sha>`" line. The reconcile must be at or after the previous release
    tag — the newest tag, `git tag --sort=-v:refname | head -1` (step 1
    below fixes this same value as the range's base; for a backfilled
    release, that's the tag *before* the one being backfilled, per step
    1's own definition there, not the newest tag): `git fetch origin
    main` then `git merge-base
    --is-ancestor <base-tag> <sha>` must succeed — the reconcile sha has
    to be the base tag itself or a descendant of it, not merely at or
    after some older commit. If it isn't:
    - run a full reconcile using `.agents/skills/security-docs/SKILL.md`'s
      **reconcile** mode against current code on `origin/main`
      (`.forge/requirements-driven-changes.md` doesn't apply here — this
      is a docs correction, not a requirement change) — don't re-derive
      the reconcile procedure here, that skill is the one copy of it;
    - land it as its own ticketed docs PR (`Requirements: none
      (internal)`; use the release ticket step 0 found or filed) and get
      it merged before continuing;
    - re-read `origin/main`'s head before step 1, in case the reconcile
      PR's merge moved it.

    Done when the threat model's reconciled sha is at or after the
    previous release tag.

1. **Fix the range.** The base is the newest release tag
   (`git tag --sort=-v:refname | head -1`); the head is the commit this
   release will be cut from: `green`'s current tip by default, or a newer
   `origin/main` commit when the owner chooses one (SDLC-111), after
   `git fetch origin main green`.
   For the first tagged release, there is no prior tag: the range runs
   from the repository's first commit (`git rev-list --max-parents=0
   HEAD`) to the head commit above.
   When backfilling a release that is already tagged, the head is that tag
   and the base is the tag before it. Counts and blame need full history:
   if `git rev-parse --is-shallow-repository` says `true`, run
   `git fetch --unshallow origin` first.
   Name both SHAs and the commit count (`git rev-list --count
   <base>..<head>`) to the person, and the next version as a placeholder
   until step 5 settles it. Done when the person has agreed the range.

2. **List every PR in the range.** Walk
   `git log --first-parent --format='%H %s' <base>..<head>`. A squash
   merge ends its subject with `(#N)`; a merge commit reads
   `Merge pull request #N`. A commit with neither gets its own ledger row
   keyed by SHA. Read each PR's title and body with
   `gh api "$R/pulls/<N>"` (REST works everywhere,
   including sessions where `gh pr` and its GraphQL calls are blocked).
   The body's template fields are the primary source: Before/After,
   `Ticket:`, `Requirements:`, `Door:` and blast radius. Where a field is
   missing (older PRs that predate the template), read the ticket and the
   diff's file list instead. Record in each row whether it is labelled or
   legacy, and for a labelled PR one row per `Release note:` entry
   (see "Labelled PRs and legacy PRs"). Past about 60 PRs, split the range into
   batches and give each batch to a subagent with the ledger columns as
   its output schema. Done when every first-parent commit in the range
   has a ledger row with every column filled except verdict and line.

   **Read the running draft.** Read every entry under `## Unreleased` in
   `docs/release-notes.md` into the ledger as its own row (source: the
   running draft, with the issue it cites). It goes through steps 3 to 5
   like a PR-derived row. An entry is never dropped silently: it is kept,
   merged with the PR row it duplicates, or listed under "considered and
   left out" with the reason, and the person confirms. Done when every
   draft entry has a row.

3. **Judge each row.** A labelled row takes its verdict from its entry's
   prefix, as "Labelled PRs and legacy PRs" says; check it against the criteria
   below and record a disagreement. A legacy row gets a line in the notes
   when any of these hold:
   - it is **user-visible**: a user would notice it (a new
     control, a changed behaviour, a fixed symptom), whether or not it
     changed a requirement;
   - it touches a **contract or config** (step 5's list);
   - it is `Door: one-way` (a migration, a cutover, a deletion), which an
     integrator needs to plan for.

   Everything else is *internal*: `Requirements: none (internal)` work,
   refactors, tests, CI, docs, agent skills, and fixes to bugs no user
   could reach. Internal rows collapse into one closing count ("plus N
   internal changes"). A row whose `Requirements:` line says internal but
   whose Before/After describes something a user sees is user-visible;
   the Before/After wins.

   Then **fold features**: PRs that build one feature (the slices of a
   design doc, a feature and its follow-up fixes, the PRs under one epic
   that ship one capability) become a single line, referenced by the
   feature's issue or epic. Fixes found by a review pass (the post-merge
   review tracker #60, or a stage 8 architecture pass) to a
   feature first shipped in this same range fold into that feature's
   line rather than appearing as bug fixes. Done when every row has a
   verdict.

4. **Net out what cancels.** A change that was introduced and undone
   inside the range is left out entirely: not reported as a fix, not
   listed as a known issue. The common shape is a bug fix whose bug was
   itself introduced after the base tag. Decide from evidence:
   - the fixing PR's ticket or body names the PR that introduced the bug;
     check that PR's merge is inside the range;
   - otherwise, `git log -L` or `git blame <base>` on the lines the fix
     changed: if those lines did not exist at the base tag, the bug never
     shipped.

   The same applies to a feature added and reverted, or a config key added
   and renamed, inside the range: report only the end state. Where the
   evidence is unclear, ask the person rather than guess. Done when every
   bug-fix row is either confirmed as fixing something that shipped at or
   before the base tag, or marked *netted* with the PR that introduced it.

5. **Diff the contracts.** Each contract the project's integrators
   consume is diffed between the base tag and the head (`git diff
   <base>:<old path> <head>:<path>`, then read the change, not just its
   size). Paths move between releases, so find each file's path at the
   base tag with `git ls-tree -r --name-only <base>` before diffing. Each
   change becomes an integrator line, and a removed or changed (not merely
   added) item is a proposed breaking change.

   The list of contracts and where each lives is project-specific: read it
   from the release-process document. Where the project hasn't written one
   down yet, draft it with the person from rows like these, then propose
   recording it in the release-process document in its own ticketed PR:

   | contract (typical rows) | where it lives |
   |---|---|
   | Public API: endpoints, request and response shapes, or a library's exported interface | the route definitions, schema files or public module surface |
   | Events, messages or wire frames, both directions | the module that defines them |
   | Health, metrics and log shapes operators scrape | their handlers and the logging setup |
   | Container entry point and health check | the project's `Dockerfile` or equivalent |
   | Config keys, defaults and environment variables | the shipped config defaults and the config models that read them |
   | Embedding surface (props, events, methods) for anything a host application vendors | the project's integration guide |
   | Pinned dependency set | the project's lock and pin files, and any base image digest (SDLC-106) |

   The pinned-dependency-set row is diffed the same way: each moved
   runtime pin (not a dev-only one) becomes a "For integrators" line, and
   a major version move to a runtime dependency is proposed as a breaking
   change the same as any other contract row. If the project publishes a
   "tested with" table for integrators, regenerate it from the head's lock
   files in the same pass, so it never drifts from what was actually
   tested.

   If the release-process document calls for an SBOM (SDLC-106), generate
   it here from a clean environment built from the head's pinned
   dependency files, using the SBOM tool the project pins in its dev
   dependencies. Step 9 hands its upload command to the person alongside
   the tag and Release commands; generating it is this skill's job,
   attaching it to the Release is theirs.

   Diff config as the set of keys and environment variable names, not as
   text: many keys exist only as model defaults, not in a shipped YAML or
   env file, and renames hide in PRs whose `Requirements:` line says
   internal. If the config loader refuses unknown keys, a removed or
   renamed key stops a deployment that still sets it: that is a breaking
   change. An added key, field or message type is an integrator line, not a
   breaking change, unless the project now requires it. A renamed or
   removed one, a changed default that alters behaviour, or a narrowed
   message type is breaking. Propose each breaking entry to the person with the
   diff that shows it; they confirm or drop it (SDLC-077). Then suggest
   the version bump by the release-process document's tag-naming rules,
   or by SemVer where it has none (MAJOR for a confirmed breaking change
   to a consumed contract, MINOR for a normal batch, PATCH for fixes
   only); the person decides. Once they confirm the version, rename step
   0's release ticket to "Release vX.Y.Z" if it was still carrying its
   placeholder title. Done when every contract has been diffed and each
   has either its proposed lines or "no change".

6. **Draft known issues** (SDLC-078). Sources:
   - open issues labelled `bug` that a user could hit
     (`gh api --paginate "$R/issues?labels=bug&state=open&per_page=100"`,
     skipping pull requests in the result). `bug` is not one of the
     canonical triage labels (`docs/agents/triage-labels.md`), so it is
     usually sparse: most post-merge review sub-issues carry
     `ready-for-build` or `ready-for-structure` instead, and some bug-shaped
     issues carry no label at all. Treat a `bug`-labelled result as a
     partial list, never as "done";
   - to compensate, also read open issues labelled `ready-for-build`,
     `ready-for-structure`, and `needs-triage`
     (`gh api --paginate "$R/issues?labels=ready-for-build&state=open&per_page=100"`,
     likewise for `ready-for-structure` and `needs-triage`), and the open
     sub-issues of the post-merge review tracker. The tracker can have more
     than 30 sub-issues, and `sub_issues` with no `per_page` returns only
     the oldest 30 (GitHub's default page size) with no filter for state —
     paginate it and filter to open ones:
     `gh api --paginate "$R/issues/$PMR/sub_issues?per_page=100" --jq '.[] | select(.state=="open")'`
     — read titles for a user-reachable bug description; most of these
     sub-issues are process or review findings, not user-facing, so most
     will be judged not user-facing rather than drafted;
   - **hanging items.** Treatment per `docs/agents/triage-labels.md`,
     "Parking labels": each open issue a user or integrator could hit
     becomes a Known issues entry, the rest are noted as not user-facing.
     This needs two queries, unioned — the `hanging` label and the
     hanging epic's sub-issues can disagree (an issue can carry the label
     without being a child yet, or be a child without the label):
     `gh api --paginate "$R/issues?labels=hanging&state=open&per_page=100" --jq ".[] | select(.pull_request | not) | select(.number != $HANGING)"`
     and
     `gh api --paginate "$R/issues/$HANGING/sub_issues?per_page=100" --jq '.[] | select(.state=="open")'`
     — the same pagination gap applies here: without `per_page`, GitHub's
     default page size silently truncates. Dedupe the two queries by issue
     number before drafting; several items can fold into one known-issue
     sentence;
   - **count of deferred architecture findings.** Treatment per
     `docs/agents/triage-labels.md`, "Parking labels": the open
     `deferred-arch-finding` issues make one summary count line, in
     the shape "N further architecture findings are deferred rather than
     scheduled (epic #343). …" plus a one-sentence theme drawn from their
     titles. An issue already listed individually elsewhere in this
     section stays listed, and also stays in this count — don't subtract
     it:
     `gh api --paginate "$R/issues?labels=deferred-arch-finding&state=open&per_page=100" --jq '.[] | select(.pull_request | not) | .number' | wc -l`
     — don't combine `--paginate` with `--jq '... | length'`: that gives a
     count **per page**, not a total, and undercounts past one page; emit
     one number per issue and count the lines (or use `--slurp`).
     Cross-check against
     `gh api --paginate "$R/issues/$ARCH/sub_issues?per_page=100" --jq '.[] | select(.state=="open")'`
     — the two should agree; a child missing `deferred-arch-finding` is
     a labelling bug to flag, not to silently reconcile. Take this count
     at step 6 time, as close to tagging as practical: an issue filed
     between when the count is taken and when the tag is cut makes the
     published number stale — re-take it if anything was filed in
     between;
   - for a backfilled release, the same queries with `state=all`, keeping
     issues created before the tag and closed after it (or still open) —
     for the hanging and deferred-findings queries above, since
     `sub_issues` has no state or date filter, filter its `created_at` /
     `closed_at` fields in `--jq` instead;
   - accepted risks recorded on `main` and still true at the head: the
     Consequences sections of ADRs, the architecture description's open
     gaps, the requirements specification's "Known gaps" section, and
     `docs/security/threat-model.md`'s "Accepted risks" section;
   - **every open row in `docs/security/threat-model.md`'s "Known gaps"
     table** (step 0b's gate means this table is always current as of
     this release). List each Must/Should row individually, naming its
     tracking issue; fold Could rows into one summary line (count plus a
     one-sentence theme) the same way the deferred-architecture-findings
     count above does, unless there are few enough to list individually.

   Write each as one plain sentence about what a user or integrator may
   see, not about the code. The person curates this list; offer it as a
   draft. Done when every source above has been read and each candidate is
   drafted or noted as not user-facing.

7. **Write the section and show it.** Write the section into
   `docs/release-notes.md` above the previous release, in the shape
   below. Then show the person, in chat:
   - the section as written;
   - **considered and left out**, one line each with the reason (this
     list goes in chat only, never into the file): for legacy rows, every
     netted row and every row judged internal that a reader might have
     expected to see; for labelled rows, only the exceptions "Labelled PRs
     and legacy PRs" names;
   - the proposed breaking changes and version bump from step 5;
   - every question still open.

   When the section is written, the `## Unreleased` entries move into it
   (merged into the lines they belong to) and the `## Unreleased` heading
   is removed; the next ticket that needs an advance note adds it again.

   Done when the person has confirmed the section, the breaking changes
   and the version, and every question has an answer.

8. **Open the PR.** Every merge to `main` needs a ticket: use step 0's
   release ticket (`Refs`, since that ticket covers the whole release,
   not just this PR). Cut a branch
   named for the change (`release-notes-vX-Y-Z`) from `origin/main`,
   commit only `docs/release-notes.md` (the new section and the removed
   `## Unreleased`, if there was one), and open the PR with the
   repository's template: `Requirements: none (internal)`, `Door:
   two-way`. The person merges it after review. Once you see it merged,
   post the merge's pending post-merge-review note on the tracker, in the
   form `.agents/skills/post-merge-review/SKILL.md`, "Pending reviews",
   gives. Done when the PR is open and its link is with the person.

9. **Hand over the tag and the GitHub Release text.** The tag goes on the
   merge commit of step 8's PR, so the tagged tree carries its own
   notes. A release tags `green`'s tip by default (SDLC-111), so either
   wait until `green` reaches that merge commit, or the owner chooses to
   dispatch CI against it and tag it ahead of `green`. `green` can lag
   `main`, so before waiting, ask the owner whether the Main Health thread
   should run a fresh local full-suite pass now
   (`.agents/skills/watch-main-ci/SKILL.md`, "Routine 2") rather than
   leaving it to the next scheduled run; whether it runs is the owner's
   call (SDLC-074). Print, for the person to run or approve:
   - the annotated tag command from the release-process document (or
     `git tag -a vX.Y.Z <sha> -m "<summary>"` where it has none), with a
     two-to-three-sentence summary of the release and its
     breaking-changes line;
   - the new section, verbatim, as the body of the GitHub Release for that
     tag, replacing whatever body a backfilled release already has;
   - if step 5 generated an SBOM, the `gh release upload vX.Y.Z <sbom file>`
     command for it, beside the tag and Release commands (SDLC-106).

   A backfilled release is already tagged, so only the Release body
   applies. Done when all of these are printed. Setting the tag,
   publishing the Release, and attaching the SBOM are the person's
   actions (SDLC-074).

## Section shape

```markdown
## vX.Y.Z (YYYY-MM-DD)

<One or two sentences: what this release is about, in users' words.>

### Enhancements

#### <Area>

- <The new capability, key words in **bold**, near the start.> (#N)

#### <Another area>

- ...

### Bug fixes

#### <Area>

- <The bug as it was, in the past tense.> (#N)

### Known issues

- <What a user may see, and any workaround.> (#N)

### For integrators

**Breaking changes: none**

- <Config, contract or operational change, naming the key, message type,
  field or endpoint.> (#N)

Plus N internal changes.
```

- Headings: release, then the three user subsections, then "For
  integrators". Inside the user subsections, group by product area, taken
  from the project's list of user-facing areas (stage 0 writes this list
  into `CLAUDE.md`'s "This project's own rules" section; the same list the
  `Release note:` field's `<area>` uses), plus another area only when a
  release's changes fit none of these. An area with nothing in it is
  omitted; a user subsection with nothing in it says "None."
- The **breaking-changes line is always present** (SDLC-077):
  `**Breaking changes: none**`, or `**Breaking changes:**` followed by one
  bullet per confirmed break saying what changed and what an integrator
  must do.
- Every bullet, in every subsection, ends with an issue or epic reference
  in parentheses: the feature's issue or epic for a folded line, the bug
  issue for a fix, the ticket for an integrator change. Use the PR number
  only when there is no issue.
- Don't hard-wrap the file: each paragraph and each bullet is one
  line, and the renderer wraps it.
- Each bullet is one short sentence, readable without opening the
  reference. The whole section should read in a few minutes.
- **User entries raise awareness; they are not usage instructions.** Say
  *what* exists, not *how* to use it, unless the change in how was the
  point. Don't address the reader ("You can..."). Keep detail and word
  count low, bold the key feature, and put the most impactful phrase near
  the start. Follow the product's own capitalisation for its named
  features, as `CONTEXT.md` writes them.
  - Enhancement: "Added **CSV export** of the overdue-invoice report.
    (#<n>)", not "You can now click Export on the report page and choose
    CSV to download the rows you can see."
  - Enhancement: "Reports can now be **scheduled** to arrive by email on
    a regular cadence. (#<n>)"
- **A bug fix states the bug in the past tense, not the fix.** "Large
  exports silently stopped at the first thousand rows. (#<n>)", not "Large
  exports now include every row." "The search box ignored a trailing
  space, so an otherwise exact match silently found nothing. (#<n>)", not
  "Search now trims trailing spaces."
- Known issues and the integrator section keep their fuller wording:
  integrators need the key, message type or endpoint and what to do.
- The date is the day the tag is set (for a backfilled release, the
  tag's own date).
- The first tagged release gets the same full treatment as any other:
  Enhancements, Bug fixes, Known issues and For integrators, drafted from
  the ledger the usual way. It opens with one short paragraph saying it
  is the first tagged release and what it is, before the subsections.
