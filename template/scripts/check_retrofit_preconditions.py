#!/usr/bin/env python3
"""Retrofit-precondition guard (`.agents/skills/retrofit-existing-project/
SKILL.md`, Phase 0).

Checks, offline, that a target repository is actually a retrofit target and
not already a forge consumer, and that its working tree is clean before the
one-shot `copier copy` runs against it. This catches the shape of mistake an
agent under time pressure could otherwise make: a stray `.copier-answers.yml`
left over from an earlier abandoned attempt, a half-finished prior
entrypoint migration, or a dirty tree that would carry stray edits into the
retrofit's diff.

This script does not check for an open pull request on the target touching
a template-shipped path, or confirm the target's standing trackers have been
retitled for reuse (`bootstrap.py`'s `ensure_trackers`) -- both need live
GitHub state this script, deliberately standard-library only, does not
reach for. The skill's Phase 0 covers those by hand.

Usage: python3 scripts/check_retrofit_preconditions.py [--root DIR]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import clean_git_env  # noqa: E402

ANSWERS_NAME = ".copier-answers.yml"
CLAUDE_NAME = "CLAUDE.md"
OLD_IMPORT_RE = re.compile(r"^@\.forge/")

ALREADY_CONSUMER_REMEDY = "This target is already a forge consumer; use forge-sync, not this skill."
DIRTY_TREE_REMEDY = "Commit or stash (git stash push -u) before running the retrofit."


def problems(root: Path) -> list[str]:
    """Returns one human-readable line per violation; an empty list means
    the target is ready for Phase 2's `copier copy`."""
    errors: list[str] = []

    if (root / ANSWERS_NAME).is_file():
        errors.append(f"{ANSWERS_NAME} already exists at {root}. {ALREADY_CONSUMER_REMEDY}")

    claude_path = root / CLAUDE_NAME
    if claude_path.is_file():
        claude_text = claude_path.read_text(encoding="utf-8")
        if any(OLD_IMPORT_RE.match(line) for line in claude_text.splitlines()):
            errors.append(f"{CLAUDE_NAME} already has an @.forge/ import line. {ALREADY_CONSUMER_REMEDY}")

    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
        env=clean_git_env(),
    )
    if status.returncode != 0:
        errors.append(f"git status failed in {root}: {status.stderr.strip() or status.returncode}")
    elif status.stdout.strip():
        errors.append(f"Working tree at {root} is not clean. {DIRTY_TREE_REMEDY}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    errors = problems(args.root)
    for line in errors:
        print(line, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
