"""Guard tests for check-merge-text.sh's --verify-merged mode: after a merge,
the squash commit on the base branch must carry exactly the message the scan
printed (and no non-no-reply identity), so a merger who scanned one message
and merged another is caught.

Split from test_check_merge_text_scan.py to stay under the module-size cap.
Standalone, standard-library-only:

    python3 scripts/test_check_merge_text_verify_merged.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _check_merge_text_harness import CLEAN_BODY, run_check_merge_text  # noqa: E402

NOREPLY = "1234+someone@users.noreply.github.com"
MERGE_SHA = "mergedcommitsha"
# Built by concatenation: the neutrality hooks scan this file and can't tell a
# fixture's "#N" from a real reference.
PR_SUFFIX = " (#" + "999999)"
TITLE = "Reword a lifecycle statement"


def _commit(message: str, *, author: str = NOREPLY, committer: str = "noreply@github.com") -> dict:
    return {
        "message": message,
        "author": {"name": "Someone", "email": author},
        "committer": {"name": "GitHub", "email": committer},
    }


def _verify(message: str, *, rest: bool = False, extra_args=None, pr_extra=None, merge_commit=None, **kwargs):
    merged = {"merged": True, "merge_commit_sha": MERGE_SHA}
    merged.update(pr_extra or {})
    return run_check_merge_text(
        title=TITLE,
        body="A real body.\n",
        use_rest=rest,
        extra_args=["--verify-merged", *(extra_args or [])],
        pr_extra=merged,
        merge_commit=merge_commit if merge_commit is not None else _commit(message),
        **kwargs,
    )


class VerifyMergedComparesTheLandedMessage(unittest.TestCase):
    def test_the_captured_unexpanded_shell_body_is_refused(self) -> None:
        """The guard test: the real incident, a squash body of the literal
        text $(cat). Replacing the comparison with `true` makes this pass."""
        for rest in (False, True):
            with self.subTest(rest=rest):
                result = _verify(TITLE + PR_SUFFIX + "\n\n$(cat)", rest=rest)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("does not match", result.stderr)

    def test_an_exact_match_passes(self) -> None:
        for rest in (False, True):
            with self.subTest(rest=rest):
                result = _verify(TITLE + PR_SUFFIX + "\n\nA real body.\n", rest=rest)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("carries exactly the scanned message", result.stdout)

    def test_a_mismatch_against_a_message_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            message_file = Path(tmp) / "msg"
            message_file.write_text("Scanned title\n\nScanned body.\n")
            result = _verify("Scanned title\n\n$(cat)", message_file=message_file)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_a_message_file_match_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            message_file = Path(tmp) / "msg"
            message_file.write_text("Scanned title\n\nScanned body.\n")
            result = _verify("Scanned title\n\nScanned body.\n", message_file=message_file)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_line_ending_and_trailing_whitespace_differences_pass(self) -> None:
        result = _verify(TITLE + PR_SUFFIX + "  \r\n\r\nA real body.  \r\n\r\n\r\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_appended_no_reply_co_author_trailer_passes(self) -> None:
        message = TITLE + PR_SUFFIX + "\n\nA real body.\n\nCo-authored-by: Someone <" + NOREPLY + ">\n"
        result = _verify(message)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_trailer_the_scanned_message_itself_carries_is_not_peeled(self) -> None:
        text = "Scanned title\n\nScanned body.\n\nCo-authored-by: Someone <" + NOREPLY + ">\n"
        with tempfile.TemporaryDirectory() as tmp:
            message_file = Path(tmp) / "msg"
            message_file.write_text(text)
            result = _verify(text, message_file=message_file)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_appended_personal_address_trailer_is_refused(self) -> None:
        message = TITLE + PR_SUFFIX + "\n\nA real body.\n\nCo-authored-by: A Person <a.person@example.com>\n"
        result = _verify(message)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_a_non_no_reply_squash_author_is_refused(self) -> None:
        merge_commit = _commit(TITLE + PR_SUFFIX + "\n\nA real body.\n", author="a.person@example.com")
        result = _verify("", merge_commit=merge_commit)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_a_mismatch_reports_a_denylist_hit_without_echoing_the_term(self) -> None:
        result = _verify(TITLE + PR_SUFFIX + "\n\nUses QuuxCorp-Zylotrex.\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("denylisted", result.stderr)
        self.assertNotIn("QuuxCorp-Zylotrex", result.stdout + result.stderr)

    def test_an_unmerged_pr_is_refused(self) -> None:
        result = _verify("", pr_extra={"merged": False, "merge_commit_sha": None})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not merged", result.stderr)

    def test_a_head_sha_that_differs_from_the_scanned_one_is_refused(self) -> None:
        result = _verify(
            TITLE + PR_SUFFIX + "\n\nA real body.\n", head_sha="movedhead", extra_args=["--head-sha", "scannedhead"]
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("scannedhead", result.stderr)
        self.assertIn("movedhead", result.stderr)

    def test_a_matching_head_sha_passes(self) -> None:
        result = _verify(TITLE + PR_SUFFIX + "\n\nA real body.\n", head_sha="abc", extra_args=["--head-sha", "abc"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_total_transport_failure_never_reports_success(self) -> None:
        result = _verify("", gh_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("carries exactly", result.stdout)

    def test_head_sha_without_verify_merged_is_a_usage_error(self) -> None:
        result = run_check_merge_text(body=CLEAN_BODY, extra_args=["--head-sha", "abc"])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_a_pr_from_a_different_base_repository_is_refused(self) -> None:
        result = _verify("", base_repo="someone-else/other-repo")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("base repository", result.stderr)

    def test_the_scan_output_names_the_verify_follow_up(self) -> None:
        result = run_check_merge_text()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--verify-merged", result.stdout)


if __name__ == "__main__":
    unittest.main()
