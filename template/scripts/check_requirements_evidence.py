#!/usr/bin/env python3
"""Check Evidence paragraphs in the requirements specification
(`.agents/skills/requirements-spec/SKILL.md`, "Evidence"; SDLC-119).

Usage:
    check_requirements_evidence.py [FILE ...]

Scans each given file (or, with no arguments,
`docs/requirements/requirements-specification.md`) for a paragraph (one or
more consecutive non-blank lines) that opens with the bold label
`**Evidence:**` or `**Evidence (<IDs>):**`, and checks that:

- the rest of the paragraph is a plain comma-separated list of backticked,
  repo-relative file paths, and nothing else (no symbol, function, line, test
  name, issue or PR number, date, or other prose), on one line or wrapped
  across several;
- every named path is confined under the repository root (no absolute path,
  no `..` escape) and exists;
- a line that opens with a near-miss of the label (`**Evidence**:`,
  `**Evidence.**` followed by file paths, and similar) is flagged too, rather
  than silently passing as ordinary prose.

`requirements_evidence_baseline.json` is a shrink-only allowlist, keyed by
"<repo-relative file>:<label>[#N]" (N disambiguating repeated labels in one
file; never a line number, which shifts whenever unrelated lines are added
above it, and never an absolute path, which only matches the clone that
seeded it), of paragraphs that already failed this check before the hook was
added, each holding the exact error text seeded for it. New content never
gets a new entry: a paragraph not in the baseline that fails is reported, an
entry whose paragraph no longer fails must be removed, and an entry whose
error text has changed must be updated to match or the paragraph fixed.
"""

from __future__ import annotations

import json
import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = [REPO_ROOT / "docs" / "requirements" / "requirements-specification.md"]
BASELINE = Path(__file__).with_name("requirements_evidence_baseline.json")

EVIDENCE_RE = re.compile(r"^\*\*Evidence(?:\s*\(([^)]*)\))?:\*\*\s*(.*)$")
# Catches a line that is trying to be an Evidence label but isn't the exact
# shape above (closing bold before the colon, a period instead of a colon,
# and similar), so a near-miss is flagged rather than silently read as prose.
EVIDENCE_NEAR_MISS_RE = re.compile(r"^\*\*Evidence\b")
PATH_TOKEN_RE = re.compile(r"^`([^`]+)`$")


def check_paragraph(rest: str, repo_root: Path) -> str | None:
    """Return an error string for a malformed or broken Evidence paragraph, or None when it's clean."""
    if not rest.strip():
        return "Evidence paragraph names no files"
    tokens = [t.strip() for t in rest.split(",")]
    paths: list[str] = []
    for token in tokens:
        match = PATH_TOKEN_RE.match(token)
        if not match:
            return f"not a plain comma-separated list of backticked paths: {rest!r}"
        paths.append(match.group(1))
    root = repo_root.resolve()
    outside: list[str] = []
    missing: list[str] = []
    for p in paths:
        if p.startswith("/") or p.startswith("~"):
            outside.append(p)
            continue
        try:
            (root / p).resolve().relative_to(root)
        except ValueError:
            outside.append(p)
            continue
        if not (root / p).is_file():
            missing.append(p)
    if outside:
        return f"path(s) are not repo-relative: {', '.join(outside)}"
    if missing:
        return f"path(s) do not exist: {', '.join(missing)}"
    return None


def paragraph_text(lines: list[str], start: int) -> tuple[str, int]:
    """Join `start`'s line with every following non-blank line; return the joined
    text and the index of the first line after the paragraph."""
    collected = [lines[start].strip()]
    i = start + 1
    while i < len(lines) and lines[i].strip():
        collected.append(lines[i].strip())
        i += 1
    return " ".join(collected), i


def scan(path: Path, repo_root: Path) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not path.is_file():
        return errors
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel = path
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: dict[str, int] = {}
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not EVIDENCE_NEAR_MISS_RE.match(stripped):
            i += 1
            continue
        text, next_i = paragraph_text(lines, i)
        match = EVIDENCE_RE.match(text)
        if not match:
            error = f"not the canonical Evidence label shape (`**Evidence:**` or `**Evidence (<IDs>):**`): {text!r}"
            label = stripped
        else:
            label = f"Evidence({match.group(1)})" if match.group(1) else "Evidence"
            error = check_paragraph(match.group(2), repo_root)
        base_key = f"{rel}:{label}"
        count = seen.get(base_key, 0)
        seen[base_key] = count + 1
        key = base_key if count == 0 else f"{base_key}#{count + 1}"
        if error:
            errors[key] = error
        i = next_i
    return errors


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] if argv else DEFAULT_FILES
    baseline: dict[str, str] = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    found: dict[str, str] = {}
    for f in files:
        if f.suffix == ".md":
            found.update(scan(f, REPO_ROOT))
    out: list[str] = []
    for key, error in sorted(found.items()):
        baselined = baseline.get(key)
        if baselined is None:
            out.append(f"{key}: {error}")
        elif baselined != error:
            out.append(f"{key}: error changed since baselined ({baselined!r} -> {error!r}); fix it or update the baseline entry")
    if not argv:
        # A full run also catches entries for paragraphs that no longer fail.
        for key in sorted(set(baseline) - set(found)):
            out.append(f"{key}: baselined but no longer failing; remove its entry")
    for line in out:
        print(line, file=sys.stderr)
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
