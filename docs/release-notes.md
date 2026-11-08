# Release notes

> **Ticket numbers.** A number written after a `#` in these notes refers to a ticket or pull request in TheForgeStaging, a private repository, so it can't be opened from here.

This repository's committed release-notes document (owner decision,
2026-10-31). Each release gets its own section here, drafted with the `release-notes`
skill (Enhancements, Bug fixes, Known issues and For integrators, with
`release:internal` PRs left out); the annotated tag `main` is cut from carries the same
notes as its tag message, per `CLAUDE.md`'s "Tagging a release of this
repository."

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
