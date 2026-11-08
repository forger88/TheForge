"""Guard tests for check_sync_duplicates.py.

Each test builds its own temporary git repository as the pre-sync state
and a separate plain directory as the fresh template render, so the
duplicate check is exercised against a base commit, a working-tree edit
and a render, with no dependency on this repository's own history.
This test no longer ships to consumers; it runs only here, and
directly against `template/scripts/` via `template-scripts-tests`.

Standalone: python3 scripts/test_check_sync_duplicates.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sync_duplicates  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env()
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


LONG_LINE = "This sentence is long enough to count as duplicated prose."


class RepoFixture(unittest.TestCase):
    """A git repo (the project) plus a plain directory (the render), with
    `new_duplicates()` called from inside the repo, matching how the real
    script runs: from the project root, against `--base` and `--render`."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.render = root / "render"
        self.render.mkdir()
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "test@example.com")
        _git(self.repo, "config", "user.name", "Test")
        self._old_cwd = Path.cwd()

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)

    def commit_base(self, path: str, text: str) -> str:
        _write(self.repo / path, text)
        _git(self.repo, "add", path)
        _git(self.repo, "commit", "-q", "-m", "base")
        os.chdir(self.repo)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, env=clean_git_env()
        )
        return result.stdout.strip()

    def duplicates(self, base: str, paths: list[Path] | None = None) -> list[tuple[Path, str, int]]:
        return check_sync_duplicates.new_duplicates(base, self.render, paths or [])


class SyncDuplicatedALine(RepoFixture):
    def test_a_line_present_once_at_base_and_render_but_twice_now_is_reported(self) -> None:
        base = self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.render / "CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.repo / "CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        hits = self.duplicates(base)
        self.assertEqual(hits, [(Path("CLAUDE.md"), LONG_LINE, 2)], "the core comparison")


class UpstreamDuplicateIsNotReported(RepoFixture):
    def test_a_line_the_render_already_has_twice_is_not_reported(self) -> None:
        base = self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.render / "CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        _write(self.repo / "CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        self.assertEqual(self.duplicates(base), [], "the render-count bound (the both-sides case)")


class ProjectDuplicateAtBaseIsNotReported(RepoFixture):
    def test_a_line_already_doubled_at_base_is_not_reported(self) -> None:
        base = self.commit_base("CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        _write(self.render / "CLAUDE.md", f"{LONG_LINE}\n")
        # An unrelated edit so the file is a changed candidate against `base`
        # (git diff reports nothing for a file identical to base), while the
        # duplicated line's own count is unchanged from base.
        _write(self.repo / "CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\nan unrelated short edit\n")
        self.assertEqual(self.duplicates(base), [], "the base-count bound")


class ShortAndMarkupLinesIgnored(RepoFixture):
    def test_dashes_braces_and_short_lines_are_never_reported(self) -> None:
        base = self.commit_base("notes.md", "---\n}\nshort line\n")
        _write(self.render / "notes.md", "---\n}\nshort line\n")
        _write(
            self.repo / "notes.md",
            "---\n---\n}\n}\nshort line\nshort line\n" + "-" * 40 + "\n" + "-" * 40 + "\n",
        )
        self.assertEqual(self.duplicates(base), [], "the length and markup filter")


class NewFileCountsFromZero(RepoFixture):
    def test_a_file_absent_at_base_counts_from_zero(self) -> None:
        base = self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.repo / "new.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        _git(self.repo, "add", "new.md")
        hits = self.duplicates(base)
        self.assertEqual(hits, [(Path("new.md"), LONG_LINE, 2)], "the absent-file default")


class HookExitsNonZeroOnlyWhenReported(RepoFixture):
    def test_main_exits_1_with_a_hit_and_0_without(self) -> None:
        base = self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.render / "CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.repo / "CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        os.chdir(self.repo)
        exit_code = check_sync_duplicates.main(["--base", base, "--render", str(self.render)])
        self.assertEqual(exit_code, 1)

        _write(self.repo / "CLAUDE.md", f"{LONG_LINE}\n")
        exit_code = check_sync_duplicates.main(["--base", base, "--render", str(self.render)])
        self.assertEqual(exit_code, 0)


class FlagLikeBaseIsRejected(RepoFixture):
    """A `--base` shaped like a git flag must never reach `git diff` or
    `git show`: both are reachable with no explicit `paths`, matching how
    the real script runs from forge-sync's "Check the result" step.
    `--output=<marker>` is a real option for both subcommands that writes
    an arbitrary file; `--upload-pack=...` is not (git rejects it outright,
    rc=129), so it couldn't make `payload_marker.exists()` fail either way."""

    def test_candidate_files_rejects_a_flag_like_base_directly(self) -> None:
        self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        os.chdir(self.repo)
        payload_marker = Path(self.tmp.name) / "PWNED"
        flag_like_base = f"--output={payload_marker}"
        with self.assertRaises(ValueError):
            check_sync_duplicates._candidate_files(flag_like_base, [])
        self.assertFalse(payload_marker.exists(), "no subprocess side effect occurred")

    def test_counts_at_base_rejects_a_flag_like_base_directly(self) -> None:
        self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        os.chdir(self.repo)
        payload_marker = Path(self.tmp.name) / "PWNED2"
        flag_like_base = f"--output={payload_marker}"
        with self.assertRaises(ValueError):
            check_sync_duplicates._counts_at_base(flag_like_base, Path("CLAUDE.md"))
        self.assertFalse(payload_marker.exists(), "no subprocess side effect occurred")

    def test_new_duplicates_rejects_a_flag_like_base(self) -> None:
        self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.repo / "CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        os.chdir(self.repo)
        payload_marker = Path(self.tmp.name) / "PWNED3"
        flag_like_base = f"--output={payload_marker}"
        with self.assertRaises(ValueError):
            check_sync_duplicates.new_duplicates(flag_like_base, self.render, [])
        self.assertFalse(payload_marker.exists(), "no subprocess side effect occurred")

    def test_main_exits_2_with_a_clear_error_instead_of_crashing(self) -> None:
        self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        os.chdir(self.repo)
        payload_marker = Path(self.tmp.name) / "PWNED4"
        # One token (`--base=...`), not two: argparse treats a bare
        # `--output=...` token as another option, not --base's value.
        exit_code = check_sync_duplicates.main(
            [f"--base=--output={payload_marker}", "--render", str(self.render)]
        )
        self.assertEqual(exit_code, 2)
        self.assertFalse(payload_marker.exists(), "no subprocess side effect occurred")


class SeparatorPrecedesTheBaseInEveryGitInvocation(RepoFixture):
    """With `looks_like_flag` forced to always pass, every argv the script
    builds for `run_git` must still place `--end-of-options` immediately
    before the base."""

    def test_every_captured_argv_places_end_of_options_immediately_before_the_base(self) -> None:
        self.commit_base("CLAUDE.md", f"{LONG_LINE}\n")
        _write(self.repo / "CLAUDE.md", f"{LONG_LINE}\n{LONG_LINE}\n")
        os.chdir(self.repo)
        payload = "--output=/tmp/should-not-run-from-sync-test"
        captured: list[list[str]] = []

        def fake_run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            captured.append(args)
            if args[1] == "diff":
                return subprocess.CompletedProcess(args, 0, stdout="CLAUDE.md\n", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout=f"{LONG_LINE}\n", stderr="")

        with (
            mock.patch("check_sync_duplicates.looks_like_flag", return_value=False),
            mock.patch("check_sync_duplicates.run_git", side_effect=fake_run_git),
        ):
            check_sync_duplicates.new_duplicates(payload, self.render, [])

        # `git show`'s call embeds the base in a combined f"{base}:{file}"
        # element, not standalone like `git diff`'s -- startswith catches both.
        argv_with_payload = [
            (args, i) for args in captured for i, a in enumerate(args) if a.startswith(payload)
        ]
        self.assertGreaterEqual(
            len(argv_with_payload),
            2,
            "expected both the git-diff and git-show call sites to carry the "
            f"payload: {captured}",
        )
        for args, index in argv_with_payload:
            self.assertGreater(index, 0, f"payload is argv[0] with nothing before it: {args}")
            self.assertEqual(
                args[index - 1],
                "--end-of-options",
                "the token immediately before the attacker-controlled value must be "
                f"'--end-of-options', not {args[index - 1]!r}: {args}",
            )


class SeparatorBlocksAFlagLikeBaseEvenWithoutTheExplicitCheck(unittest.TestCase):
    # Sanity check on git's own behaviour only; it never calls
    # check_sync_duplicates, so SeparatorPrecedesTheBaseInEveryGitInvocation
    # (above) is what actually guards the script.
    def test_diff_refuses_a_flag_like_positional_after_end_of_options(self) -> None:
        marker = Path(tempfile.gettempdir()) / "should-not-run-from-diff-test"
        result = subprocess.run(
            ["git", "diff", "--name-only", "--end-of-options", f"--output={marker}"],
            capture_output=True,
            text=True,
            env=clean_git_env(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists(), "no subprocess side effect occurred")

    def test_show_refuses_a_flag_like_positional_after_end_of_options(self) -> None:
        marker = Path(tempfile.gettempdir()) / "should-not-run-from-show-test"
        result = subprocess.run(
            ["git", "show", "--end-of-options", f"--output={marker}:a.txt"],
            capture_output=True,
            text=True,
            env=clean_git_env(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists(), "no subprocess side effect occurred")


if __name__ == "__main__":
    unittest.main()
