"""Guard tests for check_pins.py, run standalone: python3 scripts/test_check_pins.py"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_pins  # noqa: E402


class StubBehaviour(unittest.TestCase):
    """CHECKS is empty until a consuming project's stage 0 fills it in; until
    then the script must say so and pass, never silently fail or silently
    pass with no explanation."""

    def test_empty_checks_passes_and_announces_itself(self) -> None:
        with mock.patch.object(check_pins, "CHECKS", []), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check_pins.main(), 0)
        self.assertIn("NOT RUNNING", out.getvalue())


class Dispatch(unittest.TestCase):
    """The guard test: once stage 0 adds a real check to CHECKS, main() must
    actually run it and fail the commit on what it reports -- dropping the
    aggregation, the exit-code mapping, or the stderr print must go red here."""

    def test_a_passing_check_with_no_findings_passes(self) -> None:
        with mock.patch.object(check_pins, "CHECKS", [lambda: []]):
            self.assertEqual(check_pins.main(), 0)

    def test_a_single_failing_check_fails_and_prints_its_lines(self) -> None:
        with (
            mock.patch.object(check_pins, "CHECKS", [lambda: ["requirements.txt: foo==1.2.* is not pinned"]]),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            self.assertEqual(check_pins.main(), 1)
        self.assertIn("foo==1.2.* is not pinned", err.getvalue())

    def test_findings_from_every_check_are_aggregated(self) -> None:
        checks = [lambda: ["a: unpinned"], lambda: [], lambda: ["b: unpinned"]]
        with (
            mock.patch.object(check_pins, "CHECKS", checks),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            self.assertEqual(check_pins.main(), 1)
        output = err.getvalue()
        self.assertIn("a: unpinned", output)
        self.assertIn("b: unpinned", output)

    def test_all_checks_passing_passes(self) -> None:
        with mock.patch.object(check_pins, "CHECKS", [lambda: [], lambda: []]):
            self.assertEqual(check_pins.main(), 0)


if __name__ == "__main__":
    unittest.main()
