"""Guard tests for check-no-issue-refs.sh.

Standalone, standard-library-only:

    python3 scripts/test_check_no_issue_refs.py
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check-no-issue-refs.sh"

# Built by concatenation, not as a literal "#NN" substring: this file is
# itself scanned by the no-issue-refs pre-commit hook, which can't tell a
# test fixture from real shipped content.
REF2 = "#" + "42"
REF6 = "#" + "123456"


def run_check(text: str, filename: str = "some-file.md", *, warn: bool = False) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / filename
        target.write_text(text)
        args = [str(CHECK)]
        if warn:
            args.append("--warn")
        args.append(str(target))
        return subprocess.run(args, env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True)


class ChecksNoIssueRefs(unittest.TestCase):
    """The guard test: loosening the regex, or adding a path to the skip list
    beyond THIRD_PARTY.md, must go red here."""

    def test_a_two_digit_reference_fails(self) -> None:
        result = run_check(f"see issue {REF2} for details\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REF2, result.stdout + result.stderr)

    def test_a_six_digit_reference_fails(self) -> None:
        result = run_check(f"closes {REF6}\n")
        self.assertNotEqual(result.returncode, 0)

    def test_a_seven_digit_reference_does_not_match(self) -> None:
        """Outside the documented 2-6 digit range -- not an issue-number shape
        this repository would ever actually see, so it is deliberately left alone."""
        result = run_check("see #1234567 in some external system\n")
        self.assertEqual(result.returncode, 0)

    def test_clean_text_passes(self) -> None:
        result = run_check("no references here at all\n")
        self.assertEqual(result.returncode, 0)

    def test_a_single_digit_reference_does_not_match(self) -> None:
        """Documented exception: a list or hypothesis number like "#3", not an
        issue/PR reference."""
        result = run_check("see hypothesis #3 above\n")
        self.assertEqual(result.returncode, 0)

    def test_a_hex_colour_does_not_match(self) -> None:
        result = run_check("background: #1a2b3c;\n")
        self.assertEqual(result.returncode, 0)

    def test_third_party_md_is_skipped_by_path(self) -> None:
        """The one documented exception: an upstream credits file may cite a
        real project's own issue numbers."""
        result = run_check(f"upstream fix for {REF2}\n", filename="THIRD_PARTY.md")
        self.assertEqual(result.returncode, 0)

    def test_third_party_md_under_a_subdirectory_is_also_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / ".agents" / "skills" / "some-skill"
            sub.mkdir(parents=True)
            target = sub / "THIRD_PARTY.md"
            target.write_text(f"upstream fix for {REF2}\n")
            result = subprocess.run(
                [str(CHECK), str(target)],
                env={"PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)

    def test_a_file_under_a_subdirectory_is_still_scanned(self) -> None:
        """Guard for a widened skip clause (e.g. `*/.agents/*`) that would
        exempt a whole shipped directory by path shape rather than by the one
        documented THIRD_PARTY.md exception: an ordinary file several levels
        deep must still be scanned and still fail on a real reference."""
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / ".agents" / "skills" / "some-skill"
            sub.mkdir(parents=True)
            target = sub / "SKILL.md"
            target.write_text(f"see issue {REF2} for details\n")
            result = subprocess.run(
                [str(CHECK), str(target)],
                env={"PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(REF2, result.stdout + result.stderr)

    def test_a_third_party_near_miss_filename_is_still_scanned(self) -> None:
        """Guard for a widened skip clause (e.g. `*THIRD_PARTY*`) that would
        exempt any filename merely containing THIRD_PARTY rather than the one
        documented exact THIRD_PARTY.md exception."""
        result = run_check(f"see issue {REF2} for details\n", filename="THIRD_PARTY_NOTES.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REF2, result.stdout + result.stderr)

    def test_a_missing_file_is_skipped_not_an_error(self) -> None:
        """pre-commit can hand this script a path that no longer exists (e.g. a
        deleted file in a staged diff); it must not crash on that."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.md"
            result = subprocess.run(
                [str(CHECK), str(missing)],
                env={"PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)

    def test_warn_mode_lists_the_hit_but_exits_zero(self) -> None:
        result = run_check(f"closes {REF2}\n", warn=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn(REF2, result.stdout + result.stderr)
        self.assertIn("Warning only", result.stdout + result.stderr)

    def test_strict_mode_is_the_default_and_fails(self) -> None:
        """Proves warn mode is opt-in, not the default -- the guard test for
        the --warn flag itself: if strict mode silently became warn-only, this
        would go from failing to passing."""
        result = run_check(f"closes {REF2}\n", warn=False)
        self.assertNotEqual(result.returncode, 0)

    def test_multiple_files_all_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.md"
            clean.write_text("nothing here\n")
            dirty = Path(tmp) / "dirty.md"
            dirty.write_text(f"closes {REF2}\n")
            result = subprocess.run(
                [str(CHECK), str(clean), str(dirty)],
                env={"PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dirty.md", result.stdout + result.stderr)
            self.assertNotIn("clean.md:", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
