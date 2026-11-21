#!/usr/bin/env python3
"""Create this project's triage labels and standing trackers on GitHub, once.

Run by `copier copy --trust` after generation, or by hand at any time:

    GITHUB_TOKEN=<token> python3 scripts/bootstrap.py [--dry-run]

Idempotent: existing labels are updated in place, existing trackers are found by
exact title and reused, and tracker numbers already recorded in
`.copier-answers.yml` are verified rather than recreated.

Security (threat: elevation of privilege): the token should be a fine-grained
personal access token limited to this one repository, with only Issues
read/write (and the Metadata read GitHub always adds). By default the script
refuses a classic or OAuth token, a fine-grained token that can see another
repository (public or private), an app installation token that can reach any
other repository, and any token that can read this repository's contents, its
Actions permissions settings, or its Actions secrets -- Issues-only access
never needs Contents, Administration or Secrets access, and those are the
three permission classes probed to tell them apart (Workflows access is not
probed on its own: GitHub never grants it without Contents, so the Contents
probe already catches it). A probe can also come back inconclusive rather
than clean: the Contents probe can't tell excess access from an empty
repository (which 404s on this endpoint regardless of permission) or from a
public repository (whose contents GitHub serves to any token); an
inconclusive probe is reported as a warning, never silently read as "no
excess". Pass --allow-broad-token to run anyway with a warning instead of a
refusal, for the rare case a narrower token genuinely cannot be issued (for
example, a CI identity that already has broader repository access for other
reasons). The script itself only reads the repository and reads or writes
labels and issues; it never touches code, settings, secrets or other
repositories.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
ANSWERS = Path(".copier-answers.yml")

LABELS = {
    "needs-triage": ("d4c5f9", "Waiting for triage"),
    "needs-info": ("fbca04", "Waiting on the reporter for more information"),
    "needs-grilling": ("e99695", "Accepted as real work, but needs a grilling session first"),
    "ready-for-structure": ("0e8a16", "Specified; needs a design-exit pass before building"),
    "ready-for-feature-design": ("fef2c0", "Feature tracker: stage 2 grilling done, stage 3 design not started"),
    "ready-for-build": ("2cbe4e", "Specified and structure decided; ready to build"),
    "ready-for-human": ("1d76db", "Needs human implementation"),
    "wontfix": ("ffffff", "Will not be actioned"),
    "needs-decision": ("b60205", "Blocked until the owner decides an open question"),
    "bug": ("d73a4a", "Something is broken"),
    "enhancement": ("a2eeef", "New feature or improvement"),
    "epic": ("3e4b9e", "Parent issue whose sub-issues are the work"),
    "queued": ("c2e0c6", "Accepted by the coordinator, not yet started"),
    "in-flight": ("5319e7", "A build thread is working on it"),
    "main-health": ("006b75", "Work for the Main Health thread, not a build thread"),
    "release:user": ("bfdadc", "Release notes: a user would notice it"),
    "release:integrator": ("bfd4f2", "Release notes: an integrator or operator must know"),
    "release:internal": ("ededed", "Release notes: nobody outside the repo would notice"),
    "breaking": ("e11d21", "Integrators must act on upgrade"),
    "hanging": ("cccccc", "Agreed gap deliberately deferred to a later point (owner only)"),
    "deferred-accepted-risk": ("bfbfbf", "Known risk the owner decided to accept, not fix (owner only)"),
    "future": ("c5def5", "Owner-deferred idea awaiting a scoping pass"),
    "deferred-arch-finding": ("f9d0c4", "Review-pass finding parked on priority"),
}

STANDING = "This is a standing tracker: it keeps accepting sub-issues and is never closed, whatever its completion reads."
TRACKERS = {
    "post_merge_review_tracker": ("Post-merge review tracker", (
        "Holds the post-merge review's pending notes (a comment per merged PR not yet reviewed), watermark and run log; "
        "the procedure is "
        "`.agents/skills/post-merge-review/SKILL.md`.\n\n" + STANDING + "\n\n"
        "**Watermark:** none yet (no PRs reviewed).\n\n**Current archive issue:** none yet.\n\n## Run log\n\n"
        "| Run | Window (merged) | PRs checked | Must | Should | Sub-issues | Archive |\n|---|---|---|---|---|---|---|\n")),
    "deferred_ideas_epic": ("Deferred ideas", (
        "Collects `future` ideas the owner raised and deferred. Starting the feature pipeline on one detaches it "
        "from this epic and removes `future` (`docs/agents/triage-labels.md`, \"Parking labels\").\n\n" + STANDING)),
    "hanging_epic": ("Hanging items", (
        "Collects `hanging` items (gaps deliberately deferred to a later point) and `deferred-accepted-risk` items "
        "(risks the owner decided to accept), each with the owner's recorded words and a `Revisit: YYYY-MM-DD` line "
        "where one applies. Revisit cadence: set by the owner.\n\n" + STANDING)),
    "arch_findings_epic": ("Deferred architecture findings", (
        "Collects `deferred-arch-finding` items from stage 8 architecture passes and post-merge review runs: "
        "review-sourced findings parked on priority, not owner ideas.\n\n" + STANDING)),
    "local_full_suite_evidence_tracker": ("Local full-suite evidence", (
        "Holds the local full-suite stand-in's evidence. Each full run with its publish switch on "
        "posts one comment here carrying a `<!-- local-full-suite-evidence sha=... finished=... aggregate=... -->` "
        "marker plus a per-step table; the newest such comment is the current status. This is the run's canonical "
        "evidence (SDLC-099) in every environment, including ones whose GitHub proxy refuses commit-status writes; "
        "a best-effort commit status is posted alongside it where that write is allowed. The procedure is "
        "`.agents/skills/watch-main-ci/SKILL.md`, Routine 2.\n\n" + STANDING)),
}


class GitHub:
    def __init__(self, token: str | None, repo: str, dry_run: bool) -> None:
        self.token, self.repo, self.dry_run = token, repo, dry_run

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[object, dict]:
        if self.dry_run and method != "GET":
            print(f"  [dry-run] {method} {path} {json.dumps(body) if body else ''}")
            return {"number": 0}, {}
        req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"null"), dict(resp.headers)

    def paged(self, path: str) -> list:
        items, page = [], 1
        while True:
            sep = "&" if "?" in path else "?"
            batch, _ = self.call("GET", f"{path}{sep}per_page=100&page={page}")
            items += batch
            if len(batch) < 100:
                return items
            page += 1


def parse_answers(text: str) -> dict[str, str]:
    """Parses a `.copier-answers.yml` file's own line shape (`key: value`,
    optionally quoted) without a YAML library, so every reader of a pin
    agrees on how one is read."""
    answers = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z_]\w*):\s*(.*)$", line)
        if m:
            answers[m.group(1)] = m.group(2).strip().strip("'\"")
    return answers


def read_answers() -> dict[str, str]:
    return parse_answers(ANSWERS.read_text())


def write_answer(key: str, value: str) -> None:
    text = ANSWERS.read_text()
    line = f"{key}: '{value}'"
    pattern = re.compile(rf"^{key}:.*$", re.M)
    text = pattern.sub(line, text) if pattern.search(text) else text.rstrip("\n") + f"\n{line}\n"
    ANSWERS.write_text(text)


class Refused(Exception):
    """Bootstrap must stop without creating anything (a too-broad token).

    Raised instead of calling sys.exit directly so main() can choose how to
    surface it: a non-zero exit for a human running the script by hand, or a
    printed warning and a clean exit when running as the Copier task, where a
    non-zero exit makes Copier delete the whole generated project (issue
    reported against this script: a refused token looked identical, from
    Copier's point of view, to the render itself having failed).
    """


def _http_error_message(err: urllib.error.HTTPError) -> str:
    """Best-effort message text from an HTTPError's JSON body; "" if it can't be read.

    A real urlopen() HTTPError carries the response body as its file object; tests
    construct one with no body (fp=None) for the common no-detail cases, so a read
    failure here is expected, not a bug to surface.
    """
    try:
        raw = err.read()
    except Exception:
        return ""
    if not raw:
        return ""
    try:
        return json.loads(raw).get("message", "")
    except (json.JSONDecodeError, AttributeError):
        return ""


def _excess_permissions(gh: GitHub, repo_is_public: bool) -> tuple[list[str], list[str]]:
    """Permission classes beyond Issues this token can reach: (excess, inconclusive).

    check_token's repository-reach checks say nothing about what the token can *do* on this one
    repository: a fine-grained token limited to this repository alone still passes them even when
    it also carries Contents, Administration or Secrets access. Each class is probed with one
    endpoint only that broader permission can read; Workflows is not probed on its own, since
    GitHub never grants it without Contents, which the Contents probe already catches.
    """
    excess: list[str] = []
    inconclusive: list[str] = []

    # Contents: GitHub serves a public repository's contents to any token regardless of
    # permission, so on a public repo this probe can't tell excess access from the
    # repository's own public readability.
    if repo_is_public:
        inconclusive.append("Contents (repository is public, so this can't be checked)")
    else:
        try:
            gh.call("GET", f"/repos/{gh.repo}/contents/")
            excess.append("Contents")
        except urllib.error.HTTPError as err:
            if err.code == 404 and "empty" in _http_error_message(err).lower():
                # An empty repository 404s on this probe regardless of permission, so it
                # can't tell a genuinely narrow token from one with real Contents access
                # the repo has no files to exercise yet -- the common case at the point
                # bootstrap actually calls this (repo creation time).
                inconclusive.append("Contents (repository is empty, so this can't be checked yet)")
            elif err.code not in (403, 404):
                excess.append("Contents")

    # Administration: reading the repository's Actions permissions settings needs
    # Administration: read, which Issues-only access never has, and the answer doesn't
    # depend on the repository having any content.
    try:
        gh.call("GET", f"/repos/{gh.repo}/actions/permissions")
        excess.append("Administration")
    except urllib.error.HTTPError as err:
        if err.code not in (403, 404):
            excess.append("Administration")

    # Secrets: listing (not reading the values of) the repository's Actions secrets
    # needs Secrets: read, which Issues-only access never has.
    try:
        gh.call("GET", f"/repos/{gh.repo}/actions/secrets")
        excess.append("Secrets")
    except urllib.error.HTTPError as err:
        if err.code not in (403, 404):
            excess.append("Secrets")

    return excess, inconclusive


def check_token(gh: GitHub, allow_broad: bool) -> None:
    """Refuse (or, with allow_broad, warn about) a token broader than Issues on this one repository.

    See the module docstring for the threat this guards against. allow_broad is the
    explicit, one-off opt-out for a token that cannot be narrowed further; the default
    stays a refusal so a broad token is never used by accident.
    """
    problems: list[str] = []
    token = gh.token or ""
    if not token.startswith(("github_pat_", "ghs_")):
        problems.append("this is not a fine-grained token limited to this repository (Issues: read and write only)")
    else:
        repo_info, headers = gh.call("GET", f"/repos/{gh.repo}")
        if any(k.lower() == "x-oauth-scopes" and v for k, v in headers.items()):
            problems.append("this token carries classic OAuth scopes; create a fine-grained token instead")
        if token.startswith("github_pat_"):
            # Any other repository counts, public ones included: "All repositories" access lets
            # the token write to every public repository the account owns, not just read them.
            visible = gh.paged("/user/repos")
            others = [r["full_name"] for r in visible if r["full_name"].lower() != gh.repo.lower()]
            if others:
                problems.append("this token can see other repositories; limit it to this repository only")
        else:
            # An installation token acts on every repository its installation covers, public ones included.
            reach, _ = gh.call("GET", "/installation/repositories?per_page=1")
            if reach.get("total_count", 0) > 1:
                problems.append("this app installation token can reach other repositories; limit the installation to this repository only")
        # Reach is only half the check: a token scoped to this repository alone can still carry
        # Contents, Administration or Secrets access that Issues-only access never needs.
        excess, inconclusive = _excess_permissions(gh, repo_is_public=not repo_info.get("private", True))
        if excess:
            problems.append(
                "this token can access " + ", ".join(excess) + ", which Issues-only access does not need; "
                "narrow its permissions to Issues (read and write) only"
            )
        if inconclusive:
            print("Warning: could not rule out excess permissions on " + "; ".join(inconclusive) + ".")
    if not problems:
        return
    message = "; ".join(problems) + "."
    if allow_broad:
        print(f"Warning: {message} Proceeding because --allow-broad-token was passed.")
    else:
        raise Refused(f"Refusing: {message} Pass --allow-broad-token to proceed anyway, or use a narrower token.")


def ensure_labels(gh: GitHub) -> None:
    existing = {lab["name"]: lab for lab in gh.paged(f"/repos/{gh.repo}/labels")} if gh.token else {}
    for name, (color, desc) in LABELS.items():
        current = existing.get(name)
        if current is None:
            gh.call("POST", f"/repos/{gh.repo}/labels", {"name": name, "color": color, "description": desc})
            print(f"  created label {name}")
        elif current.get("color") != color or (current.get("description") or "") != desc:
            gh.call("PATCH", f"/repos/{gh.repo}/labels/{name.replace(':', '%3A')}", {"color": color, "description": desc})
            print(f"  updated label {name}")
        else:
            print(f"  label {name} already present")


def ensure_trackers(gh: GitHub, answers: dict[str, str]) -> dict[str, str]:
    issues = gh.paged(f"/repos/{gh.repo}/issues?state=all&labels=epic") if gh.token else []
    by_title = {i["title"]: i for i in issues if "pull_request" not in i}
    numbers = {}
    for key, (title, body) in TRACKERS.items():
        recorded = answers.get(key, "")
        found = by_title.get(title)
        if recorded and found and str(found["number"]) == recorded:
            print(f"  {title}: #{recorded} already recorded")
            numbers[key] = recorded
            continue
        if found:
            print(f"  {title}: found existing #{found['number']}")
            numbers[key] = str(found["number"])
            continue
        created, _ = gh.call("POST", f"/repos/{gh.repo}/issues", {"title": title, "body": body, "labels": ["epic"]})
        numbers[key] = str(created["number"])
        print(f"  {title}: created #{numbers[key]}")
    return numbers


def manual_dispatch_only() -> list[str]:
    """Workflow files that trigger on anything other than workflow_dispatch."""
    offenders = []
    for wf in sorted(Path(".github/workflows").glob("*.y*ml")):
        text = wf.read_text()
        if re.search(r"^\s*(push|pull_request|pull_request_target|schedule|workflow_run)\s*:", text, re.M):
            offenders.append(str(wf))
    return offenders


def print_checklist(repo: str, numbers: dict[str, str], dry_run: bool) -> None:
    # scripts/project_init_checklist.md is the one copy of the manual steps;
    # this reports only what this run actually did, which that static file can't know.
    mark = "[dry-run]" if dry_run else "[x]"
    offenders = manual_dispatch_only()
    print("\nWhat this run did:")
    print(f"  {mark} triage labels created or confirmed ({len(LABELS)})")
    for key, (title, _) in TRACKERS.items():
        print(f"  {mark} {title}: #{numbers.get(key, '?')} recorded in {ANSWERS}")
    print(f"  {'[ ]' if offenders else '[x]'} every workflow is manual-dispatch only" + (f": fix {', '.join(offenders)}" if offenders else ""))
    print("  [ ] re-render with the tracker numbers: copier recopy --trust --skip-tasks --defaults --overwrite")
    print("\nFor the manual steps this script has no permission to do (repository settings,")
    print("harness follow-ups, stage 0), see scripts/project_init_checklist.md.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    parser.add_argument("--repo", help="owner/name; defaults to the answers file's repo_owner/repo_name")
    parser.add_argument(
        "--allow-broad-token",
        action="store_true",
        help="warn instead of refusing a too-broad GITHUB_TOKEN; off by default (see module docstring)",
    )
    parser.add_argument(
        "--from-copier",
        action="store_true",
        help=(
            "running as Copier's own post-copy task: print a refused token or a GitHub API "
            "error (for example a 404 because the repository does not exist yet) as a warning "
            "and exit 0, instead of exiting non-zero and making Copier delete the new project"
        ),
    )
    args = parser.parse_args()
    if not ANSWERS.exists():
        sys.exit(f"{ANSWERS} not found: run this from the generated project's root.")
    answers = read_answers()
    repo = args.repo or f"{answers.get('repo_owner')}/{answers.get('repo_name')}"
    token = os.environ.get("GITHUB_TOKEN")
    if not token and not args.dry_run:
        print("GITHUB_TOKEN is not set, so nothing was created on GitHub.")
        print("Create the repository, then run: GITHUB_TOKEN=<fine-grained token> python3 scripts/bootstrap.py")
        print_checklist(repo, {k: answers.get(k) or "?" for k in TRACKERS}, dry_run=True)
        return 0
    gh = GitHub(token, repo, args.dry_run)
    try:
        if token:
            check_token(gh, args.allow_broad_token)
        print(f"Labels on {repo}:")
        ensure_labels(gh)
        print("Standing trackers:")
        numbers = ensure_trackers(gh, answers)
    except (Refused, urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as err:
        # HTTPError is a URLError subclass, so it's checked first; the other branches
        # cover a request that never got a response, and one that wasn't valid JSON.
        if isinstance(err, urllib.error.HTTPError):
            hint = " (does the repository exist, and can the token see it?)" if err.code in (401, 403, 404) else ""
            message = f"GitHub API error {err.code} on {err.url}{hint}"
        elif isinstance(err, urllib.error.URLError):
            message = f"network error reaching {API}: {err.reason}"
        elif isinstance(err, (TimeoutError, OSError)):
            message = f"network error reaching {API}: {err}"
        elif isinstance(err, json.JSONDecodeError):
            message = f"GitHub API returned a response {API} couldn't parse as JSON: {err}"
        else:
            message = str(err)
        if args.from_copier:
            print(f"{message}\nSkipping bootstrap's GitHub steps; rerun later with: GITHUB_TOKEN=<token> python3 scripts/bootstrap.py")
            return 0
        sys.exit(message)
    if not args.dry_run:
        for key, number in numbers.items():
            write_answer(key, number)
    print_checklist(repo, numbers, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
