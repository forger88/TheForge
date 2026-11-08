# HTML Report Format

The architectural review is rendered as a single self-contained HTML file in the OS temp directory. Mermaid comes from a CDN. Styling is a small inline utility stylesheet (no external CSS framework — see why below). Mermaid handles graph-shaped diagrams reliably; hand-built divs and inline SVG handle the more editorial visuals (mass diagrams, cross-sections). Mix the two: don't lean on Mermaid for everything, it'll start to look generic.

**No Tailwind CDN.** `https://cdn.tailwindcss.com` prints a "cdn.tailwindcss.com should not be used in production" warning in the browser console every time a report is opened — noisy for something that's a static, one-shot file, never served in production. Use the fixed utility stylesheet in the scaffold below instead: it covers every class name this document uses. If a new report needs a layout the sheet doesn't cover, add the specific rule to the stylesheet (same place, same naming style) rather than reaching for an arbitrary Tailwind-looking class name that has no definition here.

## Scaffold

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Architecture review for {{repo name}}</title>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      /* Fixed utility set covering every class name used in this document
         and in reports generated from it. Add to this list rather than
         inventing an undefined class — there's no CDN giving life to
         arbitrary Tailwind-looking names any more. */
      .max-w-5xl { max-width: 64rem; }
      .mx-auto { margin-left: auto; margin-right: auto; }
      .px-6 { padding-left: 1.5rem; padding-right: 1.5rem; }
      .py-10 { padding-top: 2.5rem; padding-bottom: 2.5rem; }
      .py-12 { padding-top: 3rem; padding-bottom: 3rem; }
      .p-4 { padding: 1rem; }
      .p-6 { padding: 1.5rem; }
      .pl-5 { padding-left: 1.25rem; }
      .mb-1 { margin-bottom: 0.25rem; }
      .gap-4 { gap: 1rem; }
      .gap-6 { gap: 1.5rem; }
      .flex { display: flex; }
      .grid { display: grid; }
      .grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .items-center { align-items: center; }
      .justify-between { justify-content: space-between; }
      .rounded-lg { border-radius: 0.5rem; }
      .border { border-width: 1px; border-style: solid; border-color: #e2e8f0; }
      .border-slate-200 { border-color: #e2e8f0; }
      .border-l-4 { border-left-width: 4px; border-left-style: solid; }
      .shadow { box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1); }
      .h-12 { height: 3rem; }
      .list-disc { list-style-type: disc; }
      .font-sans { font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
      .font-serif { font-family: ui-serif, Georgia, "Times New Roman", serif; }
      .font-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
      .font-semibold { font-weight: 600; }
      .text-2xl { font-size: 1.5rem; line-height: 2rem; }
      .text-lg { font-size: 1.125rem; line-height: 1.75rem; }
      .text-sm { font-size: 0.875rem; line-height: 1.25rem; }
      .text-xs { font-size: 0.75rem; line-height: 1rem; }
      .uppercase { text-transform: uppercase; }
      .tracking-wider { letter-spacing: 0.05em; }
      .bg-slate-900 { background-color: #0f172a; }
      .bg-stone-50 { background-color: #fafaf9; }
      .bg-white { background-color: #fff; }
      .text-red-700 { color: #b91c1c; }
      .text-slate-50 { color: #f8fafc; }
      .text-slate-500 { color: #64748b; }
      .text-slate-600 { color: rgb(71 85 105); }
      .text-slate-900 { color: #0f172a; }
      .space-y-1 > * + * { margin-top: 0.25rem; }
      .space-y-2 > * + * { margin-top: 0.5rem; }
      .space-y-3 > * + * { margin-top: 0.75rem; }
      .space-y-8 > * + * { margin-top: 2rem; }
      .space-y-10 > * + * { margin-top: 2.5rem; }
      .space-y-12 > * + * { margin-top: 3rem; }

      /* small custom layer for things the utility set doesn't cover cleanly:
         dashed seam lines, hand-drawn-feeling arrow heads, etc. */
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

## Header

Repo name, date, and a compact legend: solid box = module, dashed line = seam, red arrow = leakage, thick dark box = deep module. No introduction paragraph. Straight into the candidates.

## Candidate card

The diagrams carry the weight. Prose is sparse, plain, and uses the glossary terms (from the `/codebase-design` skill) without ceremony.

Each candidate is one `<article>`:

- **Title**: short, names the deepening (e.g. "Collapse the Order intake pipeline").
- **Badge row**: recommendation strength (`Strong` = emerald, `Worth exploring` = amber, `Speculative` = slate), plus a tag for the dependency category (`in-process`, `local-substitutable`, `ports & adapters`, `mock`).
- **Files**: monospaced list, `font-mono text-sm`.
- **Before / After diagram**: the centrepiece. Two columns, side by side. See patterns below.
- **Problem**: one sentence. What hurts.
- **Solution**: one sentence. What changes.
- **Wins**: bullets, ≤6 words each. e.g. "Tests hit one interface", "Pricing logic stops leaking", "Delete 4 shallow wrappers".
- **ADR callout** (if applicable): one line in an amber-tinted box.

No paragraphs of explanation. If the diagram needs a paragraph to be understood, redraw the diagram.

## Diagram patterns

Pick the pattern that fits the candidate. Mix them. Don't make every diagram look the same. Variety is part of the point.

### Mermaid graph (the workhorse for dependencies / call flow)

Use a Mermaid `flowchart` or `graph` when the point is "X calls Y calls Z, and look at the mess." Wrap it in a bordered card so it doesn't feel parachuted in. Style with classDef to colour leakage edges red and the deep module dark. Sequence diagrams work well for "before: 6 round-trips; after: 1."

```html
<div class="rounded-lg border border-slate-200 bg-white p-4">
  <pre class="mermaid">
    flowchart LR
      A[OrderHandler] --> B[OrderValidator]
      B --> C[OrderRepo]
      C -.leak.-> D[PricingClient]
      classDef leak stroke:#dc2626,stroke-width:2px;
      class C,D leak
  </pre>
</div>
```

### Hand-built boxes-and-arrows (when Mermaid's layout fights you)

Modules as `<div>`s with borders and labels. Arrows as inline SVG `<line>` or `<path>` elements positioned absolutely over a relative container. Reach for this when you want the "after" diagram to feel like one thick-bordered deep module with greyed-out internals, since Mermaid won't render that with the right weight.

### Cross-section (good for layered shallowness)

Stack horizontal bands (`h-12 border-l-4`) to show layers a call passes through. Before: 6 thin layers each doing nothing. After: 1 thick band labelled with the consolidated responsibility.

### Mass diagram (good for "interface as wide as implementation")

Two rectangles per module: one for interface surface area, one for implementation. Before: interface rectangle is nearly as tall as the implementation rectangle (shallow). After: interface rectangle is short, implementation rectangle is tall (deep).

### Call-graph collapse

Before: a tree of function calls rendered as nested boxes. After: the same tree collapsed into one box, with the now-internal calls shown faded inside it.

## Style guidance

- Lean editorial, not corporate-dashboard. Generous whitespace. Serif optional for headings (`font-serif` works well with stone/slate).
- Colour sparingly: one accent (emerald or indigo) plus red for leakage and amber for warnings.
- Keep diagrams ~320px tall so before/after sits comfortably side by side without scrolling.
- Use `text-xs uppercase tracking-wider` for module labels inside diagrams, so they read as schematic, not as UI.
- The only external resource is the Mermaid ESM import; all styling is the inline utility stylesheet above. The report is otherwise static: no app code, no interactivity beyond Mermaid's own rendering.

## Top recommendation section

One larger card. Candidate name, one sentence on why, anchor link to its card. That's it.

## Tone

Plain English, concise, but the architectural nouns and verbs come straight from the `/codebase-design` skill. Concision is not an excuse to drift.

**Use exactly:** module, interface, implementation, depth, deep, shallow, seam, adapter, leverage, locality.

**Never substitute:** component, service, unit (for module) · API, signature (for interface) · boundary (for seam) · layer, wrapper (for module, when you mean module).

**Phrasings that fit the style:**

- "Order intake module is shallow: interface nearly matches the implementation."
- "Pricing leaks across the seam."
- "Deepen: one interface, one place to test."
- "Two adapters justify the seam: HTTP in prod, in-memory in tests."

**Wins bullets** name the gain in glossary terms: *"locality: bugs concentrate in one module"*, *"leverage: one interface, N call sites"*, *"interface shrinks; implementation absorbs the wrappers"*. Don't write *"easier to maintain"* or *"cleaner code"*, because those terms aren't in the glossary and don't earn their place.

No hedging, no throat-clearing, no "it's worth noting that…". If a sentence could be a bullet, make it a bullet. If a bullet could be cut, cut it. If a term isn't in the `/codebase-design` glossary, reach for one that is before inventing a new one.
