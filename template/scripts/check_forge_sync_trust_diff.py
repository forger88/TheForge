#!/usr/bin/env python3
"""Check whether a forge sync touches copier.yml's unsafe features or the
executable-content paths, before `copier update --trust` runs any of it.

`--trust` runs upstream's `copier.yml` tasks, migrations and Jinja
extensions, and copier update's ordinary conflict-resolution flow treats
every other file -- including `.claude/` hooks, the pre-commit config and
`scripts/` -- as plain text to merge, with nothing that singles out a change
to code that executes for its own review. This is read-only: it clones
`_src_path` to diff the old and new commits and never runs Copier or any
file it finds.

Usage: python3 scripts/check_forge_sync_trust_diff.py [--new REF]

With no --new, diffs against the ref `copier update` syncs to by default: the
latest release tag upstream has, or its HEAD when it has none. Pass --new <ref>
to match a `--vcs-ref <ref>` sync.

Exits 1 and prints the diff for each changed path when `copier.yml` or any
executable-content path differs between the project's current `_commit` and
REF, calling out a `_migrations` or `_jinja_extensions` key by name when the
new `copier.yml` adds or changes one. Exits 0 when none of those paths
changed, 2 on bad input or a git failure.

On exit 0 or 1, the last stdout line is a `Trust diff: <old>..<new> clean` or
`Trust diff: <old>..<new> changed: <paths>` record -- paste it into the sync
PR body (rewriting `changed:` to `reviewed: <why>` once the diff above has
actually been checked); `check_forge_sync_trust_record.py` verifies it
mechanically in CI. Exit 2 prints no record.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap  # noqa: E402
from _git_subprocess import (  # noqa: E402
    copier_yml_at,
    display_url,
    looks_like_flag,
    resolve_sync_target,
    run_git,
    source_url,
)

CLONE_TIMEOUT = 300
DIFF_TIMEOUT = 60

# Paths whose content Copier executes, or that a consumer's own tooling
# executes unreviewed once synced in: the root Copier config, the session
# hooks, the pre-commit config, every script `scripts/` ships, and every
# doc-build tool `docs/tools/` ships (document_build.py/render_diagrams.py
# render a project's docs by shelling out to pandoc/d2/weasyprint/mmdc;
# check_document_consistency.py and process_map.py each run as a pre-commit
# hook once `doc-build-setup`/`process-map-setup` wires them in).
EXECUTABLE_PATHS = (
    "copier.yml",
    "template/.claude/",
    "template/.pre-commit-config.yaml.jinja",
    "template/scripts/",
    "template/.github/workflows/",
    "template/docs/tools/",
)

UNSAFE_COPIER_KEYS = ("_migrations", "_jinja_extensions")
_TOP_LEVEL_KEY_RE = re.compile(r"^(_migrations|_jinja_extensions)\s*:")


def _unsafe_keys(copier_yml_text: str | None) -> dict[str, str]:
    """Each unsafe top-level key present in `copier_yml_text`, mapped to its header line
    plus every indented line under it, so a value-only edit inside the block (a changed
    list item, say, with the header line itself untouched) still counts as a change."""
    if not copier_yml_text:
        return {}
    found: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in copier_yml_text.splitlines():
        match = _TOP_LEVEL_KEY_RE.match(line)
        if match:
            current_key = match.group(1)
            found[current_key] = [line]
        elif current_key is not None and (line.startswith((" ", "\t")) or not line.strip()):
            found[current_key].append(line)
        else:
            current_key = None
    return {key: "\n".join(lines).strip() for key, lines in found.items()}


def check(repo: Path, old: str, new: str) -> tuple[list[str], list[str]]:
    """(changed paths, unsafe-key findings) between `old` and `new` in the clone at `repo`."""
    changed: list[str] = []
    findings: list[str] = []

    for path in EXECUTABLE_PATHS:
        diff_result = run_git(
            ["git", "-C", str(repo), "diff", "--end-of-options", f"{old}..{new}", "--", path],
            DIFF_TIMEOUT,
        )
        if diff_result.returncode == 0 and diff_result.stdout.strip():
            changed.append(path)
            print(f"--- {path} changed between {old} and {new} ---")
            print(diff_result.stdout)

    old_keys = _unsafe_keys(copier_yml_at(repo, old, DIFF_TIMEOUT, run_git))
    new_keys = _unsafe_keys(copier_yml_at(repo, new, DIFF_TIMEOUT, run_git))
    for key in UNSAFE_COPIER_KEYS:
        if new_keys.get(key) and new_keys.get(key) != old_keys.get(key):
            header = new_keys[key].splitlines()[0]
            findings.append(f"copier.yml now sets {key!r} ({header}): review before trusting it")

    return changed, findings


def _describe(repo: Path, rev: str) -> str | None:
    """`rev`'s `git describe --tags --always` form -- the same shape Copier
    writes into `_commit` on the next sync (a tag, `tag-N-gSHA`, or a bare
    short SHA) -- or None on a git failure. Split out of `main` to keep it
    under this repo's function-size cap."""
    result = run_git(
        ["git", "-C", str(repo), "describe", "--tags", "--always", "--end-of-options", rev],
        DIFF_TIMEOUT,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def record_line(old: str, new_described: str, changed: list[str]) -> str:
    """The ``Trust diff:`` sync PR body line `check_forge_sync_trust_record.py` parses back."""
    if changed:
        return f"Trust diff: {old}..{new_described} changed: {', '.join(changed)}"
    return f"Trust diff: {old}..{new_described} clean"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", default=None, help="upstream ref to diff against; defaults to the latest release tag, else upstream HEAD")
    args = parser.parse_args(argv)

    try:
        answers = bootstrap.read_answers()
    except (OSError, ValueError) as exc:
        print(f"error: could not read .copier-answers.yml: {exc}", file=sys.stderr)
        return 2

    src_path = answers.get("_src_path")
    old = answers.get("_commit")
    if not src_path or not old:
        print("error: missing _src_path or _commit in .copier-answers.yml", file=sys.stderr)
        return 2
    if looks_like_flag(src_path) or looks_like_flag(old) or (args.new and looks_like_flag(args.new)):
        print("error: a value begins with '-'; refusing to treat it as a git argument", file=sys.stderr)
        return 2

    url = source_url(src_path)

    try:
        new_ref = args.new
        if new_ref is None:
            target = resolve_sync_target(url, DIFF_TIMEOUT, run_git)
            if target is None:
                print(f"error: could not reach {display_url(url)}", file=sys.stderr)
                return 2
            new_ref = target.ref if target.tagged else None

        with tempfile.TemporaryDirectory() as tmpdir:
            clone_result = run_git(
                ["git", "clone", "--quiet", "--", url, tmpdir],
                CLONE_TIMEOUT,
            )
            if clone_result.returncode != 0:
                print(f"error: could not clone {display_url(url)}", file=sys.stderr)
                return 2

            repo = Path(tmpdir)
            local_new_ref = "refs/forge-sync-check/new"
            if new_ref is None:
                rev_result = run_git(
                    ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "--end-of-options", "HEAD"],
                    DIFF_TIMEOUT,
                )
                if rev_result.returncode != 0:
                    print("error: could not resolve upstream HEAD", file=sys.stderr)
                    return 2
                new = rev_result.stdout.strip()
            else:
                fetch_result = run_git(
                    ["git", "-C", str(repo), "fetch", "--quiet", "--", url, f"{new_ref}:{local_new_ref}"],
                    CLONE_TIMEOUT,
                )
                if fetch_result.returncode != 0:
                    print(f"error: could not fetch ref {new_ref!r} from {display_url(url)}", file=sys.stderr)
                    return 2
                new = local_new_ref

            verify_result = run_git(
                ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "--end-of-options", f"{old}^{{commit}}"],
                DIFF_TIMEOUT,
            )
            if verify_result.returncode != 0:
                print(f"error: {old} is not in {display_url(url)}'s history", file=sys.stderr)
                return 2

            changed, findings = check(repo, old, new)

            new_described = _describe(repo, new)
            if new_described is None:
                print(f"error: could not describe {new!r}", file=sys.stderr)
                return 2
    except subprocess.TimeoutExpired as exc:
        print(f"error: git command timed out after {exc.timeout:g}s", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not run git: {exc}", file=sys.stderr)
        return 2

    for finding in findings:
        print(f"finding: {finding}")

    if changed or findings:
        print(
            "check_forge_sync_trust_diff: review the diff above before running "
            "`copier update --trust`; it executes or merges unreviewed every path it touched"
        )
        print(record_line(old, new_described, changed))
        return 1

    print(f"check_forge_sync_trust_diff: no change under copier.yml or the executable-content paths ({old}..{new})")
    print(record_line(old, new_described, changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
