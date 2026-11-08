---
name: security-docs
description: "Produce, update, or reconcile a repo's STRIDE threat model and the rest of its security docs, in three modes: bootstrap (a repo with no threat model yet), delta (the security section of a design or a design-exit pass), and reconcile (bring an existing threat model current against the repo's head). Runs on design-tier. Use whenever a design, a design-exit Structure guidance, a release gate, or a post-merge security finding needs a security-doc write, rather than hand-writing one each time."
disable-model-invocation: true
---

# Security docs

> Before any other work, check the model actually serving this turn against what `.forge/model-tiers.md` maps this tier to.
> In Claude Code on the web, for example, call `get_session` with no id and read `session_context.model` and `external_metadata.last_served_model`; another harness has its own equivalent of "what model is actually running this turn."
> If it is below the mapped model, do no other work on this ticket or stage: report to the coordinator and the owner that this thread must be restarted on the right model, and stop there.
> A thread cannot switch its own model, which is why the gate stops and reports rather than continuing or switching itself.
> Running on a model above the mapped one is not a problem: note it in one line and proceed.

This applies to all three modes below (`.forge/orchestration.md`, "Tier gate"); none of them is an exception, since a threat model written below design-tier is decoration, not a contract anyone can rely on ("Tier", below).

A repo's security docs (a STRIDE threat model, plus whatever companion docs it keeps: an authorization policy, a data-leakage-paths doc, upload or incident runbooks) are a contract like its architecture description.
They describe the system's attack surface and controls **as they are now, plus the open gaps**, not an evolution story (`.forge/docs-describe-current-state.md`).
Nothing in a repo's process writes to them unless something makes that writing happen on purpose; left alone, they drift silently while the code moves.
This skill is that something, in three modes, so a design thread, a design-exit pass, a release gate, or a post-merge reviewer's filed gap all produce the same shape of edit instead of improvising one each time.

Cite code by symbol (function, class, route, message type), never by line number: line numbers drift on the next unrelated commit and make a diff's reviewer re-derive what changed.

## Per-repo values

Fill these in once per repo; every mode below reads from this table instead of naming a repo's files directly.
Record a change to this table in `docs/forge-overrides.md`, since this file is forge-owned.

| Value | This repo |
|---|---|
| Threat model file | `docs/security/threat-model.md` |
| Framework | STRIDE |
| Other security docs | none yet (add each companion doc here as it is created, for example an authorization policy or `docs/security/runbooks/`) |
| Requirements spec, if any (for `FR-`/`NF-` citations) | `docs/requirements/requirements-specification.md` |
| Architecture description, if any (trust-boundary peers, deployment shape) | none yet |
| "Last reconciled" line format | `**Last reconciled against \`main\` @ \`<sha>\`** (<date>).` near the top, directly under the scope and method section |
| Known-gaps table columns (§8) | `Gap | Severity | Threat | Tracking` |
| Accepted-risks table columns (§10) | `Risk | Threat | Why accepted | Owner's recorded words | Tracking` |
| Severity vocabulary | Must (reachable today by an authenticated user or an on-path attacker), Should (degrades cleanly or needs a precondition), Could (defensive depth) |

The generated `docs/security/threat-model.md` is a skeleton with the section shape below and no content; bootstrap mode fills it in, and that act is what makes every later mode meaningful on this repo.

## Mode: bootstrap

Produce a first threat model for a repo whose threat model file is still the skeleton.
Follow the skeleton's section shape, which isn't repo-specific; only its content is:

1. **Scope and method**: name the framework (STRIDE), what's in scope (the codebase's own components: services, clients, container images, CI, and any owned-but-external dependencies the repo consumes) and what's a trust-boundary peer rather than a subject (anything the repo calls but doesn't own: an identity provider, a payment or model provider, the deployment platform, an upstream repo it depends on).
2. **Assets**: what the system holds that's worth protecting, in the repo's own vocabulary (its `CONTEXT.md` glossary).
3. **Actors**: who can reach the system, and at what privilege.
4. **Entry points**: every way in.
   Regenerate this from the code's own declarations (route decorators, a command registry, a message-handler table, a public-paths allowlist), not by hand-enumerating from memory, so it's mechanically re-derivable at the next reconcile.
5. **Trust boundaries and data flows**: where a security decision actually changes (process boundary, network boundary, privilege boundary), and the paths data takes across those boundaries.
6. **Security assumptions**: what's assumed true about a boundary peer (for example "the identity provider is deployed and verifies tokens") so the threat register can build on it instead of re-litigating it per threat.
7. **STRIDE by boundary (threat register)**: one entry per threat, grouped by trust boundary and STRIDE category, each naming the entry points and assets it touches, the control or controls in place (cited by symbol), and the residual risk.
8. **Known gaps**: a table (the column shape above) of every gap a control doesn't close, each with a tracking issue, never a TODO with no issue.
9. **Residual risk summary**: one row per major threat, its current residual risk level, and the state of its controls.
10. **Accepted risks**: every risk the owner has decided to accept rather than close, with the owner's recorded words (SDLC-107); a risk nobody has decided on belongs in §8, not here.
11. **Keeping this document current**: the reconcile instructions (this skill's reconcile mode, plus any repo-specific regeneration commands for the entry-point table).

Land it as a single ticketed docs PR (`Requirements: none (internal)`) with the "Last reconciled" line set to the commit it was written against.

## Mode: delta

Write the security content for one of two callers, a feature-pipeline design step or a design-exit pass on a ticket outside the pipeline, never both in the same invocation, since they write into different places:

- **A stage 3 design comment** (`.forge/feature-pipeline.md`): a short section covering new attack surface, trust boundaries crossed, data newly stored or exposed, and the STRIDE threats this design raises, each with its proposed control.
  This is a forecast, not yet a diff against the threat model file; the file isn't touched at this stage.
- **A stage 5 design doc's per-slice "Threat-model delta" section**: the same content as stage 3's, now as concrete proposed rows for the threat model's register (§7) and known-gaps table (§8) (new rows, or edits to existing ones this slice changes), plus any runbook the control needs.
  A feature that introduces a new incident type always gets a runbook under `docs/security/runbooks/` (SDLC-085).
  This is what the terminal-slice merge (`.forge/feature-pipeline.md`, stage 7) later folds into the threat model file itself, so write it as the literal row text to fold in, not a paraphrase of it.
- **A design-exit Structure guidance's "Security" part** (`implement-with-merge` step 0a, for a ticket outside the pipeline): read the threat model file and any other security doc the ticket's change touches, then write three things.
  First, the threats the change raises, by STRIDE category.
  Second, the controls the build must keep or add, each naming the guard test that must go red with that control removed.
  Third, the security-doc delta the build PR must carry (which doc, which section, what the new or changed text says).
  If none apply, write "Security: none" with a one-line reason: a true negative is still a recorded judgement, not silence.

In every case, name the actual symbols the new code will touch or add (not yet-unwritten placeholder names), and don't invent a control the design doesn't actually call for just to fill the section.

### Folding deltas at the terminal-slice merge

This is still delta mode, run once more at the point `.forge/feature-pipeline.md` stage 7 names.
When a feature's terminal slice merges and every other terminal slice is already merged, `implement-with-merge` step 3 calls this to fold every slice's Threat-model delta (the whole feature's, not just the terminal slice's own) into the live threat model file, inside that same small follow-up PR, never inside the slice's own PR diff:

1. Collect every slice's Threat-model delta section from the design doc.
   Each slice wrote its own at stage 5, and a non-terminal slice's PR never touched the live file with it, so every one of them is still unfolded until this point.
2. Where two slices' deltas touch the same threat-register entry or the same known-gap row, merge them into one entry reflecting the feature's final state; never append both as separate rows for the same threat.
3. Insert the merged rows into the threat model file's register and known-gaps table, and land any runbook a delta named.
4. Update the "Last reconciled" line to the merge commit just produced.
5. Land this in the same small follow-up PR as the status-line and checklist-tick bookkeeping `implement-with-merge` step 3 already makes at this point, never a direct write to `main` and never delta mode's design-exit path (which always lands inside its own ticket's PR, never at a feature-pipeline merge point).

## Mode: reconcile

Bring an existing threat model (and any other named security doc) up to date against the repo's current head.
Two callers use this: a release gate that found the threat model stale against the previous release tag, and a ticket a post-merge security-axis finding filed for a doc gap.
The reviewer that found the gap never fixes it itself; this mode is where the fix actually happens.

1. Re-walk every section against the code on the repo's current default branch, not against what the document already says.
   Regenerate the entry-point and attack-surface table mechanically from the code's own declarations, the same way bootstrap's step 4 does.
2. Re-check every row in the known-gaps table against its tracking issue's current state.
   Delete rows whose issue is closed and whose underlying gap is actually fixed (verify the fix landed; don't take the issue's closed status alone as proof), and add rows for anything newly found during this pass that isn't already tracked.
3. Re-check that every threat-register entry's control citations still point at real, current symbols; update or remove a citation that moved or no longer exists.
4. Re-check every accepted risk in §10 still describes the system as built; a risk whose shape changed needs the owner's decision again, so move it back to §8 with a `needs-decision` ticket.
5. Update the "Last reconciled" line to the commit this reconcile was run against.
6. Land it as its own ticketed docs PR (`Requirements: none (internal)`; cite whichever ticket asked for the reconcile, the release ticket or the post-merge-filed gap ticket) and get it merged.
   This mode never edits code, only the security docs it's reconciling; a code weakness found along the way is a separate finding for whoever's running the review this reconcile serves, not something this mode fixes itself.

## Tier

All three modes run on **design-tier** (`.forge/orchestration.md`, "Capability tiers": security reasoning is explicitly a design-tier judgement, the same reason design and architecture passes are).
`.forge/model-tiers.md` says which model that resolves to on this harness.
Never run any mode on build-tier or lower: a threat model written by a tier that isn't doing the actual security reasoning is decoration, not a contract anyone can rely on.
