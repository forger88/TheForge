"""Guard tests for check_dead_code.py, run standalone: python3 scripts/test_check_dead_code.py"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_dead_code  # noqa: E402

FINDING = "src/app/export.py:3: unused function 'render'\n"


def finder(returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="finder crashed")


class DeadCodeRatchet(unittest.TestCase):
    """Driven with a stand-in finder that exits 0 when clean and 3 with findings."""

    def run_with(self, result: subprocess.CompletedProcess[str], baseline: dict[str, int]) -> int:
        with (
            mock.patch.object(check_dead_code, "FINDER_COMMAND", ["finder"]),
            mock.patch.object(check_dead_code, "FINDER_OK_EXIT_CODES", {0, 3}),
            mock.patch.object(check_dead_code.subprocess, "run", return_value=result),
            mock.patch.object(check_dead_code, "BASELINE", mock.Mock(exists=lambda: True, read_text=lambda: json.dumps(baseline))),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return check_dead_code.main()

    def test_crashed_finder_fails_even_with_no_output(self) -> None:
        self.assertEqual(self.run_with(finder(1), {}), 1)

    def test_clean_run_passes(self) -> None:
        self.assertEqual(self.run_with(finder(0), {}), 0)

    def test_new_finding_fails(self) -> None:
        self.assertEqual(self.run_with(finder(3, FINDING), {}), 1)

    def test_finding_within_baseline_passes(self) -> None:
        self.assertEqual(self.run_with(finder(3, FINDING), {"src/app/export.py": 1}), 0)

    def test_count_below_an_unlowered_baseline_fails(self) -> None:
        self.assertEqual(self.run_with(finder(3, FINDING), {"src/app/export.py": 2}), 1)

    def test_baseline_entry_with_nothing_left_fails(self) -> None:
        self.assertEqual(self.run_with(finder(0), {"src/app/export.py": 1}), 1)


class UnconfiguredStub(unittest.TestCase):
    def test_stub_says_it_is_not_running(self) -> None:
        out = io.StringIO()
        with mock.patch.object(check_dead_code, "FINDER_COMMAND", []), contextlib.redirect_stdout(out):
            self.assertEqual(check_dead_code.main(), 0)
        self.assertIn("NOT RUNNING", out.getvalue())


if __name__ == "__main__":
    unittest.main()
