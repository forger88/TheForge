"""Guard tests for local-full-suite.sh, run standalone:
python3 scripts/test_local_full_suite.py

`PrivateDirOk` exercises private_dir_ok through the --is-running flag, which
calls it on LOCAL_FULL_SUITE_LOCK_DIR before anything else runs
(.forge/code-shape-rules.md, "A safety-critical process step needs a tested
mechanism"): a wrong answer here lets another account hold the lock, plant a
symlink a privileged write follows, or make a caller believe no run is in
progress when one actually can't start.

`PublishControls` exercises the five controls that keep
LOCAL_FULL_SUITE_PUBLISH=1 honest -- the dirty-tree refusal, no publish from
a SKIP run, the green push only on a fully clean run, the stale-sha
re-check, and the plain non-force push -- against a throwaway bare remote
and working clone, each proven to go red when its own control is removed
rather than merely trusted to still be there. `gh` is stubbed out (a fake
binary that always fails fast) so these tests need no network or
authentication; the publish controls that matter here are the git-level
ones (dirty tree, SKIP, stale sha, fast-forward-only), never the best-effort
tracker comment or commit statuses, which `gh`'s absence already exercises
as failing harmlessly.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import clean_git_env  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "local-full-suite.sh"


def run_is_running(lock_dir: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["LOCAL_FULL_SUITE_LOCK_DIR"] = str(lock_dir)
    return subprocess.run(
        ["bash", str(SCRIPT), "--is-running"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


class PrivateDirOk(unittest.TestCase):
    def test_refuses_a_symlinked_lock_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "real"
            target.mkdir()
            link = Path(tmp) / "lock-dir"
            link.symlink_to(target)
            result = run_is_running(link)
            # --is-running treats "cannot open the lock" as "a run in progress"
            # (an unknown answer must never say "safe to start").
            self.assertEqual(result.returncode, 0)
            self.assertIn("is a symlink; refusing to use it", result.stderr)

    def test_refuses_a_world_writable_lock_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "lock-dir"
            lock_dir.mkdir(mode=0o777)
            os.chmod(lock_dir, 0o777)  # mkdir's mode is umask-reduced; force it open
            result = run_is_running(lock_dir)
            self.assertEqual(result.returncode, 0)
            self.assertIn("is writable by others; refusing to use it", result.stderr)

    def test_accepts_a_fresh_private_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "lock-dir"  # does not exist yet; mkdir -p -m 700 creates it
            result = run_is_running(lock_dir)
            # private_dir_ok succeeded and nothing else holds the flock: not running.
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env()
    )


def _git_ok(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Like _git, but doesn't raise: for a probe whose failure is itself the answer."""
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=clean_git_env()
    )


def _clone(url: str, dest: Path) -> None:
    subprocess.run(
        ["git", "clone", "-q", url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
        env=clean_git_env(),
    )
    # The bare remote's own HEAD symref may still name an unborn default
    # branch (e.g. "master") from before this fixture ever pushed "main",
    # which leaves the clone's checkout on that nonexistent branch even
    # though origin/main (the one every fixture actually pushes) exists.
    _git(dest, "checkout", "-q", "-B", "main", "origin/main")


def _ref_exists(repo: Path, ref: str) -> bool:
    return _git_ok(repo, "show-ref", "--verify", "--quiet", ref).returncode == 0


def _ref_sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


_DUMMY_TEST = (
    "import unittest\n\n\nclass Dummy(unittest.TestCase):\n"
    "    def test_ok(self) -> None:\n        self.assertTrue(True)\n"
)

_FAKE_GH_FAILS = "#!/usr/bin/env bash\nexit 1\n"


class PublishControls(unittest.TestCase):
    """A throwaway bare remote plus a working clone that passes every
    local-full-suite.sh step trivially (empty .pre-commit-config.yaml,
    one passing dummy test under scripts/ and template/scripts/, a
    no-op review-gate stub), so each test below isolates exactly one
    publish-mode control rather than fighting unrelated step failures."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.remote = root / "remote.git"
        self.work = root / "work"
        self.lock_dir = root / "lock"
        bin_dir = root / "bin"
        bin_dir.mkdir()

        self.remote.mkdir()
        _git(self.remote, "init", "-q", "--bare")

        self.work.mkdir()
        _git(self.work, "init", "-q", "-b", "main")
        _git(self.work, "config", "user.email", "test@example.com")
        _git(self.work, "config", "user.name", "Test")
        _git(self.work, "remote", "add", "origin", str(self.remote))

        (self.work / ".pre-commit-config.yaml").write_text("repos: []\n")
        (self.work / ".copier-answers.yml").write_text(
            "local_full_suite_evidence_tracker: '1'\n"
        )
        (self.work / "scripts").mkdir()
        (self.work / "scripts" / "test_dummy.py").write_text(_DUMMY_TEST)
        (self.work / "template" / "scripts").mkdir(parents=True)
        (self.work / "template" / "scripts" / "test_dummy.py").write_text(_DUMMY_TEST)
        review_gate = self.work / "scripts" / "check_review_gate_local.sh"
        review_gate.write_text("#!/usr/bin/env bash\nexit 0\n")
        review_gate.chmod(review_gate.stat().st_mode | stat.S_IEXEC)

        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-q", "-m", "base")
        _git(self.work, "push", "-q", "-u", "origin", "main")

        # A fake `gh` that always fails fast, plus a symlink to the real
        # python3 (local-full-suite.sh's hook-id read and both test-discover
        # steps need it): the restricted PATH below keeps every other tool
        # this script calls (git, bash, flock, stat, mkdir, date, sed, grep,
        # env) while never reaching the real `gh`, so a publish-mode test
        # never depends on this sandbox's network reachability or auth state.
        gh_stub = bin_dir / "gh"
        gh_stub.write_text(_FAKE_GH_FAILS)
        gh_stub.chmod(gh_stub.stat().st_mode | stat.S_IEXEC)
        python3 = shutil.which("python3")
        assert python3, "python3 not found on PATH"
        (bin_dir / "python3").symlink_to(python3)
        self.path = f"{bin_dir}:/usr/bin:/bin"

    def run_script(self, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        env = {
            **clean_git_env(),
            "PATH": self.path,
            "GIT_TERMINAL_PROMPT": "0",
            "LOCAL_FULL_SUITE_LOCK_DIR": str(self.lock_dir),
            **extra_env,
        }
        return subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _diverge_green(self) -> str:
        """Push an unrelated, ancestor-less commit to refs/heads/green on the
        remote, so a later fast-forward-only push of the work fixture's own
        main tip is rejected as a true non-fast-forward (not merely "behind",
        which a real history could still resolve some other way)."""
        other = Path(self.tmp.name) / "diverge"
        _clone(str(self.remote), other)
        _git(other, "config", "user.email", "test@example.com")
        _git(other, "config", "user.name", "Test")
        _git(other, "checkout", "-q", "--orphan", "unrelated")
        (other / "unrelated.txt").write_text("unrelated\n")
        _git(other, "add", "unrelated.txt")
        _git(other, "commit", "-q", "-m", "unrelated history")
        _git(other, "push", "-q", "origin", "unrelated:refs/heads/green")
        return _ref_sha(other, "unrelated")

    # Control 1: the dirty-tree refusal (local-full-suite.sh, "refusing to
    # publish from a dirty working tree"). Removing this check would let a
    # publish run proceed and later tag evidence/a green push with HEAD's
    # sha even though the tree it actually tested doesn't match that commit.
    def test_a_dirty_working_tree_refuses_to_publish(self) -> None:
        (self.work / "scripts" / "test_dummy.py").write_text(_DUMMY_TEST + "\n# dirty\n")
        result = self.run_script({"LOCAL_FULL_SUITE_PUBLISH": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to publish from a dirty working tree", result.stderr)

    # Control 2: a SKIP (partial) run posts no evidence, no aggregate status
    # and attempts no green push, even when every step that did run passed.
    # Removing the `skipped_any` guard would let a partial run's "nothing
    # failed" read as "everything passed" and push green on an unverified sha.
    def test_a_skip_run_never_attempts_the_green_push(self) -> None:
        result = self.run_script(
            {"LOCAL_FULL_SUITE_PUBLISH": "1", "SKIP": "review-gate"}
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("SKIP  review-gate", result.stdout)
        self.assertFalse(_ref_exists(self.remote, "refs/heads/green"))

    # Control 3: the green push happens only on a fully clean run (SKIP
    # unset *and* every step passed) -- not merely "SKIP was empty".
    # Removing the `failed` check would push green even though a real step
    # failed, certifying an untested or broken commit as green.
    def test_a_failing_step_blocks_the_green_push_even_without_skip(self) -> None:
        review_gate = self.work / "scripts" / "check_review_gate_local.sh"
        review_gate.write_text("#!/usr/bin/env bash\nexit 1\n")
        _git(self.work, "add", "scripts/check_review_gate_local.sh")
        _git(self.work, "commit", "-q", "-m", "break review-gate")
        _git(self.work, "push", "-q", "origin", "main")

        result = self.run_script({"LOCAL_FULL_SUITE_PUBLISH": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertFalse(_ref_exists(self.remote, "refs/heads/green"))

    # Control 4: the stale-sha re-check. If origin/main moved past this
    # run's sha while it ran, a fresh `git fetch` + compare must skip the
    # push: pushing this (older, already-superseded) sha to green would let
    # it move backwards relative to what main has already reached.
    # Removing this re-check would push green to the sha this run started
    # with, no matter how far origin/main has since moved past it.
    def test_a_stale_sha_skips_the_green_push(self) -> None:
        other = Path(self.tmp.name) / "advance"
        _clone(str(self.remote), other)
        _git(other, "config", "user.email", "test@example.com")
        _git(other, "config", "user.name", "Test")
        (other / "advance.txt").write_text("advance\n")
        _git(other, "add", "advance.txt")
        _git(other, "commit", "-q", "-m", "advance main while the run is in flight")
        _git(other, "push", "-q", "origin", "main")

        result = self.run_script({"LOCAL_FULL_SUITE_PUBLISH": "1"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("GREEN-PUSH-SKIPPED-STALE", result.stderr)
        self.assertFalse(_ref_exists(self.remote, "refs/heads/green"))

    # Control 5: the green push is always a plain, non-force push (SDLC-109).
    # A true non-fast-forward (green points somewhere with no common
    # ancestor with this run's sha) must leave green exactly where it was;
    # a force push would instead silently discard whatever commit green was
    # protecting.
    def test_a_true_non_fast_forward_is_never_force_pushed(self) -> None:
        diverged_sha = self._diverge_green()
        result = self.run_script({"LOCAL_FULL_SUITE_PUBLISH": "1"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(_ref_sha(self.remote, "refs/heads/green"), diverged_sha)

    # Companion to control 5, and the classification fix above: an ordinary
    # non-fast-forward rejection must log GREEN-PUSH-REFUSED (green is
    # stuck; recovery is manual per watch-main-ci's Routine 2), never
    # GREEN-PUSH-FAILED (which reads as a script bug to investigate).
    def test_an_ordinary_non_fast_forward_rejection_is_refused_not_failed(self) -> None:
        self._diverge_green()
        result = self.run_script({"LOCAL_FULL_SUITE_PUBLISH": "1"})
        self.assertIn("GREEN-PUSH-REFUSED", result.stderr)
        self.assertNotIn("GREEN-PUSH-FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
