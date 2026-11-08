# docs/principles.md Format

## Structure

```md
# Engineering principles

The standing rules every design and code change in this project has to respect,
each with why it holds and what enforces it. A principle is wider than one
decision (that's an ADR in `docs/adr/`) and isn't vocabulary (that's
`CONTEXT.md`). Strength markers follow the **Never** / **Default**
convention in `.forge/never-default.md`. A new principle lands only once the repo owner has confirmed it;
`.agents/skills/domain-modeling/` maintains this file, in the shape this file
sets.

## <Principle name> (<Never|Default>)

**Principle:** <one or two sentences, stated as what holds now>

**Why:** <the domain fact or the cost already paid; ADR and issue numbers as pointers>

**Enforcement:** <one of: a guard test, by path · a lint or pre-commit rule, by hook or config key · "Review only (`code-review` Standards axis)">

<optional: sub-rules or worked detail the principle needs, kept short>
```

## Rules

- **One principle per H2, with a strength marker.** Cite principles by name, never by number.
- **Principle / Why / Enforcement, every time.** If there is no guard, Enforcement says "Review only".
- **Wider than a decision.** If it constrains one choice, it's an ADR. If it constrains every future choice in an area, it's a principle.
- **Not vocabulary.** Terms go in `CONTEXT.md`. A principle may use glossary terms but never defines one.
- **Owner-approved wording only.** An agent proposes a principle's exact wording to the owner and writes it into the file, verbatim, only after the owner approves that wording; a rewording or removal needs the same approval (SDLC-068).
- **Current state.** No history. Cite ADRs and issues as pointers.
