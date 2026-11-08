# Composing one set of project instructions from several forge repositories

**Status:** superseded by ADR-0012; the generator and composer this document specifies were retired, and the coordinator core and its snippet replace them. Kept as the record of what was built.
**Tracking issue:** "Let the coordinator compose one set of project instructions from several forge repos". That issue holds the owner's direction, the high-level design (stage 3), and its verified facts. This repository has no requirements specification, so that issue is the requirement record. No slice here adds or changes requirement wording, and no SDLC statement changes (the stage 3 comment explains why SDLC-113's meaning holds).
**Decision record:** ADR-0011.

**Superseded in part:** the notes check and its constants (`notes_check`, `extract_notes_zone`, `NOTES_HEADING`, `MARKER`) now live in `scripts/check_coordinator_core.py` as `notes_problems` and its siblings (ADR-0012); read the names below accordingly.

This document is written for the agents that build the slices. Each slice section is that slice's contract.

## Goal

A project can work across several repositories, each a forge consumer with its own generated condensed copy of the coordinator and build-thread-brief skills. The harness gives the project one instructions field. Today whichever repository's copy was pasted last wins, and every other repository's `queue-sweep` check 7 reports drift against it.

After this design:

- each repository's generator writes that repository's **contribution**, never pasted on its own in a multi-repository project;
- the coordinator runs a **composer** that builds the one text from every member's contribution;
- a **lead repository**, named by the owner in their scope section, breaks ties;
- a real contradiction goes to the owner, and version skew does not;
- one audit, in the lead repository's sweep, checks the composed text.

A single-repository project keeps working as it does today: its one repository is the lead, and the composed text is its generated text plus a one-row Repo facts table.

## Out of scope

- Making room under the host's size limit. The generated copy already uses most of it, and the owner has parked that risk as hanging (issue "Generated project instructions leave almost no room for the owner's scope section and coordinator notes"). This design keeps composition from making it worse and fails closed when the text will not fit. It never trims anything.
- Writing the composed text into the harness's settings. The coordinator does that with whatever its harness offers, or hands the text to the owner, as it does today for a re-paste.
- Composing rules from a member that does not consume the forge. Such a member gets a one-line pointer only.
- The template repository leading a project before it consumes its own template. That is the self-governance design's job (`docs/design/theforge-self-governance.md`, slices 3 and 4).

## Terms

- **Member**: a repository the project works in, as the harness's own project configuration lists it.
- **Forge consumer**: a member whose `origin/main` has a `.copier-answers.yml` with a `_commit` line and a generated `docs/agents/condensed-project-instructions.generated.md`.
- **Pin**: a forge consumer's raw `_commit` value. Copier writes it as `git describe --tags --always`, so it may be a short SHA, `<tag>-<n>-g<sha>` or a bare tag. Two pins are the same only when the strings are equal. The same commit spelled two ways counts as skew, which costs one extra delta line and nothing else.
- **Contribution**: a forge consumer's generated file at its `origin/main`.
- **Top-level sections**: the generator's own four, found by its heading constants: `## Boot routine`, `## Decision facts`, `## Coordinator`, `## Build thread brief`. Every `##` or `###` heading below one of them, up to the next top-level heading, belongs to it. For example, the coordinator summary's own `## Skills and tiers` to `## Progress reports` all belong to `## Coordinator`. Decision facts is compared as its two `###` parts, the tier-to-model map and the approval list.
- **Shared sections**: every top-level section of a contribution. Repo facts is not one.
- **Repo facts**: the contribution's `## Repo facts` section, a one-row table of this repository's own values.
- **Lead**: the member named on the owner's `Lead repo:` line, or the only member when there is one.
- **Owner content**: everything in the live instructions text above the marker line, which is the owner's scope section plus the coordinator-notes zone (SDLC-118).
- **Coordinator-scoped section**: Boot routine, Decision facts' tier-to-model map, Coordinator. These govern the one coordinator.
- **Repo-scoped section**: Decision facts' approval list (source: `.forge/process-and-evidence.md`), Build thread brief (source: `.agents/skills/build-thread-brief/SKILL.md`). These govern work inside one repository.

## Invariants every slice keeps

1. **I1. Shared sections carry no copier answer.** Two renders at the same template commit with different answers produce byte-identical shared sections. Every answer value the condensed text needs lives in Repo facts.
2. **I2. Owner content is never generated.** The composer's output above the marker is byte-identical to the live text above the marker, and `notes_check(live, new)` passes on every write (SDLC-118).
3. **I3. Coordinator-scoped text comes only from the lead.** No member other than the lead puts a single line of coordinator-scoped text into the output.
4. **I4. Fail closed.** On any refusal listed under slice 2, the composer writes no output file and exits 1. It never writes partial output, and it never trims to fit.
5. **I5. Read members at `origin/main`, never from the working tree.** Every member file the composer reads, it reads with `git -C <path> show origin/main:<file>`.
6. **I6. Standard library only.** The composer runs under `python3` with nothing installed, like every other guard script under `template/scripts/`.
7. **I7. Every carried load-bearing block is present verbatim.** The composer's self-test checks the lead's blocks and every member block it carries in a delta, the same way the generator's `self_test` does.
8. **I8. Forge-owned rule files stay one sentence per line.**

## Module map

| Module | New or touched | Its one job | Named hook |
|---|---|---|---|
| `template/.agents/skills/coordinator/repo-facts.md.jinja` | new (slice 1) | One Repo facts row, rendered from this repository's answers | read by `build_repo_facts_section()` |
| `template/scripts/generate_condensed_copy.py` | touched (slices 1, 2, 3) | Writes this repository's contribution | slice 1: `build_repo_facts_section()` and the top-level heading constants; slice 2: `MARKER`, `extract_notes_zone`; slice 3: `PREAMBLE` |
| `template/.agents/skills/coordinator/SKILL.md.jinja` | touched (slices 1, 3) | Coordinator rules | slice 1: Boot routine block loses `{{ working_folder }}`; slice 3: new section "Composing the project instructions" |
| `template/.agents/skills/build-thread-brief/SKILL.md.jinja` | touched (slice 1) | Build-thread rules | Handover block loses `{{ pmr_ref }}` |
| `template/scripts/test_generate_condensed_copy.py` | touched (slices 1, 2) | Generator tests | slice 1: `RepoFactsSection`; slice 2: `NotesZoneEndsAtMarker` |
| `template/scripts/compose_project_instructions.py` | new (slice 2) | Builds and checks the one composed text | `compose(live_text, members)`, `main(argv)` |
| `template/scripts/test_compose_project_instructions.py` | new (slice 2) | Composer tests | the slice 2 test classes |
| `template/.agents/skills/queue-sweep/SKILL.md.jinja` | touched (slice 3) | Sweep procedure | checks 7(b) and 12 |
| `template/.forge/orchestration.md.jinja` | touched (slice 3) | Orchestration rules | "The coordinator's rules are mirrored" |
| `template/scripts/project_init_checklist.md.jinja` | touched (slice 3) | Stage 0 checklist | the paste item |
| `template/instructing-agents.md` | touched (slice 3) | Owner write-up | one paragraph on naming a lead repository |
| `template/scripts/bootstrap.py` | touched (slice 2) | Bootstrap | `parse_answers(text)` factored out of `read_answers()` |
| `scripts/test_answer_free_shared_sections.py` (root) | new (slice 1) | Two-render guard for I1 | `AnswerFreeSharedSections` |
| `.pre-commit-config.yaml` (root) | touched (slice 1) | Runs the two-render guard | hook id `answer-free-shared-sections` |
| `docs/security/threat-model.md` | touched (slice 2) | TheForge's own threat model | §1, §4, §5, §7 rows below |

**Deletion test.**

- `compose_project_instructions.py`: deleting it puts the coordinator back to merging several generated files by hand. That is the failure this design exists to fix, and SDLC-113 forbids hand-compression. It stays.
- `repo-facts.md.jinja`: deleting it means the generator must parse `.copier-answers.yml` to learn this repository's values, or the values go back into shared text and break I1. It stays.
- A separate contribution format, with a header or a manifest: not added. The generated file already is the contribution once I1 holds, and the composer reads pins from `.copier-answers.yml`.

**Seams.** No new Protocol or adapter. The composer imports the generator's own functions and constants (`extract_load_bearing_blocks`, `notes_check`, `NOTES_HEADING`, `MARKER`, `CHAR_LIMIT`, the top-level heading constants) rather than copying them. It reads answers with the same line parse `bootstrap.read_answers` uses, factored out as `parse_answers(text)` so that both call one function, and it calls git only through `_git_subprocess.run_git`.

**Build versus buy.** Section splitting and text comparison use the standard library (`difflib` for the `check` diff), as the generator already does. Reading `_commit` reuses the existing standard-library answers parser (`bootstrap.read_answers`'s line match), not a YAML library, which keeps I6. A YAML library was considered and rejected: the composer needs one key, and every guard script under `template/scripts/` stays standard-library-only. Templating the composed text through Jinja was rejected: the composer only arranges text that is already rendered.

## Data model and configuration

**The marker line.** It separates owner content from generated content in the live text. The composer writes it, and only it:

```
<!-- generated below: compose_project_instructions.py (SDLC-113); edit the source skills, never this text -->
```

The generator defines it once as `MARKER`, the composer imports it, and the coordinator skill quotes it. `extract_notes_zone` ends the notes zone at `MARKER` as well as at the next `#` or `##` heading (slice 2). Without that, the marker and the provenance line would count as notes, and every pin change would make `notes_check` refuse.

**The lead line.** One line inside owner content, matched as `^Lead repo:\s*(\S+/\S+)\s*$`. The value is `<owner>/<name>` as the hosting platform spells it, compared case-insensitively.

**Repo facts row** (`repo-facts.md.jinja`), with a header that is identical in every repository:

```
## Repo facts

| Repo | Forge pin | Working folder | Post-merge review tracker |
|---|---|---|---|
| {{ repo_owner }}/{{ repo_name }} | – | {{ working_folder }} | {{ pmr_ref }} |
```

In a contribution, the pin cell is `–`. In the composed text the composer fills it from each member's `_commit`, appends ` (lead)` to the lead's repo cell, and puts the lead's row first. A later answer the condensed text needs becomes a new column here, never a value in shared text.

**Composed text layout:**

```
<owner content, verbatim>
<MARKER>
Composed from <lead> @ <pin> (lead), <member> @ <pin>, <member> (not a forge consumer).

## Boot routine          ┐
## Decision facts        │ the lead's shared sections, verbatim, in the generator's order
## Coordinator           │
## Build thread brief    ┘
## Repo facts            one row per member, lead first; non-consumers get no row
## Repo deltas           only when at least one delta exists
### In <member>          one per member with a delta
```

The generator's `PREAMBLE` (paste instructions) is not carried into the composed text.

No new `copier.yml` question. No new configuration key.

## Slice 1: answer-free shared text and Repo facts

**Purpose.** Make I1 true, so that two contributions at the same pin can be compared as plain text.

**Changes.**

- `coordinator/SKILL.md.jinja`, Boot routine block, step 3: replace `` (`{{ working_folder }}/coordinator/boot-log.md`) `` with `` `coordinator/boot-log.md` in the working folder (Repo facts) ``. Add an untagged sentence directly after `<!-- /condensed -->` that names this repository's working folder, `{{ working_folder }}`, so the full skill still states it.
- `build-thread-brief/SKILL.md.jinja`, Handover block: replace `the post-merge review tracker {{ pmr_ref }}` with `this repository's post-merge review tracker (Repo facts)`. Add an untagged sentence after the block naming `{{ pmr_ref }}`.
- Add `repo-facts.md.jinja` as specified above.
- `generate_condensed_copy.py`: add `REPO_FACTS = ROOT / ".agents" / "skills" / "coordinator" / "repo-facts.md"`, and add `build_repo_facts_section() -> str`, which returns the file's text, stripped, with a trailing newline. `generate()` appends it as the last section. Add constants for the four top-level headings (`DECISION_FACTS_HEADING`, `COORDINATOR_HEADING`, `BUILD_BRIEF_HEADING`, beside the existing `BOOT_ROUTINE_HEADING`) and use them where the literals and `SKILLS[...]["heading"]` sit today, so the composer can import one list.
- Root `.pre-commit-config.yaml`: add hook `answer-free-shared-sections`, running the guard below, scoped like `denylist-not-shipped-render` to changes under `template/.agents/skills/coordinator/`, `template/.agents/skills/build-thread-brief/`, `template/scripts/generate_condensed_copy.py` and `copier.yml`. `check-render.sh` runs only its own root test, so without this hook nothing runs the guard. No text-matching check on answer values is added to `self_test`, because answer values collide with ordinary text (ADR-0011). The two-render guard below is the check.
- Regenerate the generated file in a render and keep it under `CHAR_LIMIT`. The Repo facts section costs more bytes than removing the two answer values saves, and a default render sat just under the limit when this was written. Make the room by tightening untagged `condensed-summary.md` prose without dropping a rule, the same way earlier changes to these skills have. If that cannot be done without dropping a rule, stop and report to the coordinator: the budget is the owner's call (open item O1).

**Error modes.** If `repo-facts.md` is missing, `GenerationError("coordinator: repo-facts.md not found")`.

**Seam.** A real render, from the repository root. `template/scripts/` tests run only inside a render, where there is no template to render from, so this guard lives in root `scripts/`, like `test_denylist_not_shipped.py`. `RepoFactsSection` in `test_generate_condensed_copy.py` covers the in-render half: the section is present, last, and one row.

**Guard test.** `AnswerFreeSharedSections` (root `scripts/test_answer_free_shared_sections.py`). It renders the template twice with `copier copy --trust --defaults --skip-tasks --vcs-ref HEAD` into two temporary directories, with different `working_folder`, `post_merge_review_tracker`, `repo_owner` and `repo_name` answers. It runs the generator's `build` in each and asserts that everything above `## Repo facts` is byte-identical. Put `{{ pmr_ref }}` back into the Handover block and the test goes red. It skips cleanly when `copier` is not installed, the same way `test_denylist_not_shipped.py` does, and `check-render.sh`'s own environment has Copier.

**Threat-model delta.** The skill text only moves between sections, and nothing new is read or executed in a consumer. The new root hook changes `.pre-commit-config.yaml`, so §4's "Commit to a TheForge clone" row gains the hook id `answer-free-shared-sections`. That is the whole delta: the hook is a guard that only renders and compares.
**UI:** none: generator and skill text only, no user interface.
**File scope.** The files above, plus the regenerated `docs/agents/condensed-project-instructions.generated.md` in a render. **Blocked by:** nothing. **Requirements:** none (internal). File scope also takes in root `.pre-commit-config.yaml` and `docs/security/threat-model.md` §4.

## Slice 2: the composer

**Purpose.** Build the one text and check the live text against it.

**Interface.**

```
python3 scripts/compose_project_instructions.py compose --live LIVE --out NEW PATH [PATH ...]
python3 scripts/compose_project_instructions.py check   --live LIVE PATH [PATH ...]
```

`PATH` is a local checkout of each member, the lead included, in any order. `compose` writes `NEW` and prints a report to stdout. `check` writes nothing.

```python
@dataclass(frozen=True)
class Member:
    path: Path
    slug: str | None          # "<owner>/<name>" from Repo facts, or from `git remote get-url origin` for a non-consumer
    pin: str | None           # from `.copier-answers.yml` `_commit`; None for a non-consumer
    contribution: str | None  # the generated file at origin/main; None for a non-consumer

@dataclass(frozen=True)
class Composed:
    text: str
    contradictions: list[str]  # "<member>: <section heading>", one per coordinator-scoped divergence

def load_member(path: Path) -> Member: ...
def compose(live_text: str, members: list[Member]) -> Composed: ...   # raises CompositionError
def main(argv: list[str]) -> int: ...
```

**Behaviour, in order.**

0. Run `git -C <path> fetch origin main` for every member, through `run_git` with its timeout, so that `origin/main` is current. A failed fetch is a refusal that names the member.
1. Split the live text at `MARKER`. If there is no marker and no line in the live text is one of the generator's top-level headings, the whole live text is owner content: this is a first composition, as at stage 0. If there is no marker but a top-level heading is present, refuse with this message: "the live text has no generated-content marker; insert `<MARKER>` on its own line directly above the first generated heading, confirm the owner content above it is unchanged, then rerun."
2. Find the lead. If there is one member, it is the lead. Otherwise, match the lead line in owner content. Refuse when there is no lead line, when more than one lead line exists, or when the named lead is not among the members.
3. Refuse if the lead is not a forge consumer.
4. Parse the Repo facts row of every forge consumer that has one. Refuse on any cell that contains a newline or a `|`, or is longer than 200 characters. A cell may start with `#`, because a tracker reference renders as `#<n>`; a single table row cannot open a heading, so a leading `#` is harmless here. The length cap is added at stage 5, to keep one hostile cell from using up the size budget. The lead and every same-pin member must have Repo facts. A member on a different pin may predate slice 1 and have none: take its slug from `git remote get-url origin`, give it no table row, and emit only its skew line. A different-pin member that does have Repo facts gets its row, validated the same way.
5. Emit owner content, `MARKER`, the provenance line, the lead's shared sections, then the merged Repo facts table.
6. For each other member, compute its delta:
   - **Not a forge consumer**: `- <slug>: not a forge consumer; its own instructions govern work inside it.`
   - **Pin differs from the lead's**: `- <slug>: on forge <pin> (lead on <lead pin>); its own full skills win for work inside it.` Do not diff anything.
   - **Same pin**: compare each top-level section, and Decision facts' two parts, with the lead's.
     - A differing coordinator-scoped section is a **contradiction**. Add it to `Composed.contradictions` and emit nothing for it.
     - A differing Build thread brief: extract the member's load-bearing blocks from `.agents/skills/build-thread-brief/SKILL.md` at `origin/main`, using `extract_load_bearing_blocks`. Emit each block not present in the lead's section, verbatim, under `### In <slug>`. Only when the section still differs after those blocks are accounted for, meaning the untagged summary prose differs too, add one line: `Other differences in Build thread brief: see <slug>'s own .agents/skills/build-thread-brief/SKILL.md.`
     - A differing approval list: it comes from `.forge/process-and-evidence.md`, not a skill, so it has no tagged blocks. Emit the member's whole approval-list part verbatim under `### In <slug>`, since it is a short closed list and partial copies of it would mislead.
7. Emit `## Repo deltas` only if at least one delta exists.
8. Post-conditions: the output is at or under `CHAR_LIMIT`; `notes_problems(live, new, first_write=True)` returns no problems (compose writes only below the marker, so a zone-less live text has nothing to drop); owner content is byte-identical; every lead block and every carried member block is present verbatim (I7). Any failure is a refusal.
9. Report: one line per member (slug, pin, lead or not, delta kind), then a `Contradictions for the owner:` list, or `none`. Contradictions do not fail `compose`. The coordinator files them (slice 3).

`check` runs steps 1 to 8 in memory and compares its generated part with the live text below the marker, ignoring trailing whitespace on each line. If they match, it exits 0. If they differ, it prints a unified diff and exits 1. It also exits 1 on any refusal.

**Error modes.** `CompositionError(message)` for every refusal above, which means exit 1 and no `NEW` written. A `git show` failure or timeout on a member that has `.copier-answers.yml` is a refusal that names the member. A member with no `.copier-answers.yml` at `origin/main` is a non-consumer, not an error. Paths are checked with `looks_like_flag` before they reach git.

**Generator change in this slice.** `extract_notes_zone` also ends the zone at a line equal to `MARKER`. Guard test `NotesZoneEndsAtMarker`: a live and a new text with the same notes zone and different provenance lines pass `notes_check`, and they fail once the `MARKER` stop is removed.

**Seam.** `compose(live_text, members)` is tested directly with hand-built `Member` values, so most tests need no git. `load_member` is tested against a throwaway repository built the same way `test_check_forge_drift.py` builds its fixtures, under `clean_git_env`.

**Guard tests** (each goes red with its check removed):

- `OwnerContentIsByteIdentical`: owner content with an unusual layout (no notes zone, a notes zone, trailing spaces) comes through unchanged. Drop the `notes_check` post-condition and change the notes slice, and it goes red.
- `CoordinatorTextOnlyFromLead`: a same-pin member whose Coordinator section differs adds a contradiction, and none of its text appears in the output (I3).
- `RepoScopedOverrideCarriedVerbatim`: a same-pin member with an extra Build thread brief block gets that block under `### In <slug>`.
- `VersionSkewIsOneLine`: a different-pin member gets exactly one delta line, whatever its text.
- `VersionSkewWithoutRepoFacts`: a different-pin member with no `## Repo facts` gets a skew line and no table row, and the composer does not refuse.
- `ApprovalListOverrideCarriedWhole`: a same-pin member with a different approval list gets its whole list under `### In <slug>`.
- `ProvenanceChangeIsNotANotesChange`: recomposing after a member's pin changes passes the `notes_check` post-condition.
- `SamePinIdenticalEmitsNoDelta`: three same-pin members with identical shared sections give no `## Repo deltas` and a three-row Repo facts table.
- `SingleMemberNeedsNoLeadLine`, `TwoMembersNeedALeadLine`.
- `RefusesOnFetchFailure`: a member whose `git fetch` fails makes the composer refuse, naming that member.
- `TrackerCellStartingWithHashIsAccepted`: a Repo facts tracker cell holding a `#<n>` reference passes validation, and a cell containing `|` is refused.
- `FirstCompositionWithoutGeneratedText`: a live text with no marker and no generated heading is treated as all owner content.
- `RefusesWithoutMarker`, `RefusesOverLimit`, `RefusesMalformedFact`, `RefusesLeadNotPassed`, `RefusesNonConsumerLead`: each writes no file.
- `CheckDetectsDrift`: `check` exits 1 when one generated line in the live text is edited by hand, and 0 when only trailing whitespace differs.

**Threat-model delta** (fold into `docs/security/threat-model.md` in this slice):

- §1 in-scope list: add `template/scripts/compose_project_instructions.py` to the executable content.
- §4, new entry point: the composer run by a consuming project's coordinator. Actor: that coordinator. Authentication: none of its own; it reads checkouts the harness already holds. Declared in: `template/.agents/skills/coordinator/SKILL.md.jinja`, "Composing the project instructions".
- §5, new boundary row: **B9 Composition**, between each member repository's `origin/main` and the project instructions the coordinator obeys. What crosses: each member's contribution, its `.copier-answers.yml` `_commit`, and its Repo facts. Controls: the ones in the two rows below.
- §7, new row **T29: B9, Elevation of privilege.** "A member repository's contribution places rules in the project instructions that govern the coordinator across every member." Assets: the composed project instructions. Controls: coordinator-scoped sections come only from the lead (I3, `CoordinatorTextOnlyFromLead`); member text enters only as labelled repo-scoped deltas; Repo facts cells are validated; each member's text has already passed that member's review gate. Guard test: `CoordinatorTextOnlyFromLead`. Residual: Low.
- §7, new row **T30: B9, Tampering.** "Composing overwrites the owner's scope section or coordinator notes." Controls: I2, the `notes_check` post-condition. Guard tests: `OwnerContentIsByteIdentical`, `NotesZoneEndsAtMarker`. Residual: Low.
- Add the composer to T2's list of shipped executables.

**UI:** none: a command-line script, no user interface.
**File scope:** `template/scripts/compose_project_instructions.py`, its test, `generate_condensed_copy.py` (`MARKER`, `extract_notes_zone`) and its test, `bootstrap.py` (`parse_answers`), `docs/security/threat-model.md`. **Blocked by:** slice 1. **Requirements:** none (internal).

## Slice 3: process text

**Purpose.** Make the coordinator and the sweep use the composer.

**Changes.**

- `coordinator/SKILL.md.jinja`: add a section "Composing the project instructions" after "Preserving coordinator notes". Tag a short load-bearing block in it covering four rules:
  - in a project with more than one member, never paste one repository's generated file; run `compose` from the lead's checkout with every member's path, and write only its output;
  - the lead is the repository named on the owner's `Lead repo:` line, and with no such line the coordinator asks the owner;
  - for each contradiction the report lists, file one `needs-decision` ticket in the lead repository unless one is already open for that member and section;
  - recompose whenever any member's contribution changes on `main`, and at every boot.

  Untagged prose covers the one-time marker migration and what each delta line means. Add the matching placeholder to `coordinator/condensed-summary.md`. Boot routine step 1 gains "(the lead is defined under 'Composing the project instructions')".
- `.forge/orchestration.md.jinja`, "The coordinator's rules are mirrored": one sentence saying that a project with several members composes its instructions with `scripts/compose_project_instructions.py`, from the lead, and one sentence saying that check 7 audits the composed text.
- `queue-sweep/SKILL.md.jinja`, check 7(b): run `compose_project_instructions.py check` with the live text and every member path. Run it only when this repository is the lead, or the only member. A member that is not the lead reports 7(b) under "Not checkable this run: covered by the lead repository's sweep". Report a contradiction with no open `needs-decision` ticket as a Should. The tag-coverage and substance parts of today's 7(b) are replaced by `check`'s exact comparison, because the composer now produces the whole generated part. Check 7(a) is unchanged.
- `coordinator/SKILL.md.jinja`, "Preserving coordinator notes": the "Every update carries the zone through" bullet names the composer as the tool that writes the text in a project with several members. Its notes check (`check_coordinator_core.py notes`) stays, and the composer also runs that check itself.
- `queue-sweep/SKILL.md.jinja`, check 12: in a project with several members, read the boot log from the lead's working folder (the lead's Repo facts row), because the one coordinator writes its receipt there. Run the check only in the lead repository's sweep, as with 7(b).
- `coordinator/SKILL.md.jinja`, the intro paragraph that says to "regenerate and re-paste": say to regenerate and then recompose.
- `scripts/project_init_checklist.md.jinja`, the stage 0 item that pastes the generator's output: run `compose` with the live text and this repository's path, and write its output instead.
- `generate_condensed_copy.py` `PREAMBLE`: change the paste instruction to "Compose the project instructions with `scripts/compose_project_instructions.py`; never paste this file directly." Rerun the generator.
- `instructing-agents.md`: add one paragraph telling an owner with several repositories to add a `Lead repo: <owner>/<name>` line to their scope section, and why.

**Seam.** The rendered prose, checked by `scripts/check-render.sh` (the generator's `check` and the size limit) and by self-review's stale-citation grep for "paste", "check 7" and "lead repo".

**Guard test.** No new script logic. The existing `RealGeneratedFile` test plus the generator's self-test cover the new load-bearing block (remove its placeholder and generation fails).

**Threat-model delta.** Security: none beyond slice 2's rows. This slice only tells the coordinator to use the controls that slice built.
**UI:** none: process text only.
**File scope:** the files above. **Blocked by:** slice 2. **Requirements:** none (internal).

## Test matrix

| Behaviour | Slice | Test or check |
|---|---|---|
| Shared sections carry no answer value | 1 | `AnswerFreeSharedSections` (root) |
| Repo facts section present, last, one row | 1 | `RepoFactsSection` |
| The two-render guard actually runs | 1 | hook `answer-free-shared-sections` fires on a skill change |
| Single-repository generator output still fits and passes | 1 | `scripts/check-render.sh` |
| Owner content byte-identical; notes zone kept | 2 | `OwnerContentIsByteIdentical` |
| Coordinator text only from the lead | 2 | `CoordinatorTextOnlyFromLead` |
| Repo-scoped override carried verbatim | 2 | `RepoScopedOverrideCarriedVerbatim` |
| Version skew is one line, with or without Repo facts | 2 | `VersionSkewIsOneLine`, `VersionSkewWithoutRepoFacts` |
| Approval-list override carried whole | 2 | `ApprovalListOverrideCarriedWhole` |
| Provenance changes never trip `notes_check` | 2 | `NotesZoneEndsAtMarker`, `ProvenanceChangeIsNotANotesChange` |
| Same pin reduces to the lead's copy | 2 | `SamePinIdenticalEmitsNoDelta` |
| Lead rules | 2 | `SingleMemberNeedsNoLeadLine`, `TwoMembersNeedALeadLine`, `RefusesLeadNotPassed`, `RefusesNonConsumerLead` |
| First composition with no generated text | 2 | `FirstCompositionWithoutGeneratedText` |
| Fails closed | 2 | `RefusesWithoutMarker`, `RefusesOverLimit`, `RefusesMalformedFact`, `RefusesOnFetchFailure` |
| Audit detects hand edits | 2 | `CheckDetectsDrift` |
| Process text renders and fits | 3 | `scripts/check-render.sh` |
| No stale paste or check 7 instructions | 3 | self-review part 9 grep |

## Open items the implementer must re-verify

- **O1.** Re-measure the default render's size on `origin/main` before slice 1; it sat just under `CHAR_LIMIT` when this was written. Slice 1 makes its own room by tightening untagged summary prose. If that would drop a rule, stop and report, because the budget beyond that is the owner's call (the hanging size issue).
- **O2.** The exact lines `{{ working_folder }}` and `{{ pmr_ref }}` sit on, and whether any other answer has reached a load-bearing block or a `condensed-summary.md` since this was written. Run `grep -n "{{" ` over both skills and both summaries, and render with two answer sets, before trusting the list in slice 1.
- **O3.** That `parse_answers` reads `_commit` correctly in every shape Copier writes it (short SHA, `<tag>-<n>-g<sha>`, bare tag, quoted or not). `check_forge_drift.commit_sha`'s docstring lists the shapes; check against a fresh render.
- **O4.** That `git remote get-url origin` gives a slug the hosting platform recognises, for the non-consumer case. If it does not, use the checkout directory's name and say so in the report line.
- **O5.** Whether the coordinator's harness can write instructions longer than the hand-edit limit (an option recorded on the hanging size issue). The composer keeps `CHAR_LIMIT` as its limit until the owner decides otherwise.
- **O6.** Whether the live text a sweep thread sees in its own context matches what was written, beyond trailing whitespace (a harness may reflow or wrap it). If it does not, `check` keeps an exact comparison for load-bearing blocks and the provenance line, and falls back to today's substance comparison for untagged prose. Record which in the PR.
