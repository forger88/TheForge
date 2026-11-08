#!/usr/bin/env python3
"""Forge drift check.

Read-only: reports how far this project's `_commit` is behind the ref a default
`copier update` would sync to (the latest release tag on `_src_path`, else
its HEAD), and whether the forge entrypoint is still in place.
Main Health runs this once a day and uses its result line to keep the held
sync ticket (`.agents/skills/watch-main-ci/SKILL.md`, "Forge drift check").
It never runs Copier and never passes or prints a credential.

Usage: python3 scripts/check_forge_drift.py [--max-subjects N]
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap  # noqa: E402
from check_forge_entrypoint import problems  # noqa: E402
from _git_subprocess import (  # noqa: E402
    copier_yml_at,
    display_url,
    looks_like_flag,
    resolve_sync_target,
    run_git,
    source_url,
)

DEFAULT_MAX_SUBJECTS = 20
LS_REMOTE_TIMEOUT = 60
CLONE_TIMEOUT = 300

_DESCRIBE_RE = re.compile(r"^.+-\d+-g([0-9a-fA-F]{7,40})$")
_BARE_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_SUBDIRECTORY_RE = re.compile(r"^_subdirectory:\s*(.+?)\s*$", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class Drift:
    commit: str | None
    upstream: str | None
    behind: int | None
    entrypoint_ok: bool
    subjects: list[str]
    error: str | None
    target: str | None = None
    unreleased: int | None = None


def commit_sha(commit: str) -> str | None:
    """Copier writes `_commit` as `git describe --tags --always`: a
    `<tag>-<n>-g<sha>` form, a bare short or full SHA, or (once tags exist
    with no commits since) a bare tag, which has no SHA of its own here and
    must be resolved by the caller against `refs/tags/<tag>`."""
    match = _DESCRIBE_RE.match(commit)
    if match:
        return match.group(1)
    if _BARE_SHA_RE.match(commit):
        return commit
    return None


def _sanitize_subject(subject: str) -> str:
    return _CONTROL_CHAR_RE.sub("", subject).strip()[:120]


def render_pathspec(clone_dir: str, upstream: str) -> list[str]:
    """Paths whose change can alter a render of `upstream`: the template
    subdirectory plus Copier's own config file. [] means "count every commit"."""
    try:
        text = copier_yml_at(clone_dir, upstream, CLONE_TIMEOUT, run_git)
        if text is None:
            return []

        match = _SUBDIRECTORY_RE.search(text)
        if not match:
            return []

        subdir = match.group(1).strip("'\"")
        if (
            not subdir
            or subdir == "."
            or ".." in subdir
            or subdir.startswith("/")
            or "{{" in subdir
            or "{%" in subdir
        ):
            return []

        return [f"{subdir}/", "copier.yml", "copier.yaml"]
    except subprocess.TimeoutExpired:
        return []


def drift(max_subjects: int = DEFAULT_MAX_SUBJECTS) -> Drift:
    entrypoint_ok = not problems(Path("."), template=False)
    commit: str | None = None

    def make(
        upstream: str | None = None,
        behind: int | None = None,
        subjects: list[str] | None = None,
        error: str | None = None,
        target: str | None = None,
        unreleased: int | None = None,
    ) -> Drift:
        return Drift(
            commit=commit,
            upstream=upstream,
            behind=behind,
            entrypoint_ok=entrypoint_ok,
            subjects=subjects if subjects is not None else [],
            error=error,
            target=target,
            unreleased=unreleased,
        )

    try:
        answers = bootstrap.read_answers()
    except (OSError, ValueError) as exc:
        # ValueError covers UnicodeDecodeError from a non-UTF-8 answers
        # file; neither carries a credential, so str(exc) is safe here.
        return make(error=f"could not read .copier-answers.yml: {exc}")

    src_path = answers.get("_src_path")
    commit = answers.get("_commit")

    if not src_path or not commit:
        return make(error="missing _src_path or _commit in .copier-answers.yml")

    if looks_like_flag(src_path):
        return make(error="_src_path begins with '-'; refusing to treat it as a git argument")

    url = source_url(src_path)

    try:
        sha = commit_sha(commit)
        if sha is None:
            # A bare tag: resolve it against the remote's own tag ref.
            tag_result = run_git(["git", "ls-remote", "--", url, f"refs/tags/{commit}"], LS_REMOTE_TIMEOUT)
            if tag_result.returncode != 0 or not tag_result.stdout.strip():
                return make(error=f"could not resolve tag {commit!r} on {display_url(url)}")
            sha = tag_result.stdout.split()[0]

        target = resolve_sync_target(url, LS_REMOTE_TIMEOUT, run_git)
        if target is None:
            return make(error=f"could not reach {display_url(url)}")
        upstream = target.sha

        # An untagged upstream has nothing "unreleased"; a tagged one reports
        # the commits past the tag for visibility only, never as drift.
        if (upstream.startswith(sha) or sha.startswith(upstream)) and not (
            target.tagged and target.head_sha != upstream
        ):
            return make(upstream=upstream, behind=0, target=target.ref, unreleased=0 if target.tagged else None)

        with tempfile.TemporaryDirectory() as tmpdir:
            clone_result = run_git(
                ["git", "clone", "--bare", "--filter=blob:none", "--quiet", "--", url, tmpdir],
                CLONE_TIMEOUT,
            )
            if clone_result.returncode != 0:
                return make(upstream=upstream, target=target.ref, error=f"could not clone {display_url(url)}")

            pathspec = render_pathspec(tmpdir, upstream)

            count_result = run_git(
                ["git", "-C", tmpdir, "rev-list", "--count", f"{sha}..{upstream}", "--", *pathspec],
                CLONE_TIMEOUT,
            )
            if count_result.returncode != 0:
                return make(
                    upstream=upstream,
                    target=target.ref,
                    error=f"{sha} is not in {display_url(url)}'s history (force-pushed upstream or wrong _src_path)",
                )
            behind = int(count_result.stdout.strip())

            unreleased: int | None = None
            if target.tagged:
                unreleased_result = run_git(
                    ["git", "-C", tmpdir, "rev-list", "--count", f"{upstream}..{target.head_sha}", "--", *pathspec],
                    CLONE_TIMEOUT,
                )
                if unreleased_result.returncode == 0:
                    unreleased = int(unreleased_result.stdout.strip())

            subjects: list[str] = []
            if behind and max_subjects > 0:
                subjects_result = run_git(
                    [
                        "git",
                        "-C",
                        tmpdir,
                        "log",
                        "--format=%s",
                        "-n",
                        str(max_subjects),
                        f"{sha}..{upstream}",
                        "--",
                        *pathspec,
                    ],
                    CLONE_TIMEOUT,
                )
                if subjects_result.returncode == 0:
                    subjects = [_sanitize_subject(line) for line in subjects_result.stdout.splitlines()]

        return make(upstream=upstream, behind=behind, subjects=subjects, target=target.ref, unreleased=unreleased)
    except subprocess.TimeoutExpired as exc:
        # Not str(exc): TimeoutExpired's own message embeds the full argv,
        # which carries the (possibly credentialed) url that display_url() exists to hide.
        return make(error=f"git command timed out after {exc.timeout:g}s")
    except OSError as exc:
        return make(error=f"could not run git: {exc}")
    except Exception as exc:  # noqa: BLE001
        # Catch-all, not a specific handler: anything else (e.g. a
        # non-numeric rev-list count) is unexpected here. type(exc).__name__
        # rather than str(exc) because an unanticipated exception's message
        # is not vetted for a credentialed url the way the handlers above are.
        return make(error=f"unexpected {type(exc).__name__} while checking drift")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-subjects", type=int, default=DEFAULT_MAX_SUBJECTS)
    args = parser.parse_args(argv)

    result = drift(args.max_subjects)

    behind_text = "unknown" if result.behind is None else str(result.behind)
    entrypoint_text = "ok" if result.entrypoint_ok else "missing"
    print(
        f"forge-drift commit={result.commit} upstream={result.upstream} "
        f"target={result.target} behind={behind_text} entrypoint={entrypoint_text}"
        + (f" unreleased={result.unreleased}" if result.unreleased is not None else "")
    )
    for subject in result.subjects:
        print(f"  - {subject}")
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)

    if not result.entrypoint_ok:
        return 3
    if result.behind is None:
        return 2
    if result.behind > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
