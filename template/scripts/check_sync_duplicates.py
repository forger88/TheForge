#!/usr/bin/env python3
"""Advisory sync-duplication scan.

A clean `copier update` or merge can duplicate a line that sits nowhere
near a conflict marker, which a reviewer scanning only the conflict hunks
would miss. This compares each changed file's working-tree line counts
against its count at the pre-sync commit and in the freshly rendered
template, and reports a line whose count grew past both: that is a
duplication the sync itself introduced, not one either side already had.

Usage: python3 scripts/check_sync_duplicates.py --base REV --render DIR [PATH ...]
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import looks_like_flag, run_git  # noqa: E402

MIN_LENGTH = 30
GIT_TIMEOUT = 30
_WORD_CHAR_RE = re.compile(r"\w")


def _is_markup_only(line: str) -> bool:
    """A line with no letter or digit (a fence, a closing brace, a rule of
    dashes) is markup, not duplicated prose, however long it runs."""
    return not _WORD_CHAR_RE.search(line)


def _reject_flag_like(base: str) -> None:
    if looks_like_flag(base):
        raise ValueError(f"--base begins with '-'; refusing to treat it as a git argument: {base!r}")


def _candidate_files(base: str, paths: list[Path]) -> list[Path]:
    if paths:
        return [p for p in paths if p.is_file()]
    _reject_flag_like(base)
    # `--` would make git treat `base` as a pathspec here, not a revision
    # (unlike ls-remote/clone's `--`), so a flag-like value would be
    # silently misread instead of refused; `--end-of-options` rejects it
    # outright while leaving a real revision argument unaffected.
    result = run_git(["git", "diff", "--name-only", "--end-of-options", base], GIT_TIMEOUT)
    if result.returncode != 0:
        raise ValueError(f"git diff against {base!r} failed: {result.stderr.strip()}")
    return [Path(line) for line in result.stdout.splitlines() if Path(line).is_file()]


def _line_counts(text: str) -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= MIN_LENGTH and not _is_markup_only(stripped):
            counts[stripped] += 1
    return counts


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _counts_at_base(base: str, file: Path) -> collections.Counter[str]:
    _reject_flag_like(base)
    result = run_git(["git", "show", "--end-of-options", f"{base}:{file.as_posix()}"], GIT_TIMEOUT)
    if result.returncode != 0:
        return collections.Counter()
    return _line_counts(result.stdout)


def _counts_in_render(render: Path, file: Path) -> collections.Counter[str]:
    text = _read_text(render / file)
    return _line_counts(text) if text is not None else collections.Counter()


def new_duplicates(base: str, render: Path, paths: list[Path]) -> list[tuple[Path, str, int]]:
    """Returns (file, line, count) for each line whose working-tree count
    exceeds both its count at `base` (0 if the file didn't exist there)
    and its count in `render` (0 if the file isn't in the render)."""
    found: list[tuple[Path, str, int]] = []
    for file in sorted(_candidate_files(base, paths)):
        text = _read_text(file)
        if text is None:
            continue
        working_counts = _line_counts(text)
        if not working_counts:
            continue
        base_counts = _counts_at_base(base, file)
        render_counts = _counts_in_render(render, file)
        for line, count in sorted(working_counts.items()):
            if count > base_counts.get(line, 0) and count > render_counts.get(line, 0):
                found.append((file, line, count))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="the pre-sync commit")
    parser.add_argument("--render", type=Path, required=True, help="the fresh template render to compare against")
    parser.add_argument("paths", nargs="*", type=Path, help="files to check; default is everything changed against --base")
    args = parser.parse_args(argv)

    try:
        hits = new_duplicates(args.base, args.render, args.paths)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for file, line, count in hits:
        print(
            f"{file}: duplicated {count} times, new since both the pre-sync commit and the render: {line!r}",
            file=sys.stderr,
        )
    if hits:
        print("This is advisory: fix the duplication, or explain it in the PR body if it's deliberate.", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
