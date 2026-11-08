---
name: grill-me
description: A relentless interview to sharpen a plan or design.
disable-model-invocation: true
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/productivity/grill-me/SKILL.md @ fcf0071560 (2026-08-15), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

If this interview is stage 2 of a feature's pipeline (`.forge/feature-pipeline.md`, grilling for use cases on a tracker issue), read `.agents/skills/feature-pipeline/SKILL.md` and follow job (a), starting the pipeline, first, so the issue carries the nine-item checklist before the interview begins.
`feature-pipeline` lives only under `.agents/skills/`, so it may not be available through the harness's skill listing: read it directly; there's no tool invocation for it.

If this interview is stage 0 (project inception: `.forge/feature-pipeline.md`, stage 0), read `.agents/skills/feature-pipeline/SKILL.md`'s "Stage 0" section instead of job (a).
After `grilling` returns, write each principle whose exact wording the owner approved into `docs/principles.md` per `domain-modeling`, and don't write any they didn't.
Stage 0 also settles the project's real tools for the generic guards (`.forge/code-shape-rules.md`) and its setup, test and lint commands; record each choice the owner makes in `docs/forge-overrides.md` or the project-owned section of `CLAUDE.md`, whichever the choice belongs in.

`grilling` lives only under `.agents/skills/`, so it may not be available through the harness's skill listing: read `.agents/skills/grilling/SKILL.md` directly and follow it; there's no tool invocation for it.

`grilling` itself stops once the user confirms shared understanding: it does not update the tracker issue, and it does not apply `domain-modeling`'s glossary discipline.
So if this was stage 2 of a feature's pipeline, after `grilling` returns, do two things in order.
First, write the use cases and product constraints it surfaced onto the feature issue (stage 2's own requirement in `.forge/feature-pipeline.md`; a new comment, or a section in the issue body, whichever this repo's tracker conventions use).
Second, resolve any term the interview settled, or that collided with an existing one, into the `CONTEXT.md` glossary right there, as stage 2 requires.
This is the glossary half of `domain-modeling`, not an ADR, so it happens now, not deferred to stage 3.

Only once both the issue write and any needed glossary update have actually succeeded, tick stage 2 (`- [x] 2. Grilling for use cases`) in the same or next edit.
Job (a) only checked stages already done *before* this interview ran, so nothing else marks this one complete.
Ticking it before the use cases are recorded and the glossary reconciled would leave the checklist claiming a stage done that the issue and `CONTEXT.md` have no evidence of.

In that same edit, swap the issue's state label for the next stage: remove `needs-grilling` if it carries one, and apply `ready-for-feature-design` (`docs/agents/triage-labels.md`'s "`ready-for-feature-design`"), since grilling finishing moves the feature into stage 3's high-level design, not straight to a build.
Leaving `needs-grilling` on past this point reads as grilling still outstanding, when it is done; leaving the issue with no ready label at all leaves the coordinator with nothing to route to a stage 3 design thread.
This whole label swap is scoped to the feature-pipeline branch above; a generic, non-pipeline `grilling` interview changes no labels.
