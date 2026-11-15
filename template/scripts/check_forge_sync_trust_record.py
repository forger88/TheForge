#!/usr/bin/env python3
"""Verify a forge-sync PR's "Trust diff" evidence line mechanically.

`forge-sync`'s "Check what `--trust` would run, before running it" step runs
`check_forge_sync_trust_diff.py` before `copier update --trust` and stops
for explicit review on a changed `copier.yml` or executable-content path.
This script is the mechanical backstop for that step: it re-checks the
sync PR's "Trust diff" record against the PR's own `_commit` change
(`docs/security/threat-model.md`, T14).

Usage:
    check_forge_sync_trust_record.py BODY_FILE OLD_ANSWERS NEW_ANSWERS

BODY_FILE holds the PR's body text. OLD_ANSWERS/NEW_ANSWERS are
`.copier-answers.yml`'s content at the PR's base and head. Only applies when
both answers files carry a `_commit` and the two values differ -- a PR that
leaves `_commit` unchanged, or whose base has none (a retrofit or first
copy), is not a sync and exits 0 with nothing printed. This trigger does not
depend on any PR-body marker, so a sync PR cannot evade the check by
dropping one.

Exits 1 when:
- the body has no `Trust diff:` line;
- its `<old>..<new>` range doesn't match the answers files' own `_commit`
  values (normalising a `git describe` string, `<tag>-<n>-g<hex>`, down to
  `<hex>`, so a bare-SHA endpoint still matches; one value may be a prefix
  of the other);
- the line says `changed: ...` (the script's own output pasted unreviewed);
- the line is anything other than `clean` or `reviewed: <non-blank reason>`.

Exits 0 otherwise, 2 on bad usage.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap  # noqa: E402
from _git_subprocess import endpoints_match  # noqa: E402

TRUST_DIFF_RE = re.compile(
    r"Trust diff:\s*(?P<old>\S+)\.\.(?P<new>\S+)\s+(?P<result>[^\n]*)",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def check(body: str, old_answers_text: str, new_answers_text: str) -> list[str]:
    """Every failure this PR's "Trust diff" record has against a fresh
    re-check of the answers files it actually carries."""
    old_answers = bootstrap.parse_answers(old_answers_text)
    new_answers = bootstrap.parse_answers(new_answers_text)
    old_commit = old_answers.get("_commit")
    new_commit = new_answers.get("_commit")
    if not old_commit or not new_commit or old_commit == new_commit:
        return []

    match = TRUST_DIFF_RE.search(body)
    if not match:
        return [
            'The PR body has no "Trust diff: <old>..<new> clean|changed: ...|reviewed: ..." '
            "line. Paste check_forge_sync_trust_diff.py's own last stdout line "
            '(.agents/skills/forge-sync/SKILL.md, "Check what `--trust` would run, '
            'before running it"), rewritten to "reviewed: ..." if it stopped you.'
        ]

    failures: list[str] = []
    if not endpoints_match(match["old"], old_commit) or not endpoints_match(match["new"], new_commit):
        failures.append(
            f'The "Trust diff" line\'s range ({match["old"]}..{match["new"]}) does not match '
            f"this PR's actual answers-file range ({old_commit}..{new_commit}). Re-run "
            "check_forge_sync_trust_diff.py (with --new matching this sync, if --vcs-ref "
            "was used) and paste its current output."
        )

    result = match["result"].strip()
    is_clean = result.lower() == "clean"
    is_reviewed = result.lower().startswith("reviewed:") and result[len("reviewed:") :].strip()
    if result.lower().startswith("changed:"):
        failures.append(
            'The "Trust diff" line still says "changed: ...": check_forge_sync_trust_diff.py '
            'found something to review and nothing has confirmed it was. Rewrite it to '
            '"reviewed: <paths> — <why it is safe to execute>" once you have actually read '
            "the diff it printed."
        )
    elif not (is_clean or is_reviewed):
        failures.append(
            'The "Trust diff" line\'s result must be "clean", or "reviewed: <non-blank '
            f'reason>" -- got {result!r}.'
        )
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check_forge_sync_trust_record.py BODY_FILE OLD_ANSWERS NEW_ANSWERS", file=sys.stderr)
        return 2
    body = _read(Path(argv[0]))
    old_answers_text = _read(Path(argv[1]))
    new_answers_text = _read(Path(argv[2]))

    failures = check(body, old_answers_text, new_answers_text)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
