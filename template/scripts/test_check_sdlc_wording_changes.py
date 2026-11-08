"""Guard tests for check_sdlc_wording_changes.py, run standalone:
python3 scripts/test_check_sdlc_wording_changes.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sdlc_wording_changes as guard  # noqa: E402


class StatementParsing(unittest.TestCase):
    def test_single_line_statement(self) -> None:
        text = "- **SDLC-001**: This document is the originating authority.\n"
        self.assertEqual(guard.statements(text), {"SDLC-001": "This document is the originating authority."})

    def test_wrapped_statement_joins_continuation_lines(self) -> None:
        text = (
            "- **SDLC-001**: This document is the originating authority for how\n"
            "  this project's software is built, reviewed, assured and released.\n"
        )
        self.assertEqual(
            guard.statements(text)["SDLC-001"],
            "This document is the originating authority for how this project's "
            "software is built, reviewed, assured and released.",
        )

    def test_desirable_marker_is_folded_into_the_stored_text(self) -> None:
        text = "- **SDLC-011** *(desirable)*: The agent that designs a feature does not build it.\n"
        self.assertEqual(
            guard.statements(text),
            {"SDLC-011": "(desirable) The agent that designs a feature does not build it."},
        )

    def test_four_space_continuation_is_still_joined(self) -> None:
        text = "- **SDLC-001**: First line\n    four-space continuation.\n"
        self.assertEqual(guard.statements(text), {"SDLC-001": "First line four-space continuation."})

    def test_two_statements_in_a_row_do_not_bleed_into_each_other(self) -> None:
        text = (
            "- **SDLC-001**: First statement, wrapped onto\n"
            "  a second line.\n"
            "- **SDLC-002**: Second statement.\n"
        )
        result = guard.statements(text)
        self.assertEqual(result["SDLC-001"], "First statement, wrapped onto a second line.")
        self.assertEqual(result["SDLC-002"], "Second statement.")

    def test_prose_outside_a_statement_is_not_collected(self) -> None:
        text = "Some prose paragraph with no bullet.\n\n- **SDLC-001**: A statement.\n"
        self.assertEqual(guard.statements(text), {"SDLC-001": "A statement."})


class ChangedStatements(unittest.TestCase):
    def test_no_change_reports_nothing(self) -> None:
        text = "- **SDLC-001**: Unchanged statement.\n"
        self.assertEqual(guard.changed(text, text), [])

    def test_reworded_statement_is_reported(self) -> None:
        old = "- **SDLC-001**: Old wording.\n"
        new = "- **SDLC-001**: New wording.\n"
        self.assertEqual(guard.changed(old, new), [("SDLC-001", "Old wording.", "New wording.")])

    def test_new_statement_is_reported_with_old_text_absent(self) -> None:
        old = "- **SDLC-001**: Existing.\n"
        new = "- **SDLC-001**: Existing.\n- **SDLC-002**: Brand new.\n"
        self.assertEqual(guard.changed(old, new), [("SDLC-002", "", "Brand new.")])

    def test_removed_statement_is_reported_with_new_text_absent(self) -> None:
        old = "- **SDLC-001**: Existing.\n- **SDLC-002**: Going away.\n"
        new = "- **SDLC-001**: Existing.\n"
        self.assertEqual(guard.changed(old, new), [("SDLC-002", "Going away.", "")])

    def test_non_statement_prose_changes_are_ignored(self) -> None:
        old = "Some intro text.\n\n- **SDLC-001**: A statement.\n"
        new = "A reworded intro paragraph, fixing a typo.\n\n- **SDLC-001**: A statement.\n"
        self.assertEqual(guard.changed(old, new), [])

    def test_adding_the_desirable_marker_is_reported_as_a_meaning_change(self) -> None:
        old = "- **SDLC-011**: Same words, same order.\n"
        new = "- **SDLC-011** *(desirable)*: Same words, same order.\n"
        self.assertEqual(
            guard.changed(old, new),
            [("SDLC-011", "Same words, same order.", "(desirable) Same words, same order.")],
        )

    def test_removing_the_desirable_marker_is_reported_as_a_meaning_change(self) -> None:
        old = "- **SDLC-011** *(desirable)*: Same words, same order.\n"
        new = "- **SDLC-011**: Same words, same order.\n"
        self.assertEqual(
            guard.changed(old, new),
            [("SDLC-011", "(desirable) Same words, same order.", "Same words, same order.")],
        )

    def test_rewrapping_a_statement_without_changing_its_words_is_not_reported(self) -> None:
        old = "- **SDLC-001**: One two three four five.\n"
        new = "- **SDLC-001**: One two three\n  four five.\n"
        self.assertEqual(guard.changed(old, new), [])


class MainExitCode(unittest.TestCase):
    def test_clean_run_exits_zero_with_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "old.md"
            new_path = Path(tmp) / "new.md"
            text = "- **SDLC-001**: Unchanged.\n"
            old_path.write_text(text)
            new_path.write_text(text)
            self.assertEqual(guard.main([str(old_path), str(new_path)]), 0)

    def test_a_reworded_statement_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "old.md"
            new_path = Path(tmp) / "new.md"
            old_path.write_text("- **SDLC-001**: Old.\n")
            new_path.write_text("- **SDLC-001**: New.\n")
            self.assertEqual(guard.main([str(old_path), str(new_path)]), 1)

    def test_a_missing_file_reads_as_no_statements_rather_than_erroring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "new.md"
            new_path.write_text("- **SDLC-001**: Brand new file.\n")
            missing_old_path = Path(tmp) / "does-not-exist.md"
            self.assertEqual(guard.main([str(missing_old_path), str(new_path)]), 1)


if __name__ == "__main__":
    unittest.main()
