---
name: claude-handoff
description: Hand the current conversation off to a fresh background agent that picks up the work immediately.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/in-progress/claude-handoff/SKILL.md @ 321658273c (2026-08-19), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

Write a handoff summary of the current conversation so a fresh agent can continue the work. Instead of saving it, launch a background agent seeded with the summary as its prompt: `claude --bg --name "<descriptive name>" "<handoff summary>"`. It starts in the current working directory and returns immediately; the user manages it with `claude agents`.

Always pass `-n`/`--name` with a descriptive name (e.g. `--name "Fix login bug"`); it sets the display name shown in the job list, the list of sessions to resume, and the terminal title.

Include a "suggested skills" section in the summary, naming which skills the next agent should use — via the Skill tool for one it lists, or by reading `.agents/skills/<name>/SKILL.md` directly for a repo-local one that isn't (see `.forge/agent-skills-and-reference.md`, "Finding a skill").

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information, since the summary becomes the agent's prompt.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the summary accordingly.
