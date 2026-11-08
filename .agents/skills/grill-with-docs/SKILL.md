---
name: grill-with-docs
description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go.
disable-model-invocation: true
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/engineering/grill-with-docs/SKILL.md @ 447ca70872 (2026-08-15), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

`grilling` and `domain-modeling` live only under `.agents/skills/`, so neither may be available through the harness's skill listing: read `.agents/skills/grilling/SKILL.md` and `.agents/skills/domain-modeling/SKILL.md` directly and follow both.

This is not the feature pipeline's grilling skill.
Stage 0 and stage 2 interviews run `grill-me` (`.agents/skills/grill-me/SKILL.md`), because `.forge/feature-pipeline.md` routes ADRs to stage 3, not to grilling.
Use this skill only for an interview outside the pipeline where the owner wants ADRs and glossary entries drafted as the conversation goes.
