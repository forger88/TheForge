#!/usr/bin/env python3
"""Check that forge-owned rule files are written one sentence per line.

Forge-owned files under `.forge/` are synced from TheForge by `copier update`,
a three-way merge. One sentence per line makes a conflict land on the sentence
that changed rather than on a whole re-wrapped paragraph (ADR-0002 in TheForge).

Usage:
    check_one_sentence_per_line.py [FILE ...]

With no arguments it checks `.forge/*.md` (and `.forge/*.md.jinja`) under the
current directory. Exits 1 and lists offending lines when any line holds more
than one sentence.

Heuristic, deliberately simple: a line is flagged when, after inline code spans,
link targets and known abbreviations are removed, it still contains a
sentence-ending mark (. ! ?), optionally followed by a closing quote, bracket or
emphasis marker, then whitespace and a capital letter. Headings, table rows,
list-item lines (the line carrying the bullet or number), block-quote markers,
HTML comments and fenced code blocks are skipped.

False-positive risk: an abbreviation not in ABBREVIATIONS followed by a capital
("approx. Ten") or an initial ("J. Smith") will be flagged; add the abbreviation
below or reword. False negatives: a second sentence starting with a digit, a
lowercase word or a code span is not caught.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.", "Mr.", "Ms.", "Dr.", "No.", "St.")

FENCE = re.compile(r"^\s*(```|~~~)")
SKIP_LINE = re.compile(r"^\s*(#|\||>|<!--|[-*+]\s|\d+[.)]\s)")
INLINE_CODE = re.compile(r"`[^`]*`")
LINK_TARGET = re.compile(r"\]\([^)]*\)")
SENTENCE_BREAK = re.compile(r"[.!?][\"')\]*_]*\s+[A-Z]")


def offending_lines(text: str) -> list[tuple[int, str]]:
    """Return (line number, line) for every line holding more than one sentence."""
    hits: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip() or SKIP_LINE.match(line):
            continue
        probe = LINK_TARGET.sub("]", INLINE_CODE.sub("code", line))
        for abbreviation in ABBREVIATIONS:
            probe = probe.replace(abbreviation, abbreviation.replace(".", ""))
        if SENTENCE_BREAK.search(probe.rstrip()):
            hits.append((number, line))
    return hits


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv] or sorted(
        [*Path(".forge").glob("*.md"), *Path(".forge").glob("*.md.jinja")]
    )
    status = 0
    for path in paths:
        for number, line in offending_lines(path.read_text(encoding="utf-8")):
            print(f"{path}:{number}: more than one sentence on this line: {line.strip()}")
            status = 1
    if status:
        print("Split each sentence onto its own line (forge-owned files are one sentence per line).")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
