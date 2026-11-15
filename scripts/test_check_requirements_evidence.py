"""Guard tests for check_requirements_evidence.py, run standalone: python3 scripts/test_check_requirements_evidence.py"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_requirements_evidence  # noqa: E402


class EvidenceShape(unittest.TestCase):
    """Shape, confinement and existence checks on a single Evidence paragraph."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text("pass\n")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_auth.py").write_text("pass\n")

    def check(self, body: str) -> tuple[int, str]:
        path = self.root / "docs" / "requirements" / "requirements-specification.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        baseline = self.root / "baseline.json"
        with (
            mock.patch.object(check_requirements_evidence, "BASELINE", baseline),
            mock.patch.object(check_requirements_evidence, "REPO_ROOT", self.root),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            code = check_requirements_evidence.main([str(path)])
        return code, err.getvalue()

    def test_well_formed_paragraph_with_existing_paths_passes(self) -> None:
        code, _ = self.check("**Evidence (FR-001):** `src/auth.py`, `tests/test_auth.py`\n")
        self.assertEqual(code, 0)

    def test_missing_path_fails(self) -> None:
        code, err = self.check("**Evidence:** `src/does_not_exist.py`\n")
        self.assertEqual(code, 1)
        self.assertIn("do not exist", err)

    def test_prose_after_paths_fails(self) -> None:
        code, err = self.check("**Evidence:** `src/auth.py`, see the design doc for more\n")
        self.assertEqual(code, 1)
        self.assertIn("not a plain comma-separated list", err)

    def test_empty_evidence_paragraph_fails(self) -> None:
        code, err = self.check("**Evidence:**\n")
        self.assertEqual(code, 1)
        self.assertIn("names no files", err)

    def test_line_that_only_mentions_evidence_inline_is_not_matched(self) -> None:
        code, _ = self.check("- **Evidence.** A paragraph starting with `**Evidence:**` names files.\n")
        self.assertEqual(code, 0)

    def test_non_evidence_lines_are_ignored(self) -> None:
        code, _ = self.check("# Spec\n\nNo evidence paragraphs here at all.\n")
        self.assertEqual(code, 0)

    def test_absolute_path_fails(self) -> None:
        code, err = self.check("**Evidence:** `/etc/passwd`\n")
        self.assertEqual(code, 1)
        self.assertIn("not repo-relative", err)

    def test_path_traversal_outside_repo_root_fails(self) -> None:
        code, err = self.check("**Evidence:** `../outside.py`\n")
        self.assertEqual(code, 1)
        self.assertIn("not repo-relative", err)

    def test_near_miss_label_shape_fails(self) -> None:
        code, err = self.check("**Evidence**: `src/auth.py`\n")
        self.assertEqual(code, 1)
        self.assertIn("not the canonical Evidence label shape", err)

    def test_wrapped_paragraph_with_paths_on_both_lines_passes(self) -> None:
        code, _ = self.check("**Evidence:** `src/auth.py`,\n`tests/test_auth.py`\n")
        self.assertEqual(code, 0)

    def test_wrapped_paragraph_with_prose_on_a_continuation_line_fails(self) -> None:
        code, err = self.check("**Evidence:** `src/auth.py`,\nsee also the design doc\n")
        self.assertEqual(code, 1)
        self.assertIn("not a plain comma-separated list", err)

    def test_duplicate_anonymous_labels_in_one_file_get_distinct_keys(self) -> None:
        code, err = self.check("**Evidence:** `src/missing1.py`\n\n**Evidence:** `src/missing2.py`\n")
        self.assertEqual(code, 1)
        self.assertIn("missing1.py", err)
        self.assertIn("missing2.py", err)
        # Two distinct baseline keys (the second's label is disambiguated with
        # "#2"), not one key that silently drops the second finding.
        self.assertEqual(err.count(":Evidence:"), 1)
        self.assertEqual(err.count(":Evidence#2:"), 1)


class BaselineRatchet(unittest.TestCase):
    """The shrink-only baseline: seeded errors pass once, drift and removal both fail,
    and keys stay stable under both a relative-path move and a line shift above them."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "docs" / "requirements" / "requirements-specification.md"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def run_with_baseline(self, body: str, baseline: dict[str, str], argv: list[str] | None = None) -> tuple[int, str]:
        self.path.write_text(body)
        baseline_path = self.root / "baseline.json"
        baseline_path.write_text(json.dumps(baseline))
        with (
            mock.patch.object(check_requirements_evidence, "BASELINE", baseline_path),
            mock.patch.object(check_requirements_evidence, "DEFAULT_FILES", [self.path]),
            mock.patch.object(check_requirements_evidence, "REPO_ROOT", self.root),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            code = check_requirements_evidence.main(argv if argv is not None else [str(self.path)])
        return code, err.getvalue()

    def key(self) -> str:
        return "docs/requirements/requirements-specification.md:Evidence"

    def test_baselined_error_with_matching_text_passes(self) -> None:
        code, _ = self.run_with_baseline(
            "**Evidence:** `missing.py`\n",
            {self.key(): "path(s) do not exist: missing.py"},
        )
        self.assertEqual(code, 0)

    def test_baselined_error_whose_text_changed_fails(self) -> None:
        code, err = self.run_with_baseline(
            "**Evidence:** `missing.py`, `also_missing.py`\n",
            {self.key(): "path(s) do not exist: missing.py"},
        )
        self.assertEqual(code, 1)
        self.assertIn("error changed since baselined", err)

    def test_full_run_flags_a_fixed_entry_still_in_the_baseline(self) -> None:
        code, err = self.run_with_baseline(
            "No evidence paragraph here any more.\n",
            {self.key(): "path(s) do not exist: missing.py"},
            argv=[],
        )
        self.assertEqual(code, 1)
        self.assertIn("no longer failing", err)

    def test_baseline_key_is_stable_when_unrelated_lines_are_added_above_it(self) -> None:
        baseline = {self.key(): "path(s) do not exist: missing.py"}
        code, _ = self.run_with_baseline("**Evidence:** `missing.py`\n", baseline)
        self.assertEqual(code, 0)
        code, _ = self.run_with_baseline(
            "# A new heading\n\nSome unrelated new prose above the paragraph.\n\n**Evidence:** `missing.py`\n",
            baseline,
        )
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
