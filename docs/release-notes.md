# Release notes

> **Ticket numbers.** A number written after a `#` in these notes refers to a ticket or pull request in TheForgeStaging, a private repository, so it can't be opened from here.

This repository's committed release-notes document (owner decision,
2026-10-31). Each release gets its own section here, drafted with the `release-notes`
skill (Enhancements, Bug fixes, Known issues and For integrators, with
`release:internal` PRs left out); the annotated tag `main` is cut from carries the same
notes as its tag message, per `CLAUDE.md`'s "Tagging a release of this
repository."

## v0.2.0 (2026-11-15)

A process-hardening release: downstream repository owners get a review gate that no longer lets an axis run silently un-reviewed, a coordinator that can no longer be satisfied by a stale or cached instruction copy, a release-notes process corrected against its own mistakes, PRs generated to the template's own shape, the requirements specification checked against the skill that sets it, a tightened SDLC document, a one-call worktree setup, a more conversational stage 0 with three more seeded principles, and three shipped bugs fixed (two of them documented as known issues at v0.1.0); several accepted risks were also re-homed, re-verified or newly classified.

### Enhancements

#### Review and merge gate

- Added a **governed-artefact standard**: wherever a skill sets a document's or test's shape, that skill is now the standard the Standards review axis, self-review and post-merge review all check a change against, with a new artefact map wiring the requirements specification's Evidence paragraphs and other governed files into all three. (#652)
- A PR built by a thread with **no reviewer sub-agent available** now gets an independent review delegated to its parent instead of silently merging with one review axis unrun. (#644)
- The governed-artefact map now **resolves what used to be left open**: the PR body stays unmapped by design (the PR template and `check_review_gate.py`'s `Review:` check are its own standard), and a project can now declare its own test-file glob(s) under its `CLAUDE.md` so test files get standards coverage too. (#653)
- A post-merge-review pending note now **keeps its canonical marker verbatim**, with any extra context added as trailing prose instead of replacing the template, so `queue-sweep`'s and the skill's own matching no longer miss a reworded note. (#657)

#### Coordinator and orchestration

- The coordinator-core reload now **always re-fetches** `origin/main` instead of trusting an existing copy, and its reload proof carries the sha it actually fetched, closing the gap where a stale or invented copy could pass unnoticed. (#666)
- The `pr` skill now **fills the PR template's own fields** instead of offering a competing shape, so a PR's Before/After and Evidence read the same way across every PR. (#664)
- `release-notes` now **re-verifies every carried-forward known issue** against its cited ticket's current state before drafting, instead of copying a previous release's wording forward unchecked. (#650)

#### Release process

- `forge-sync` now **reads every release's "For integrators" items across the whole synced tag range** and pastes them into the sync PR as an explicit checklist to work through after the Copier sync, instead of leaving them to be found by reading `docs/release-notes.md` prose; a mechanical check fails the sync PR until each item is addressed. (#696)

#### Feature pipeline and tickets

- A multi-slice design doc now **names one shared idiom per cross-cutting concern** in a shared-idioms table before slicing (stage 5), and the stage 8 architecture pass **actually verifies each named idiom was used**, rather than re-solved per call site — closing the gap where the DRY principle claimed this check but no skill performed it. (#642)
- Stage 0 project inception now **talks the owner through what's happening and why**, instead of just asking its questions: an opening orientation, narration through each sub-step, and a walk-through of whatever principles `docs/principles.md` already seeds, with a reminder that the owner can change or add to them at stage 0 or later. (#390)
- A newly generated project's seeded `docs/principles.md` now starts with three more owner-approved principles — "Don't repeat yourself", a fail-closed existence-oracle check, and a check against doc/skill text drifting from the script it describes — instead of only "Efficient with model costs". (#592, #376, #544)
- The requirements-spec skill's drafting guidance now **states the effect-not-how principle explicitly**, with a worked contrast, so a drafted requirement states what changed rather than encoding the library or algorithm behind it. (#604)

#### Toolchain and guards

- Added **`worktree_setup.py`**: one call now does a ticket's whole per-project worktree setup (fetch, branch, shared git-ignored path symlinks, hook-installed check) that previously had to be done by hand every time. (#57)

### Bug fixes

#### Toolchain and guards

- Three shipped rule and skill files **spoke from TheForge's own viewpoint**, calling TheForge, or a project's own PR template, just "the template", which is ambiguous when read from inside a generated project. (#543)
- A generated project's root `AGENTS.md` **could drift into a second, undetected copy of `CLAUDE.md`'s rules**, with nothing checking for the shape at all. (#369)
- `check_no_snapshots.py` **false-positived on a TOML lock file** (`uv.lock`/`poetry.lock`/`pdm.lock`) whenever a banned package name appeared only inside another package's own `[package.extras]` metadata, never actually installed. (#599)

### Known issues

- The coordinator-core reload proof's quoted `origin/main` sha is self-reported, not independently verified; a coordinator or helper could in principle quote a sha it did not actually fetch. (#668)
- A coordinator's reload proof can still be satisfied by a plain grep for the mid-file check word's fixed label, so the proof does not guarantee a whole read; the owner accepted this as residual risk. (ADR-0013)
- Nothing server-side protects `main`, release tags or `green`; the review gate, neutrality checks and merge-text scan are rules a push credential can skip, and the owner accepted this as residual risk. (#74)
- The shipped guards `check_pins`, `check_coverage_baseline`, `check_one_sentence_per_line` and `check_branch_name` still have no test that goes red when the check is removed. (#534)
- A harness that does not follow `@`-imports recursively may load only `.forge/entrypoint.md` and miss the rule files it imports. (#86)
- A project spread over several repositories has no single point of truth for policy, skills and instructions. (#1)
- Mermaid rendering still needs a Chromium installed on the machine; lower-infrastructure rendering is not yet settled. (#468)
- On Windows, a mixed-case skill directory can hash differently from a Linux or macOS checkout, so a Windows checkout's computed skills-lock hash can disagree with the recorded one for the same skill directory. (#682)

### For integrators

**Breaking changes:**

- The `requirements-evidence` pre-commit hook (`check_requirements_evidence.py`) now runs `always_run` over `docs/requirements/requirements-specification.md`'s `**Evidence…:**` paragraphs, checking them against the shape `.agents/skills/requirements-spec/SKILL.md`'s "Evidence" section sets. That file is project-owned, so a sync never rewrites it, and the seeded `scripts/requirements_evidence_baseline.json` arrives empty: an existing project's older free-text Evidence paragraphs fail every commit immediately after syncing. Before the first commit after syncing, either rewrite the specification's Evidence paragraphs to the new shape or seed `scripts/requirements_evidence_baseline.json` with the current failures. (#652)
- `template/scripts/check_review_gate.py` now fails a `Review:` Standards or Spec entry (other than the light gate's `n/a`) that does not record `clean-context` (or `clean sub-agent`); `template/.github/workflows/review-gate-check.yml` runs this on every PR event. After syncing, any open PR, and any project-owned brief or template text that dictates the `Review:` wording in other words, fails this check immediately. Update every open PR's body and any such text before relying on the check. (#644)

- After syncing, re-paste the text between the markers in `docs/agents/coordinator-core-snippet.md` into the harness's project-instruction field again — the coordinator's reload proof now carries the fetched `origin/main` sha, the self-check always re-fetches rather than trusting an existing copy, and a timer/sibling/owner ping asking to confirm or reload now triggers the full check. (#666)
- After syncing, answer (or accept the defaults for) the new `local_full_suite_script` and `local_full_suite_publish_var` Copier questions, which let a project name its own local-full-suite stand-in script and publish-switch environment variable instead of the hard-coded `local-full-suite.sh`/`LOCAL_FULL_SUITE_PUBLISH` names; a project carrying a forge-override entry for this naming mismatch can retire it once this syncs. (#598)
- After syncing, create the `deferred-accepted-risk` label (the colour and description `scripts/bootstrap.py`'s `ensure_labels` gives it, since `forge-sync` only creates labels on first generation) and move any `hanging` item that actually records an accepted risk onto it; `hanging` itself now covers only a gap deliberately deferred to a later point in time. (#614)
- After syncing, create an `UPSTREAM_SRC_READ_TOKEN` repository secret (a read-only token scoped to the template source) if the project's own `_src_path` is private; the SDLC-wording-hold step in `review-gate-check.yml` reads it when cloning that source, and a sync PR's hold step fails closed in CI without it. (#619)
- After syncing, `check_forge_entrypoint.py` now also checks that `AGENTS.md`, where it exists, stays a thin shell (no `##`-or-deeper heading, 300-word cap, no 30+-character line duplicated from `CLAUDE.md`/`.forge/*`); a project whose own `AGENTS.md` has grown real content will need trimming before its next commit passes. (#369)
- After syncing, `docs/software-development-lifecycle.md` carries SDLC-119 (new) and a reworded SDLC-042; `forge-sync` holds the sync PR at this point until the project's own owner approves the new wording (SDLC-117), but expect that hold — it is not a sync failure. (#652, #653, #646)
- After syncing, `template/.forge/feature-pipeline.md.jinja` and `template/.agents/skills/improve-codebase-architecture/SKILL.md` cite `docs/principles.md`, "Don't repeat yourself" by heading; that principle is seeded only into a newly generated project, so an existing project gets the citation without the principle it points at. Adopt the cited wording (it needs the project's own owner's exact-wording approval, SDLC-068) or note where an equivalent principle already lives under a different heading. (#642, #648)
- After syncing, an SDLC sync PR (one where `.copier-answers.yml`'s `_commit` moves across a change to upstream's `docs/software-development-lifecycle.md`) must carry a `SDLC upstream changes: <old>..<new> held: ...; current: ...` field on the PR body; `check_sdlc_wording_hold.py` now re-derives what upstream actually changed and fails the hold-check without it. An open sync PR already underway when this syncs needs that field added. (#597)
- After syncing, `self-review`'s checklist runs a new "Sync-impact category checklist" before any diff is recorded `release:internal` or `Release note: none`, in a project that itself ships shared process, scaffolding or configuration other repositories pull in on their own schedule; it adds a review step, not a mechanical check. (#678)
- After syncing, list this project's shared, git-ignored dependency directories in `scripts/worktree_shared_paths.txt`; stage 0 fills it only for a newly generated project, so an existing project's copy arrives with comments only and `worktree_setup.py` symlinks nothing until the integrator fills it in. (#57)

Plus 21 internal changes.

## v0.1.0 (2026-11-08)

The first tagged release of TheForge: a Copier template that gives a new or existing repository an engineering process for software built mostly by AI agents under a human owner, and keeps that process current through `forge-sync`.

### Enhancements

#### Generating and adopting a project

- Added **project generation** with `copier copy --trust`: the full process behind a single `.forge/entrypoint.md` import, and a bootstrap step that creates the labels and five standing trackers using a narrowly scoped token and refuses an over-broad one. (#113, #32)
- Added **adoption into an existing repository**, with a retrofit skill, a precondition guard and a documented landing sequence. (#55, #165)
- Added **stage 0 project initiation** from one checklist: toolchain answers, a coverage floor the rules hold the project to, and offers of stack-specific skills and a documents-and-diagrams build. (#67, #40, #380)
- Added a generated **process map and skills index**, so every skill and reference doc is findable from one list. (#251)

#### Feature pipeline and tickets

- Added the **feature pipeline** from idea to architecture pass, with a checklist on each feature, `needs-grilling` as a ticket state, a split of design work into `ready-for-structure` and `ready-for-feature-design`, a stage 3 route that skips stages 5 and 8 for a single low-risk ticket, and checklist item 9 ticked only once its filed findings are resolved. (#478, #458, #394, #487)
- Added **release-note labels** on tickets and a `Release note:` field on PRs, with the `release-notes` skill as the only way notes are drafted. (#395)
- Added **capability tiers** (design, review, build, mechanical) with a tier gate on every design-tier and review-tier entry point, and a model-cost efficiency principle. (#282, #385)

#### Review and merge gates

- Added the **review gate**: Standards and Spec reviews by clean-context sub-agents, then a mandatory self-review that checks mutually dependent files and fix-the-class lists, and stops when no sub-agent tool exists. (#77, #279)
- Added a **mechanical review-gate check** of each PR's `Review:` field, run at the merge step. (#259, #503)
- Added a **closed list of changes that need the owner's approval** before merge: requirement, SDLC and principle wording, plus what a numbered statement requires. (#254, #255)
- Added **post-merge review** with a tracker of pending-review notes trusted only from authorized commenters, one canonical watermark line and a STRIDE security axis. (#36, #100)
- Added **pre-commit guards** for branch names, module and function size, dead code, snapshot tests, dependency pins and one-sentence-per-line rule files, each with tests that go red when the check is removed. (#26, #27, #28)

#### Staying current

- Added **`forge-sync`**: wraps `copier update`, resolves conflicts against `docs/forge-overrides.md`, holds synced SDLC wording for the owner's own PR, surfaces upstream candidates as owner decisions, and targets the latest release. (#54, #42, #89, #90)
- Added **sync supply-chain checks**: a render-and-diff check, a duplicate scan, a trust diff before `--trust` runs `copier.yml` changes, a mechanical check of the sync PR's trust record, and a drift check. (#114, #75, #337)
- Added a **skills lock** that fails when a vendored skill no longer matches its recorded hash. (#23, #172)

#### Coordination

- Added the **coordinator core**, a coordinator-only rule file loaded at session start from a project-instruction snippet, with a truncation guard, a codeword and mid-file proof of a whole read, codeword rotation, a drift check and a check that the owner's notes survive updates. (#381, #389, #550)
- Added **coordinator rules** for the default queue, thread resolution, build-thread slots and approval requests that name their closed-list item, and a rule that the owner's coordinator notes survive every project-instructions update. (#58, #416, #260)

#### Documents and diagrams

- Added a **unified document and diagram build**: manifest-driven, with Mermaid and D2 diagrams rendered by fence class, cross-document consistency checks, per-document diagram overrides, a pinned toolchain and a CI workflow. (#56)

### Bug fixes

None.

### Known issues

- Review, neutrality and merge-text checks are rules a push credential can skip: nothing server-side protects `main`, release tags or `green`, which the owner accepted. (#74)
- `check-merge-text.sh` can detect, but cannot prevent, a merged squash message that differs from the one it scanned, and nothing yet makes a merger run the check. (#539)
- The merge-time scan does not enforce the head pin it prints, so a push after the scan can land content the scan never saw. A merge run from the PR's own branch can also use weakened scripts. The owner accepted both risks: detection after the merge is the control. (#549)
- A coordinator's reload proof can be found with a plain grep of the mid-file check word, so the proof does not guarantee a whole read. The owner accepted this as residual risk. (#555)
- The raw-clone tripwire passes a raw copy of this repository's own current tree. (#533)
- The shipped guards `check_pins`, `check_coverage_baseline`, `check_one_sentence_per_line` and `check_branch_name` have no test that goes red when the check is removed. (#534)
- A harness that does not follow `@`-imports recursively may load only `.forge/entrypoint.md` and miss the rule files it imports. (#86)
- A project spread over several repositories has no single point of truth for policy, skills and instructions. (#1)
- A generated project keeps both a populated `AGENTS.md` and `CLAUDE.md`, which can drift apart. (#369)
- The review-gate check runs at the merge step only, with no CI workflow behind it. (#505)
- Mermaid rendering needs a Chromium installed on the machine; lower-infrastructure rendering is not yet settled. (#468)
- 1 further architecture finding is deferred rather than scheduled (epic #343): shipped rule and skill files that still say "the template" from TheForge's own viewpoint. (#543)

### For integrators

**Breaking changes:**

- Projects that synced from `main` before this release must, after syncing, paste the text between the markers in `docs/agents/coordinator-core-snippet.md` into the harness's project-instruction field, because sync cannot reach it, and again after any later sync that changes the snippet. The old condensed-copy generator and compose step, and the `copier.yml` task that ran it, are removed; drop any step that calls them. (#389, #512, #550)
- The `ready-for-design` label is retired in favour of `ready-for-structure` (ticket level, same meaning) and `ready-for-feature-design` (feature level). Relabel open tickets after syncing. (#478)
- A project with `mermaid` fenced content whose build let `mmdc` fetch its own Chromium now needs `CHROMIUM_EXECUTABLE_PATH` set to an installed Chromium or Chrome binary; otherwise that document's render is skipped with a logged error and the build reports failure. (#446)

- Added the environment variable `CHROMIUM_EXECUTABLE_PATH`, read by `doc-build-setup`'s Mermaid renderer. (#446)
- Generation and sync need Copier 9.6.0 or later and `--trust`, because the template runs one post-creation task and `forge-sync` reviews any `copier.yml` change before trusting it. (#75)
- With release tags in place, `copier copy` and `forge-sync` take the latest tag rather than whatever `main` holds. (#90)
