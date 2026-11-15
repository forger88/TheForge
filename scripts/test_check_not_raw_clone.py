"""Guard tests for check-not-raw-clone.sh.

Standalone, standard-library-only:

    python3 scripts/test_check_not_raw_clone.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_env import clean_git_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check-not-raw-clone.sh"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=clean_git_env())


def _run_in(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(CHECK)], cwd=repo, env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True)


def _make_raw_clone_shape(tmp: Path) -> Path:
    """The signature this script exists to catch: copier.yml and template/
    both present at the root, no .copier-answers.yml, no forge remote."""
    repo = tmp / "repo"
    repo.mkdir()
    (repo / "copier.yml").write_text("_subdirectory: template\n")
    (repo / "template").mkdir()
    _git("init", "-q", cwd=repo)
    return repo


class ChecksNotRawClone(unittest.TestCase):
    """The guard test: dropping the remote check, the copier.yml/template/
    presence check, or restoring the removed answers-file exemption
    (ADR-0004's Amendment, ADR-0009), must go red here."""

    def test_a_raw_clone_shape_with_no_forge_remote_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _make_raw_clone_shape(Path(tmp_str))
            result = _run_in(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw copy of TheForge", result.stdout + result.stderr)

    def test_a_remote_naming_the_public_repo_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _make_raw_clone_shape(Path(tmp_str))
            _git("remote", "add", "origin", "https://github.com/forger88/TheForge.git", cwd=repo)
            result = _run_in(repo)
            self.assertEqual(result.returncode, 0)

    def test_a_remote_naming_the_private_staging_repo_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _make_raw_clone_shape(Path(tmp_str))
            _git("remote", "add", "origin", "https://github.com/forger88/TheForgeStaging.git", cwd=repo)
            result = _run_in(repo)
            self.assertEqual(result.returncode, 0)

    def test_an_upstream_remote_on_a_fork_also_passes(self) -> None:
        """A contributor's fork: 'origin' points at their own fork, 'upstream'
        names the forge -- either remote qualifying is enough."""
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _make_raw_clone_shape(Path(tmp_str))
            _git("remote", "add", "origin", "https://github.com/someone-else/TheForge.git", cwd=repo)
            _git("remote", "add", "upstream", "https://github.com/forger88/TheForge.git", cwd=repo)
            result = _run_in(repo)
            self.assertEqual(result.returncode, 0)

    def test_a_remote_naming_an_unrelated_repo_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _make_raw_clone_shape(Path(tmp_str))
            _git("remote", "add", "origin", "https://github.com/someone-else/some-other-project.git", cwd=repo)
            result = _run_in(repo)
            self.assertNotEqual(result.returncode, 0)

    def test_a_tree_with_only_copier_yml_is_not_the_raw_clone_shape(self) -> None:
        """Both copier.yml and template/ must be present at the root for this
        to be the forge's own raw-copy signature; a generated project (or an
        unrelated repo) that happens to have only one of them is not it."""
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = Path(tmp_str) / "repo"
            repo.mkdir()
            (repo / "copier.yml").write_text("_subdirectory: template\n")
            _git("init", "-q", cwd=repo)
            result = _run_in(repo)
            self.assertEqual(result.returncode, 0)

    def test_an_unrelated_repo_with_neither_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = Path(tmp_str) / "repo"
            repo.mkdir()
            _git("init", "-q", cwd=repo)
            result = _run_in(repo)
            self.assertEqual(result.returncode, 0)

    def test_an_answers_file_does_not_exempt_a_raw_copy(self) -> None:
        """A root .copier-answers.yml is not evidence of a real render
        (ADR-0009): this repository commits one at root, so a raw copy of
        root is byte-identical, answers file included. An answers file,
        even one whose _src_path names this repository, must not exempt a
        tree with no qualifying remote."""
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _make_raw_clone_shape(Path(tmp_str))
            (repo / ".copier-answers.yml").write_text("_src_path: https://github.com/forger88/TheForgeStaging.git\n")
            result = _run_in(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw copy of TheForge", result.stdout + result.stderr)

    def test_roots_own_shape_passes_on_its_remote(self) -> None:
        """The same answers file, but with a qualifying remote: this is this
        repository's own legitimate self-retrofit shape, and must pass."""
        with tempfile.TemporaryDirectory() as tmp_str:
            repo = _make_raw_clone_shape(Path(tmp_str))
            (repo / ".copier-answers.yml").write_text("_src_path: https://github.com/forger88/TheForgeStaging.git\n")
            _git("remote", "add", "origin", "https://github.com/forger88/TheForgeStaging.git", cwd=repo)
            result = _run_in(repo)
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
