"""Guard test: a project's own local-full-suite stand-in name, publish
switch and commit-status prefix must render consistently everywhere the
template mentions them, with no leftover default literal once a project
overrides them.

Standalone: python3 scripts/test_local_full_suite_answers.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_env import clean_git_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# The two markers are a fixed protocol (queue-sweep,
# test_pending_marker_authorization.py), never a per-project value, so a
# whole-tree scan allowlists them rather than treating them as a leak.
ALLOWED_LITERALS = (
    "<!-- local-full-suite-evidence sha=",
    "<!-- local-full-suite-script-missing -->",
)

OVERRIDDEN_SCRIPT = "scripts/other-suite.sh"
OVERRIDDEN_PUBLISH_VAR = "OTHER_PUBLISH"
DEFAULT_SCRIPT = "scripts/local-full-suite.sh"
DEFAULT_PUBLISH_VAR = "LOCAL_FULL_SUITE_PUBLISH"
DEFAULT_STATUS_LITERALS = ("local-full-suite/", "`local-full-suite`")


def _render(dest: Path, *extra_data: str) -> None:
    try:
        import copier  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise unittest.SkipTest("copier is not installed in this environment") from exc

    data_args: list[str] = []
    for item in extra_data:
        data_args += ["--data", item]
    subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--trust",
            "--defaults",
            "--skip-tasks",
            "--vcs-ref",
            "HEAD",
            "--data",
            "project_name=Generic Co Billing",
            "--data",
            "repo_owner=example-org",
            *data_args,
            str(ROOT),
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=clean_git_env(),
    )


def _strip_allowed(text: str) -> str:
    for literal in ALLOWED_LITERALS:
        text = text.replace(literal, "")
    return text


def _rendered_text_files(dest: Path):
    for path in dest.rglob("*"):
        if not path.is_file():
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # a binary asset, not a place this literal could hide


class DefaultRenderKeepsTodaysNames(unittest.TestCase):
    def test_default_answers_render_todays_script_and_publish_var(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "rendered"
            _render(dest)
            skill = dest / ".agents" / "skills" / "watch-main-ci" / "SKILL.md"
            self.assertIn(DEFAULT_SCRIPT, skill.read_text(encoding="utf-8"))
            self.assertIn(DEFAULT_PUBLISH_VAR, skill.read_text(encoding="utf-8"))


class OverriddenAnswersLeaveNoDefaultLiteral(unittest.TestCase):
    """The guard test: reintroducing any hardcoded default literal anywhere
    in the render must make this go red."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dest = Path(cls._tmp.name) / "rendered"
        try:
            _render(
                cls.dest,
                f"local_full_suite_script={OVERRIDDEN_SCRIPT}",
                f"local_full_suite_publish_var={OVERRIDDEN_PUBLISH_VAR}",
            )
        except unittest.SkipTest:
            cls._tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_an_overridden_stand_in_leaves_no_default_literal_anywhere(self) -> None:
        for path, text in _rendered_text_files(self.dest):
            text = _strip_allowed(text)
            rel = path.relative_to(self.dest)
            self.assertNotIn(DEFAULT_SCRIPT, text, f"{rel}: default script literal must not survive an override")
            self.assertNotIn(
                DEFAULT_PUBLISH_VAR, text, f"{rel}: default publish-var literal must not survive an override"
            )
            for literal in DEFAULT_STATUS_LITERALS:
                self.assertNotIn(
                    literal, text, f"{rel}: default commit-status prefix must not survive an override"
                )

    def test_an_overridden_stand_in_renders_its_own_names(self) -> None:
        skill = self.dest / ".agents" / "skills" / "watch-main-ci" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn(OVERRIDDEN_SCRIPT, text)
        self.assertIn(OVERRIDDEN_PUBLISH_VAR, text)
        self.assertIn("other-suite/<step>", text)


if __name__ == "__main__":
    unittest.main()
