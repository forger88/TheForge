#!/usr/bin/env python3
"""Enumerate, or verify a sync PR's handling of, every "For integrators"
step a TheForge release in a synced `_commit` range asked a downstream
project to act on.

`forge-sync` ("Walk the integrator steps") runs this script against a full
clone of `.copier-answers.yml`'s `_src_path` (the same clone "Hold SDLC
wording changes for the owner" already needs) to find every release in
`(OLD, NEW]` and every "For integrators" bullet each one carries, so the
sync PR can address each one explicitly instead of leaving it for the
integrator to notice by reading `docs/release-notes.md` themselves.

A release that shipped a machine-readable sidecar
(`docs/release-notes/<version>.integrator-steps.json`, written by the
`release-notes` skill's step 7) is read from that file, `breaking`/`refs`
included. A release with no sidecar (one tagged before this check existed)
falls back to the release's own `docs/release-notes.md` section: every
bullet under its "For integrators" heading that ends `(#N)` or
`(#N, #M, ...)` becomes an item (the first id is `item.id`, the rest
`item.refs`), flagged `breaking` when it falls inside that section's
"**Breaking changes:**" run (never for "**Breaking changes: none**").

Usage:
    check_integrator_steps.py --template DIR --old REV --new REV
    check_integrator_steps.py --template DIR --old REV --new REV --pr-body FILE

Both forms read `docs/release-notes.md` and
`docs/release-notes/*.integrator-steps.json` at repo root in DIR (an
existing clone of `_src_path`), never under a `template/` or other subdir
-- the release notes describe changes to TheForge itself, which is DIR's
own root, not the seed a generated project receives.

Without `--pr-body`: prints `Integrator steps: <old>..<new> N: <ids or
"none">`, then one `- #<id> (<version>)[ [breaking]]: <summary>` line per
item, oldest release first. Exits 1 when N > 0 (there is something to walk
the integrator through), 0 when the range introduced no release or no
release in range carries any "For integrators" item.

With `--pr-body FILE`: re-enumerates the same list, then checks that each
item's `#<id>` appears somewhere after a case-insensitive "Integrator
steps" marker line in FILE's text -- the same shape "SDLC wording held"
uses, but for this list. Exits 1 and prints one line per item missing from
the PR body (or, when the list is non-empty and FILE has no "Integrator
steps" marker at all, one line saying so); exits 0 when every item is
addressed, including the trivial case of an empty list.

Exits 2 on a bad `--old`/`--new` revision, a `--pr-body` file that does
not exist, or a malformed sidecar (JSON that isn't an object with an
`items` list of objects each carrying a string `id` and `summary`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import looks_like_flag, run_git  # noqa: E402

GIT_TIMEOUT = 60
RELEASE_NOTES = "docs/release-notes.md"
SIDECAR_DIR = "docs/release-notes"
VERSION_HEADING_RE = re.compile(r"^## v(?P<version>\d+\.\d+\.\d+)\b")
INTEGRATORS_HEADING_RE = re.compile(r"^### For integrators\s*$")
BREAKING_HEADING_RE = re.compile(r"^\*\*Breaking changes:?\s*(none)?\*\*\s*$", re.IGNORECASE)
SECTION_HEADING_RE = re.compile(r"^#{1,3} ")
# The trailing `(#N)` or `(#N, #M, ...)` a bullet ends with; group 1 is every
# `#<digits>` inside the parens, split out below -- a bullet citing more than
# one issue (this repo's own release notes do this) must not be silently
# dropped just because it carries more than one id.
BULLET_WITH_ID_RE = re.compile(r"^-\s.*\((?P<refs>#\d+(?:,\s*#\d+)*)\)\s*$")
ISSUE_NUMBER_RE = re.compile(r"#(\d+)")
INTEGRATOR_STEPS_MARKER_RE = re.compile(r"integrator steps", re.IGNORECASE)


class IntegratorStepsError(ValueError):
    """A revision can't be resolved, or a sidecar is malformed."""


@dataclass(frozen=True)
class Item:
    id: str
    version: str
    summary: str
    breaking: bool = False
    refs: tuple[str, ...] = ()


def _require_commit(template: Path, rev: str) -> None:
    result = run_git(
        ["git", "-C", str(template), "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}"],
        GIT_TIMEOUT,
    )
    if result.returncode != 0:
        raise IntegratorStepsError(f"{rev!r} is not a commit in {template}")


def _show(template: Path, rev: str, path: str) -> str | None:
    result = run_git(["git", "-C", str(template), "show", "--end-of-options", f"{rev}:{path}"], GIT_TIMEOUT)
    return result.stdout if result.returncode == 0 else None


def _release_tags_in_range(template: Path, old: str, new: str) -> list[str]:
    """Every tag that is an ancestor of `new` but not of `old` -- the
    releases a sync from `old` to `new` actually crosses -- oldest first."""
    merged = run_git(["git", "-C", str(template), "tag", "--merged", new], GIT_TIMEOUT)
    not_merged = run_git(["git", "-C", str(template), "tag", "--no-merged", old], GIT_TIMEOUT)
    if merged.returncode != 0 or not_merged.returncode != 0:
        raise IntegratorStepsError(f"could not list tags in {template} merged into {new} / not merged into {old}")
    in_range = set(merged.stdout.split()) & set(not_merged.stdout.split())
    if not in_range:
        return []

    def _sort_key(tag: str) -> tuple:
        result = run_git(["git", "-C", str(template), "log", "-1", "--format=%ct", "--end-of-options", tag], GIT_TIMEOUT)
        return (result.stdout.strip() or "0", tag)

    return sorted(in_range, key=_sort_key)


def _sidecar_items(template: Path, tag: str, version: str) -> list[Item] | None:
    raw = _show(template, tag, f"{SIDECAR_DIR}/{version}.integrator-steps.json")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        items_raw = data["items"]
        items = [
            Item(
                id=str(item["id"]),
                version=version,
                summary=str(item["summary"]),
                breaking=bool(item.get("breaking", False)),
                refs=tuple(str(ref) for ref in item.get("refs", ())),
            )
            for item in items_raw
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IntegratorStepsError(f"{tag}:{SIDECAR_DIR}/{version}.integrator-steps.json is malformed: {exc}") from exc
    return items


def _fallback_items(template: Path, tag: str, version: str) -> list[Item]:
    notes = _show(template, tag, RELEASE_NOTES)
    if notes is None:
        return []
    lines = notes.splitlines()
    in_version = False
    in_integrators = False
    breaking = False
    breaking_bullet_seen = False
    items: list[Item] = []
    for line in lines:
        version_match = VERSION_HEADING_RE.match(line)
        if version_match:
            in_version = version_match["version"] == version
            in_integrators = False
            continue
        if not in_version:
            continue
        if INTEGRATORS_HEADING_RE.match(line):
            in_integrators = True
            breaking = False
            breaking_bullet_seen = False
            continue
        if in_integrators and SECTION_HEADING_RE.match(line):
            in_integrators = False
            continue
        if not in_integrators:
            continue
        # "**Breaking changes:**" (no "none") starts a run of breaking
        # bullets; the section shape (`release-notes/SKILL.md.jinja`) puts
        # a blank line both before that run (the heading's own trailing
        # blank) and after it (before the plain bullets that follow), with
        # no heading of its own between the two bullet runs -- so the
        # *first* bullet seen after the heading starts the run, and the
        # first blank line seen *after that first bullet* ends it.
        if BREAKING_HEADING_RE.match(line):
            breaking = "none" not in line.lower()
            breaking_bullet_seen = False
            continue
        if not line.strip():
            if breaking_bullet_seen:
                breaking = False
            continue
        bullet_match = BULLET_WITH_ID_RE.match(line)
        if bullet_match:
            if breaking:
                breaking_bullet_seen = True
            refs = ISSUE_NUMBER_RE.findall(bullet_match["refs"])
            items.append(
                Item(
                    id=refs[0],
                    version=version,
                    summary=line[2:].strip(),
                    breaking=breaking,
                    refs=tuple(refs[1:]),
                )
            )
    return items


def collect(template: Path, old: str, new: str) -> list[Item]:
    """Every "For integrators" item from every release in `(old, new]`,
    oldest release first, deduped by id (first occurrence wins)."""
    _require_commit(template, old)
    _require_commit(template, new)
    items: list[Item] = []
    seen: set[str] = set()
    for tag in _release_tags_in_range(template, old, new):
        version = tag.lstrip("v")
        release_items = _sidecar_items(template, tag, version)
        if release_items is None:
            release_items = _fallback_items(template, tag, version)
        for item in release_items:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items


def _check_pr_body(body: str, items: list[Item]) -> list[str]:
    marker = INTEGRATOR_STEPS_MARKER_RE.search(body)
    if not items:
        return []
    if not marker:
        return ['The PR body has no "Integrator steps" section, and this sync range carries integrator steps.']
    addressed_text = body[marker.start() :]
    failures = []
    for item in items:
        if f"#{item.id}" not in addressed_text:
            failures.append(
                f'#{item.id} ({item.version}) is not addressed in the PR body\'s "Integrator steps" section: '
                f"{item.summary}"
            )
    return failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], add_help=False)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--pr-body", type=Path, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    for value in (args.old, args.new):
        if looks_like_flag(value):
            print(f"error: revision begins with '-'; refusing to pass it to git: {value!r}", file=sys.stderr)
            return 2

    try:
        items = collect(args.template, args.old, args.new)
    except IntegratorStepsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.pr_body is not None:
        if not args.pr_body.is_file():
            print(f"error: {args.pr_body} does not exist", file=sys.stderr)
            return 2
        body = args.pr_body.read_text(encoding="utf-8", errors="replace")
        failures = _check_pr_body(body, items)
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1 if failures else 0

    ids = ", ".join(item.id for item in items) or "none"
    print(f"Integrator steps: {args.old}..{args.new} {len(items)}: {ids}")
    for item in items:
        flag = " [breaking]" if item.breaking else ""
        print(f"- #{item.id} ({item.version}){flag}: {item.summary}")
    return 1 if items else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
