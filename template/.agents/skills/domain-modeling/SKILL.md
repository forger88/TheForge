---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a CONTEXT.md or docs/principles.md, or recording or editing an ADR.
---

<!-- Source: mattpocock/skills (https://github.com/mattpocock/skills), skills/engineering/domain-modeling/SKILL.md @ 321658273c (2026-08-19), MIT. See ../THIRD_PARTY.md. Modified for TheForge. -->

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline: challenging terms, inventing edge-case scenarios, and writing the glossary, the decisions and the project's principles down the moment they crystallise. (Merely *reading* `CONTEXT.md` for vocabulary is not this skill: that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

## File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   ├── principles.md
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── CONTEXT-MAP.md
├── docs/
│   ├── principles.md                 ← system-wide principles
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files lazily: only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed. The generated `docs/principles.md` starts as a skeleton whose heading says no principles are recorded yet; replace that heading with the first principle whose exact wording the owner approves (normally at stage 0, project inception: `.forge/feature-pipeline.md`).

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account': do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up: capture them as they happen. Use the format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Record a principle once the owner approves its wording

Three things get written down, and each has one home: a **term** goes in `CONTEXT.md`, a **single hard-to-reverse decision** goes in an ADR, and a **standing rule every future design in an area must respect** goes in `docs/principles.md`. When the conversation surfaces the third kind, name it to the user as a candidate principle and show them its exact wording (statement, Why and Enforcement) and ask them to approve that wording; never write one whose wording they haven't approved. Once they approve it, add it right there, verbatim, in the format in [PRINCIPLES-FORMAT.md](./PRINCIPLES-FORMAT.md), with its Why and its Enforcement (a guard test, a lint rule, or "Review only"). If an existing principle already covers it, propose the reworded entry instead of a near-duplicate; a reworded principle needs the same approval of its exact new wording. `CONTEXT.md` stays a glossary: no principle text goes there.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).
