# Forge sync upstream candidates

**Status:** implemented, reconciled against main @ 87f216b.
**Tracking issue:** "How does policy flow from a consuming project back into TheForge?". That issue holds the use cases (stage 2) and the high-level design (stage 3). This repository has no requirements specification, so that issue is the requirement record.
**Decision record:** none. No decision here is hard to reverse.

This document is written for the agent that builds the slice. The slice section is its contract.

## Goal

A consuming project's local edit to a forge-owned file is sometimes worth sending back to TheForge. The project marks it in `docs/forge-overrides.md` with `**Upstream candidate:** yes`. Nothing reads that mark today, so it reaches TheForge only if someone happens to remember it.

This design makes `forge-sync` put every open candidate to the project's owner as a decision each time a sync runs. The owner can propose it upstream as a ticket, decline it, or defer it.

## Out of scope

- A schedule or routine of its own. Candidates surface only when a sync runs (owner decision, stage 2).
- Building the back-port itself. That follows this repository's "Back-porting from a consuming project (upstream first)" procedure once the forge owner starts the proposed ticket.
- How the public TheForge repository receives changes. That is the issue "Publish TheForge as a fresh repository with no history".

## Invariants

1. **I1. A mark is an offer.** Skill text, card wording and the proposed ticket say "offer" or "propose". The forge owner decides whether a proposal is built.
2. **I2. Every open candidate is surfaced at every sync until it is answered.** An open candidate is an offered part of an entry whose `Upstream candidate` value begins with "yes", that carries neither a `proposed` nor a `declined` marker, and whose entry doesn't already say the change has come back upstream.
3. **I3. An answered candidate is not asked about again.** "Propose" and "Decline" each write a marker. "Not yet" writes nothing, so the candidate stays open.
4. **I4. The agent posts to the upstream tracker only when it is verified safe.** It posts only when `_src_path` is a hosted repository whose visibility is private and on which the session can create issues. In every other case, including when the check can't answer, the ticket is drafted for the owner to file. This combines stage 3's two conditions: a public repository, and one the session has no access to.
5. **I5. No repository name is hardcoded.** The upstream repository is always `_src_path` from `.copier-answers.yml`.
6. **I6. The skill text is the definition.** The four marker values and the open-candidate test live in the `forge-sync` skill, which every consuming project receives on its next sync. The seed's entry shape repeats them only for projects generated afterwards, since `docs/forge-overrides.md` is project-owned and a sync never touches it.

## Module map

| Module | New or touched | Its one job | Named hook |
|---|---|---|---|
| `template/.agents/skills/forge-sync/SKILL.md` | touched | The one way a project syncs | "Before you start" step 4 (collect); "Review and merge" (surface and record) |
| `template/docs/forge-overrides.md` | touched (project-owned seed; reaches new projects only) | The local-edit log a project keeps | The entry shape's `Upstream candidate` line |
| `docs/security/threat-model.md` (this repository's own, project-owned) | touched | TheForge's own threat model | One new row under the Sync boundary |

This repository's root `.agents/skills/forge-sync/SKILL.md` is a render of the template copy and is currently byte-identical to it, so it receives the same edit. This repository's root `docs/forge-overrides.md` is project-owned, so its own entry-shape line is hand-edited to match in the same PR.

No new module, so there is no build-versus-buy line. A parser for the overrides file was considered and rejected. The agent already reads the whole file at step 4, entries are free-form prose that may offer only part of their change, which needs judgement to split, and a script would fail the deletion test: removing it would leave the agent's own read doing the same job.

## Data model

An offered part's `Upstream candidate` text takes one of four values. The first is open; the other three are not.

| Value | Meaning | Written by |
|---|---|---|
| `yes, rewritten generically` (or free-form text beginning "yes") | Open: offered, not yet answered | The PR that logs the override |
| `yes — proposed as <ticket link or "drafted in <sync PR link>">, <date>` | Proposed upstream; not asked again | `forge-sync`, on "Propose" |
| `no, project-specific` | Never a candidate | The PR that logs the override |
| `no — declined by owner, <date>` | Declined; not asked again | `forge-sync`, on "Decline" |

For an entry that offers only part of its change, the marker replaces the offered part's wording only, and the rest of the value stays as written.
The removal rule is the seed's own, unchanged ("Remove an entry once the change has gone upstream and come back through `forge-sync`, or once the local edit is reverted.").

No configuration keys.

## Slice 1: surface upstream candidates during forge-sync

**Purpose.** Make every open candidate a decision for the project's owner at each sync, and record the answer.

**Behaviour.**

1. *Collect.* At "Before you start" step 4, while reading `docs/forge-overrides.md`, list each open candidate (I2), one per offered part. An entry whose text says its change has already come back upstream isn't a candidate. List it in the PR body for removal under the existing removal rule.
2. *Surface.* Right after the sync PR opens, ask the owner once per open candidate, with a decision card where the harness offers one, otherwise one comment on the sync PR addressed to the owner (the same fallback as this skill's "Hold SDLC wording changes for the owner" step). The question is "Offer `<file>`'s `<part>` upstream to TheForge?", linking the entry at the sync branch. A project with many open candidates gets that many questions at once; the owner can answer "Not yet" to any of them. Options:
   - **Propose this as a back-port patch.** Under I4, either file a ticket on `_src_path`'s repository or draft it in the sync PR body. Either way it holds the entry, the project's diff of that file against the upstream render, the project's `_commit`, and a link to the sync PR. Then write the `proposed` marker.
   - **Decline.** Write the `declined` marker.
   - **Not yet.** Change nothing.
3. *Record.* Marker edits are commits on the sync PR. The PR body gains an "Upstream candidates" list: each question and the owner's answer in the approval-record form (`.forge/process-and-evidence.md`), or "none". Add "Upstream candidates" to "Review and merge"'s list of PR-body contents. The sync PR does not wait on the questions: one still unanswered at merge is recorded as "Not yet".
4. *Entry shape.* The skill text states the four values and the open-candidate test (I6). `template/docs/forge-overrides.md`'s `Upstream candidate` line lists the same four values.

**Interface and error modes.**

- I4's check: for a GitHub `_src_path`, `gh repo view <owner/repo> --json visibility,viewerPermission` (or the harness's equivalent). It posts only on `PRIVATE` visibility with write permission. Any other answer, an error, a local path or a non-hosted URL means draft.
- Filing fails (auth, network, rate limit): draft the ticket in the sync PR body instead, and write the `proposed` marker pointing at that draft.
- `docs/forge-overrides.md` is missing or has no `Upstream candidate` lines: no questions, and "Upstream candidates: none".

**Seam.** The rendered skill and seed text. It's agent instruction text, so there is no executable seam.

**Guard test.** None mechanical: the behaviour is agent judgement over free-form prose. It is review-only, through the full review gate's Spec axis against this section, the same as other instruction-only slices.

**Threat-model delta.** One new row in this repository's `docs/security/threat-model.md`, numbered after the current highest (T31 today):

| ID | Boundary | STRIDE | Threat | Entry points / assets | Controls (by symbol) | Guard test | Residual risk |
|---|---|---|---|---|---|---|---|
| next | B5 | Information disclosure | A proposed back-port ticket carries a consuming project's names, paths or diff into the upstream tracker | The proposed ticket; the upstream issue tracker | I4: posts only to a verified private repository the session can write to, otherwise drafts for the owner; the back-port PR built later from the ticket is rewritten generically and never quotes the ticket's diff verbatim (this repository's neutrality rule) | None: procedural | Low for a private upstream the owner controls; Medium otherwise |

**UI.** None. It uses the harness's own decision mechanism, or a PR comment.

**File scope.** The three files in the module map, the root render of the skill, and this repository's root `docs/forge-overrides.md` entry-shape line.

**Blocking edges.** None.

**Requirement IDs.** None (internal).

## Test matrix

| Case | Expected |
|---|---|
| No entry is marked "yes" | No questions; PR body says "Upstream candidates: none" |
| One open candidate, owner proposes, upstream verified private and writable | Ticket filed; `proposed` marker on the sync PR; not asked at the next sync |
| One open candidate, owner proposes, upstream public or check inconclusive | Ticket drafted in the sync PR, never posted; `proposed` marker points at the draft |
| One open candidate, owner declines | `declined` marker; not asked at the next sync |
| One open candidate, owner says not yet, or the question is unanswered at merge | No edit; asked again at the next sync |
| An entry that offers part of its change | One question for the offered part; the marker replaces only that part's wording |
| An entry that says its change has already come back upstream | No question; listed for removal |
| Harness has no decision cards | One PR comment per candidate, addressed to the owner |

## Open items for the implementer

- Re-read the "Review and merge" list and the "Hold SDLC wording changes" fallback wording at build time, and match them.
- One sentence per line in both touched template files.
- `scripts/check-render.sh` and `pre-commit run --all-files` must pass.
