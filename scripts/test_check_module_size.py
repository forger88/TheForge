"""Guard tests for check_module_size.py, run standalone: python3 scripts/test_check_module_size.py"""

from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jinja_paths import is_rendered  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# check_module_size.py.jinja isn't valid Python until Copier strips its
# .jinja suffix and fills in the two caps, so every class below is skipped
# rather than imported against TheForge's own unrendered tree -- a plain
# SkipTest raised here would only be caught by unittest discover's loader,
# not a standalone `python3 test_check_module_size.py` run.
RENDERED = is_rendered()
if RENDERED:
    import check_module_size  # noqa: E402

    MODULE_CAP = check_module_size.MAX_MODULE_LINES
    FUNCTION_CAP = check_module_size.MAX_FUNCTION_CODE_LINES
else:
    check_module_size = None
    MODULE_CAP = FUNCTION_CAP = 0

SKIP_REASON = "unrendered template: check_module_size.py doesn't exist until Copier strips .jinja"
skip_unless_rendered = unittest.skipUnless(RENDERED, SKIP_REASON)


def function_source(code_lines: int) -> str:
    body = "".join(f"    x{i} = {i}\n" for i in range(code_lines - 1))
    return '"""Module."""\n\n\ndef f():\n    """Docstring lines do not count."""\n    # nor comments\n\n' + body


@skip_unless_rendered
class SizeCaps(unittest.TestCase):
    """Both sides of each cap."""

    def check(self, source: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.py"
            path.write_text(source)
            with (
                mock.patch.object(check_module_size, "ALLOWLIST", path.with_name("none.json")),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                return check_module_size.main([str(path)])

    def test_function_at_the_cap_passes(self) -> None:
        self.assertEqual(self.check(function_source(FUNCTION_CAP)), 0)

    def test_function_over_the_cap_fails(self) -> None:
        self.assertEqual(self.check(function_source(FUNCTION_CAP + 1)), 1)

    def test_module_at_the_cap_passes(self) -> None:
        self.assertEqual(self.check("x = 1\n" * MODULE_CAP), 0)

    def test_module_over_the_cap_fails(self) -> None:
        self.assertEqual(self.check("x = 1\n" * (MODULE_CAP + 1)), 1)


@skip_unless_rendered
class AllowlistRatchet(unittest.TestCase):
    """A full run (no argv) compares every tracked file/function against its allowlist entry four ways."""

    def run_full(self, sources: dict[str, str], allow_sizes: dict[str, int]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, body in sources.items():
                path = Path(tmp) / name
                path.write_text(body)
                paths.append(path)
            allow = {str(Path(tmp) / name): size for name, size in allow_sizes.items()}
            allow_path = Path(tmp) / "allow.json"
            allow_path.write_text(json.dumps(allow))
            stderr = io.StringIO()
            with (
                mock.patch.object(check_module_size, "ALLOWLIST", allow_path),
                mock.patch.object(check_module_size, "tracked_sources", return_value=paths),
                contextlib.redirect_stderr(stderr),
            ):
                return check_module_size.main([]), stderr.getvalue()

    def test_entry_that_grew_past_its_allowance_fails(self) -> None:
        code, err = self.run_full({"m.py": "x = 1\n" * 5}, {"m.py": 3})
        self.assertEqual(code, 1)
        self.assertIn("grew to 5 lines, past its allowlisted 3", err)

    def test_entry_now_under_the_cap_must_be_removed(self) -> None:
        code, err = self.run_full({"m.py": "x = 1\n" * 2}, {"m.py": 10})
        self.assertEqual(code, 1)
        self.assertIn("now 2 lines, under the cap; remove its allowlist entry", err)

    def test_entry_that_shrank_without_being_lowered_fails(self) -> None:
        size = MODULE_CAP + 5
        allowed = MODULE_CAP + 10
        code, err = self.run_full({"m.py": "x = 1\n" * size}, {"m.py": allowed})
        self.assertEqual(code, 1)
        self.assertIn(f"shrank to {size} lines; lower its allowlist entry from {allowed} to {size}", err)

    def test_stale_entry_for_a_removed_file_fails(self) -> None:
        code, err = self.run_full({"m.py": "x = 1\n"}, {"gone.py": 50})
        self.assertEqual(code, 1)
        self.assertIn("gone.py: allowlisted but not found; remove its entry", err)


@skip_unless_rendered
class NestedFunctionsAndMethods(unittest.TestCase):
    """python_functions attributes nested defs to their parent and dotted-prefixes class methods."""

    def test_nested_function_counts_toward_its_parent_not_separately(self) -> None:
        inner_lines = FUNCTION_CAP
        source = (
            '"""Module."""\n\n\n'
            "def outer():\n"
            "    y = 0\n"
            "    def inner():\n"
            + "".join(f"        z{i} = {i}\n" for i in range(inner_lines))
            + "    inner()\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.py"
            path.write_text(source)
            sizes = check_module_size.python_functions(path, source)
        self.assertEqual(set(sizes), {f"{path}::outer"})
        self.assertGreater(sizes[f"{path}::outer"], FUNCTION_CAP)

    def test_method_is_measured_under_its_class_dotted_name(self) -> None:
        source = '"""Module."""\n\n\nclass Widget:\n    def render(self):\n        return 1\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.py"
            path.write_text(source)
            sizes = check_module_size.python_functions(path, source)
        self.assertEqual(sizes.get(f"{path}::Widget.render"), 2)


@skip_unless_rendered
class VendoredSkillsSkipped(unittest.TestCase):
    def test_full_run_skips_files_under_agents_skills_only(self) -> None:
        listing = ".agents/skills/some-skill/scripts/vendored.js\nsrc/app/export.py\n"
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout=listing, stderr="")
        with mock.patch.object(check_module_size.subprocess, "run", return_value=done):
            self.assertEqual(check_module_size.tracked_sources(), [Path("src/app/export.py")])


@skip_unless_rendered
class CapsMatchTheRuleAndTheAnswers(unittest.TestCase):
    """The rule text and the guard render from the same answers; a hand edit to either goes red here."""

    def test_answers_file_holds_the_guards_caps(self) -> None:
        answers = (ROOT / ".copier-answers.yml").read_text(encoding="utf-8")
        self.assertRegex(answers, rf"(?m)^max_module_lines: {MODULE_CAP}$")
        self.assertRegex(answers, rf"(?m)^max_function_code_lines: {FUNCTION_CAP}$")

    def test_rule_states_the_guards_caps(self) -> None:
        rule = (ROOT / ".forge" / "code-shape-rules.md").read_text(encoding="utf-8")
        sentence = re.search(r"(?m)^Keep a module under (\d+) lines and a function under (\d+) code lines", rule)
        self.assertIsNotNone(sentence)
        self.assertEqual((int(sentence.group(1)), int(sentence.group(2))), (MODULE_CAP, FUNCTION_CAP))


if __name__ == "__main__":
    unittest.main()
