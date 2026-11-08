"""Guard tests for check_sdlc_wording_hold.py, run standalone:
python3 scripts/test_check_sdlc_wording_hold.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sdlc_wording_hold as guard  # noqa: E402

SYNC_BODY_PREFIX = "Before: _commit abc123.\n\nAfter: _commit def456.\n\nDrift before this sync: none.\n\n"


def sync_body(held_line: str | None) -> str:
    held = f"- SDLC wording held: {held_line}\n" if held_line is not None else ""
    return SYNC_BODY_PREFIX + held


class NotASyncPR(unittest.TestCase):
    def test_a_body_with_no_sync_marker_is_never_checked(self) -> None:
        body = "Before: x\n\nAfter: y\n\nTicket: Closes #1\n"
        old = "- **SDLC-001**: Old.\n"
        new = "- **SDLC-001**: New.\n"
        self.assertEqual(guard.check(body, old, new), [])

    def test_an_ordinary_lifecycle_doc_pr_with_a_real_change_and_no_sync_marker_passes(self) -> None:
        body = "Before: x\n\nAfter: y\n\nOwner approved this wording in chat.\n"
        old = "- **SDLC-042**: Old wording.\n"
        new = "- **SDLC-042**: New, owner-approved wording.\n"
        self.assertEqual(guard.check(body, old, new), [])


class UnrevertedWording(unittest.TestCase):
    def test_a_surviving_statement_change_fails_even_with_a_held_line(self) -> None:
        body = sync_body("none")
        old = "- **SDLC-001**: Old wording.\n"
        new = "- **SDLC-001**: New wording that slipped through.\n"
        failures = guard.check(body, old, new)
        self.assertEqual(len(failures), 1)
        self.assertIn("SDLC-001", failures[0])

    def test_multiple_surviving_changes_are_all_named(self) -> None:
        body = sync_body("none")
        old = "- **SDLC-001**: Old one.\n- **SDLC-002**: Old two.\n"
        new = "- **SDLC-001**: New one.\n- **SDLC-002**: New two.\n"
        failures = guard.check(body, old, new)
        self.assertEqual(len(failures), 1)
        self.assertIn("SDLC-001", failures[0])
        self.assertIn("SDLC-002", failures[0])

    def test_a_correctly_reverted_sync_with_nothing_held_passes(self) -> None:
        body = sync_body("none")
        text = "- **SDLC-001**: Unchanged statement.\n"
        self.assertEqual(guard.check(body, text, text), [])

    def test_a_correctly_held_statement_passes_when_the_final_file_matches_pre_sync(self) -> None:
        # The sync branch reverted SDLC-003 back to its pre-sync wording per
        # step 3, so the final diff is empty even though something was held.
        body = sync_body("SDLC-003 -> lifecycle-doc PR <n>")
        text = "- **SDLC-001**: Unchanged.\n- **SDLC-003**: Pre-sync wording.\n"
        self.assertEqual(guard.check(body, text, text), [])


class MissingEvidenceLine(unittest.TestCase):
    def test_no_held_line_at_all_fails_even_with_nothing_to_hold(self) -> None:
        body = SYNC_BODY_PREFIX
        text = "- **SDLC-001**: Unchanged.\n"
        failures = guard.check(body, text, text)
        self.assertEqual(len(failures), 1)
        self.assertIn("SDLC wording held", failures[0])

    def test_a_blank_held_line_fails(self) -> None:
        body = sync_body("")
        text = "- **SDLC-001**: Unchanged.\n"
        failures = guard.check(body, text, text)
        self.assertEqual(len(failures), 1)
        self.assertIn("SDLC wording held", failures[0])

    def test_a_blank_held_line_fails_even_with_trailing_content_after_it(self) -> None:
        # A real PR's held line is rarely the last line of the body: it's
        # usually followed by Tests:/Review: sections or similar. A `\s*`
        # regex would cross the blank held line's newline and pick up the
        # next non-blank line's text as the "value", wrongly passing.
        body = sync_body("") + "\nTests: none.\n\nReview: self-review only.\n"
        text = "- **SDLC-001**: Unchanged.\n"
        failures = guard.check(body, text, text)
        self.assertEqual(len(failures), 1)
        self.assertIn("SDLC wording held", failures[0])

    def test_a_held_line_with_real_content_passes(self) -> None:
        body = sync_body("none")
        text = "- **SDLC-001**: Unchanged.\n"
        self.assertEqual(guard.check(body, text, text), [])

    def test_both_failures_are_reported_together(self) -> None:
        body = SYNC_BODY_PREFIX
        old = "- **SDLC-001**: Old.\n"
        new = "- **SDLC-001**: New.\n"
        failures = guard.check(body, old, new)
        self.assertEqual(len(failures), 2)


class MainExitCode(unittest.TestCase):
    def test_main_requires_exactly_three_arguments(self) -> None:
        self.assertEqual(guard.main(["one", "two"]), 2)

    def test_main_passes_file_paths_through(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            old_path = Path(tmp) / "old.md"
            new_path = Path(tmp) / "new.md"
            body_path.write_text("Before: x\n\nAfter: y\n\nTicket: Closes #1\n")
            old_path.write_text("- **SDLC-001**: Old.\n")
            new_path.write_text("- **SDLC-001**: New.\n")
            # No sync marker in the body, so an unheld change still passes.
            self.assertEqual(guard.main([str(body_path), str(old_path), str(new_path)]), 0)

    def test_main_fails_a_real_sync_pr_with_an_unreverted_change(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            old_path = Path(tmp) / "old.md"
            new_path = Path(tmp) / "new.md"
            body_path.write_text(sync_body("none"))
            old_path.write_text("- **SDLC-001**: Old.\n")
            new_path.write_text("- **SDLC-001**: New.\n")
            self.assertEqual(guard.main([str(body_path), str(old_path), str(new_path)]), 1)

    def test_main_reads_a_missing_old_doc_as_no_statements(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            missing_old_path = Path(tmp) / "does-not-exist.md"
            new_path = Path(tmp) / "new.md"
            body_path.write_text(sync_body("none"))
            new_path.write_text("- **SDLC-001**: Brand new file.\n")
            self.assertEqual(guard.main([str(body_path), str(missing_old_path), str(new_path)]), 1)


if __name__ == "__main__":
    unittest.main()
