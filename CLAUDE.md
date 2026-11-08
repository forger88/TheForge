# Working on TheForge

This file governs work on TheForge itself: the template repository.
It is never copied into a generated project; `template/CLAUDE.md` is what a generated project gets.

@.forge/entrypoint.md

## This project's own rules

### Agent commit identity (Never)

Every commit an agent makes to this repository is authored and committed under the agentic harness's own non-personal bot identity (the generic address or account it provides for this purpose), never under a personal address.
A squash merge is then authored by the hosting platform under the merging account's own no-reply alias and committed by the platform's own no-reply identity; that is acceptable, since it is the platform's mechanism, not a personal address chosen by anyone.
A real personal address is never acceptable in a commit author, a commit committer, or a `Co-authored-by:` trailer, on a head commit or on the squash commit alike.
Keep the account's email-privacy setting on (both "Keep my email addresses private" and "Block command line pushes that expose my email"); with it on, the host can refuse a push whose tip commit carries a non-anonymised author, and squash-merges under the account's no-reply alias.
`scripts/check-merge-text.sh` (via `scripts/check-commit-identities.sh`) checks every head commit's author, committer and `Co-authored-by:` trailer against this before a merge; the squash commit's own author, written by the platform at merge time under the merging account's alias, is the one identity no pre-merge check can see, which is why that specific shape is the one explicitly accepted above; `scripts/check-merge-text.sh <pr-number> --verify-merged` checks it, with the landed message, after the merge.
Fix a violation forward with a new commit, never by rewriting history already on the default branch.

This is stricter than the forge-rendered seed every other consuming project starts from (bot identity, platform squash shape): it names the exact platform mechanism this repository relies on, so it is kept here as a project-owned rule rather than left to the generic wording.

### TheForge stays project-neutral (Never)

TheForge is public, and its whole value is that any company can adopt it unchanged.
Its content is distilled from real projects that use this process, which is exactly how project-specific material leaks in.

TheForge never contains, anywhere in the repository (file contents, file names, directory names, commit messages, PR text):

- product names or host-system names from a source or consuming project;
- repository paths from a source project's layout;
- issue or PR numbers from any project, including TheForge's own, in shipped content;
- a source project's domain-model vocabulary, module or class names, or configuration keys;
- worked examples still shaped like the incident they came from, even with the names changed;
- people's names, other than the upstream credits (Matt Pocock, `impeccable`'s authors, and Dex Horthy / HumanLayer for the `show-me` skill reproduced inside `pr`) in `THIRD_PARTY.md`, `template/.agents/skills/THIRD_PARTY.md`, the licence files, `template/NOTICE.md`, and a credited skill's own attribution file or frontmatter source-note (for example `template/.agents/skills/pr/CREDITS.md`).

Where a rule's rationale benefits from an example, invent a fresh, clearly generic one (a caching layer, an invoice export, a rate limiter), and never reword a real incident.
The human directing the agents is "the owner" or "the user", never a named person.

Every change goes through three checks before it is pushed or merged, including an upstream-first refinement back-ported from a consuming project:

1. **A mechanical scan.** The pre-commit hooks in `.pre-commit-config.yaml` run `scripts/check-no-issue-refs.sh` (an `#NNN`-style reference pattern) and `scripts/check-denylist.sh` (a case-insensitive grep against a denylist; see `scripts/denylist-path.sh` for which one). By default that is `.theforge-denylist`, this private staging repository's own committed list of the owner's standing terms (name, email addresses, other projects' names); `$THEFORGE_DENYLIST_FILE` or `~/.theforge-denylist`, when set, unions with that default for the one scan rather than replacing it — a maintainer back-porting from a real project points it at that project's own terms, which get checked alongside the owner's committed ones, not instead of them (see "Running the contamination scan" below).
   `.theforge-denylist` itself must never ship under `template/`, into a generated project: `scripts/check-denylist-not-shipped.sh` (an always-run pre-commit hook checking the static tree) and the `denylist-not-shipped-render` hook (`scripts/test_denylist_not_shipped.py`, scoped to changes under `template/`, `copier.yml` or the denylist scripts themselves, since a full render is slower than a filesystem scan) guard that, because a public list of what to hide would itself be a leak. `scripts/publish_snapshot.py` also drops every `.theforge-denylist*` file from a public snapshot, and `scripts/test_publish_snapshot.py` goes red if it stops; `docs/security/threat-model.md` §8 names the remaining gap, that the first publish has not run yet.
   `.copier-answers.yml`, `.forge/` and `.agents/skills/` are excluded from `no-issue-refs` and `denylist`, since the retrofit that gave this repository its own root `CLAUDE.md` import renders those paths from `template/` with real tracker numbers and the owner account (see `docs/forge-overrides.md`); `template/` itself, which produced them, stays scanned.
   `docs/release-notes.md` is a different case: it legitimately cites this repository's own merged PR numbers by design (its entries cite the PRs they describe, as a release tag's message always has), so `no-issue-refs` runs against it in `--warn` mode only, the same semantics the tagging procedure above already used for the tag's notes file before they were committed; `denylist` still runs on it in its normal failing mode, since a release line should never need a denylisted term.
2. **A read-through by a fresh, context-free reviewing agent.** Start a sub-agent with no history of the source project and no briefing beyond this rule, give it the diff, and ask it to list every term or example that looks oddly specific.
   The reviewer treats any oddly specific term, number, path or example as a finding to raise, not something to wave through, and the change does not merge until each finding is resolved or explained.
3. **A merge-text scan.** Before merging, run `scripts/check-merge-text.sh <pr-number>` and merge with exactly the message it checked. When merging with a hand-written message, or with the hosting platform's own default (its commit-list message, for example) rather than this script's title-plus-body guess, write that exact message to a file first and re-run the scan with `--message-file <file>` before merging with it: a message the script never saw is a message that was never checked.
   After merging, run `scripts/check-merge-text.sh <pr-number> --verify-merged` with the same `--message-file` (if any) and the `--head-sha` the scan printed: it fails unless the squash commit on the base branch carries exactly the scanned message and only no-reply identities.
   On a failure, fix forward (never rewrite history on the default branch) and post a comment on the PR and on the post-merge review tracker naming the mismatch, never quoting a denylist hit.
   The pre-commit hooks scan file contents and commit messages, but the squash message is written on the hosting platform at merge time and is never a file.
   The script's own GitHub calls try the REST API directly with a bearer token first and fall back to `gh api` only when that fails, precisely so a sandbox whose `gh auth status` reports invalid (but whose underlying token still works) doesn't lose this check — but when *neither* path can produce a scan, the merge does not proceed on a manual approximation instead: fix whatever is blocking the script (an invalid or missing token, a network block) or escalate the blocker, and re-run it, before merging. Issue "scripts/check-merge-text.sh can't run in some cloud sandboxes (gh auth invalid)" is the record of two merges that went ahead this way instead — one on a hand-checked guess, one with no scan at all until after the fact — and the second of those found a real leak a pre-merge run would have caught.

ADR-0003 records why it takes all three checks: the mechanical scan catches the shapes a regex and a denylist can check without context, the reader catches what neither can, and the merge-text scan catches what no pre-commit hook ever sees — the PR's own title and body, and the message actually written at merge time.

### This repository's own threat model (Default)

`docs/security/threat-model.md` is TheForge's own STRIDE threat model: its assets, trust boundaries, threats, controls, known gaps and accepted risks, written with the template's own `template/.agents/skills/security-docs/SKILL.md` (bootstrap mode, at design-tier) and kept current with that skill's reconcile mode. A PR that touches `template/scripts/bootstrap.py`, `copier.yml`'s `_tasks` or any other unsafe Copier feature, a root guard script, `.pre-commit-config.yaml`, `.theforge-denylist-allow`, `.theforge-denylist`, `template/.claude/`, `template/.github/workflows/`, the `forge-sync` skill, or a control rule in this file updates that document in the same PR; its own "Keeping this document current" section says how.

### Review gate for this repository's own PRs (Default)

`.forge/review-gate.md` (imported above) carries the full/light gate split, the mandatory self-review step, the MoSCoW triage table, the mechanical `review-gate-check`, and "skills are used, never substituted" for this repository's own PRs, the same as for `template/`. Two things stay project-owned, since they are specific to this repository rather than to every consuming project:

- **A neutrality miss is always a Must.** This repository's own neutrality checks above have no analog in a generated project, so this grading rule for them lives here, not in the imported file.
- **Repeat offender, this repository only:** before merging, strip any harness-injected attribution or identity block from the PR body (a comment naming the requester, a link to a private project thread, or similar) and run `scripts/check-merge-text.sh <pr-number>` on the merge message you intend to use, per "TheForge stays project-neutral" check 3 above. This is a `scripts/check-merge-text.sh`-specific addition for this private repository's own PRs; it does not belong in `.agents/skills/self-review/SKILL.md` itself, since that file ships verbatim into every generated project and naming this repository's own script there would itself be a neutrality leak.

### This clone needs a `forger88/TheForge` or `forger88/TheForgeStaging` remote

`scripts/check-not-raw-clone.sh`, wired into `.pre-commit-config.yaml`, refuses any commit into a tree that has `copier.yml` and `template/` at its root but no remote naming `forger88/TheForge` or the private staging repository `forger88/TheForgeStaging` (ADR-0004) — the signature of a raw clone or "Use this template" copy being used as a project instead of generated via `copier copy`.
If you are working from a fork, add an `upstream` remote pointing at either `https://github.com/forger88/TheForge.git` or `https://github.com/forger88/TheForgeStaging.git` so the hook recognises this as a legitimate TheForge clone.

### This repository's own post-merge review (Default)

`.forge/post-merge-review.md` and the rendered `.agents/skills/post-merge-review/SKILL.md` (both imported/rendered by this retrofit) now carry the tracker's body shape, the batching and worktree-per-subsystem procedure, the MoSCoW triage, and the pending-note convention for this repository too — the same as for a generated project. What stays project-owned, because it is specific to running that process on TheForge's own un-generated root rather than on a generated consumer:

- **Render-checking.** Wherever a finding needs checking against rendered output, not just the template source, each reviewing worktree renders with `copier copy --trust --defaults --skip-tasks --vcs-ref HEAD . <worktree>/render-check` (`--vcs-ref HEAD`, not the default, or Copier checks out the latest tag over the working tree once one exists).
- **The neutrality axis.** Every reviewer's brief names it explicitly, alongside the security axis; a brief that leaves it implied gets a review that skips it, and a neutrality miss is graded a Must (as above).
- **An extra cadence trigger.** A pass also runs before each snapshot of this repository's files into the public TheForge repository, since that is the point an unreviewed merge costs the most, on top of the standing ~10-PR/2-3-day cadence the imported file already states. The cadence's owner is the Main Health TheForge thread (ADR-0010).
- **Interim health routine.** Until this repository is a consumer of its own template (ADR-0009), it has no CI for Main Health TheForge to watch, so each time the post-merge review routine fires, Main Health TheForge runs `pre-commit run --all-files` on `main`'s head (which includes `check-render`) and reports a red result the way a consumer's Main Health reports red CI. In the same firing it posts, as a comment on the tracker and never an edit to its body, any pending note a merge to `main` is missing (ADR-0010's pending-note backstop).
- **Where this repository still differs from what it ships.** It has no requirements specification of its own yet, so a review here checks a diff against `CLAUDE.md`/`AGENTS.md` and the ADRs in place of a spec, until the stage 0 follow-up gives it one. (This retrofit's own `ensure_trackers` run created the "Deferred architecture findings" epic (`arch_findings_epic` in `.copier-answers.yml`) that `.forge/post-merge-review.md` already names, so the earlier "no architecture-findings epic" exception no longer applies; it has no numbered SDLC document yet either, which is a separate, still-open gap tracked for the stage-0 follow-up, not this exception.)

### Tagging a release of this repository (Default)

Unlike a generated project, where `.forge/process-and-evidence.md`'s "Releases" rule reserves tagging to the owner, **an agent is allowed to tag and push a release here.** This is a recorded owner waiver of that imported rule, kept here so nobody "fixes" it back: the owner will not create releases of this repository by hand, and with no tags at all, every consumer's `forge-sync` syncs to `HEAD`, so every merge ships to every consumer on its next sync with no point at which a batch of changes has been declared reviewed and good.

There is no GitHub Release object — Copier reads only git tags — but,
unlike the generic consumer procedure this section otherwise mirrors,
release notes here are a committed file, `docs/release-notes.md`, not
drafted fresh into a tag message each time (owner decision, 2026-10-31):
the owner needs to be able to read and review notes on `main` as they're
written, ahead of any tag. The annotated tag's own message is a copy of
that release's section, not a separate draft.

**When to tag:** after a post-merge review run on this repository covers
its whole window with no open Must findings, and `scripts/check-render.sh`
passes on the commit being tagged. The tag goes on the commit at that
review's watermark.
Before tagging, ask the owner whether to run a fresh, unpublished
`scripts/local-full-suite.sh` pass against that commit first, so the tag
rests on a current check; the owner decides.

**How:**

1. `git fetch origin main --tags`, and check out that commit.
2. Pick the version: `vMAJOR.MINOR.PATCH` (Copier sorts tags as PEP 440,
   so no other shape works). Bump MINOR when consumers must act on the
   update (a new Copier question, a new standing tracker, a renamed
   file). Bump PATCH otherwise. Stay on `0.x` until the owner says
   otherwise.
3. Draft the release's section with `.agents/skills/release-notes/SKILL.md`
   — it owns the section shape (Enhancements/Bug fixes/Known issues/For
   integrators, the breaking-changes line, past-tense bug wording) and the
   known-issues sourcing; don't rederive any of that here, and don't
   draft from a bare `git log` listing instead of running the skill. Land
   the draft into `docs/release-notes.md` in its own PR, replacing any
   earlier draft of that version — this repository's own file is
   committed, not drafted fresh into the tag message (see above). Run
   `scripts/check-denylist.sh` and `scripts/check-no-issue-refs.sh
   --warn` over the section before merging that PR — the neutrality
   hooks' standard pre-commit run already treats
   `docs/release-notes.md` as warn-only for issue/PR numbers (see
   "TheForge stays project-neutral" below), but the denylist check
   still runs in its normal failing mode and needs a clean pass.
4. Once that PR is merged, copy its exact section text as the tag
   message.
5. Ask the owner by name for explicit authorization to push this
   specific tag, naming the exact tag and version, and record their
   quoted reply (on the ticket or thread where the release was
   requested) before proceeding. There is no standing approval: this
   is required every time, not just once up front.
6. `git tag -a vX.Y.Z -F <notes-file>` then `git push origin vX.Y.Z`.
7. Add the tag to the post-merge review run's archive comment.

**A real constraint:** `git push <tag>` can be denied outright by the
harness's own permission classifier (as a "Modify Shared Resources"
action) — not a network or git-proxy limit, but a harness-level safety
gate. No GitHub tooling available to an agent session offers an
equivalent of a generic git-refs-creation call that could push an
annotated tag as a fallback (`create_branch` only creates
`refs/heads/*`; there is no `create_tag`/`create_ref`). Don't assume the
push in step 6 will succeed: try it, and if it's denied, stop and hand
the exact tag name, the chosen version, and the notes file's contents to
the owner rather than guessing around the denial. This is an
environment-specific blocker (`environment.permissions`-style guidance
covers this kind of case) that may need a session-configuration change,
not a procedure change, to unblock agent tagging as the owner intends.
Open gap: once the owner identifies a workaround or a configuration
fix, this section is updated to describe it.

This repository's tags won't carry over to the planned fresh public
repository; this procedure has to keep working in whichever repository
consumers end up syncing from, once that migration happens.

### Contributing to `template/`

- **Forge-owned rule files** live under `template/.forge/`, one topic per file, one sentence per line.
  One sentence per line is what lets a consuming project's `copier update` conflict on the sentence that changed rather than a re-wrapped paragraph.
  `template/scripts/check_one_sentence_per_line.py` checks it, and runs here as a pre-commit hook too.
- **Skills** live under `template/.agents/skills/<name>/SKILL.md`.
  A skill adapted from upstream keeps its one-line source note under the frontmatter and its row in `template/.agents/skills/THIRD_PARTY.md`.
- **Project-owned seeds** (`CLAUDE.md`, `CONTEXT.md`, `docs/principles.md`, `docs/decisions-log.md`, `docs/agents/lessons.md`, `docs/agents/operational-constants.md`, `docs/forge-overrides.md`, the threat model and requirements skeletons) are listed under `_skip_if_exists` in `copier.yml`, so `copier update` never overwrites a project's own content.
  A new project-owned file joins that list in the same change.
- **Templating.** Only files that need a Copier variable carry the `.jinja` suffix.
  Inside a `.jinja` file, a literal `{{` or `{%` must be wrapped in `{% raw %}`.
  Standing tracker numbers are filled after generation, so text refers to them through the computed `*_ref` variables in `copier.yml`, never a literal number.
- **Check a change renders.** Run `scripts/check-render.sh` before every push that touches `template/` or `copier.yml`: it renders the template, stages the render as a project's first commit would, then runs the render's own guard-script tests and pre-commit hooks against it, so a broken guard is caught here instead of shipped to every consumer who runs `copier copy` next. For a quick manual look at the rendered output instead, `copier copy --trust --defaults --skip-tasks --vcs-ref HEAD . /tmp/forge-render-check` from a clean checkout and read what you changed (`--vcs-ref HEAD`, not the default, or Copier checks out the latest tag over the working tree once one exists).
- **Credit third-party material** in `THIRD_PARTY.md` and `template/.agents/skills/THIRD_PARTY.md`, with its licence text alongside, in the same change that adds it.

### Back-porting from a consuming project (upstream first)

A refinement a consuming project makes to a forge-owned file should come back here first, then flow out to every project through `forge-sync`.
Before opening the change:

1. rewrite it generically, as if no consuming project existed;
2. put that project's own terms in your local denylist file and run the hooks (`pre-commit run --all-files`);
3. run the fresh-reviewer read-through above;
4. remove the matching entry from the consuming project's `docs/forge-overrides.md` once the upstream change has synced back.

### Running the contamination scan

```bash
pre-commit install --install-hooks                                   # once per clone
pre-commit run --all-files                                           # before every push
```

This defaults to scanning against this repository's own committed `.theforge-denylist`, so no setup is needed for the owner's standing terms. A maintainer back-porting from a real project instead sets `THEFORGE_DENYLIST_FILE` to a session-local file naming that project's own terms, kept outside every repository: this unions with the committed default for that scan, so the owner's standing terms stay checked alongside that project's own, during the one run that most needs both (ADR-0005 amended from "replaces" to "unions").

```bash
export THEFORGE_DENYLIST_FILE=/path/outside/the/repo/denylist.txt   # one term per line
pre-commit run --all-files
```

With none of the three denylist locations present, the denylist hook fails rather than skipping when the checkout is this private repository itself (`forger88/TheForgeStaging`, detected by its git remote), since this repository always commits its own: a missing committed file here means it was deleted or renamed, not that nothing needs checking. A checkout with no reason to carry this repository's denylist at all — a contributor working on the public `TheForge` template, say — still skips with a note and exits cleanly. An explicit but wrong `THEFORGE_DENYLIST_FILE` (a typo, a stale path) always fails, in either checkout: it is a misconfiguration, never "nothing to check."
