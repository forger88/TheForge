"""Guard tests for check-merge-text.sh reading its scan configuration (the
.theforge-denylist-allow list and the denylist hook's exclude pattern) from
the PR's base commit, so a PR cannot widen its own allowance.

Split from test_check_merge_text_scan.py to stay under the module-size cap;
it reuses that file's fake gh/curl harness.

Standalone: python3 scripts/test_check_merge_text_base_config.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _check_merge_text_harness import ROOT, run_check_merge_text  # noqa: E402


class ScanConfigIsReadFromTheBase(unittest.TestCase):
    def test_a_pr_cannot_allow_list_its_own_leak(self) -> None:
        """Guard test: the allow-list is read at the PR's base, so a
        PR adding both the allow-list file and an entry for its own leaky
        file still fails. Fails if the fetch goes back to the head commit."""
        result = run_check_merge_text(
            pr_files={
                ".theforge-denylist-allow": (
                    b".theforge-denylist-allow:QuuxCorp-Zylotrex\nnotes.md:QuuxCorp-Zylotrex\n"
                ),
                "notes.md": b"mentions QuuxCorp-Zylotrex\n",
            },
            head_allowlist=".theforge-denylist-allow:QuuxCorp-Zylotrex\nnotes.md:QuuxCorp-Zylotrex\n",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_pr_cannot_allow_list_its_own_leak_over_rest(self) -> None:
        result = run_check_merge_text(
            use_rest=True,
            pr_files={
                ".theforge-denylist-allow": (
                    b".theforge-denylist-allow:QuuxCorp-Zylotrex\nnotes.md:QuuxCorp-Zylotrex\n"
                ),
                "notes.md": b"mentions QuuxCorp-Zylotrex\n",
            },
            head_allowlist=".theforge-denylist-allow:QuuxCorp-Zylotrex\nnotes.md:QuuxCorp-Zylotrex\n",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_pr_cannot_widen_the_denylist_exclude_for_its_own_leak(self) -> None:
        """Guard test: the denylist hook's exclude pattern is read at
        the PR's base, so a PR widening it to cover its own leaky file still
        fails. Fails if the pattern is read from the head or the worktree."""
        original = (ROOT / ".pre-commit-config.yaml").read_text()
        widened = original.replace("|^NOTICE\\.md$|", "|^NOTICE\\.md$|^docs/notes\\.md$|")
        self.assertNotEqual(widened, original)
        result = run_check_merge_text(
            pr_files={"docs/notes.md": b"Credits: QuuxCorp-Zylotrex\n"},
            head_precommit_config=widened,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_unreadable_base_pre_commit_config_refuses_the_scan(self) -> None:
        result = run_check_merge_text(base_sha="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("names no commit", result.stderr)


if __name__ == "__main__":
    unittest.main()
