"""Guard tests for check_review_gate.py, run standalone: python3 scripts/test_check_review_gate.py"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_review_gate  # noqa: E402

REAL_STANDARDS = "clean sub-agent, build-tier -- no findings"
REAL_SPEC = "clean sub-agent, build-tier -- matches issue #1, no findings"
REAL_SELF_REVIEW = "build-tier (builder's own) -- covered all parts; no findings"
LIGHT_NA = "n/a (light gate: prose-only doc edit)"


def body(standards: str, spec: str, selfreview: str) -> str:
    return (
        "Before: x\n\nAfter: y\n\nTicket: Closes #1\n\n"
        f"Review: Standards: {standards}. Spec: {spec}. Self-review: {selfreview}."
    )


class FullGateRealEntries(unittest.TestCase):
    def test_real_entries_on_code_change_pass(self) -> None:
        failures = check_review_gate.check(
            body(REAL_STANDARDS, REAL_SPEC, REAL_SELF_REVIEW), ["scripts/thing.py"]
        )
        self.assertEqual(failures, [])

    def test_missing_review_field_fails(self) -> None:
        failures = check_review_gate.check("Before: x\n\nAfter: y\n", ["scripts/thing.py"])
        self.assertEqual(len(failures), 1)
        self.assertIn("Review: field missing", failures[0])

    def test_placeholder_standards_fails(self) -> None:
        failures = check_review_gate.check(
            body("<performer, tier[, model]>", REAL_SPEC, REAL_SELF_REVIEW), ["scripts/thing.py"]
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Standards", failures[0])

    def test_placeholder_spec_fails(self) -> None:
        failures = check_review_gate.check(
            body(REAL_STANDARDS, "<same, against the design doc slice>", REAL_SELF_REVIEW), ["scripts/thing.py"]
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Spec", failures[0])

    def test_placeholder_self_review_fails(self) -> None:
        failures = check_review_gate.check(
            body(REAL_STANDARDS, REAL_SPEC, "<parts covered; found/addressed>"), ["scripts/thing.py"]
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Self-review", failures[0])

    def test_empty_entries_fail(self) -> None:
        failures = check_review_gate.check(body("", "", ""), ["scripts/thing.py"])
        self.assertEqual(len(failures), 3)


class BuildersOwnAxisFails(unittest.TestCase):
    """An axis the builder reviewed itself never clears the full gate."""

    def test_builders_own_standards_fails(self) -> None:
        failures = check_review_gate.check(
            body("builder's own, no sub-agent tool available", REAL_SPEC, REAL_SELF_REVIEW),
            ["scripts/thing.py"],
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Standards", failures[0])

    def test_no_sub_agent_tool_spec_fails(self) -> None:
        failures = check_review_gate.check(
            body(REAL_STANDARDS, "reviewed inline, no sub-agent tool", REAL_SELF_REVIEW),
            ["scripts/thing.py"],
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Spec", failures[0])

    def test_negated_phrase_fails_closed(self) -> None:
        failures = check_review_gate.check(
            body("clean-context sub-agent, not the builder's own", REAL_SPEC, REAL_SELF_REVIEW),
            ["scripts/thing.py"],
        )
        self.assertEqual(len(failures), 1)

    def test_builders_own_self_review_still_passes(self) -> None:
        failures = check_review_gate.check(
            body(REAL_STANDARDS, REAL_SPEC, "builder's own, build-tier — nine parts, nothing found"),
            ["scripts/thing.py"],
        )
        self.assertEqual(failures, [])


class AxisMustRecordACleanContextReview(unittest.TestCase):
    """.forge/review-gate.md, "A builder with no sub-agent tool asks its parent for the
    review": an axis that is real content but still waiting for its reviewer, or
    reviewed only in chat, carries no clean-context marker and must not clear the
    full gate either."""

    def test_awaiting_standards_fails(self) -> None:
        failures = check_review_gate.check(
            body("awaiting independent review, requested from the parent build thread", REAL_SPEC, REAL_SELF_REVIEW),
            ["scripts/thing.py"],
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Standards", failures[0])

    def test_awaiting_with_clean_context_wording_still_fails(self) -> None:
        """AWAITING_RE has to do its own work: this entry already contains `clean-context`,
        so only the `awaiting` clause, not CLEAN_CONTEXT_RE, is what catches it."""
        failures = check_review_gate.check(
            body("awaiting clean-context review from the parent build thread", REAL_SPEC, REAL_SELF_REVIEW),
            ["scripts/thing.py"],
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Standards", failures[0])

    def test_reviewed_in_chat_only_spec_fails(self) -> None:
        failures = check_review_gate.check(
            body(REAL_STANDARDS, "independent review could not run, left unmerged", REAL_SELF_REVIEW),
            ["scripts/thing.py"],
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Spec", failures[0])

    def test_real_entry_with_no_context_marker_fails(self) -> None:
        failures = check_review_gate.check(
            body("sub-agent abc of https://example.invalid/session, build-tier -- no findings", REAL_SPEC, REAL_SELF_REVIEW),
            ["scripts/thing.py"],
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Standards", failures[0])

    def test_parent_started_review_with_clean_context_passes(self) -> None:
        failures = check_review_gate.check(
            body(
                "sub-agent a1 of https://example.invalid/session, started by the parent on the builder's "
                "request, build-tier, clean-context -- no findings",
                REAL_SPEC,
                REAL_SELF_REVIEW,
            ),
            ["scripts/thing.py"],
        )
        self.assertEqual(failures, [])

    def test_light_gate_na_entry_still_passes_with_no_clean_context_text(self) -> None:
        failures = check_review_gate.check(
            body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW), ["docs/design/a.md"]
        )
        self.assertEqual(failures, [])


class LightGateOnNonDocFails(unittest.TestCase):
    """Light gate claimed on a non-`.md` config file -- never eligible."""

    def test_light_gate_on_config_file_fails(self) -> None:
        failures = check_review_gate.check(
            body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW), [".copier-answers.yml"]
        )
        self.assertEqual(len(failures), 2)
        for failure in failures:
            self.assertIn("not a prose-only doc", failure)
            self.assertIn(".copier-answers.yml", failure)

    def test_light_gate_on_code_file_fails(self) -> None:
        failures = check_review_gate.check(body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW), ["backend/app.py"])
        self.assertEqual(len(failures), 2)

    def test_light_gate_on_rule_bearing_md_fails(self) -> None:
        for path in (
            "CLAUDE.md",
            "docs/principles.md",
            "docs/software-development-lifecycle.md",
            "docs/requirements/requirements-specification.md",
            ".agents/skills/self-review/SKILL.md",
            ".forge/review-gate.md",
            "docs/agents/lessons.md",
            "docs/security/threat-model.md",
            "docs/forge-overrides.md",
            ".github/pull_request_template.md",
        ):
            with self.subTest(path=path):
                failures = check_review_gate.check(body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW), [path])
                self.assertEqual(len(failures), 2)


class RequirementsSpecIsNeverLightGateEligible(unittest.TestCase):
    """A status-only edit to the requirements specification reads like the
    most plausible light-gate claim this file can make (a status line is
    plain prose, changes no requirement wording, and touches no snippet
    text) -- which is exactly why it must still fail: the gate is chosen by
    path, never by how harmless the edit inside the path looks.
    `.forge/requirements-driven-changes.md`'s "needs no owner approval"
    carve-out for a non-wording edit answers the approval question only; it
    never answers which review gate that edit gets. This goes red if
    `docs/requirements/requirements-specification.md` is ever removed from
    DISQUALIFYING_DOC_PATTERNS."""

    def test_status_only_requirements_spec_edit_rejects_light_gate(self) -> None:
        failures = check_review_gate.check(
            body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW),
            ["docs/requirements/requirements-specification.md"],
        )
        self.assertEqual(len(failures), 2)
        for failure in failures:
            self.assertIn("not a prose-only doc", failure)
            self.assertIn("requirements-specification.md", failure)

    def test_full_gate_on_requirements_spec_still_passes(self) -> None:
        """A builder may always take the full gate instead."""
        failures = check_review_gate.check(
            body(REAL_STANDARDS, REAL_SPEC, REAL_SELF_REVIEW),
            ["docs/requirements/requirements-specification.md"],
        )
        self.assertEqual(failures, [])


class LightGateOnProseDocPasses(unittest.TestCase):
    def test_light_gate_on_ordinary_doc_passes(self) -> None:
        failures = check_review_gate.check(body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW), ["docs/design/widget.md"])
        self.assertEqual(failures, [])

    def test_light_gate_requires_every_changed_file_to_qualify(self) -> None:
        failures = check_review_gate.check(
            body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW), ["docs/design/widget.md", "scripts/thing.py"]
        )
        self.assertEqual(len(failures), 2)

    def test_self_review_still_required_on_light_gate(self) -> None:
        failures = check_review_gate.check(
            body(LIGHT_NA, LIGHT_NA, "<parts covered; found/addressed>"), ["docs/design/widget.md"]
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("Self-review", failures[0])


class InventedExemptionFails(unittest.TestCase):
    """A cited exemption that isn't the sanctioned light-gate phrase -- fails closed."""

    def test_invented_lifecycle_exception_fails(self) -> None:
        invented = "n/a (lifecycle-doc exception, SDLC-043/SDLC-117)"
        failures = check_review_gate.check(body(invented, invented, REAL_SELF_REVIEW), ["backend/app.py"])
        self.assertEqual(len(failures), 2)
        for failure in failures:
            self.assertIn("doesn't recognize", failure)

    def test_bare_na_with_no_reason_fails_even_on_an_eligible_doc(self) -> None:
        failures = check_review_gate.check(body("n/a", "n/a", REAL_SELF_REVIEW), ["docs/design/widget.md"])
        self.assertEqual(len(failures), 2)

    def test_mechanical_tier_citation_alone_is_not_accepted(self) -> None:
        failures = check_review_gate.check(
            body("n/a (mechanical-tier)", "n/a (mechanical-tier)", REAL_SELF_REVIEW), ["docs/design/widget.md"]
        )
        self.assertEqual(len(failures), 2)

    def test_light_gate_claim_with_an_unfilled_reason_placeholder_fails(self) -> None:
        """The template's own unfilled default text, `n/a (light gate:
        <reason>)`, must not itself read as a valid light-gate claim."""
        unfilled = "n/a (light gate: <reason>)"
        failures = check_review_gate.check(body(unfilled, unfilled, REAL_SELF_REVIEW), ["docs/design/widget.md"])
        self.assertEqual(len(failures), 2)

    def test_light_gate_claim_with_an_empty_reason_fails(self) -> None:
        failures = check_review_gate.check(
            body("n/a (light gate: )", "n/a (light gate: )", REAL_SELF_REVIEW), ["docs/design/widget.md"]
        )
        self.assertEqual(len(failures), 2)


class EmptyFileListFailsClosed(unittest.TestCase):
    """A PR always changes at least one file; an empty list means the
    caller's own data is broken, not that there's nothing to disqualify a
    light-gate claim."""

    def test_light_gate_claim_with_no_changed_files_fails(self) -> None:
        failures = check_review_gate.check(body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW), [])
        self.assertEqual(len(failures), 2)
        for failure in failures:
            self.assertIn("not a prose-only doc", failure)


class MixedChanges(unittest.TestCase):
    def test_one_disqualifying_file_among_many_docs_blocks_light_gate(self) -> None:
        failures = check_review_gate.check(
            body(LIGHT_NA, LIGHT_NA, REAL_SELF_REVIEW),
            ["docs/design/a.md", "docs/design/b.md", "CLAUDE.md"],
        )
        self.assertEqual(len(failures), 2)

    def test_full_gate_on_all_docs_still_passes(self) -> None:
        """A builder may always take the full gate even when the light gate
        would have been available."""
        failures = check_review_gate.check(
            body(REAL_STANDARDS, REAL_SPEC, REAL_SELF_REVIEW), ["docs/design/a.md"]
        )
        self.assertEqual(failures, [])


class RealBodyShapes(unittest.TestCase):
    """A real PR body isn't just the template's own fields: it often has more
    text after `Review:` (an attribution footer, say), and a drafter
    explaining a departure may quote the field's own format earlier in the
    body. Neither should confuse which occurrence is the real field or how
    much of the body belongs to Self-review."""

    def test_trailing_footer_after_review_line_does_not_swallow_into_self_review(self) -> None:
        text = (
            body(REAL_STANDARDS, REAL_SPEC, REAL_SELF_REVIEW)
            + "\n\n---\n_Generated by an agent <https://example.invalid/tool>_\n"
        )
        failures = check_review_gate.check(text, ["scripts/thing.py"])
        self.assertEqual(failures, [])

    def test_a_trailer_with_no_blank_line_before_it_does_not_swallow_into_self_review(self) -> None:
        """A commit-style attribution trailer (`Key: value`) is routinely
        appended right after the template's last field, with no blank line."""
        text = body(REAL_STANDARDS, REAL_SPEC, REAL_SELF_REVIEW) + "\nCo-Authored-By: Agent <noreply@example.invalid>\n"
        failures = check_review_gate.check(text, ["scripts/thing.py"])
        self.assertEqual(failures, [])

    def test_an_earlier_quoted_example_is_ignored_in_favour_of_the_real_field(self) -> None:
        quoted_example = (
            "For reference, the template's field reads:\n"
            "Review: Standards: <performer, tier[, model]>. Spec: <same>. Self-review: <parts covered>.\n\n"
        )
        text = quoted_example + body(REAL_STANDARDS, REAL_SPEC, REAL_SELF_REVIEW)
        failures = check_review_gate.check(text, ["scripts/thing.py"])
        self.assertEqual(failures, [])


class RealContentContainingAngleBrackets(unittest.TestCase):
    """A real, filled-in entry can legitimately cite a URL/autolink in angle
    brackets; that is not an unfilled template placeholder."""

    def test_self_review_citing_an_autolink_passes(self) -> None:
        selfreview = "build-tier (builder's own) -- verified against <https://example.invalid/pull/905#discussion_r1> for the other-caller sweep"
        failures = check_review_gate.check(body(REAL_STANDARDS, REAL_SPEC, selfreview), ["scripts/thing.py"])
        self.assertEqual(failures, [])

    def test_an_actual_placeholder_still_fails_even_with_a_url_elsewhere(self) -> None:
        selfreview = "<parts covered; found/addressed>, see <https://example.invalid/pull/905>"
        failures = check_review_gate.check(body(REAL_STANDARDS, REAL_SPEC, selfreview), ["scripts/thing.py"])
        self.assertEqual(len(failures), 1)
        self.assertIn("Self-review", failures[0])


class NonUrlBracketFailsClosedByDesign(unittest.TestCase):
    """A real entry that cites a non-URL bracketed term (e.g. a literal tag
    name) still fails -- a deliberate trade-off: a real entry can always
    reword or quote it instead, which is far cheaper than letting a
    half-filled placeholder read as real (see field_is_real's docstring)."""

    def test_a_non_url_bracket_in_otherwise_real_prose_still_fails(self) -> None:
        standards = (
            "clean sub-agent, build-tier -- checked that user input containing "
            "<script> tags is escaped before render; no findings"
        )
        failures = check_review_gate.check(body(standards, REAL_SPEC, REAL_SELF_REVIEW), ["scripts/thing.py"])
        self.assertEqual(len(failures), 1)
        self.assertIn("Standards", failures[0])

    def test_a_half_filled_placeholder_with_real_words_added_still_fails(self) -> None:
        """The regression a word-count heuristic would have let through:
        the template's own placeholder left in place, with a few genuine
        words tacked on around it."""
        standards = "<performer, tier[, model]>, build-tier -- no findings"
        failures = check_review_gate.check(body(standards, REAL_SPEC, REAL_SELF_REVIEW), ["scripts/thing.py"])
        self.assertEqual(len(failures), 1)
        self.assertIn("Standards", failures[0])


class SingleWordColonLineInSelfReviewDoesNotTruncate(unittest.TestCase):
    """Self-review's trailer-stop only matches a hyphenated trailer key
    (`Co-Authored-By:`), not an ordinary single-word line such as a
    self-review checklist note, so a multi-line self-review entry isn't cut
    short partway through."""

    def test_a_single_word_colon_line_inside_self_review_does_not_truncate(self) -> None:
        selfreview = (
            "build-tier (builder's own) --\n"
            "Reuse: extended the existing helper instead of writing a new one.\n"
            "No stale citations found."
        )
        failures = check_review_gate.check(body(REAL_STANDARDS, REAL_SPEC, selfreview), ["scripts/thing.py"])
        self.assertEqual(failures, [])

    def test_a_hyphenated_colon_line_inside_self_review_does_not_truncate(self) -> None:
        """An earlier version stopped the self-review capture at the
        *first* hyphenated `Key: value` line, mistaking a self-review entry's
        own hyphenated label (`Fast-path:`) for a commit-style trailer and
        silently dropping everything after it. `failures == []` alone
        wouldn't catch a regression here -- the truncated capture can still
        happen to look real -- so this asserts the full retained text
        directly, the same way the module's own trailer-stripping is unit
        tested below."""
        selfreview = "build-tier --\nFast-path: used the existing helper.\nNo other findings."
        failures = check_review_gate.check(body(REAL_STANDARDS, REAL_SPEC, selfreview), ["scripts/thing.py"])
        self.assertEqual(failures, [])

        segment = body(REAL_STANDARDS, REAL_SPEC, selfreview)
        match = check_review_gate.REVIEW_FIELD_RE.search(segment)
        retained = check_review_gate._strip_trailing_trailer_block(match["selfreview"])
        self.assertEqual(retained, selfreview)


class StripTrailingTrailerBlock(unittest.TestCase):
    """Unit tests for _strip_trailing_trailer_block in isolation, since
    `check()`'s `failures == []` can't distinguish a correctly retained
    self-review entry from a truncated one that happens to still look real."""

    def test_strips_a_single_trailing_trailer_line(self) -> None:
        text = "build-tier -- no findings.\nCo-Authored-By: Agent <noreply@example.invalid>"
        self.assertEqual(
            check_review_gate._strip_trailing_trailer_block(text), "build-tier -- no findings."
        )

    def test_strips_multiple_contiguous_trailing_trailer_lines(self) -> None:
        text = (
            "build-tier -- no findings.\n"
            "Co-Authored-By: Agent <noreply@example.invalid>\n"
            "Claude-Session: https://example.invalid/session/abc"
        )
        self.assertEqual(
            check_review_gate._strip_trailing_trailer_block(text), "build-tier -- no findings."
        )

    def test_keeps_a_hyphenated_label_line_followed_by_prose(self) -> None:
        text = "build-tier --\nFast-path: used the existing helper.\nNo other findings."
        self.assertEqual(check_review_gate._strip_trailing_trailer_block(text), text)

    def test_keeps_text_with_no_trailing_trailer_at_all(self) -> None:
        text = "build-tier (builder's own) -- covered all parts; no findings"
        self.assertEqual(check_review_gate._strip_trailing_trailer_block(text), text)

    def test_keeps_a_non_trailer_hyphenated_label_even_as_the_last_line(self) -> None:
        """A self-review entry's own hyphenated label can legitimately be
        its last line, with nothing after it -- only a known trailer key
        (the `-by` family, Claude-Session, etc.) is ever stripped, not any
        hyphenated `Key:` shape, so this doesn't collide with that case."""
        text = "build-tier --\nFast-path: used the existing helper."
        self.assertEqual(check_review_gate._strip_trailing_trailer_block(text), text)


class MultiLineLightGateReason(unittest.TestCase):
    def test_a_line_wrapped_light_gate_reason_is_still_recognized(self) -> None:
        wrapped = "n/a (light gate: prose-only doc edit,\nno rule touched)"
        failures = check_review_gate.check(body(wrapped, wrapped, REAL_SELF_REVIEW), ["docs/design/widget.md"])
        self.assertEqual(failures, [])


class MainCli(unittest.TestCase):
    def test_main_reads_files_and_returns_exit_code(self, tmp_path: Path | None = None) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            files_path = Path(tmp) / "files.txt"
            body_path.write_text(body(REAL_STANDARDS, REAL_SPEC, REAL_SELF_REVIEW), encoding="utf-8")
            files_path.write_text("scripts/thing.py\n", encoding="utf-8")
            self.assertEqual(check_review_gate.main([str(body_path), str(files_path)]), 0)

    def test_main_fails_closed_on_a_bad_review_field(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            body_path = Path(tmp) / "body.txt"
            files_path = Path(tmp) / "files.txt"
            body_path.write_text("no review field here", encoding="utf-8")
            files_path.write_text("scripts/thing.py\n", encoding="utf-8")
            self.assertEqual(check_review_gate.main([str(body_path), str(files_path)]), 1)

    def test_main_requires_exactly_two_arguments(self) -> None:
        self.assertEqual(check_review_gate.main([]), 2)
        self.assertEqual(check_review_gate.main(["one"]), 2)


if __name__ == "__main__":
    unittest.main()
