"""Executable guard for queue-sweep check 11(a)'s archive-comment
classification: a comment only ever becomes a covering archive record when
it is from an OWNER/MEMBER/COLLABORATOR commenter, never "anything that
isn't a recognized pending-note marker". This guards against a defect
found once before: that trust filter being bypassable by any outside
comment.

test_pending_marker_authorization.py pins that the author-association
filter text is present in the jq source; an edit could keep that exact
string while still letting an untrusted comment's shape slip past it (or a
future edit could reintroduce the "every other comment is an archive"
bug this check once had). This test instead extracts the
actual jq program from the skill and runs it with the real `jq` binary
against a fixture mirroring the GitHub comments API -- including an
outside, non-owner comment -- and checks what the query actually produces,
which a string match cannot.

Run standalone: python3 template/scripts/test_queue_sweep_archive_fixture.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jinja_paths import rendered_or_jinja  # noqa: E402

QUEUE_SWEEP = rendered_or_jinja(".agents", "skills", "queue-sweep", "SKILL.md")


def _extract_jq_program() -> str:
    text = QUEUE_SWEEP.read_text(encoding="utf-8")
    match = re.search(
        r"jq -c '(\.\[\]\s*\|\s*select\(.*?pending_pr:.*?covered:.*?\})'",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(
            "check 11(a)'s pending-note/archive jq program was not found in "
            "queue-sweep -- has its shape changed?"
        )
    return match.group(1)


def _run_jq(program: str, comments: list[dict]) -> list[dict]:
    proc = subprocess.run(
        ["jq", "-c", program],
        input=json.dumps(comments),
        capture_output=True,
        text=True,
        check=True,
    )
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


# Row 3 mirrors the issue's own reproduction (an unmarked outside comment);
# row 4 adds a stronger case the issue's own three-step repro doesn't reach:
# an outside commenter forging the archive marker itself, which only the
# author-association select -- not the marker-vs-elimination fix alone --
# can stop.
FIXTURE = [
    {
        "author_association": "OWNER",
        "created_at": "2026-10-01T00:00:00Z",
        "body": "<!-- post-merge-review-archive covered=41,42 -->\nRun 1 archive.",
    },
    {
        "author_association": "OWNER",
        "created_at": "2026-10-02T00:00:00Z",
        "body": (
            "<!-- pending-post-merge-review pr=7 sha=deadbeef -->\n"
            "Pending post-merge review: PR 7, merged as deadbeef."
        ),
    },
    {
        "author_association": "NONE",
        "created_at": "2026-10-03T00:00:00Z",
        "body": "bumping this thread",
    },
    {
        "author_association": "NONE",
        "created_at": "2026-10-04T00:00:00Z",
        "body": "<!-- post-merge-review-archive covered=7 -->\nForged archive, covering PR 7.",
    },
]


@unittest.skipUnless(shutil.which("jq"), "jq is not installed in this environment")
class ArchiveClassificationIgnoresOutsideComments(unittest.TestCase):
    def test_outside_comments_produce_no_rows_at_all(self) -> None:
        rows = _run_jq(_extract_jq_program(), FIXTURE)

        self.assertEqual(
            len(rows), 2, f"expected only the two OWNER comments to survive the select: {rows}"
        )
        created_ats = {row["created_at"] for row in rows}
        self.assertNotIn(
            "2026-10-03T00:00:00Z",
            created_ats,
            "an outside (author_association=NONE) comment must never reach the "
            "pending_pr/covered capture, however it's worded",
        )
        self.assertNotIn(
            "2026-10-04T00:00:00Z",
            created_ats,
            "an outside comment forging the archive marker itself must never reach "
            "the capture either -- the select must filter on author_association, "
            "not on whether the marker regex happens to match",
        )

    def test_latest_marked_archive_is_not_advanced_by_either_outside_comment(self) -> None:
        """The issue's failure mode: with an outside comment wrongly counted,
        <latest-marked-archive> jumps forward and the real 10-02 pending note
        reads as already swept, silencing the overdue check for good. Confirm
        <latest-marked-archive> stays at the 10-01 OWNER archive instead, even
        though the 10-04 forged comment's `created_at` is later and its body
        matches the covered-marker regex."""
        rows = _run_jq(_extract_jq_program(), FIXTURE)

        marked_archives = [row for row in rows if row.get("covered")]
        self.assertTrue(marked_archives, "the OWNER archive comment must itself survive the select")
        latest_marked_archive = max(marked_archives, key=lambda row: row["created_at"])
        self.assertEqual(
            latest_marked_archive["created_at"],
            "2026-10-01T00:00:00Z",
            "no outside comment -- unmarked or forged -- must ever become "
            "<latest-marked-archive>",
        )

    def test_real_pending_note_is_not_swept_by_a_forged_covered_list(self) -> None:
        rows = _run_jq(_extract_jq_program(), FIXTURE)

        pending_rows = [row for row in rows if row.get("pending_pr")]
        self.assertEqual(len(pending_rows), 1)
        self.assertEqual(pending_rows[0]["pending_pr"], "7")

        covered = {
            pr for row in rows for pr in (row.get("covered") or "").split(",") if pr
        }
        self.assertNotIn(
            "7",
            covered,
            "the real pending note's PR must not read as swept by the outside "
            "commenter's forged covered-list marker",
        )


if __name__ == "__main__":
    sys.exit(unittest.main())
