#!/usr/bin/env python3
"""Verify a forge-sync PR's "SDLC wording held" evidence line mechanically.

`forge-sync`'s "Hold SDLC wording changes for the owner" step
(`.agents/skills/forge-sync/SKILL.md`) is the one place a sync is allowed to
touch `docs/software-development-lifecycle.md` at all: it reverts every
`- **SDLC-NNN**: ...` statement `copier update` reworded back to its
pre-sync text, and records what it held (or "none") in the sync PR body
under "SDLC wording held" (`.agents/skills/forge-sync/SKILL.md`, "Review and
merge"). That step was purely procedural -- nothing confirmed it actually
ran before the PR merged (`docs/security/threat-model.md`, T15).

Usage:
    check_sdlc_wording_hold.py BODY_FILE OLD_DOC NEW_DOC

BODY_FILE holds the PR's body text. OLD_DOC/NEW_DOC are the lifecycle doc's
content at the PR's base and head. Only applies when BODY_FILE carries
forge-sync's own "Drift before this sync" marker (`.agents/skills/
forge-sync/SKILL.md`, "Before you start"); exits 0 with nothing printed for
any other PR, including one that happens to also touch the lifecycle doc.

Exits 1 when either:
- re-running `check_sdlc_wording_changes.changed()` between OLD_DOC and
  NEW_DOC still reports a changed statement (the revert in step 3 didn't
  happen, or missed one); or
- the PR body's "SDLC wording held" line is missing or blank (the step must
  say "none" explicitly, even when there was nothing to hold).
Exits 0 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sdlc_wording_changes as wording  # noqa: E402

SYNC_MARKER_RE = re.compile(r"Drift before this sync", re.IGNORECASE)
HELD_LINE_RE = re.compile(r"SDLC wording held[^:\n]*:[ \t]*(?P<value>[^\n]*)", re.IGNORECASE)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def check(body: str, old_text: str, new_text: str) -> list[str]:
    """Every failure this PR's SDLC-wording hold has against a fresh re-check."""
    if not SYNC_MARKER_RE.search(body):
        return []

    failures: list[str] = []
    diffs = wording.changed(old_text, new_text)
    if diffs:
        ids = ", ".join(statement_id for statement_id, _, _ in diffs)
        failures.append(
            f"The lifecycle doc still differs from this PR's base for: {ids}. "
            'A forge-sync PR must revert every SDLC statement\'s wording to its '
            'pre-sync text (.agents/skills/forge-sync/SKILL.md, "Hold SDLC '
            'wording changes for the owner", step 3) before it merges, '
            "whatever the \"SDLC wording held\" line says."
        )

    match = HELD_LINE_RE.search(body)
    if not match or not match["value"].strip():
        failures.append(
            'The PR body has no "SDLC wording held" line, or it\'s blank. '
            'Record "none", or each held statement and the lifecycle-doc PR '
            "it moved to, even when nothing was held."
        )
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check_sdlc_wording_hold.py BODY_FILE OLD_DOC NEW_DOC", file=sys.stderr)
        return 2
    body = _read(Path(argv[0]))
    old_text = _read(Path(argv[1]))
    new_text = _read(Path(argv[2]))

    failures = check(body, old_text, new_text)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
