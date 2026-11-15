# TheForge self-governance

**Status:** implemented, reconciled against main @ f308c5d.
**Tracking issue:** "Give TheForge a way to properly review and maintain itself". That issue holds the use cases (stage 2), the high-level design (stage 3), and the stage 3 amendment this document builds on (A1–A7). This repository has no requirements specification, so that issue is the requirement record. No slice here adds or changes requirement wording.
**Decision records:** ADR-0009 (TheForge is a standing consumer of its own template), ADR-0010 (Main Health TheForge's scope). Also ADR-0008 (retrofit), which the first self-render follows, and ADR-0006 (single entrypoint).

**Terminal-step note, recorded at build time:** slice 4's own procedure (step 5) planned to fold every slice's threat-model delta into `docs/security/threat-model.md` at this terminal step. In practice, slices 1, 3 and 4 each folded their own delta directly into the live file within their own landing PR (visible on `main` as the B5/T31 row from slice 1, the B8/T8/B2 rows from slice 3, and the T4/T2/T13 amendments and B10 row from slice 4); slice 2's delta was "Security: none". At the terminal step there was accordingly nothing left unfolded to fold; this is recorded here as the departure from the plan it is, not as a step silently skipped.

This document is written for the agents that build the slices. Each slice section is that slice's contract.

## Goal

TheForge's own content goes through the same change and quality-control process that TheForge ships to its consumers. TheForge does not keep a hand-maintained parallel copy of that process.

Two problems stand in the way today:

- **TheForge's own rules drift from what it ships.** Root `CLAUDE.md`, `AGENTS.md`, `.claude/hooks/session-start.sh` and `.github/pull_request_template.md` are hand copies or hand adaptations of what `template/` ships, and root has no `.forge/` and no `.agents/skills/` at all. TheForge threads borrow another project's skills, under a temporary carve-out in the project instructions.
- **Nothing standing watches TheForge's own `main`.** Its post-merge review is orchestrated by hand or by another repository's Main Health thread. It has no drift signal, and no local stand-in for the CI it does not run.

The fix makes TheForge a consumer of its own template. The first render is a retrofit (ADR-0008), because TheForge's root has never been rendered. After that it syncs through the ordinary `forge-sync` path. A dedicated Main Health TheForge thread owns the watching. No new sync mechanism is built.

## Out of scope

- How a refinement in a consuming project gets noticed as TheForge-worthy. That is the issue "how policy changes flow from a consuming project into TheForge".
- How TheForge decides a change is safe for consumers to pull, and release tagging. Those are the safe-propagation issue and the release-tagging issue. Self-sync tracks `main` HEAD, by the owner's stage 3 decision.
- The pre-run check of upstream `copier.yml` and executable files before `copier update --trust`. That is the issue "forge-sync: check upstream copier.yml and executable files before copier update --trust runs them" (the threat model's T13/T14 gap). This design depends on it: slice 3 is blocked by it.
- The publish mechanism into the public repository. `scripts/publish_snapshot.py` implements it; this design adds one input to it (see slice 3's threat-model delta).
- TheForge's own stage 0: principles, real toolchain answers, and its own `scripts/local-full-suite.sh`. This becomes a follow-up ticket filed at stage 6 alongside the slices, blocked by slice 4, because a consumer owes a stage 0 and TheForge becomes one. Its principle wording needs the owner's approval when that ticket runs.

## Invariants every slice keeps

1. **I1. Copier never writes forge-source.** No Copier run against the root changes `copier.yml`, anything under `template/`, a root guard script under `scripts/` that the template does not ship (the `check-*.sh` family, `check_template_pins.py`, `_git_env.py`, `denylist-path.sh`, and their `test_*.py` files), `.theforge-denylist*`, `docs/adr/0*.md`, `docs/design/`, `README.md`, `THIRD_PARTY.md`, `LICENSE` or `licenses/`. `_subdirectory: template` already enforces this, and the stage 3 spike confirmed it on both `copy` and `update`.
2. **I2. Every meta-rule survives.** Every rule in today's root `CLAUDE.md` and `AGENTS.md` ends up exactly once in one of three places: an imported `.forge/` file that already carries it, the project-owned section after `@.forge/entrypoint.md`, or a `docs/forge-overrides.md` entry. None is dropped silently.
3. **I3. Every meta-guard hook stays active on every commit to `main`.** The hooks are `no-issue-refs`, `denylist`, `no-issue-refs-commit-msg`, `denylist-commit-msg`, `one-sentence-per-line-template`, `not-raw-clone`, `denylist-not-shipped`, `denylist-not-shipped-render`, `answer-free-shared-sections`, `skills-lock-template`, `forge-entrypoint-template`, `check-render` and `template-pins`. No intermediate state of the root `.pre-commit-config.yaml` lacks any of them. (Self-retrofit part 2, slice 4, renamed `one-sentence-per-line`/`skills-lock` to their `-template` ids once the root `.pre-commit-config.yaml.jinja` render introduced a root-scoped hook of each original id; see `EveryMetaGuardHookIsPresent` in `scripts/test_precommit_hook_coverage.py`, which guards this exact list.)
4. **I4. No `--trust` Copier run against the root before the pre-run check exists.** The first retrofit `copier copy --trust` and every later `copier update --trust` against TheForgeStaging's own root wait until the T13/T14 pre-run-check issue is closed or substantially mitigated (owner, stage 2). Rendering into a scratch directory, as `check-render.sh` and the spike do, is not covered by this invariant.
5. **I5. Self-sync is deliberate.** A merged `template/` change becomes TheForge's own active governance only when someone deliberately runs `forge-sync`, never autonomously and never on merge. Each landing PR in this design is reviewed under the rules active on `main` before it merges, never the rules it introduces.
6. **I6. `_src_path` is the repository's HTTPS URL.** It is the `origin` remote's HTTPS clone URL, never a local path or `.`. Otherwise the drift check's `ls-remote` reads the working tree instead of `main`.
7. **I7. The template change stays neutral.** Slice 1 is the only `template/` change. It must name nothing about TheForgeStaging. It is a generic improvement for every consumer, and the three neutrality checks in root `CLAUDE.md` apply to it as to any `template/` change.

## Module map

| Module | New or touched | Its one job | Named hook |
|---|---|---|---|
| `template/scripts/check_forge_drift.py` | touched (slice 1) | Report how far `_commit` is behind upstream, counting only commits that can change a render | `render_pathspec(clone_dir, upstream)` (new), called from `drift()` |
| `template/scripts/test_check_forge_drift.py` | touched (slice 1) | Guard tests for the drift check | new classes, slice 1 |
| `template/.agents/skills/watch-main-ci/SKILL.md.jinja` | touched (slice 1) | Interprets the drift result line | one sentence in "Forge drift check" saying what `behind` now counts |
| `CLAUDE.md`, `AGENTS.md` (root) | touched (slices 2 and 3) | TheForge's own rules | slice 2: "This repository's own post-merge review"; slice 3: full hand-rewrite to `@.forge/entrypoint.md` plus a project-owned section |
| `.copier-answers.yml` (root) | new (slice 3) | Records TheForge's own consumer relationship | written by the retrofit `copier copy`, never by hand (ADR-0008) |
| `.forge/`, `.agents/skills/` (root) | new (slice 3) | TheForge's own active rules and skills, rendered | the `@.forge/entrypoint.md` line |
| `docs/forge-overrides.md` (root) | new (slice 3, extended in slice 4) | Log of every forge-owned file TheForge keeps different | one entry per kept departure |
| `.pre-commit-config.yaml` (root) | touched (slice 4) | Forge hooks plus TheForge's meta-guard hooks | override entry "TheForge meta-guard hooks" |
| `scripts/test_precommit_hook_coverage.py` (root) | touched (slice 4) | Proves I3 mechanically | new test that every meta-guard hook ID is present and not skipped |
| `.claude/`, `.gitignore`, `.github/pull_request_template.md` (root) | touched (slice 4) | Forge versions with TheForge's kept lines on top | one override entry each where a line is kept |
| `.github/workflows/`, `scripts/*.py` (forge-shipped), `docs/agents/`, `docs/tools/`, `docs/development/`, the project-owned seeds (root) | new (slice 4) | What every consumer gets | none: rendered content |
| `docs/security/threat-model.md` | touched (terminal merge) | Folds in the deltas below | §4 entry points, §5 B2/B5/B8 rows, §7, §8 |
| `docs/adr/0009-*.md`, `docs/adr/0010-*.md` | touched (terminal merge) | Status line goes from proposed to accepted | status line |

**Deletion test.** No new module is added. `render_pathspec` is a new function inside an existing module. Deleting it puts back the whole-repository count, which never reaches 0 for a self-consumer, so the self-consumer's drift signal becomes useless. Every consumer also keeps being told it is behind by TheForge commits that cannot change its render. It stays.

**Seams.** No new Protocol or adapter. Slice 1 adds one pure function at the git-subprocess layer that already exists (`_git_subprocess.run_git`). Slices 3 and 4 reuse Copier, `retrofit-existing-project` and `forge-sync` unchanged.

**Build versus buy.** Slice 1 uses git's own pathspec filtering (`rev-list -- <paths>`), not a hand-rolled walk over commits. Reading `_subdirectory` out of upstream's `copier.yml` uses a single-key line match, not a YAML library, to keep the guard scripts standard-library-only (the convention every `template/scripts/` guard follows). A full YAML parse was considered and rejected: the script never needs any other key, and an unparsable or templated value falls back to the unfiltered count (slice 1, behaviour). Slices 3 and 4 use Copier, already adopted (ADR-0001). A bespoke sync for TheForge's own root was rejected in ADR-0009.

## Data model and configuration

The root `.copier-answers.yml`, written by slice 3's real `copier copy`, answers each question from what is already true of TheForge (retrofit Phase 2's answer table):

| Question | TheForge's answer | Source |
|---|---|---|
| `project_name` / `project_slug` | `TheForge` / `theforge` | the repository's own name in `README.md` |
| `repo_owner` / `repo_name` | the `origin` remote's owner and name | the `origin` remote |
| `owner_timezone` | the owner's IANA timezone | the project instructions' progress-report timezone |
| `setup_command` | `pip install pre-commit==4.3.0 && pre-commit install --install-hooks` | `.claude/hooks/session-start.sh`'s pinned version |
| `test_command` | the root and `template/scripts/` guard tests, as the builder verifies they run today (open item O3) | today's `scripts/test_*.py` and `scripts/check-render.sh` |
| `lint_command` | `pre-commit run --all-files` | root `CLAUDE.md`, "Running the contamination scan" |
| `coverage_floor`, `max_module_lines`, `max_function_code_lines` | template defaults, until TheForge's stage 0 sets real values | none today; that is the stage 0 follow-up |
| `max_build_threads` | `3` | the project instructions' pooled slot limit |
| `working_folder` | template default | none specific |
| the five `*_tracker` / `*_epic` keys | filled by `bootstrap.py` (the post-merge review tracker reuses the existing "Post-merge review tracker" issue by exact title; the other four are created) | retrofit Phase 1 and Phase 5 |

`_src_path` follows I6. `_commit` is the `origin/main` commit slice 3 renders from.

No new configuration key is added anywhere. `.copier-answers.yml`'s `_subdirectory` is read from upstream's `copier.yml`, not from the answers file.

## Slice 1: the drift check counts only render-input commits

**Purpose.** `check_forge_drift.py` today counts every commit in `_commit..upstream HEAD`. A commit that touches only TheForge's own ADRs, design docs or root guard scripts cannot change any consumer's render, yet it shows as drift. For a self-consumer the count never reaches 0, because the sync PR's own merge comes after `_commit`. After this slice, `behind` counts only commits that touch what a render reads.

**Module and interface.** In `template/scripts/check_forge_drift.py`:

```python
def render_pathspec(clone_dir: str, upstream: str) -> list[str]:
    """Paths whose change can alter a render of `upstream`: the template
    subdirectory plus Copier's own config file. [] means "count every commit"."""
```

It reads upstream's `copier.yml`, and `copier.yaml` only if that is missing (Copier's own lookup order), with `run_git(["git", "-C", clone_dir, "show", f"{upstream}:copier.yml"], CLONE_TIMEOUT)`. It finds a top-level `_subdirectory:` line and returns `[f"{subdir}/", "copier.yml", "copier.yaml"]`. Git ignores a pathspec that matches nothing, so naming both config file names is harmless. Error modes: none raised. Every failure returns `[]`.

`drift()` calls it after the clone and passes `["--", *pathspec]` to both the `rev-list --count` and the subjects `log` call.

**Behaviour.**

- `_subdirectory` present and a plain relative path: count and list only commits touching that subdirectory, `copier.yml` or `copier.yaml`.
- `_subdirectory` absent, empty, `.`, containing `{{` or `{%` (a templated value), absolute, or containing `..`: return `[]` and count every commit. That is today's behaviour. The check fails toward over-reporting drift, never toward hiding it.
- `git show` fails (file missing, network, timeout): return `[]`. A timeout must not escape. Today's `TimeoutExpired` handler sits in `drift()`'s outer `try`, so `render_pathspec` catches its own timeout and returns `[]`, which keeps the count working.
- The result line format and exit codes are unchanged. `behind=0` from a filtered count means the same as today's `behind=0`: nothing to sync.
- The early `behind=0` return when `_commit` equals upstream HEAD is unchanged.
- The pathspec values reach git only after `--`, the same flag-injection rule every `run_git` call already follows (`SeparatorPrecedesTheUrlInEveryGitInvocation`).

**Seam it is tested through.** `test_check_forge_drift.py`'s existing `RepoFixture`: a real local (non-bare) upstream repository used as `_src_path`, with real commits.

**Guard tests that must go red when the check is removed.**

- `RootOnlyCommitsAreNotDrift`: upstream has `copier.yml` with `_subdirectory: template` and three commits after `_commit` that touch only `docs/adr/x.md`. It expects `behind=0`. Removing the pathspec from the `rev-list` call turns this red (it reports 3).
- `TemplateAndConfigCommitsAreDrift`: one commit touching `template/a.md` and one touching `copier.yml` are counted (2). The subjects list holds those two subjects only. A pathspec missing `copier.yml` turns this red.
- `UnfilterableSubdirectoryCountsEverything`: one case each for a templated `_subdirectory`, a missing `_subdirectory` and an unreadable `copier.yml`. Each counts every commit. Turning the fallback into "count nothing" turns this red.
- `PathspecFollowsTheSeparator`: extends the captured-argv check so the pathspec appears only after `--`.

**Threat-model delta.** One new row under B5 (Sync):

| ID | Boundary | STRIDE | Threat | Control | Guard test |
|---|---|---|---|---|---|
| new | B5 | Spoofing | The drift check's filter is too narrow and hides an upstream change that does alter the render, so a consumer believes it is current when it is not | `render_pathspec` fails open: any parse doubt counts every commit; the filter names `_subdirectory` and both config file names | `UnfilterableSubdirectoryCountsEverything`, `TemplateAndConfigCommitsAreDrift` |

T13's control list also gains the filtered count, with no change of residual risk.

**UI:** none. A script's output line only.

**File scope.** `template/scripts/check_forge_drift.py`, `template/scripts/test_check_forge_drift.py`, one sentence in `template/.agents/skills/watch-main-ci/SKILL.md.jinja`'s "Forge drift check".
**Blocked by:** none. **Requirements:** none (internal). Full review gate: it changes `template/`.

## Slice 2: Main Health TheForge owns the cadence now

**Purpose.** A Main Health TheForge thread already watches this repository in practice. This slice makes it, in TheForge's own rules, the standing owner of the post-merge review cadence and of an interim health routine. The routine covers the time before slices 3 and 4 make TheForge an ordinary consumer.

**Change.** In root `CLAUDE.md`, "This repository's own post-merge review", and the matching `AGENTS.md` bullets:

- "Cadence and owner": the owner is the Main Health TheForge thread. Delete "No single owner is designated yet" and the "whichever thread notices" fallback.
- "Where this repository differs": delete "it has no Main Health thread of its own…". Keep the other two clauses; slice 3's hand-rewrite removes the no-architecture-epic clause once its own tracker reconciliation creates that epic, but keeps the no-SDLC-document clause, which stays true until a later slice renders `docs/software-development-lifecycle.md`.
- Add an interim routine, stated once: each time the post-merge review routine fires, Main Health TheForge runs `pre-commit run --all-files` on `main`'s head, which includes `check-render`. A red result is reported the way a consumer's Main Health reports red CI. In the same firing it posts, as a comment on the tracker and never an edit to its body, any pending-review note a merge to `main` is missing (the backstop ADR-0010 item 4 names).
- "Pending notes": add one sentence saying Main Health TheForge posts any note still missing, mirroring `.forge/post-merge-review.md`'s own wording.

**Outside the repository, same session.** The builder hands the coordinator the text needed to retire the project instructions' line that has another repository's Main Health thread run this repository's post-merge review, in favour of Main Health TheForge. The builder doesn't edit the project settings.

**Seam and guard test.** Prose only. There is no mechanical guard: this is a rule about which thread acts. Self-review part 9 (stale citations) greps for "whichever thread notices" and "no Main Health thread" across the repository.

**Threat-model delta.** Security: none. It changes which thread orchestrates a pass that already runs, and it grants no new access.

**UI:** none.

**File scope.** Root `CLAUDE.md`, root `AGENTS.md`. **Blocked by:** none. **Requirements:** none (internal). Full review gate: it is an agent-instruction change.

## Slice 3: self-retrofit, part 1 — the forge import, skills and answers file

**Purpose.** Run `retrofit-existing-project` on TheForgeStaging itself, Phases 0 to 3. Land its first PR: TheForge's root now imports `@.forge/entrypoint.md` and runs its own shipped skills.

**Procedure.** Follow `template/.agents/skills/retrofit-existing-project/SKILL.md`, unmodified except for the one recorded departure below.

- **Phase 0.** `python3 template/scripts/check_retrofit_preconditions.py --root .` exits 0. Confirm no open PR touches a path the template ships.
- **Phase 1.** The "Post-merge review tracker" issue already has `bootstrap.py`'s exact title. No other TheForgeStaging issue plays the other four roles, so `ensure_trackers` creates "Deferred ideas", "Hanging items", "Deferred architecture findings" and "Local full-suite evidence". Before the copy, check the existing `hanging` and `future` items. If an existing issue already serves as one of these epics, retitle it instead.
- **Phase 2.** `copier copy --trust --overwrite --vcs-ref <origin/main sha> <origin's HTTPS URL> .`, answered from the table under "Data model and configuration". `_tasks` run: the condensed-copy generation and `bootstrap.py --from-copier`, which needs a narrowly scoped token for this one repository (T9's control refuses a broad one).
- **Phase 5, step 1, before any PR opens.** Confirm each tracker key in `.copier-answers.yml` resolved to the existing "Post-merge review tracker" issue or a freshly created one, with no duplicate of an existing issue. Fix a duplicate (retitle the real one, close the accidental one) before the PR opens.
- **Pre-commit exclusions this PR needs.** Today's root `no-issue-refs` and `denylist` hooks would reject two kinds of rendered content: rendered `.forge/` files carry real tracker numbers through the `*_ref` variables, and `.copier-answers.yml` names the owner account. This PR therefore adds a precise `exclude:` to exactly those two hooks (and their commit-message twins where they scan files), naming only the rendered paths: `.copier-answers.yml`, `.forge/`, `.agents/skills/` and `docs/agents/condensed-project-instructions.generated.md`. It never names a directory forge-source lives in. The guard reason is that each excluded path is regenerated from `template/`, which both hooks still scan, and `denylist-not-shipped-render` scans the rendered output for denylist terms. The exclusion is logged in `docs/forge-overrides.md` and in the T4 amendment below. `scripts/test_precommit_hook_coverage.py` gains a case proving an ordinary file next to each excluded path (for example `docs/agents/other.md`, `README.md`) is still scanned. This is the one place slice 3 touches `.pre-commit-config.yaml`.
- **Phase 3.** Hand-rewrite root `CLAUDE.md` and `AGENTS.md`, rule by rule. The starting mapping is below. The builder checks every row against the rendered `.forge/` text and records the final mapping in the PR body.

**Recorded departure from the retrofit skill's landing order.** The skill lands the `.forge/` import first and skills second. Here they land together in this PR. TheForge's own threads read root `.agents/skills/` from the moment the import is on `main`. Split, there would be a window where every imported rule names a skill that doesn't exist yet, and SDLC-112 makes a missing skill a hard stop for every thread working on TheForge. The PR body states this departure.

**Starting mapping for root `CLAUDE.md`.**

| Today's section | Outcome |
|---|---|
| Lead-in prose ("Rules come in two strengths: Never … Default …") | Drop. `.forge/never-default.md`, now imported, states the identical convention generically, including "an unmarked rule defaults to Default and is not meant to read as weaker." |
| "Agent commit identity (Never)" | Keep, project-owned. TheForge's wording is stricter than the template seed (bot identity, platform squash shape). |
| "TheForge stays project-neutral (Never)" | Keep, project-owned. It must never ship. |
| "This repository's own threat model" | Keep, project-owned. Its path list is TheForge's own. |
| "Review gate for this repository's own PRs" | Drop the full/light gate restatement and the "using the template's own skills by path" sentences: `.forge/review-gate.md` and root `.agents/skills/` now carry them. Keep, project-owned: "a neutrality miss is always a Must", and the repeat-offender step (strip harness attribution, run `check-merge-text.sh`). |
| "This clone needs a … remote" | Keep, project-owned. |
| "This repository's own post-merge review" | Drop what `.forge/post-merge-review.md` and the rendered `post-merge-review` skill now carry (tracker body shape, batching, MoSCoW, pending notes). Keep, project-owned: the neutrality axis in every brief, rendering with `--vcs-ref HEAD` where a finding needs rendered output, and the extra cadence trigger "before each public snapshot". Delete the "Where this repository differs" paragraph's no-architecture-epic clause, which this render makes untrue (the self-retrofit's own tracker reconciliation creates that epic). **Correction, recorded at build time:** keep, not delete, the no-SDLC-document clause — this slice's own file scope does not render `docs/software-development-lifecycle.md` (that is slice 4's), so the clause stays true; the original instruction to delete it assumed a scope this slice doesn't actually have. Keep "no requirements specification content yet" until the stage 0 follow-up. |
| "Tagging a release of this repository (Default)" | Keep as a recorded owner waiver of `.forge/process-and-evidence.md`, "Releases" ("agents … never push a tag"), stating that it is a waiver of that imported rule. |
| "Contributing to `template/`", "Back-porting from a consuming project", "Running the contamination scan" | Keep, project-owned. |

**File scope correction, recorded at build time.** This paragraph's list omits two files the rest of this same section already requires: `scripts/check_forge_entrypoint.py` (the "Seam and guard tests" bullet below runs it from root) and `docs/security/threat-model.md` (the "Threat-model delta" table below amends it in this PR). Both are in scope; the list above was incomplete, not the diff. The landing PR also adds two `.gitignore` lines for the new guard-test's scratch-probe paths (`scripts/test_precommit_hook_coverage.py`'s `RenderedPathExclusionStaysNarrow` class), the same kind of test-driven addition the retrofit skill's own guard tests already make elsewhere.

`AGENTS.md` gets the same read-and-map. Its "Where things live" ADR list gains ADR-0009 and ADR-0010.

**Outside the repository, same session.** The builder hands the coordinator the text to retire the project instructions' "until TheForge governs itself" carve-out (borrowing another consuming project's `implement-with-merge` and `feature-pipeline`). From this merge on, TheForge threads use root `.agents/skills/`. The condensed copy `generate_condensed_copy.py` wrote is TheForge's own regenerated text; it goes to the coordinator too.

**Seam and guard tests.**

- `python3 scripts/check_forge_entrypoint.py` (rendered into root by this copy) passes against root: I1 and I2 of ADR-0006 hold for TheForge itself.
- `python3 template/scripts/check_retrofit_preconditions.py --root .` now exits non-zero. That is the expected proof that the root counts as a consumer.
- `scripts/check-not-raw-clone.sh` still exits 0. It passes on the remote alone (ADR-0004, amended).
- I1 check: `git diff --name-only origin/main` lists nothing under the I1 paths.
- I2 check: every `##` heading of today's root `CLAUDE.md` appears in the PR body's mapping table with exactly one outcome.

**Threat-model delta.**

| ID | Boundary | STRIDE | Threat | Control | Guard test |
|---|---|---|---|---|---|
| amend T4 | B1 | Tampering | The rendered-path exclusions on `no-issue-refs` and `denylist` widen to cover a hand-written file, so a leak there passes | exact rendered-path patterns only; the source under `template/` stays scanned; `denylist-not-shipped-render` | the new `test_precommit_hook_coverage.py` case |
| amend B8 | B8 | (boundary) | B8 now also names TheForge's own root as a retrofit target | the retrofit skill's preconditions; I4 | none: procedural |
| amend B5 | B5 | (boundary) | B5's description becomes "A TheForge release and each consuming project, including TheForge's own root" | as today | none |
| amend T8, T13, T14 | B3/B5 | Elevation of privilege, Tampering | The `--trust` copy and later updates run with the session's push-to-staging credential, the highest privilege this repository has; a bad `template/` merge becomes TheForge's own active rules on the next self-sync | I4 (blocked on the pre-run check); I5; the full review gate on each landing PR and each later sync PR | none |
| new | B2 | Information disclosure | Once root carries rendered consumer files, a public snapshot would carry a root `.copier-answers.yml` naming the private staging repository and its owner account, and rendered docs naming the same | Open gap: the publish mechanism must exclude or rewrite root `.copier-answers.yml` and check rendered root files against the denylist; tracked on the publish-method issue | none yet |

**UI:** none.

**File scope.** Root `CLAUDE.md`, `AGENTS.md`, `.copier-answers.yml`, the two hook exclusions in `.pre-commit-config.yaml` and their test in `scripts/test_precommit_hook_coverage.py`, `.forge/`, `.agents/skills/`, `docs/forge-overrides.md` (the seed plus the `CLAUDE.md` waiver note, if the builder records it there), `docs/agents/condensed-project-instructions.generated.md`. Nothing else from the render. The rest of the render is slice 4's, re-rendered from the same `_commit`.
**Blocked by:** the T13/T14 pre-run-check issue (I4); slice 2.
**Requirements:** none (internal). Full review gate.

## Slice 4: self-retrofit, part 2 — everything else, then the verification sync

**Purpose.** Land the rest of the render: scripts, workflows, the five colliding files, and the docs seeds. Prove TheForge is an ordinary syncable consumer.

**Procedure.**

1. Re-render at the root `.copier-answers.yml`'s `_commit` into a scratch directory with `copier copy --trust --defaults --skip-tasks --vcs-ref <_commit> --data-file .copier-answers.yml <_src_path> <tmp>`. Copy in every path slice 3 didn't land. This is the same render the real copy produced. It is not a synthesized answers file, which stays as Copier wrote it.
2. Collision triage (retrofit Phase 4) for the five files the stage 3 spike showed being overwritten. Take the forge version, and keep TheForge's lines on top through one `docs/forge-overrides.md` entry each:
   - `.pre-commit-config.yaml`: the forge hooks plus every I3 meta-guard hook, in one entry, "TheForge meta-guard hooks". Each forge hook that would scan `template/` or the rendered copies twice (for example size, dead-code or one-sentence checks over both `template/.forge/` and root `.forge/`) is scoped so it checks each file once, and each scope change is listed in the same entry (open item O1).
   - `.claude/hooks/session-start.sh`, `.claude/settings.json`: forge version, plus anything TheForge's copy does that the forge one doesn't (today, nothing beyond wording, so expect no entry).
   - `.github/pull_request_template.md`: forge version, plus the `Neutrality:` line as an override. `Requirements:` and `Process:` now apply: this render gives TheForge an SDLC document, and `Requirements: none (internal)` is the honest value until its stage 0.
   - `.gitignore`: union, recorded only if a root-only line stays.
3. Workflows: take the three `workflow_dispatch` ones. `review-gate-check.yml`, which runs on every PR and so spends Actions minutes, follows the owner's decision on the issue: taken as is, or deleted and logged as an override. This slice does not merge before that decision is recorded on the issue. The three `workflow_dispatch` workflows are dispatched only by Main Health's scheduled pass, and only once the owner sets up that routine for TheForge.
4. Run `pre-commit run --all-files` on the merged config. Every hook passes.
5. **Terminal step** (retrofit Phase 6, and stage 7's terminal fold). Slices 1 and 4 are this feature's terminal slices, since nothing blocks on either. The step runs as part of whichever of the two merges last, never inside a slice's own PR. The stage 6 post-merge review ticket is blocked by both:
   - Run `forge-sync`'s dry run on root: `copier update --trust --defaults --skip-tasks --conflict inline`. No unexpected diff appears. Every difference traces to a `docs/forge-overrides.md` entry, a `_skip_if_exists` file, or forge-source under I1.
   - `python3 scripts/check_forge_drift.py` on root reports `behind=0`, or reports only commits that touch `template/` or `copier.yml`. This is slice 1's filter working on its first self-consumer.
   - Flip ADR-0009 and ADR-0010 to accepted. Set this document's status line to "implemented, reconciled against main @ <sha>".
   - A design-tier sub-agent folds every slice's threat-model delta into `docs/security/threat-model.md`.
   - Hand the coordinator the switch-over: Main Health TheForge moves from slice 2's interim routine to the standard `watch-main-ci` skill (forge drift check, plus Routine 2 once TheForge's stage 0 writes `scripts/local-full-suite.sh`). The stage 0 follow-up ticket (filed at stage 6) unblocks here.

**Seam and guard tests.**

- `scripts/test_precommit_hook_coverage.py` gains `EveryMetaGuardHookIsPresent`. It lists the I3 hook IDs and asserts each `- id:` block exists, has no `stages: [manual]`, and has no `files:` narrower than its own default. Deleting any one meta-guard hook from the merged config turns it red. Run it with one hook removed and paste that run into `Evidence:`.
- The rendered guard tests under root `scripts/test_*.py` pass from root.
- `scripts/check-render.sh` still passes. It renders `template/`, not root, so root's rendered files must not change its result.

**Threat-model delta.**

| ID | Boundary | STRIDE | Threat | Control | Guard test |
|---|---|---|---|---|---|
| amend T4 | B1 | Tampering | Merging root's pre-commit config with the forge one drops or narrows a meta-guard hook, so later leaks pass; a later self-sync's conflict resolution does the same | The override entry naming every meta-guard hook; `forge-sync`'s "Resolve each conflict" keeps an entry's lines | `EveryMetaGuardHookIsPresent` |
| amend T2, T13 | B1/B5 | Tampering | TheForge's root `.claude/hooks/session-start.sh` and rendered `scripts/` become synced content, so a `template/` change to them runs in TheForge's own sessions and commits after the next self-sync | I5; the full review gate on the sync PR, as for every consumer | as today |
| new entry point | §4 | (entry point) | `review-gate-check.yml` runs on `pull_request` in the staging repository with `contents: read`, `pull-requests: read` | read-only permissions; `pull_request`, not `pull_request_target`, so a fork PR runs with no secrets; pinned action SHA | `scripts/check_template_pins.py` already covers the pin in `template/` |

**UI:** none.

**File scope.** Every root path the render writes that slice 3 didn't land; `docs/forge-overrides.md`; `scripts/test_precommit_hook_coverage.py`. At the terminal merge: `docs/security/threat-model.md`, the two ADR status lines, this document's status line.
**Blocked by:** slice 3; the owner's decision on `review-gate-check.yml`. **Requirements:** none (internal). Full review gate.

## Test matrix

| Behaviour | Slice | Test or check |
|---|---|---|
| Root-only upstream commits are not drift | 1 | `RootOnlyCommitsAreNotDrift` |
| Template and config commits are drift, and only they appear in subjects | 1 | `TemplateAndConfigCommitsAreDrift` |
| Any doubt about `_subdirectory` counts everything | 1 | `UnfilterableSubdirectoryCountsEverything` |
| Pathspec never precedes `--` | 1 | `PathspecFollowsTheSeparator` |
| Existing drift behaviour unchanged | 1 | the existing `test_check_forge_drift.py` classes |
| No stale "no owner" / "no Main Health" prose | 2 | self-review part 9 grep |
| Root is a valid forge consumer | 3 | `check_forge_entrypoint.py` on root; `check_retrofit_preconditions.py` now refuses |
| Copier wrote no forge-source | 3, 4 | `git diff --name-only` against the I1 path list |
| Every meta-rule mapped once | 3 | PR-body mapping table against today's headings |
| Every meta-guard hook present and active | 4 | `EveryMetaGuardHookIsPresent`, red with one hook removed |
| Root is syncable with no unexpected diff | 4 (terminal) | `forge-sync` dry run |
| Self-consumer drift reaches 0 | 4 (terminal) | `check_forge_drift.py` on root |

## Open items the implementer must re-verify

- **O1.** Which forge pre-commit hooks double-scan once root carries rendered copies of `template/` content. Decide each hook's scope on the real merged config, never from this list. The aim is to check each file once, in whichever form is authoritative.
- **O2.** Whether `bootstrap.py --from-copier` in slice 3 should run with a token at all, or skip and be rerun by hand with a token scoped to this one repository. Follow T9's control either way. Never pass a broad token.
- **O3.** The exact `test_command`. Root `scripts/test_*.py` are standard-library `unittest` files, and `template/scripts/test_*.py` are written to run inside a render. Confirm what one command runs both correctly from root today before writing it into the answers.
- **O4.** That `_subdirectory` in this repository's `copier.yml` is still the literal `template` when slice 1 builds, so the fixture matches the real file.
- **O5.** That the T13/T14 pre-run-check issue's fix, once merged, actually runs in the `forge-sync` and retrofit paths slices 3 and 4 use. I4 lifts only when it does, or when the owner judges that issue substantially mitigated.
- **O6.** Re-run the stage 3 spike against `origin/main` at build time if `copier.yml` has changed since the stage 3 amendment was written.
