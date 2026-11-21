"""Guard tests for check_coverage_baseline.py, run standalone:
python3 scripts/test_check_coverage_baseline.py"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_coverage_baseline  # noqa: E402

try:
    from _git_env import clean_git_env  # noqa: E402
except ImportError:
    from _git_subprocess import clean_git_env  # noqa: E402


def _write_baseline(path: Path, modules: dict) -> None:
    path.write_text(json.dumps({"modules": modules}), encoding="utf-8")


class Checks(unittest.TestCase):
    """The guard test: each of these must go red if the shape check, the
    range check, the growth check, or the missing-file/unreachable-origin
    fallbacks are removed."""

    def _run(self, *, modules: dict, module_root: Path, origin_modules: dict | None) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "coverage_baseline.json"
            _write_baseline(baseline, modules)
            stderr = io.StringIO()
            with (
                mock.patch.object(check_coverage_baseline, "BASELINE", baseline),
                mock.patch.object(check_coverage_baseline, "MODULE_ROOT", module_root),
                mock.patch.object(check_coverage_baseline, "_origin_main_modules", return_value=origin_modules),
                contextlib.redirect_stderr(stderr),
            ):
                return check_coverage_baseline.main(), stderr.getvalue()

    def test_no_baseline_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with (
                mock.patch.object(check_coverage_baseline, "BASELINE", Path(tmp) / "missing.json"),
                mock.patch.object(check_coverage_baseline, "MODULE_ROOT", Path(tmp)),
                mock.patch.object(check_coverage_baseline, "_origin_main_modules", return_value=None),
                contextlib.redirect_stderr(stderr),
            ):
                status = check_coverage_baseline.main()
        self.assertEqual(status, 0)

    def test_entry_for_a_module_that_does_not_exist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            status, stderr = self._run(modules={"missing/module.py": 90}, module_root=tmp, origin_modules=None)
        self.assertEqual(status, 1)
        self.assertIn("not found under", stderr)

    def test_entry_for_a_real_module_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "real_module.py").write_text("x = 1\n", encoding="utf-8")
            status, stderr = self._run(modules={"real_module.py": 90}, module_root=tmp, origin_modules=None)
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")

    def test_percentage_above_100_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "m.py").write_text("x = 1\n", encoding="utf-8")
            status, stderr = self._run(modules={"m.py": 150}, module_root=tmp, origin_modules=None)
        self.assertEqual(status, 1)
        self.assertIn("not a 0-100 coverage percentage", stderr)

    def test_negative_percentage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "m.py").write_text("x = 1\n", encoding="utf-8")
            status, stderr = self._run(modules={"m.py": -5}, module_root=tmp, origin_modules=None)
        self.assertEqual(status, 1)
        self.assertIn("not a 0-100 coverage percentage", stderr)

    def test_non_numeric_percentage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "m.py").write_text("x = 1\n", encoding="utf-8")
            status, stderr = self._run(modules={"m.py": "high"}, module_root=tmp, origin_modules=None)
        self.assertEqual(status, 1)
        self.assertIn("not a 0-100 coverage percentage", stderr)

    def test_unreachable_origin_skips_growth_check_and_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "m.py").write_text("x = 1\n", encoding="utf-8")
            stdout = io.StringIO()
            with (
                mock.patch.object(check_coverage_baseline, "BASELINE", tmp / "coverage_baseline.json"),
                mock.patch.object(check_coverage_baseline, "MODULE_ROOT", tmp),
                mock.patch.object(check_coverage_baseline, "_origin_main_modules", return_value=None),
                contextlib.redirect_stdout(stdout),
            ):
                _write_baseline(tmp / "coverage_baseline.json", {"m.py": 90})
                status = check_coverage_baseline.main()
        self.assertEqual(status, 0)
        self.assertIn("origin/main not reachable", stdout.getvalue())

    def test_coverage_fallen_against_origin_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "m.py").write_text("x = 1\n", encoding="utf-8")
            status, stderr = self._run(modules={"m.py": 80}, module_root=tmp, origin_modules={"m.py": 90})
        self.assertEqual(status, 1)
        self.assertIn("fell from 90", stderr)
        self.assertIn("to 80", stderr)

    def test_coverage_equal_to_origin_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "m.py").write_text("x = 1\n", encoding="utf-8")
            status, stderr = self._run(modules={"m.py": 90}, module_root=tmp, origin_modules={"m.py": 90})
        self.assertEqual(status, 0)

    def test_coverage_risen_above_origin_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "m.py").write_text("x = 1\n", encoding="utf-8")
            status, stderr = self._run(modules={"m.py": 95}, module_root=tmp, origin_modules={"m.py": 90})
        self.assertEqual(status, 0)

    def test_an_origin_module_not_in_the_current_baseline_is_not_a_regression(self) -> None:
        """A module dropped from the current baseline (deleted, or genuinely
        untracked now) is not the same thing as its coverage falling."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            status, stderr = self._run(modules={}, module_root=tmp, origin_modules={"gone.py": 90})
        self.assertEqual(status, 0)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=clean_git_env())


class GrowthCheckAgainstARealOriginMain(unittest.TestCase):
    """Every other test here mocks `_origin_main_modules`, so none of them run
    the real `git show origin/main:...` read at all; a bug in that call (e.g.
    reading `HEAD:` instead of `origin/main:`) would pass every test above.
    This one builds a throwaway origin+clone pair with a real, divergent
    `origin/main` and calls `main()` with `_origin_main_modules` unmocked."""

    def test_growth_check_reads_the_real_origin_main_ref_not_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            origin = tmp / "origin"
            origin.mkdir()
            _git("init", "-q", "-b", "main", cwd=origin)
            (origin / "scripts").mkdir()
            _write_baseline(origin / "scripts" / "coverage_baseline.json", {"m.py": 90})
            _git("add", "scripts/coverage_baseline.json", cwd=origin)
            _git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init", cwd=origin)

            local = tmp / "local"
            _git("clone", "-q", str(origin), str(local), cwd=tmp)
            # A local-only commit, never pushed: HEAD now disagrees with the
            # origin/main remote-tracking ref captured at clone time (90).
            # If the guard ever reads `HEAD:` instead of `origin/main:`, it
            # would see this 70 instead and the assertions below would miss
            # the real regression (current 80 is not below 70).
            _write_baseline(local / "scripts" / "coverage_baseline.json", {"m.py": 70})
            _git("add", "scripts/coverage_baseline.json", cwd=local)
            _git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "diverge", cwd=local)

            (local / "m.py").write_text("x = 1\n", encoding="utf-8")
            current_baseline = local / "current_coverage_baseline.json"
            _write_baseline(current_baseline, {"m.py": 80})

            cwd = Path.cwd()
            os.chdir(local)
            try:
                stderr = io.StringIO()
                with (
                    mock.patch.object(check_coverage_baseline, "BASELINE", current_baseline),
                    mock.patch.object(check_coverage_baseline, "MODULE_ROOT", local),
                    contextlib.redirect_stderr(stderr),
                ):
                    status = check_coverage_baseline.main()
            finally:
                os.chdir(cwd)
        self.assertEqual(status, 1)
        self.assertIn("fell from 90", stderr.getvalue())
        self.assertIn("to 80", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
