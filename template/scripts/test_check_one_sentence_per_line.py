"""Guard tests for check_one_sentence_per_line.py, run standalone:
python3 scripts/test_check_one_sentence_per_line.py"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_one_sentence_per_line as guard  # noqa: E402


class OffendingLines(unittest.TestCase):
    """The guard test: each of these must go red if a skip rule (heading,
    list item, table row, block quote, fenced code), the inline-code or
    link-target stripping, or the abbreviation list is removed."""

    def test_single_sentence_line_passes(self) -> None:
        self.assertEqual(guard.offending_lines("One clear sentence.\n"), [])

    def test_two_sentences_on_one_line_is_flagged(self) -> None:
        hits = guard.offending_lines("First sentence. Second sentence.\n")
        self.assertEqual([n for n, _ in hits], [1])

    def test_heading_line_is_skipped_even_with_two_sentences(self) -> None:
        self.assertEqual(guard.offending_lines("# First sentence. Second sentence.\n"), [])

    def test_list_item_line_is_skipped(self) -> None:
        self.assertEqual(guard.offending_lines("- First sentence. Second sentence.\n"), [])

    def test_numbered_list_item_line_is_skipped(self) -> None:
        self.assertEqual(guard.offending_lines("1. First sentence. Second sentence.\n"), [])

    def test_table_row_is_skipped(self) -> None:
        # No pipe between the two sentences: without SKIP_LINE's table-row
        # rule this line would otherwise match SENTENCE_BREAK and be flagged.
        self.assertEqual(guard.offending_lines("| First. Second. |\n"), [])

    def test_block_quote_line_is_skipped(self) -> None:
        self.assertEqual(guard.offending_lines("> First sentence. Second sentence.\n"), [])

    def test_html_comment_line_is_skipped(self) -> None:
        self.assertEqual(guard.offending_lines("<!-- First sentence. Second sentence. -->\n"), [])

    def test_fenced_code_block_content_is_skipped(self) -> None:
        text = "```\nFirst sentence. Second sentence.\n```\n"
        self.assertEqual(guard.offending_lines(text), [])

    def test_content_after_a_closed_fence_is_still_checked(self) -> None:
        text = "```\ncode\n```\nFirst sentence. Second sentence.\n"
        hits = guard.offending_lines(text)
        self.assertEqual([n for n, _ in hits], [4])

    def test_inline_code_span_periods_do_not_trigger_a_break(self) -> None:
        # A capital right after the span's period: without INLINE_CODE
        # stripping this would match SENTENCE_BREAK and be flagged.
        self.assertEqual(guard.offending_lines("Run `Stop. Go` now.\n"), [])

    def test_link_target_periods_do_not_trigger_a_break(self) -> None:
        # A capital right after the target's period: without LINK_TARGET
        # stripping this would match SENTENCE_BREAK and be flagged.
        self.assertEqual(guard.offending_lines("See [x](a. B.md) for more.\n"), [])

    def test_known_abbreviation_does_not_trigger_a_break(self) -> None:
        # A capital right after the abbreviation's period: without stripping
        # it from ABBREVIATIONS this would match SENTENCE_BREAK and be flagged.
        self.assertEqual(guard.offending_lines("Keep it short, e.g. One line.\n"), [])

    def test_known_abbreviation_does_not_mask_a_real_second_sentence(self) -> None:
        hits = guard.offending_lines("Keep it short, e.g. one line. Then stop.\n")
        self.assertEqual([n for n, _ in hits], [1])

    def test_blank_line_is_skipped(self) -> None:
        self.assertEqual(guard.offending_lines("\n"), [])


class Main(unittest.TestCase):
    def test_explicit_file_argument_with_a_violation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            path = Path(tmp_str) / "rule.md"
            path.write_text("First sentence. Second sentence.\n", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = guard.main([str(path)])
        self.assertEqual(status, 1)
        self.assertIn(str(path), stdout.getvalue())

    def test_explicit_file_argument_with_no_violation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            path = Path(tmp_str) / "rule.md"
            path.write_text("One sentence per line.\nAnother sentence.\n", encoding="utf-8")
            status = guard.main([str(path)])
        self.assertEqual(status, 0)

    def test_default_glob_checks_dot_forge_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / ".forge").mkdir()
            (tmp / ".forge" / "rule.md").write_text("First sentence. Second sentence.\n", encoding="utf-8")
            cwd = Path.cwd()
            os.chdir(tmp)
            try:
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    status = guard.main([])
            finally:
                os.chdir(cwd)
        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
