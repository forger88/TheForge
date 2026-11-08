# ADR-0007: Unify the documentation build into one manifest, with diagram rendering dispatched by fence class

**Status:** accepted

## Context

The reference implementation this feature ports into TheForge's stage 0 has two separate, non-unified render paths that grew independently:

- `docs/tools/build_docs.py` + `docs/tools/document-build.json`: a manifest-driven PDF build. Every manifest entry's `output` must end in `.pdf` (`_validate_inputs`'s suffix check); there is no way to ask the same manifest for a PPTX.
- A second, hardcoded-to-one-file script that builds exactly one deck source document to `.pptx`, duplicating `build_docs.py`'s Pandoc-AST-then-D2-render shape rather than extending it.

Both paths already share the same diagram-rendering idea (`docs/tools/render_d2.py`'s Pandoc-AST walk, swapping a `d2`-classed CodeBlock for a rendered Image), but neither generalizes it: `render_d2.py` only ever looks for the `d2` class, and nothing in either path asks what format a block is in before deciding whether to render it.

TheForge's stage-2 grill for this feature's tracking issue (recorded on the issue, 2026-10-29) decided TheForge should ship one unified manifest (grill decision 2) and add Mermaid as a second diagram tool, with C4 diagrams going through Mermaid's native syntax rather than a dedicated C4 tool (grill decision 3). Both of those land most cleanly if the duplication is fixed first: a second diagram tool is easy to add to one dispatch point, hard to add to two independently-maintained render paths.

## Decision

One manifest (`docs/tools/document-build.json`) drives every document's build. Each `documents[]` entry carries `outputs: list[str]`, each element `"pdf"` or `"pptx"`, instead of a single forced suffix — so a document that needs both formats (as the stakeholder deck document effectively does today, split across two scripts) is one entry, not two scripts.

Diagram rendering is selected by the fenced code block's language class (`d2`, `mermaid`), never by which output format the document is being built to. `docs/tools/render_diagrams.py` replaces `render_d2.py`: it keeps the same Pandoc-AST walk, but holds a `{class_name: renderer}` table instead of a single hardcoded `d2` check. `document_build.py` builds the Pandoc AST once per document and renders every requested output from that one AST — diagrams are rendered once per document, not once per output format.

This is why the two changes compose: unifying the manifest (this ADR) is what lets Mermaid (a second entry in the renderer table) land with no change to `document_build.py`'s build loop at all.

## Alternatives rejected

- **Keep two scripts, and just add a Mermaid-aware copy of `render_d2.py` for the second script to call too.** Rejected — doubles the exact duplication the stage-2 grill flagged as the thing to fix, and leaves every future diagram tool needing to be wired into two places instead of one.
- **A dedicated C4-diagramming tool (e.g. a Structurizr-shaped tool) alongside D2 and Mermaid.** Rejected per grill decision 3 — Mermaid's native `C4Context`/`C4Container` syntax already covers C4 diagrams, and a consuming project's own existing diagram convention already established the precedent of treating C4 as "a diagram Mermaid draws," not a separate tool.
- **Render diagrams once per output format instead of once per document.** Rejected — would re-run (and re-pay the cost of) every diagram render for each additional output format a document requests, for no benefit: the rendered image is identical regardless of whether the document becomes a PDF or a PPTX.

## Consequences

- Adding a third diagram tool later is one new entry in `render_diagrams.py`'s renderer table, not a change to `document_build.py` or the manifest schema.
- `document-build.json`'s `documents[]` schema is a breaking change versus the reference implementation's own `{"source", "output"}` shape if it, or any other already-adopted consumer, ever adopts this template's build-pipeline files wholesale — that migration, if it happens, is its own ticket; this ADR does not retrofit any existing consumer's own pipeline.
- `document-build.json` is a project-owned seed (`copier.yml`'s `_skip_if_exists`), since its `documents[]` list is inherently project-specific; `docs/design/doc-build-setup.md` §"Module map" records which other shipped files are forge-synced instead.
