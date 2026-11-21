---
name: security-docs
description: "Produce, update, or reconcile a repo's STRIDE threat model and the rest of its security docs, in three modes: bootstrap (a repo with no threat model yet), delta (the security section of a design or a design-exit pass), and reconcile (bring an existing threat model current against the repo's head). Runs on design-tier. Use whenever a design, a design-exit Structure guidance, a release gate, or a post-merge security finding needs a security-doc write, rather than hand-writing one each time. Also governs the form of any other edit to a file under docs/security/."
disable-model-invocation: true
---

# Security docs

> Before any other work, check the model actually serving this turn against what `.forge/model-tiers.md` maps this tier to.
> In Claude Code on the web, for example, call `get_session` with no id and read `session_context.model` and `external_metadata.last_served_model`; another harness has its own equivalent of "what model is actually running this turn."
> If it is below the mapped model, do no other work on this ticket or stage: report to the coordinator and the owner that this thread must be restarted on the right model, and stop there.
> A thread cannot switch its own model, which is why the gate stops and reports rather than continuing or switching itself.
> Running on a model above the mapped one is not a problem: note it in one line and proceed.

This applies to all three modes (`.forge/orchestration.md`, "Tier gate"), with no exception ("Tier", below).

A repo's security docs (a STRIDE threat model, plus any companion docs: an authorization policy, a data-leakage-paths doc, upload or incident runbooks) are a contract like its architecture description.
They describe the attack surface and controls **as they are now, plus the open gaps**, not an evolution story (`.forge/docs-describe-current-state.md`).
Left alone, they drift silently while the code moves; this skill makes the writing happen on purpose, so a design thread, a design-exit pass, a release gate and a post-merge reviewer's filed gap all produce the same shape of edit.

Cite code by symbol (function, class, route, message type), never by line number, which drifts on the next unrelated commit.

## Structure and size discipline

The threat model's register sections (§2 to §5 and §7 to §10) are tables: one row per item (asset, actor, entry point, boundary, threat, gap, risk), scanned a row at a time.
A cell holds a few dense clauses of fact and citation, never an unbroken narrative paragraph, and doesn't repeat a fact an adjacent column already carries.
A row that doesn't fit this size is usually several items: split it into sibling rows under a shared ID (`T7a`, `T7b`, ...) rather than widening one field.
A single threat that genuinely carries more controls than a cell holds keeps its row as the summary, plus a `### T7 detail` heading under the table with one bullet per control, each a short clause citing its symbol and guard test.
No mechanical check measures this; the review gate's Standards axis enforces it, and a guard is added only if cell bloat recurs despite this rule.

## Per-repo values

Fill these in once per repo; every mode reads them from here rather than naming a repo's files.
Record a change to this table in `docs/forge-overrides.md`, since this file is forge-owned.

| Value | This repo |
|---|---|
| Threat model file | `docs/security/threat-model.md` |
| Framework | STRIDE |
| Other security docs | none yet (add each companion doc here as it is created, for example an authorization policy or `docs/security/runbooks/`) |
| Requirements spec, if any (for `FR-`/`NF-` citations) | `docs/requirements/requirements-specification.md` |
| Architecture description, if any (trust-boundary peers, deployment shape) | none yet |
| "Last reconciled" line format | `**Last reconciled against \`main\` @ \`<sha>\`** (<date>).` near the top, directly under the scope and method section |
| "Delta folded" line format | `**Delta folded for <feature> @ \`<sha>\`** (<date>, <PR>) — <one-line scope note>.` appended next to the "Last reconciled" line, one per feature fold still newer than the last full reconcile; dropped once the next full reconcile supersedes it |
| Known-gaps table columns (§8) | `Gap | Severity | Threat | Tracking` |
| Accepted-risks table columns (§10) | `Risk | Threat | Why accepted | Owner's recorded words | Tracking` |
| Severity vocabulary | Must (reachable today by an authenticated user or an on-path attacker), Should (degrades cleanly or needs a precondition), Could (defensive depth) |

The generated `docs/security/threat-model.md` is a skeleton with the section shape below and no content; bootstrap mode fills it in, and every later mode depends on that.

## Mode: bootstrap

Produce a first threat model for a repo whose threat model file is still the skeleton, following the skeleton's section shape:

1. **Scope and method**: the framework (STRIDE); what's in scope (the codebase's own components: services, clients, container images, CI, and owned-but-external dependencies the repo consumes); and what's a trust-boundary peer rather than a subject (anything the repo calls but doesn't own: an identity provider, a payment or model provider, the deployment platform, an upstream repo).
2. **Assets**: what the system holds that's worth protecting, in the repo's `CONTEXT.md` vocabulary.
3. **Actors**: who can reach the system, and at what privilege.
4. **Entry points**: every way in, regenerated from the code's own declarations (route decorators, a command registry, a message-handler table, a public-paths allowlist), not enumerated from memory, so the next reconcile can re-derive it mechanically.
5. **Trust boundaries and data flows**: where a security decision changes (process, network, privilege boundary), and the paths data takes across them.
6. **Security assumptions**: what's assumed true of a boundary peer (for example "the identity provider is deployed and verifies tokens"), so the threat register builds on it rather than re-litigating it per threat.
7. **STRIDE by boundary (threat register)**: one entry per threat, grouped by trust boundary and STRIDE category, naming the entry points and assets it touches, the controls in place (cited by symbol), and the residual risk — each field held to "Structure and size discipline" above.
8. **Known gaps**: a table (the column shape above) of every gap a control doesn't close, each with a tracking issue, never a TODO.
9. **Residual risk summary**: one row per major threat, with its residual risk level and the state of its controls.
10. **Accepted risks**: every risk the owner decided to accept rather than close, with the owner's recorded words (SDLC-107); an undecided risk belongs in §8.
11. **Keeping this document current**: the reconcile instructions (this skill's reconcile mode, plus any repo-specific regeneration commands for the entry-point table).

Land it as one ticketed docs PR (`Requirements: none (internal)`), with the "Last reconciled" line set to the commit it was written against.

## Mode: delta

Write the security content for one caller per invocation, since each writes to a different place:

- **A stage 3 design comment** (`.forge/feature-pipeline.md`): a short section on new attack surface, trust boundaries crossed, data newly stored or exposed, and the STRIDE threats the design raises, each with its proposed control.
  It is a forecast; the threat model file isn't touched at this stage.
- **A stage 5 design doc's per-slice "Threat-model delta" section**: the same content as concrete proposed rows for the register (§7) and known-gaps table (§8) (new rows, or edits to rows this slice changes), plus any runbook the control needs.
  A feature introducing a new incident type always gets a runbook under `docs/security/runbooks/` (SDLC-085).
  Write the literal row text the terminal-slice merge (`.forge/feature-pipeline.md`, stage 7) will fold in, not a paraphrase.
- **A design-exit Structure guidance's "Security" part** (`implement-with-merge` step 0a, for a ticket outside the pipeline): read the threat model and any other security doc the change touches, then write the threats it raises, by STRIDE category; the controls the build must keep or add, each naming the guard test that must go red with the control removed; and the security-doc delta the build PR must carry (which doc, which section, what text).
  If none apply, write "Security: none" with a one-line reason: a true negative is a recorded judgement, not silence.

Always name the actual symbols the new code will touch or add, not placeholders, and don't invent a control the design doesn't call for just to fill the section.
Write proposed rows to "Structure and size discipline" above, split before they are handed off to be folded in.

### Folding deltas at the terminal-slice merge

Still delta mode, run once more at the point `.forge/feature-pipeline.md` stage 7 names: when a feature's terminal slice merges and every other terminal slice already has, `implement-with-merge` step 3 calls it to fold the whole feature's Threat-model deltas into the live threat model file, in that small follow-up PR, never in a slice's own PR diff.

1. Collect every slice's Threat-model delta section from the design doc; no slice's PR touched the live file, so all are still unfolded.
2. Where two deltas touch the same register entry or known-gap row, merge them into one entry reflecting the feature's final state, never two rows for one threat.
3. Insert the merged rows into the register and known-gaps table, and land any runbook a delta named.
4. Leave the "Last reconciled" line alone, and add or update a "Delta folded" line next to it in the per-repo format (feature name, the merge commit just produced, today's date, the follow-up PR, and a one-line scope note): "Last reconciled" records only a full reconcile or bootstrap, and a fold is a narrower claim.
5. Land it in the same follow-up PR as `implement-with-merge` step 3's status-line and checklist-tick bookkeeping, never as a direct write to `main`; this differs from delta mode's design-exit path, which always lands inside its own ticket's PR.

## Mode: reconcile

Bring an existing threat model (and any other named security doc) up to date against the repo's current head.
Two callers use it: a release gate that found the threat model stale against the previous release tag, and a ticket filed for a doc gap a post-merge security-axis finding raised; the reviewer that found the gap never fixes it itself.

1. Re-walk every section against the code on the current default branch, not against what the document says, regenerating the entry-point and attack-surface table from the code's declarations as bootstrap step 4 does.
   Tighten or split any row that has drifted into a narrative paragraph, per "Structure and size discipline" above; this is also how a threat model already written in narrative rows converges on this shape, keeping its own column shape.
2. Re-check every known-gaps row against its tracking issue: delete each row whose issue is closed and whose fix has actually landed (verify it; a closed issue alone is not proof), and add rows for anything newly found and untracked.
3. Re-check that every register entry's control citations still name real, current symbols; update or remove one that moved or no longer exists.
4. Re-check that every §10 accepted risk still describes the system as built; one whose shape changed needs the owner's decision again, so move it back to §8 with a `needs-decision` ticket.
5. Set the "Last reconciled" line to the commit reconciled against, and remove every "Delta folded" line it supersedes.
6. Land it as its own ticketed docs PR (`Requirements: none (internal)`, citing the release ticket or the gap ticket that asked for it) and get it merged.
   This mode edits only the security docs, never code: a code weakness found along the way is a separate finding for whoever runs the review this reconcile serves.

## Tier

All three modes run on **design-tier** (`.forge/orchestration.md`, "Capability tiers": security reasoning is a design-tier judgement, like design and architecture passes); `.forge/model-tiers.md` gives the model.
Never run any mode on build-tier or lower: a threat model written without real security reasoning is decoration, not a contract anyone can rely on.
