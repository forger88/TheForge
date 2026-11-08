"""Guard tests for check_retrofit_preconditions.py.

Every test builds its own fixture directory and never reads this
repository's `template/`. This test no longer ships to consumers:
it runs only here, and directly against `template/scripts/`
via `template-scripts-tests`.

Standalone: python3 scripts/test_check_retrofit_preconditions.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_retrofit_preconditions  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "check_retrofit_preconditions.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _init_git_repo(root: Path) -> None:
    # Runs as part of a pre-commit hook (`guard-script-tests` or
    # `template-scripts-tests`), where git has
    # already set GIT_DIR/GIT_INDEX_FILE etc. in this process's own
    # environment for the real repo being committed to; left unstripped,
    # these throwaway-fixture git calls inherit them and operate on that real
    # repo's index instead of `root`'s (see _git_subprocess.clean_git_env's
    # docstring -- this is the exact hazard it exists to guard against).
    env = clean_git_env()
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, env=env)


class CleanFixture(unittest.TestCase):
    """A clean, committed git repository with no `.copier-answers.yml` and
    no `@.forge/` import line -- a genuine retrofit target."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _init_git_repo(self.root)
        _write(self.root / "CLAUDE.md", "# Working on example\n\nOur own rules, written independently.\n")
        env = clean_git_env()
        subprocess.run(["git", "add", "."], cwd=self.root, check=True, env=env)
        subprocess.run(["git", "commit", "--quiet", "-m", "init"], cwd=self.root, check=True, env=env)

    def problems(self) -> list[str]:
        return check_retrofit_preconditions.problems(self.root)


class CleanTargetPasses(CleanFixture):
    def test_a_clean_genuine_retrofit_target_has_no_problems(self) -> None:
        self.assertEqual(self.problems(), [], "a check that over-fires on a correct fixture goes red here")


class AnswersFileAlreadyExists(CleanFixture):
    def test_an_existing_answers_file_fails(self) -> None:
        _write(self.root / ".copier-answers.yml", "_src_path: somewhere\n_commit: abc123\n")
        problems = self.problems()
        self.assertTrue(any(".copier-answers.yml" in p for p in problems))


class ClaudeMdHasOldStyleImport(CleanFixture):
    def test_an_existing_forge_import_line_fails(self) -> None:
        _write(self.root / "CLAUDE.md", "# Working on example\n\n@.forge/review-gate.md\n")
        problems = self.problems()
        self.assertTrue(any("@.forge/" in p for p in problems))


class DirtyWorkingTree(CleanFixture):
    def test_an_uncommitted_edit_fails(self) -> None:
        _write(self.root / "CLAUDE.md", "# Working on example\n\nA stray uncommitted edit.\n")
        problems = self.problems()
        self.assertTrue(any("not clean" in p for p in problems))


class GitStatusCommandFails(unittest.TestCase):
    """Not a `CleanFixture`: no git repo exists at `root` at all, so `git -C
    root status --porcelain` itself fails (`status.returncode != 0`) rather
    than reporting a dirty tree. Covers `problems()`'s fourth branch."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_a_target_with_no_git_repo_fails(self) -> None:
        problems = check_retrofit_preconditions.problems(self.root)
        self.assertTrue(
            any("git status failed" in p for p in problems),
            f"expected a 'git status failed' problem, got: {problems}",
        )


class HookWrapperReturnsExitCode(CleanFixture):
    def test_the_script_run_as_a_subprocess_exits_nonzero_on_a_dirty_tree(self) -> None:
        _write(self.root / "CLAUDE.md", "# Working on example\n\nA stray uncommitted edit.\n")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not clean", result.stderr)

    def test_the_script_run_as_a_subprocess_exits_zero_on_a_clean_target(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
