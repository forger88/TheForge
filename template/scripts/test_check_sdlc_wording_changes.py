"""Guard tests for check_sdlc_wording_changes.py, run standalone:
python3 scripts/test_check_sdlc_wording_changes.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sdlc_wording_changes as guard  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402

OLD_STATEMENT = "- **SDLC-001**: Old wording.\n"
NEW_STATEMENT = "- **SDLC-001**: New wording.\n"
CONFLICT_MARKED = "<<<<<<< HEAD\n- **SDLC-001**: Ours.\n=======\n- **SDLC-001**: Theirs.\n>>>>>>> branch\n"


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

    def test_a_conflict_marker_in_either_plain_mode_file_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "old.md"
            new_path = Path(tmp) / "new.md"
            old_path.write_text(CONFLICT_MARKED)
            new_path.write_text(NEW_STATEMENT)
            self.assertEqual(guard.main([str(old_path), str(new_path)]), 2)


class Accounting(unittest.TestCase):
    def test_upstream_change_already_matched_by_pre_sync_text_is_current_not_held(self) -> None:
        acc = guard.account(OLD_STATEMENT, NEW_STATEMENT, NEW_STATEMENT, NEW_STATEMENT)
        self.assertEqual(acc.to_hold, [])
        self.assertEqual(acc.current, ["SDLC-001"])
        self.assertEqual(acc.unheld, [])
        self.assertEqual(acc.local_only, [])

    def test_upstream_change_correctly_reverted_is_held_and_not_unheld(self) -> None:
        acc = guard.account(OLD_STATEMENT, NEW_STATEMENT, OLD_STATEMENT, OLD_STATEMENT)
        self.assertEqual(acc.to_hold, ["SDLC-001"])
        self.assertEqual(acc.current, [])
        self.assertEqual(acc.unheld, [])
        self.assertEqual(acc.local_only, [])

    def test_upstream_change_let_through_unreverted_is_unheld(self) -> None:
        # pre_sync still has the old wording, but the synced doc ended up
        # with upstream's new wording: the revert step never ran, or missed it.
        acc = guard.account(OLD_STATEMENT, NEW_STATEMENT, OLD_STATEMENT, NEW_STATEMENT)
        self.assertEqual(acc.to_hold, ["SDLC-001"])
        self.assertEqual(acc.unheld, ["SDLC-001"])

    def test_statement_upstream_never_touched_is_not_to_hold_even_if_local_changed_it(self) -> None:
        unrelated_old = "- **SDLC-002**: Pre-sync local wording.\n"
        unrelated_new = "- **SDLC-002**: Synced local wording.\n"
        acc = guard.account(OLD_STATEMENT, OLD_STATEMENT, unrelated_old, unrelated_new)
        self.assertEqual(acc.to_hold, [])
        self.assertEqual(acc.unheld, [])
        self.assertEqual(acc.local_only, ["SDLC-002"])

    def test_a_conflict_marker_in_any_of_the_four_texts_raises(self) -> None:
        with self.assertRaises(guard.ConflictMarkersError):
            guard.account(CONFLICT_MARKED, NEW_STATEMENT, OLD_STATEMENT, OLD_STATEMENT)
        with self.assertRaises(guard.ConflictMarkersError):
            guard.account(OLD_STATEMENT, CONFLICT_MARKED, OLD_STATEMENT, OLD_STATEMENT)
        with self.assertRaises(guard.ConflictMarkersError):
            guard.account(OLD_STATEMENT, NEW_STATEMENT, CONFLICT_MARKED, OLD_STATEMENT)
        with self.assertRaises(guard.ConflictMarkersError):
            guard.account(OLD_STATEMENT, NEW_STATEMENT, OLD_STATEMENT, CONFLICT_MARKED)


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


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        _write(repo / name, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


DOC = "docs/software-development-lifecycle.md"


class AccountModeCli(unittest.TestCase):
    """Builds a throwaway upstream template clone, matching
    test_check_held_sdlc_prose.py's own fixture convention, so the
    --template mode runs with no dependency on this repository's history."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.template = root / "template-repo"
        _init(self.template)
        self.old = _commit(self.template, {f"template/{DOC}": OLD_STATEMENT}, "old")
        self.new = _commit(self.template, {f"template/{DOC}": NEW_STATEMENT}, "reword SDLC-001")
        self.pre_sync_path = root / "pre-sync.md"
        self.synced_path = root / "synced.md"

    def test_held_correctly_exits_zero(self) -> None:
        self.pre_sync_path.write_text(OLD_STATEMENT)
        self.synced_path.write_text(OLD_STATEMENT)
        self.assertEqual(
            guard.main(
                [
                    "--template", str(self.template), "--old", self.old, "--new", self.new,
                    str(self.pre_sync_path), str(self.synced_path),
                ]
            ),
            0,
        )

    def test_unheld_exits_one(self) -> None:
        self.pre_sync_path.write_text(OLD_STATEMENT)
        self.synced_path.write_text(NEW_STATEMENT)
        self.assertEqual(
            guard.main(
                [
                    "--template", str(self.template), "--old", self.old, "--new", self.new,
                    str(self.pre_sync_path), str(self.synced_path),
                ]
            ),
            1,
        )

    def test_unresolvable_revision_exits_two(self) -> None:
        self.pre_sync_path.write_text(OLD_STATEMENT)
        self.synced_path.write_text(OLD_STATEMENT)
        self.assertEqual(
            guard.main(
                [
                    "--template", str(self.template), "--old", "not-a-real-rev", "--new", self.new,
                    str(self.pre_sync_path), str(self.synced_path),
                ]
            ),
            2,
        )

    def test_flag_like_revision_is_refused_not_passed_to_git(self) -> None:
        self.pre_sync_path.write_text(OLD_STATEMENT)
        self.synced_path.write_text(OLD_STATEMENT)
        self.assertEqual(
            guard.main(
                [
                    "--template", str(self.template), "--old", "--upload-pack=evil", "--new", self.new,
                    str(self.pre_sync_path), str(self.synced_path),
                ]
            ),
            2,
        )

    def test_subdir_flag_is_honoured(self) -> None:
        other_template = Path(self.template).parent / "flat-template"
        _init(other_template)
        old = _commit(other_template, {DOC: OLD_STATEMENT}, "old")
        new = _commit(other_template, {DOC: NEW_STATEMENT}, "reword SDLC-001")
        self.pre_sync_path.write_text(OLD_STATEMENT)
        self.synced_path.write_text(OLD_STATEMENT)
        self.assertEqual(
            guard.main(
                [
                    "--template", str(other_template), "--subdir", "", "--old", old, "--new", new,
                    str(self.pre_sync_path), str(self.synced_path),
                ]
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
