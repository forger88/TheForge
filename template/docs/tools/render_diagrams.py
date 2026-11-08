"""Transform Pandoc fenced code blocks into rendered diagram images.

Which renderer handles a block is chosen by the block's fenced-code-block
language class (e.g. ``d2``, ``mermaid``), never by the document's target
output format. Adding a new diagram tool later is one new entry in the
``renderers`` table a caller builds and passes in; this module's own
dispatch logic never changes for it.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import atexit
from collections.abc import Callable
from pathlib import Path
from typing import Any

import vl_convert as vlc
from fontTools.ttLib import TTFont

from build_errors import BuildError, ChromiumNotConfiguredError

__all__ = [
    "BuildError",
    "ChromiumNotConfiguredError",
    "render_d2",
    "render_diagram_blocks",
    "render_mermaid",
    "render_svg_to_png",
]

# (source_text, destination_png) -> None; raises BuildError on failure.
DiagramRenderer = Callable[[str, Path], None]

D2_RENDER_ARGS = ["--layout=dagre", "--theme=0", "--pad=32"]

# `overrides` key -> the D2 CLI flag it replaces in `D2_RENDER_ARGS`. Keep in
# step with `document_build._D2_OVERRIDE_TYPES`, which allowlists and
# type-checks the same keys before they ever reach here.
_D2_OVERRIDE_FLAGS = {
    "layout": "--layout",
    "theme": "--theme",
    "pad": "--pad",
    "scale": "--scale",
}


def _d2_args(overrides: dict[str, Any] | None) -> list[str]:
    """`D2_RENDER_ARGS`, with each key present in `overrides` replacing its
    matching flag -- never appended alongside it, which would duplicate it.
    """
    if not overrides:
        return list(D2_RENDER_ARGS)
    replaced = {_D2_OVERRIDE_FLAGS[key] for key in overrides}
    args = [arg for arg in D2_RENDER_ARGS if arg.split("=", 1)[0] not in replaced]
    args.extend(
        f"{_D2_OVERRIDE_FLAGS[key]}={value}" for key, value in overrides.items()
    )
    return args


# Matches one SVG-emitted `@font-face { font-family: NAME; src:
# url("data:MIME;base64,DATA") }` rule -- see `_resolve_embedded_fonts`'s own
# docstring for why this needs parsing at all rather than just handing the
# SVG straight to the rasterizer.
_FONT_FACE_RE = re.compile(
    r"@font-face\s*\{\s*font-family:\s*(?P<name>[^;]+?)\s*;\s*"
    r'src:\s*url\("data:[^;]+;base64,(?P<data>[^"]+)"\)\s*;?\s*\}',
    re.DOTALL,
)


def _text_inlines(text: str) -> list[dict[str, Any]]:
    words = text.split()
    inlines: list[dict[str, Any]] = []
    for index, word in enumerate(words):
        if index:
            inlines.append({"t": "Space"})
        inlines.append({"t": "Str", "c": word})
    return inlines


def render_diagram_blocks(
    document: dict[str, Any],
    output_dir: Path,
    renderers: dict[str, DiagramRenderer],
) -> dict[str, Any]:
    """Return a Pandoc document whose matching CodeBlocks are rendered Images.

    A CodeBlock whose classes include a key of ``renderers`` is replaced with
    an Image, rendered by that key's renderer. A CodeBlock whose classes
    match no key in ``renderers`` -- including every class, when
    ``renderers`` is empty -- passes through unchanged: an unrecognized
    fenced-block language (a `python` or `bash` example, say) is not an
    error, it simply isn't a diagram.
    """
    transformed = copy.deepcopy(document)
    counter = 0

    def visit(value: Any) -> Any:
        nonlocal counter
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value

        if value.get("t") == "CodeBlock":
            attributes, source = value["c"]
            identifier, classes, key_values = attributes
            matched = [name for name in classes if name in renderers]
            if not matched:
                return value
            renderer = renderers[matched[0]]

            counter += 1
            digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
            filename = f"diagram-{counter:02d}-{digest}.png"
            destination = output_dir / filename
            output_dir.mkdir(parents=True, exist_ok=True)
            renderer(source, destination)

            options = dict(key_values)
            caption = options.get("caption", "")
            alt = _text_inlines(caption)
            image_attributes = [
                identifier,
                [name for name in classes if name not in renderers],
                [[key, item] for key, item in key_values if key != "caption"],
            ]
            return {
                "t": "Para",
                "c": [{"t": "Image", "c": [image_attributes, alt, [filename, ""]]}],
            }

        return {key: visit(item) for key, item in value.items()}

    return visit(transformed)


def _resolve_embedded_fonts(svg_text: str, font_dir: Path) -> str:
    """Make a diagram tool's self-contained embedded fonts resolvable by the
    SVG rasterizer below.

    Several diagram-rendering tools' SVG export embeds each font it used as a
    base64 data URI under an invented per-diagram `@font-face` name -- this
    is what lets the SVG stand alone in a browser with no external font
    file. The rasterizer used below renders SVG via a library that does
    *not* parse `@font-face`'s `src: url(data:...)` at all: it resolves a
    `font-family` name only by matching it, by name, against fonts it
    already knows about, populated either from the system's installed fonts
    or from a registered font directory. Left alone, a diagram tool's
    invented per-diagram name never matches anything, and the text silently
    disappears -- not a fallback glyph, no glyph drawn at all.

    So each embedded font is decoded here, saved as a real sfnt file for a
    registered font directory to pick up, and every occurrence of its
    invented name in the SVG is rewritten to the font's own internal family
    name (`name` table, nameID 1) -- the one the rasterizer's font database
    will actually have, once that directory is registered.
    """
    replacements: dict[str, str] = {}
    for match in _FONT_FACE_RE.finditer(svg_text):
        invented_name = match.group("name").strip().strip("\"'")
        if invented_name in replacements:
            continue
        font_bytes = base64.b64decode(match.group("data"))
        font = TTFont(io.BytesIO(font_bytes))
        font.flavor = None
        real_name = font["name"].getDebugName(1) or invented_name
        digest = hashlib.sha256(font_bytes).hexdigest()[:16]
        font.save(font_dir / f"{digest}.ttf")
        replacements[invented_name] = real_name

    resolved = svg_text
    for invented_name, real_name in replacements.items():
        resolved = resolved.replace(invented_name, real_name)
    return resolved


_shared_font_directory: Path | None = None


def _font_directory() -> Path:
    """The one on-disk directory the rasterizer's font registration is ever
    pointed at, for this whole process.

    A fresh directory per diagram would be wrong: the rasterizer's font
    database accumulates registered directories for the life of the
    process, and diagrams from the same tool almost always embed the *same*
    real font under the *same* invented name. A second diagram's
    registration of an already-deleted directory leaves the database's
    first (stale) registration in place, silently losing all of that
    second diagram's text. A single directory that lives for the whole
    process keeps every font written for an earlier diagram on disk, at the
    same registered path, when a later diagram looks for it.
    """
    global _shared_font_directory
    if _shared_font_directory is None:
        _shared_font_directory = Path(tempfile.mkdtemp(prefix="diagram-fonts-"))
        atexit.register(shutil.rmtree, _shared_font_directory, ignore_errors=True)
    return _shared_font_directory


def render_svg_to_png(svg_path: Path, png_path: Path) -> None:
    """Rasterize an SVG to PNG, resolving any embedded diagram-tool fonts
    first (see `_resolve_embedded_fonts`).

    Shared by every renderer below: the SVG-then-rasterize path needs no
    browser or network access, unlike a diagram tool's own direct
    image-export step, which typically drives a headless browser.
    """
    svg_text = svg_path.read_text(encoding="utf-8")
    font_directory = _font_directory()
    svg_text = _resolve_embedded_fonts(svg_text, font_directory)
    vlc.register_font_directory(str(font_directory))
    png_path.write_bytes(vlc.svg_to_png(svg_text))


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0])
    if executable is None:
        raise BuildError(f"Required command '{command[0]}' was not found on PATH.")
    try:
        return subprocess.run(
            [executable, *command[1:]], check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        suffix = f"\n{detail}" if detail else ""
        raise BuildError(f"Command failed ({' '.join(command)}).{suffix}") from error


def render_d2(
    source_text: str,
    destination: Path,
    *,
    command: str = "d2",
    overrides: dict[str, Any] | None = None,
) -> None:
    """Render D2 source to a PNG via D2's own SVG export, then
    `render_svg_to_png` above.

    PNG, not SVG, as the final output: a D2-emitted SVG embeds its
    label/text font as a base64 @font-face inside an <svg><style> block,
    which an HTML-to-PDF or HTML-to-slide pipeline's own SVG support
    commonly fails to resolve (nor a plain font-family fallback declared
    the same way) -- every diagram's text renders as solid, borderless
    shapes with no text visible otherwise. Rendering to PNG here, once,
    keeps that failure mode out of every caller's own output step.

    `command` is the binary to invoke -- a caller building from a manifest
    passes its `toolchain.d2.command`, the exact path `_check_toolchain`
    version-checked; the literal `"d2"` default is for direct callers (the
    tests below) with no manifest to read it from.

    `overrides` replaces the matching default flag(s) in `D2_RENDER_ARGS`
    (see `_d2_args`) -- a caller building from a manifest passes that
    document's own `diagram_overrides["d2"]`, already allowlisted and
    type-checked by `document_build._validate_diagram_overrides`.
    """
    d2_source = destination.with_suffix(".d2")
    d2_svg = destination.with_suffix(".svg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    d2_source.write_text(source_text, encoding="utf-8")
    try:
        _run([command, *_d2_args(overrides), str(d2_source), str(d2_svg)])
        render_svg_to_png(d2_svg, destination)
    finally:
        d2_source.unlink(missing_ok=True)
        d2_svg.unlink(missing_ok=True)


# By default `mmdc` writes flowchart node labels as HTML inside an SVG
# <foreignObject>, which `render_svg_to_png`'s resvg-based rasterizer does
# not render at all -- the same silent-blank-text failure
# `_resolve_embedded_fonts` exists to prevent for D2, but with no text
# drawn whatsoever rather than a wrong font. `htmlLabels: false` is the
# top-level Mermaid config key (`flowchart.htmlLabels` is a deprecated
# alias for it as of Mermaid 11); it makes every renderer emit labels as
# plain SVG <text>, which the rasterizer does draw.
_MERMAID_CONFIG_PATH = Path(__file__).resolve().parent / "mermaid-render-config.json"


def render_mermaid(
    source_text: str,
    destination: Path,
    *,
    command: str = "mmdc",
    chromium_executable: str | None = None,
) -> None:
    """Render Mermaid source to a PNG via `mmdc`'s own SVG export, then
    `render_svg_to_png` above.

    Mermaid's native C4 diagram syntax (`C4Context`, `C4Container`, and the
    rest of that family) is plain Mermaid source text: this function never
    inspects or special-cases it. Whether a block draws a C4 diagram is
    entirely a property of the Mermaid source it is given, not of anything
    this renderer does.

    `command` is the binary to invoke -- a caller building from a manifest
    passes its `toolchain.mmdc.command`, the exact path `_check_toolchain`
    version-checked; the literal `"mmdc"` default is for direct callers
    (the tests below) with no manifest to read it from.

    `chromium_executable` is the path to a pre-installed Chromium/Chrome
    binary -- a caller building from a manifest passes
    `environment.get("CHROMIUM_EXECUTABLE_PATH")`; this function never reads
    the environment itself (owner decision, 2026-11-01: reuse a
    pre-installed Chromium rather than let `mmdc` fetch its own, with no
    runtime fallback). Falsy, or not an existing file, raises
    `ChromiumNotConfiguredError` and never invokes `mmdc` at all.
    """
    if not chromium_executable:
        raise ChromiumNotConfiguredError(
            "CHROMIUM_EXECUTABLE_PATH is not set; mmdc needs a pre-installed "
            "Chromium/Chrome binary to render a mermaid diagram. See "
            "docs/development/documentation-build.md for how to set it."
        )
    if not Path(chromium_executable).is_file():
        raise ChromiumNotConfiguredError(
            f"CHROMIUM_EXECUTABLE_PATH={chromium_executable!r} does not exist; "
            "mmdc needs a pre-installed Chromium/Chrome binary to render a "
            "mermaid diagram. See docs/development/documentation-build.md "
            "for how to set it."
        )

    mermaid_source = destination.with_suffix(".mmd")
    mermaid_svg = destination.with_suffix(".svg")
    puppeteer_config = destination.with_suffix(".puppeteer.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    mermaid_source.write_text(source_text, encoding="utf-8")
    # Puppeteer's bundled Chromium refuses to launch as root without
    # --no-sandbox (confirmed against a real end-to-end render).
    puppeteer_config.write_text(
        json.dumps({"executablePath": chromium_executable, "args": ["--no-sandbox"]}),
        encoding="utf-8",
    )
    try:
        _run(
            [
                command,
                "-i",
                str(mermaid_source),
                "-o",
                str(mermaid_svg),
                "-c",
                str(_MERMAID_CONFIG_PATH),
                "-p",
                str(puppeteer_config),
            ]
        )
        render_svg_to_png(mermaid_svg, destination)
    finally:
        mermaid_source.unlink(missing_ok=True)
        mermaid_svg.unlink(missing_ok=True)
        puppeteer_config.unlink(missing_ok=True)
