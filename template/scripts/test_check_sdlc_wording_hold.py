"""Guard tests for check_sdlc_wording_hold.py, run standalone:
python3 scripts/test_check_sdlc_wording_hold.py

check()'s positional order is (body, old_answers, new_answers, old_doc,
new_doc, upstream_old_doc, upstream_new_doc): old_doc/new_doc are this
project's own lifecycle doc at the PR's base (pre-sync) and head (synced);
upstream_old_doc/upstream_new_doc are the upstream template's doc at the
two `_commit`s. `_check` below binds those by name so a test reads as the
scenario it builds, not as seven positional strings.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sdlc_wording_changes as wording  # noqa: E402
import check_sdlc_wording_hold as guard  # noqa: E402

OLD_ANSWERS = "_src_path: 'gh:example-org/example-forge'\n_commit: 'v1.0.0'\n"
NEW_ANSWERS = "_src_path: 'gh:example-org/example-forge'\n_commit: 'v1.1.0'\n"
OLD_STATEMENT = "- **SDLC-001**: Old wording.\n"
NEW_STATEMENT = "- **SDLC-001**: New wording.\n"
UNRELATED_OLD = "- **SDLC-002**: Pre-sync local wording.\n"
UNRELATED_NEW = "- **SDLC-002**: Synced local wording.\n"
CONFLICT_MARKED = "<<<<<<< HEAD\n- **SDLC-001**: Ours.\n=======\n- **SDLC-001**: Theirs.\n>>>>>>> branch\n"


def sync_body(upstream_line: str | None, held_line: str | None) -> str:
    upstream = f"SDLC upstream changes: {upstream_line}\n" if upstream_line is not None else ""
    held = f"- SDLC wording held: {held_line}\n" if held_line is not None else ""
    return f"Before: v1.0.0\n\nAfter: v1.1.0\n\n{upstream}\n{held}"


def _check(
    body: str,
    old_answers: str = OLD_ANSWERS,
    new_answers: str = NEW_ANSWERS,
    pre_sync: str = OLD_STATEMENT,
    synced: str = OLD_STATEMENT,
    upstream_old: str = OLD_STATEMENT,
    upstream_new: str = OLD_STATEMENT,
) -> list[str]:
    return guard.check(body, old_answers, new_answers, pre_sync, synced, upstream_old, upstream_new)


class NonSyncPrsAreNotChecked(unittest.TestCase):
    def test_commit_unchanged_between_base_and_head_is_not_a_sync(self) -> None:
        self.assertEqual(_check("no upstream-changes line at all", old_answers=OLD_ANSWERS, new_answers=OLD_ANSWERS), [])

    def test_retrofit_with_no_commit_at_base_is_not_a_sync(self) -> None:
        no_commit_answers = "_src_path: 'gh:example-org/example-forge'\n"
        self.assertEqual(_check("no upstream-changes line at all", old_answers=no_commit_answers), [])

    def test_trigger_is_commit_change_not_a_pr_body_marker(self) -> None:
        # No marker of any kind in the body -- still checked, since the
        # trigger is the answers files' own _commit change, not a marker
        # the PR could simply omit.
        body = "Ticket: Closes #1\n\nNo sync marker here at all.\n"
        failures = _check(body, upstream_old=OLD_STATEMENT, upstream_new=NEW_STATEMENT, pre_sync=OLD_STATEMENT, synced=NEW_STATEMENT)
        self.assertTrue(failures)

    def test_trigger_is_not_whether_the_lifecycle_doc_appears_in_the_file_list(self) -> None:
        # pre_sync == synced == OLD_STATEMENT: the project's own doc never
        # changes, so a trigger gated on the doc's presence in the file list
        # would see nothing. The _commit change fires this check anyway, and
        # it still catches the unreverted upstream change (old -> new) the
        # body's held list wrongly claims as "none".
        body = sync_body("v1.0.0..v1.1.0 held: none; current: none", "none")
        failures = _check(body, pre_sync=OLD_STATEMENT, synced=OLD_STATEMENT, upstream_old=OLD_STATEMENT, upstream_new=NEW_STATEMENT)
        self.assertTrue(any("SDLC-001" in f and "held list" in f for f in failures))


class MissingOrMismatchedUpstreamChangesLine(unittest.TestCase):
    def test_no_upstream_changes_line_fails(self) -> None:
        body = sync_body(None, "none")
        failures = _check(body)
        self.assertEqual(len(failures), 1)
        self.assertIn("SDLC upstream changes", failures[0])

    def test_range_mismatch_fails(self) -> None:
        body = sync_body("v0.9.0..v1.1.0 held: none; current: none", "none")
        failures = _check(body)
        self.assertTrue(any("range" in f for f in failures))

    def test_describe_and_sha_endpoints_match(self) -> None:
        old_answers = "_commit: 'abcdef1'\n"
        new_answers = "_commit: 'abcdef1234567890'\n"
        body = sync_body("abcdef1..v1.0.0-5-gabcdef1234567890 held: none; current: none", "none")
        self.assertEqual(_check(body, old_answers=old_answers, new_answers=new_answers), [])

    def test_held_list_mismatch_fails(self) -> None:
        # Upstream actually changed SDLC-001 and it was correctly reverted
        # (synced matches pre_sync), but the PR body under-reports it as
        # held: none.
        body = sync_body("v1.0.0..v1.1.0 held: none; current: none", "none")
        failures = _check(
            body,
            pre_sync=OLD_STATEMENT,
            synced=OLD_STATEMENT,
            upstream_old=OLD_STATEMENT,
            upstream_new=NEW_STATEMENT,
        )
        self.assertTrue(any("held list" in f for f in failures))

    def test_current_list_mismatch_fails(self) -> None:
        # Upstream changed SDLC-001 and the pre-sync text already matched
        # the new wording (nothing to hold), but the body claims it was held.
        body = sync_body("v1.0.0..v1.1.0 held: SDLC-001; current: none", "SDLC-001 -> lifecycle-doc PR 1")
        failures = _check(
            body,
            pre_sync=NEW_STATEMENT,
            synced=NEW_STATEMENT,
            upstream_old=OLD_STATEMENT,
            upstream_new=NEW_STATEMENT,
        )
        self.assertTrue(any("current list" in f for f in failures))

    def test_matching_accounting_passes(self) -> None:
        body = sync_body("v1.0.0..v1.1.0 held: SDLC-001; current: none", "SDLC-001 -> lifecycle-doc PR 1")
        self.assertEqual(
            _check(
                body,
                pre_sync=OLD_STATEMENT,
                synced=OLD_STATEMENT,
                upstream_old=OLD_STATEMENT,
                upstream_new=NEW_STATEMENT,
            ),
            [],
        )

    def test_a_local_only_reword_with_no_matching_upstream_change_still_fails(self) -> None:
        # Nothing upstream changed, but the sync PR's own doc carries an SDLC
        # statement edit anyway (coincidentally or not) -- still a failure:
        # only the owner approves any SDLC wording change at all.
        body = sync_body("v1.0.0..v1.1.0 held: none; current: none", "none")
        failures = _check(
            body,
            pre_sync=UNRELATED_OLD,
            synced=UNRELATED_NEW,
            upstream_old=OLD_STATEMENT,
            upstream_new=OLD_STATEMENT,
        )
        self.assertTrue(any("SDLC-002" in f and "no matching upstream change" in f for f in failures))


class UnrevertedWording(unittest.TestCase):
    def test_upstream_change_not_reverted_fails_even_with_a_held_line(self) -> None:
        # Upstream changed SDLC-001; the project's synced doc ended up with
        # the new text instead of being reverted to pre-sync -- the exact
        # failure shape this check exists to catch.
        body = sync_body("v1.0.0..v1.1.0 held: SDLC-001; current: none", "none")
        failures = _check(
            body,
            pre_sync=OLD_STATEMENT,
            synced=NEW_STATEMENT,
            upstream_old=OLD_STATEMENT,
            upstream_new=NEW_STATEMENT,
        )
        self.assertTrue(any("Upstream changed" in f for f in failures))

    def test_correctly_reverted_sync_passes(self) -> None:
        body = sync_body("v1.0.0..v1.1.0 held: SDLC-001; current: none", "SDLC-001 -> lifecycle-doc PR 1")
        self.assertEqual(
            _check(
                body,
                pre_sync=OLD_STATEMENT,
                synced=OLD_STATEMENT,
                upstream_old=OLD_STATEMENT,
                upstream_new=NEW_STATEMENT,
            ),
            [],
        )


class MissingHeldLine(unittest.TestCase):
    def test_no_held_line_at_all_fails_even_with_nothing_to_hold(self) -> None:
        body = sync_body("v1.0.0..v1.1.0 held: none; current: none", None)
        failures = _check(body)
        self.assertTrue(any("SDLC wording held" in f for f in failures))

    def test_blank_held_line_fails(self) -> None:
        body = sync_body("v1.0.0..v1.1.0 held: none; current: none", "")
        failures = _check(body)
        self.assertTrue(any("SDLC wording held" in f for f in failures))


class ConflictMarkersAreRefused(unittest.TestCase):
    def test_a_conflict_marker_in_any_doc_raises_rather_than_being_compared(self) -> None:
        body = sync_body("v1.0.0..v1.1.0 held: none; current: none", "none")
        with self.assertRaises(wording.ConflictMarkersError):
            _check(body, pre_sync=CONFLICT_MARKED)

    def test_main_exits_two_on_a_conflict_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = {
                name: Path(tmp) / f"{name}.txt"
                for name in ("body", "old_answers", "new_answers", "old_doc", "new_doc", "upstream_old", "upstream_new")
            }
            paths["body"].write_text(sync_body("v1.0.0..v1.1.0 held: none; current: none", "none"))
            paths["old_answers"].write_text(OLD_ANSWERS)
            paths["new_answers"].write_text(NEW_ANSWERS)
            paths["old_doc"].write_text(CONFLICT_MARKED)
            paths["new_doc"].write_text(OLD_STATEMENT)
            paths["upstream_old"].write_text(OLD_STATEMENT)
            paths["upstream_new"].write_text(OLD_STATEMENT)
            self.assertEqual(guard.main([str(p) for p in paths.values()]), 2)


class MainExitCode(unittest.TestCase):
    def test_main_requires_exactly_seven_arguments(self) -> None:
        self.assertEqual(guard.main(["one", "two", "three"]), 2)

    def _write_all(self, tmp: str, **overrides: str) -> list[str]:
        defaults = {
            "body": sync_body("v1.0.0..v1.1.0 held: none; current: none", "none"),
            "old_answers": OLD_ANSWERS,
            "new_answers": NEW_ANSWERS,
            "old_doc": OLD_STATEMENT,
            "new_doc": OLD_STATEMENT,
            "upstream_old": OLD_STATEMENT,
            "upstream_new": OLD_STATEMENT,
        }
        defaults.update(overrides)
        order = ["body", "old_answers", "new_answers", "old_doc", "new_doc", "upstream_old", "upstream_new"]
        paths = []
        for name in order:
            path = Path(tmp) / f"{name}.txt"
            path.write_text(defaults[name])
            paths.append(str(path))
        return paths

    def test_main_passes_a_clean_sync_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(guard.main(self._write_all(tmp)), 0)

    def test_main_fails_a_real_sync_pr_with_an_unreverted_upstream_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self._write_all(
                tmp,
                body=sync_body("v1.0.0..v1.1.0 held: SDLC-001; current: none", "none"),
                old_doc=OLD_STATEMENT,
                new_doc=NEW_STATEMENT,
                upstream_old=OLD_STATEMENT,
                upstream_new=NEW_STATEMENT,
            )
            self.assertEqual(guard.main(args), 1)

    def test_a_missing_pre_sync_doc_with_a_statement_in_synced_is_a_local_only_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self._write_all(tmp)
            # old_doc's path doesn't exist on disk -> reads as "" (no statements),
            # while new_doc still carries one: a local_only change, not a clean sync.
            args[3] = str(Path(tmp) / "does-not-exist.txt")
            self.assertEqual(guard.main(args), 1)


@unittest.skipUnless(
    (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "review-gate-check.yml").exists(),
    "review-gate-check.yml is not present in this checkout",
)
class WorkflowInvokesThisGuard(unittest.TestCase):
    def test_workflow_invokes_the_sdlc_wording_hold_guard(self) -> None:
        path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "review-gate-check.yml"
        text = path.read_text()
        self.assertIn("check_sdlc_wording_hold.py", text)

    def test_workflow_triggers_on_the_answers_file_not_the_lifecycle_doc(self) -> None:
        # A lifecycle-doc-presence trigger can miss a sync whose doc ends up unchanged.
        path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "review-gate-check.yml"
        text = path.read_text()
        self.assertIn('grep -qxF ".copier-answers.yml" /tmp/pr_files.txt', text)


if __name__ == "__main__":
    unittest.main()
