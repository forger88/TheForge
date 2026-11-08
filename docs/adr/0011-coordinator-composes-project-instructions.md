# ADR-0011: The coordinator composes the project instructions; a lead repository named by the owner breaks ties

**Status:** superseded by ADR-0012; the composer it describes was retired

## Context

A harness gives a project one instructions field. A project can work across several repositories that are forge consumers, and each one generates its own condensed copy of the coordinator and build-thread-brief skills (SDLC-113). Pasting one repository's copy makes every other repository's `queue-sweep` check 7 report drift. Copying several in by hand is the hand-compression SDLC-113 rules out.

Three things make member copies differ, even when every repository consumes the same forge:

- **Pins**: repositories sync at different times.
- **Copier answers**: the working folder and the post-merge review tracker are rendered into the copied rule text.
- **Logged overrides**: a project may edit a forge-owned skill and record the edit in `docs/forge-overrides.md`.

The host's size limit is close to full with one repository's copy, so composition cannot repeat shared text once per repository.

## Decision

1. **Contributions.** Each forge consumer's generated file is its contribution. Its shared sections carry no copier answer. The answer values the condensed rules need move into a per-repository Repo facts row, rendered from a Jinja file, so the generator never parses `.copier-answers.yml`.
2. **A composer the coordinator runs.** `scripts/compose_project_instructions.py`, run from the lead repository's checkout with the path of every member the harness lists for the project. It reads each member at its `origin/main` and writes, in order:
   - the owner's content, verbatim (everything above a fixed marker line);
   - a provenance line;
   - the lead's shared sections, once;
   - one Repo facts table;
   - per-repository deltas.
3. **The lead.** The owner names the lead repository on a `Lead repo: <owner>/<name>` line in their scope section. A single-repository project needs no line. The lead must be a forge consumer.
4. **Conflict rules, by whose work a section governs.**
   - **Coordinator-scoped sections** (boot routine, tier map, coordinator rules) come only from the lead. Where a same-pin member differs, that is a contradiction: the coordinator files a `needs-decision` ticket in the lead repository.
   - **Repo-scoped sections** (approval list, build-thread brief) let a same-pin member's differing load-bearing blocks through verbatim (for the approval list, which has no tagged blocks, its whole list), labelled with that member, because they govern work inside it.
   - **A member on a different pin** gets one line naming its pin. Its own full skills win for work inside it, and no one is asked.
   - **A non-consumer member** gets one pointer line.
5. **Fail closed.** The composer refuses, and writes nothing, when:
   - the live text has generated sections but no marker (a live text with no generated sections at all is a first composition, and all of it is the owner's);
   - the lead is missing or ambiguous;
   - a fact cell is malformed;
   - the result is over the size limit;
   - the coordinator-notes zone would change (SDLC-118).

   It never trims.
6. **One audit.** The composer's `check` mode backs `queue-sweep` check 7(b), which runs in the lead repository's sweep only. Every repository's sweep still checks that its own contribution is current, in check 7(a).

## Consequences

- SDLC-113's meaning is unchanged:
  - the composed text is produced by a generation process;
  - it is checked against the size limit and against every load-bearing block it carries;
  - it is audited by a scheduled sweep;
  - a different-pin member's skill is not carried at all, only pointed at.
- Single-repository projects keep today's behaviour, plus a one-row Repo facts table.
- Owner content needs a one-time migration: inserting the marker line above the first generated heading.
- A template repository that does not yet consume its own template cannot lead a project.
- Size pressure grows by about one table row per member, not by one copy per member.

## Alternatives rejected

- **A member list kept in the lead repository.** Membership is a fact about the project, not about any repository, and a repository can belong to several projects. The harness's own project configuration is the source.
- **Discovering members from `.copier-answers.yml`.** It shows whether a checkout consumes the forge, not whether the checkout belongs to this project. The composer uses it only to classify each member and read its pin.
- **Concatenating every member's full copy.** This goes over the host's size limit at two repositories.
- **Having the composer normalise answer values out of rendered text.** Answer values such as a tracker number or a folder name collide with ordinary text. Moving the values out of shared text at the source makes same-pin comparison exact.
- **Letting a member's coordinator-level override apply.** There is one coordinator. Two repositories cannot both govern it, so the disagreement goes to the owner.
