"""Guard test: .theforge-denylist must never ship under template/ or in a render.

Standalone, standard-library-only except for the optional end-to-end render
(see RenderNeverCarriesTheDenylist, which skips cleanly when `copier` is not
importable in this environment -- scripts/check-denylist-not-shipped.sh, the
pre-commit hook, is the always-available layer of this same guard).

    python3 scripts/test_denylist_not_shipped.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_env import clean_git_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHECK_NOT_SHIPPED = ROOT / "scripts" / "check-denylist-not-shipped.sh"


def _init_scratch_template_repo(tmp: str) -> Path:
    """check-denylist-not-shipped.sh resolves its root via `git rev-parse
    --show-toplevel`, not an env var, so testing it needs its own throwaway
    git repo with a template/ dir and a copier.yml, like the real one."""
    repo = Path(tmp) / "repo"
    (repo / "template").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=clean_git_env())
    (repo / "copier.yml").write_text("_min_copier_version: '9'\n")
    (repo / ".theforge-denylist").write_text("QuuxCorp-Zylotrex\n")
    return repo


class StaticTreeNeverShipsTheDenylist(unittest.TestCase):
    """The guard test: letting the file back under template/ must go red here."""

    def test_no_file_named_like_the_denylist_sits_under_template(self):
        hits = list((ROOT / "template").rglob(".theforge-denylist*"))
        self.assertEqual(hits, [], f"must never ship under template/: {hits}")

    def test_copier_yml_never_names_the_denylist(self):
        text = (ROOT / "copier.yml").read_text()
        self.assertNotIn(".theforge-denylist", text, "copier.yml must not reference .theforge-denylist")


class BypassesCaughtByNameAloneAreRefused(unittest.TestCase):
    """The guard tests for the bypasses the filename-only check above misses:
    a Jinja include or an escaping symlink ships the denylist's content under
    template/ with no file ever named like it -- these must catch either."""

    def test_a_jinja_include_of_the_denylist_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_scratch_template_repo(tmp)
            (repo / "template" / "leak.txt.jinja").write_text('{% include ".theforge-denylist" %}\n')
            result = subprocess.run(
                [str(CHECK_NOT_SHIPPED)],
                cwd=repo,
                env=clean_git_env(),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                f"a template/ file referencing .theforge-denylist by name must be refused:\n{result.stdout}{result.stderr}",
            )

    def test_a_symlink_resolving_outside_template_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_scratch_template_repo(tmp)
            (repo / "template" / "terms.txt").symlink_to(Path("..") / ".theforge-denylist")
            result = subprocess.run(
                [str(CHECK_NOT_SHIPPED)],
                cwd=repo,
                env=clean_git_env(),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                f"a template/ symlink resolving outside template/ must be refused:\n{result.stdout}{result.stderr}",
            )

    def test_a_symlink_resolving_inside_template_is_allowed(self):
        """Not every symlink under template/ is a leak vector -- only one that
        escapes the tree. A legitimate same-tree symlink must still pass."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_scratch_template_repo(tmp)
            (repo / "template" / "real.txt").write_text("harmless\n")
            (repo / "template" / "alias.txt").symlink_to(Path("real.txt"))
            result = subprocess.run(
                [str(CHECK_NOT_SHIPPED)],
                cwd=repo,
                env=clean_git_env(),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")


class RenderNeverCarriesTheDenylist(unittest.TestCase):
    """End-to-end: an actual `copier copy` render must not carry the file either."""

    def test_a_fresh_render_has_no_denylist_file(self):
        try:
            import copier  # noqa: F401
        except ImportError:
            self.skipTest("copier is not installed in this environment; see check-denylist-not-shipped.sh")

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "rendered"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "copier",
                    "copy",
                    "--trust",
                    "--defaults",
                    "--skip-tasks",
                    # HEAD, not the default (ref unset): with no ref, Copier wraps a
                    # dirty working tree into a WIP commit and then checks out the
                    # latest tag over it, discarding the change this test exists to
                    # scan -- HEAD is the one other value Copier still treats as
                    # "pick up dirty changes".
                    "--vcs-ref",
                    "HEAD",
                    "--data",
                    "project_name=Generic Co Billing",
                    "--data",
                    "repo_owner=example-org",
                    str(ROOT),
                    str(dest),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=clean_git_env(),
            )
            hits = list(dest.rglob(".theforge-denylist*"))
            self.assertEqual(hits, [], f"a render must never carry the denylist: {hits}")

    def test_a_fresh_render_contains_no_denylist_terms(self):
        """A filename check alone misses a Jinja include or an escaping
        symlink, both of which render the denylist's terms into files with
        ordinary names. This scans rendered *content*, the way check-denylist.sh
        scans a commit's changed files, so either bypass is caught even if a
        future third bypass defeats the name/reference/symlink checks above."""
        try:
            import copier  # noqa: F401
        except ImportError:
            self.skipTest("copier is not installed in this environment; see check-denylist-not-shipped.sh")

        terms = [
            line.strip()
            for line in (ROOT / ".theforge-denylist").read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertTrue(terms, "the real denylist must have at least one term to scan against")
        pattern = re.compile("|".join(re.escape(term) for term in terms), re.IGNORECASE)

        # .theforge-denylist-allow's "template/<path>:<term>" entries name terms that
        # legitimately ship (e.g. the copyright holder in template/NOTICE.md) --
        # mapped to their rendered path the same way _subdirectory/_templates_suffix
        # map it (strip the template/ prefix and a trailing .jinja), since those
        # entries are the only ones this scan's render could ever reach.
        allowed_by_rendered_path: dict[str, set[str]] = {}
        for line in (ROOT / ".theforge-denylist-allow").read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            src_path, term = line.split(":", 1)
            if not src_path.startswith("template/"):
                continue
            rendered_path = src_path[len("template/") :].removesuffix(".jinja")
            allowed_by_rendered_path.setdefault(rendered_path, set()).add(term)

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "rendered"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "copier",
                    "copy",
                    "--trust",
                    "--defaults",
                    "--skip-tasks",
                    # See the --vcs-ref HEAD comment in the sibling test above.
                    "--vcs-ref",
                    "HEAD",
                    "--data",
                    "project_name=Generic Co Billing",
                    "--data",
                    "repo_owner=example-org",
                    str(ROOT),
                    str(dest),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=clean_git_env(),
            )
            hits = []
            for path in dest.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                rel = str(path.relative_to(dest))
                allowed = allowed_by_rendered_path.get(rel, set())
                for term in allowed:
                    text = re.sub(re.escape(term), "", text, flags=re.IGNORECASE)
                if pattern.search(text):
                    hits.append(rel)
            self.assertEqual(hits, [], f"a render must never contain a denylisted term: {hits}")


if __name__ == "__main__":
    unittest.main()
