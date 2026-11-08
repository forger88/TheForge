---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/productivity/handoff/SKILL.md @ d28dfdc39b (2026-08-15), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS - not the current workspace.

Include a "suggested skills" section in the document, naming which skills the next agent should use — via the Skill tool for one it lists, or by reading `.agents/skills/<name>/SKILL.md` directly for a repo-local one that isn't (see `.forge/agent-skills-and-reference.md`, "Finding a skill").

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
