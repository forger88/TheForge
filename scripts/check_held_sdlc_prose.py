#!/usr/bin/env python3
"""Find synced prose that still carries held SDLC wording.

`forge-sync`'s hold step reverts a held statement's own text; this finds the
lines of other files, changed by the same upstream commits, that the sync
still brings in or takes out. Whole-line matches only (whitespace collapsed),
so a reworded dependent line still needs the skill's read-through.

Usage: python3 scripts/check_held_sdlc_prose.py --template DIR [--subdir D]
       --old REV --new REV --base REV SDLC-NNN [SDLC-NNN ...]

DIR is a full clone of `_src_path`; OLD and NEW are the old and new `_commit`;
BASE is the project's pre-sync commit. Run from the project root, after
`copier update` and again after reverting. Exits 1 listing each hit, 0 when
clean, 2 on bad input.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import looks_like_flag, run_git  # noqa: E402
from check_sdlc_wording_changes import statements  # noqa: E402

MIN_LENGTH = 30
GIT_TIMEOUT = 60
LIFECYCLE_DOC = "docs/software-development-lifecycle.md"
_WORD_CHAR_RE = re.compile(r"\w")
_WHITESPACE_RE = re.compile(r"\s+")
_HELD_ID_RE = re.compile(r"^SDLC-\d+$")


def _normalize(line: str) -> str | None:
    """The comparable form of a line, or None for a line too short, markup-only or Jinja to match on."""
    text = _WHITESPACE_RE.sub(" ", line).strip()
    if len(text) < MIN_LENGTH or not _WORD_CHAR_RE.search(text) or "{{" in text or "{%" in text:
        return None
    return text


def _lines(text: str | None) -> set[str]:
    return {n for n in map(_normalize, (text or "").splitlines()) if n}


def _git(args: list[str]) -> str | None:
    result = run_git(["git", *args], GIT_TIMEOUT)
    return result.stdout if result.returncode == 0 else None


def _show(repo: list[str], rev: str, path: str) -> str | None:
    return _git([*repo, "show", "--end-of-options", f"{rev}:{path}"])


def _require_commit(repo: list[str], rev: str, where: str) -> None:
    # A rev git can't resolve would otherwise read as "file absent" and pass silently.
    if _git([*repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}"]) is None:
        raise ValueError(f"{rev!r} is not a commit in {where}")


def held_commits(template: Path, subdir: str, old: str, new: str, held: set[str]) -> list[str]:
    """Every non-merge commit in OLD..NEW, oldest first, that changed a held statement's text."""
    repo = ["-C", str(template)]
    shallow = _git([*repo, "rev-parse", "--is-shallow-repository"])
    if shallow is None:
        raise ValueError(f"{template} is not a git repository")
    if shallow != "false\n":
        raise ValueError(f"{template} is not a full clone; a shallow one hides each commit's parent")
    doc = f"{subdir}/{LIFECYCLE_DOC}" if subdir else LIFECYCLE_DOC
    listing = _git([*repo, "rev-list", "--reverse", "--no-merges", "--end-of-options", f"{old}..{new}", "--", doc])
    if listing is None:
        raise ValueError(f"git rev-list {old}..{new} failed in {template}")
    found = []
    for commit in listing.split():
        before = statements(_show(repo, f"{commit}^", doc) or "")
        after = statements(_show(repo, commit, doc) or "")
        if any(before.get(sid) != after.get(sid) for sid in held):
            found.append(commit)
    return found


def _changed_lines(template: Path, subdir: str, commit: str) -> dict[str, tuple[set[str], set[str]]]:
    """Map each project-relative path the commit touched, bar the lifecycle doc, to its (added, removed) lines."""
    pathspec = [subdir] if subdir else []
    # Fixed output options: a user's color, prefix or external-diff config would otherwise hide every header.
    diff = _git([
        "-C", str(template), "-c", "core.quotePath=false", "show", "--format=", "--no-renames", "--no-color",
        "--no-ext-diff", "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/", "-U0",
        "--end-of-options", commit, "--", *pathspec,
    ])
    if diff is None:
        raise ValueError(f"git show {commit} failed in {template}")
    changes: dict[str, tuple[set[str], set[str]]] = {}
    path: str | None = None
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path, in_header = None, True
        elif in_header and line.startswith(("--- ", "+++ ")):
            # A deleted file's "+++" is /dev/null, so its "---" path is the one kept.
            name = line[4:].rstrip("\t")
            if name != "/dev/null":
                path = _project_path(name[2:], subdir)
        elif line.startswith("@@"):
            in_header = False
        elif not in_header and path and path != LIFECYCLE_DOC and line[:1] in ("+", "-"):
            added, removed = changes.setdefault(path, (set(), set()))
            normalized = _normalize(line[1:])
            if normalized:
                (added if line[0] == "+" else removed).add(normalized)
    return changes


def _project_path(template_path: str, subdir: str) -> str:
    path = template_path.removeprefix(f"{subdir}/") if subdir else template_path
    return path.removesuffix(".jinja")


def find_leaks(template: Path, subdir: str, old: str, new: str, base: str, held: set[str]) -> list[str]:
    """One report line per synced line that still carries a held commit's change."""
    for rev in (old, new, base):
        if looks_like_flag(rev):
            raise ValueError(f"revision begins with '-'; refusing to pass it to git: {rev!r}")
    _require_commit([], base, "this project")
    leaks = []
    for commit in held_commits(template, subdir, old, new, held):
        for path, (added, removed) in sorted(_changed_lines(template, subdir, commit).items()):
            synced_file = Path(path)
            synced = _lines(synced_file.read_text(encoding="utf-8", errors="replace") if synced_file.is_file() else None)
            pre_sync = _lines(_show([], base, path))
            for line in sorted((added & synced) - pre_sync):
                leaks.append(f"{path}: added by held commit {commit[:12]}: {line}")
            for line in sorted((removed & pre_sync) - synced):
                leaks.append(f"{path}: removed by held commit {commit[:12]}: {line}")
    return leaks


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--template", required=True, type=Path, help="local clone of the template repository")
    parser.add_argument("--subdir", default="template", help="the template's _subdirectory (default: template)")
    parser.add_argument("--old", required=True, help="the old _commit")
    parser.add_argument("--new", required=True, help="the new _commit")
    parser.add_argument("--base", required=True, help="the project's pre-sync commit")
    parser.add_argument("held", nargs="+", help="each held statement id, e.g. SDLC-012")
    args = parser.parse_args(argv)
    bad = [sid for sid in args.held if not _HELD_ID_RE.match(sid)]
    if bad:
        print(f"check_held_sdlc_prose: not a statement id: {', '.join(bad)}", file=sys.stderr)
        return 2
    try:
        leaks = find_leaks(args.template, args.subdir.strip("/"), args.old, args.new, args.base, set(args.held))
    except ValueError as error:
        print(f"check_held_sdlc_prose: {error}", file=sys.stderr)
        return 2
    for leak in leaks:
        print(leak)
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
