"""Guard tests for check_integrator_steps.py, run standalone:
python3 scripts/test_check_integrator_steps.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_integrator_steps as guard  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env())


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


RELEASE_NOTES_V1 = """\
# Release notes

## v1.0.0 (2026-01-01)

A first release.

### Enhancements

None.

### Bug fixes

None.

### Known issues

None.

### For integrators

**Breaking changes: none**

- Create the `example` label before the next commit. (#1)
- Rename the `OLD_VAR` environment variable to `NEW_VAR`. (#2)

Plus 0 internal changes.
"""

RELEASE_NOTES_V2 = (
    RELEASE_NOTES_V1
    + """
## v2.0.0 (2026-02-01)

A second release.

### Enhancements

None.

### Bug fixes

None.

### Known issues

None.

### For integrators

**Breaking changes: none**

- Accept the new `widget_mode` Copier question. (#3)

Plus 0 internal changes.
"""
)

SIDECAR_V2 = """\
{
  "version": "2.0.0",
  "items": [
    {"id": "3", "breaking": false, "summary": "Accept the new widget_mode Copier question."}
  ]
}
"""

RELEASE_NOTES_V3 = """\
# Release notes

## v3.0.0 (2026-03-01)

A third release.

### Enhancements

None.

### Bug fixes

None.

### Known issues

None.

### For integrators

**Breaking changes:**

- A breaking change to the widget API. (#4)
- Another breaking change. (#5)

- A plain bullet citing three issues at once. (#6, #7, #8)

Plus 0 internal changes.
"""


class RepoFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "test@example.com")
        _git(self.repo, "config", "user.name", "Test")

    def commit(self, message: str) -> str:
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", message)
        result = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            env=clean_git_env(),
        )
        return result.stdout.strip()


class TestCollect(RepoFixture):
    def test_no_releases_in_range_is_empty(self) -> None:
        _write(self.repo / "docs/release-notes.md", "# Release notes\n")
        base = self.commit("base")
        self.assertEqual(guard.collect(self.repo, base, base), [])

    def test_fallback_parses_bullets_with_issue_numbers(self) -> None:
        _write(self.repo / "README.md", "placeholder\n")
        base = self.commit("base")
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V1)
        self.commit("v1")
        _git(self.repo, "tag", "v1.0.0")
        items = guard.collect(self.repo, base, "v1.0.0")
        self.assertEqual([item.id for item in items], ["1", "2"])
        self.assertEqual(items[0].version, "1.0.0")
        self.assertIn("example", items[0].summary)

    def test_sidecar_is_preferred_over_fallback(self) -> None:
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V1)
        self.commit("base")
        _git(self.repo, "tag", "v1.0.0")
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V2)
        _write(self.repo / "docs/release-notes/2.0.0.integrator-steps.json", SIDECAR_V2)
        self.commit("v2")
        _git(self.repo, "tag", "v2.0.0")
        items = guard.collect(self.repo, "v1.0.0", "v2.0.0")
        self.assertEqual([item.id for item in items], ["3"])
        self.assertEqual(items[0].summary, "Accept the new widget_mode Copier question.")

    def test_range_spans_multiple_releases_oldest_first(self) -> None:
        _write(self.repo / "README.md", "placeholder\n")
        base = self.commit("base")
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V1)
        self.commit("v1")
        _git(self.repo, "tag", "v1.0.0")
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V2)
        self.commit("v2")
        _git(self.repo, "tag", "v2.0.0")
        items = guard.collect(self.repo, base, "v2.0.0")
        self.assertEqual([item.id for item in items], ["1", "2", "3"])

    def test_sidecar_breaking_and_refs_are_read(self) -> None:
        _write(self.repo / "README.md", "placeholder\n")
        base = self.commit("base")
        _write(self.repo / "docs/release-notes.md", "# Release notes\n")
        _write(
            self.repo / "docs/release-notes/1.0.0.integrator-steps.json",
            '{"version": "1.0.0", "items": [{"id": "40", "breaking": true, '
            '"summary": "Breaking thing.", "refs": ["41", "42"]}]}',
        )
        self.commit("v1")
        _git(self.repo, "tag", "v1.0.0")
        items = guard.collect(self.repo, base, "v1.0.0")
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].breaking)
        self.assertEqual(items[0].refs, ("41", "42"))

    def test_malformed_sidecar_raises(self) -> None:
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V1)
        base = self.commit("base")
        _write(self.repo / "docs/release-notes/1.0.0.integrator-steps.json", "{not json")
        self.commit("bad sidecar")
        _git(self.repo, "tag", "v1.0.0")
        with self.assertRaises(guard.IntegratorStepsError):
            guard.collect(self.repo, base, "v1.0.0")

    def test_fallback_handles_multi_ref_bullets_and_breaking_section(self) -> None:
        _write(self.repo / "README.md", "placeholder\n")
        base = self.commit("base")
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V3)
        self.commit("v3")
        _git(self.repo, "tag", "v3.0.0")
        items = guard.collect(self.repo, base, "v3.0.0")
        self.assertEqual([item.id for item in items], ["4", "5", "6"])
        self.assertTrue(items[0].breaking)
        self.assertTrue(items[1].breaking)
        self.assertFalse(items[2].breaking)
        self.assertEqual(items[2].refs, ("7", "8"))

    def test_unresolvable_revision_raises(self) -> None:
        _write(self.repo / "docs/release-notes.md", "# Release notes\n")
        self.commit("base")
        with self.assertRaises(guard.IntegratorStepsError):
            guard.collect(self.repo, "not-a-real-rev", "HEAD")


class TestCheckPrBody(unittest.TestCase):
    def test_empty_item_list_always_passes(self) -> None:
        self.assertEqual(guard._check_pr_body("anything at all", []), [])

    def test_missing_marker_fails_when_items_exist(self) -> None:
        item = guard.Item(id="3", version="2.0.0", summary="Do the thing.")
        failures = guard._check_pr_body("no marker here", [item])
        self.assertEqual(len(failures), 1)
        self.assertIn("Integrator steps", failures[0])

    def test_item_addressed_after_marker_passes(self) -> None:
        item = guard.Item(id="3", version="2.0.0", summary="Do the thing.")
        body = "Integrator steps: #3 handled by updating config.\n"
        self.assertEqual(guard._check_pr_body(body, [item]), [])

    def test_item_mentioned_before_marker_only_still_fails(self) -> None:
        item = guard.Item(id="3", version="2.0.0", summary="Do the thing.")
        body = "See #3 above.\n\nIntegrator steps: nothing here.\n"
        failures = guard._check_pr_body(body, [item])
        self.assertEqual(len(failures), 1)
        self.assertIn("#3", failures[0])

    def test_two_items_one_missing(self) -> None:
        items = [
            guard.Item(id="3", version="2.0.0", summary="A."),
            guard.Item(id="4", version="2.0.0", summary="B."),
        ]
        body = "Integrator steps: #3 done.\n"
        failures = guard._check_pr_body(body, items)
        self.assertEqual(len(failures), 1)
        self.assertIn("#4", failures[0])


class TestMain(RepoFixture):
    def test_enumerate_mode_exit_code_reflects_item_count(self) -> None:
        _write(self.repo / "docs/release-notes.md", "# Release notes\n")
        base = self.commit("base")
        self.assertEqual(guard.main(["--template", str(self.repo), "--old", base, "--new", base]), 0)

        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V1)
        self.commit("v1")
        _git(self.repo, "tag", "v1.0.0")
        self.assertEqual(guard.main(["--template", str(self.repo), "--old", base, "--new", "v1.0.0"]), 1)

    def test_rejects_flag_like_revision(self) -> None:
        self.assertEqual(guard.main(["--template", str(self.repo), "--old", "--evil", "--new", "HEAD"]), 2)

    def test_pr_body_mode_passes_with_all_items_addressed(self) -> None:
        _write(self.repo / "README.md", "placeholder\n")
        base = self.commit("base")
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V1)
        self.commit("v1")
        _git(self.repo, "tag", "v1.0.0")
        body_file = Path(self.tmp.name) / "body.txt"
        body_file.write_text("Integrator steps: #1 done, #2 done.\n")
        self.assertEqual(
            guard.main(
                [
                    "--template",
                    str(self.repo),
                    "--old",
                    base,
                    "--new",
                    "v1.0.0",
                    "--pr-body",
                    str(body_file),
                ]
            ),
            0,
        )

    def test_pr_body_mode_fails_on_missing_item(self) -> None:
        _write(self.repo / "README.md", "placeholder\n")
        base = self.commit("base")
        _write(self.repo / "docs/release-notes.md", RELEASE_NOTES_V1)
        self.commit("v1")
        _git(self.repo, "tag", "v1.0.0")
        body_file = Path(self.tmp.name) / "body.txt"
        body_file.write_text("Integrator steps: #1 done.\n")
        self.assertEqual(
            guard.main(
                [
                    "--template",
                    str(self.repo),
                    "--old",
                    base,
                    "--new",
                    "v1.0.0",
                    "--pr-body",
                    str(body_file),
                ]
            ),
            1,
        )

    def test_missing_pr_body_file_is_exit_2(self) -> None:
        _write(self.repo / "docs/release-notes.md", "# Release notes\n")
        base = self.commit("base")
        self.assertEqual(
            guard.main(
                [
                    "--template",
                    str(self.repo),
                    "--old",
                    base,
                    "--new",
                    base,
                    "--pr-body",
                    str(Path(self.tmp.name) / "nope.txt"),
                ]
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
