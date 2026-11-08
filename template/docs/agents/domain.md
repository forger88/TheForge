# Domain docs

How the engineering skills consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context, and you read each one relevant to the topic.
- **`docs/adr/`**: ADRs that touch the area you're about to work in.
  In a multi-context repo, also check `src/<context>/docs/adr/` for context-scoped decisions.
- **`docs/principles.md`**: the project's standing engineering principles.
  A proposal that breaks one is flagged the same way as an ADR conflict (below).

If any of these files are still the generated skeletons, or don't exist, **proceed silently**.
Don't flag their absence and don't suggest creating them up front: `/domain-modeling` (reached through `/grill-me` at stages 0 and 2, `/grill-with-docs`, and `/improve-codebase-architecture`) fills them in as terms, principles and decisions actually get resolved.

## File structure

Single-context repo (this repo, as generated):

```
/
├── CONTEXT.md
├── docs/principles.md
├── docs/adr/
│   ├── 0001-<slug>.md
│   └── 0002-<slug>.md
└── src/
```

`CONTEXT.md` is a pure glossary in the shape `.agents/skills/domain-modeling/CONTEXT-FORMAT.md` sets: a term, a one- or two-sentence definition of what the term is, and an `_Avoid_:` line where a synonym needs ruling out.
No file or module paths, issue history, status notes, configuration keys or retired terms: those belong in the architecture docs, an ADR, or the design docs.
A definition may end with a pointer such as "(ADR-0004)".

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`.
Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap.
Either way, **surface it explicitly rather than silently noting it**, in your reply, the PR body, or an issue comment, the same way an ADR conflict is surfaced below:

> _Your glossary defines "cancellation" as X, but this needs Y; reusing the term would collide._
> _"Grace period" isn't in the glossary yet; flagging for `/domain-modeling` rather than inventing it silently._

## Flag ADR and principle conflicts

If your output contradicts an existing ADR or principle, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (single write path for invoices), but worth reopening because…_
