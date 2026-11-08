"""Guard test: every flow that can end in an owner's or person's own merge
tells its agent to post the post-merge-review pending note once it sees
that merge.

Run standalone: python3 template/scripts/test_pending_note_coverage.py

These are prose/jinja skill and rule files read by an agent, not executable
code, so there is no runtime behaviour to exercise directly. This test pins
the specific sentence in each flow, joined with the context phrase it must
sit next to (not just appear somewhere in the same file), so a later edit
that silently drops the instruction, or moves it away from its context,
is caught mechanically instead of only by a human re-reading the prose.
This guards against a defect found once before: a flow that opens a PR but
never posts the pending note once that PR is merged, whether a human merges
it directly or the agent merges it itself once the approval it needs is
recorded.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jinja_paths import ROOT, rendered_or_jinja  # noqa: E402

IMPLEMENT = ROOT / ".agents" / "skills" / "implement" / "SKILL.md"
REQUIREMENTS_DRIVEN_CHANGES = ROOT / ".forge" / "requirements-driven-changes.md"
PROCESS_AND_EVIDENCE = rendered_or_jinja(".forge", "process-and-evidence.md")
RELEASE_NOTES = rendered_or_jinja(".agents", "skills", "release-notes", "SKILL.md")
POST_MERGE_REVIEW = rendered_or_jinja(".agents", "skills", "post-merge-review", "SKILL.md")


def _normalized(text: str) -> str:
    """Collapse whitespace runs so a sentence wrapped across lines (a numbered
    step's continuation, say) still matches as one contiguous phrase."""
    return re.sub(r"\s+", " ", text)


class OwnerMergeFlowsPostThePendingNote(unittest.TestCase):
    def test_implement_tells_the_agent_to_watch_for_the_merge_and_post_the_note(self) -> None:
        text = _normalized(IMPLEMENT.read_text(encoding="utf-8"))
        self.assertIn(
            "a human merges it, not you. Once you see it merged, post the merge's "
            'pending post-merge-review note on the tracker, in the form '
            '`.agents/skills/post-merge-review/SKILL.md`, "Pending reviews", gives',
            text,
            "implement must say a human merges its PR and tell the agent to post "
            "the pending post-merge-review note once it sees that merge, since "
            "this skill ends at PR open",
        )

    def test_requirements_driven_changes_tells_the_agent_to_post_the_note_on_the_spec_only_pr(self) -> None:
        text = _normalized(REQUIREMENTS_DRIVEN_CHANGES.read_text(encoding="utf-8"))
        self.assertIn(
            "Once the spec-only PR merges, the agent that opened it posts the "
            "merge's pending post-merge-review note on the tracker, in the form "
            '`.agents/skills/post-merge-review/SKILL.md`, "Pending reviews", gives',
            text,
            "requirements-driven-changes must tell the agent that opened the "
            "spec-only PR to post the pending note once it merges it, having "
            "recorded the owner's approval of the wording",
        )

    def test_process_and_evidence_tells_the_agent_to_post_the_note_on_the_lifecycle_doc_pr(self) -> None:
        text = _normalized(PROCESS_AND_EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn(
            "Once the owner's approval of the exact wording is recorded on "
            "that lifecycle-doc PR, the agent that opened it merges it and "
            "posts the merge's pending post-merge-review note on the tracker, "
            'in the form `.agents/skills/post-merge-review/SKILL.md`, "Pending '
            'reviews", gives',
            text,
            "process-and-evidence must tell the agent that opened the "
            "lifecycle-doc PR to merge it and post the pending note once the "
            "owner's approval of the wording is recorded",
        )

    def test_release_notes_tells_the_agent_to_post_the_note_on_its_pr(self) -> None:
        text = _normalized(RELEASE_NOTES.read_text(encoding="utf-8"))
        self.assertIn(
            "The person merges it after review. Once you see it merged, post "
            "the merge's pending post-merge-review note on the tracker, in the "
            'form `.agents/skills/post-merge-review/SKILL.md`, "Pending '
            'reviews", gives',
            text,
            "release-notes must tell the agent that opened its PR to post the "
            "pending note once the person merges it, the same owner-merge shape "
            "as implement",
        )

    def test_post_merge_review_enumerates_every_owner_or_person_merged_flow(self) -> None:
        text = _normalized(POST_MERGE_REVIEW.read_text(encoding="utf-8"))
        self.assertIn(
            "When the owner or the person merges a PR an agent opened instead "
            "(an `implement` PR, where the owner chose that route, or a "
            "release-notes PR), the agent that opened it posts the note once "
            "it sees the merge",
            text,
            "post-merge-review's own Pending reviews section must name every "
            "flow whose PR an owner or person (not the agent) merges, so the "
            "enumeration itself doesn't go stale as a flow is added",
        )


if __name__ == "__main__":
    sys.exit(unittest.main())
