"""Guard tests for check_coordinator_core.py, run standalone: python3 scripts/test_check_coordinator_core.py"""

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_coordinator_core as ccc  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402

GOOD_CORE = (
    "# Coordinator core\n\n"
    "**TRUNCATION GUARD — read this first.**\n"
    "If the end marker is missing, tell the owner.\n\n"
    "Mid-file check word: HERONQUILL\n\n"
    "Rules.\n\n"
    "END OF COORDINATOR CORE — codeword: OSPREYWING\n"
)


def _rolled(text: str) -> str:
    """`text` with both proof words rolled, as a real body edit must."""
    return text.replace("OSPREYWING", "KINGFISHER").replace("HERONQUILL", "PLOVERMOSS")

SNIPPET_FILE = (
    "# Snippet\n\nPreamble.\n\n"
    f"{ccc.SNIPPET_START}\n"
    "## Coordinator core\n\n"
    "Only the coordinator acts on this.\n"
    "1. Copy the file.\n"
    f"{ccc.SNIPPET_END}\n"
)


class ShapeTests(unittest.TestCase):
    def test_good_core_passes(self) -> None:
        self.assertEqual(ccc.shape_problems(GOOD_CORE), [])

    def test_truncated_core_fails(self) -> None:
        truncated = GOOD_CORE[: GOOD_CORE.index("END OF")]
        self.assertTrue(any("does not end" in p for p in ccc.shape_problems(truncated)))

    def test_marker_not_last_fails(self) -> None:
        self.assertTrue(any("does not end" in p for p in ccc.shape_problems(GOOD_CORE + "More rules.\n")))

    def test_missing_guard_instruction_fails(self) -> None:
        text = GOOD_CORE.replace("TRUNCATION GUARD", "Guard")
        self.assertTrue(any("TRUNCATION GUARD" in p for p in ccc.shape_problems(text)))

    def test_guard_instruction_too_low_fails(self) -> None:
        text = "\n" * ccc.GUARD_WINDOW_LINES + GOOD_CORE
        self.assertTrue(any("TRUNCATION GUARD" in p for p in ccc.shape_problems(text)))

    def test_codeword_leaked_above_marker_fails(self) -> None:
        text = GOOD_CORE.replace("Rules.", "The codeword is OSPREYWING.")
        self.assertTrue(any("more than once" in p for p in ccc.shape_problems(text)))

    def test_missing_mid_file_word_fails(self) -> None:
        text = GOOD_CORE.replace("Mid-file check word: HERONQUILL\n\n", "")
        self.assertTrue(any("Mid-file check word" in p for p in ccc.shape_problems(text)))

    def test_two_mid_file_words_fail(self) -> None:
        text = GOOD_CORE.replace("Rules.", "Mid-file check word: PLOVERMOSS")
        self.assertTrue(any("exactly one" in p for p in ccc.shape_problems(text)))

    def test_mid_file_word_in_a_tail_read_fails(self) -> None:
        text = GOOD_CORE.replace("Mid-file check word: HERONQUILL\n\n", "").replace(
            "Rules.\n\n", "Rules.\n\nMid-file check word: HERONQUILL\n\n"
        )
        self.assertTrue(any("middle third" in p for p in ccc.shape_problems(text)))

    def test_mid_file_word_in_a_head_read_fails(self) -> None:
        text = GOOD_CORE.replace("Mid-file check word: HERONQUILL\n\n", "").replace(
            "# Coordinator core\n\n", "# Coordinator core\n\nMid-file check word: HERONQUILL\n\n"
        )
        self.assertTrue(any("middle third" in p for p in ccc.shape_problems(text)))

    def test_mid_file_word_leaked_elsewhere_fails(self) -> None:
        text = GOOD_CORE.replace("Rules.", "The check word is HERONQUILL.")
        self.assertTrue(any("mid-file check word 'HERONQUILL' more than once" in p for p in ccc.shape_problems(text)))

    def test_mid_file_word_equal_to_codeword_fails(self) -> None:
        text = GOOD_CORE.replace("HERONQUILL", "OSPREYWING")
        self.assertTrue(any("same word" in p for p in ccc.shape_problems(text)))

    def test_size_limit_is_inclusive(self) -> None:
        body_len = ccc.MAX_CHARS - len(GOOD_CORE)
        at_limit = GOOD_CORE.replace("Rules.", "x" * (body_len + len("Rules.")))
        self.assertEqual(len(at_limit), ccc.MAX_CHARS)
        self.assertEqual(ccc.shape_problems(at_limit), [])
        over = at_limit.replace("x", "xx", 1)
        self.assertTrue(any("over the" in p for p in ccc.shape_problems(over)))

    def test_empty_file_fails(self) -> None:
        self.assertTrue(ccc.shape_problems(""))


class DriftTests(unittest.TestCase):
    def test_live_carrying_snippet_passes_despite_rewrapping(self) -> None:
        live = "## Scope\nowner text\n\n## Coordinator core\n\nOnly the coordinator\n   acts on this.\n1. Copy the file.\n\n## Notes\n"
        self.assertEqual(ccc.drift_problems(live, SNIPPET_FILE), [])

    def test_edited_live_field_fails_and_names_the_line(self) -> None:
        live = "## Coordinator core\n\nOnly the coordinator acts on this.\n1. Copy the whole file.\n"
        problems = ccc.drift_problems(live, SNIPPET_FILE)
        self.assertEqual(len(problems), 1)
        self.assertIn("1. Copy the file.", problems[0])

    def test_reordered_live_field_fails(self) -> None:
        live = "1. Copy the file.\n## Coordinator core\nOnly the coordinator acts on this.\n"
        self.assertTrue(ccc.drift_problems(live, SNIPPET_FILE))

    def test_snippet_without_markers_fails(self) -> None:
        self.assertTrue(ccc.drift_problems("anything", "no markers here"))


class RotatedProblemsTests(unittest.TestCase):
    def test_same_body_same_codeword_passes(self) -> None:
        self.assertEqual(ccc.rotated_problems(GOOD_CORE, GOOD_CORE), [])

    def test_same_body_different_codeword_passes(self) -> None:
        new = GOOD_CORE.replace("OSPREYWING", "KINGFISHER")
        self.assertEqual(ccc.rotated_problems(GOOD_CORE, new), [])

    def test_different_body_both_words_rolled_passes(self) -> None:
        new = _rolled(GOOD_CORE.replace("Rules.", "More rules."))
        self.assertEqual(ccc.rotated_problems(GOOD_CORE, new), [])

    def test_different_body_same_mid_file_word_fails(self) -> None:
        new = GOOD_CORE.replace("Rules.", "More rules.").replace("OSPREYWING", "KINGFISHER")
        problems = ccc.rotated_problems(GOOD_CORE, new)
        self.assertEqual(len(problems), 1)
        self.assertIn("mid-file check word", problems[0])

    def test_only_the_mid_file_word_changed_still_rolls_the_codeword(self) -> None:
        new = GOOD_CORE.replace("HERONQUILL", "PLOVERMOSS")
        self.assertTrue(any("codeword is still" in p for p in ccc.rotated_problems(GOOD_CORE, new)))

    def test_old_core_without_mid_file_word_needs_only_the_codeword_rolled(self) -> None:
        old = GOOD_CORE.replace("Mid-file check word: HERONQUILL\n\n", "")
        self.assertEqual(ccc.rotated_problems(old, _rolled(GOOD_CORE)), [])

    def test_different_body_same_codeword_fails(self) -> None:
        new = GOOD_CORE.replace("Rules.", "More rules.")
        self.assertTrue(ccc.rotated_problems(GOOD_CORE, new))

    def test_no_old_text_passes_regardless(self) -> None:
        self.assertEqual(ccc.rotated_problems(None, GOOD_CORE), [])

    def test_malformed_old_marker_defers_to_shape(self) -> None:
        malformed_old = GOOD_CORE.replace("END OF COORDINATOR CORE — codeword: OSPREYWING\n", "")
        self.assertEqual(ccc.rotated_problems(malformed_old, GOOD_CORE), [])


class RotatedCliTests(unittest.TestCase):
    """A throwaway local git repo, since `rotated`'s CLI path reads the old
    text via `git show <ref>:<path>` rather than a plain file read."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        self.core = self.repo / "core.md"
        self.core.write_text(GOOD_CORE, encoding="utf-8")
        self._git("add", "core.md")
        self._git("commit", "-q", "-m", "initial")
        old_cwd = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, old_cwd)

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True, env=clean_git_env()
        )

    def _run(self, argv: list[str]) -> int:
        with contextlib.redirect_stderr(io.StringIO()):
            return ccc.main(argv)

    def test_rotated_exit_codes(self) -> None:
        self.assertEqual(self._run(["rotated", "core.md"]), 0)
        self.core.write_text(GOOD_CORE.replace("Rules.", "More rules."), encoding="utf-8")
        self.assertEqual(self._run(["rotated", "core.md"]), 1)
        self.core.write_text(_rolled(GOOD_CORE.replace("Rules.", "More rules.")), encoding="utf-8")
        self.assertEqual(self._run(["rotated", "core.md"]), 0)

    def test_rotated_brand_new_file_passes(self) -> None:
        new_file = self.repo / "new.md"
        new_file.write_text(GOOD_CORE, encoding="utf-8")
        self.assertEqual(self._run(["rotated", "new.md", "--against", "HEAD"]), 0)


class MainTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _run(self, argv: list[str]) -> int:
        with contextlib.redirect_stderr(io.StringIO()):
            return ccc.main(argv)

    def test_shape_exit_codes(self) -> None:
        core = self.root / "core.md"
        core.write_text(GOOD_CORE, encoding="utf-8")
        self.assertEqual(self._run(["shape", str(core)]), 0)
        core.write_text(GOOD_CORE[:40], encoding="utf-8")
        self.assertEqual(self._run(["shape", str(core)]), 1)
        self.assertEqual(self._run(["shape", str(self.root / "missing.md")]), 1)

    def test_drift_exit_codes(self) -> None:
        snippet = self.root / "snippet.md"
        snippet.write_text(SNIPPET_FILE, encoding="utf-8")
        live = self.root / "live.txt"
        live.write_text("x\n" + ccc.snippet_text(SNIPPET_FILE) + "\ny", encoding="utf-8")
        self.assertEqual(self._run(["drift", str(live), "--snippet", str(snippet)]), 0)
        live.write_text("x", encoding="utf-8")
        self.assertEqual(self._run(["drift", str(live), "--snippet", str(snippet)]), 1)
        self.assertEqual(self._run(["drift", str(self.root / "none.txt"), "--snippet", str(snippet)]), 1)


REWORDED = "## Coordinator notes (kept by the owner)"


class NotesZoneEndsAtMarker(unittest.TestCase):
    """Live instructions written while the composer existed carry MARKER directly above the
    generated content it owns in the live project settings text; a notes
    zone sitting right above the marker, with no heading in between, must
    not swallow the composer's provenance line below it."""

    def test_notes_zone_stops_at_marker_with_no_heading_between(self) -> None:
        text = (
            f"{ccc.NOTES_HEADING}\n\n- 2026-01-02: hold the export ticket.\n\n"
            f"{ccc.MARKER}\n"
            "Composed from example-org/widgets @ abc1234 (lead).\n\n"
            "## Boot routine\n\ngenerated text\n"
        )
        zone = ccc.extract_notes_zone(text, "live")
        self.assertEqual(zone, f"{ccc.NOTES_HEADING}\n\n- 2026-01-02: hold the export ticket.")
        self.assertNotIn("Composed from", zone)


class NotesCheck(unittest.TestCase):
    """SDLC-118: an update must carry the coordinator-notes zone through."""

    LIVE = (
        "## Project scope\n\nOwner text.\n\n"
        f"{ccc.NOTES_HEADING}\n\n- 2026-01-02: hold the export ticket.\n\n"
        "## Coordinator\n\nold generated text\n"
    )

    def test_unchanged_zone_passes_when_generated_sections_change(self) -> None:
        new = self.LIVE.replace("old generated text", "new generated text")
        self.assertEqual(ccc.notes_problems(self.LIVE, new), [])

    def test_changed_note_fails_with_diff(self) -> None:
        new = self.LIVE.replace("hold the export ticket", "hold nothing")
        problems = ccc.notes_problems(self.LIVE, new)
        self.assertEqual(len(problems), 1)
        self.assertIn("+- 2026-01-02: hold nothing.", problems[0])

    def test_dropped_note_fails(self) -> None:
        new = self.LIVE.replace("- 2026-01-02: hold the export ticket.\n", "")
        self.assertEqual(len(ccc.notes_problems(self.LIVE, new)), 1)

    def test_dropped_zone_fails(self) -> None:
        new = "## Project scope\n\nOwner text.\n\n## Coordinator\n\nnew generated text\n"
        problems = ccc.notes_problems(self.LIVE, new)
        self.assertEqual(len(problems), 1)
        self.assertIn("would be lost", problems[0])

    def test_no_live_zone_with_first_write_allows_creating_one(self) -> None:
        live = "## Project scope\n\nOwner text.\n"
        self.assertEqual(ccc.notes_problems(live, self.LIVE, first_write=True), [])

    def test_no_live_zone_fails_closed_without_first_write(self) -> None:
        live = "## Project scope\n\nOwner text.\n"
        problems = ccc.notes_problems(live, self.LIVE)
        self.assertEqual(len(problems), 1)
        self.assertIn("--first-write", problems[0])

    def test_first_write_changes_nothing_when_live_has_a_zone(self) -> None:
        new = self.LIVE.replace("hold the export ticket", "hold nothing")
        self.assertEqual(len(ccc.notes_problems(self.LIVE, new, first_write=True)), 1)

    def test_reworded_live_heading_dropped_from_new_text_fails(self) -> None:
        live = self.LIVE.replace(ccc.NOTES_HEADING, REWORDED)
        new = "## Project scope\n\nOwner text.\n\n## Coordinator\n\nold generated text\n"
        problems = ccc.notes_problems(live, new)
        self.assertEqual(len(problems), 1)
        self.assertIn("would be lost", problems[0])

    def test_same_reworded_heading_in_live_and_new_passes(self) -> None:
        live = self.LIVE.replace(ccc.NOTES_HEADING, REWORDED)
        new = live.replace("old generated text", "new generated text")
        self.assertEqual(ccc.notes_problems(live, new), [])

    def test_reworded_live_heading_replaced_by_canonical_is_a_difference(self) -> None:
        live = self.LIVE.replace(ccc.NOTES_HEADING, REWORDED)
        problems = ccc.notes_problems(live, self.LIVE)
        self.assertEqual(len(problems), 1)
        self.assertIn(REWORDED, problems[0])
        self.assertIn(ccc.NOTES_HEADING, problems[0])

    def test_differently_worded_duplicate_headings_error(self) -> None:
        with self.assertRaises(ccc.NotesError):
            ccc.notes_problems(self.LIVE + "\n" + REWORDED + "\n\n- b\n", self.LIVE)

    def test_heading_recognition_is_prefix_and_case_insensitive_not_looser(self) -> None:
        self.assertTrue(ccc.is_notes_heading("## coordinator Notes"))
        self.assertTrue(ccc.is_notes_heading(REWORDED))
        self.assertFalse(ccc.is_notes_heading("## Coordinator core"))
        self.assertFalse(ccc.is_notes_heading("## Coordinator notesy"))

    def test_duplicate_heading_errors(self) -> None:
        with self.assertRaises(ccc.NotesError):
            ccc.notes_problems(self.LIVE, self.LIVE + "\n" + self.LIVE)

    def test_zone_ends_at_next_heading_not_end_of_text(self) -> None:
        zone = ccc.extract_notes_zone(self.LIVE, "live")
        self.assertEqual(zone, f"{ccc.NOTES_HEADING}\n\n- 2026-01-02: hold the export ticket.")

    def test_heading_quoted_inline_is_not_a_zone(self) -> None:
        text = f"Never overwrite the `{ccc.NOTES_HEADING}` zone.\n"
        self.assertIsNone(ccc.extract_notes_zone(text, "prose"))

    def test_over_limit_new_text_fails(self) -> None:
        new = self.LIVE + "x" * ccc.CHAR_LIMIT
        problems = ccc.notes_problems(self.LIVE, new)
        self.assertEqual(len(problems), 1)
        self.assertIn("harness limit", problems[0])

    def test_cli_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live, same, changed = (Path(tmp) / n for n in ("live", "same", "changed"))
            live.write_text(self.LIVE)
            same.write_text(self.LIVE.replace("old generated", "new generated"))
            changed.write_text(self.LIVE.replace("export", "import"))
            self.assertEqual(ccc.main(["notes", str(live), str(same)]), 0)
            self.assertEqual(ccc.main(["notes", str(live), str(changed)]), 1)
            changed.write_text(self.LIVE + self.LIVE)
            self.assertEqual(ccc.main(["notes", str(live), str(changed)]), 1)

    def test_cli_first_write_flag_and_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live, new = (Path(tmp) / n for n in ("live", "new"))
            live.write_text("## Project scope\n\nOwner text.\n")
            new.write_text(self.LIVE)
            self.assertEqual(ccc.main(["notes", str(live), str(new)]), 1)
            self.assertEqual(ccc.main(["notes", "--first-write", str(live), str(new)]), 0)
            self.assertEqual(ccc.main(["notes", str(live), str(new), "--first-write"]), 0)
            for bad in (["notes", "--bogus", str(live), str(new)], ["notes", str(live)]):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    ccc.main(bad)
                self.assertEqual(raised.exception.code, 2)

    def test_cli_live_heading_with_semicolon_wording_dropped_exits_nonzero(self) -> None:
        heading = "## Coordinator notes (owner-requested; never overwrite or remove, SDLC-118)"
        with tempfile.TemporaryDirectory() as tmp:
            live, new = (Path(tmp) / n for n in ("live", "new"))
            live.write_text(f"## Scope\nx\n\n{heading}\n- note A\n\n## Coordinator core\ny\n")
            new.write_text("## Scope\nx\n\n## Coordinator core\ny\n")
            self.assertEqual(ccc.main(["notes", str(live), str(new)]), 1)

    def test_cli_reworded_heading_dropped_exits_nonzero(self) -> None:
        live_text = (
            "## Scope\nx\n\n"
            f"{REWORDED}\n- note A\n\n## Coordinator core\ny\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            live, new = (Path(tmp) / n for n in ("live", "new"))
            live.write_text(live_text)
            new.write_text("## Scope\nx\n\n## Coordinator core\ny\n")
            self.assertEqual(ccc.main(["notes", str(live), str(new)]), 1)


REPO = Path(__file__).resolve().parent.parent

# True when this file is discovered as `template/scripts/...` against the raw tree (REPO is
# `template/` itself), where rendered-project paths 404 and only their `.jinja` sources exist.
IN_RAW_TEMPLATE_TREE = REPO.name == "template" and (REPO / ".forge" / "coordinator-core.md.jinja").is_file()


def _repo_path(relative: str) -> Path:
    """Resolve a rendered-project-relative path, falling back to its raw `.jinja` source
    when discovered directly against the unrendered `template/` tree."""
    if IN_RAW_TEMPLATE_TREE:
        jinja_path = REPO / f"{relative}.jinja"
        if jinja_path.is_file():
            return jinja_path
    return REPO / relative


def _repo_text(relative: str) -> str:
    return " ".join(_repo_path(relative).read_text(encoding="utf-8").split())


class ConstraintGuards(unittest.TestCase):
    """One guard per testable constraint of TheForge's coordinator-core ADR; each phrase is the
    shortest one that a deletion of its sentence removes and a rewording that keeps the meaning does not."""

    def test_constraint_1_core_is_synced_through_the_entrypoint(self) -> None:
        self.assertTrue(_repo_path(".forge/coordinator-core.md").is_file())
        self.assertIn("coordinator-core.md", _repo_text(".forge/entrypoint.md"))
        if (REPO / "template").is_dir():
            self.assertTrue((REPO / "template" / ".forge" / "coordinator-core.md.jinja").is_file())
            self.assertIn("coordinator-core.md", _repo_text("template/.forge/entrypoint.md"))

    def test_constraint_5_snippet_keeps_the_coordinator_only_wording(self) -> None:
        snippet = " ".join((ccc.snippet_text(_repo_text_raw("docs/agents/coordinator-core-snippet.md")) or "").split())
        self.assertIn("Only the coordinator session acts on this section", snippet)
        self.assertIn("Every other thread", snippet)
        self.assertIn("ignores it", snippet)

    def test_snippet_tells_a_coordinator_that_forgot_the_codeword_to_reload(self) -> None:
        snippet = " ".join((ccc.snippet_text(_repo_text_raw("docs/agents/coordinator-core-snippet.md")) or "").split())
        self.assertIn("can't say what the current codeword is, reload the coordinator core", snippet)
        self.assertIn("can't say what the current codeword is, reload this file", _repo_text(".forge/coordinator-core.md"))

    def test_proof_needs_the_coordinators_own_whole_read(self) -> None:
        snippet = " ".join((ccc.snippet_text(_repo_text_raw("docs/agents/coordinator-core-snippet.md")) or "").split())
        core = _repo_text(".forge/coordinator-core.md")
        for label, text in (("snippet", snippet), ("core", core)):
            self.assertIn("in full yourself, first line to last, with your own file-read tool, in this session", text, label)
            self.assertIn("report nothing but the fetched short commit sha and the copy's timestamp", text, label)
            self.assertIn("Mid-file check word:", text, label)
            self.assertIn("Proof: codeword XXXX, mid-file check YYYY, origin/main sha Z", text, label)
            self.assertIn("a word seen in a partial or tail read is not proof", text, label)
            self.assertIn("tell the owner plainly that the earlier proof was not valid", text, label)
            self.assertIn("posted, or were about to post, the proof without that read", text, label)

    def test_unreachable_core_spawns_a_fetch_thread_and_partial_copy_is_rechecked(self) -> None:
        """An unreachable authoritative copy has one defined next action, and a partial-copy
        report is preceded by a re-read of the whole file from disk; removing either
        sentence from any copy of the snippet or the core's self-check fails here."""
        fetch = "immediately spawn a thread to attempt to fetch a copy"
        reread = "for a partial copy error, first double check that you actually read the whole of the file from disk"
        paths = [".forge/coordinator-core.md", "docs/agents/coordinator-core-snippet.md"]
        texts = {path: _repo_text(path) for path in paths}
        if IN_RAW_TEMPLATE_TREE:  # the donated root copies, beside the template's own
            for path in paths:
                root_copy = REPO.parent / path
                if root_copy.is_file():
                    texts["root " + path] = " ".join(root_copy.read_text(encoding="utf-8").split())
        for path, text in texts.items():
            self.assertIn(fetch, text, path)
            self.assertIn("do not carry on without", text, path)
            if "snippet" in path:
                self.assertIn("However, " + reread, text, path)
            else:
                self.assertGreaterEqual(text.count("double check that you actually read the whole of the file from disk"), 2, path)

    def test_fetch_always_runs_never_a_cached_copy(self) -> None:
        """TheForge's coordinator-core ADR, freshness constraint: a copy already present,
        or a claim it was refreshed, never counts as current on its own."""
        snippet = " ".join((ccc.snippet_text(_repo_text_raw("docs/agents/coordinator-core-snippet.md")) or "").split())
        core = _repo_text(".forge/coordinator-core.md")
        for label, text in (("snippet", snippet), ("core", core)):
            self.assertIn("never counts as current on its own", text, label)

    def test_confirm_or_reload_ping_means_the_full_check(self) -> None:
        """TheForge's coordinator-core ADR, reload-ping constraint: a timer, sibling-thread or
        owner ping asking to confirm or reload the coordinator's instructions runs the full
        self-check, not a restated codeword."""
        snippet = " ".join((ccc.snippet_text(_repo_text_raw("docs/agents/coordinator-core-snippet.md")) or "").split())
        core = _repo_text(".forge/coordinator-core.md")
        for label, text in (("snippet", snippet), ("core", core)):
            self.assertIn("asks you to confirm or reload your instructions", text, label)
            self.assertIn("never a restatement of a codeword already in context", text, label)

    def test_constraint_8_core_keeps_the_timer_helper_and_fails_loudly_sentences(self) -> None:
        core = _repo_text(".forge/coordinator-core.md")
        self.assertIn("## The 30-minute timer is essential", core)
        self.assertIn("If you have no deferred-wake tool, start a one-off mechanical-tier thread", core)
        self.assertIn("setup fails loudly", core)

    def test_constraint_9_core_keeps_the_mechanical_tier_helper_sentence(self) -> None:
        core = _repo_text(".forge/coordinator-core.md")
        self.assertIn("Helper work with one obviously correct outcome", core)
        self.assertIn("mechanical-tier, never build-tier", core)

    def test_core_is_the_authoritative_text_of_the_coordinators_rules(self) -> None:
        core = _repo_text(".forge/coordinator-core.md")
        self.assertIn("It is the authoritative text of the coordinator's own rules", core)
        self.assertNotIn("It duplicates `.agents/skills/coordinator/SKILL.md`", core)

    def test_coordinator_skill_points_at_the_core_as_authoritative(self) -> None:
        skill = _repo_text(".agents/skills/coordinator/SKILL.md")
        self.assertIn(
            "The authoritative text of the coordinator's rules is `.forge/coordinator-core.md`; this file holds only look-up procedures.",
            skill,
        )

    def test_bootstrap_checklist_pastes_the_snippet_not_the_retired_generator(self) -> None:
        paths = ["scripts/project_init_checklist.md", ".agents/skills/retrofit-existing-project/SKILL.md"]
        if (REPO / "template").is_dir():
            paths += ["template/scripts/project_init_checklist.md.jinja", "template/.agents/skills/retrofit-existing-project/SKILL.md"]
        for path in paths:
            text = _repo_text(path)
            self.assertIn("coordinator-core-snippet.md", text, path)
            self.assertIn("an empty `## Coordinator notes` zone", text, path)
            self.assertNotIn("generate_condensed_copy", text, path)


class LockTests(unittest.TestCase):
    """The lock fails when a cited source section changes, a citation is broken or missing, or the codeword differs."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".forge").mkdir()
        self.source = self.root / ".forge" / "rules.md"
        self.source.write_text("# Rules\n\n## Alpha\n\nDo   the first thing.\n\n## Beta\n\nOther.\n", encoding="utf-8")
        self.core = (
            "# Core\n\n**TRUNCATION GUARD — read this first.**\nIf missing, tell the owner.\n\n"
            '## One\n\nCondenses: .forge/rules.md "Alpha"\n\nText.\n\n'
            "## Two\n\nCondenses: none (authoritative)\n\nText.\n\n"
            "END OF COORDINATOR CORE — codeword: OSPREYWING\n"
        )

    def _lock(self) -> dict:
        lock, problems = ccc.refresh_lock(self.core, None, self.root)
        self.assertEqual(problems, [])
        assert lock is not None
        return lock

    def test_fresh_lock_passes_and_ignores_whitespace(self) -> None:
        lock = self._lock()
        self.assertEqual(ccc.lock_problems(self.core, lock, self.root), [])
        self.source.write_text(self.source.read_text().replace("Do   the", "Do the"), encoding="utf-8")
        self.assertEqual(ccc.lock_problems(self.core, lock, self.root), [])

    def test_changed_source_section_fails_but_other_sections_do_not(self) -> None:
        lock = self._lock()
        self.source.write_text(self.source.read_text().replace("Other.", "Changed."), encoding="utf-8")
        self.assertEqual(ccc.lock_problems(self.core, lock, self.root), [])
        self.source.write_text(self.source.read_text().replace("first thing", "second thing"), encoding="utf-8")
        self.assertTrue(any("changed since the lock" in p for p in ccc.lock_problems(self.core, lock, self.root)))

    def test_jinja_source_is_read_from_its_raw_text(self) -> None:
        self.source.rename(self.root / ".forge" / "rules.md.jinja")
        self.assertEqual(ccc.lock_problems(self.core, self._lock(), self.root), [])

    def test_missing_path_or_heading_fails(self) -> None:
        lock = self._lock()
        self.source.unlink()
        self.assertTrue(any("not found" in p for p in ccc.lock_problems(self.core, lock, self.root)))
        self.source.write_text("# Rules\n\n## Beta\n\nOther.\n", encoding="utf-8")
        self.assertTrue(any("found 0 times" in p for p in ccc.lock_problems(self.core, lock, self.root)))

    def test_section_without_provenance_line_fails(self) -> None:
        core = self.core.replace("Condenses: none (authoritative)\n\n", "")
        self.assertTrue(any("no \"Condenses:\" provenance line" in p for p in ccc.lock_problems(core, self._lock(), self.root)))

    def test_codeword_difference_fails(self) -> None:
        lock = self._lock()
        core = self.core.replace("OSPREYWING", "KESTRELDOWN")
        self.assertTrue(any("codeword" in p for p in ccc.lock_problems(core, lock, self.root)))

    def test_refresh_refuses_until_the_codeword_rolls(self) -> None:
        lock = self._lock()
        self.source.write_text(self.source.read_text().replace("first thing", "second thing"), encoding="utf-8")
        refreshed, problems = ccc.refresh_lock(self.core, lock, self.root)
        self.assertIsNone(refreshed)
        self.assertTrue(any("roll the codeword" in p for p in problems))
        rolled = self.core.replace("OSPREYWING", "KESTRELDOWN")
        refreshed, problems = ccc.refresh_lock(rolled, lock, self.root)
        self.assertEqual(problems, [])
        assert refreshed is not None
        self.assertEqual(ccc.lock_problems(rolled, refreshed, self.root), [])

    def test_cli_check_and_refresh_round_trip(self) -> None:
        core_file, lock_file = self.root / "core.md", self.root / "core.lock.json"
        core_file.write_text(self.core, encoding="utf-8")
        argv = [str(core_file), "--lock", str(lock_file), "--source-root", str(self.root)]
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ccc.main(["lock", *argv]), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ccc.main(["lock", "--refresh", *argv]), 0)
            self.assertEqual(ccc.main(["lock", *argv]), 0)
        self.source.write_text(self.source.read_text().replace("first thing", "second thing"), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(ccc.main(["lock", *argv]), 1)
            self.assertEqual(ccc.main(["lock", "--refresh", *argv]), 1)
        self.assertIn("roll the codeword", err.getvalue())
        lock_file.write_text("{not json", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ccc.main(["lock", *argv]), 1)

    def test_malformed_lock_is_a_problem_not_a_crash(self) -> None:
        for bad in ([], {"sections": None}, {"sections": []}):
            self.assertTrue(any("malformed" in p for p in ccc.lock_problems(self.core, bad, self.root)))  # type: ignore[arg-type]
        refreshed, problems = ccc.refresh_lock(self.core, [], self.root)  # type: ignore[arg-type]
        self.assertEqual(problems, [])
        self.assertIsNotNone(refreshed)

    def test_shipped_template_core_carries_the_same_provenance_and_codeword(self) -> None:
        template_core = REPO / "template" / ".forge" / "coordinator-core.md.jinja"
        if not template_core.is_file():
            self.skipTest("only TheForge's own repository has the template source")
        root_text = (REPO / ".forge" / "coordinator-core.md").read_text(encoding="utf-8")
        template_text = template_core.read_text(encoding="utf-8")
        provenance = lambda text: [ln for ln in text.splitlines() if ln.startswith(ccc.PROVENANCE_PREFIX)]  # noqa: E731
        self.assertEqual(provenance(root_text), provenance(template_text))
        self.assertEqual(ccc.core_codeword(root_text), ccc.core_codeword(template_text))
        self.assertEqual(ccc._mid_word(root_text), ccc._mid_word(template_text))

    def test_committed_lock_matches_the_repository(self) -> None:
        core_path, lock_path = REPO / ".forge" / "coordinator-core.md", REPO / "coordinator-core.lock.json"
        if not (lock_path.is_file() and (REPO / "template").is_dir()):
            self.skipTest("the lock is root-only and is not shipped to consumers")
        problems = ccc.lock_problems(core_path.read_text(encoding="utf-8"), json.loads(lock_path.read_text(encoding="utf-8")), REPO / "template")
        self.assertEqual(problems, [])


def _repo_text_raw(relative: str) -> str:
    return _repo_path(relative).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
