"""Guard tests for check_held_sdlc_prose.py.

Each test builds a throwaway template repository (the upstream history) and
a throwaway project repository (the pre-sync commit plus a synced working
tree), so the check runs with no dependency on this repository's own
history. This test no longer ships to consumers; it runs only here,
and directly against `template/scripts/` via `template-scripts-tests`.

Standalone: python3 scripts/test_check_held_sdlc_prose.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_held_sdlc_prose  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402

DOC = "docs/software-development-lifecycle.md"
RULE = ".forge/rule.md"
OLD_STATEMENTS = "- **SDLC-001**: The first statement stays the same.\n- **SDLC-002**: The second statement says the old thing.\n"
NEW_STATEMENTS = "- **SDLC-001**: The first statement stays the same.\n- **SDLC-002**: The second statement says the new thing.\n"
KEPT = "This rule line is in every version of the file.\n"
OLD_DEPENDENT = "This rule line leans on the second statement's old wording.\n"
NEW_DEPENDENT = "This rule line leans on the second statement's new wording.\n"
UNRELATED = "This rule line came from a later commit that held nothing.\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env()
    ).stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _init(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def _commit(repo: Path, files: dict[str, str | None], message: str) -> str:
    for name, text in files.items():
        if text is None:
            (repo / name).unlink()
        else:
            _write(repo / name, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


class Fixture(unittest.TestCase):
    """Upstream: OLD, then a held commit (SDLC-002 plus a dependent rule line),
    then an unrelated commit. The project's working tree is the synced state."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.template = root / "template-repo"
        _init(self.template)
        self.old = _commit(
            self.template,
            {f"template/{DOC}": OLD_STATEMENTS, f"template/{RULE}": KEPT + OLD_DEPENDENT},
            "old",
        )
        self.held = _commit(
            self.template,
            {f"template/{DOC}": NEW_STATEMENTS, f"template/{RULE}": KEPT + NEW_DEPENDENT},
            "reword SDLC-002",
        )
        self.new = _commit(
            self.template,
            {f"template/{DOC}": NEW_STATEMENTS + "\nNew prose under the statements.\n", f"template/{RULE}": KEPT + NEW_DEPENDENT + UNRELATED},
            "unrelated",
        )
        self.project = root / "project"
        _init(self.project)
        self.base = _commit(self.project, {DOC: OLD_STATEMENTS, RULE: KEPT + OLD_DEPENDENT}, "pre-sync")
        _write(self.project / DOC, OLD_STATEMENTS)
        _write(self.project / RULE, KEPT + NEW_DEPENDENT + UNRELATED)
        old_cwd = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, old_cwd)

    def leaks(self, held: set[str] | None = None) -> list[str]:
        return check_held_sdlc_prose.find_leaks(self.template, "template", self.old, self.new, self.base, held or {"SDLC-002"})


class HeldCommits(Fixture):
    def test_finds_only_the_commit_that_changed_a_held_statement(self) -> None:
        found = check_held_sdlc_prose.held_commits(self.template, "template", self.old, self.new, {"SDLC-002"})
        self.assertEqual(found, [self.held])

    def test_unheld_statement_finds_nothing(self) -> None:
        self.assertEqual(check_held_sdlc_prose.held_commits(self.template, "template", self.old, self.new, {"SDLC-001"}), [])


class Leaks(Fixture):
    def test_dependent_prose_is_reported_both_ways(self) -> None:
        leaks = self.leaks()
        self.assertEqual(len(leaks), 2, leaks)
        self.assertTrue(any("added by held commit" in leak and NEW_DEPENDENT.strip() in leak for leak in leaks))
        self.assertTrue(any("removed by held commit" in leak and OLD_DEPENDENT.strip() in leak for leak in leaks))
        self.assertTrue(all(leak.startswith(f"{RULE}: ") for leak in leaks))

    def test_unrelated_commit_and_lifecycle_doc_are_not_reported(self) -> None:
        joined = "\n".join(self.leaks())
        self.assertNotIn(UNRELATED.strip(), joined)
        self.assertNotIn(DOC, joined)

    def test_reverted_prose_reports_nothing(self) -> None:
        _write(self.project / RULE, KEPT + OLD_DEPENDENT + UNRELATED)
        self.assertEqual(self.leaks(), [])

    def test_line_the_project_already_had_is_not_reported(self) -> None:
        _commit(self.project, {RULE: KEPT + OLD_DEPENDENT + NEW_DEPENDENT}, "project already had it")
        self.base = _git(self.project, "rev-parse", "HEAD")
        _write(self.project / RULE, KEPT + NEW_DEPENDENT + UNRELATED)
        leaks = self.leaks()
        self.assertEqual(len(leaks), 1, leaks)
        self.assertIn("removed by held commit", leaks[0])

    def test_reworded_line_is_not_caught(self) -> None:
        _write(self.project / RULE, KEPT + OLD_DEPENDENT + "This rule line leans on the new wording, reworded.\n")
        self.assertEqual(self.leaks(), [])

    def test_whitespace_differences_still_match(self) -> None:
        _write(self.project / RULE, KEPT + OLD_DEPENDENT.replace(" ", "  ") + NEW_DEPENDENT.replace(" ", "   "))
        leaks = self.leaks()
        self.assertEqual(len(leaks), 1, leaks)
        self.assertIn("added by held commit", leaks[0])


class GitConfigDoesNotHideHeaders(Fixture):
    def test_color_and_noprefix_config_still_report(self) -> None:
        for key, value in (("color.ui", "always"), ("diff.noprefix", "true"), ("diff.mnemonicPrefix", "true")):
            _git(self.template, "config", key, value)
        self.assertEqual(len(self.leaks()), 2)


class PathHandling(Fixture):
    def test_path_with_space_and_non_ascii(self) -> None:
        name = "docs/caf\u00e9 notes.md"
        self.held = _commit(
            self.template,
            {f"template/{DOC}": OLD_STATEMENTS.replace("SDLC-001**: The first", "SDLC-001**: The very first"), f"template/{name}": NEW_DEPENDENT},
            "reword SDLC-001 and add an awkwardly named file",
        )
        self.new = self.held
        _write(self.project / name, NEW_DEPENDENT)
        self.assertEqual(self.leaks({"SDLC-001"}), [f"{name}: added by held commit {self.held[:12]}: {NEW_DEPENDENT.strip()}"])

    def test_jinja_suffix_maps_to_the_rendered_path(self) -> None:
        self.held = _commit(
            self.template,
            {f"template/{DOC}": OLD_STATEMENTS.replace("SDLC-001**: The first", "SDLC-001**: The very first"), "template/skill.md.jinja": NEW_DEPENDENT},
            "reword SDLC-001 and add a jinja file",
        )
        self.new = self.held
        _write(self.project / "skill.md", NEW_DEPENDENT)
        leaks = self.leaks({"SDLC-001"})
        self.assertEqual(leaks, [f"skill.md: added by held commit {self.held[:12]}: {NEW_DEPENDENT.strip()}"])

    def test_deleted_file_reports_its_removed_lines(self) -> None:
        _commit(self.project, {"gone.md": OLD_DEPENDENT}, "project has the file")
        self.base = _git(self.project, "rev-parse", "HEAD")
        self.old = self.new
        _commit(self.template, {"template/gone.md": OLD_DEPENDENT}, "add gone.md")
        self.old = _git(self.template, "rev-parse", "HEAD")
        self.new = _commit(
            self.template,
            {f"template/{DOC}": OLD_STATEMENTS, "template/gone.md": None},
            "revert SDLC-002 and delete gone.md",
        )
        (self.project / "gone.md").unlink()
        leaks = self.leaks()
        self.assertIn(f"gone.md: removed by held commit {self.new[:12]}: {OLD_DEPENDENT.strip()}", leaks)

    def test_short_markup_and_jinja_lines_are_ignored(self) -> None:
        for line in ("Too short to match.", "-------------------------------------", "A long line with {{ a_variable }} in it, rendered differently."):
            self.assertIsNone(check_held_sdlc_prose._normalize(line))


class Cli(Fixture):
    def run_main(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_held_sdlc_prose.main(
                ["--template", str(self.template), "--old", self.old, "--new", self.new, "--base", self.base, *extra]
            )
        return code, out.getvalue(), err.getvalue()

    def test_leak_exits_one(self) -> None:
        code, out, _ = self.run_main("SDLC-002")
        self.assertEqual(code, 1)
        self.assertIn(NEW_DEPENDENT.strip(), out)

    def test_clean_exits_zero(self) -> None:
        self.assertEqual(self.run_main("SDLC-001")[0], 0)

    def test_bad_statement_id_exits_two(self) -> None:
        code, _, err = self.run_main("12")
        self.assertEqual(code, 2)
        self.assertIn("not a statement id", err)

    def test_flag_like_revision_exits_two(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_held_sdlc_prose.main(
                ["--template", str(self.template), "--old", self.old, "--new", self.new, "--base=--output=x", "SDLC-002"]
            )
        self.assertEqual(code, 2)
        self.assertIn("begins with '-'", err.getvalue())

    def test_unknown_base_exits_two(self) -> None:
        self.base = "0" * 40
        code, out, err = self.run_main("SDLC-002")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("is not a commit in this project", err)

    def test_shallow_template_clone_exits_two(self) -> None:
        shallow = self.template.parent / "shallow"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", self.template.as_uri(), str(shallow)],
            check=True, capture_output=True, env=clean_git_env(),
        )
        self.template = shallow
        code, _, err = self.run_main("SDLC-002")
        self.assertEqual(code, 2)
        self.assertIn("not a full clone", err)

    def test_non_git_template_exits_two(self) -> None:
        self.template = self.template.parent / "not-a-repo"
        self.template.mkdir()
        code, _, err = self.run_main("SDLC-002")
        self.assertEqual(code, 2)
        self.assertIn("is not a git repository", err)

    def test_bad_range_exits_two(self) -> None:
        self.old = "0" * 40
        code, _, err = self.run_main("SDLC-002")
        self.assertEqual(code, 2)
        self.assertIn("rev-list", err)


class SeparatorPrecedesEveryRevision(Fixture):
    def test_end_of_options_sits_before_each_revision(self) -> None:
        calls: list[list[str]] = []
        real = check_held_sdlc_prose.run_git

        def spy(args: list[str], timeout: int):  # type: ignore[no-untyped-def]
            calls.append(args)
            return real(args, timeout)

        with mock.patch.object(check_held_sdlc_prose, "looks_like_flag", return_value=False), mock.patch.object(check_held_sdlc_prose, "run_git", spy):
            self.leaks()
        revisions = {self.old, self.new, self.base, self.held}
        checked = 0
        for args in calls:
            for index, arg in enumerate(args):
                if any(arg.startswith(rev) for rev in revisions) and arg not in ("--", "-C"):
                    self.assertEqual(args[index - 1], "--end-of-options", args)
                    checked += 1
        self.assertGreaterEqual(checked, 5)


if __name__ == "__main__":
    unittest.main()
