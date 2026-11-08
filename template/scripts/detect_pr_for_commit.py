#!/usr/bin/env python3
"""Detect whether a commit on `main` came from a merged PR, via a
`merge_commit_sha` lookup -- never by parsing the commit's title or message
for a `(#N)` suffix or issue number. `.agents/skills/post-merge-review/
SKILL.md` and `.agents/skills/watch-main-ci/SKILL.md` point here instead of
inlining the lookup themselves, so the lookup is a tested function, not
prose a future agent has to remember to run by hand.

Title-parsing misreads a real PR's squash commit as a direct-to-main
bypass whenever the merger supplies a custom squash title with no
auto-appended `(#N)` suffix, which this project's commit-identity rules can
make routine -- a false positive found and fixed in this project's own
post-merge review history. Leaving the fix as unenforced prose, rather than
a script with its own guard test, let the same false positive (or the
inverse false negative) recur unnoticed, which is what this script and its
test file close.

Usage: python3 scripts/detect_pr_for_commit.py <owner/repo> <sha>
(<sha> may be abbreviated; the printed `sha` is always the full one.)
Exits 1 and prints the classification as JSON when the commit is flagged as
a likely direct-to-main bypass: no PR's `merge_commit_sha` matches it, and
its committer isn't GitHub's own merge-commit identity (the `web-flow` bot
that commits every PR merge, or a direct web-UI edit/commit, which carries
the same identity with no PR at all). Exits 0 when a matching PR was found.
Exits 3 when no PR matches but the committer is GitHub's own identity
anyway: this is unresolved, not clean -- it's either a real merge the
`/commits/{sha}/pulls` index hasn't caught up to yet, or a web-UI
direct-to-main commit, and the identity alone can't tell the two apart.
Exits 2 on a usage or `gh` error.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from typing import Callable

# The GitHub-hosted merge commit's own identity (not an agent's or a human's
# no-reply alias, both of which are no-reply-shaped too but are not this).
_GITHUB_MERGE_LOGIN = "web-flow"
_GITHUB_MERGE_EMAIL = "noreply@github.com"


@dataclasses.dataclass(frozen=True)
class CommitPrStatus:
    sha: str
    pr_numbers: tuple[int, ...]
    committer_login: str | None
    committer_email: str | None
    flagged: bool
    unresolved: bool

    @property
    def has_pr(self) -> bool:
        return bool(self.pr_numbers)


def is_github_merge_identity(login: str | None, email: str | None) -> bool:
    """True only for GitHub's own merge-commit identity, never an agent's or
    a human's no-reply alias (CLAUDE.md, "Agent commit identity" accepts
    those as commit identities, but neither is evidence a PR was merged)."""
    return (login or "").lower() == _GITHUB_MERGE_LOGIN or (
        email or ""
    ).lower() == _GITHUB_MERGE_EMAIL


class ToolError(Exception):
    """`gh` itself is missing, or returned output that isn't JSON (e.g. a
    proxy/rate-limit HTML page) -- distinct from `CalledProcessError`, which
    is `gh` running and reporting its own failure."""


def _run_gh_json(args: list[str]) -> object:
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    except OSError as exc:
        raise ToolError(f"could not run gh: {exc}") from exc
    text = result.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError(f"gh returned non-JSON output: {text[:200]!r}") from exc


def classify_commit(
    repo: str,
    sha: str,
    *,
    run_gh_json: Callable[[list[str]], object] = _run_gh_json,
) -> CommitPrStatus:
    """`repo` is `owner/name`. The `/commits/{sha}/pulls` endpoint is GitHub's
    own `merge_commit_sha` lookup: it lists every PR whose merge commit (or,
    for a rebase merge, any of whose commits) is this sha -- no title or
    message text is ever read. A matching PR here is proof the commit was
    reviewed and merged through one, regardless of what the squash title or
    message says.

    `/commits/{sha}/pulls` returns every PR merely *associated* with the
    commit -- open, closed-unmerged, or merged into any branch -- not only
    the one this sha is the actual merge of. Each candidate is kept only
    when its own `merged_at` is set and its own `merge_commit_sha` equals
    this sha: that is the one check that can't be satisfied by an
    unrelated open or closed-unmerged PR that happens to share a commit."""
    commit = run_gh_json(["api", f"repos/{repo}/commits/{sha}"]) or {}
    # Both endpoints accept an abbreviated sha, but a PR's `merge_commit_sha` is always the
    # full 40 characters, so compare against the commit's own full sha (hazard: comparing
    # to the argument reported every short-sha lookup as unresolved).
    sha = commit.get("sha") or sha
    pulls = run_gh_json(["api", f"repos/{repo}/commits/{sha}/pulls"]) or []
    pr_numbers = [pr["number"] for pr in pulls if pr.get("merged_at") and pr.get("merge_commit_sha") == sha]
    account = commit.get("committer") or {}
    committer_login = account.get("login")
    commit_committer = (commit.get("commit") or {}).get("committer") or {}
    committer_email = commit_committer.get("email")
    has_pr = bool(pr_numbers)
    github_identity = is_github_merge_identity(committer_login, committer_email)
    flagged = not has_pr and not github_identity
    # Not clean either: indistinguishable here from a real merge the
    # /commits/{sha}/pulls index hasn't caught up to.
    unresolved = not has_pr and github_identity
    return CommitPrStatus(
        sha=sha,
        pr_numbers=tuple(pr_numbers),
        committer_login=committer_login,
        committer_email=committer_email,
        flagged=flagged,
        unresolved=unresolved,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: detect_pr_for_commit.py <owner/repo> <sha>", file=sys.stderr)
        return 2
    repo, sha = argv
    try:
        status = classify_commit(repo, sha)
    except subprocess.CalledProcessError as exc:
        print(f"detect_pr_for_commit: gh api failed: {exc.stderr.strip() or exc}", file=sys.stderr)
        return 2
    except ToolError as exc:
        print(f"detect_pr_for_commit: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(dataclasses.asdict(status)))
    if status.flagged:
        return 1
    if status.unresolved:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
