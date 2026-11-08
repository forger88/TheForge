# Retrofitting TheForge onto an existing project

**Status:** proposed.
**Tracking issue:** the issue "How well does TheForge apply to an existing project, not just a fresh `copier copy`?" holds the use cases (stage 2 grilling) and the high-level design (stage 3). This repository has no requirements specification, so that issue is the requirement record; there are no FR-/NF- IDs, only the decisions and the stage-3 comment's facts.
**Decision record:** ADR-0008.

This document is written for the agents that build the slices. Each slice section is that slice's contract.

## Goal

A project that already exists, independently of TheForge — one with its own prior process that independently converged on something forge-equivalent, or one with no prior forge-equivalent process at all — becomes an ongoing `copier update`-tracked TheForge consumer, the same relationship an already-generated consumer has, without losing anything project-specific along the way. The procedure that does this is a new, reusable skill, so a real retrofit has an actual thing to run rather than inventing its own steps each time.

The root README already gives a human reader the one-paragraph version of this, under "Adopting it into an existing repository". This design is the full procedure an agent actually runs: every precondition, the standing-tracker reconciliation the README doesn't cover, the sequenced-landing order, and the one guard test the procedure gets.

## Out of scope

- Actually running the retrofit against any specific real project. That is each such project's own conversion ticket, filed and blocked on this design; this ticket delivers the skill those tickets run.
- A repository with zero prior forge-equivalent process at all is a legitimate class of target this procedure must cover, even though validating it end to end against a real such repository is separate, later work.
- Turning a retrofitted project's fresh `docs/security/threat-model.md` skeleton into a real document. That's the project's own stage-0 `security-docs` bootstrap work, same as any newly generated project, named explicitly here so it isn't silently absorbed into a build ticket or silently dropped.
- Release-tag pinning. TheForge has no tags yet; the owner decided that a first retrofit pins `.copier-answers.yml`'s `_commit` to a commit SHA, re-pinned to a tag later via an ordinary `forge-sync`.
- `forge-sync`'s own hardening (duplicate-check script, drift check, SDLC-wording hold) — that's `docs/design/forge-sync-hardening.md` (ADR-0006), already built. This design reuses it unchanged at Phase 6's verification step.

## Invariants every slice keeps

1. **I1. The real mechanism, never a synthesized answers file.** Every retrofit runs an actual `copier copy --trust --overwrite` against the target's live checkout. Nothing in this design writes or edits `.copier-answers.yml` by hand.
2. **I2. CLAUDE.md and AGENTS.md are hand-rewritten, never Copier-overwritten.** Both are `_skip_if_exists` and already present on every target, so Copier leaves them untouched; the skill's own procedure is the only thing that changes them, and it never uses `forge-sync`'s positional-span migration (ADR-0006), which requires a prior forge render that a retrofit target never has.
3. **I3. No rule is silently dropped.** Every rule in the target's existing `CLAUDE.md`, and every file the template collides with, is accounted for as one of: now covered by a forge file, a logged departure in `docs/forge-overrides.md`, or genuinely project-specific and kept.
4. **I4. No standing tracker is duplicated.** A target's existing standing-tracker issue is reused by exact-title match, never left aside while a second, empty tracker of the same kind is created.
5. **I5. The new scripts use only the standard library.** Same as every other guard script under `template/scripts/`.
6. **I6. No unsafe Copier feature is added.** This design adds no new `_tasks` entry, `_migrations`, or `_jinja_extensions` beyond what `copier.yml` already has.

## Module map

| Module | New or touched | Its one job | Named hook |
|---|---|---|---|
| `template/.agents/skills/retrofit-existing-project/SKILL.md` | new | The full retrofit procedure, phases 0–6 | the skill's own phase list |
| `template/scripts/check_retrofit_preconditions.py` | new | Offline-checkable preconditions for Phase 0: no `.copier-answers.yml`, no `@.forge/` line in `CLAUDE.md`, clean `git status` | `problems(root)` |
| `template/scripts/test_check_retrofit_preconditions.py` | new | Guard tests for the script above | one test per check |
| `README.md` (root) | touched | Points "Adopting it into an existing repository" at the new skill | new sentence, end of that section |
| `docs/security/threat-model.md` | touched | Folds in the B8 boundary and its rows from the stage-3 security delta | §4, §5, §7, §9 |
| `AGENTS.md` (root) | touched | "Where things live" ADR list gains ADR-0008 | that list |

**Deletion test.**

- `check_retrofit_preconditions.py`: deleting it leaves Phase 0 a purely manual read of three things an agent could get wrong under time pressure (a stray `.copier-answers.yml` from a previous abandoned attempt, a half-finished prior migration, a dirty tree) with no single command to catch them before the one-shot `copier copy` runs. It stays.
- `SKILL.md` itself: deleting it leaves every real retrofit with nothing to run, which is the problem this design exists to solve.

**Seams.** No new Protocol or adapter. `problems()` has one real caller, the skill's own Phase 0 instruction to run it; no second caller exists, so no interface beyond a plain function and a CLI wrapper is introduced.

## Build versus buy

| Concern | Considered | Decision |
|---|---|---|
| Precondition checks | pre-commit's `pygrep`/`exists`-style hooks | Rejected. These checks run once, by hand, at the start of a one-time procedure, not on every commit — there is nothing to wire into `.pre-commit-config.yaml`, and git-status-cleanliness isn't a pygrep-shaped check. |
| Precondition checks, git status | the `git` command line via `subprocess` | Adopted. Already the pattern `template/scripts/check_forge_drift.py` uses; no new dependency, same as every other guard script (I5). |
| Tracker/label reconciliation | new reconciliation logic in `bootstrap.py` | Rejected. `ensure_trackers` already reuses a tracker found by exact title (verified against `origin/main`, threat model T11); retitling the target's existing trackers before the copy runs is strictly less code than teaching `bootstrap.py` a second matching strategy, and it reuses a control that already has its own guard tests. |

## Data and configuration

No new Copier question and no new answers-file key. The skill answers Copier's *existing* questions (`project_name`, `repo_owner`, `repo_name`, `owner_timezone`, `setup_command`, `test_command`, `lint_command`, `coverage_floor`, `max_module_lines`, `max_function_code_lines`, `working_folder`) from what is already true of the target project — never with Copier's own defaults, and never hand-written into `.copier-answers.yml` (I1).

`template/scripts/bootstrap.py`'s `TRACKERS` table names five tracker keys and the exact title `ensure_trackers` searches for under each (`post_merge_review_tracker` → "Post-merge review tracker"; `deferred_ideas_epic` → "Deferred ideas"; `hanging_epic` → "Hanging items"; `arch_findings_epic` → "Deferred architecture findings"; `local_full_suite_evidence_tracker` → "Local full-suite evidence"). A target that has been running its own forge-equivalent process for a while typically already has an issue serving each of these roles, under whatever title that project's own history gave it — Phase 0 retitles each one found to the exact string above, so the existing exact-title reuse in `ensure_trackers` records the real issue instead of creating a duplicate. A key with no existing equivalent on the target is left alone; `ensure_trackers` simply creates it fresh, the same as for a brand-new project. The build ticket for each real retrofit looks up that project's own current titles against its own live issues at the time it runs, not against any snapshot in this document, since a project's own tracker titles can themselves be retitled before the retrofit happens.

## Slice 1: the retrofit skill and its precondition guard

**Purpose.** Deliver the actual procedure a real retrofit runs, and the one offline-checkable guard it gets.

**Files.**

- `template/.agents/skills/retrofit-existing-project/SKILL.md` (new)
- `template/scripts/check_retrofit_preconditions.py` (new)
- `template/scripts/test_check_retrofit_preconditions.py` (new)

**Blocked by.** Nothing.

**Interface: `check_retrofit_preconditions.py`.**

```
python3 scripts/check_retrofit_preconditions.py [--root DIR]
```

- `problems(root: Path) -> list[str]` returns one human-readable line per violation; an empty list means the target is ready for Phase 2's `copier copy`.
- Checks, each one line in `problems()`'s output when it fails:
  1. `.copier-answers.yml` already exists at `root` (the target is already a forge consumer; this is `forge-sync`'s job, not retrofit's).
  2. `CLAUDE.md` exists at `root` and contains a line matching `^@\.forge/` (same reason as check 1, the pre-ADR-0006 shape).
  3. `git -C root status --porcelain` is non-empty (a dirty tree would carry stray edits into the one-shot diff).
- Exit 0 with nothing printed when `problems()` is empty. Exit 1, printing each problem and a final remedy line, otherwise. The remedy line for checks 1–2 is: "This target is already a forge consumer; use `forge-sync`, not this skill." For check 3: "Commit or stash (`git stash push -u`) before running the retrofit."
- Standard library only (`subprocess`, `pathlib`), per I5.

**Behaviour the skill's Phase 0 and Phase 1 follow**, beyond what the script checks (left as the agent's own judgement, not mechanized, because both need live GitHub state the script would otherwise need a token and network access for):

- Phase 0: no open PR on the target touches a path the template ships (`.forge/`, `.agents/skills/`, CI workflow files, `.pre-commit-config.yaml`, any `docs/` path the template seeds).
- Phase 1: the target's standing-tracker issues are retitled to the exact strings `ensure_trackers` searches for, per the "Data and configuration" section above, for whichever keys have an existing equivalent on that specific target.

**Guard tests** (`test_check_retrofit_preconditions.py`, one per check):

| Test | Fixture | Goes red if removed |
|---|---|---|
| `AnswersFileAlreadyExists` | a fixture dir with `.copier-answers.yml` | check 1 |
| `ClaudeMdHasOldStyleImport` | `CLAUDE.md` with an `@.forge/review-gate.md` line and no answers file | check 2 |
| `DirtyWorkingTree` | a git repo fixture with an unstaged edit | check 3 |
| `GitStatusCommandFails` | a plain directory with no git repo at all | the `status.returncode != 0` branch |
| `CleanTargetPasses` | a git repo fixture with none of the above | all (a check that over-fires goes red here) |
| `HookWrapperReturnsExitCode` | the script run as a subprocess against a dirty fixture | the exit code the skill's Phase 0 relies on |

The PR's `Evidence:` line records each check commented out and its test going red.

**Seam it is tested through.** Every test builds its own fixture directory (a temporary git repo, same pattern as `test_check_forge_entrypoint.py`) and never reads this repository's own tree, since the test file ships to consumers via `template/scripts/` and runs there too.

**Threat-model delta.** New boundary, **B8 Retrofit**: a one-shot `copier copy --trust --overwrite` run directly against an existing, populated, real repository, by this skill.

| STRIDE | Threat | Entry points / assets | Controls | Residual |
|---|---|---|---|---|
| Tampering | `_tasks` run with write access to a repo with real collaborators, history and open work, not a fresh scratch directory — a tracker-reuse miss could misrecord an existing tracker's number or create a duplicate | `bootstrap.py`'s `ensure_trackers`/`ensure_labels`; the target's standing trackers | Phase 0's retitle-before-copy step (relying on `ensure_trackers`'s existing exact-title reuse, T11); Phase 5's post-run check that no duplicate tracker was created | Low: the retitle step is procedural, not mechanically enforced, so a skipped retitle still only *creates a fresh, correctly-labelled tracker* rather than corrupting an existing one — `ensure_trackers` never edits a tracker it finds, so the failure mode is a duplicate, not data loss |
| Denial of service | The one-shot diff collides with in-flight work on the target that Copier has no way to know about | Any open PR on the target touching a template-shipped path | Phase 0's precondition check (`check_retrofit_preconditions.py` for the local checks; a manual open-PR check for the GitHub-side one) | Low |
| Tampering | A colliding file's departure is dropped rather than logged, losing project-specific process | Every file the template ships that the target also already has | Phase 3/4's rule-by-rule mapping and departure audit, landed in the PR body (I3) | Low: procedural, same class of control as the rest of the review gate |

No new elevation-of-privilege or information-disclosure surface beyond what `copier copy --trust` already carries for ordinary generation (existing T8/T9/T10): the retrofit target is a private repository the same owner already controls.

**UI.** None. This is a skill, a guard script, and process text.

## Slice 2: tracker and label reconciliation guidance

**Purpose.** Make Phase 1's retitle-before-copy step and Phase 5's post-run verification concrete enough that a build thread doesn't have to re-derive `bootstrap.py`'s matching behaviour from scratch, and name the two phases as skill sections rather than leaving them implicit inside Phase 2's "run `copier copy`" instruction.

**Files.**

- `template/.agents/skills/retrofit-existing-project/SKILL.md`, the "Reconcile trackers and labels before copying" and "Verify the reconciliation" sections only (written as part of slice 1's file, sequenced second because it depends on slice 1's skill skeleton existing first)

**Blocked by.** Slice 1 (the skill file must exist before a section is added to it).

**Behaviour.**

1. Before Phase 2's `copier copy` runs, for each of the five tracker keys named in "Data and configuration" above that has a named existing equivalent on the target, rename that issue (via the hosting platform's own issue-edit, not a file change) to the exact title `ensure_trackers` searches for.
2. Leave any key with no existing equivalent alone; `ensure_trackers` creates it fresh, exactly as it would for a brand-new project.
3. After `bootstrap.py --from-copier` has run (automatically, as one of `copier.yml`'s `_tasks`, since Phase 2 is a real `copier copy`), read `.copier-answers.yml`'s five tracker fields and confirm each resolved to the renamed issue's number, not a new one. `ensure_trackers`'s own idempotency (never editing a tracker it finds) means a second accidental run is self-correcting for the trackers it did find; a tracker it didn't find because the retitle step was skipped or mistyped shows up as a visibly duplicate issue, which this verification step catches before the PR opens, not after.
4. `ensure_labels` needs no reconciliation step of its own: it only ever creates labels named in its own `LABELS` table and never touches an existing label with a different name, so a target's own existing labels are untouched by construction. Note this explicitly in the skill so a build thread doesn't go looking for a label-reconciliation step that doesn't need to exist.

**Threat-model delta.** Covered under slice 1's B8 rows; this slice makes the control in the first row concrete rather than adding a new threat.

**UI.** None.

## Slice 3: README cross-link and threat-model fold-in

**Purpose.** Close the loop the README's existing retrofit section left open (a section with no reusable-procedure link to point at) and fold the stage-3 security delta into the live threat model.

**Files.**

- `README.md` (root), "Adopting it into an existing repository" section only — append one sentence pointing at the new skill
- `docs/security/threat-model.md` — §4 (new B8 entry points), §5 (new B8 boundary row), §7 (the three STRIDE rows from slice 1, numbered to follow the existing register), §8 known gaps (one row for the three new threats' residual risk, following the document's own convention that every threat row with residual risk gets a known-gaps entry), §9 residual risk summary

**Blocked by.** Slice 1 (the skill must exist for the README to link to it, and the threat-model rows cite it by path).

**Behaviour.** Mechanical: the README gets one added sentence, the threat model gets the rows slice 1 already specified, folded in verbatim per `security-docs`' delta-mode convention (the per-slice delta is written as the literal row text to fold in, not a paraphrase).

**UI.** None.

## Test matrix

| Slice | Command | Asserts |
|---|---|---|
| 1 | `python3 template/scripts/test_check_retrofit_preconditions.py` (or the repo's standard test runner, scoped to this file) | Every guard test in slice 1's table |
| 1 | `pre-commit run --all-files` | `one-sentence-per-line` does not apply here (it's scoped to `template/.forge/*.md`, which none of the new files are); `vendored skills match skills-lock.json` stays green (the new skill is first-party, so it gets no `skills-lock.json`/`THIRD_PARTY.md` entry); `a freshly rendered project passes its own guards` (`check-render.sh`) stays green; existing hooks still pass |
| 3 | manual read | README's new sentence resolves to a real path; threat-model §4/§5/§7/§8/§9 rows match slice 1's text verbatim |

## Open items for the implementer to re-verify

- Confirm the target's exact current tracker titles against its live issues at the time a real retrofit actually runs, not against any document snapshot — a project's own tracker titles can drift between when this design was written and when the retrofit happens.
- Confirm no open PR on the target touches a template-shipped path before that project's own retrofit PR sequence opens (a point-in-time check, re-run at retrofit time, not at design time).
- A first retrofit pins `.copier-answers.yml`'s `_commit` to a commit SHA, not a tag, per the owner's decision recorded on the needs-decision ticket this design filed. Confirm at build time that `_commit`'s value is in fact a resolvable commit SHA on this repository's `main`, not a floating branch name.
