"""Guard tests for check-merge-text.sh naming one explicit target repository
for both transports (REST and the `gh api` fallback), and refusing when the
remote's repository is not the PR's base repository.

Split from test_check_merge_text_scan.py to stay under the module-size cap;
it reuses that file's fake gh/curl harness.

Standalone: python3 scripts/test_check_merge_text_owner_repo.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _check_merge_text_harness import run_check_merge_text  # noqa: E402


class OneTargetRepositoryForBothTransports(unittest.TestCase):
    def test_gh_fallback_calls_name_the_origin_repository_explicitly(self) -> None:
        """Fails if a `gh api` call goes back to gh's own {owner}/{repo} default,
        which names the upstream in a fork checkout."""
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "gh.log"
            result = run_check_merge_text(extra_env={"FAKE_GH_LOG": str(log)})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = [line for line in log.read_text().splitlines() if line.strip()]
        self.assertTrue(calls)
        for call in calls:
            self.assertIn("repos/fake-owner/fake-repo/", call)
            self.assertNotIn("{owner}", call)

    def test_a_pr_from_a_different_base_repository_is_refused(self) -> None:
        """A fork checkout whose origin is the fork must not scan the fork's
        PR that happens to share the number."""
        for use_rest in (False, True):
            with self.subTest(use_rest=use_rest):
                result = run_check_merge_text(base_repo="upstream-owner/fake-repo", use_rest=use_rest)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("base repository", result.stderr)

    def test_a_pr_with_no_base_repository_is_refused(self) -> None:
        result = run_check_merge_text(base_repo="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("base repository", result.stderr)


if __name__ == "__main__":
    unittest.main()
