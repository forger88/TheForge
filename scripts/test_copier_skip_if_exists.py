"""Guard test: copier.yml's `_skip_if_exists` entries survive `copier update`.

Protects the two paths docs/design/doc-build-setup.md's "Slice 4" names.
Root-only (not shipped under `template/`): see that doc for why.

Standalone: python3 scripts/test_copier_skip_if_exists.py
Skips cleanly when `copier` is not importable in this environment.
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

try:
    import copier  # noqa: F401

    _HAS_COPIER = True
except ImportError:
    _HAS_COPIER = False

import yaml

# The two project-owned paths this slice protects.
PROTECTED_PATHS = ("docs/tools/document-build.json", "docs/development/documentation-build.md")

_GIT_IDENTITY = ["-c", "user.email=guard-test@example.com", "-c", "user.name=guard-test"]


def _real_skip_if_exists() -> list[str]:
    with open(ROOT / "copier.yml") as f:
        data = next(yaml.safe_load_all(f))
    return list(data.get("_skip_if_exists", []))


def _git_commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=clean_git_env())
    subprocess.run(["git", *_GIT_IDENTITY, "commit", "-q", "-m", message], cwd=repo, check=True, env=clean_git_env())


def _write_protected_paths(repo_template_dir: Path, content: str) -> None:
    for rel in PROTECTED_PATHS:
        path = repo_template_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _build_scratch_template(tmp: Path, skip_if_exists: list[str]) -> Path:
    """A throwaway, git-committed Copier template with a stub file at each
    PROTECTED_PATHS entry, so `copier update` has something upstream to try
    overwriting -- unlike the real template, which (by design) ships no file
    at either path yet. Also needs its own copier-answers Jinja seed
    (`template/{{_copier_conf.answers_file}}.jinja`, mirroring this
    repository's real one): without it, Copier writes no `.copier-answers.yml`
    at all, and `copier update` refuses with "only supported in git-tracked
    templates/subprojects"."""
    repo = tmp / "template-src"
    (repo / "template").mkdir(parents=True)
    _write_protected_paths(repo / "template", "UPSTREAM-V1")
    (repo / "template" / "{{_copier_conf.answers_file}}.jinja").write_text(
        "{{ _copier_answers|to_nice_yaml -}}\n"
    )
    skip_lines = "".join(f"  - {p}\n" for p in skip_if_exists)
    (repo / "copier.yml").write_text(
        "_min_copier_version: '9'\n_subdirectory: template\n_skip_if_exists:\n" + skip_lines
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=clean_git_env())
    _git_commit(repo, "v1")
    return repo


def _render_edit_and_update(skip_if_exists: list[str]) -> dict[str, str]:
    """Render a fixture from v1 of a scratch template, locally edit both
    protected paths, bump the scratch template to v2, run `copier update`,
    and return the fixture's resulting content for each path.

    `copier update` requires both the fixture and the template source to be
    git-tracked, and re-resolves `_src_path` at update time, so the source
    passed to `copier copy` must be an absolute path (a relative one, valid
    only from the original cwd, breaks once `copier update` runs from inside
    the fixture directory instead)."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        repo = _build_scratch_template(tmp, skip_if_exists)
        fixture = tmp / "fixture"
        subprocess.run(
            ["copier", "copy", "--trust", "--defaults", str(repo), str(fixture)],
            check=True,
            capture_output=True,
            text=True,
            env=clean_git_env(),
        )
        subprocess.run(["git", "init", "-q"], cwd=fixture, check=True, env=clean_git_env())
        _git_commit(fixture, "initial render")
        for rel in PROTECTED_PATHS:
            (fixture / rel).write_text("LOCAL-EDIT")
        _git_commit(fixture, "local edit")

        _write_protected_paths(repo / "template", "UPSTREAM-V2")
        _git_commit(repo, "v2")

        subprocess.run(
            [
                "copier",
                "update",
                "--trust",
                "--defaults",
                "--skip-tasks",
                "--conflict",
                "inline",
                "--vcs-ref",
                "HEAD",
            ],
            cwd=fixture,
            check=True,
            capture_output=True,
            text=True,
            env=clean_git_env(),
        )
        return {rel: (fixture / rel).read_text() for rel in PROTECTED_PATHS}


@unittest.skipUnless(_HAS_COPIER, "copier is not installed in this environment")
class SkipIfExistsProtectsEachNewPath(unittest.TestCase):
    """The guard test: dropping either path from `_skip_if_exists` must go red here."""

    def test_both_new_paths_are_listed_in_the_real_copier_yml(self) -> None:
        listed = _real_skip_if_exists()
        for rel in PROTECTED_PATHS:
            self.assertIn(rel, listed, f"{rel} must be listed in copier.yml's _skip_if_exists")

    def test_a_local_edit_survives_copier_update_with_both_entries_present(self) -> None:
        results = _render_edit_and_update(skip_if_exists=list(PROTECTED_PATHS))
        for rel, content in results.items():
            self.assertEqual(
                content,
                "LOCAL-EDIT",
                f"{rel}: a locally edited path listed in _skip_if_exists must survive `copier update`",
            )

    def test_a_local_edit_is_overwritten_once_an_entry_is_dropped(self) -> None:
        """Proves the test above is a real check, not a vacuous pass: with a
        path removed from _skip_if_exists, the same local edit to it must NOT
        survive untouched -- if it did regardless, this test (and the
        production `_skip_if_exists` entry it stands in for) would prove
        nothing. A git-tracked fixture with a real upstream/local conflict
        gets inline conflict markers (`--conflict inline`) rather than a
        clean overwrite, so "not protected" is checked as "changed, and the
        new upstream content shows up somewhere in it", not as an exact
        new-content match."""
        results = _render_edit_and_update(skip_if_exists=[PROTECTED_PATHS[1]])
        unprotected = results[PROTECTED_PATHS[0]]
        self.assertNotEqual(
            unprotected,
            "LOCAL-EDIT",
            f"{PROTECTED_PATHS[0]}: dropped from _skip_if_exists, so a local edit is expected to be "
            "touched by `copier update` -- if it survives untouched anyway, this test proves nothing",
        )
        self.assertIn(
            "UPSTREAM-V2",
            unprotected,
            f"{PROTECTED_PATHS[0]}: expected the new upstream content to reach the fixture somehow "
            f"(directly or as a conflict-marker side) once no longer protected; got {unprotected!r}",
        )
        self.assertEqual(
            results[PROTECTED_PATHS[1]],
            "LOCAL-EDIT",
            f"{PROTECTED_PATHS[1]}: still listed in this run's _skip_if_exists, so it must still survive",
        )


if __name__ == "__main__":
    sys.exit(unittest.main())
