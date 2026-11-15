#!/usr/bin/env python3
"""Forge-entrypoint guard (CLAUDE.md, "This project's own rules"; a generated
CLAUDE.md carries no forge rule text of its own beyond the one import line
this guard checks for).

A generated project's `CLAUDE.md` carries no forge-authored rule text beyond
one line, `@.forge/entrypoint.md`; `.forge/entrypoint.md` itself carries the
framing sentences, every always-loaded `@.forge/` import, and the
reference-files sentence. This guards that shape: losing the entrypoint line
would silently disable every forge rule, including this review gate itself.

Where `AGENTS.md` exists, it must also stay a thin shell: no `##`-or-deeper
heading, at most AGENTS_MAX_WORDS words, and no 30+-char line duplicated from
`CLAUDE.md` or any `.forge/*` file -- the condensed restatement that shape
rules out belongs in `CLAUDE.md` (or the forge-owned file it imports), read
once, not copied into a second file that then drifts from it.

Two hooks run this script:

- Consumer side (`forge-entrypoint`), against a generated project's own
  `CLAUDE.md`, `AGENTS.md` and `.forge/*.md`.
- Root side (`forge-entrypoint-template`, `--root template --template`),
  against this repository's own `template/CLAUDE.md.jinja`,
  `template/AGENTS.md.jinja` and `template/.forge/*`, with the `.jinja`
  suffix stripped when matching a name against an import or reference.

Usage: python3 scripts/check_forge_entrypoint.py [--root DIR] [--template]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

IMPORT_RE = re.compile(r"^@(\.forge/[\w.-]+\.md)\s*$")
REFERENCE_RE = re.compile(r"`(\.forge/[\w.-]+\.md)`")

CLAUDE_NAME = "CLAUDE.md"
AGENTS_NAME = "AGENTS.md"
ENTRYPOINT_NAME = ".forge/entrypoint.md"
AGENTS_HEADING_RE = re.compile(r"^#{2,}\s", re.M)
AGENTS_MAX_WORDS = 300
MIN_SHARED_LINE_LEN = 30


def entrypoint_targets(text: str) -> tuple[list[str], list[str]]:
    """Returns (imports, references): the `@.forge/<x>.md` lines, and the
    backticked `.forge/<x>.md` occurrences on every other line."""
    imports: list[str] = []
    references: list[str] = []
    for line in text.splitlines():
        match = IMPORT_RE.match(line)
        if match:
            imports.append(match.group(1))
            continue
        references.extend(REFERENCE_RE.findall(line))
    return imports, references


def _read(root: Path, name: str, template: bool) -> str | None:
    """`name` is a path like "CLAUDE.md" or ".forge/entrypoint.md". In
    template mode, also tries the `.jinja`-suffixed sibling, since a
    forge-owned file ships under `template/` either as-is (like
    `.forge/entrypoint.md`) or with a `.jinja` suffix stripped at render
    time (like `CLAUDE.md.jinja` or `.forge/orchestration.md.jinja`)."""
    candidates = [root / name]
    if template:
        candidates.append(root / f"{name}.jinja")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return None


def _forge_file_names(root: Path, template: bool) -> list[str]:
    """Every `.forge/<name>.md` this tree ships, with a template-mode
    `.jinja` suffix stripped so it matches the name an import or reference
    uses."""
    forge_dir = root / ".forge"
    if not forge_dir.is_dir():
        return []
    names: list[str] = []
    for entry in sorted(forge_dir.iterdir()):
        if not entry.is_file():
            continue
        name = entry.name
        if template and name.endswith(".jinja"):
            name = name[: -len(".jinja")]
        if name.endswith(".md"):
            names.append(f".forge/{name}")
    return names


def _forge_texts(root: Path) -> dict[str, str]:
    """Every file directly under `.forge/`, by name, read as text. Shared by
    every check below that needs the forge-owned files' own content rather
    than just their names (`_forge_file_names` covers that narrower need)."""
    forge_dir = root / ".forge"
    if not forge_dir.is_dir():
        return {}
    return {
        entry.name: entry.read_text(encoding="utf-8")
        for entry in sorted(forge_dir.iterdir())
        if entry.is_file()
    }


def _long_lines(text: str) -> set[str]:
    """Every line of `text`, stripped, at least MIN_SHARED_LINE_LEN chars --
    short enough lines (a heading, a single word) collide too often to mean
    real duplication."""
    return {line.strip() for line in text.splitlines() if len(line.strip()) >= MIN_SHARED_LINE_LEN}


def _shared_long_lines(a_text: str, b_texts: dict[str, str]) -> list[tuple[str, str]]:
    """Returns (source name, line) pairs: every long line in `a_text` that
    also appears verbatim in one of `b_texts` (name -> text), sorted for a
    deterministic report. Shared by the CLAUDE.md.jinja-vs-.forge check and
    the AGENTS.md-vs-CLAUDE.md/.forge check below, so both read the same
    "this rule text lives in exactly one place" rule the same way."""
    a_lines = _long_lines(a_text)
    if not a_lines:
        return []
    shared: list[tuple[str, str]] = []
    for name, text in sorted(b_texts.items()):
        for line in sorted(a_lines & _long_lines(text)):
            shared.append((name, line))
    return shared


def problems(root: Path, template: bool) -> list[str]:
    errors: list[str] = []

    entrypoint_text = _read(root, ENTRYPOINT_NAME, template)
    if entrypoint_text is None:
        errors.append(f"{ENTRYPOINT_NAME} is missing")
    entrypoint_imports, entrypoint_refs = entrypoint_targets(entrypoint_text) if entrypoint_text else ([], [])

    claude_text = _read(root, CLAUDE_NAME, template)
    if claude_text is None:
        errors.append(f"{CLAUDE_NAME} is missing")
    else:
        claude_imports, _ = entrypoint_targets(claude_text)
        if ENTRYPOINT_NAME not in claude_imports:
            errors.append(f"{CLAUDE_NAME} has no line exactly '@{ENTRYPOINT_NAME}'")
        for imp in claude_imports:
            if imp != ENTRYPOINT_NAME and imp in entrypoint_imports:
                errors.append(f"{CLAUDE_NAME} has '@{imp}', which {ENTRYPOINT_NAME} already imports (double load)")

    agents_text = _read(root, AGENTS_NAME, template)
    if agents_text is not None:
        if ".forge/entrypoint.md" not in agents_text:
            errors.append(f"{AGENTS_NAME} exists but does not mention '.forge/entrypoint.md'")
        agents_imports, _ = entrypoint_targets(agents_text)
        for imp in agents_imports:
            if imp != ENTRYPOINT_NAME and imp in entrypoint_imports:
                errors.append(f"{AGENTS_NAME} has '@{imp}', which {ENTRYPOINT_NAME} already imports (double load)")
        if AGENTS_HEADING_RE.search(agents_text):
            errors.append(f"{AGENTS_NAME} has a '##'-or-deeper heading; keep it a flat shell with no sub-headings")
        word_count = len(agents_text.split())
        if word_count > AGENTS_MAX_WORDS:
            errors.append(f"{AGENTS_NAME} is {word_count} words, over the {AGENTS_MAX_WORDS}-word shell cap")
        duplicate_sources: dict[str, str] = dict(_forge_texts(root))
        if claude_text is not None:
            duplicate_sources[CLAUDE_NAME] = claude_text
        for name, shared in _shared_long_lines(agents_text, duplicate_sources):
            errors.append(f"{AGENTS_NAME} carries rule text also in {name}: {shared!r}")

    for target in entrypoint_imports + entrypoint_refs:
        if _read(root, target, template) is None:
            errors.append(f"{ENTRYPOINT_NAME} names '{target}', which does not exist")

    covered = set(entrypoint_imports) | set(entrypoint_refs)
    for forge_name in _forge_file_names(root, template):
        if forge_name != ENTRYPOINT_NAME and forge_name not in covered:
            errors.append(f"{forge_name} is not imported or referenced by {ENTRYPOINT_NAME}")

    if template and claude_text is not None:
        for name, shared in _shared_long_lines(claude_text, _forge_texts(root)):
            errors.append(f"CLAUDE.md.jinja carries rule text also in {name}: {shared!r}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--template", action="store_true")
    args = parser.parse_args(argv)

    errors = problems(args.root, args.template)
    for line in errors:
        print(line, file=sys.stderr)
    if errors:
        if args.template:
            print("Fix template/ directly -- these are TheForge's own files, not a generated project's.", file=sys.stderr)
        else:
            print("If this project predates the entrypoint, run forge-sync's 'Entrypoint migration' section.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
