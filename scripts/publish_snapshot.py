#!/usr/bin/env python3
"""Publish one snapshot of TheForge's files to its public repository.

Exports a released staging commit, drops the denylist files, applies fixed
rewrites, scans the tree, commit message and identity with check-denylist.sh,
then commits one new commit, pushes, and re-scans a fresh clone.

Contract: exit 0 on success or nothing new to publish, 1 when a scan finds
something, 2 when a step refuses or could not run. A scan that cannot run is a
refusal, never a pass. Nothing is pushed before the scan passes.
Scan output names files and lines, not the matched text, except that a path
hit shows the path.

    python3 scripts/publish_snapshot.py --version v0.1.0 --remote <public-url>
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_env import clean_git_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHECK_DENYLIST = ROOT / "scripts" / "check-denylist.sh"

# Never published, wherever they sit in the tree: a public list of what to hide is itself the leak.
# The allow-list goes too: it only qualifies the denylist, and the public tree's own guard tests pass without it.
EXCLUDED_BASENAME_GLOBS = (".theforge-denylist*",)

VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
# A no-reply address identifies no one; anything else is refused as a commit identity.
NOREPLY_EMAIL_RE = re.compile(r"^(?:\d+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com$|^noreply@anthropic\.com$")
DEFAULT_AUTHOR_NAME = "forger88"
DEFAULT_AUTHOR_EMAIL = "238909326+forger88@users.noreply.github.com"
MESSAGE_TEMPLATE = "TheForge {version}\n\nSnapshot of release {version}.\n"
SCAN_BATCH = 200

RELEASE_NOTES_NOTICE = (
    "> **Ticket numbers.** A number written after a `#` in these notes refers to a ticket or pull "
    "request in TheForgeStaging, a private repository, so it can't be opened from here.\n"
)


class PublishError(RuntimeError):
    """A step refused or could not run; nothing may be pushed."""


def insert_release_notes_notice(text: str) -> str:
    heading = "# Release notes\n"
    if not text.startswith(heading):
        raise PublishError("docs/release-notes.md no longer starts with its heading; update the notice rewrite")
    return heading + "\n" + RELEASE_NOTES_NOTICE + text[len(heading):]


# Fixed edits made to the exported copy; each fails closed if its anchor has moved.
REWRITES: dict[str, Callable[[str], str]] = {"docs/release-notes.md": insert_release_notes_notice}


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    out = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if out.returncode != 0:
        raise PublishError(f"{' '.join(cmd[:3])} failed: {out.stderr.strip()[-500:]}")
    return out.stdout


def isolated_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A git environment with no inherited repository state and no user or system config (signing, hooks)."""
    env = clean_git_env()
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    env.update(extra or {})
    return env


def list_files(tree: Path) -> list[str]:
    """Every file under tree, relative; a symlink or special file is an error, as a scan can't follow it."""
    found = []
    for dirpath, _dirs, names in os.walk(tree):
        for name in names:
            full = Path(dirpath) / name
            if full.is_symlink() or not full.is_file():
                raise PublishError(f"not a regular file: {full.relative_to(tree)}")
            found.append(str(full.relative_to(tree)))
    return sorted(found)


def export_release(repo: Path, sha: str, dest: Path) -> None:
    dest.mkdir()
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", sha], capture_output=True, env=isolated_env()
    )
    if archive.returncode != 0:
        raise PublishError(f"git archive failed: {archive.stderr.decode(errors='replace').strip()}")
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)


def is_excluded(rel: str) -> bool:
    return any(fnmatch.fnmatch(Path(rel).name, g) for g in EXCLUDED_BASENAME_GLOBS)


def drop_excluded(tree: Path) -> None:
    for rel in list_files(tree):
        if is_excluded(rel):
            (tree / rel).unlink()


def apply_rewrites(tree: Path) -> None:
    for rel, rewrite in REWRITES.items():
        target = tree / rel
        if not target.is_file():
            raise PublishError(f"{rel} is missing from the export; update the rewrite list")
        target.write_text(rewrite(target.read_text(encoding="utf-8")), encoding="utf-8")


def ensure_outside_git(path: Path) -> None:
    """Inside a work tree check-denylist.sh would honour that tree's allow-list, which a publish scan must not."""
    probe = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, env=isolated_env()
    )
    if probe.returncode == 0:
        raise PublishError(f"{path} is inside a git work tree; the scan must run outside any repository")


def scan(files: list[str], cwd: Path) -> bool:
    """True only when check-denylist.sh ran over every file and found nothing."""
    ensure_outside_git(cwd)
    clean = True
    for i in range(0, len(files), SCAN_BATCH):
        batch = ["./" + f for f in files[i : i + SCAN_BATCH]]
        out = subprocess.run(["bash", str(CHECK_DENYLIST), *batch], cwd=cwd, capture_output=True, text=True)
        if out.returncode != 0:
            clean = False
            sys.stderr.write(out.stderr)
    return clean


def commit_identity(name: str, email: str) -> dict[str, str]:
    """Fixed identity at +0000: a local offset would publish the maintainer's timezone."""
    if not NOREPLY_EMAIL_RE.match(email):
        raise PublishError("the commit email must be a no-reply address")
    date = f"{int(time.time())} +0000"
    return isolated_env({
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": date,
    })


def open_public(remote: str, dest: Path) -> bool:
    """Clone the public main branch, or start an empty repository when it has none. True if cloned."""
    heads = run(["git", "ls-remote", remote, "refs/heads/main"], env=isolated_env())
    if heads.strip():
        run(["git", "clone", "-q", "--branch", "main", remote, str(dest)], env=isolated_env())
        return True
    run(["git", "init", "-q", "-b", "main", str(dest)], env=isolated_env())
    run(["git", "-C", str(dest), "remote", "add", "origin", remote], env=isolated_env())
    return False


def commit_snapshot(public: Path, tree: Path, message: Path, env: dict[str, str]) -> bool:
    """Make the public work tree equal the scanned tree and commit it; False when nothing changed."""
    for entry in public.iterdir():
        if entry.name != ".git":
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
    shutil.copytree(tree, public, dirs_exist_ok=True)
    # -f: a .gitignore inside the snapshot must not drop a file the scan already passed.
    run(["git", "-C", str(public), "add", "-A", "-f"], env=env)
    unchanged = subprocess.run(["git", "-C", str(public), "diff", "--cached", "--quiet"], env=env).returncode == 0
    has_head = subprocess.run(
        ["git", "-C", str(public), "rev-parse", "--verify", "-q", "HEAD"], env=env, capture_output=True
    ).returncode == 0
    if unchanged and has_head:
        return False
    run(["git", "-C", str(public), "commit", "-q", "--no-gpg-sign", "-F", str(message)], env=env)
    return True


def verify_remote(remote: str, tmp: Path) -> None:
    """Scan a fresh clone: every file, and the author and message of every commit."""
    clone = tmp / "verify"
    run(["git", "clone", "-q", remote, str(clone)], env=isolated_env())
    files = [f for f in run(["git", "-C", str(clone), "ls-files", "-z"], env=isolated_env()).split("\0") if f]
    (tmp / "verify-log.txt").write_text(
        run(["git", "-C", str(clone), "log", "--all", "--format=%an %ae %cn %ce%n%B"], env=isolated_env())
    )
    # The scan must run outside a git work tree, so scan a copy of the clone without its .git.
    with tempfile.TemporaryDirectory(prefix="publish-verify-") as copy:
        shutil.copytree(clone, copy, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
        clean = scan(files, Path(copy))
    clean = scan(["verify-log.txt"], tmp) and clean
    if not clean:
        raise PublishError("PUBLIC REPOSITORY FAILED ITS POST-PUSH SCAN: make it private first, then investigate")


def resolved_denylist() -> str:
    """The denylist check-denylist.sh will scan against (the committed list is unioned in as well)."""
    return run(["bash", "-c", f'. "{ROOT}/scripts/denylist-path.sh"; resolve_denylist_path'], env=isolated_env()).strip()


def resolve_release(repo: Path, ref: str, ancestor_of: str) -> str:
    sha = run(["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"], env=isolated_env()).strip()
    ancestry = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, ancestor_of], env=isolated_env()
    )
    if ancestry.returncode != 0:
        raise PublishError(f"{ref} is not on {ancestor_of}; only released commits are published")
    return sha


def publish(args: argparse.Namespace) -> int:
    if not VERSION_RE.match(args.version):
        raise PublishError("--version must look like v1.2.3")
    sha = resolve_release(args.repo, args.ref or args.version, args.require_ancestor_of)
    env = commit_identity(args.author_name, args.author_email)
    with tempfile.TemporaryDirectory(prefix="publish-") as tmpdir:
        tmp = Path(tmpdir)
        tree = tmp / "tree"
        export_release(args.repo, sha, tree)
        drop_excluded(tree)
        apply_rewrites(tree)
        message = tmp / "message.txt"
        message.write_text(MESSAGE_TEMPLATE.format(version=args.version))
        (tmp / "identity.txt").write_text(f"{args.author_name} <{args.author_email}>\n")
        files = list_files(tree)
        print(f"publish_snapshot: scanning {len(files)} files against {resolved_denylist()}")
        ok = scan(files, tree)
        ok = scan(["message.txt", "identity.txt"], tmp) and ok
        if not ok:
            print("publish_snapshot: scan failed; nothing was committed or pushed.", file=sys.stderr)
            return 1
        public = tmp / "public"
        open_public(args.remote, public)
        if not commit_snapshot(public, tree, message, env):
            print("publish_snapshot: the public repository already matches this release; nothing to publish.")
            return 0
        head = run(["git", "-C", str(public), "rev-parse", "HEAD"], env=env).strip()
        if args.dry_run:
            print(f"publish_snapshot: dry run, {len(files)} files scanned clean, local commit {head} not pushed.")
            return 0
        refs = ["main"]
        if args.tag:
            run(["git", "-C", str(public), "tag", "-a", "-F", str(message), args.version], env=env)
            refs.append(args.version)
        run(["git", "-C", str(public), "push", "--atomic", "origin", *refs], env=isolated_env())
        verify_remote(args.remote, tmp)
        print(f"publish_snapshot: pushed {head} ({len(files)} files) and verified a fresh clone.")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--version", required=True, help="release label vX.Y.Z; also the staging tag unless --ref is given")
    p.add_argument("--ref", help="staging commit or tag to publish (default: the --version tag)")
    p.add_argument("--remote", required=True, help="the public repository's URL")
    p.add_argument("--repo", type=Path, default=ROOT, help="the staging repository")
    p.add_argument("--require-ancestor-of", default="origin/main", help="the release must be on this ref")
    p.add_argument("--author-name", default=DEFAULT_AUTHOR_NAME)
    p.add_argument("--author-email", default=DEFAULT_AUTHOR_EMAIL)
    p.add_argument("--tag", action="store_true", help="also push an annotated release tag; off unless asked")
    p.add_argument("--dry-run", action="store_true", help="scan and commit locally, but push nothing")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return publish(args)
    except PublishError as exc:
        print(f"publish_snapshot: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
