"""The one exception class every doc-build module raises and catches.

`document_build.py`'s top-level error handler (`main`) only catches its own
exceptions; before this module existed, `render_diagrams.py` defined its own
separate `BuildError` class, so a renderer failure (a missing `d2`/`mmdc`
binary, a failed render) was never caught there and escaped as an unhandled
traceback instead of the `error: ...` / exit 2 shape every other failure
takes.
"""

from __future__ import annotations


class BuildError(RuntimeError):
    pass


class ChromiumNotConfiguredError(BuildError):
    """`CHROMIUM_EXECUTABLE_PATH` is unset or doesn't point at a real file.

    Caught specially by `document_build.main`'s per-document loop, which
    skips only the affected document rather than aborting the whole build
    (owner decision, 2026-11-01: reuse a pre-installed Chromium, and when
    it isn't configured, fail loudly and skip rather than silently fall
    back to a bundled download or silently drop the diagram).
    """
