# Engineering principles

The standing rules every design and code change in this project has to respect, each with why it holds and what enforces it.
A principle is wider than one decision (that's an ADR in `docs/adr/`) and isn't vocabulary (that's `CONTEXT.md`).
Strength markers follow the **Never** / **Default** convention in `.forge/never-default.md`.
A new, reworded or removed principle lands only once the owner has approved its exact wording; `.agents/skills/domain-modeling/` maintains this file, in the shape its `PRINCIPLES-FORMAT.md` sets.

## Efficient with model costs (Default)

**Principle:** Coordinators and agents are to be efficient with respect to model costs, by using (and being instructed to use) models that are no more capable than necessary for the task, and by ensuring instructions and skills are no more verbose than necessary to ensure clear direction.

**Why:** model capability and instruction length are both paid for on every run; a more capable model than the task needs, or a longer instruction than clear direction needs, multiplies that cost across every thread and every reader.

**Enforcement:** Review only (`code-review` Standards axis); `.forge/model-tiers.md` is the mapping from task to the least capable sufficient tier.

## Don't repeat yourself (Default)

**Principle:** each piece of knowledge (a rule, a check, a mapping, a piece of fixed prompt or UI text) lives in one place. Before writing logic a sibling already has, reuse or extend the helper, seam or module that holds it; a deliberate second copy states its reason at the site.

For a design that splits into multiple build slices (`.agents/skills/feature-pipeline/` stage 5), the design doc names one shared idiom for each cross-cutting concern every slice will need — a key-building rule, a "is this still current" check, where a shared-key query is defined, how a write is made, and similarly — before the slices are cut. A slice does not invent its own answer to a concern the doc left open; the doc is amended first.

**Why:** a copy drifts. A fix or a security hardening made to one copy misses the others, and adding one more case means finding every copy. A multi-slice design is exactly as exposed to this as any other code: a cross-cutting concern left unnamed at design time gets solved separately by each slice, one copy per slice instead of one.

**Enforcement:** Review only (`code-review` Standards axis, and `self-review`'s reuse-over-recreation check); for a multi-slice design specifically, stage 5's detailed-design check and the stage 8 architecture pass both check that each cross-cutting concern has exactly one named idiom across the doc's slices.

## Fail closed on an existence check across an authorization boundary (Default)

**Principle:** when whether a resource exists and whether the caller may see it are both in question, the response to an unauthorized or unauthenticated caller does not reveal which: a resource that genuinely doesn't exist and one that exists but is inaccessible to this caller get the same client-facing status and body. The distinction stays in server-side logs or an audit trail, never in what the caller gets back.

**Why:** letting a caller tell "doesn't exist" apart from "exists but you can't see it" is an information leak across the authorization boundary itself — it confirms the existence of something the caller was never meant to learn about, independent of whatever the resource actually is.

**Enforcement:** Review only (`code-review` Standards axis); a test for this asserts full response-body equality between the missing-resource and inaccessible-resource cases, not matching status codes alone, since two routes can share a status while differing in body.

## Doc and skill text tracks the script it describes (Default)

**Principle:** when a change alters what a script, tool or check does — its behavior, its scope, the cases it covers, what it reports — every doc or skill passage that describes that behavior is checked against the new behavior and updated in the same change. A change whose own purpose is fixing stale doc or skill text is not exempt from this: it re-checks its own new wording against the script's actual behavior before merging, not just the gap it set out to close.

**Why:** a doc or skill passage describing a script's behavior is only ever as accurate as it was when written; nothing re-checks it against the script's current behavior except the change that next touches that behavior. Left to chance, that gap compounds: a change aimed at fixing one drifted passage is not itself exempt from introducing the next one.

**Enforcement:** Review only (`code-review` Standards axis) — a reviewer reads the script's current behavior and checks it against every doc or skill passage the diff touches, or that describes the script at all, not only the wording the change intended to fix.

## No principles recorded yet — run the stage 0 grilling interview to seed this file.

Stage 0 (project inception, `.forge/feature-pipeline.md`) runs `grill-me` with the owner over six topics: what in the domain will change underneath the project, which external systems it trusts and how far, which frameworks it builds on rather than writes, size and complexity budgets, test philosophy, and security posture.
The principles above are forge-seeded and do not count as stage 0 having run.
Each principle whose exact wording the owner approves replaces this heading, one H2 per principle:

```md
## <Principle name> (<Never|Default>)

**Principle:** <one or two sentences, stated as what holds now>

**Why:** <the domain fact or the cost already paid; ADR and issue numbers as pointers>

**Enforcement:** <a guard test, by path · a lint or pre-commit rule · "Review only (`code-review` Standards axis)">
```

Until this heading is gone, `feature-pipeline` treats stage 0 as not yet run.
