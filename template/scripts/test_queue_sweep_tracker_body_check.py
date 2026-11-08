"""Guard for queue-sweep check 13 (tracker body corrupted): the two gap
conditions it names actually catch the real failure that motivated the
check, and still flag it on their own, independent of whichever LLM is
reading the skill at the time.

queue-sweep's checks are prose a thread follows, not code this repo ships
and runs, so there is no program to extract and execute the way
test_queue_sweep_archive_fixture.py does for check 11(a)'s jq. This test
instead pins that check 13's section text still names both conditions, and
implements them in Python exactly as written so a change to the check's
wording that silently drops or weakens a condition is caught here, by
giving that implementation the exact body check 13 was written to catch
and a healthy tracker body it must leave alone.

Run standalone: python3 template/scripts/test_queue_sweep_tracker_body_check.py
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jinja_paths import rendered_or_jinja  # noqa: E402

QUEUE_SWEEP = rendered_or_jinja(".agents", "skills", "queue-sweep", "SKILL.md")


def _check_13_section() -> str:
    text = QUEUE_SWEEP.read_text(encoding="utf-8")
    match = re.search(
        r"### 13\. Post-merge review tracker body corrupted\n(.*?)(?=\n## |\Z)",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("queue-sweep check 13 (tracker body corrupted) was not found")
    return match.group(1)


def _is_body_corrupted(body: str) -> bool:
    """The two gap conditions check 13 states, applied to a tracker body."""
    missing_watermark = "**Watermark:**" not in body
    leaked_marker = "<!-- pending-post-merge-review" in body or "<!-- post-merge-review-archive" in body
    return missing_watermark or leaked_marker


class Check13SectionNamesBothConditions(unittest.TestCase):
    def test_the_section_exists_and_names_both_conditions(self) -> None:
        section = _check_13_section()
        self.assertIn("**Watermark:**", section)
        self.assertIn("pending-post-merge-review", section)
        self.assertIn("post-merge-review-archive", section)
        self.assertIn("Must", section, "losing the tracker's only durable record must be graded a Must")


class HealthyTrackerBodyIsNotFlagged(unittest.TestCase):
    def test_a_normal_body_with_watermark_and_run_log_passes(self) -> None:
        body = (
            "**Watermark:** aaaaaaa (PR N1, merged 2001-01-01T00:00:00Z)\n\n"
            "Procedure: `.agents/skills/post-merge-review/SKILL.md`.\n\n"
            "| Run | Archive |\n|---|---|\n| 1 | link |\n| 2 | link |\n| 3 | link |\n"
        )
        self.assertFalse(_is_body_corrupted(body))


class CorruptedTrackerBodyIsFlagged(unittest.TestCase):
    def test_the_shape_this_check_was_written_for(self) -> None:
        # A single pending note's own text, sent as a body edit instead of a
        # comment, wiping whatever watermark and run log were there.
        body = "<!-- pending-post-merge-review pr=N1 sha=aaaaaaa -->\n" "Pending post-merge review: PR N1, merged as aaaaaaa."
        self.assertTrue(_is_body_corrupted(body), "a body with no watermark and a leaked marker must be flagged")

    def test_a_body_missing_only_the_watermark_line_is_still_flagged(self) -> None:
        body = "Procedure: `.agents/skills/post-merge-review/SKILL.md`.\n\n| Run | Archive |\n|---|---|\n"
        self.assertTrue(_is_body_corrupted(body))

    def test_a_body_that_keeps_its_watermark_but_leaks_a_marker_is_still_flagged(self) -> None:
        # Guards the "or", not just the "missing watermark" half: a body
        # that somehow retains its watermark line but also picks up a
        # leaked marker (e.g. a partial/duplicated write) must still flag.
        body = (
            "**Watermark:** aaaaaaa (PR N1, merged 2001-01-01T00:00:00Z)\n\n"
            "<!-- pending-post-merge-review pr=N2 sha=bbbbbbb -->\n"
            "Pending post-merge review: PR N2, merged as bbbbbbb.\n"
        )
        self.assertTrue(_is_body_corrupted(body))


if __name__ == "__main__":
    sys.exit(unittest.main())
