#!/usr/bin/env python3
"""One call to set up a per-ticket git worktree off `origin/main`.

`implement-with-merge`'s "one worktree per ticket" step is plain git
(`fetch`, `worktree add -b`) plus a per-project set of symlinks into
shared, installed dependency directories, done by hand at every ticket.
This script collapses that into one idempotent call: fetch, create the
worktree, create the symlinks `worktree_shared_paths.txt` names, and
report whether the pre-commit hook needs installing.

`worktree_shared_paths.txt` is project-owned (`copier.yml`'s
`_skip_if_exists`): which directories to share is the project's answer,
never hardcoded here.

Usage:
    worktree_setup.py BRANCH [--path DIR] [--no-shared-paths]

Exit codes: 0 ready; 2 ready but the pre-commit hook is missing;
1 refused or failed, with nothing created.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import looks_like_flag, run_git  # noqa: E402

GIT_TIMEOUT = 60
SHARED_PATHS_FILE = Path("scripts/worktree_shared_paths.txt")


class Refused(Exception):
    """Validation failed before anything was created."""


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    full = ["git"] + (["-C", str(cwd)] if cwd is not None else []) + args
    return run_git(full, GIT_TIMEOUT)


def primary_checkout() -> Path:
    """The main checkout's root, resolved through `--git-common-dir` so this
    works the same run from inside another worktree: every worktree shares
    one common dir, which sits directly inside the primary checkout's own
    `.git`."""
    result = _run(["rev-parse", "--git-common-dir"])
    if result.returncode != 0:
        raise Refused(f"not a git repository: {result.stderr.strip()}")
    common_dir = Path(result.stdout.strip()).resolve()
    return common_dir.parent if common_dir.name == ".git" else common_dir


def validate_branch(branch: str) -> None:
    if looks_like_flag(branch):
        raise Refused(f"branch name {branch!r} looks like a flag")
    result = _run(["check-ref-format", "--branch", branch])
    if result.returncode != 0:
        raise Refused(f"{branch!r} is not a valid branch name")


def existing_worktree_path(root: Path, branch: str) -> Path | None:
    """The worktree path already checked out on `branch`, or None. Reads
    `git worktree list --porcelain` rather than guessing from a branch-to-
    path convention, so a worktree at an unexpected path is still found."""
    result = _run(["worktree", "list", "--porcelain"], cwd=root)
    if result.returncode != 0:
        raise Refused(f"cannot list worktrees: {result.stderr.strip()}")
    current_path: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree ") :]
        elif line.startswith("branch ") and current_path is not None:
            ref = line[len("branch ") :]
            if ref == f"refs/heads/{branch}":
                return Path(current_path)
    return None


def branch_exists(root: Path, branch: str) -> bool:
    result = _run(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root)
    return result.returncode == 0


def ensure_worktree(root: Path, branch: str, path: Path) -> Path:
    """Fetches `origin/main`, then creates the worktree or reuses it.
    Refuses (never force-resets, per `-b` not `-B`) when the branch
    already exists with no worktree, or with one at a different path, or
    when `path` exists but isn't a worktree at all."""
    existing = existing_worktree_path(root, branch)
    if existing is not None:
        if existing.resolve() != path.resolve():
            raise Refused(f"branch {branch!r} already has a worktree at {existing}, not {path}")
        return existing

    if path.exists():
        raise Refused(f"{path} exists but is not a worktree of branch {branch!r}")

    if branch_exists(root, branch):
        raise Refused(f"branch {branch!r} exists but has no worktree; look at it before reusing or deleting it")

    fetch = _run(["fetch", "origin", "main"], cwd=root)
    if fetch.returncode != 0:
        raise Refused(f"git fetch origin main failed: {fetch.stderr.strip()}")

    add = _run(["worktree", "add", "-b", branch, str(path), "origin/main"], cwd=root)
    if add.returncode != 0:
        raise Refused(f"git worktree add failed: {add.stderr.strip()}")
    return path


def read_shared_paths(root: Path) -> list[str]:
    seed = root / SHARED_PATHS_FILE
    if not seed.exists():
        return []
    entries = []
    for line in seed.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.append(line)
    return entries


def validate_shared_path(root: Path, entry: str) -> None:
    """Checked before anything is created: an absolute, `..`-containing or
    `.git`-prefixed entry, or one that isn't git-ignored in the primary
    checkout, could turn the symlink step into writing outside the
    repository or committing a symlink that something later dereferences
    as tracked content."""
    if entry.startswith("/"):
        raise Refused(f"worktree_shared_paths.txt entry {entry!r} must be relative, not absolute")
    parts = Path(entry).parts
    if ".." in parts:
        raise Refused(f"worktree_shared_paths.txt entry {entry!r} must not contain '..'")
    if parts and parts[0].startswith(".git"):
        raise Refused(f"worktree_shared_paths.txt entry {entry!r} must not start with '.git'")
    if not is_git_ignored(root, entry):
        raise Refused(f"worktree_shared_paths.txt entry {entry!r} is not git-ignored in the primary checkout")


def is_git_ignored(root: Path, entry: str) -> bool:
    result = _run(["check-ignore", "-q", "--", entry], cwd=root)
    return result.returncode == 0


def create_symlinks(root: Path, worktree: Path, entries: list[str]) -> list[str]:
    """Creates a symlink in `worktree` for every already-validated entry
    that exists in `root`, skipping (with a note) one that doesn't exist
    there yet. Returns the notes to print."""
    notes = []
    for entry in entries:
        source = root / entry
        if not source.exists():
            notes.append(f"skipped {entry}: not present in the primary checkout")
            continue
        target = worktree / entry
        if target.is_symlink():
            if target.resolve() == source.resolve():
                continue
            notes.append(f"skipped {entry}: a different symlink already exists")
            continue
        if target.exists():
            notes.append(f"left {entry}: a real file or directory is already there")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=source.is_dir())
    return notes


def hook_installed(worktree: Path) -> bool:
    result = _run(["rev-parse", "--git-path", "hooks/pre-commit"], cwd=worktree)
    if result.returncode != 0:
        return False
    hook_path = Path(result.stdout.strip())
    if not hook_path.is_absolute():
        hook_path = worktree / hook_path
    return hook_path.exists()


HOOK_MISSING = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch", help="Branch to create (fresh off origin/main) or reuse")
    parser.add_argument("--path", type=Path, default=None, help="Worktree path (default: ../<branch>)")
    parser.add_argument("--no-shared-paths", action="store_true", help="Skip creating the shared-path symlinks")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 2 on a usage error; reserve 2 for "ready, hook missing"
        # so an agent can't mistake a bad invocation for a ready worktree.
        return 1 if exc.code == 2 else (exc.code or 0)

    try:
        root = primary_checkout()
        validate_branch(args.branch)
        path = (args.path if args.path is not None else root.parent / args.branch).resolve()

        entries = [] if args.no_shared_paths else read_shared_paths(root)
        for entry in entries:
            validate_shared_path(root, entry)

        worktree = ensure_worktree(root, args.branch, path)
    except Refused as exc:
        print(f"worktree_setup: refused: {exc}", file=sys.stderr)
        return 1

    if entries:
        for note in create_symlinks(root, worktree, entries):
            print(f"worktree_setup: {note}")

    if not hook_installed(worktree):
        print(
            "worktree_setup: pre-commit hook is not installed in this worktree "
            "(build-thread-setup.md installs it)",
            file=sys.stderr,
        )
        print(f"worktree_setup: ready at {worktree}")
        return HOOK_MISSING
    print(f"worktree_setup: ready at {worktree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
