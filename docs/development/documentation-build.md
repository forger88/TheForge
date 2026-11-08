# Building documents and diagrams

This project renders some of its Markdown sources to `.pdf` and/or `.pptx`, with D2 and Mermaid diagrams drawn inline, via `docs/tools/document_build.py`. `docs/tools/document-build.json` is the manifest: which documents build, and to which output formats. Built files live under `docs/_build/` (gitignored) and are never committed.

## Toolchain

Install, alongside the project's own setup (`pip install pre-commit==4.3.0 && pre-commit install --install-hooks`):

- `pandoc` (pinned version recorded in `docs/tools/document-build.json`'s `toolchain.pandoc.version`)
- `d2` (`toolchain.d2.version`)
- `mmdc` (`@mermaid-js/mermaid-cli`, only if any document source contains a `mermaid` fenced block; `toolchain.mmdc.version`)
- `weasyprint`, plus `pip install -r docs/tools/requirements.txt` into whatever Python runs `document_build.py` (only needed if any document requests `"pdf"`)
- A font family your system's `fc-match` can resolve, matching `toolchain.font`

`scripts/install-doc-build-tools.sh`, run from the repository root, is the one-command way to get a fresh sandbox ready: it installs the pinned `pandoc` and `d2` by checksum-verified extraction into `~/.local/bin` (no root needed) and `weasyprint` into a venv.
It needs Linux x86_64 with `dpkg-deb`, and refuses to run if its pandoc or d2 version disagrees with the manifest.
It prints the `PATH` line to export.

Check everything is in place without building anything:

```bash
python3 docs/tools/document_build.py --check
```

## Running a build

```bash
python3 docs/tools/document_build.py                    # full build: screenshots (if configured) + every document
python3 docs/tools/document_build.py --reuse-screenshots # skip recapturing; reuse the committed screenshots as-is
```

Outputs land under `docs/_build/pdfs/<stem>.pdf` and `docs/_build/pptx/<stem>.pptx`.

## CI

`.github/workflows/documentation.yml` runs the same build in CI, `workflow_dispatch`-only: nobody dispatches it except on request (`.forge/ci-and-checks.md`, "Don't manually trigger CI runs"). It installs its own pinned pandoc/d2/weasyprint, cross-checked against this manifest's `toolchain` versions, then uploads the built PDFs and PPTX files as separate artifacts.

## Adding a document to the manifest (agent-facing)

Add one entry to `document-build.json`'s `documents` list:

```json
{"source": "docs/some-doc.md", "outputs": ["pdf", "pptx"]}
```

- `outputs` is any non-empty subset of `["pdf", "pptx"]`.
- If any document in the manifest requests `"pdf"`, the manifest also needs a top-level `"style"` key naming a CSS stylesheet path.
- A document's D2 (` ```d2 `) and Mermaid (` ```mermaid `) fenced code blocks are rendered to images automatically; nothing else in the manifest entry names them.
- An optional `"diagram_overrides": {"d2": {...}}` key changes that document's D2 rendering for every output it requests, once per document, never per output (a document is rendered to Pandoc AST once; every output format it requests is emitted from that same render). Allowed keys: `layout` (`"dagre"` or `"elk"`), `theme` (integer), `pad` (integer), `scale` (number). Each key present replaces the matching default CLI flag; an unlisted key keeps its default. There's no font-size key: D2's CLI has no global font-size flag (font size is a per-shape style attribute in the D2 source itself, not something a manifest can override).

  ```json
  {"source": "docs/some-doc.md", "outputs": ["pptx"], "diagram_overrides": {"d2": {"layout": "elk", "scale": 1.5}}}
  ```

- `python3 docs/tools/document_build.py --check` validates the new entry (source exists, outputs are valid, toolchain is present, any `diagram_overrides.d2` keys and values are in the allowlist) before a real build.

## Screenshots

If this project's manifest has a `screenshots` block, `document_build.py` either reuses the committed screenshots (`--reuse-screenshots`) or recaptures them by running the manifest's own `command` against a locally-started stack (`services`), writing into `SCREENSHOTS_DIR` (an environment variable `document_build.py` sets for the capture command to read). Screenshots are committed to the repository, unlike the PDF/PPTX outputs; nothing mechanically checks they're current, so keep them current the way the rest of this project's review process does.
