"""Guard test for the pending-marker author check: a pending-review note, a
post-merge-review-archive covered-PR marker, or a local-full-suite evidence
marker must only be trusted from an OWNER/MEMBER/COLLABORATOR comment.

Run standalone: python3 template/scripts/test_pending_marker_authorization.py

These are prose/jinja skill files read by an agent, not executable code, so
there is no runtime behaviour in them to exercise directly. This test pulls
the exact jq `select(...)` predicate out of queue-sweep's own source and runs
it with the real `jq` binary against fixture GitHub-comment JSON spanning
every author_association value, so a disjunction silently appended to the
filter (e.g. `or true`) is caught by its effect on real input, not just by
whether the filter text still contains an expected substring.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _skill_file(skill_dir: Path) -> Path:
    """The one SKILL.md (or SKILL.md.jinja, pre-render) a skill is read from.

    Mirrors check_skills_lock.py's own resolution: this test file ships into
    every generated project via template/scripts/, where Copier has already
    stripped the .jinja suffix, so it must find the skill under either name.
    """
    for candidate in (skill_dir / "SKILL.md.jinja", skill_dir / "SKILL.md"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"no SKILL.md or SKILL.md.jinja under {skill_dir}")


QUEUE_SWEEP = _skill_file(ROOT / ".agents" / "skills" / "queue-sweep")
POST_MERGE_REVIEW = _skill_file(ROOT / ".agents" / "skills" / "post-merge-review")

ASSOCIATIONS_ALLOWED = ("OWNER", "MEMBER", "COLLABORATOR")
ASSOCIATIONS_DENIED = ("CONTRIBUTOR", "NONE")


def _balanced_parens(text: str, open_idx: int) -> str:
    """Text inside the parens opened at `open_idx` (`text[open_idx]` must be
    `"("`), respecting nesting, so extraction isn't cut at the first `)`."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    raise ValueError(f"unbalanced parens starting at index {open_idx}")


def _select_predicate(text: str, anchor: str) -> str:
    """The exact predicate inside the `select(...)` call that starts at
    `anchor`, pulled from the live source rather than hand-copied, so a
    later edit to the real filter is what this test runs through `jq`."""
    anchor_idx = text.index(anchor)
    select_idx = text.index("select(", anchor_idx)
    open_idx = select_idx + len("select")
    return _balanced_parens(text, open_idx)


def _run_jq_select(predicate: str, comments: list[dict]) -> list[dict]:
    program = f".[] | select({predicate})"
    result = subprocess.run(
        ["jq", "-c", program],
        input=json.dumps(comments),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise AssertionError(f"jq failed on {program!r}: {result.stderr}")
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def _comment(author_association: str, body: str) -> dict:
    return {"author_association": author_association, "body": body}


@unittest.skipUnless(shutil.which("jq"), "jq is not installed in this environment")
class PendingNotesAndEvidenceMarkersRequireAnAuthorizedCommenter(unittest.TestCase):
    def test_watermark_pending_note_query_filters_by_author_association(self) -> None:
        text = QUEUE_SWEEP.read_text(encoding="utf-8")
        predicate = _select_predicate(text, "jq -c '.[] | select(")
        comments = [
            _comment(assoc, f"<!-- pending-post-merge-review pr={n} -->")
            for n, assoc in enumerate(ASSOCIATIONS_ALLOWED + ASSOCIATIONS_DENIED, start=1)
        ]
        accepted = {c["author_association"] for c in _run_jq_select(predicate, comments)}
        self.assertEqual(
            accepted,
            set(ASSOCIATIONS_ALLOWED),
            "check 11(a)'s pending-note/archive jq filter must accept exactly "
            "OWNER/MEMBER/COLLABORATOR and reject every other author_association "
            f"(extracted predicate: {predicate!r})",
        )

    def test_local_full_suite_evidence_query_filters_by_author_association(self) -> None:
        text = QUEUE_SWEEP.read_text(encoding="utf-8")
        predicate = _select_predicate(
            text, 'select((.body | test("<!-- local-full-suite-evidence sha='
        )
        marker_body = (
            "<!-- local-full-suite-evidence sha=abc123 "
            "finished=2026-01-01T00:00:00Z aggregate=pass -->"
        )
        comments = [_comment(assoc, marker_body) for assoc in ASSOCIATIONS_ALLOWED + ASSOCIATIONS_DENIED]
        accepted = {c["author_association"] for c in _run_jq_select(predicate, comments)}
        self.assertEqual(
            accepted,
            set(ASSOCIATIONS_ALLOWED),
            "check 11(b)'s evidence-marker jq filter must accept exactly "
            "OWNER/MEMBER/COLLABORATOR when the marker body matches "
            f"(extracted predicate: {predicate!r})",
        )
        # The filter is an AND of the author check and the marker-body test:
        # an authorized commenter's unrelated comment must not count either.
        unrelated = [_comment("OWNER", "unrelated comment, no marker")]
        self.assertEqual(
            _run_jq_select(predicate, unrelated),
            [],
            "an authorized commenter's non-marker comment must not pass the "
            "body-test half of the filter",
        )

    def test_queue_sweep_explains_why_untrusted_markers_are_ignored(self) -> None:
        text = QUEUE_SWEEP.read_text(encoding="utf-8")
        self.assertIn(
            "does not count, pending or archive",
            text,
            "queue-sweep should explain that neither a pending-note nor an "
            "archive marker from an unauthorized commenter counts",
        )
        self.assertIn(
            "does not count:",
            text,
            "queue-sweep should explain that a local-full-suite-evidence marker "
            "from an unauthorized commenter does not count",
        )

    def test_post_merge_review_states_the_author_association_rule(self) -> None:
        text = POST_MERGE_REVIEW.read_text(encoding="utf-8")
        self.assertIn(
            "author_association",
            text,
            "post-merge-review's Pending reviews section must state the "
            "author_association trust rule",
        )
        self.assertIn("OWNER", text)
        self.assertIn("MEMBER", text)
        self.assertIn("COLLABORATOR", text)
        self.assertIn(
            "Trust a pending note only when",
            text,
            "post-merge-review must say explicitly that an untrusted pending "
            "note is not trusted",
        )


if __name__ == "__main__":
    sys.exit(unittest.main())
