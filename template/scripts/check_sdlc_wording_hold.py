#!/usr/bin/env python3
"""Verify a forge-sync PR's SDLC-statement accounting mechanically.

`forge-sync`'s "Hold SDLC wording changes for the owner" step
(`.agents/skills/forge-sync/SKILL.md`) is the one place a sync is allowed to
touch `docs/software-development-lifecycle.md` at all: it reverts every
`- **SDLC-NNN**: ...` statement `copier update` reworded back to its
pre-sync text, and records what it held (or "none") in the sync PR body
under "SDLC upstream changes" and "SDLC wording held" (`.agents/skills/
forge-sync/SKILL.md`, "Review and merge"). That step was purely
procedural -- nothing confirmed it actually ran before the PR merged.
Comparing only the project's own before/after, with no independent view of
what upstream actually changed, also cannot tell "upstream didn't change
this" apart from "upstream changed it and a merge conflict, resolved before
this check ever ran, already silently matched or diverged from the new
text" (`docs/security/threat-model.md`, T15) -- a before/after diff alone
can read as clean even when upstream changed several statements.

Usage:
    check_sdlc_wording_hold.py BODY_FILE OLD_ANSWERS NEW_ANSWERS OLD_DOC NEW_DOC UPSTREAM_OLD_DOC UPSTREAM_NEW_DOC

BODY_FILE holds the PR's body text. OLD_ANSWERS/NEW_ANSWERS are
`.copier-answers.yml`'s content at the PR's base and head. OLD_DOC/NEW_DOC
are the project's own lifecycle doc at the PR's base and head (regardless
of whether that file appears in the PR's own changed-file list -- its
*content* is needed either way to tell a real revert from a no-op).
UPSTREAM_OLD_DOC/UPSTREAM_NEW_DOC are the upstream template's lifecycle doc
at the two `_commit`s, fetched by the caller (the same clone-or-fetch this
project's own forge-sync skill or merge-scan already does for `_src_path`,
since a private `_src_path` and the credentials available to fetch it are
this check's caller's problem, not this script's).

The trigger is OLD_ANSWERS'/NEW_ANSWERS' own `_commit` value changing --
never a PR-body marker, and never whether the lifecycle doc happens to
appear in the PR's changed-file list, which is exactly the gap a
file-list-gated trigger leaves (the doc's own before/after can end up
identical even though upstream changed several statements, so such a
trigger sees nothing to check). Exits 0 with nothing printed for any PR
whose `_commit` doesn't change or is missing from either answers file
(a retrofit or first copy, the same convention
`check_forge_sync_trust_record.py` uses), including one that happens to
also touch the lifecycle doc for an unrelated reason.

Exits 1 when:
- the PR body has no `SDLC upstream changes: <old>..<new> held: ...;
  current: ...` line, or its `<old>..<new>` range doesn't match the
  answers files' own `_commit` change (allowing a `git describe` suffix,
  the same normalisation `check_forge_sync_trust_record.py` uses);
- its `held`/`current` lists don't equal `account()`, freshly recomputed
  from the four doc texts;
- `account()` reports any statement as `unheld` or `local_only` -- an
  upstream change the sync let through unreverted, or any other SDLC
  wording edit riding the sync PR with no matching upstream change --
  whatever the PR body claims (both are failures: see `Accounting`'s own
  docstring for why `local_only` is one too);
- the PR body's "SDLC wording held" line is missing or blank (the step
  must say "none" explicitly, even when there was nothing to hold), or is
  "none" while `account()` reports anything to hold at all.

Exits 2 when any of the four doc texts still carries an unresolved
merge-conflict marker (`account()`'s own refusal: a conflict resolved by
picking a side before this check runs is exactly the shape it exists to
catch, not a doc to compare as if already resolved).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap  # noqa: E402
import check_sdlc_wording_changes as wording  # noqa: E402
from _git_subprocess import endpoints_match  # noqa: E402

HELD_LINE_RE = re.compile(r"SDLC wording held[^:\n]*:[ \t]*(?P<value>[^\n]*)", re.IGNORECASE)
UPSTREAM_CHANGES_RE = re.compile(
    r"SDLC upstream changes:\s*(?P<old>\S+)\.\.(?P<new>\S+)\s+held:\s*(?P<held>[^;\n]*);\s*current:\s*(?P<current>[^\n]*)",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _parse_id_list(raw: str) -> set[str]:
    raw = raw.strip()
    if not raw or raw.lower() == "none":
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def check(
    body: str,
    old_answers_text: str,
    new_answers_text: str,
    old_doc: str,
    new_doc: str,
    upstream_old_doc: str,
    upstream_new_doc: str,
) -> list[str]:
    """Every failure this PR's SDLC-statement accounting has against a
    fresh re-check of the four doc texts it actually carries. Raises
    `check_sdlc_wording_changes.ConflictMarkersError` (a caller's exit-2
    case) when any of the four still carries an unresolved marker."""
    old_answers = bootstrap.parse_answers(old_answers_text)
    new_answers = bootstrap.parse_answers(new_answers_text)
    old_commit = old_answers.get("_commit")
    new_commit = new_answers.get("_commit")
    if not old_commit or not new_commit or old_commit == new_commit:
        return []

    accounting = wording.account(upstream_old_doc, upstream_new_doc, old_doc, new_doc)

    failures: list[str] = []

    match = UPSTREAM_CHANGES_RE.search(body)
    if not match:
        failures.append(
            'The PR body has no "SDLC upstream changes: <old>..<new> held: ...; current: ..." '
            "line. Run check_sdlc_wording_changes.py's --template mode and paste its first "
            'line (.agents/skills/forge-sync/SKILL.md, "Hold SDLC wording changes for the owner").'
        )
    else:
        if not endpoints_match(match["old"], old_commit) or not endpoints_match(match["new"], new_commit):
            failures.append(
                f'The "SDLC upstream changes" line\'s range ({match["old"]}..{match["new"]}) does not '
                f"match this PR's actual answers-file range ({old_commit}..{new_commit}). Re-run "
                "check_sdlc_wording_changes.py's --template mode and paste its current first line."
            )
        reported_held = _parse_id_list(match["held"])
        reported_current = _parse_id_list(match["current"])
        if reported_held != set(accounting.to_hold):
            failures.append(
                f'The "SDLC upstream changes" line\'s held list ({sorted(reported_held) or "none"}) does not '
                f"match what upstream actually changed between the two commits "
                f'({sorted(accounting.to_hold) or "none"}).'
            )
        if reported_current != set(accounting.current):
            failures.append(
                f'The "SDLC upstream changes" line\'s current list ({sorted(reported_current) or "none"}) does '
                f'not match the recomputed one ({sorted(accounting.current) or "none"}).'
            )

    if accounting.unheld:
        failures.append(
            f"Upstream changed {', '.join(accounting.unheld)} between {old_commit} and {new_commit}, and "
            "the synced text still differs from this PR's own pre-sync text for at least one of them. "
            'A forge-sync PR must revert every such statement\'s wording to its pre-sync text '
            '(.agents/skills/forge-sync/SKILL.md, "Hold SDLC wording changes for the owner", step 3) '
            "before it merges, whatever the PR body says."
        )
    if accounting.local_only:
        failures.append(
            f"{', '.join(accounting.local_only)} changed between this PR's pre-sync and synced lifecycle "
            "doc with no matching upstream change. Only the owner approves any SDLC statement's wording "
            'changing at all (.forge/process-and-evidence.md, "Process changes follow the lifecycle doc"); '
            "a sync PR carries none of it, whatever caused the change."
        )

    held_match = HELD_LINE_RE.search(body)
    if not held_match or not held_match["value"].strip():
        failures.append(
            'The PR body has no "SDLC wording held" line, or it\'s blank. '
            'Record "none", or each held statement and the lifecycle-doc PR '
            "it moved to, even when nothing was held."
        )
    elif accounting.to_hold and held_match["value"].strip().lower() == "none":
        failures.append(
            f'The "SDLC wording held" line says "none", but upstream changed '
            f"{', '.join(accounting.to_hold)} between {old_commit} and {new_commit}. Name each held "
            "statement and the lifecycle-doc PR it moved to, even when the revert already matches "
            "pre-sync text."
        )
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 7:
        print(
            "usage: check_sdlc_wording_hold.py BODY_FILE OLD_ANSWERS NEW_ANSWERS OLD_DOC NEW_DOC "
            "UPSTREAM_OLD_DOC UPSTREAM_NEW_DOC",
            file=sys.stderr,
        )
        return 2
    body, old_answers_text, new_answers_text, old_doc, new_doc, upstream_old_doc, upstream_new_doc = (
        _read(Path(p)) for p in argv
    )

    try:
        failures = check(body, old_answers_text, new_answers_text, old_doc, new_doc, upstream_old_doc, upstream_new_doc)
    except wording.ConflictMarkersError as exc:
        print(f"check_sdlc_wording_hold: {exc}", file=sys.stderr)
        return 2
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
