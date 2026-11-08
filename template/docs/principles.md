# Engineering principles

The standing rules every design and code change in this project has to respect, each with why it holds and what enforces it.
A principle is wider than one decision (that's an ADR in `docs/adr/`) and isn't vocabulary (that's `CONTEXT.md`).
Strength markers follow the **Never** / **Default** convention in `.forge/never-default.md`.
A new, reworded or removed principle lands only once the owner has approved its exact wording; `.agents/skills/domain-modeling/` maintains this file, in the shape its `PRINCIPLES-FORMAT.md` sets.

## Efficient with model costs (Default)

**Principle:** Coordinators and agents are to be efficient with respect to model costs, by using (and being instructed to use) models that are no more capable than necessary for the task, and by ensuring instructions and skills are no more verbose than necessary to ensure clear direction.

**Why:** model capability and instruction length are both paid for on every run; a more capable model than the task needs, or a longer instruction than clear direction needs, multiplies that cost across every thread and every reader.

**Enforcement:** Review only (`code-review` Standards axis); `.forge/model-tiers.md` is the mapping from task to the least capable sufficient tier.

## No principles recorded yet — run the stage 0 grilling interview to seed this file.

Stage 0 (project inception, `.forge/feature-pipeline.md`) runs `grill-me` with the owner over six topics: what in the domain will change underneath the project, which external systems it trusts and how far, which frameworks it builds on rather than writes, size and complexity budgets, test philosophy, and security posture.
The principle above is forge-seeded and does not count as stage 0 having run.
Each principle whose exact wording the owner approves replaces this heading, one H2 per principle:

```md
## <Principle name> (<Never|Default>)

**Principle:** <one or two sentences, stated as what holds now>

**Why:** <the domain fact or the cost already paid; ADR and issue numbers as pointers>

**Enforcement:** <a guard test, by path · a lint or pre-commit rule · "Review only (`code-review` Standards axis)">
```

Until this heading is gone, `feature-pipeline` treats stage 0 as not yet run.
