"""Guard tests for worktree_setup.py, run standalone:
python3 scripts/test_worktree_setup.py
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worktree_setup as ws  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=clean_git_env()
    )


def _rev(cwd: Path, ref: str = "HEAD") -> str:
    return _git("rev-parse", ref, cwd=cwd).stdout.strip()


@contextlib.contextmanager
def _chdir(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _run_main(argv: list[str]) -> tuple[int, str]:
    """Runs `ws.main`, returning (exit code, captured stderr) so a test
    can assert on *why* a call was refused, not just that it was."""
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = ws.main(argv)
    return code, stderr.getvalue()


def _make_primary(tmp: Path) -> Path:
    """A bare 'origin' plus a clone with one commit on main, the clone
    configured as a usable git identity -- the shape worktree_setup.py
    assumes it runs inside."""
    origin = tmp / "origin.git"
    origin.mkdir()
    _git("init", "--bare", "-q", "-b", "main", cwd=origin)

    primary = tmp / "primary"
    _git("clone", "-q", str(origin), str(primary), cwd=tmp)
    _git("config", "user.email", "test@example.com", cwd=primary)
    _git("config", "user.name", "Test", cwd=primary)
    (primary / "README.md").write_text("seed\n", encoding="utf-8")
    _git("add", "README.md", cwd=primary)
    _git("commit", "-q", "-m", "seed", cwd=primary)
    _git("push", "-q", "origin", "main", cwd=primary)
    return primary


def _primary_with_gitignore(tmp: Path, patterns: str) -> Path:
    """A primary checkout with a committed `.gitignore`, so a worktree's
    symlink target is actually ignored (not merely untracked) -- and so
    `RemovalKeepsTheSymlinkTarget` can `git worktree remove` without
    `--force`."""
    primary = _make_primary(tmp)
    (primary / ".gitignore").write_text(patterns, encoding="utf-8")
    _git("add", ".gitignore", cwd=primary)
    _git("commit", "-q", "-m", "gitignore", cwd=primary)
    _git("push", "-q", "origin", "main", cwd=primary)
    (primary / "scripts").mkdir()
    return primary


class FreshRun(unittest.TestCase):
    def test_creates_the_worktree_on_origin_mains_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            expected_sha = _rev(primary)
            with _chdir(primary):
                code = ws.main(["feature-a"])
            self.assertEqual(code, 2)  # no hook installed in this fixture
            worktree = primary.parent / "feature-a"
            self.assertTrue(worktree.is_dir())
            self.assertEqual(_rev(worktree, "feature-a"), expected_sha)


class RerunIsIdempotent(unittest.TestCase):
    def test_rerun_changes_nothing_and_creates_no_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "scripts" / "worktree_shared_paths.txt").write_text("vendor/deps\n", encoding="utf-8")
            deps = primary / "vendor" / "deps"
            deps.mkdir(parents=True)
            (deps / "marker.txt").write_text("hi\n", encoding="utf-8")
            with _chdir(primary):
                first = ws.main(["feature-b"])
                second = ws.main(["feature-b"])
            self.assertEqual(first, 2)
            self.assertEqual(second, 2)
            worktrees = _git("worktree", "list", "--porcelain", cwd=primary).stdout
            self.assertEqual(worktrees.count("branch refs/heads/feature-b"), 1)
            linked = primary.parent / "feature-b" / "vendor" / "deps"
            self.assertTrue(linked.is_symlink())
            self.assertEqual(linked.resolve(), deps.resolve())
            # a duplicated/nested re-link would put a second "deps" inside it
            self.assertFalse((linked / "deps").exists())


class BranchWithNoWorktreeIsRefused(unittest.TestCase):
    def test_refused_without_minus_capital_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            _git("branch", "feature-c", cwd=primary)
            # Its own commit, diverging from origin/main, so a `-B` reset
            # (which would discard it) is distinguishable from a correct
            # refusal (which leaves it alone) by more than coincidence.
            worktree_c = primary.parent / "feature-c-build"
            _git("worktree", "add", str(worktree_c), "feature-c", cwd=primary)
            (worktree_c / "only-on-feature-c.txt").write_text("x\n", encoding="utf-8")
            _git("add", "only-on-feature-c.txt", cwd=worktree_c)
            _git("commit", "-q", "-m", "diverge", cwd=worktree_c)
            _git("worktree", "remove", str(worktree_c), cwd=primary)
            sha_before = _git("rev-parse", "feature-c", cwd=primary).stdout.strip()
            self.assertNotEqual(sha_before, _git("rev-parse", "origin/main", cwd=primary).stdout.strip())
            with _chdir(primary):
                code, stderr = _run_main(["feature-c"])
            self.assertEqual(code, 1)
            self.assertIn("exists but has no worktree", stderr)
            self.assertFalse((primary.parent / "feature-c").exists())
            self.assertEqual(_git("rev-parse", "feature-c", cwd=primary).stdout.strip(), sha_before)


class PathExistsButIsNotAWorktree(unittest.TestCase):
    def test_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            collision = primary.parent / "feature-d"
            collision.mkdir()
            (collision / "unrelated.txt").write_text("x\n", encoding="utf-8")
            with _chdir(primary):
                code = ws.main(["feature-d"])
            self.assertEqual(code, 1)
            self.assertTrue((collision / "unrelated.txt").exists())


class SharedPathValidation(unittest.TestCase):
    """Each bad entry below is also covered by a `.gitignore` pattern, so
    `is_git_ignored` alone would *accept* it; only its own specific
    structural check (absolute / `..` / `.git*`-prefixed) refuses it.
    Disabling the matching check in `validate_shared_path` makes the
    corresponding test here fail (verified by hand, per this repo's
    guard-removal convention)."""

    def test_an_absolute_entry_is_refused_even_though_it_is_git_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "vendor").mkdir()
            bad_entry = str(primary / "vendor" / "evil")
            (primary / "scripts" / "worktree_shared_paths.txt").write_text(bad_entry + "\n", encoding="utf-8")
            self.assertTrue(ws.is_git_ignored(primary, bad_entry), "fixture bug: entry isn't even git-ignored")
            # A bad remote: if validation ran *after* a fetch attempt, the
            # fetch itself would fail first and mask which check refused.
            _git("remote", "set-url", "origin", "https://example.invalid/nonexistent.git", cwd=primary)
            with _chdir(primary):
                code, stderr = _run_main(["feature-e1"])
            self.assertEqual(code, 1)
            self.assertIn("must be relative, not absolute", stderr)
            self.assertFalse((primary.parent / "feature-e1").exists())

    def test_a_dotdot_entry_is_refused_even_though_it_normalizes_to_something_git_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "vendor").mkdir()
            bad_entry = "vendor/../vendor/evil"
            (primary / "scripts" / "worktree_shared_paths.txt").write_text(bad_entry + "\n", encoding="utf-8")
            self.assertTrue(ws.is_git_ignored(primary, bad_entry), "fixture bug: entry isn't even git-ignored")
            with _chdir(primary):
                code, stderr = _run_main(["feature-e2"])
            self.assertEqual(code, 1)
            self.assertIn("must not contain '..'", stderr)
            self.assertFalse((primary.parent / "feature-e2").exists())

    def test_a_dotgit_prefixed_entry_is_refused_even_though_it_is_git_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, ".github/\n")
            (primary / ".github").mkdir()
            bad_entry = ".github/evil"
            (primary / "scripts" / "worktree_shared_paths.txt").write_text(bad_entry + "\n", encoding="utf-8")
            self.assertTrue(ws.is_git_ignored(primary, bad_entry), "fixture bug: entry isn't even git-ignored")
            with _chdir(primary):
                code, stderr = _run_main(["feature-e3"])
            self.assertEqual(code, 1)
            self.assertIn("must not start with '.git'", stderr)
            self.assertFalse((primary.parent / "feature-e3").exists())

    def test_a_shared_path_not_git_ignored_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            (primary / "scripts").mkdir()
            (primary / "scripts" / "worktree_shared_paths.txt").write_text(
                "vendor/not-ignored\n", encoding="utf-8"
            )
            (primary / "vendor").mkdir()
            (primary / "vendor" / "not-ignored").mkdir()
            with _chdir(primary):
                code, stderr = _run_main(["feature-f"])
            self.assertEqual(code, 1)
            self.assertIn("is not git-ignored", stderr)
            self.assertFalse((primary.parent / "feature-f").exists())

    def test_a_shared_path_missing_from_the_primary_checkout_is_skipped_with_a_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "scripts" / "worktree_shared_paths.txt").write_text("vendor/absent\n", encoding="utf-8")
            with _chdir(primary):
                code = ws.main(["feature-g"])
            self.assertEqual(code, 2)
            self.assertFalse((primary.parent / "feature-g" / "vendor").exists())

    def test_no_shared_paths_flag_creates_no_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "scripts" / "worktree_shared_paths.txt").write_text("vendor/deps\n", encoding="utf-8")
            (primary / "vendor" / "deps").mkdir(parents=True)
            with _chdir(primary):
                code = ws.main(["feature-h", "--no-shared-paths"])
            self.assertEqual(code, 2)
            self.assertFalse((primary.parent / "feature-h" / "vendor").exists())

    def test_a_valid_shared_path_is_symlinked_and_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "scripts" / "worktree_shared_paths.txt").write_text("vendor/deps\n", encoding="utf-8")
            deps = primary / "vendor" / "deps"
            deps.mkdir(parents=True)
            (deps / "marker.txt").write_text("hi\n", encoding="utf-8")
            with _chdir(primary):
                code = ws.main(["feature-i"])
            self.assertEqual(code, 2)
            linked = primary.parent / "feature-i" / "vendor" / "deps"
            self.assertTrue(linked.is_symlink())
            self.assertEqual((linked / "marker.txt").read_text(encoding="utf-8"), "hi\n")


class HookCheck(unittest.TestCase):
    def test_missing_hook_exits_2_present_hook_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            with _chdir(primary):
                self.assertEqual(ws.main(["feature-j"]), 2)
            worktree = primary.parent / "feature-j"
            hook_path = Path(
                _git("rev-parse", "--git-path", "hooks/pre-commit", cwd=worktree).stdout.strip()
            )
            if not hook_path.is_absolute():
                hook_path = worktree / hook_path
            hook_path.parent.mkdir(parents=True, exist_ok=True)
            hook_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            with _chdir(primary):
                self.assertEqual(ws.main(["feature-j"]), 0)

    def test_relative_hookspath_is_resolved_against_the_worktree_not_the_cwd(self) -> None:
        """A relative `core.hooksPath` makes `--git-path` return a relative
        path; `hook_installed` must resolve it against the worktree, not
        the process's current directory (which is the primary checkout
        while `main` runs), or a present hook reads as missing."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            with _chdir(primary):
                self.assertEqual(ws.main(["feature-j2"]), 2)
            worktree = primary.parent / "feature-j2"
            _git("config", "core.hooksPath", ".githooks", cwd=worktree)
            hooks_dir = worktree / ".githooks"
            hooks_dir.mkdir()
            (hooks_dir / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            reported = _git("rev-parse", "--git-path", "hooks/pre-commit", cwd=worktree).stdout.strip()
            self.assertFalse(Path(reported).is_absolute(), "fixture bug: expected a relative --git-path")
            with _chdir(primary):
                self.assertEqual(ws.main(["feature-j2"]), 0)


class RunFromInsideAnotherWorktree(unittest.TestCase):
    def test_resolves_the_primary_checkout_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "scripts" / "worktree_shared_paths.txt").write_text("vendor/deps\n", encoding="utf-8")
            deps = primary / "vendor" / "deps"
            deps.mkdir(parents=True)
            (deps / "marker.txt").write_text("hi\n", encoding="utf-8")
            with _chdir(primary):
                code1 = ws.main(["feature-k1"])
            self.assertEqual(code1, 2)
            other_worktree = primary.parent / "feature-k1"
            # vendor/deps exists only in the *primary* checkout; a run that
            # mistook the current worktree for the primary checkout would
            # see no vendor/deps to share and symlink nothing.
            with _chdir(other_worktree):
                code2 = ws.main(["feature-k2"])
            self.assertEqual(code2, 2)
            new_worktree = primary.parent / "feature-k2"
            self.assertTrue(new_worktree.is_dir())
            linked = new_worktree / "vendor" / "deps"
            self.assertTrue(linked.is_symlink())
            self.assertEqual((linked / "marker.txt").read_text(encoding="utf-8"), "hi\n")


class FlagLikeBranchIsRejected(unittest.TestCase):
    def test_a_branch_name_starting_with_dash_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            with _chdir(primary):
                code, stderr = _run_main(["--upload-pack=touch /tmp/PWNED-worktree-setup"])
            self.assertEqual(code, 1)
            self.assertIn("looks like a flag", stderr)
            self.assertFalse(Path("/tmp/PWNED-worktree-setup").exists())

    def test_a_malformed_but_not_flag_like_branch_name_is_refused(self) -> None:
        """check-ref-format, not just looks_like_flag, rejects an invalid name."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            with _chdir(primary):
                code, stderr = _run_main(["a..b"])
            self.assertEqual(code, 1)
            self.assertIn("is not a valid branch name", stderr)
            self.assertFalse((primary.parent / "a..b").exists())


class PathArgumentCannotInjectAGitOption(unittest.TestCase):
    def test_a_flag_like_path_value_is_resolved_to_an_absolute_path_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            with _chdir(primary):
                code = ws.main(["feature-m", "--path", "--upload-pack=touch /tmp/PWNED-worktree-setup-path"])
            self.assertEqual(code, 2)
            self.assertFalse(Path("/tmp/PWNED-worktree-setup-path").exists())
            resolved = primary / "--upload-pack=touch /tmp/PWNED-worktree-setup-path"
            self.assertTrue(resolved.is_dir())


class UsageErrorExitCodeIsUnambiguous(unittest.TestCase):
    def test_a_bad_invocation_does_not_exit_with_the_hook_missing_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _make_primary(tmp)
            with _chdir(primary):
                code, _ = _run_main([])  # missing required "branch" argument
            self.assertEqual(code, 1)


class RemovalKeepsTheSymlinkTarget(unittest.TestCase):
    def test_worktree_remove_deletes_the_symlink_not_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            primary = _primary_with_gitignore(tmp, "vendor/\n")
            (primary / "scripts" / "worktree_shared_paths.txt").write_text("vendor/deps\n", encoding="utf-8")
            deps = primary / "vendor" / "deps"
            deps.mkdir(parents=True)
            (deps / "marker.txt").write_text("hi\n", encoding="utf-8")
            with _chdir(primary):
                ws.main(["feature-l"])
            worktree = primary.parent / "feature-l"
            self.assertTrue((worktree / "vendor" / "deps").is_symlink())
            # Plain removal, no --force: the fixture's committed .gitignore
            # means the symlink is ignored rather than untracked, so git
            # doesn't refuse to remove the worktree over it.
            _git("worktree", "remove", str(worktree), cwd=primary)
            self.assertFalse(worktree.exists())
            self.assertTrue(deps.is_dir())
            self.assertTrue((deps / "marker.txt").exists())


if __name__ == "__main__":
    unittest.main()
