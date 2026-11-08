"""Guard test: Routine 2's green-push logging distinguishes a platform
refusal and a stale-main skip from an actual script bug, and documents the
recovery.

Run standalone: python3 template/scripts/test_green_push_refusal_recovery.py

watch-main-ci/SKILL.md.jinja is prose an agent reads, not executable code,
so there is no runtime behaviour to exercise directly. This test pins the
specific log-line names and the recovery instructions the prose must carry,
so a later edit that silently collapses them back into "GREEN-PUSH-FAILED
is always a script bug" is caught mechanically.
"""

from __future__ import annotations

import re
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


WATCH_MAIN_CI = _skill_file(ROOT / ".agents" / "skills" / "watch-main-ci")


class GreenPushDistinguishesRefusalFromScriptBug(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WATCH_MAIN_CI.read_text(encoding="utf-8")

    def test_push_is_gated_on_a_freshly_checked_main_head(self) -> None:
        self.assertIn(
            "GREEN-PUSH-SKIPPED-STALE",
            self.text,
            "a stale-main run must skip the green push under its own named "
            "log line, not attempt (and maybe fail) the push",
        )
        # "origin/main" alone is too weak: it already appears elsewhere in this
        # file (the Cadence skip-check, the handover section) for unrelated
        # reasons, so it stays present even if the fresh re-check itself is
        # deleted. Anchor to the specific re-check sentence instead.
        self.assertRegex(
            self.text,
            re.compile(
                r"re-checks that the run's sha is still `origin/main`'s current head"
            ),
            "the push gate must re-check the current origin/main head, not "
            "reuse the sha read when the run started",
        )

    def test_platform_refusal_is_logged_separately_from_a_script_bug(self) -> None:
        self.assertIn(
            "GREEN-PUSH-REFUSED",
            self.text,
            "a remote-side push rejection (non-fast-forward, or a platform "
            "policy like GH007) must be logged under its own name, not as "
            "GREEN-PUSH-FAILED",
        )
        self.assertIn(
            "GREEN-PUSH-FAILED",
            self.text,
            "a genuine script-side push failure must still be named and "
            "still treated as a bug to investigate",
        )
        # The two must be told apart in the handling prose, not merged. Match
        # within the sentence that introduces the log line, not a fixed
        # character window, so wording changes elsewhere can't break this.
        self.assertRegex(
            self.text,
            re.compile(r"`GREEN-PUSH-REFUSED`[^.]*\bnever a script bug\b"),
            "GREEN-PUSH-REFUSED must be explicitly carved out of the "
            "'treat as a script bug' instruction that covers GREEN-PUSH-FAILED",
        )

    def test_recovery_procedure_is_documented(self) -> None:
        self.assertIn(
            "Recovery when the green push is refused",
            self.text,
            "the skill must document how to recover a stuck green ref, not "
            "just name the symptom",
        )
        self.assertIn("delete", self.text.lower())
        self.assertIn("create-ref", self.text)
        self.assertIn(
            'force=false',
            self.text,
            "the documented REST ref-update fallback must specify "
            "force=false, matching the plain push's fast-forward-only "
            "semantics",
        )

    def test_recovery_is_escalated_to_the_owner_not_done_unilaterally(self) -> None:
        self.assertIn(
            "**Recovery when the green push is refused.**",
            self.text,
            "the recovery section must be its own heading",
        )
        # Anchored to the specific instruction, not a character window, so
        # expanding the explanation elsewhere in the section can't break this.
        self.assertRegex(
            self.text,
            re.compile(r"Report it to the owner\b.*\bdelete `refs/heads/green`"),
            "deleting and recreating a ref is destructive enough that the "
            "skill must route it through the owner, not perform it silently",
        )


if __name__ == "__main__":
    sys.exit(unittest.main())
