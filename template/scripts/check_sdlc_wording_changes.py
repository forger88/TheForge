#!/usr/bin/env python3
"""Find every SDLC statement whose wording a sync would change.

Usage: check_sdlc_wording_changes.py OLD_DOC NEW_DOC

`forge-sync`'s "Hold SDLC wording changes for the owner" step runs this
against the lifecycle doc as rendered at the project's old and new `_commit`,
to find any `- **SDLC-NNN**: ...` statement copier update would add, remove
or reword, before any of it reaches the sync PR (`.forge/process-and-evidence.md`,
"Process changes follow the lifecycle doc" (Never): only the owner approves
a change to an SDLC statement's wording or meaning).

Exits 1 and lists each changed statement's id and both versions of its text
("(absent)" for a statement added or removed) when any differ; 0 otherwise.
A missing file reads as holding no statements, so a doc that doesn't exist
yet at one of the two commits is not an error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

STATEMENT_START = re.compile(r"^- \*\*(SDLC-\d+)\*\*( \*\([^)]*\)\*)?: (.*)$")
CONTINUATION = re.compile(r"^\s{2,}\S")


def statements(text: str) -> dict[str, str]:
    """Map each SDLC-NNN id to its full statement text, continuation lines joined.

    The `*(desirable)*` marker, if present, is folded into the stored text (as a
    leading tag) rather than discarded, so toggling it between old and new counts
    as a change: SDLC-002 treats a change to a statement's meaning, not only its
    exact words, as something only the owner approves, and *(desirable)* marks a
    goal rather than a commitment -- adding, removing or moving it changes meaning.
    """
    result: dict[str, str] = {}
    current_id: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_id is not None:
            result[current_id] = " ".join(current_lines).strip()

    for line in text.splitlines():
        start = STATEMENT_START.match(line)
        if start:
            flush()
            current_id = start.group(1)
            marker = "(desirable) " if start.group(2) else ""
            current_lines = [marker + start.group(3)]
        elif current_id is not None and CONTINUATION.match(line):
            current_lines.append(line.strip())
        else:
            flush()
            current_id, current_lines = None, []
    flush()
    return result


def changed(old_text: str, new_text: str) -> list[tuple[str, str, str]]:
    """Every SDLC-NNN whose text differs, as (id, old text, new text)."""
    old, new = statements(old_text), statements(new_text)
    ids = sorted(set(old) | set(new), key=lambda sid: int(sid.split("-")[1]))
    return [(sid, old.get(sid, ""), new.get(sid, "")) for sid in ids if old.get(sid, "") != new.get(sid, "")]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_sdlc_wording_changes.py OLD_DOC NEW_DOC", file=sys.stderr)
        return 2
    diffs = changed(_read(Path(argv[0])), _read(Path(argv[1])))
    for statement_id, old_statement, new_statement in diffs:
        print(f"{statement_id}: changed")
        print(f"  old: {old_statement or '(absent)'}")
        print(f"  new: {new_statement or '(absent)'}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
