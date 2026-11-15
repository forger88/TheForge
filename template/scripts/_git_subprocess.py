"""Shared git-subprocess helper for check_forge_drift.py,
check_sync_duplicates.py and check_forge_sync_trust_diff.py, and for
their own test fixtures; `authenticated_url` is also called directly
from `review-gate-check.yml`'s SDLC-hold-check step.

Each script passes a project-owned, review-gated value (`_src_path`,
`--base`, `--new`) to git as a positional revision or URL; a value
beginning with `-` is parsed by git as an option instead. `looks_like_flag`
is the one place that check lives, and `run_git` is the one place the
subprocess call and its timeout live, so neither is reinvented per
script with its own timeout (or lack of one). `source_url` and
`display_url` are the one place `_src_path`'s shorthand expansion and
its credential redaction live, for the same reason; `authenticated_url`
is the one place a credential is embedded into a URL, the inverse
operation. `resolve_sync_target`
is the one place the ref a sync targets is decided, so the trust diff and
the drift check cannot disagree with each other or with `copier update`.
`copier_yml_at` is the one place `copier.yml`'s (or `copier.yaml`'s) text
at an arbitrary rev is read, so the drift check's path-scoping and the
trust diff's unsafe-key check read the same file the same way.

`clean_git_env` guards a different hazard: when this hook runs as a
`git commit` pre-commit hook rather than a standalone `pre-commit run`,
git sets GIT_DIR/GIT_INDEX_FILE (and, under a core.hooksPath override,
the GIT_CONFIG_* family) in the hook's own environment, and they
propagate to every subprocess the hook spawns. `test_check_forge_drift.py`
and `test_check_sync_duplicates.py` each `git init`/`git add`/`git
commit` their own throwaway repository to exercise their guard without
depending on this project's real history; left unstripped, those
nested git calls inherit the leaked variables and operate on the real
invoking repository instead of their own temp one -- corrupting its
index or overwriting its local `user.name`/`user.email`.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Fixed-name variables git uses to point a command at a *different*
# repository than the one `cwd` implies. GIT_SSL_CAINFO, GIT_ASKPASS,
# GIT_AUTHOR_*/GIT_COMMITTER_* and the rest are left alone: harmless (or
# needed, for a corporate CA bundle) outside the identity-redirection
# this guards against.
_DANGEROUS_GIT_ENV_NAMES = frozenset(
    (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
    )
)
# A core.hooksPath (or other) override arrives as a numbered family,
# GIT_CONFIG_KEY_<n>/GIT_CONFIG_VALUE_<n>; the count alone (above)
# doesn't remove these.
_DANGEROUS_GIT_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")


def clean_git_env() -> dict[str, str]:
    """A copy of this process's environment with every repository-
    identity-redirecting GIT_* variable removed, so a nested git
    command (this module's own `run_git`, or a test fixture's own
    throwaway repo) is never silently redirected at an unrelated
    repository by a leaked pre-commit-hook environment."""
    return {
        name: value
        for name, value in os.environ.items()
        if name not in _DANGEROUS_GIT_ENV_NAMES
        and not name.startswith(_DANGEROUS_GIT_ENV_PREFIXES)
    }


def looks_like_flag(value: str) -> bool:
    """A `-`-prefixed value is parsed by git as an option, not a
    positional argument; reject it rather than rely only on a
    `--`/`--end-of-options` separator."""
    return value.startswith("-")


def run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """`args` is a full command including the leading `"git"`. A
    credential prompt from a misconfigured remote would otherwise hang
    the run past its own timeout instead of failing it cleanly."""
    env = {**clean_git_env(), "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def source_url(src_path: str) -> str:
    """`gh:owner/repo` and `gl:owner/repo` expand to their HTTPS clone URL;
    anything else (an HTTPS URL, an SSH URL, a local path) is unchanged."""
    if src_path.startswith("gh:"):
        return f"https://github.com/{src_path[len('gh:'):]}.git"
    if src_path.startswith("gl:"):
        return f"https://gitlab.com/{src_path[len('gl:'):]}.git"
    return src_path


def copier_yml_at(repo: str | Path, rev: str, timeout: int, runner=None) -> str | None:
    """`copier.yml`'s (or `copier.yaml`'s) full text at `rev` in the git
    repository/clone at `repo`, or None when neither exists there.
    `runner` replaces `run_git`, the same convention `resolve_sync_target`
    uses, so each caller's own module-level `run_git` -- and that module's
    `mock.patch("<module>.run_git", ...)` tests -- keeps controlling the
    call instead of this module's."""
    runner = runner or run_git
    for config_name in ("copier.yml", "copier.yaml"):
        result = runner(
            ["git", "-C", str(repo), "show", "--end-of-options", f"{rev}:{config_name}"],
            timeout,
        )
        if result.returncode == 0:
            return result.stdout
    return None


_DESCRIBE_SUFFIX_RE = re.compile(r"^.*-\d+-g([0-9a-f]+)$", re.IGNORECASE)


def normalise_endpoint(endpoint: str) -> str:
    """A `git describe` string (`<tag>-<n>-g<hex>`) reduces to its trailing
    `<hex>`; a bare tag or SHA passes through unchanged."""
    match = _DESCRIBE_SUFFIX_RE.match(endpoint)
    return match.group(1) if match else endpoint


def endpoints_match(reported: str, actual: str) -> bool:
    """Whether a PR-body-reported `<old>..<new>` endpoint matches the
    answers file's own `_commit` value, allowing for a `git describe`
    suffix on either side and a short SHA being a prefix of the full one.
    Shared by every PR-body record line that cites a `_commit` endpoint
    (`check_forge_sync_trust_record.py`, `check_sdlc_wording_hold.py`), so
    a change to this matching rule changes both the same way at once."""
    reported, actual = normalise_endpoint(reported), normalise_endpoint(actual)
    if reported == actual:
        return True
    shorter, longer = sorted((reported, actual), key=len)
    return bool(shorter) and longer.startswith(shorter)


def display_url(url: str) -> str:
    """Strip userinfo (a credential) from a URL before it reaches an error
    message. Handles standard URL forms (`https://user:token@host/...`) and
    SSH shorthand (`user@host:path`), which `urlsplit` does not parse as a
    netloc. Total: a malformed url (e.g. an unbracketed IPv6 host) that
    `urlsplit` itself can't parse is redacted wholesale rather than ever
    risking a return of the raw, possibly credentialed url."""
    try:
        parts = urlsplit(url)
        if parts.netloc and "@" in parts.netloc:
            netloc = parts.netloc.rsplit("@", 1)[-1]
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        if "@" in url and ":" in url and "://" not in url:
            return url.split("@", 1)[-1]
        return url
    except ValueError:
        return "<unparsable URL>"


def authenticated_url(url: str, token: str) -> str:
    """`url` with `token` embedded as HTTPS Basic-auth userinfo
    (`x-access-token:<token>@host`), the credential shape `display_url`
    above already redacts; lets a caller read a private `_src_path`
    (docs/security/threat-model.md, T15) without changing `source_url`'s
    own output, which stays public-shaped. Returns `url` unchanged for an
    empty token, a non-http(s) scheme (an SSH URL or local path can't
    take a token this way), or a URL that already carries userinfo. The
    caller is responsible for not logging the result; CI's automatic
    masking of a `secrets.*`-sourced token covers that case, nothing
    else does."""
    if not token:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if parts.scheme not in ("http", "https") or not parts.netloc or "@" in parts.netloc:
        return url
    netloc = f"x-access-token:{token}@{parts.netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


# Final-release tags only (`1.2.3`, `v1.2.3`), the only shape TheForge publishes. Copier also accepts other PEP 440
# shapes, but it skips prereleases by default and a non-matching tag is ignored
# here, never chosen; `packaging` is not stdlib and these scripts run without
# Copier's environment.
_RELEASE_TAG_RE = re.compile(r"^v?(\d+(?:\.\d+)*)$")


@dataclasses.dataclass(frozen=True)
class SyncTarget:
    """`ref` is the latest release tag, or `HEAD` when upstream has none;
    `sha` is the commit it names and `head_sha` is upstream's HEAD."""

    ref: str
    sha: str
    head_sha: str

    @property
    def tagged(self) -> bool:
        return self.ref != "HEAD"


def resolve_sync_target(url: str, timeout: int, runner=None) -> SyncTarget | None:
    """The ref `copier update` syncs to by default: the latest release tag
    on `url`, else HEAD. None when the remote cannot be reached or has no
    HEAD. Callers pass a `url` they have already checked with
    `looks_like_flag`. `runner` replaces `run_git`, so a caller's tests can
    intercept the git calls through their own module's `run_git`."""
    runner = runner or run_git
    head = runner(["git", "ls-remote", "--", url, "HEAD"], timeout)
    if head.returncode != 0 or not head.stdout.strip():
        return None
    head_sha = head.stdout.split()[0]

    tags = runner(["git", "ls-remote", "--tags", "--", url], timeout)
    if tags.returncode != 0:
        return None
    best: tuple[tuple[int, ...], str, str] | None = None
    peeled: dict[str, str] = {}
    direct: dict[str, str] = {}
    for line in tags.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        name = parts[1][len("refs/tags/") :]
        if name.endswith("^{}"):
            peeled[name[: -len("^{}")]] = parts[0]
        else:
            direct[name] = parts[0]
    for name, sha in direct.items():
        match = _RELEASE_TAG_RE.match(name)
        if match is None:
            continue
        key = tuple(int(part) for part in match.group(1).split("."))
        # Trailing zeros are insignificant in PEP 440 ordering (1.0 == 1.0.0).
        while len(key) > 1 and key[-1] == 0:
            key = key[:-1]
        if best is None or key > best[0]:
            best = (key, name, peeled.get(name, sha))
    if best is None:
        return SyncTarget(ref="HEAD", sha=head_sha, head_sha=head_sha)
    return SyncTarget(ref=best[1], sha=best[2], head_sha=head_sha)
