"""Shared fixtures for the check-merge-text.sh test files: the fake `gh` and
`curl` on PATH, the PR/commit JSON builders, and `run_check_merge_text`, which
runs the script against them. Split out of test_check_merge_text_scan.py to
keep that file under the module-size cap.
"""

from __future__ import annotations

import base64
import json
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from _git_env import clean_git_env

ROOT = Path(__file__).resolve().parent.parent
CHECK_MERGE_TEXT = ROOT / "scripts" / "check-merge-text.sh"

# Built by concatenation, not as a literal "#NN" substring: this file is
# itself scanned by the no-issue-refs pre-commit hook, which can't tell a
# test fixture from real shipped content.
REF2 = "#" + "42"

# Neither fake below passes a bare "--jq" through any more: check-merge-text.sh's
# api_get/api_get_paginated/api_get_raw_file helpers never pass --jq to `gh api`
# (jq filtering now happens as a separate, explicit step on the raw JSON they
# return), so both fakes serve whole-resource JSON and the real `jq` does the
# rest -- the same convention the files endpoint already established.

FAKE_GH = """#!/usr/bin/env bash
set -euo pipefail
if [ "${FAKE_GH_FAIL:-0}" = "1" ]; then
  echo "fake gh: simulated gh api failure" >&2
  exit 1
fi
# Finds the endpoint path as the first bare (non-flag, non-flag-value)
# argument after "api" -- a plain "$2" assumption breaks the moment a call
# carries a flag with its own value before the path, like
# `gh api -H "Accept: ..." "repos/.../contents/..."`, where $2 is "-H" and
# the real path is $4.
[ -z "${FAKE_GH_LOG:-}" ] || printf '%s\n' "$*" >> "$FAKE_GH_LOG"
path=""
expect=""
for arg in "$@"; do
  if [ -n "$expect" ]; then
    expect=""
    continue
  fi
  case "$arg" in
    api|--paginate) continue ;;
    -H) expect=header; continue ;;
    -*) continue ;;
    *) [ -z "$path" ] && path="$arg" ;;
  esac
done
case "$path" in
  */git/commits/*)
    merge_commit_json="${FAKE_GH_MERGE_COMMIT_JSON:-}"
    [ -n "$merge_commit_json" ] || merge_commit_json='{}'
    printf '%s' "$merge_commit_json"
    ;;
  */commits)
    printf '%s' "${FAKE_GH_COMMITS_JSON:-[]}"
    ;;
  */files)
    # An empty array, not empty output, when a test sets no files: `jq -s`
    # needs valid JSON on every "page".
    printf '%s' "${FAKE_GH_FILES_JSON:-[]}"
    ;;
  */git/blobs/*)
    blob_sha="${path##*/}"
    fail_var="FAKE_GH_BLOB_FAIL_$blob_sha"
    if [ "${!fail_var:-0}" = "1" ]; then
      echo "fake gh: simulated blob fetch failure for $blob_sha" >&2
      exit 1
    fi
    content_var="FAKE_GH_BLOB_$blob_sha"
    printf '{"content":"%s"}' "${!content_var:-}"
    ;;
  */contents/docs/*|*/contents/.copier-answers.yml*)
    # A guard's old/new file version: served from FAKE_GH_CONTENTS_DIR/<ref>/<path>,
    # and a hard failure when absent, so a test can simulate gh trouble.
    rel="${path#*/contents/}"
    ref="${rel#*ref=}"
    rel="${rel%%\\?*}"
    f="${FAKE_GH_CONTENTS_DIR:-/nonexistent}/$ref/$rel"
    if [ -f "$f" ]; then cat "$f"; else echo "fake gh: no $rel at $ref" >&2; exit 1; fi
    ;;
  */contents/.pre-commit-config.yaml*)
    # Served per ref: FAKE_GH_PRECOMMIT_<ref> if set, else the real file, so a
    # test can give the PR's head a widened exclude the base does not have.
    ref="${path#*ref=}"
    ref_var="FAKE_GH_PRECOMMIT_$ref"
    if [ -n "${!ref_var:-}" ]; then printf '%s' "${!ref_var}"; else cat "${FAKE_PRECOMMIT_REAL:?}"; fi
    ;;
  */contents/.theforge-denylist-allow*)
    # Served per ref: only FAKE_GH_ALLOWLIST_<ref> (set for the base, or the
    # head by a test proving the head's copy is ignored). Default empty: a PR carries no allow-list unless a test opts in, the
    # same as a real repository with none committed -- gh would 404 and
    # check-merge-text.sh's empty-file fallback handles that; the fake just
    # prints nothing, and check-denylist.sh treats an absent file the same
    # as an empty one (no exceptions).
    ref="${path#*ref=}"
    ref_var="FAKE_GH_ALLOWLIST_$ref"
    printf '%s' "${!ref_var:-}"
    ;;
  *)
    # Not "${FAKE_GH_PR_JSON:-{}}" inline: bash's ${VAR:-word} scans for the
    # *first* unescaped "}" to end the expansion, so a literal "{}" default
    # leaves a stray extra "}" appended outside it. Two steps instead.
    pr_json_or_default="${FAKE_GH_PR_JSON:-}"
    [ -n "$pr_json_or_default" ] || pr_json_or_default='{}'
    # FAKE_GH_PR_JSON_SECOND + FAKE_GH_PR_JSON_CALL_COUNTER simulate the PR's
    # head moving between the script's two bare-PR fetches (the initial one
    # and check-merge-text.sh's own re-check before reporting success): every
    # call here that isn't /commits, /files, a blob or the allow-list hits
    # this branch, so a counter file is the only way to tell the two apart.
    if [ -n "${FAKE_GH_PR_JSON_SECOND:-}" ] && [ -n "${FAKE_GH_PR_JSON_CALL_COUNTER:-}" ]; then
      count="$(( $(cat "$FAKE_GH_PR_JSON_CALL_COUNTER" 2>/dev/null || echo 0) + 1 ))"
      echo "$count" > "$FAKE_GH_PR_JSON_CALL_COUNTER"
      [ "$count" -le 1 ] || pr_json_or_default="$FAKE_GH_PR_JSON_SECOND"
    fi
    printf '%s' "$pr_json_or_default"
    ;;
esac
"""

# Stands in for `curl` so a test can exercise the REST-primary path
# (api_get/api_get_paginated/api_get_raw_file try this before ever
# touching `gh`) and the fallback-to-gh path when it fails.
# FAKE_CURL_FAIL=1 simulates the REST path being unusable outright (the
# scenario this ticket is about: a token that would work, but something
# about the sandbox breaks the request) -- the real check-merge-text.sh
# must fall back to `gh api` and still produce a correct scan.
FAKE_CURL = """#!/usr/bin/env bash
set -euo pipefail
[ -z "${FAKE_CURL_LOG:-}" ] || printf '%s\n' "$*" >> "$FAKE_CURL_LOG"
if [ "${FAKE_CURL_FAIL:-0}" = "1" ]; then
  echo "fake curl: simulated REST failure" >&2
  exit 22
fi
url=""
hdrfile=""
expect=""
for arg in "$@"; do
  if [ -n "$expect" ]; then
    case "$expect" in
      hdrfile) hdrfile="$arg" ;;
    esac
    expect=""
    continue
  fi
  case "$arg" in
    -D) expect=hdrfile; continue ;;
    -H) expect=header; continue ;;
    -*) continue ;;
    *) url="$arg" ;;
  esac
done
# No "Link: ...; rel=next" header: every REST fixture here is a single page.
[ -z "$hdrfile" ] || : > "$hdrfile"
rest="${url#https://api.github.com/repos/}"  # "<owner>/<repo>/pulls/..."
owner_repo_in_url="${rest%%/*}/$(x="${rest#*/}"; printf '%s' "${x%%/*}")"
# FAKE_CURL_REQUIRE_OWNER_REPO, when set, makes a wrong owner/repo in the
# URL a hard failure instead of something this fake silently tolerates --
# otherwise this fixture would "pass" a REST call made with a garbled
# owner_repo just as happily as a correct one, since it dispatches on the
# URL's path suffix alone and never otherwise looks at the owner/repo
# segment (see OwnerRepoParsesNonGithubLiteralRemoteForms, which needs
# exactly this to actually prove owner_repo was parsed correctly, not
# merely that *some* non-empty string made it choose the REST branch).
if [ -n "${FAKE_CURL_REQUIRE_OWNER_REPO:-}" ] && [ "$owner_repo_in_url" != "${FAKE_CURL_REQUIRE_OWNER_REPO}" ]; then
  echo "fake curl: wrong owner/repo '$owner_repo_in_url' in URL (expected '${FAKE_CURL_REQUIRE_OWNER_REPO}')" >&2
  exit 22
fi
path="$rest"
path="${path#*/}"                            # strip "<owner>/"
path="${path#*/}"                            # strip "<repo>/"
path="${path%%\\?*}"                         # strip the query string
# Unlike the fake `gh` above, `path` here has already had the
# "repos/<owner>/<repo>/" prefix stripped off the real URL, so
# "git/blobs/<sha>" and "contents/..." have no leading segment before
# them at all -- "*/git/blobs/*" (matching the fake gh's literal,
# unresolved "repos/{owner}/{repo}/..." argument) would never match
# here; only "pulls/<n>/commits" and "pulls/<n>/files" still have one.
case "$path" in
  git/commits/*)
    merge_commit_json="${FAKE_CURL_MERGE_COMMIT_JSON:-}"
    [ -n "$merge_commit_json" ] || merge_commit_json='{}'
    printf '%s' "$merge_commit_json"
    ;;
  */commits)
    printf '%s' "${FAKE_CURL_COMMITS_JSON:-[]}"
    ;;
  */files)
    printf '%s' "${FAKE_CURL_FILES_JSON:-[]}"
    ;;
  git/blobs/*)
    blob_sha="${path##*/}"
    content_var="FAKE_CURL_BLOB_$blob_sha"
    printf '{"content":"%s"}' "${!content_var:-}"
    ;;
  contents/.pre-commit-config.yaml*)
    ref="${url#*ref=}"
    ref_var="FAKE_CURL_PRECOMMIT_$ref"
    if [ -n "${!ref_var:-}" ]; then printf '%s' "${!ref_var}"; else cat "${FAKE_PRECOMMIT_REAL:?}"; fi
    ;;
  contents/.theforge-denylist-allow*)
    ref="${url#*ref=}"
    ref_var="FAKE_CURL_ALLOWLIST_$ref"
    printf '%s' "${!ref_var:-}"
    ;;
  *)
    curl_pr_json_or_default="${FAKE_CURL_PR_JSON:-}"
    [ -n "$curl_pr_json_or_default" ] || curl_pr_json_or_default='{}'
    # See the matching FAKE_GH_PR_JSON_SECOND comment above: same mechanism,
    # REST side.
    if [ -n "${FAKE_CURL_PR_JSON_SECOND:-}" ] && [ -n "${FAKE_CURL_PR_JSON_CALL_COUNTER:-}" ]; then
      count="$(( $(cat "$FAKE_CURL_PR_JSON_CALL_COUNTER" 2>/dev/null || echo 0) + 1 ))"
      echo "$count" > "$FAKE_CURL_PR_JSON_CALL_COUNTER"
      [ "$count" -le 1 ] || curl_pr_json_or_default="$FAKE_CURL_PR_JSON_SECOND"
    fi
    printf '%s' "$curl_pr_json_or_default"
    ;;
esac
"""


def _utf8_locale_available() -> str | None:
    """The first installed locale (per `locale -a`) that looks like a
    UTF-8 one, or None if this environment has none -- used to skip the
    one test that needs a real UTF-8 locale to reproduce grep's
    locale-dependent binary-file misdetection, rather than hand-assuming
    a specific locale name is installed everywhere this suite runs."""
    try:
        result = subprocess.run(["locale", "-a"], capture_output=True, text=True, timeout=10)
    except OSError:
        return None
    for line in result.stdout.splitlines():
        if "utf8" in line.lower() or "utf-8" in line.lower():
            return line.strip()
    return None


_UTF8_LOCALE = _utf8_locale_available() or ""


def _balanced_parens(text: str, open_idx: int) -> str:
    """Text inside the parens opened at `open_idx` (`text[open_idx]` must be
    "("), respecting nesting, so extraction isn't cut at the first ")"."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    raise ValueError(f"unbalanced parens starting at index {open_idx}")


# Stands in for `curl` to test api_get_paginated()'s pagination logic in
# isolation (ApiGetPaginatedPagesExplicitly below): serves two real pages,
# each only in response to its own "&page=N" query parameter (never a
# followed Link URL, which this fixture doesn't even provide), and a real
# 'Link: ...; rel="next"' response header only on page 1, so pagination
# must read that header to know to continue, and must stop on page 2.
_FAKE_CURL_TWO_PAGES = """#!/usr/bin/env bash
set -euo pipefail
url=""
hdrfile=""
expect=""
for arg in "$@"; do
  if [ -n "$expect" ]; then
    case "$expect" in
      hdrfile) hdrfile="$arg" ;;
    esac
    expect=""
    continue
  fi
  case "$arg" in
    -D) expect=hdrfile; continue ;;
    -H) expect=header; continue ;;
    -*) continue ;;
    *) url="$arg" ;;
  esac
done
case "$url" in
  *'&page=1')
    printf 'Link: <https://api.github.com/repos/fake-owner/fake-repo/pulls/1/commits?per_page=100&page=2>; rel="next"\\r\\n' > "$hdrfile"
    printf '[{"page":1}]'
    ;;
  *'&page=2')
    : > "$hdrfile"
    printf '[{"page":2}]'
    ;;
  *)
    echo "fake curl: unexpected page request '$url'" >&2
    exit 1
    ;;
esac
"""

# Stands in for `grep` to prove api_get_paginated() never depends on `-P`
# (PCRE) support: rejects any `-P`/`-oP`-style option the way a grep built
# without PCRE support would, then delegates to the real grep for
# everything else -- so a test using this shim only passes if the function
# under test truly never asks for `-P`.
_FAKE_GREP_NO_DASH_P = """#!/usr/bin/env bash
for arg in "$@"; do
  case "$arg" in
    -*P*) echo "grep: invalid option -- 'P'" >&2; exit 2 ;;
  esac
done
exec /bin/grep "$@"
"""


def _files_select_predicate() -> str:
    """The exact predicate inside check-merge-text.sh's own
    `select(...)` call over the PR's /files listing, pulled from the live
    source (the same technique test_pending_marker_authorization.py uses
    for queue-sweep's jq filter) rather than hand-copied, so a later edit
    to the real filter is what the test below runs through `jq`."""
    text = CHECK_MERGE_TEXT.read_text(encoding="utf-8")
    anchor_idx = text.index('"pulls/$pr/files"')
    select_idx = text.index("select(", anchor_idx)
    open_idx = select_idx + len("select")
    return _balanced_parens(text, open_idx)


def _extract_function(name: str) -> str:
    """The exact `name() { ... }` source of a top-level function in
    check-merge-text.sh, pulled from the live file (same technique as
    _files_select_predicate, generalised to a whole function body) so a
    test can run the real buffering/pagination/fallback logic directly,
    without a hand-copied duplicate of it drifting out of sync."""
    text = CHECK_MERGE_TEXT.read_text(encoding="utf-8")
    anchor = text.index(f"{name}() {{")
    open_idx = text.index("{", anchor)
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[anchor : i + 1]
    raise ValueError(f"unbalanced braces extracting function '{name}'")


def _install_fake_gh(bin_dir: Path) -> None:
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)


def _install_fake_curl(bin_dir: Path) -> None:
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)


DEFAULT_COMMITS = [
    {
        "message": "A clean commit message.\n",
        "author_name": "Someone",
        "author_email": "noreply@example.com",
        "committer_name": "Someone",
        "committer_email": "noreply@example.com",
    }
]


def _commits_json(commits: list[dict]) -> str:
    return json.dumps(
        [
            {
                "commit": {
                    "message": c["message"],
                    "author": {"name": c["author_name"], "email": c["author_email"]},
                    "committer": {"name": c["committer_name"], "email": c["committer_email"]},
                }
            }
            for c in commits
        ]
    )


def _build_rest_env(
    *,
    title: str,
    body: str,
    head_sha: str,
    commits: list[dict],
    commits_count: int,
    pr_files: dict[str, bytes] | None,
    files_count: int,
    rest_commits: list[dict] | None,
    rest_pr_files: dict[str, bytes] | None,
    rest_title: str | None,
    rest_fails: bool,
    require_owner_repo: str | None,
    allowlist: str | None,
    base_sha: str,
    head_allowlist: str | None,
    base_repo: str,
    pr_extra: dict | None = None,
) -> dict[str, str]:
    """The env vars that configure the fake curl's REST-path responses --
    split out of run_check_merge_text to keep that function under this
    repo's function-size cap, not because it's reused elsewhere."""
    rest_env: dict[str, str] = {
        "GH_TOKEN": "fake-rest-token",
        "FAKE_PRECOMMIT_REAL": str(ROOT / ".pre-commit-config.yaml"),
    }
    if require_owner_repo is not None:
        rest_env["FAKE_CURL_REQUIRE_OWNER_REPO"] = require_owner_repo
    if rest_fails:
        rest_env["FAKE_CURL_FAIL"] = "1"
        return rest_env
    rest_commits_count = len(rest_commits) if rest_commits is not None else commits_count
    rest_files = rest_pr_files if rest_pr_files is not None else pr_files
    rest_files_count = len(rest_pr_files) if rest_pr_files is not None else files_count
    rest_env["FAKE_CURL_PR_JSON"] = json.dumps(
        {
            "title": rest_title if rest_title is not None else title,
            "body": body,
            "head": {"sha": head_sha},
            "base": {"sha": base_sha, "repo": {"full_name": base_repo}},
            "commits": rest_commits_count,
            "changed_files": rest_files_count,
            **(pr_extra or {}),
        }
    )
    rest_env["FAKE_CURL_COMMITS_JSON"] = _commits_json(rest_commits if rest_commits is not None else commits)
    rest_records = []
    for index, (path, content) in enumerate((rest_files or {}).items()):
        blob_sha = f"restfakesha{index}"
        rest_records.append({"filename": path, "sha": blob_sha, "status": "modified"})
        rest_env[f"FAKE_CURL_BLOB_{blob_sha}"] = base64.b64encode(content).decode()
    rest_env["FAKE_CURL_FILES_JSON"] = json.dumps(rest_records)
    if allowlist is not None:
        rest_env[f"FAKE_CURL_ALLOWLIST_{base_sha}"] = allowlist
    if head_allowlist is not None:
        rest_env[f"FAKE_CURL_ALLOWLIST_{head_sha}"] = head_allowlist
    return rest_env


def _build_drift_env(
    *,
    tmp: Path,
    title: str,
    body: str,
    drift_head_sha_to: str,
    commits_count: int,
    files_count: int,
) -> dict[str, str]:
    """The env vars that make the fake gh/curl answer the script's own
    re-check PR fetch with a different head.sha than the initial one --
    split out of run_check_merge_text to keep that function under this
    repo's function-size cap, not because it's reused elsewhere."""
    drifted_pr_json = json.dumps(
        {
            "title": title,
            "body": body,
            "head": {"sha": drift_head_sha_to},
            "commits": commits_count,
            "changed_files": files_count,
        }
    )
    return {
        "FAKE_GH_PR_JSON_SECOND": drifted_pr_json,
        "FAKE_GH_PR_JSON_CALL_COUNTER": str(tmp / "gh-pr-json-call-counter"),
        "FAKE_CURL_PR_JSON_SECOND": drifted_pr_json,
        "FAKE_CURL_PR_JSON_CALL_COUNTER": str(tmp / "curl-pr-json-call-counter"),
    }


def _gh_config_env(
    base_sha: str,
    head_sha: str,
    allowlist: str | None,
    head_allowlist: str | None,
    head_precommit_config: str | None,
) -> dict[str, str]:
    """Per-ref allow-list and pre-commit config the fake gh/curl serve;
    split out to keep run_check_merge_text under the function-size cap."""
    env: dict[str, str] = {}
    if allowlist is not None:
        env[f"FAKE_GH_ALLOWLIST_{base_sha}"] = allowlist
    if head_allowlist is not None:
        env[f"FAKE_GH_ALLOWLIST_{head_sha}"] = head_allowlist
    if head_precommit_config is not None:
        env[f"FAKE_GH_PRECOMMIT_{head_sha}"] = head_precommit_config
        env[f"FAKE_CURL_PRECOMMIT_{head_sha}"] = head_precommit_config
    return env


# A body that clears check_review_gate.py (full-gate shape), so tests about
# other scans stay green; the review-gate tests below override it.
CLEAN_BODY = (
    "A clean PR body.\n\n"
    "Review: Standards: sub-agent, build-tier - clean. "
    "Spec: sub-agent, build-tier - clean. "
    "Self-review: builder's own, build-tier - nothing further.\n"
)


def _make_origin_repo(path: Path, origin_url: str) -> Path:
    """A throwaway git repo with its own "origin", not the real checkout's:
    owner_repo resolution (git remote get-url origin) must not depend on
    whatever remote happens to be configured in the environment running
    this test suite."""
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, env=clean_git_env(), check=True)
    subprocess.run(["git", "remote", "add", "origin", origin_url], cwd=path, env=clean_git_env(), check=True)
    return path


def _gh_files_env(pr_files: dict[str, bytes] | None, blob_fail_paths: frozenset[str] | None) -> dict[str, str]:
    """The fake gh's /files listing and per-blob content for the PR's changed files."""
    env: dict[str, str] = {}
    file_records = []
    for index, (path, content) in enumerate((pr_files or {}).items()):
        blob_sha = f"fakesha{index}"
        file_records.append({"filename": path, "sha": blob_sha, "status": "modified"})
        env[f"FAKE_GH_BLOB_{blob_sha}"] = base64.b64encode(content).decode()
        if blob_fail_paths and path in blob_fail_paths:
            env[f"FAKE_GH_BLOB_FAIL_{blob_sha}"] = "1"
    if file_records:
        env["FAKE_GH_FILES_JSON"] = json.dumps(file_records)
    return env


def run_check_merge_text(
    *,
    title: str = "A clean PR title",
    body: str = CLEAN_BODY,
    commits: list[dict] | None = None,
    denylist_terms: str = "QuuxCorp-Zylotrex\n",
    message_file: Path | None = None,
    pr_files: dict[str, bytes] | None = None,
    allowlist: str | None = None,
    head_allowlist: str | None = None,
    head_precommit_config: str | None = None,
    head_sha: str = "deadbeef",
    use_rest: bool = False,
    rest_fails: bool = False,
    rest_commits: list[dict] | None = None,
    rest_pr_files: dict[str, bytes] | None = None,
    rest_title: str | None = None,
    gh_fails: bool = False,
    pr_commits_count: int | None = None,
    pr_changed_files_count: int | None = None,
    origin_url: str = "https://github.com/fake-owner/fake-repo.git",
    require_owner_repo: str | None = None,
    extra_env: dict[str, str] | None = None,
    blob_fail_paths: frozenset[str] | None = None,
    drift_head_sha_to: str | None = None,
    base_sha: str = "basesha",
    base_repo: str = "Fake-Owner/Fake-Repo",
    extra_args: list[str] | None = None,
    pr_extra: dict | None = None,
    merge_commit: dict | None = None,
) -> subprocess.CompletedProcess:
    """pr_files maps a changed file's path to its raw (pre-base64) content;
    each gets a distinct fake blob sha so the fake gh/curl can look its
    content up by sha, the same way the real git/blobs endpoint would.
    allowlist is the .theforge-denylist-allow content at the PR's base commit
    (None = none there, the common case); head_allowlist and
    head_precommit_config are the PR's own head versions, which the scan must
    ignore. commits is a list of
    {message, author_name, author_email, committer_name, committer_email}
    dicts, one per commit (default: a single clean commit).

    use_rest=True sets GH_TOKEN so the REST-primary path (fake curl) is
    tried; rest_* overrides let a test give the REST path different data
    than the gh fallback would, so a passing test actually proves the REST
    response was used, not just tolerated. rest_fails=True makes the fake
    curl fail outright, so the real script's fallback to `gh api` is what's
    under test. gh_fails=True makes the fake gh fail outright too -- combined
    with rest_fails, this proves the script aborts (no silent "clean" result)
    when neither path can produce a scan at all. blob_fail_paths names
    pr_files entries whose own blob fetch (not the top-level PR/commits
    fetch gh_fails covers) must fail outright, for a test that isolates a
    single changed file's content from being readable at all.

    pr_commits_count/pr_changed_files_count override the PR resource's own
    `.commits`/`.changed_files` fields independently of the actual number of
    commits/files served -- the default is the real count (so an ordinary
    test's PR resource is internally consistent and passes the real script's
    own mismatch check), and a test proving that check's refusal sets one of
    these to something that doesn't match what's actually served.
    origin_url overrides the throwaway repo's "origin" remote, for a test of
    owner_repo's parsing of a non-github.com-literal remote form.
    require_owner_repo, when use_rest=True, makes the fake curl itself fail
    unless the URL's owner/repo segment matches exactly -- without it, a
    wrong-but-non-empty owner_repo would still make the fake curl answer
    (it dispatches on the URL's path suffix alone), so a parsing bug that
    produces garbage instead of truly nothing would go unnoticed.
    extra_env overrides/adds environment variables for the script's own
    subprocess (not the fakes' installation) -- e.g. LC_ALL/LANG, since
    check-denylist.sh's binary/invalid-UTF-8 handling is locale-dependent
    and this sandbox's own ambient locale (POSIX) doesn't reproduce the
    bug a UTF-8 locale does.
    base_repo is the PR resource's base.repo.full_name (the scan refuses when
    it differs from origin's owner/repo, case-insensitively).
    drift_head_sha_to simulates the PR's head moving between the script's
    initial PR fetch and its own re-check right before reporting success:
    the second bare-PR fetch (gh or REST, whichever is in use) answers with
    this sha instead of head_sha, counted via a fresh counter file so the
    two calls are told apart.
    extra_args are appended to the script's command line. pr_extra is merged
    into the PR resource (e.g. merged/merge_commit_sha), and merge_commit is the
    JSON the git/commits/<sha> endpoint serves ({message, author, committer})."""
    commits = commits if commits is not None else DEFAULT_COMMITS
    commits_count = pr_commits_count if pr_commits_count is not None else len(commits)
    files_count = pr_changed_files_count if pr_changed_files_count is not None else len(pr_files or {})
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        _install_fake_gh(bin_dir)
        _install_fake_curl(bin_dir)
        home_dir = tmp / "home"
        home_dir.mkdir()
        cwd_dir = _make_origin_repo(tmp / "cwd", origin_url)
        denylist = tmp / "denylist"
        denylist.write_text(denylist_terms)
        args = [str(CHECK_MERGE_TEXT), "999999"]
        if message_file is not None:
            args += ["--message-file", str(message_file)]
        args += extra_args or []
        pr_json = json.dumps(
            {
                "title": title,
                "body": body,
                "head": {"sha": head_sha},
                "base": {"sha": base_sha, "repo": {"full_name": base_repo}},
                "commits": commits_count,
                "changed_files": files_count,
                **(pr_extra or {}),
            }
        )
        env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(home_dir),
            "THEFORGE_DENYLIST_FILE": str(denylist),
            "FAKE_GH_PR_JSON": pr_json,
            "FAKE_GH_COMMITS_JSON": _commits_json(commits),
            "FAKE_PRECOMMIT_REAL": str(ROOT / ".pre-commit-config.yaml"),
        }
        env.update(_gh_config_env(base_sha, head_sha, allowlist, head_allowlist, head_precommit_config))
        env.update(_gh_files_env(pr_files, blob_fail_paths))
        if gh_fails:
            env["FAKE_GH_FAIL"] = "1"
        if drift_head_sha_to is not None:
            env.update(_build_drift_env(
                tmp=tmp, title=title, body=body, drift_head_sha_to=drift_head_sha_to,
                commits_count=commits_count, files_count=files_count,
            ))
        if use_rest:
            env.update(_build_rest_env(
                title=title, body=body, head_sha=head_sha, commits=commits,
                commits_count=commits_count, pr_files=pr_files, files_count=files_count,
                rest_commits=rest_commits, rest_pr_files=rest_pr_files, rest_title=rest_title,
                rest_fails=rest_fails, require_owner_repo=require_owner_repo, allowlist=allowlist,
                base_sha=base_sha, head_allowlist=head_allowlist, base_repo=base_repo,
                pr_extra=pr_extra,
            ))
        if merge_commit is not None:
            env["FAKE_GH_MERGE_COMMIT_JSON"] = json.dumps(merge_commit)
            env["FAKE_CURL_MERGE_COMMIT_JSON"] = json.dumps(merge_commit)
        if extra_env is not None:
            env.update(extra_env)
        return subprocess.run(args, env=env, cwd=cwd_dir, capture_output=True, text=True)
