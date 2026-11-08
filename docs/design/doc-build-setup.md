# Design: a stage-0 document/diagram build offer (`doc-build-setup`)

**Status:** implemented, reconciled against main @ c456a08.
**Tracking issue:** "Give TheForge stage 0 a document/diagram rendering pipeline setup offer." Stage-3 design comments (architecture, security section, the owner's approved wording) live on the issue; this document is the stage-5 detail that constrains implementation.

## Invariants every slice keeps

- A project's `docs/tools/document-build.json` is the single source of truth for which documents build, and to which output formats. No second, hardcoded-to-one-file build path exists alongside it (ADR-0007).
- Diagram rendering is selected by a fenced code block's language class, never by the document's target output format. Adding a diagram tool never requires a change to the build-loop module.
- Build artifacts (`.pdf`, `.pptx`) are never committed; `.gitignore` covers `docs/_build/` and every manifest-declared output path. Only source documents and (when a project opts in) captured screenshots are committed.
- The build only ever runs against content that already passed the project's standing review gate — a doc or diagram source is never treated as untrusted/external input, because it reached the manifest the same way any other source file reaches `main`.
- The offer itself is asked at most once per project at stage 0, and a decline is recorded plainly rather than silently dropped (mirrors `impeccable`'s existing stage-0 offer).

## Module map

| Module | New? | Responsibility | Named hook |
|---|---|---|---|
| `docs/tools/document_build.py` | new | Toolchain/version checks, screenshot staging, per-document Pandoc round-trip, emits every output format a document's manifest entry requests; binds each diagram renderer to its manifest-pinned toolchain command and rejects a document whose fenced blocks need a toolchain entry the manifest doesn't have. | `_render_document(document, manifest, root, env) -> list[Path]` |
| `docs/tools/render_diagrams.py` | new | Pandoc-AST walk; replaces a CodeBlock with a rendered Image, dispatching on the block's language class. | `render_diagram_blocks(ast, output_dir, renderers) -> dict` |
| `docs/tools/build_errors.py` | new | The one `BuildError` class both modules above raise and `document_build.main`'s top-level handler catches — kept in its own module since `document_build.py` already imports from `render_diagrams.py`, and a second, independent `BuildError` class there escaped that handler uncaught. Also `ChromiumNotConfiguredError(BuildError)` — the one `BuildError` subtype `main`'s per-document loop catches specially to skip just that document rather than abort the whole build (design-exit resolution — see build-vs-buy). | n/a — exception classes |
| `docs/tools/mermaid-render-config.json` | new | `mmdc -c` config forcing `htmlLabels: false`; without it `mmdc` emits flowchart labels as HTML inside an SVG `<foreignObject>`, which the resvg-based rasterizer `render_svg_to_png` uses never renders, so labels come out blank. | n/a — data, not code |
| `docs/tools/document-build.json` | new (project-owned seed) | The manifest: toolchain pins, optional screenshot config, `documents: [{source, outputs}]`. | n/a — data, not code |
| `docs/tools/requirements.txt` | new | Pinned Python deps for the renderer side (`weasyprint`, `vl_convert-python`, `fonttools`). | n/a |
| `.github/workflows/documentation.yml` | new | `workflow_dispatch`-only CI entrypoint; installs the pinned toolchain and runs `document_build.py`. No `.jinja` suffix: unlike the seed files above, it needs no Copier variable, so it stays plain per "Contributing to `template/`". | n/a — no logic of its own |
| `template/.agents/skills/doc-build-setup/SKILL.md` | new | The stage-0 offer: ask once, scaffold the files above plus the guide doc, append one step to `scripts/local-full-suite.sh`. | the skill's own "run now / skip" decision point |
| `template/docs/development/documentation-build.md` (seeded per-project as `docs/development/documentation-build.md`) | new (project-owned seed) | Toolchain setup instructions, the manifest format, and the agent-facing "how do I add a document to the manifest" note (grill decision 8). | n/a |
| `template/.forge/feature-pipeline.md.jinja` | touched | Stage 0's paragraph gains one sentence offering `doc-build-setup`, parallel to the existing `impeccable` sentence. | n/a |
| `copier.yml` | touched | `_skip_if_exists` gains `docs/tools/document-build.json` and `docs/development/documentation-build.md`, protecting them the moment a project's skill run creates them, even though `copier copy` itself never creates them. | n/a |

`document_build.py` is the one caller of `render_diagrams.py`; nothing else in the template calls either module directly, so there is exactly one seam to test each through (their own unit tests) and one seam to test the pair through (an end-to-end fixture manifest + a two-diagram, two-output-format fixture document).

## Data model and configuration keys

`docs/tools/document-build.json` schema (`schema_version: 2` — the reference implementation's own pre-existing manifest shape, if it is ever carried forward unchanged, is `schema_version: 1`; this is a breaking shape change, not an in-place evolution of that version):

```jsonc
{
  "schema_version": 2,
  "repository_root": "../..",
  "style": "docs/styles/pdf.css",            // optional; required only if any document outputs "pdf"
  "toolchain": {
    "pandoc": {"command": "pandoc", "version": "3.11"},
    "d2": {"command": "d2", "version": "0.9.0"},
    "mmdc": {"command": "mmdc", "version": "10.9.0"},   // required only if any document contains a `mermaid` block; its Chromium comes from the CHROMIUM_EXECUTABLE_PATH env var, not the manifest (see build-vs-buy below)
    "weasyprint": {"command": "weasyprint", "version": "70.0"},
    "font": "DejaVu Sans"
  },
  "reuse_screenshots_by_default": false,       // grill decision 9 — project's own choice, no TheForge-wide default imposed
  "screenshots": { /* optional — omitted entirely for a project with no screenshot-bearing documents */ },
  "documents": [
    {"source": "docs/architecture/overview.md", "outputs": ["pdf"]},
    {"source": "docs/presentations/stakeholder-deck.md", "outputs": ["pptx"]}
  ]
}
```

No new Copier *question* is added for this feature (matching `impeccable`'s own precedent — a stage-0 offer is a skill decision, not a generation-time prompt). `reuse_screenshots_by_default` lives in the manifest itself, not in `.copier-answers.yml`, because it is a build-tool setting a project can revisit at any time, not a one-time generation choice.

## Build-versus-buy

| Concern | Choice | Alternative rejected |
|---|---|---|
| Markdown parsing / AST transform | Pandoc (already the reference implementation's choice) | A hand-rolled Markdown parser — far more code for a well-solved problem |
| Declarative diagrams (D2) | D2 CLI, ported renderer | N/A — carried forward unchanged from the reference implementation |
| Diagrams-as-code, including C4 | Mermaid CLI (`mmdc`) | A dedicated C4 tool (rejected per grill decision 3 / ADR-0007) |
| HTML→PDF | WeasyPrint (already the reference implementation's choice) | A headless-browser PDF export — needs a browser dependency the D2/font fix below exists specifically to avoid |
| SVG→PNG rasterization, D2 font resolution | `vl_convert` + `fonttools` (ported verbatim from the reference implementation) | Re-deriving the embedded-font-resolution fix from scratch — it is hard-won (D2's invented per-diagram font-family names don't match `resvg`'s fontdb without it) and project-neutral as written, so porting it is cheaper and safer than rewriting it |
| Mermaid rendering substrate | `mmdc` against the CI/dev image's already-installed Chromium, via `--puppeteerConfigFile`'s `executablePath` (owner decision, 2026-11-01 — reaffirming the original call; see the next row for where the path comes from) | Letting `mmdc` fetch its own Chromium — doubles the image's browser footprint when one (already installed for Playwright-based e2e jobs) is usually already present; also the owner's explicit instruction is to fail loudly rather than degrade to this, so it is never a runtime fallback either (next row) |
| Where that Chromium's path comes from | A single environment variable, `CHROMIUM_EXECUTABLE_PATH`, resolved once per build by whatever already installs a browser in that environment for its own purposes (a CI image's Dockerfile, the devcontainer's Dockerfile, a cloud sandbox's setup script) — never re-resolved by `render_mermaid` itself at render time. `render_mermaid` only reads the value its caller hands it (a `chromium_executable` parameter), consistent with how `command` is already injected rather than hardcoded. A project with no browser-automation install of its own simply never sets it. | Discovering the path automatically at *build* time by shelling into Node to call a browser-automation library's own `executablePath()` — rejected: that cache path is revision-pinned with no fixed location, so discovery needs a cross-language subprocess call into whatever directory happens to hold the project's own install, which varies per project and fails unpredictably for a project with none. Recording the path in the manifest instead of an env var was also considered and rejected: an env var needs no manifest-schema change and matches how the value is actually produced (an environment-setup step, not a per-project authored fact) |
| What happens when that Chromium isn't configured | **Fail loudly and skip only the affected document** — owner's explicit instruction (2026-11-01): *"if chromium isn't set up, fail loudly and skip the affected document. The repo owner can then fix it themselves."* `render_mermaid` raises a new `ChromiumNotConfiguredError(BuildError)` when `chromium_executable` is falsy or doesn't exist on disk, naming what's wrong. `document_build.main`'s per-document loop catches only this error, logs `error: skipping {document}: {error}` to stderr, and continues to the next document; every other `BuildError` keeps aborting the whole build as it does today. `main` still returns non-zero if any document was skipped this way, even though it built everything it could — "loudly" means the overall build reports failure, not a quiet partial success | Silently falling back to `mmdc` fetching its own Chromium when the env var is unset or invalid — this is the specific behaviour the owner's instruction above rules out; silently skipping the document with no logged error was also rejected on the same grounds |

## Slice 1 — `render_diagrams.py`: fence-class-dispatched diagram rendering

**Purpose:** generalize `render_d2.py`'s Pandoc-AST transform so it dispatches on a CodeBlock's language class instead of hardcoding `d2`, and add the Mermaid renderer as the second table entry.

**Module and interface:**

```python
DiagramRenderer = Callable[[str, Path], None]  # (source_text, destination_png) -> None; raises BuildError

def render_diagram_blocks(
    document: dict[str, Any],
    output_dir: Path,
    renderers: dict[str, DiagramRenderer],
) -> dict[str, Any]: ...
```

Behaviour: walks the Pandoc JSON AST exactly as `render_d2_blocks` does today; for a CodeBlock whose classes intersect `renderers.keys()`, calls that class's renderer and replaces the block with an Image (same caption/attribute handling as today); every other CodeBlock passes through unchanged. Unknown classes are not errors — a document may legitimately have a `python` or `bash` fenced block that stays a CodeBlock.

Two renderers ship: `render_d2` (ported from `build_docs.py`'s `render_svg_to_png` + the font-resolution fix, unchanged in substance) and `render_mermaid` (new: `mmdc -i <source>.mmd -o <dest>.svg -c mermaid-render-config.json -p <puppeteer-config>`, then the same `vl_convert` SVG→PNG step D2 already uses — `mmdc`'s own PNG export needs no separate justification to avoid, since the SVG→`vl_convert` path is already proven and reused, not duplicated).

`render_mermaid` takes a `chromium_executable: str | None = None` keyword parameter (parallel to its existing `command` parameter; the renderer never reads the environment itself — see build-vs-buy). When falsy, or when `Path(chromium_executable).is_file()` is false, it raises `ChromiumNotConfiguredError(BuildError)` naming what's wrong, and never invokes `mmdc` at all — no silent fallback to a bundled-Chromium download. When valid, it builds a `-p` config in memory (`{"executablePath": chromium_executable, "args": ["--no-sandbox"]}` — the `--no-sandbox` arg confirmed necessary against a real `mmdc 12.0.0 --help` and an end-to-end render, since Puppeteer's Chromium refuses to launch as root without it), writes it to a temp file beside the `.mmd`/`.svg` temp files already used here (cleaned up in the same `finally` block), and passes it via `-p` alongside the existing `-c mermaid-render-config.json`.

**Seam tested through:** direct unit calls to `render_diagram_blocks` with a synthetic Pandoc AST and a fake renderer table (no real `d2`/`mmdc` binary needed) — proves the dispatch-by-class logic in isolation. A second, slower test calls the two real renderers against a tiny fixture diagram of each kind, gated on the binaries being on `PATH` (matches how `test_render_d2.py` already gates its font-resolution test).

**Guard test:** a test with an *empty* `renderers` table, fed a document containing one `d2` and one `mermaid` block, asserts both blocks survive as plain CodeBlocks (not Images) — this is what must go red if the dispatch table is ever accidentally bypassed (e.g. a future change that special-cases `d2` again instead of going through the table).

**Threat-model delta:** none at this slice — this module only ever runs against already-reviewed source text; it introduces no network access and no new credential.

**UI:** none.

**File scope:** `template/docs/tools/render_diagrams.py.jinja` (identical for every project, so `.jinja` is only needed if a project-specific value is ever templated in — none is known yet, so this may ship as a plain `.py` file; confirmed at implementation time), `template/docs/tools/build_errors.py`, `template/docs/tools/mermaid-render-config.json`, its test file, `template/docs/tools/requirements.txt` additions.

**Blocking edges:** none — this is the first slice.

**Acceptance criteria (this repo carries no FR-/NF- spec; these are the "shall" statements this slice's ticket checks against):**
1. `render_diagram_blocks` shall replace a CodeBlock whose class is a key of the `renderers` argument with a rendered Image, and shall leave every other CodeBlock unchanged.
2. The D2 renderer shall produce output byte-identical in substance to the reference implementation's existing `render_svg_to_png` (same font-resolution behaviour) for an equivalent input diagram.
3. The Mermaid renderer shall render a `C4Context` or `C4Container` Mermaid block without special-casing C4 syntax anywhere in `render_diagrams.py` — C4-ness is entirely inside the Mermaid source text, per grill decision 3.

## Slice 2 — `document_build.py`: the unified manifest-driven build loop

**Purpose:** generalize `build_docs.py` to read the new `outputs: list[str]` manifest shape and emit every requested format from one Pandoc AST per document, folding the reference implementation's separate deck-build script's PPTX path in rather than leaving it a separate script.

**Module and interface:** keeps `build_docs.py`'s existing toolchain-check / screenshot-staging shape (`_check_toolchain`, `_prepare_screenshots`, `ManagedServices`) verbatim — none of that is PDF-specific. `_render_document` changes shape:

```python
def _render_document(
    document: dict[str, Any], manifest: dict[str, Any], root: Path, env: dict[str, str]
) -> list[Path]:
    """Builds the document's Pandoc AST once, renders its diagrams once
    (via render_diagrams.render_diagram_blocks), then emits one output
    file per entry in document["outputs"]. Raises BuildError on any
    toolchain failure or an outputs entry outside {"pdf", "pptx"}."""
```

`outputs == ["pdf"]` reuses today's HTML→WeasyPrint path unchanged; `outputs == ["pptx"]` reuses the reference implementation's separate deck-build script's pandoc-to-pptx invocation — both now live in the one script, keyed off the same already-rendered AST. The deck-build script's deck-specific D2 layout override is now a per-*document* manifest key, `diagram_overrides.d2` (`layout`, `theme`, `pad`, `scale`), applied once per document to every output it requests, never per output format — a pdf/pptx-only split would need rendering twice, which ADR-0007 forbids. Font-size is out: D2's CLI has no global font-size flag, confirmed against the pinned D2 version (this supersedes this slice's original `pptx_diagram_overrides` name and PDF/PPTX-split framing, once the build ticket implemented it).

**Behaviour:** `_validate_inputs` validates each `outputs` entry is `"pdf"` or `"pptx"` (replacing today's single `.suffix.lower() != ".pdf"` check) and that `style` is present in the manifest whenever any document requests `"pdf"`. `_build_renderers` gains an `environment: dict[str, str]` parameter and binds `render_mermaid`'s `chromium_executable` keyword to `environment.get("CHROMIUM_EXECUTABLE_PATH")` — never read from the manifest (design-exit resolution — see build-vs-buy); `_render_document`'s own `env` parameter already carries this straight through to its one `_build_renderers` call site, no new resolution logic needed there.

`main()`'s per-document loop (today, one bare call to `_render_document` per document inside the function's single outer `try`) catches `ChromiumNotConfiguredError` specifically, per document: logs `error: skipping {document['source']}: {error}` to stderr, records that a skip happened, and `continue`s to the next document — every other document still builds. Every other `BuildError` keeps today's behaviour, aborting the whole build immediately via the outer handler; this loop change is scoped to the one failure mode the owner's instruction names, not a general "keep going on any error" change. `main` returns non-zero if *any* document was skipped this way (reusing exit code `2`, which already means "a `BuildError` occurred") — even though every other document built successfully, the overall build still reports failure.

**Seam tested through:** `docs/tools/tests/test_build_docs_cli.py`'s existing pattern — a throwaway fixture manifest + repo root, run end to end against real `pandoc`/`d2`/`weasyprint` (and `mmdc` once a document's source contains a `mermaid` block), asserting the right output files exist with the right magic bytes (`%PDF` / a valid pptx zip signature).

**Guard test:** a document manifest entry with `outputs: ["pdf", "pptx"]` and a test double standing in for `render_diagram_blocks` that counts its own calls — asserts the double is called exactly once per document, not once per requested output. This is the test that must go red if a future change starts re-rendering diagrams per output format, silently reintroducing the duplicated-render cost ADR-0007 exists to avoid.

**Threat-model delta:** `docs/security/threat-model.md` gains one row — *new build-time subprocess surface (pandoc/d2/mmdc/weasyprint) driven by a project-controlled manifest*, STRIDE category Tampering/Elevation, control: pinned-version-only invocation (no network fetch of any toolchain binary at build time) plus the "doc/diagram sources are first-party, already-reviewed content" trust-boundary note from the stage-3 security section. No other STRIDE category applies (no new credential, no new data store, no spoofable identity).

**UI:** none.

**File scope:** `template/docs/tools/document_build.py.jinja`, `template/docs/tools/build_errors.py` (shared with slice 1), its tests, `template/docs/tools/document-build.json` (the project-owned-seed *example* manifest content, not the per-project runtime copy), `template/.gitignore` additions for `docs/_build/`.

**Blocking edges:** blocked by slice 1 (imports `render_diagram_blocks`).

**Acceptance criteria:**
1. A manifest entry with `outputs: ["pdf", "pptx"]` shall produce both a `.pdf` and a `.pptx` from one document, without rendering any diagram in that document more than once.
2. `document_build.py --check` shall validate the manifest and toolchain without invoking any renderer.
3. A manifest entry whose `outputs` contains a value other than `"pdf"` or `"pptx"` shall fail `_validate_inputs` with a `BuildError` naming the offending document.
4. With `CHROMIUM_EXECUTABLE_PATH` unset or pointing at a nonexistent path, a document containing a `mermaid` block shall be skipped (logged, no output files for it) while every other document in the same build still produces its output, and `main` shall return non-zero overall.

## Slice 3 — `doc-build-setup` skill: the stage-0 offer

**Purpose:** the skill a stage-0 thread runs to offer, scaffold, and record this feature for one project, mirroring `impeccable`'s existing setup flow.

**Module and interface:** a `SKILL.md`, not code — its "interface" is the sequence it tells the invoking thread to follow: (1) ask the owner once, in the same conversation turn as the `impeccable` offer if that stage-0 interview is already covering optional setup choices; (2) on yes, copy slices 1–2's files into the project (from the template, already forge-synced — this skill does not duplicate their content, it only decides *whether* and *when* to place them) and write the project's own first `docs/tools/document-build.json` (an example manifest, not an empty one — grill decision 4 is explicit that this ships real, working content, not a bare convention left for the project to fill from scratch) plus `docs/development/documentation-build.md`; if the project has `mermaid` content, note in `docs/development/documentation-build.md` that a build needs `CHROMIUM_EXECUTABLE_PATH` set to a pre-installed Chromium/Chrome binary (e.g. wired into the project's own CI image or devcontainer Dockerfile, wherever it already installs one for another purpose such as Playwright-based e2e) — this skill does not resolve or set the value itself, since that's an environment-setup concern outside the manifest; (3) append one step to `scripts/local-full-suite.sh` running `document_build.py` (full render, not `--check` — per the owner's decision on the feature's tracking issue); (4) on skip, say so plainly and note the re-offer trigger (the first time a design doc or the SAD needs a diagram/doc it can't yet render) for the stage-3/5 design thread to watch for.

**Behaviour / seam tested through:** this is process text for an agent to follow, not a program; `codebase-design`'s module-map tests don't apply to it the way they do to slices 1–2. Its "test" is the design-exit/self-review check that the skill's steps match this document and the stage-3 comment, the same verification any other skill gets.

**Guard test:** n/a (no executable guard for a SKILL.md's own correctness beyond review; `check_skills_lock.py` and `check_sync_duplicates.py` already guard the forge-sync mechanics every skill goes through).

**Threat-model delta:** none — the skill only decides *whether* slices 1–2 run; it adds no new surface beyond what slice 2 already covers.

**UI:** none — `impeccable`'s own check is for a feature that introduces or changes a user interface; this feature introduces none.

**File scope:** `template/.agents/skills/doc-build-setup/SKILL.md`, `template/docs/development/documentation-build.md.jinja` (seeded content), `template/.gitignore`.

**Blocking edges:** blocked by slice 2 (the skill scaffolds slice 2's files).

**Acceptance criteria:**
1. The skill shall ask the owner at most once per project, recording a skip plainly rather than silently dropping the offer.
2. On acceptance, the skill shall leave `scripts/local-full-suite.sh` with exactly one new step that runs `document_build.py` (full render).
3. The skill's guide doc shall include the agent-facing "how to add a document to the manifest" note named in grill decision 8.

## Slice 4 — stage-0 process text and `copier.yml` wiring

**Purpose:** make the offer discoverable from the one place every stage-0 thread already reads, and protect the manifest/guide files the skill creates from a later `copier update`.

**Module and interface:** a one-sentence addition to `template/.forge/feature-pipeline.md.jinja`'s "Stage 0: project inception" section, parallel to its existing `impeccable` sentence; two new entries in `copier.yml`'s `_skip_if_exists` list (`docs/tools/document-build.json`, `docs/development/documentation-build.md`).

**Behaviour:** no runtime behaviour — this is the "how does a stage-0 thread learn this offer exists" and "how does `copier update` not clobber it" wiring.

**Seam tested through:** `scripts/test_copier_skip_if_exists.py` (implementation deviation: this line originally pointed at `template/scripts/test_copier_update_defaults.py`'s "existing pattern," but that file only checks documented `copier update --data ... --defaults` commands and has no `_skip_if_exists` logic to extend — no such pattern existed anywhere in the repo before this slice. The new test is root-only (`scripts/`, not `template/scripts/`), since `copier.yml` itself never ships to a generated project under `_subdirectory: template`, so there is nothing in a rendered project for a shipped copy of this test to check).

**Guard test:** a test that runs `copier update` against a fixture project that already has a locally-edited `docs/tools/document-build.json`, and asserts the local edit survives — the test that must go red if either path is ever dropped from `_skip_if_exists`.

**Threat-model delta:** none.

**UI:** none.

**File scope:** `template/.forge/feature-pipeline.md.jinja`, `copier.yml`.

**Blocking edges:** blocked by slice 3 (the sentence names the skill by its real name).

**Acceptance criteria:**
1. Stage 0's text shall name `doc-build-setup` alongside `impeccable` as an optional stage-0 offer, in the same ask-once/skip-and-say-so shape.
2. `copier.yml`'s `_skip_if_exists` shall list both new project-owned paths.

## Test matrix

| Slice | Unit | Integration/E2E | Guard |
|---|---|---|---|
| 1 | dispatch-table logic against a synthetic AST | real `d2`/`mmdc` binaries against a fixture diagram each (gated on `PATH`) | empty-renderers-table test (§ guard test above) |
| 2 | manifest validation (`_validate_inputs`) unit tests | full fixture-manifest build producing real `.pdf`/`.pptx` | render-once-per-document call-count test |
| 3 | n/a (prose) | design-exit/self-review check against this doc | n/a |
| 4 | `_skip_if_exists` presence check | `copier update` local-edit-survives fixture | same test, strengthened |

## Open items for the implementer to re-verify

- Resolved (design-exit pass, 2026-11-01): `mmdc`'s real flag is `-p, --puppeteerConfigFile <file>` — confirmed against a real `mmdc 12.0.0 --help` (the stage-8 pass's own pinned-version example was `10.9.0`; `--help`'s own option list has carried this flag across both). The flag takes a JSON file matching Puppeteer's `launch()` options; `{"executablePath": "<path>", "args": ["--no-sandbox"]}` was verified end to end (a real `mmdc` render succeeded, pointed at a real pre-installed Chromium binary with Puppeteer's own download disabled) — the mechanism works.
- Resolved (owner decision, 2026-11-01): a first design-exit pass proposed dropping the reuse (letting `mmdc` always fetch its own Chromium) on the grounds that no project offers a *build-time-discoverable* path. The owner reaffirmed the original decision instead: reuse stays, the path is never discovered at build time, and — explicitly — a missing/invalid path is never papered over by falling back to a bundled Chromium. It comes from a single environment variable (`CHROMIUM_EXECUTABLE_PATH`) resolved once by whatever already installs a browser in that environment, and a document whose render needs it but can't get it is skipped with a loud, logged error rather than silently degraded. See the build-vs-buy table above.
- Resolved: the override moved from the reference implementation's deck-build script's hardcoded Python heredoc into the manifest-driven `diagram_overrides.d2` key, scoped to the D2-rendering CLI flags only (`layout`, `theme`, `pad`, `scale`). It changes no WeasyPrint invocation or option: WeasyPrint only ever consumes the already-rendered PNG images, the same as before this key existed, so there is nothing WeasyPrint-side left to re-verify.
- Resolved: `diagram_overrides` is per-document, keyed in `document-build.json` on each document entry, not a build-script constant — confirmed against `--check`'s validation (`_validate_diagram_overrides`) and the renderer-binding test (`_build_renderers` now takes the document and binds its own `diagram_overrides.d2`).
