"""Shared helper for guard tests that read a forge file by its rendered or `.jinja` name.

A test under `scripts/` ships verbatim into every generated project, where
Copier has already stripped `.jinja`, while the same file in TheForge itself
still carries it. Does not match `test_*.py`, so `unittest discover` never
treats this as a test module on its own.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rendered_or_jinja(*relative_parts: str) -> Path:
    """The actual file for a path given without its possible `.jinja` suffix."""
    base = ROOT.joinpath(*relative_parts)
    jinja = base.with_name(base.name + ".jinja")
    for candidate in (jinja, base):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"no {base.name} or {base.name}.jinja under {base.parent}")


def is_rendered() -> bool:
    """False in TheForge's own tree, true in a Copier-generated project: Copier
    always writes `.copier-answers.yml` on copy, and nothing else does."""
    return (ROOT / ".copier-answers.yml").is_file()
