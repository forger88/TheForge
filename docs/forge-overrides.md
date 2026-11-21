# Forge overrides

Every local edit to a forge-owned file is recorded here, in the same PR as the edit (`.forge/forge-overrides.md`).
A forge-owned file is any file TheForge ships outside the project-owned and seeded lists `.forge/forge-overrides.md` names: that covers `.forge/`, the skills under `.agents/skills/`, `instructing-agents.md`, `scripts/project_init_checklist.md`, the generated reference docs under `docs/agents/`, and the guard-bearing configuration (`scripts/*.py`, `.pre-commit-config.yaml`, the workflows, `.devcontainer/devcontainer.json` and `.claude/`).
Edits to a seeded file (the baselines, allowlists and other data files `.forge/forge-overrides.md` lists under "Seeded files") are not logged here.
`forge-sync` reads this file before every `copier update`, so a conflict on a logged file is expected and resolved in the project's favour unless upstream now covers the same need.
An unlogged edit to a forge-owned file is a review finding.

This file is project-owned: TheForge created it once and a sync never touches it.

## Entry shape

```md
### <path of the forge-owned file>

**Changed:** <which sentences or section, and to what>

**Why:** <the project need, citing the ticket>

**Upstream candidate:** <yes, rewritten generically | yes — proposed as <ticket link or "drafted in <sync PR link>">, <date> | no, project-specific | no — declined by owner, <date>>
```

Remove an entry once the change has gone upstream and come back through `forge-sync`, or once the local edit is reverted.

## Overrides

### `.pre-commit-config.yaml`

**Changed:** the `no-issue-refs` and `denylist` hooks' `exclude:` patterns gained rendered-path exclusions. First landed (self-retrofit part 1, slice 3) as exact paths: `.copier-answers.yml`, `.forge/`, `.agents/skills/`. Widened (self-retrofit part 2, slice 4), once rendering the rest of the forge content surfaced more rendered paths carrying the same real-tracker-number and real-owner-account shape than slice 3 alone had landed, to: `NOTICE.md` (carries the real `repo_owner` answer); every direct markdown file under `docs/agents/` except `lessons.md` and `operational-constants.md` (both project-owned and hand-maintained, never forge-generated — this also replaced the exact matches with the general pattern); and `scripts/project_init_checklist.md` (forge-generated, same scope this file's own header already names as forge-owned).

**Why:** TheForge's own self-retrofit renders these at root; `.copier-answers.yml`/`NOTICE.md` name the owner account and the rendered `.forge/`/`docs/agents/`/`scripts/project_init_checklist.md` files carry real tracker numbers through the `*_ref` variables, which the two hooks would otherwise reject. The patterns name only the rendered paths, never a directory forge-source itself lives in, so `template/` stays scanned and `denylist-not-shipped-render` still checks the render (threat-model T4).

**Upstream candidate:** no, project-specific. This file is never copied into a generated project; `template/.pre-commit-config.yaml.jinja` is TheForge's shipped consumer config, and it already carries the analogous shape for a consumer's own rendered forge paths.

### `.pre-commit-config.yaml` — `docs/release-notes.md` warn-only issue refs

**Changed:** `no-issue-refs`'s `exclude:` gained `^docs/release-notes\.md$`, and a new hook, `no-issue-refs-release-notes`, scans that one path with `scripts/check-no-issue-refs.sh --warn` instead. `denylist` is untouched; it still runs on `docs/release-notes.md` in its normal failing mode.

**Why:** the owner's committed release-notes document (CLAUDE.md, "Tagging a release of this repository") legitimately cites this repository's own merged PR numbers by design — its entries cite the PRs they describe, the same content the tag message always carried — so the strict `no-issue-refs` hook would fail on every release-notes edit. The tagging procedure already treated the tag's own notes file this way (`--warn`, never failing) before release notes were a committed file; this carries the same warn-only treatment over to the committed path.

**Upstream candidate:** no, project-specific. `no-issue-refs` and its commit-msg counterpart are TheForge-staging-only hooks (project-neutrality has no equivalent for a generated project), so `template/.pre-commit-config.yaml.jinja` has no matching hook to widen.

### `.pre-commit-config.yaml` — TheForge meta-guard hooks

**Changed:** self-retrofit part 2 (slice 4) renders this repository's own `.pre-commit-config.yaml.jinja` at root, the same way any consumer gets it, and merges it with every hook this repository already had before that render (the meta-guard hooks that govern `template/` as forge-source, listed under the "TheForge's own meta-guard hooks" heading in the merged file). Two id collisions came out of the merge, both renamed on the pre-existing (template-scoped) side to keep both hooks distinct and both active (I3): `one-sentence-per-line` → `one-sentence-per-line-template` (scans `template/.forge/*.md(.jinja)?`; the rendered `one-sentence-per-line` now scans root `.forge/*.md`), and `skills-lock` → `skills-lock-template` (`--template` flag, scans `template/skills-lock.json`; the rendered `skills-lock` now scans root `.agents/skills/` and root `skills-lock.json`). `forge-entrypoint-template` already had a distinct id from the rendered `forge-entrypoint` before this slice, so it needed no rename.

**Open item O1 (double-scanning), resolved:** checked whether any hook on either side now scans the same file as a hook on the other side. None does: every meta-guard hook's `files:`/`entry:` scope is `template/`-rooted (or, for the two renamed ones, explicitly re-scoped to stay that way), and every rendered consumer hook's scope is root-rooted, disjoint from `template/`. The two renamed hooks keep their original file scope unchanged; only their ids moved, so no hook newly scans a file it didn't already scan, and no file is now scanned twice by two hooks claiming to do the same check.

**Why:** TheForge rendering its own consumer template end-to-end is this self-governance feature's whole point; landing the collision without the renames would have silently disabled one of two genuinely different checks that happened to share an id, which is exactly the I3 invariant this slice exists to protect.

**Upstream candidate:** no, project-specific. The rename only exists because this one repository runs both the forge-source hooks and a rendered copy of its own consumer hooks side by side; no generated project has that collision, so `template/.pre-commit-config.yaml.jinja` needs no equivalent change.

### `.pre-commit-config.yaml` — `coordinator-core-template` hook

**Changed:** added `coordinator-core-template`, a meta-guard hook alongside the rendered `coordinator-core` hook, checking `template/.forge/coordinator-core.md.jinja`'s own shape the same way `coordinator-core` checks the rendered root copy. It never comes from a template render (no generated project has a `template/` to check), so each sync's merge conflicts on it the same way the other meta-guard hooks above do; this entry retroactively logs it, found unlogged during a later sync.

**Why:** same as "TheForge meta-guard hooks" above — this repo runs both the forge-source hook and the rendered consumer hook side by side.

**Upstream candidate:** no, project-specific, same reason as "TheForge meta-guard hooks" above.

### `.pre-commit-config.yaml` — `coordinator-core-lock` hook

**Changed:** added `coordinator-core-lock`, which runs `check_coordinator_core.py lock` against the root-only `coordinator-core.lock.json`. It never comes from a template render and is not in `template/.pre-commit-config.yaml.jinja`.

**Why:** the lock hashes the `template/` text of the shared sources the coordinator core condenses, so it is a TheForge maintainer's guard; a consumer's rendered sources differ per project, so a shipped lock would churn. Consumers keep `shape`, `rotated`, `drift` and `notes`.

**Upstream candidate:** no, project-specific.

### `.pre-commit-config.yaml` — `template-scripts-tests` hook

**Changed:** added `template-scripts-tests`, running `python3 -m unittest discover -s template/scripts -p 'test_*.py'`. It never comes from a template render (no generated project has a `template/` to test) and is not in `template/.pre-commit-config.yaml.jinja`. Found unlogged during the 2026-11-07 sync to `2861902`, which also widened `guard-script-tests`'s own comment and trigger upstream: upstream's new `guard-script-tests` comment ("Most are tested once in TheForge itself; only the two rendered-state tests ... run here") is written for a consumer that has no `template/scripts/` to run those other tests against; this project does, via this hook, so it keeps its own comment on `guard-script-tests` explaining the split instead of taking upstream's.

**Why:** most of `template/scripts/test_*.py` stopped shipping to consumers (a later sync landed `copier.yml`'s `_exclude` list for this); this repository is the one place left that still has to run them, directly against the `template/scripts/` source they're written against, the same shape `template-doc-tools-tests` already uses for `docs/tools/tests/`.

**Upstream candidate:** no, project-specific, same reason as "TheForge meta-guard hooks" above: no other repository runs both a forge-source and a rendered copy of its own template side by side.

### `.pre-commit-config.yaml` — forge-source/rendered-consumer hook-id collision convention

**Changed:** stated the convention the entries above each applied by hand, as its own documented rule: whenever a new forge-source meta-guard hook's id would collide with a rendered consumer hook of the same name (the id already present from rendering `template/.pre-commit-config.yaml.jinja` at root), rename the forge-source side `<id>-template` and keep both active. `scripts/test_precommit_hook_coverage.py`'s `NoHookIdCollidesAcrossForgeSourceAndRenderedConsumer` is the mechanical half of this entry: it fails on any `- id:` defined more than once in `.pre-commit-config.yaml`, which is what an un-renamed collision always produces in this one file (the rendered copy always carries every template id unchanged, so a forge-source hook sharing one without the suffix is a literal duplicate, not a second file to diff against).

**Why:** four collisions happened by hand before this was written down anywhere (`one-sentence-per-line`, `skills-lock`, `forge-entrypoint-template` pre-existing, `coordinator-core-template`); the fourth shipped unrenamed for a time because nothing caught it before merge.

**Upstream candidate:** no, project-specific. TheForgeStaging is the only repository running both a forge-source and a rendered copy of its own template side by side; `template/.pre-commit-config.yaml.jinja` needs no equivalent.

### `.gitignore`

**Changed:** unioned with the forge-shipped `.gitignore` (self-retrofit part 2, slice 4). Every forge line landed; six root-only lines stayed on top of it: `*.swp` (not implied by any forge pattern) and five pre-commit-hook-coverage probe paths (`/scripts/.precommit_probe_scratch/`, `/probe_rendered_root.md`, `/docs/agents/probe_rendered.md`, `/.agents/probe_agents_sibling.md`, `/.forgex/`) that `scripts/test_precommit_hook_coverage.py` creates and cleans up as scratch fixtures.

**Why:** the probe paths are this repository's own guard-test fixtures (added in the slice landing the `.forge/` import and the skills together); nothing forge-shipped anticipates them, and dropping them would commit test scratch output on a run that doesn't clean up.

**Upstream candidate:** no, project-specific. `.gitignore` is a seeded file (`.forge/forge-overrides.md`'s "Seeded files" list), not a forge-owned one this file's header scope covers, but the design doc for this feature calls for logging a `.gitignore` union here when a root-only line survives it, so the entry is kept consistent with that rather than left unlogged.

### `.github/pull_request_template.md`

**Changed:** rendered the forge-shipped template at root (self-retrofit part 2, slice 4), keeping every section it ships (`Before:`/`After:`/`How:`/`Requirements:`/`Process:`/`Release note:`/`Evidence:`/`Tests:`/`Guides:`), and adding one override section the shipped template has no equivalent for: `Neutrality:`, placed just before `Door:`. `Requirements:` reads `none (internal)` until this repository has a requirements specification of its own (no stage 0 has run here yet); `Process:` already applies, since `CLAUDE.md` imports the forge entrypoint.

**Why:** every PR to this repository goes through the project-neutrality checks (`CLAUDE.md`, "TheForge stays project-neutral"), which record their mechanical-scan and fresh-reviewer results on the PR the same way `Tests:`/`Evidence:` record theirs; no consuming project has an equivalent check, so the shipped template carries no line for it.

**Upstream candidate:** no, project-specific. `template/.github/pull_request_template.md.jinja` needs no `Neutrality:` line, since project-neutrality is a TheForge-repository-only concern, not something a generated project's own PRs are reviewed against.

### `scripts/check_module_size.py`, `scripts/check_no_snapshots.py`

**Changed:** both scripts' vendored-path exclusion tuple (`VENDORED_PREFIXES` / `_VENDORED_PREFIXES`) gained `"template/"` alongside the existing `".agents/skills/"` entry. Found running the merged `.pre-commit-config.yaml` for the first time (self-retrofit part 2, slice 4): both scripts do a full `git ls-files` tree walk regardless of which files pre-commit's own trigger passed them, so once `module-size`/`no-snapshot-assertions` landed at root, that walk reached into `template/` and flagged a vendored third-party skill file (`template/.agents/skills/impeccable/scripts/live-browser.js`, over the module-size cap) and the `no-snapshot-assertions` checker's own byte-identical `template/` copy of itself (its `SELF` self-exclusion only resolves its own root-invoked path, not the separate `template/scripts/check_no_snapshots.py` file).

**Why:** `template/` is forge-source, not this project's own code — the same reason `.agents/skills/` (root, rendered) is already excluded — but no other consuming project has a `template/` directory at all, so this gap was invisible until this repository rendered and ran these hooks against itself.

**Upstream candidate:** no, project-specific. `template/scripts/check_module_size.py.jinja`/`template/scripts/check_no_snapshots.py` need no `template/` exclusion for any other consumer, since none of them has a `template/` directory.

### `.github/workflows/review-gate-check.yml`

**Changed:** deleted at root. The check it ran (`scripts/check_review_gate.py`, plus the lifecycle-wording and trust-record guards) runs in `scripts/check-merge-text.sh` at the merge instead. `.forge/review-gate.md`, `.agents/skills/forge-sync/SKILL.md` and `scripts/check_review_gate_local.sh` still describe the workflow as always-on; they are forge-owned and left unedited, so read them as "the merge-time check" here. `WorkflowPinsTheGuardCheckoutToBase` in `template/scripts/test_check_forge_sync_trust_record.py` (no root copy any more: it no longer syncs to a generated project; it runs here directly, via `template-scripts-tests`) skips when the workflow file is absent.

**Why:** the owner does not want Actions credits spent on CI; the workflow also never ran, because an unquoted `Review: ` in a step name made it invalid YAML. Restoring it is parked in a hanging ticket ("Re-enable review-gate-check as a CI workflow if the local merge-step check proves unreliable").

**Upstream candidate:** no, project-specific. The template's copy has the same YAML bug, tracked in the ticket "Fix invalid YAML in template review-gate-check workflow".

### `.agents/skills/build-thread-brief/SKILL.md`

**Changed:** added a "Forge-porting tickets" bullet: a ticket whose content ports material from a consuming project runs `CLAUDE.md`'s "Back-porting from a consuming project (upstream first)" steps 1-3 and "TheForge stays project-neutral"'s three checks, recording the result on the PR's `Neutrality:` field.

**Why:** the ticket "Decide how a ticket that ports content into TheForge names its decontamination pass" (serving an open owner question an earlier forge-porting ticket carried, since answering it there would have blocked that ticket's own build): nothing made a build thread's brief name the back-porting procedure for a future forge-porting ticket, so a thread picking one up through the ordinary queue would run the standard mechanical scan against the committed denylist only, missing the source project's own terms. The owner chose the standard-brief-line option over a dedicated skill.

**Upstream candidate:** no, project-specific. Porting content *into* TheForge from a consuming project is a concept unique to this repository's own self-governance; no generated project has one.

### `.forge/main-health-patterns.md`

**Changed:** added a paragraph to "Patterns worth recording" naming this repository's own fourth recurrence of the same post-merge-review finding shape, with its merged-PR history.

**Why:** `.forge/main-health-patterns.md`'s own header says this file states what the Main Health thread watches "for this project"; the fix ticket that introduced this paragraph named this exact path for recording the recurrence, and most of the paragraph cites this repository's own merged-PR history throughout, so it reads as this project's own experience, not generic guidance any consuming project could use unchanged. Its closing sentence is the exception — found on a second look at this log, prompted by the owner asking what else might have been wrongly kept local-only after the `forge-sync` skill's own candidate (above): the lesson that a category-shaped PR search by file path misses hits outside the paths it happened to list, and that a periodic full-range re-sweep is the fix, carries no real issue number and reads as a general Main Health lesson, the same shape as the three already-generic patterns listed just above it in this file.

**Upstream candidate (closing sentence only):** yes — proposed as [ticket 718](https://github.com/forger88/TheForgeStaging/issues/718), 2026-11-15. The rest of the paragraph stays `no, project-specific`.

### `.agents/skills/post-merge-review/SKILL.md`, `.agents/skills/queue-sweep/SKILL.md`, `.forge/model-tiers.md` — real-issue-number citations

**Changed:** three sentences each carry a parenthetical citation of one of this repository's own issue numbers (post-merge-review's "Pending reviews" paragraph, queue-sweep's finding (e), and model-tiers.md's self-report paragraph), where the `template/` mirror carries the same sentence generically, with no number. Each citation lands at root only, in the same PR that also updated the `template/` mirror generically — the PR that touched post-merge-review's paragraph says so in its own body ("The root file's version also cites the issue; the `template/` mirror omits that citation to stay neutral."). Found unlogged during the 2026-11-15 self-sync to v0.2.0: `copier update` raised the first two (post-merge-review, queue-sweep) as merge conflicts against the newly-released, still-generic `template/` wording, resolved by keeping the project's cited version unchanged (no net diff against the pre-sync file, since the resolution matches what was already there); the third (model-tiers.md) was never part of a conflict at all — upstream hadn't touched that sentence in this sync's range — and only surfaced because "Check the result"'s full render-diff compares root against a clean render regardless of what `copier update` itself touched. This entry retroactively logs all three the same way, so a later sync's conflict resolution keeps the citations instead of taking upstream's uncited version.

**Why:** these three decision/behaviour citations are, like the rest of this repository's self-governing docs (see ".pre-commit-config.yaml" above and the render-path exclusions it documents), citing this project's own real tracker history; `template/`'s copy stays neutral per "TheForge stays project-neutral" (`CLAUDE.md`), so the two can never converge on their own.

**Upstream candidate:** no, project-specific. Each citation names a real issue number from this repository's own tracker; `template/`'s mirror has no equivalent repository to cite.

**Upstream candidate:** no, project-specific. The paragraph is written entirely in terms of this repository's own issue and PR history; a generated project has none of that history and would gain nothing from carrying this text forward on its next sync.
