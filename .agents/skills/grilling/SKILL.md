---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/productivity/grilling/SKILL.md @ 85f83d3fde (2026-08-20), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

Facts to find always include whether this repo already has an existing decision on the topic: check `docs/adr/` (and, for vocabulary, `CONTEXT.md`; for engineering principles, `docs/principles.md`) before the first round, read-only. This is not to draft or amend anything, just so a frontier question doesn't silently assume something the repo already decided and rejected or accepted. If an existing ADR or principle bears directly on the topic, surface that as its own frontier question (e.g. "this already decided X for reason Y: still the right call, or does something now outweigh that reason?") rather than treating the topic as unexplored ground.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
