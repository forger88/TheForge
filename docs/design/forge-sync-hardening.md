# Forge sync hardening

**Status:** implemented, reconciled against main @ ca5eda1.
**Tracking issue:** "How do repos started from TheForge receive later TheForge changes?" That issue holds the use cases (stage 2), the high-level design and its amendment (stage 3), and the approved behaviour wording W1–W9 (stage 4). This repository has no requirements specification, so that issue is the requirement record. Every slice below cites W-numbers from it.
**Decision record:** ADR-0006.

This document is written for the agents that build the slices. Each slice section is that slice's contract.

## Goal

A project generated from TheForge keeps receiving TheForge's later changes through the existing `forge-sync` skill (`copier update`). The sync happens only when the project's owner asks for it.

Three things stop that working today:

- **`CLAUDE.md` is frozen.** It is in `_skip_if_exists` and carries forge-authored text: the import list, a preamble, and the rule-strength section. That text never updates after generation.
- **Nothing tells a project it is behind.** There is no signal at all.
- **Nothing tells the owner how to sync.** No document explains how to ask for one.

The design fixes all three by hardening `forge-sync`. It adds no new sync mechanism.

## Out of scope

- TheForge syncing changes into itself, including keeping its own copy of `.forge/entrypoint.md` current. That is the issue "Give TheForge a way to properly review and maintain itself".
- Deciding which TheForge changes are safe for consumers to pull at all. That is TheForge's own issue on safe propagation out of TheForge.
- Release tags. That is the issue "Tag releases cheaply enough for an agent to do it, so consumers sync to vetted versions". The drift check compares against upstream `HEAD` until tags exist.
- Pre-checking upstream `copier.yml` unsafe features and executable files before `copier update --trust` runs. That is the issue "forge-sync: check upstream copier.yml and executable files before copier update --trust runs them". Slice 2 leaves the seam where that check slots in.

## Invariants every slice keeps

1. **I1. No forge-authored rule text in `CLAUDE.md`.** A generated `CLAUDE.md` carries forge-authored rule text only as the single line `@.forge/entrypoint.md` (W1). Everything else in it is the project's own.
2. **I2. Every rule file is reachable from the entrypoint.** Every `.forge/*.md` file other than the entrypoint itself is either imported by `.forge/entrypoint.md` or named in its reference-files sentence. Every file the entrypoint names exists (W2).
3. **I3. No unsafe Copier features.** Nothing in this design adds an unsafe Copier feature: no `_migrations`, no `_jinja_extensions`, and no new `_tasks` entry (ADR-0006).
4. **I4. Copier runs only on the owner's request.** `copier update` runs only inside `forge-sync`, and only when the owner has asked for a sync (W6). The drift check and Main Health never run Copier.
5. **I5. The migration deletes only exact matches.** The entrypoint migration removes from a project-owned file only lines byte-identical to the old template's render, matched positionally against the render's contiguous forge-authored block, never by a set-membership test against the whole file, and keeps every other line (W7).
6. **I6. The new scripts use only the standard library.** They run under `python3` with nothing installed, like the other guard scripts under `template/scripts/`.
7. **I7. Forge-owned rule files stay one sentence per line.** That includes `.forge/entrypoint.md`, which the existing `one-sentence-per-line` hook already covers.

## Module map

| Module | New or touched | Its one job | Named hook |
|---|---|---|---|
| `template/.forge/entrypoint.md` | new | The single forge-authored entry point: framing, `@.forge/` imports, reference-files sentence | imported by `CLAUDE.md` |
| `template/CLAUDE.md.jinja` | touched | Project-owned seed; forge content reduced to the import line | the `@.forge/entrypoint.md` line |
| `template/AGENTS.md.jinja` | touched | Points other harnesses at the entrypoint | step 2 of its reading list |
| `template/scripts/check_forge_entrypoint.py` | new | Checks I1 and I2 on a rendered project or on the template | `problems(root, template)` |
| `template/scripts/check_forge_drift.py` | new | Read-only: how far `_commit` is behind upstream, plus the entrypoint check | `drift(max_subjects)` |
| `template/scripts/check_sync_duplicates.py` | new | Advisory: lines a sync duplicated that neither side had twice | `new_duplicates(base, render, paths)` |
| `template/scripts/_git_subprocess.py` | new | The one place the git-subprocess timeout and flag-injection check live, shared by `check_forge_drift.py` and `check_sync_duplicates.py` | `run_git(args, timeout)`, `looks_like_flag(value)` |
| `template/.pre-commit-config.yaml.jinja` | touched | Wires `forge-entrypoint` into consumer commits | hook id `forge-entrypoint` |
| `.pre-commit-config.yaml` (root) | touched | Wires the template-mode check into TheForge's own commits | hook id `forge-entrypoint-template` |
| `template/.agents/skills/forge-sync/SKILL.md` | touched | The sync procedure | new sections "Entrypoint migration", "Check the result" |
| `template/.agents/skills/watch-main-ci/SKILL.md.jinja` | touched | Runs the drift check daily; holds the sync ticket | new section "Forge drift check" under Routine 1 |
| `template/instructing-agents.md` | touched | Owner write-up | new section "Keeping the project current" |
| `docs/security/threat-model.md` | touched | Folds in the threat-model deltas below | §4, §7, §9 rows |

**Deletion test.**

- `check_forge_entrypoint.py`: deleting it leaves W3 unenforced. It also removes the one implementation that both the hook and the drift check call, so they would each re-derive it.
- `check_forge_drift.py`: deleting it leaves W4 with no mechanism. Main Health would be hand-running `git ls-remote` with no consistent output line for the sync ticket to parse.
- `check_sync_duplicates.py`: deleting it returns the duplicate check to re-reading hunks by eye, which misses a duplication that is not adjacent to the conflict. That module stays.
- `_git_subprocess.py`: deleting it leaves both scripts to reinvent the timeout and the flag-injection check separately, which is how `check_sync_duplicates.py` ended up with no timeout at all while `check_forge_drift.py` had one. It is a hard dependency of both, not an optional convenience.
- `entrypoint.md`: deleting it puts the import list back in a frozen file, which is the original problem.

**Seams.** No new Protocol or adapter is introduced. `problems()` has two real callers: the `forge-entrypoint` hook (and its template-mode twin) and `check_forge_drift.py`.

## Build versus buy

| Module | Considered | Decision |
|---|---|---|
| `check_forge_entrypoint.py` | pre-commit's `pygrep` with `--negate` (fails files lacking a pattern) | Rejected. It covers only the "line present" check. The duplicate-import and I2 coverage checks need cross-file logic, and the drift check needs a callable. The script is hand-rolled, about 100 lines, standard library only. |
| `check_forge_drift.py`, upstream query | the hosting platform's compare API | Rejected. It is host-specific, needs a token for a private upstream, and is rate-limited. |
| `check_forge_drift.py`, upstream query | GitPython or dulwich | Rejected. Either adds a dependency, which breaks I6. |
| `check_forge_drift.py`, upstream query | the `git` command line | Adopted. It is already present wherever Copier runs, uses the environment's existing git credential, and works against any host or a local path. |
| `check_forge_drift.py`, answers parsing | PyYAML | Rejected under I6. Reuse `bootstrap.read_answers()`, which already parses `.copier-answers.yml`'s flat `key: value` shape. |
| `check_sync_duplicates.py` | `git diff` options, `uniq -d` | Rejected. Neither compares occurrence counts across three trees (pre-sync, upstream render, result), and a clean merge can duplicate lines that are far apart. The script is hand-rolled, about 80 lines. |

## Data and configuration

No new Copier question and no new answers-file key.

The drift check reads two existing answers keys:

- `_src_path`: where the template came from.
- `_commit`: the template version. Copier writes it as `git describe --tags --always`, so the value is a bare short SHA today, and `<tag>-<n>-g<sha>` or a bare tag once tags exist.

The drift check prints exactly one result line, which the sync ticket and Main Health parse:

```
forge-drift commit=<_commit> upstream=<full sha> target=<ref> behind=<n|unknown> entrypoint=<ok|missing> [unreleased=<n>]
```

`upstream` and `target` name the ref a default `copier update` syncs to: the latest release tag on `_src_path`, or `HEAD` when it has none (`_git_subprocess.resolve_sync_target`). `unreleased` appears only when tags exist and counts commits past that tag, for information only.

Up to `--max-subjects` (default 20) commit subjects follow, one per line, each prefixed `  - `. Control characters are stripped and each subject is cut to 120 characters.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | current and the entrypoint is ok |
| 1 | behind |
| 2 | could not determine (`behind=unknown`) |
| 3 | entrypoint missing; takes precedence over 1 and 2 |

The held sync ticket:

- **Title:** `Sync forge-owned files to TheForge <short upstream sha>`.
- **Label:** `needs-decision`, and only that.
- **Body:** the result line, the subject list (ending "…and N more" when `behind` exceeds the listed subjects, so every unsynced commit is counted), and the sentence "Held until the owner says to sync; then run `.agents/skills/forge-sync/SKILL.md` against this ticket."

## Slice 1: entrypoint, its guard, and the migration

**Purpose.** Satisfy W1, W2, W3 and W7. The migration step ships with the guard because the guard arrives in a consumer through the same sync that has to migrate it. A sync of slice 1 without the migration step would fail `pre-commit run --all-files` with no instruction on how to proceed.

**Requirement IDs.** W1, W2, W3, W7.

**Files.**

- `template/.forge/entrypoint.md` (new)
- `template/CLAUDE.md.jinja`
- `template/AGENTS.md.jinja`
- `template/scripts/check_forge_entrypoint.py` (new)
- `template/scripts/test_check_forge_entrypoint.py` (new)
- `template/.pre-commit-config.yaml.jinja`
- `.pre-commit-config.yaml`
- `template/.agents/skills/forge-sync/SKILL.md`, "Entrypoint migration" section only
- `template/instructing-agents.md`, line 18's description of `CLAUDE.md` only (the full write-up is slice 4)
- `template/.agents/skills/code-review/SKILL.md`, line 38's "the `.forge/` files it imports" becomes "the `.forge/` files it imports through `.forge/entrypoint.md`"
- `docs/security/threat-model.md`, because the root `.pre-commit-config.yaml` changes
- root `AGENTS.md`'s "Where things live" ADR list, which gains ADR-0006

**Blocked by.** Nothing.

**`.forge/entrypoint.md`** holds, one sentence per line:

1. The framing sentences now in `CLAUDE.md.jinja`'s preamble:
   - the process rules live in the `.forge/` files imported below;
   - procedures live under `.agents/skills/`;
   - project rules go in `CLAUDE.md`, never inside a `.forge/` file (`.forge/forge-overrides.md`).
2. One sentence saying this file is forge-owned and synced, so `CLAUDE.md` must keep its `@.forge/entrypoint.md` line, and the `forge-entrypoint` hook refuses a commit that drops it.
3. The 17 `@.forge/` import lines, in today's order, with `never-default.md` first.
4. The reference-files sentence, naming the same four files in backticks as today.

**`CLAUDE.md.jinja`** becomes:

- the `# Working on {{ project_name }}` heading;
- one sentence saying the file is project-owned and `copier update` never overwrites it;
- one sentence pointing at `instructing-agents.md` for how to work with the agents and keep the project current;
- `@.forge/entrypoint.md`;
- the existing "This project's own rules" and "Lessons this project has paid for" sections, unchanged.

The "Rule strengths" section and the "Forge rules" heading are removed. `never-default.md` delivers the rule strengths.

**`AGENTS.md.jinja`** step 2 becomes: "`.forge/entrypoint.md`, and every file it imports (its lines starting with `@.forge/`); a harness that does not resolve `@` imports opens each of those files itself, since they are the forge-owned process rules and are not optional." Step 1 drops "for the rule-strength framework".

**Interface: `check_forge_entrypoint.py`.**

```
python3 scripts/check_forge_entrypoint.py [--root DIR] [--template]
```

- `problems(root: Path, template: bool) -> list[str]` returns one human-readable line per violation. An empty list means compliant.
- `entrypoint_targets(text: str) -> tuple[list[str], list[str]]` returns `(imports, references)`:
  - **imports**: the paths on lines matching `^@(\.forge/[\w.-]+\.md)\s*$`;
  - **references**: backticked `` `.forge/<name>.md` `` occurrences on non-import lines.
- In `--template` mode, `root` is the `template/` directory. Files are read as `CLAUDE.md.jinja`, `AGENTS.md.jinja` and `.forge/<name>.md` or `.forge/<name>.md.jinja`, and a `.jinja` suffix is stripped when matching names.
- Exit 0 when there are no problems. Exit 1 after printing each problem and a final remedy line. Outside template mode, the remedy line is: "If this project predates the entrypoint, run `forge-sync`'s 'Entrypoint migration' section."

**Behaviour.** `problems()` reports:

1. `CLAUDE.md` is missing, or has no line exactly equal to `@.forge/entrypoint.md`.
2. `AGENTS.md` exists and does not contain the string `.forge/entrypoint.md`.
3. `CLAUDE.md` or `AGENTS.md` has an `@.forge/<x>.md` line where `<x>` is also an entrypoint import (a double load).
4. An entrypoint import or reference names a file that doesn't exist.
5. A `.forge/*.md` file (other than `entrypoint.md`) is neither imported nor referenced by the entrypoint.
6. `.forge/entrypoint.md` itself is missing.
7. In `--template` mode only: `CLAUDE.md.jinja` has a stripped line of 30 or more characters that also appears in any `.forge/*.md` file. This is W1's "no forge-authored rule text" half. It is template-only because a consumer's `CLAUDE.md` is the owner's to write.

**Hooks.**

Consumer side, `forge-entrypoint`:

```
entry: python3 scripts/check_forge_entrypoint.py
pass_filenames: false
files: ^(CLAUDE\.md|AGENTS\.md|\.forge/.*\.md|scripts/check_forge_entrypoint\.py)$
```

Root side, `forge-entrypoint-template`:

```
entry: python3 template/scripts/check_forge_entrypoint.py --root template --template
pass_filenames: false
files: ^template/(CLAUDE\.md\.jinja|AGENTS\.md\.jinja|\.forge/.*|scripts/check_forge_entrypoint\.py)$
```

The trigger includes `.forge/`, because the entrypoint's import list defines what checks 3 to 5 enforce. A gate's trigger must cover the file that defines its scope.

**`forge-sync` "Entrypoint migration"** is a new section, placed after "Run the update" and before "Resolve each conflict":

1. When to run it: `CLAUDE.md` has no `@.forge/entrypoint.md` line and still has `@.forge/` import lines.
2. Render the template at the **old** `_commit` with the project's answers file:

   ```
   copier copy --trust --defaults --skip-tasks --vcs-ref <old _commit> --data-file .copier-answers.yml <_src_path> <tmp>
   ```

   Take `<tmp>/CLAUDE.md` and `<tmp>/AGENTS.md` as the old render.
3. Find the forge-authored block's **positional span** in the project's `CLAUDE.md`: the contiguous run of lines starting at the preamble's second sentence and ending at the reference-files sentence, covering in order:
   - the preamble's second and third sentences;
   - the "Rule strengths" section with its heading;
   - the "Forge rules" heading;
   - the `@.forge/` lines;
   - the reference-files sentence.

   Match this span positionally, line by line in sequence against the old render's own block — never by a set-membership test against the whole file, which would also delete a blank line, a repeated heading, or a quoted rule-strength sentence elsewhere that merely equals one of the block's lines. Delete only the lines inside that span that are byte-identical, position for position, to the old render's block; blank-line collapsing applies only inside this span. Insert the new seed's `instructing-agents.md` pointer sentence and `@.forge/entrypoint.md` in the span's place, where the "Forge rules" heading was.
4. Keep every other line, including any line inside that span that differs from the old render, and every line outside the span regardless of its text. List each kept line from inside the span in the PR body under "Migration: kept lines" for the owner to decide.
5. Do the same for `AGENTS.md`: find the positional span covering its step 1 and step 2 lines, delete only what matches the old render position for position inside that span, and insert the new seed's equivalent step 1 and step 2 lines (the `instructing-agents.md` pointer and `@.forge/entrypoint.md` reference, in `AGENTS.md`'s own wording) in the span's place.
6. Run `python3 scripts/check_forge_entrypoint.py`; it must pass.

**Seam it is tested through.** Every test builds its own fixture directory and never reads this repository's `template/`, because the test file ships to consumers and runs there under `guard-script-tests`, where no `template/` exists. The real template is checked by the root `forge-entrypoint-template` hook instead. `problems()` is called on a temporary directory built by each test, with no subprocess and no Copier. The two hooks are exercised once each by running the script as a subprocess on a fixture directory.

**Guard tests that must go red when the check is removed** (`test_check_forge_entrypoint.py`, one per check):

| Test | Fixture | Goes red if removed |
|---|---|---|
| `MissingEntrypointLine` | `CLAUDE.md` without the line | check 1 |
| `AgentsDoesNotNameEntrypoint` | `AGENTS.md` without the path | check 2 |
| `DoubleImport` | `CLAUDE.md` with both the entrypoint and `@.forge/review-gate.md` | check 3 |
| `DanglingImport` | entrypoint importing a missing file | check 4 |
| `UncoveredForgeFile` | an extra `.forge/new-rule.md` the entrypoint never names | check 5 |
| `MissingEntrypointFile` | no `.forge/entrypoint.md` | check 6 |
| `CompliantProjectPasses` | the both-sides case: a correct fixture returns no problems, so a check that over-fires goes red here | all |
| `TemplateModeStripsJinja` | `--template` against a `.md.jinja` rule file named without the suffix in the entrypoint | the suffix strip |
| `SeedCarriesNoForgeText` | `CLAUDE.md.jinja` with a sentence copied from a `.forge/` file | check 7 |
| `HookRefusesMissingLine` | the script run as a subprocess on a fixture without the line | the exit code W3 relies on |

The PR records, on its `Evidence:` line, each check commented out and its test going red.

**Threat-model delta** (rows for `docs/security/threat-model.md`):

- **§4 entry points.** Add the `forge-entrypoint` consumer hook to "Consumer commits". Correct the `copier copy --trust` row's "one entry" to name both `_tasks` entries now in `copier.yml`. Add `forge-entrypoint-template` to the root hook list.
- **§7, new row "T20, B5, Denial of service".** Threat: a consumer's `CLAUDE.md` loses its `@.forge/entrypoint.md` line, silently disabling every forge rule including the review gate. Controls: the `forge-entrypoint` hook; the drift check's `entrypoint=missing` (slice 3); `forge-sync`'s final `pre-commit run --all-files`. Guard test: `test_check_forge_entrypoint.py`. Residual: Low.
- **§7, new row "T21, B5, Tampering".** Threat: the one-time migration deletes project-owned rules from `CLAUDE.md` or `AGENTS.md`. Controls: positional, contiguous-region deletion against the old render (never a set-membership match against the whole file); kept lines listed in the PR body; the full review gate; the entrypoint check after migration. Guard test: none (procedural). Residual: Low.
- **§7, T13 extended.** The threat now also covers a sync changing which rule files load (an upstream edit to the entrypoint's import list). Controls add slice 2's PR-body listing of entrypoint import changes.

**UI.** None. This is template and process text, with no user interface.

## Slice 2: `forge-sync` hardening

**Purpose.** Make the sync procedure itself catch duplications and unexplained drift that a reviewer would otherwise have to find by hand, and state W6 in the skill.

**Requirement IDs.** W6 (and W7's PR-body listing, which slice 1 began).

**Files.**

- `template/.agents/skills/forge-sync/SKILL.md` ("Before you start", "Run the update", a new "Check the result", "Review and merge")
- `template/scripts/check_sync_duplicates.py` (new)
- `template/scripts/test_check_sync_duplicates.py` (new)
- `template/scripts/_git_subprocess.py` (new; shared with slice 3's `check_forge_drift.py`)
- `docs/security/threat-model.md` (this repository's CLAUDE.md requires it for any change to the `forge-sync` skill)

**Blocked by.** Slice 1, which edits the same skill file.

**Behaviour.** Skill text changes:

1. **"Before you start" gains a first line:** run this skill only when the owner has asked for a sync, either by a direct request or by releasing a held sync ticket (W6). Record the old `_commit` now.
2. **"Run the update" gains a placeholder sentence** for the pre-run upstream check owned by the issue "forge-sync: check upstream copier.yml and executable files before copier update --trust runs them": "The `--trust` flag above runs upstream's `copier.yml` tasks and any executable files it ships, and nothing here checks what changed in them before they run. Review upstream's diff for `copier.yml` and its executable files yourself before running the update, until this skill gets its own pre-run check for that." This is the seam only, not the check. (A later review found that placeholder's original wording named that issue inline, which leaked into shipped content; the skill text now describes the limitation itself instead, while this design doc still names the issue, since this doc is never shipped.)
3. **A new "Check the result" section** comes after "Resolve each conflict":
   1. Render the template at the **new** `_commit` with the project's answers file (the same `copier copy … --data-file` command as the migration, with the new ref) into a temporary directory. Run `diff -rq <render> . --exclude=.git`. Every "differ" or "Only in" line must trace to a `docs/forge-overrides.md` entry, a `_skip_if_exists` file, or a project-owned file the template never ships. List any that do not, and resolve them before the PR opens.
   2. Run `python3 scripts/check_sync_duplicates.py --base <pre-sync commit> --render <render dir>`. Fix every reported line, or explain it in the PR body if it is a deliberate duplicate.
   3. Run `pre-commit run --all-files`, which includes `forge-entrypoint`.
4. **"Review and merge"** adds three required PR-body items:
   - `_commit` before and after;
   - every line added to or removed from `.forge/entrypoint.md`'s imports, under "Entrypoint import changes", or "none";
   - "Migration: kept lines", or "not needed".

**Interface: `check_sync_duplicates.py`.**

```
python3 scripts/check_sync_duplicates.py --base REV --render DIR [PATH ...]
```

- `new_duplicates(base: str, render: Path, paths: list[Path]) -> list[tuple[Path, str, int]]` returns `(file, line, count)` entries.
- The candidate files are those changed against `base` (`git diff --name-only --end-of-options <base>`), filtered to text files, or the given paths.
- For each file and each stripped line of 30 or more characters that isn't only punctuation or markup, it reports the line when its count in the working tree exceeds both its count in `git show --end-of-options <base>:<file>` (0 if absent) and its count in `<render>/<file>` (0 if absent).
- `--end-of-options` sits immediately before `<base>` at both call sites, and a `--base` beginning with `-` is rejected outright before either call runs, so a flag-like value can never be parsed as a git option (T24; shares T23's `looks_like_flag` mechanism).
- Exit 0 when nothing is reported, 1 if a duplicate is found, 2 on a rejected `--base` or a failed `git diff`. It is advisory: the skill says what to do with a hit.

**Seam it is tested through.** `new_duplicates()` runs against a temporary git repository the test builds, with a base commit, a working-tree edit and a render directory.

**Guard tests.**

| Test | Fixture | Goes red if removed |
|---|---|---|
| `SyncDuplicatedALine` | the line occurs once at base, once in the render, twice after | the core comparison |
| `UpstreamDuplicateIsNotReported` | the render itself has the line twice | the render-count bound (the both-sides case) |
| `ProjectDuplicateAtBaseIsNotReported` | base already had it twice | the base-count bound |
| `ShortAndMarkupLinesIgnored` | `---`, `}`, a 10-character line repeated | the length and markup filter |
| `NewFileCountsFromZero` | a file absent at base | the absent-file default |
| `HookExitsNonZeroOnlyWhenReported` | `main()` run as a function call, with and without a hit | the exit code the skill's "Check the result" step relies on |
| `FlagLikeBaseIsRejected` | a `-`-prefixed `--base`, checked against `_candidate_files()`, `_counts_at_base()`, `new_duplicates()` and `main()` directly | the explicit flag-rejection check at either call site |
| `SeparatorBlocksAFlagLikeBaseEvenWithoutTheExplicitCheck` | the same payload shape against a real `git diff`/`git show --end-of-options` with no script code in between | the `--end-of-options` separator itself |

**Threat-model delta.**

- **§7, T13 controls.** Add "the render-and-diff and duplicate checks (`forge-sync`, 'Check the result')" and "the PR body's 'Entrypoint import changes' list".
- **§8.** Unchanged. The upstream executable pre-check stays the open gap it already is.

**UI.** None. This is a skill and a script, with no user interface.

## Slice 3: drift check and the held sync ticket

**Purpose.** Satisfy W4, W5 and W9. Main Health learns once a day how far behind the project is, keeps one held sync ticket, and raises a missing entrypoint at once.

**Requirement IDs.** W4, W5, W9.

**Files.**

- `template/scripts/check_forge_drift.py` (new)
- `template/scripts/test_check_forge_drift.py` (new)
- `template/scripts/_git_subprocess.py` (new; shared with slice 2's `check_sync_duplicates.py`)
- `template/.agents/skills/watch-main-ci/SKILL.md.jinja`: a per-repo values row "Forge drift check | `scripts/check_forge_drift.py`", and a new subsection "Forge drift check" under Routine 1
- `docs/security/threat-model.md`

**Blocked by.** Slice 1, because it imports `problems()` from `check_forge_entrypoint.py`.

**Interface: `check_forge_drift.py`.**

```
python3 scripts/check_forge_drift.py [--max-subjects N]
```

- The script runs from the project root, because `bootstrap.read_answers()` reads `.copier-answers.yml` relative to the current directory. That is why it takes no `--root` option.
- `drift(max_subjects: int = 20) -> Drift` returns a frozen dataclass with fields `commit`, `upstream`, `behind: int | None`, `entrypoint_ok: bool`, `subjects: list[str]` and `error: str | None`.
- `source_url(src_path: str) -> str`: `gh:owner/repo` becomes `https://github.com/owner/repo.git`, and `gl:owner/repo` becomes `https://gitlab.com/owner/repo.git`. Anything else (an HTTPS URL, an SSH URL or a local path) is returned unchanged.
- `commit_sha(commit: str) -> str | None` handles the three `git describe` shapes:
  - `<tag>-<n>-g<sha>` returns `<sha>`;
  - a bare hex string of 7 to 40 characters returns itself;
  - a bare tag returns `None`, and the caller resolves it with `git ls-remote -- <url> refs/tags/<tag>`.
- `main()` prints the result line and subjects, then exits with the code in "Data and configuration".

**Behaviour.**

1. Read the answers with `bootstrap.read_answers()`, imported from the sibling script, run from the project root. A missing or unreadable `.copier-answers.yml`, or a missing `_src_path` or `_commit`, gives `error`, exit 2.
2. Resolve the sync target (`resolve_sync_target`: `git ls-remote -- <url> HEAD` and `git ls-remote --tags -- <url>`), which gives `upstream`: the latest release tag's commit, or HEAD's when no tag exists. If the commit SHA is a prefix of `upstream`, then `behind=0` with no fetch.
3. Otherwise, run `git clone --bare --filter=blob:none --quiet -- <url> <tmpdir>`, then:
   - `git -C <tmpdir> rev-list --count <sha>..<upstream>` gives `behind`;
   - `git log --format=%s -n <max> <sha>..<upstream>` gives the subjects.

   If `<sha>` is not in upstream's history, the result is `behind=None` with an error naming that: a force-pushed upstream or a wrong `_src_path`.
4. Every git call has a timeout (60 seconds for `ls-remote`, 300 for the clone) and runs with `GIT_TERMINAL_PROMPT=0`, so a credential prompt from a misconfigured remote fails fast instead of hanging past the timeout. The script never passes a token, never reads one and never prints the URL's userinfo. `--` sits immediately before `<url>` at every call site, and a `_src_path` beginning with `-` is rejected outright before any of these calls run, so a flag-like value can never be parsed as a git option (T23). `TimeoutExpired` and `OSError` around every git call are caught and reported as `error`, exit 2 ("unknown"), rather than propagating as an uncaught exception; the caught message never includes the raw command, since `TimeoutExpired`'s own message embeds the full argv.
5. Compute `entrypoint_ok = not problems(Path("."), template=False)`.
6. The temporary directory is removed in a `finally`.

**`watch-main-ci` "Forge drift check"** runs in Routine 1's first daily firing (the firing that runs `queue-sweep`), as its own step. It is API and git only, so it needs no setup and stays outside the Routine 2 overlap rule. `queue-sweep` doesn't call it. The step:

1. Run `python3 scripts/check_forge_drift.py`.
2. **Exit 3 (`entrypoint=missing`):** report it to the owner immediately as a Must: "the forge rules are not loading" (W5). Do this whatever the drift result, and before the steps below.
3. **Behind (`behind=<n>` with n > 0 on the result line, whatever the exit code, so a missing entrypoint does not suppress the ticket).** Look for an open issue whose title starts with `Sync forge-owned files to TheForge ` and whose author is the repo's own configured identity (W9, T16) — the one account Main Health and `forge-sync` ever file or act on this ticket under, which another GitHub account cannot forge. Defaults to `{{ repo_owner }}`, which is only correct for a user-owned repo; an org-owned repo overrides it in `docs/forge-overrides.md` to the actual posting account, since a GitHub issue is always authored by a user, never an organisation.
   - If it carries `needs-decision`, retitle it to the new short upstream SHA and replace its body with the new result.
   - If it exists without `needs-decision`, the owner has released it and a sync is under way. Leave it alone and only mention the drift in the report. This departs from amendment 1's literal "update it if one already exists": once the owner releases the ticket it is the running sync's backing ticket, W9's held state has ended, and retitling it mid-sync would move the sync's target under the builder.
   - If there is none from that author, create it with the "Data and configuration" title, body and label. A title-matching issue from a different author is ignored for this logic (never retitled, never treated as a release, never counted as "none") and is mentioned once in the report as a possible forged look-alike.
   - Never label it `queued`, and never run `forge-sync`.
4. **Current (exit 0):** nothing to do.
5. **Unknown (exit 2):** mention the error once in the daily report. Don't file anything.

**Seam it is tested through.** `drift()` runs against a temporary local bare repository the test builds as the upstream, with `_src_path` set to its local path, so no network is involved. `source_url()` and `commit_sha()` are tested as pure functions.

**Guard tests.**

| Test | Fixture | Goes red if removed |
|---|---|---|
| `CurrentProjectIsNotBehind` | `_commit` equals upstream HEAD | the prefix short-circuit (the both-sides case) |
| `CountsCommitsBehind` | three upstream commits after `_commit` | the rev-list count |
| `SubjectsAreCappedAndSanitised` | 25 commits, one subject with a control character and 200 characters | the cap, the strip and the cut |
| `DescribeFormParsed` | `v1.0-3-gabc1234` | `commit_sha`'s describe branch |
| `BareTagResolved` | a tagged upstream and `_commit: v1.0` | the tag resolution |
| `UnknownCommitIsUnknownNotCurrent` | `_commit` not in upstream history | the not-found branch (it must not report `behind=0`) |
| `MissingEntrypointWins` | behind, and `CLAUDE.md` without the line | exit 3 precedence, with `behind=<n>` still reported so the ticket step runs |
| `GhShorthandMapped` | `gh:a/b` | `source_url` |

**Threat-model delta.**

- **§4 entry points.** Add "Consumer Main Health drift check: `scripts/check_forge_drift.py`, outbound `git ls-remote` and blobless clone to `_src_path`, environment credential only".
- **§7, T13.** Note that the controls now include the drift check's visibility of unsynced upstream changes. The residual stays High until release tags exist.
- **§7, new row "T22, B5, Spoofing".** Threat: a tampered `_src_path` points the drift check at a look-alike repository and reports "current". Controls: the check is advisory; the answers file is under the consumer's review gate; a tampered `_src_path` already misdirects `copier update` itself (T13). Residual: Low.
- **§7, T16.** Correct the row: a forged, unlabelled issue matching the title prefix previously made Main Health treat the real drift as "already released", permanently suppressing creation or retitling of the genuine held ticket (bounded by the drift still appearing as a one-line report note). The held sync ticket is now matched by title prefix *and* author identity, which another account cannot forge; T16's residual drops to Low on a public consumer too.
- **Prompt injection via commit subjects.** The subjects come from the same upstream whose text the consumer obeys after sync, so this adds no new trust. They are capped and sanitised in the script. No new row.

**UI.** None. This is a script and skill text, with no user interface.

## Slice 4: owner write-up

**Purpose.** Satisfy W8: the downstream owner can find and follow how to keep the project current.

**Requirement IDs.** W8.

**Files.**

- `template/instructing-agents.md`: a new section "Keeping the project current" after "Checking on progress"
- `template/.agents/skills/forge-sync/SKILL.md`, "Before you start" step 1 and the drift-check step below
- `docs/security/threat-model.md`, re-read and its "Last reconciled" line confirmed, since this repository's CLAUDE.md requires it for any `forge-sync` change; no row changes

**Blocked by.** Slices 2 and 3, since it describes both.

**Behaviour.** The section covers, in this order:

1. TheForge changes after the project is generated. The project's forge-owned files (`.forge/`, `.agents/skills/`, the scripts and hooks) follow it only through a sync, and project-owned files never change in one.
2. Main Health's daily drift check. It produces the held sync ticket and says how far behind the project is, and an `entrypoint=missing` report means "fix this now".
3. How to ask for a sync: "sync the forge", or tell the coordinator to release the held sync ticket. Either runs `forge-sync`, and nothing syncs without that request.
4. What the sync PR contains: `_commit` before and after, every conflict and how `docs/forge-overrides.md` decided it, entrypoint import changes, and any kept migration lines.
5. Why `CLAUDE.md` keeps its `@.forge/entrypoint.md` line, and that the hook refuses a commit that drops it.

`forge-sync` changes in two places:

- The "Before you start" item that says "Confirm there is a ticket for the sync … file one if not" becomes: "Use the held sync ticket Main Health keeps (`.agents/skills/watch-main-ci/SKILL.md`, 'Forge drift check') when one exists; otherwise file one. The sync PR closes it."
- A new step runs `python3 scripts/check_forge_drift.py` before the update, and its result line goes into the PR body. This step is the stage 3 design's "before the update, run the drift check" step. It lands here rather than in slice 2 because the script arrives in slice 3.

**Seam it is tested through.** Reading only. This is a prose slice.

**Guard test.** None, since it is prose only. The PR's `Evidence:` line is a read-through against W8 and against slices 2 and 3 as merged.

**Threat-model delta.** "Security: none". The slice adds prose and a call to slice 3's already-modelled drift script, with no new entry point, boundary or control.

**UI.** None. It is a document, with no user interface.

## Test matrix

| Requirement | Slice | Test or check |
|---|---|---|
| W1 | 1 | `SeedCarriesNoForgeText`; `MissingEntrypointLine`; the root `forge-entrypoint-template` hook passing on this repository's real template (recorded on the PR's `Evidence:` line) |
| W2 | 1 | `UncoveredForgeFile`; `DanglingImport`; `MissingEntrypointFile` |
| W3 | 1 | `HookRefusesMissingLine` |
| W4 | 3 | `CountsCommitsBehind`; `CurrentProjectIsNotBehind`; `UnknownCommitIsUnknownNotCurrent` |
| W5 | 3 | `MissingEntrypointWins`; skill text read-through |
| W6 | 2 | skill text read-through ("Before you start" first line; Main Health never runs Copier) |
| W7 | 1 | migration procedure read-through, plus a render of the template at a pre-entrypoint commit, migrated by hand and passing `check_forge_entrypoint.py` (recorded on the PR's `Evidence:` line) |
| W8 | 4 | read-through |
| W9 | 3 | skill text read-through; `SubjectsAreCappedAndSanitised` for the body content |
| I3 | all | `copier.yml` diff is empty in every slice's PR |
| I6 | 1, 2, 3 | each new script imports only the standard library and sibling scripts |

## Open items the implementer must re-verify

1. **Claude Code's recursive import depth.** Confirm against current Claude Code documentation before slice 1 merges that it still resolves nested `@` imports (CLAUDE.md, then the entrypoint, then each rule file: two hops). If it doesn't, stop and raise it on the tracking issue.
2. **Private upstream in sandboxes.** Confirm `git ls-remote` against a private `_src_path` works from a consumer Main Health sandbox with the environment's own credential. If it is refused, the result is exit 2 (`unknown`), which slice 3 already handles. Record what you saw on the PR.
3. **`_commit` shape.** Copier writes `_commit` from `git describe --tags --always`, which is why `commit_sha()` handles three shapes. Re-check against the pinned Copier version.
4. **New `_tasks` entries.** `copier.yml` carries a `_tasks` entry that runs on every operation. Confirm `forge-sync`'s `--skip-tasks` still skips it during a sync, and that no slice's migration render needs it.
5. **Line references.** The ones in this document (`code-review/SKILL.md` line 38, `instructing-agents.md` line 18) are as of the design commit. Find the sentences by content, not by number.
6. **Release tags.** When they land, the drift check's comparison target becomes the newest tag. That is a follow-up on the tag issue, not part of this design.
7. **Non-resolving harnesses.** The issue "Harnesses without recursive @-imports may load only .forge/entrypoint.md, not the rule files it imports" is `needs-decision`. If the owner's answer asks for more than the `AGENTS.md` wording, slice 1 takes it in. Check the issue before slice 1 merges.
