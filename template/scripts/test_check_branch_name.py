"""Guard tests for check_branch_name.sh, run standalone:
python3 scripts/test_check_branch_name.py"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _git_env import clean_git_env  # noqa: E402
except ImportError:
    from _git_subprocess import clean_git_env  # noqa: E402

CHECK = Path(__file__).resolve().parent / "check_branch_name.sh"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=clean_git_env())


def _repo_on_branch(tmp: Path, branch: str) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", branch, cwd=repo)
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git("add", "README.md", cwd=repo)
    _git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init", cwd=repo)
    return repo


def _run_in(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(CHECK)], cwd=repo, env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True)


class ChecksBranchName(unittest.TestCase):
    """The guard test: dropping the exempt-names list, the tool-prefix check,
    or the random-suffix check must go red here."""

    def test_main_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "main"))
        self.assertEqual(result.returncode, 0)

    def test_green_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "green"))
        self.assertEqual(result.returncode, 0)

    def test_prototype_prefixed_branch_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "prototype/spike-idea"))
        self.assertEqual(result.returncode, 0)

    def test_prototype_exemption_is_what_lets_a_suffix_shaped_name_through(self) -> None:
        # The last word, "x7m2qd", is 6 characters mixing letters and digits:
        # on its own it would fail the random-suffix rule below. Only the
        # exempt-names case lets this one through; drop that case and this
        # must go red.
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "prototype/spike-x7m2qd"))
        self.assertEqual(result.returncode, 0)

    def test_session_title_shaped_branch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            branch = "claude/setup-skills-x7k2qp"
            result = _run_in(_repo_on_branch(Path(tmp_str), branch))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("session title", result.stderr)

    def test_every_known_tool_prefix_fails(self) -> None:
        for tool in ("claude", "codex", "copilot", "cursor", "agent", "session", "chat"):
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_str:
                result = _run_in(_repo_on_branch(Path(tmp_str), f"{tool}/do-the-thing"))
                self.assertNotEqual(result.returncode, 0)

    def test_a_descriptive_branch_name_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "fix-invoice-rounding"))
        self.assertEqual(result.returncode, 0)

    def test_a_branch_ending_in_a_random_session_suffix_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "add-export-retry-x7k2qp"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("random session suffix", result.stderr)

    def test_a_branch_ending_in_a_meaningful_short_word_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "add-export-retry"))
        self.assertEqual(result.returncode, 0)

    def test_a_branch_ending_in_a_four_digit_year_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "plan-for-2024"))
        self.assertEqual(result.returncode, 0)

    def test_a_six_letter_last_word_with_no_digit_passes(self) -> None:
        # Exactly 6 characters (the length the random-suffix rule checks),
        # but all letters: the rule's digit condition is what lets this pass.
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "fix-header"))
        self.assertEqual(result.returncode, 0)

    def test_a_six_digit_last_word_with_no_letter_passes(self) -> None:
        # Exactly 6 characters, but all digits: the rule's letter condition
        # is what lets this pass.
        with tempfile.TemporaryDirectory() as tmp_str:
            result = _run_in(_repo_on_branch(Path(tmp_str), "release-202611"))
        self.assertEqual(result.returncode, 0)

    def test_detached_head_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _repo_on_branch(Path(tmp_str), "main")
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
                env=clean_git_env(),
            ).stdout.strip()
            _git("checkout", "-q", sha, cwd=repo)
            result = _run_in(repo)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
