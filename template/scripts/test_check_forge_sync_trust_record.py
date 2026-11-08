"""Guard tests for check_forge_sync_trust_record.py, run standalone:
python3 scripts/test_check_forge_sync_trust_record.py
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_forge_sync_trust_record as guard  # noqa: E402

OLD_ANSWERS = "_src_path: 'gh:example-org/example-forge'\n_commit: 'v1.0.0'\n"
NEW_ANSWERS = "_src_path: 'gh:example-org/example-forge'\n_commit: 'v1.1.0'\n"


def sync_body(trust_line: str | None) -> str:
    line = f"Trust diff: {trust_line}\n" if trust_line is not None else ""
    return f"_commit before: v1.0.0\n_commit after: v1.1.0\n\n{line}"


class NonSyncPrsAreNotChecked(unittest.TestCase):
    def test_non_sync_pr_not_checked(self) -> None:
        # _commit unchanged between base and head: not a sync.
        self.assertEqual(guard.check("no trust diff line at all", OLD_ANSWERS, OLD_ANSWERS), [])

    def test_retrofit_not_checked(self) -> None:
        # No _commit at base: a retrofit or first copy, not a sync.
        no_commit_answers = "_src_path: 'gh:example-org/example-forge'\n"
        self.assertEqual(guard.check("no trust diff line at all", no_commit_answers, NEW_ANSWERS), [])

    def test_trigger_is_commit_change_not_marker(self) -> None:
        # No "Drift before this sync" marker anywhere in the body -- still
        # checked, since the trigger is the answers file's own _commit change.
        body_with_no_marker = "Ticket: Closes #1\n\nNo sync marker here at all.\n"
        failures = guard.check(body_with_no_marker, OLD_ANSWERS, NEW_ANSWERS)
        self.assertEqual(len(failures), 1)
        self.assertIn("Trust diff", failures[0])


class MissingRecordLine(unittest.TestCase):
    def test_sync_pr_without_record_fails(self) -> None:
        failures = guard.check(sync_body(None), OLD_ANSWERS, NEW_ANSWERS)
        self.assertEqual(len(failures), 1)
        self.assertIn("Trust diff", failures[0])


class RangeMustMatchAnswers(unittest.TestCase):
    def test_record_range_must_match_answers(self) -> None:
        # Stale old endpoint.
        failures = guard.check(sync_body("v0.9.0..v1.1.0 clean"), OLD_ANSWERS, NEW_ANSWERS)
        self.assertEqual(len(failures), 1)
        self.assertIn("range", failures[0])

    def test_forgotten_new_flag_leaves_a_stale_new_endpoint(self) -> None:
        # A --vcs-ref sync whose check_forge_sync_trust_diff.py run forgot
        # --new would describe the default target instead of the one
        # actually synced -- caught the same way as a stale old endpoint.
        failures = guard.check(sync_body("v1.0.0..v9.9.9 clean"), OLD_ANSWERS, NEW_ANSWERS)
        self.assertEqual(len(failures), 1)
        self.assertIn("range", failures[0])

    def test_describe_and_sha_endpoints_match(self) -> None:
        # A `git describe` form (<tag>-<n>-g<hex>) normalises to its hex
        # suffix, which the stored bare-SHA _commit is a prefix of.
        old_answers = "_commit: 'abcdef1'\n"
        new_answers = "_commit: 'abcdef1234567890'\n"
        body = "Trust diff: abcdef1..v1.0.0-5-gabcdef1234567890 clean\n"
        self.assertEqual(guard.check(body, old_answers, new_answers), [])

    def test_matching_range_passes(self) -> None:
        self.assertEqual(guard.check(sync_body("v1.0.0..v1.1.0 clean"), OLD_ANSWERS, NEW_ANSWERS), [])


class UnreviewedChangeFails(unittest.TestCase):
    def test_unreviewed_change_fails(self) -> None:
        failures = guard.check(
            sync_body("v1.0.0..v1.1.0 changed: copier.yml"),
            OLD_ANSWERS,
            NEW_ANSWERS,
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("changed:", failures[0])

    def test_reviewed_with_a_reason_passes(self) -> None:
        failures = guard.check(
            sync_body("v1.0.0..v1.1.0 reviewed: copier.yml — adds a harmless comment, no new task"),
            OLD_ANSWERS,
            NEW_ANSWERS,
        )
        self.assertEqual(failures, [])

    def test_reviewed_with_no_reason_fails(self) -> None:
        failures = guard.check(sync_body("v1.0.0..v1.1.0 reviewed:"), OLD_ANSWERS, NEW_ANSWERS)
        self.assertEqual(len(failures), 1)

    def test_an_unrecognised_result_word_fails(self) -> None:
        failures = guard.check(sync_body("v1.0.0..v1.1.0 looks fine to me"), OLD_ANSWERS, NEW_ANSWERS)
        self.assertEqual(len(failures), 1)


class MultipleFailuresAreAllReported(unittest.TestCase):
    def test_both_a_range_mismatch_and_an_unreviewed_change_are_named(self) -> None:
        failures = guard.check(sync_body("v0.0.0..v0.0.0 changed: copier.yml"), OLD_ANSWERS, NEW_ANSWERS)
        self.assertEqual(len(failures), 2)


class MainExitCode(unittest.TestCase):
    def test_main_requires_exactly_three_arguments(self) -> None:
        self.assertEqual(guard.main(["one", "two"]), 2)

    def test_main_passes_file_paths_through(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            old_path = Path(tmp) / "old.yml"
            new_path = Path(tmp) / "new.yml"
            body_path.write_text(sync_body("v1.0.0..v1.1.0 clean"))
            old_path.write_text(OLD_ANSWERS)
            new_path.write_text(NEW_ANSWERS)
            self.assertEqual(guard.main([str(body_path), str(old_path), str(new_path)]), 0)

    def test_main_fails_a_real_sync_pr_with_no_record_line(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            old_path = Path(tmp) / "old.yml"
            new_path = Path(tmp) / "new.yml"
            body_path.write_text(sync_body(None))
            old_path.write_text(OLD_ANSWERS)
            new_path.write_text(NEW_ANSWERS)
            self.assertEqual(guard.main([str(body_path), str(old_path), str(new_path)]), 1)

    def test_main_reads_a_missing_old_answers_file_as_a_retrofit(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            missing_old_path = Path(tmp) / "does-not-exist.yml"
            new_path = Path(tmp) / "new.yml"
            body_path.write_text("no trust diff line\n")
            new_path.write_text(NEW_ANSWERS)
            self.assertEqual(guard.main([str(body_path), str(missing_old_path), str(new_path)]), 0)


@unittest.skipUnless(
    (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "review-gate-check.yml").exists(),
    "review-gate-check.yml is not present in this checkout",
)
class WorkflowPinsTheGuardCheckoutToBase(unittest.TestCase):
    """The hazard this ticket names: with `on: pull_request`, `actions/checkout`
    defaults to the PR's merge ref, so a sync PR that edits a guard script or
    this workflow would run its own tampered copy against itself. The
    workflow must check out `pull_request.base.sha` before any guard step."""

    def _workflow_text(self) -> str:
        path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "review-gate-check.yml"
        return path.read_text()

    def test_workflow_checks_out_the_base_sha(self) -> None:
        # github.event.pull_request.base.sha also appears, pre-existing, in
        # two BASE_SHA: env lines unrelated to the checkout step -- match the
        # checkout step's own `ref:` key specifically, not any occurrence of
        # the expression anywhere in the file.
        text = self._workflow_text()
        checkout_step = re.search(r"uses:\s*actions/checkout@\S+.*?(?=\n\s*- (?:uses|name):|\Z)", text, re.DOTALL)
        self.assertIsNotNone(checkout_step, text)
        self.assertRegex(checkout_step.group(0), r"ref:\s*\$\{\{\s*github\.event\.pull_request\.base\.sha\s*\}\}")

    def test_workflow_invokes_the_trust_record_guard(self) -> None:
        text = self._workflow_text()
        self.assertIn("check_forge_sync_trust_record.py", text)


if __name__ == "__main__":
    unittest.main()
