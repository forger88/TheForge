#!/usr/bin/env python3
"""Find every SDLC statement whose wording a sync would change.

Usage:
    check_sdlc_wording_changes.py OLD_DOC NEW_DOC
    check_sdlc_wording_changes.py --template DIR [--subdir D] --old REV --new REV PRE_SYNC SYNCED

`forge-sync`'s "Hold SDLC wording changes for the owner" step runs the first
form against the lifecycle doc as rendered at the project's old and new
`_commit`, to find any `- **SDLC-NNN**: ...` statement copier update would
add, remove or reword, before any of it reaches the sync PR
(`.forge/process-and-evidence.md`, "Process changes follow the lifecycle
doc" (Never): only the owner approves a change to an SDLC statement's
wording or meaning).

Exits 1 and lists each changed statement's id and both versions of its text
("(absent)" for a statement added or removed) when any differ; 0 otherwise.
A missing file reads as holding no statements, so a doc that doesn't exist
yet at one of the two commits is not an error. Exits 2 when either input
still carries a merge-conflict marker (`<<<<<<<`/`=======`/`>>>>>>>`): a
conflict resolved by picking a side before this check runs is exactly the
silent-miss shape this script exists to catch, not a doc to compare as if
it had already been resolved correctly.

The second form accounts for the project's own pre-sync/synced diff against
what the *upstream* template itself changed between the two `_commit`s,
read from DIR, an existing full clone of `.copier-answers.yml`'s
`_src_path` (the same clone "Hold SDLC wording changes for the owner" step
2 already asks for). Comparing only the project's own before/after misses a
statement that upstream changed but that the project's pre-sync copy had
already drifted to match (or already differed from) for an unrelated
reason -- this form is the positive check: every statement upstream
actually changed is accounted for as either held or already current, never
simply absent from the report. Prints one line, `SDLC upstream changes:
<old>..<new> held: <ids or "none">; current: <ids or "none">`, then one
line per statement in `unheld` or `local_only` (see `account()`). Exits 1
while `unheld` or `local_only` is non-empty -- an upstream change that
still differs from the project's pre-sync text was not reverted, or the
sync PR carries some other SDLC wording change neither the project's
pre-sync copy nor upstream's new text explains, and only the owner
approves either (`.forge/process-and-evidence.md`, above) -- 2 on a bad
or unresolvable `--old`/`--new` revision or a conflict marker in any of
the four texts."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import looks_like_flag, run_git  # noqa: E402

STATEMENT_START = re.compile(r"^- \*\*(SDLC-\d+)\*\*( \*\([^)]*\)\*)?: (.*)$")
CONTINUATION = re.compile(r"^\s{2,}\S")
# Only the distinctive open/close markers, never the bare "=======" divider
# alone: git always leaves all three when a conflict is unresolved, and a
# bare seven-equals line can otherwise be a Markdown setext heading
# underline.
CONFLICT_MARKER_RE = re.compile(r"^(<<<<<<< |>>>>>>> )", re.M)
LIFECYCLE_DOC = "docs/software-development-lifecycle.md"
GIT_TIMEOUT = 60


class ConflictMarkersError(ValueError):
    """A doc passed to `account()` still carries unresolved merge-conflict
    markers (`<<<<<<<`/`=======`/`>>>>>>>`): treating it as resolved text
    would silently compare the wrong statement text."""


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


def _sort_key(statement_id: str) -> int:
    return int(statement_id.split("-")[1])


def changed(old_text: str, new_text: str) -> list[tuple[str, str, str]]:
    """Every SDLC-NNN whose text differs, as (id, old text, new text)."""
    old, new = statements(old_text), statements(new_text)
    ids = sorted(set(old) | set(new), key=_sort_key)
    return [(sid, old.get(sid, ""), new.get(sid, "")) for sid in ids if old.get(sid, "") != new.get(sid, "")]


def _check_no_conflict_markers(label: str, text: str) -> None:
    if CONFLICT_MARKER_RE.search(text):
        raise ConflictMarkersError(f"{label} still carries an unresolved merge-conflict marker")


@dataclass(frozen=True)
class Accounting:
    """`account()`'s result. `to_hold` is every statement upstream changed
    between the two `_commit`s; `current` is the subset the project's
    pre-sync text already matches upstream's new wording for (so there was
    nothing to hold); `unheld` is the subset of `to_hold` whose synced text
    still differs from pre-sync -- an upstream change that was not reverted
    before merge; `local_only` is every statement that changed between
    pre-sync and synced without a matching upstream change -- a sync PR
    carrying its own SDLC wording edit, coincidentally or not. Both
    `unheld` and `local_only` are failures of this check: only the owner
    approves any SDLC statement's wording changing at all
    (`.forge/process-and-evidence.md`, "Process changes follow the
    lifecycle doc"), whatever caused the change."""

    to_hold: list[str]
    current: list[str]
    unheld: list[str]
    local_only: list[str]


def account(upstream_old: str, upstream_new: str, pre_sync: str, synced: str) -> Accounting:
    """Accounts for every SDLC statement upstream changed between
    `upstream_old` and `upstream_new` against what this sync's own
    `pre_sync`/`synced` pair actually did with it -- the positive check
    `check_sdlc_wording_changes.py`'s plain before/after diff cannot give
    on its own, since that diff only sees the project's two files and has
    no way to tell "upstream didn't change this" apart from "upstream
    changed it and the project's pre-sync copy already happened to match
    or differ"."""
    for label, text in (
        ("the upstream old doc", upstream_old),
        ("the upstream new doc", upstream_new),
        ("the pre-sync doc", pre_sync),
        ("the synced doc", synced),
    ):
        _check_no_conflict_markers(label, text)

    upstream_changed = {statement_id for statement_id, _, _ in changed(upstream_old, upstream_new)}
    upstream_new_statements = statements(upstream_new)
    pre_sync_statements, synced_statements = statements(pre_sync), statements(synced)
    all_ids = set(pre_sync_statements) | set(synced_statements) | upstream_changed

    current = sorted(
        (sid for sid in upstream_changed if pre_sync_statements.get(sid, "") == upstream_new_statements.get(sid, "")),
        key=_sort_key,
    )
    to_hold = sorted(upstream_changed - set(current), key=_sort_key)
    unheld = sorted(
        (sid for sid in to_hold if synced_statements.get(sid, "") != pre_sync_statements.get(sid, "")),
        key=_sort_key,
    )
    local_only = sorted(
        (
            sid
            for sid in all_ids - upstream_changed
            if pre_sync_statements.get(sid, "") != synced_statements.get(sid, "")
        ),
        key=_sort_key,
    )
    return Accounting(to_hold=to_hold, current=current, unheld=unheld, local_only=local_only)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _require_commit(template: Path, rev: str) -> None:
    # A rev git can't resolve would otherwise read as "file absent at that
    # rev" and pass silently (check_held_sdlc_prose.py's _require_commit
    # guards the same hazard the same way).
    result = run_git(
        ["git", "-C", str(template), "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}"],
        GIT_TIMEOUT,
    )
    if result.returncode != 0:
        raise ValueError(f"{rev!r} is not a commit in {template}")


def _doc_at(template: Path, subdir: str, rev: str) -> str:
    _require_commit(template, rev)
    doc = f"{subdir}/{LIFECYCLE_DOC}" if subdir else LIFECYCLE_DOC
    result = run_git(["git", "-C", str(template), "show", "--end-of-options", f"{rev}:{doc}"], GIT_TIMEOUT)
    return result.stdout if result.returncode == 0 else ""


def _run_account_mode(args: argparse.Namespace) -> int:
    if args.old is None or args.new is None or len(args.docs) != 2:
        print(
            "usage: check_sdlc_wording_changes.py --template DIR [--subdir D] --old REV --new REV PRE_SYNC SYNCED",
            file=sys.stderr,
        )
        return 2
    for value in (args.old, args.new):
        if looks_like_flag(value):
            print(f"error: revision begins with '-'; refusing to pass it to git: {value!r}", file=sys.stderr)
            return 2
    pre_sync_path, synced_path = (Path(p) for p in args.docs)
    try:
        upstream_old = _doc_at(args.template, args.subdir.strip("/"), args.old)
        upstream_new = _doc_at(args.template, args.subdir.strip("/"), args.new)
        accounting = account(upstream_old, upstream_new, _read(pre_sync_path), _read(synced_path))
    except ValueError as exc:  # ConflictMarkersError is a ValueError subclass
        print(f"error: {exc}", file=sys.stderr)
        return 2

    held = ", ".join(accounting.to_hold) or "none"
    current = ", ".join(accounting.current) or "none"
    print(f"SDLC upstream changes: {args.old}..{args.new} held: {held}; current: {current}")
    for statement_id in accounting.unheld:
        print(f"{statement_id}: upstream changed this and it was not reverted to pre-sync text before merge")
    for statement_id in accounting.local_only:
        print(f"{statement_id}: changed locally with no matching upstream change (not held by this check)")
    return 1 if accounting.unheld else 0


def _run_plain_diff_mode(args: argparse.Namespace) -> int:
    if len(args.docs) != 2:
        print("usage: check_sdlc_wording_changes.py OLD_DOC NEW_DOC", file=sys.stderr)
        return 2
    old_path, new_path = (Path(p) for p in args.docs)
    old_text, new_text = _read(old_path), _read(new_path)
    try:
        _check_no_conflict_markers("OLD_DOC", old_text)
        _check_no_conflict_markers("NEW_DOC", new_text)
    except ConflictMarkersError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    diffs = changed(old_text, new_text)
    for statement_id, old_statement, new_statement in diffs:
        print(f"{statement_id}: changed")
        print(f"  old: {old_statement or '(absent)'}")
        print(f"  new: {new_statement or '(absent)'}")
    return 1 if diffs else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], add_help=False)
    parser.add_argument("--template", type=Path, default=None)
    parser.add_argument("--subdir", default="template")
    parser.add_argument("--old", default=None)
    parser.add_argument("--new", default=None)
    parser.add_argument("docs", nargs="*")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.template is not None:
        return _run_account_mode(args)
    return _run_plain_diff_mode(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
