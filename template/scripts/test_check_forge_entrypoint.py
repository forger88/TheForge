"""Guard tests for check_forge_entrypoint.py.

Every test builds its own fixture directory and never reads this
repository's `template/`. This test no longer ships to consumers:
it runs only here, and directly against `template/scripts/` via
`template-scripts-tests`. The real template is checked by the root
`forge-entrypoint-template` hook instead (run directly: `python3
scripts/check_forge_entrypoint.py --root template --template`).

Standalone: python3 scripts/test_check_forge_entrypoint.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_forge_entrypoint  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "check_forge_entrypoint.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_compliant_fixture(root: Path) -> None:
    """The same fully-compliant consumer-shaped tree `CompliantFixture` builds,
    factored out so the subprocess test in `HookRefusesMissingLine` can build
    it too and then remove only the one line it's isolating."""
    _write(
        root / "CLAUDE.md",
        "# Working on example\n\nSee instructing-agents.md.\n\n@.forge/entrypoint.md\n\n## This project's own rules\n",
    )
    _write(root / "AGENTS.md", "Read .forge/entrypoint.md and every file it imports.\n")
    _write(
        root / ".forge" / "entrypoint.md",
        "Framing sentence.\n\n@.forge/review-gate.md\n\nSee also `.forge/model-tiers.md`.\n",
    )
    _write(root / ".forge" / "review-gate.md", "The review gate rule.\n")
    _write(root / ".forge" / "model-tiers.md", "Tier reference material.\n")


class CompliantFixture(unittest.TestCase):
    """Builds a minimal but fully compliant consumer-shaped fixture: an entrypoint
    importing one rule file and referencing one more, each present."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _write_compliant_fixture(self.root)

    def problems(self, template: bool = False) -> list[str]:
        return check_forge_entrypoint.problems(self.root, template)


class CompliantProjectPasses(CompliantFixture):
    def test_the_both_sides_compliant_fixture_has_no_problems(self) -> None:
        self.assertEqual(self.problems(), [], "a check that over-fires on a correct fixture goes red here")


class MissingEntrypointLine(CompliantFixture):
    def test_claude_md_without_the_entrypoint_line_fails(self) -> None:
        _write(self.root / "CLAUDE.md", "# Working on example\n\nNo entrypoint import here.\n")
        self.assertTrue(any("CLAUDE.md" in p and "@.forge/entrypoint.md" in p for p in self.problems()))


class AgentsDoesNotNameEntrypoint(CompliantFixture):
    def test_agents_md_without_the_path_fails(self) -> None:
        _write(self.root / "AGENTS.md", "Read CLAUDE.md and its imports.\n")
        self.assertTrue(any("AGENTS.md" in p for p in self.problems()))


class DoubleImport(CompliantFixture):
    def test_claude_md_importing_a_file_the_entrypoint_already_imports_fails(self) -> None:
        _write(
            self.root / "CLAUDE.md",
            "@.forge/entrypoint.md\n\n@.forge/review-gate.md\n",
        )
        self.assertTrue(any("double load" in p for p in self.problems()))


class DanglingImport(CompliantFixture):
    def test_an_entrypoint_import_naming_a_missing_file_fails(self) -> None:
        _write(
            self.root / ".forge" / "entrypoint.md",
            "@.forge/review-gate.md\n\n@.forge/does-not-exist.md\n",
        )
        self.assertTrue(any("does-not-exist.md" in p and "does not exist" in p for p in self.problems()))


class UncoveredForgeFile(CompliantFixture):
    def test_an_extra_forge_file_the_entrypoint_never_names_fails(self) -> None:
        _write(self.root / ".forge" / "new-rule.md", "An orphaned rule file.\n")
        self.assertTrue(any("new-rule.md" in p and "not imported or referenced" in p for p in self.problems()))


class MissingEntrypointFile(CompliantFixture):
    def test_no_forge_entrypoint_md_at_all_fails(self) -> None:
        (self.root / ".forge" / "entrypoint.md").unlink()
        problems = self.problems()
        self.assertTrue(any(".forge/entrypoint.md is missing" in p for p in problems))


class TemplateModeStripsJinja(unittest.TestCase):
    """In --template mode, a rule file shipped as `<name>.md.jinja` is matched
    against an import or reference that names it without the suffix."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _write(self.root / "CLAUDE.md.jinja", "# Working on {{ project_name }}\n\n@.forge/entrypoint.md\n")
        _write(self.root / "AGENTS.md.jinja", "Read .forge/entrypoint.md and every file it imports.\n")
        _write(
            self.root / ".forge" / "entrypoint.md",
            "Framing sentence.\n\n@.forge/orchestration.md\n",
        )
        # Shipped with a .jinja suffix, named without it in the entrypoint's import.
        _write(self.root / ".forge" / "orchestration.md.jinja", "{{ project_name }}'s orchestration rules.\n")

    def test_the_jinja_suffixed_file_is_matched_by_its_stripped_name(self) -> None:
        self.assertEqual(check_forge_entrypoint.problems(self.root, True), [])

    def test_without_template_mode_the_same_fixture_reports_the_suffix_as_missing(self) -> None:
        """The guard-removal case for the suffix strip: turning template mode off
        must make the same fixture fail, confirming the strip is what made it pass."""
        problems = check_forge_entrypoint.problems(self.root, False)
        self.assertTrue(any("orchestration.md" in p for p in problems))


class UncoveredJinjaForgeFile(unittest.TestCase):
    """Template mode only: an uncovered `.forge/<name>.md.jinja` file must be
    caught by check 5 under its stripped name, the same as a plain `.md` one.

    `_forge_file_names`'s `.jinja`-suffix strip is what lets a covered file
    like `orchestration.md.jinja` match the entrypoint's `.forge/orchestration.md`
    import; without that strip, every `.jinja`-suffixed file stops being
    treated as a `.md` file at all and silently drops out of this scan, so an
    orphaned one would pass unnoticed instead of being flagged."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _write(self.root / "CLAUDE.md.jinja", "# Working on {{ project_name }}\n\n@.forge/entrypoint.md\n")
        _write(self.root / "AGENTS.md.jinja", "Read .forge/entrypoint.md and every file it imports.\n")
        _write(
            self.root / ".forge" / "entrypoint.md",
            "Framing sentence.\n\n@.forge/orchestration.md\n",
        )
        _write(self.root / ".forge" / "orchestration.md.jinja", "{{ project_name }}'s orchestration rules.\n")
        # Covered by nothing in the entrypoint above -- the orphan this test checks for.
        _write(self.root / ".forge" / "orphan.md.jinja", "An unnamed rule file.\n")

    def test_an_uncovered_jinja_forge_file_fails_in_template_mode(self) -> None:
        problems = check_forge_entrypoint.problems(self.root, True)
        self.assertTrue(any("orphan.md" in p and "not imported or referenced" in p for p in problems))


class SeedCarriesNoForgeText(unittest.TestCase):
    """Template mode only: a CLAUDE.md.jinja line of 30+ characters that duplicates
    a line in a .forge/*.md file is forge-authored rule text that leaked into the
    project-owned seed."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.shared_line = "This sentence is forge-authored rule text, not project text.\n"
        _write(
            self.root / "CLAUDE.md.jinja",
            "# Working on {{ project_name }}\n\n@.forge/entrypoint.md\n\n" + self.shared_line,
        )
        _write(self.root / "AGENTS.md.jinja", "Read .forge/entrypoint.md and every file it imports.\n")
        _write(self.root / ".forge" / "entrypoint.md", "@.forge/never-default.md\n")
        _write(self.root / ".forge" / "never-default.md", self.shared_line)

    def test_a_duplicated_long_line_fails_in_template_mode(self) -> None:
        self.assertTrue(any("never-default.md" in p for p in check_forge_entrypoint.problems(self.root, True)))


class SeedCheckScopedToTemplateMode(unittest.TestCase):
    """Uses its own non-jinja fixture rather than `SeedCarriesNoForgeText`'s,
    so `claude_text` is genuinely non-None outside template mode instead of
    passing vacuously. Giving the fixture both a plain and a `.jinja`
    `CLAUDE.md` would have the plain file shadow the jinja one in `_read`'s
    own template-mode lookup, defeating `SeedCarriesNoForgeText` instead."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.shared_line = "This sentence is forge-authored rule text, not project text.\n"
        _write(
            self.root / "CLAUDE.md",
            "# Working on example\n\n@.forge/entrypoint.md\n\n" + self.shared_line,
        )
        _write(self.root / "AGENTS.md", "Read .forge/entrypoint.md and every file it imports.\n")
        _write(self.root / ".forge" / "entrypoint.md", "@.forge/never-default.md\n")
        _write(self.root / ".forge" / "never-default.md", self.shared_line)

    def test_the_duplicated_line_is_not_checked_outside_template_mode(self) -> None:
        problems = check_forge_entrypoint.problems(self.root, False)
        self.assertFalse(any("never-default.md" in p for p in problems))


class AgentsHasSubHeading(CompliantFixture):
    def test_a_heading_in_agents_md_fails(self) -> None:
        _write(
            self.root / "AGENTS.md",
            "Read .forge/entrypoint.md and every file it imports.\n\n## A sub-heading\n",
        )
        self.assertTrue(any("AGENTS.md" in p and "heading" in p for p in self.problems()))


class AgentsOverWordCap(CompliantFixture):
    def test_agents_md_past_the_word_cap_fails(self) -> None:
        body = " ".join(f"word{i}" for i in range(check_forge_entrypoint.AGENTS_MAX_WORDS + 1))
        _write(self.root / "AGENTS.md", f"Read .forge/entrypoint.md and every file it imports.\n\n{body}\n")
        self.assertTrue(any("AGENTS.md" in p and "word" in p for p in self.problems()))


class AgentsDuplicatesForgeText(CompliantFixture):
    def test_a_30_char_line_shared_with_claude_md_fails(self) -> None:
        shared_line = "This sentence is forge-authored rule text, not project text.\n"
        _write(
            self.root / "CLAUDE.md",
            "# Working on example\n\n@.forge/entrypoint.md\n\n" + shared_line,
        )
        _write(
            self.root / "AGENTS.md",
            "Read .forge/entrypoint.md and every file it imports.\n\n" + shared_line,
        )
        problems = self.problems()
        self.assertTrue(any("AGENTS.md" in p and "CLAUDE.md" in p for p in problems))

    def test_a_30_char_line_shared_with_a_forge_file_fails(self) -> None:
        shared_line = "This sentence is forge-authored rule text, not project text.\n"
        _write(self.root / "AGENTS.md", "Read .forge/entrypoint.md and every file it imports.\n\n" + shared_line)
        _write(self.root / ".forge" / "review-gate.md", "The review gate rule.\n\n" + shared_line)
        problems = self.problems()
        self.assertTrue(any("AGENTS.md" in p and "review-gate.md" in p for p in problems))


class CompliantWithTitleHeading(CompliantFixture):
    """An `AGENTS.md` whose only heading is its title line (a single `#`) must
    keep passing -- without this, a regex loosened to also match a bare `#`
    would have no unit test go red, only the root hook's own real file."""

    def test_a_single_h1_title_does_not_trip_the_heading_check(self) -> None:
        _write(
            self.root / "AGENTS.md",
            "# Agents working on example\n\nRead .forge/entrypoint.md and every file it imports.\n",
        )
        self.assertEqual(self.problems(), [])


class OverLongAgentsWithSubHeadings(unittest.TestCase):
    """A restated-rules shape -- several `##` bullet sections, well past the
    word cap -- confirms both the heading check and the word cap fire
    together on the kind of drift-prone restatement this feature guards
    against, using an invented example rather than this repository's own
    history."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _write_compliant_fixture(self.root)
        section = (
            "## A restated rule\n\n"
            "This paragraph stands in for a condensed restatement of a project rule, "
            "repeated here only to push the fixture past the word cap for this test, "
            "with enough padding words that the total comfortably clears three hundred. "
        )
        _write(
            self.root / "AGENTS.md",
            "# Agents working on example\n\n"
            "Read .forge/entrypoint.md and every file it imports.\n\n" + section * 15,
        )

    def test_the_restated_rules_shape_trips_the_heading_check(self) -> None:
        problems = check_forge_entrypoint.problems(self.root, False)
        self.assertTrue(any("AGENTS.md" in p and "heading" in p for p in problems))

    def test_the_restated_rules_shape_trips_the_word_cap(self) -> None:
        problems = check_forge_entrypoint.problems(self.root, False)
        self.assertTrue(any("AGENTS.md" in p and "word" in p for p in problems))


class HookRefusesMissingLine(unittest.TestCase):
    """Exercises the script as a subprocess, the shape the pre-commit hook runs
    it in, on a fixture missing the entrypoint line -- the non-zero exit the hook relies on."""

    def test_the_script_exits_non_zero_on_a_non_compliant_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Otherwise-fully-compliant fixture, minus only the one entrypoint
            # import line, so this isolates check 1 instead of also tripping
            # every other check (a missing .forge/ dir, AGENTS.md not naming
            # the entrypoint, and so on) the way an empty fixture would.
            _write_compliant_fixture(root)
            _write(root / "CLAUDE.md", "# Working on example\n\nNo entrypoint import here.\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Entrypoint migration", result.stderr)
            self.assertIn("CLAUDE.md", result.stderr)
            self.assertIn("@.forge/entrypoint.md", result.stderr)

    def test_the_root_template_hook_shape_reports_its_own_remedy_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "CLAUDE.md.jinja", "# Working on {{ project_name }}\n\nNo entrypoint import.\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--template"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Fix template/ directly", result.stderr)


if __name__ == "__main__":
    unittest.main()
