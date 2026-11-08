"""Guard tests for check-denylist.sh and check-merge-text.sh's empty-denylist,
self-scan, and per-file allow-list scoping behaviour.

Standalone, standard-library-only:

    python3 scripts/test_check_denylist.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_env import clean_git_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHECK_DENYLIST = ROOT / "scripts" / "check-denylist.sh"
CHECK_MERGE_TEXT = ROOT / "scripts" / "check-merge-text.sh"
DENYLIST_PATH_SH = ROOT / "scripts" / "denylist-path.sh"


def _init_scratch_repo(tmp: str) -> Path:
    """check-denylist.sh's allow-list path is resolved via `git rev-parse
    --show-toplevel`, not an env var, so testing allow-list scoping needs its
    own throwaway git repo rather than a bare temp directory."""
    repo = Path(tmp) / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=clean_git_env())
    return repo


def _make_fake_repo_with_its_own_scripts(tmp: str, committed_term: str) -> Path:
    """A self-contained copy of check-denylist.sh + denylist-path.sh, with its
    own committed .theforge-denylist naming `committed_term`, structured
    exactly like this repository (scripts/ one level below the denylist).
    Shared by the tier-3-resolution tests and the override-union tests below,
    both of which need this same fake-repo shape."""
    fake_repo = Path(tmp) / "fake-repo"
    (fake_repo / "scripts").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=fake_repo, check=True, env=clean_git_env())
    shutil.copy2(CHECK_DENYLIST, fake_repo / "scripts" / "check-denylist.sh")
    shutil.copy2(DENYLIST_PATH_SH, fake_repo / "scripts" / "denylist-path.sh")
    (fake_repo / "scripts" / "check-denylist.sh").chmod(0o755)
    (fake_repo / ".theforge-denylist").write_text(f"{committed_term}\n")
    return fake_repo


class EmptyDenylistFailsClosed(unittest.TestCase):
    """The guard test: letting an empty-but-present denylist exit 0 again must go red here."""

    def test_check_denylist_refuses_an_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty-denylist"
            empty.write_text("# just a header, no terms\n")
            target = Path(tmp) / "some-file.txt"
            target.write_text("nothing sensitive here\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(empty), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, "an empty-but-present denylist must not exit 0")

    def test_check_denylist_refuses_an_explicit_override_pointing_at_nothing(self):
        """A typo'd or stale THEFORGE_DENYLIST_FILE must fail, not silently
        exit 0 as though no denylist were available at all -- that silent
        rc=0 is exactly the gap this guards against."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            target = Path(tmp) / "some-file.txt"
            target.write_text("nothing sensitive here\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(missing), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not exist", result.stdout + result.stderr)

    def test_check_merge_text_refuses_an_empty_denylist_before_any_api_call(self):
        """Exits 1 on the empty-denylist check alone; a fake, unauthenticated PR number never
        reaches a gh call, since that check runs first in the script."""
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty-denylist"
            empty.write_text("# just a header, no terms\n")
            result = subprocess.run(
                [str(CHECK_MERGE_TEXT), "999999"],
                env={"THEFORGE_DENYLIST_FILE": str(empty), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("has no terms", result.stdout + result.stderr)


class DenylistHookNeverScansItsOwnFile(unittest.TestCase):
    """The guard test: dropping .theforge-denylist from the hook's exclude must go red here."""

    def test_pre_commit_skips_the_denylist_file_itself(self):
        if subprocess.run(["which", "pre-commit"], capture_output=True).returncode != 0:
            self.skipTest("pre-commit is not installed in this environment")
        result = subprocess.run(
            ["pre-commit", "run", "denylist", "--files", ".theforge-denylist"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"the denylist hook must skip .theforge-denylist itself, not scan it against its own terms:\n{result.stdout}\n{result.stderr}",
        )

    def test_check_denylist_sh_would_otherwise_flag_a_planted_term_against_itself(self):
        """Confirms the hazard the exclude guards against is real: invoking the script directly
        (bypassing the exclude) on a file that contains one of its own listed terms does fail,
        which is exactly why the pre-commit exclude -- not reliance on the script alone -- is
        the fix: a self-scan is a tautology, not a check."""
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "planted-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            self_file = Path(tmp) / ".theforge-denylist"
            self_file.write_text("QuuxCorp-Zylotrex\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(self_file)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_check_denylist_sh_never_prints_the_matched_line_content(self):
        """A hit is reported by file:line only -- never the line itself, which would repeat the
        very term the hook exists to keep out of its own output."""
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "planted-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            target = Path(tmp) / "some-file.txt"
            target.write_text("this line names QuuxCorp-Zylotrex directly\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("QuuxCorp-Zylotrex", result.stdout + result.stderr)
            self.assertNotIn("this line names", result.stdout + result.stderr)


class AllowlistScopesToTheNamedFileOnly(unittest.TestCase):
    """The guard test: an allow-list entry leaking past its own named file, in
    either direction, must go red here."""

    def test_allowed_term_passes_in_its_named_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_scratch_repo(tmp)
            denylist = repo / "scratch-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            (repo / ".theforge-denylist-allow").write_text("README.md:QuuxCorp-Zylotrex\n")
            target = repo / "README.md"
            target.write_text("Credits: QuuxCorp-Zylotrex\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), "README.md"],
                cwd=repo,
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_allowed_term_still_fails_in_a_different_file(self):
        """Scoping, not a blanket exemption: the same term in a file the allow-list
        does not name for it is still refused -- this is what keeps template/ and
        every other file strict even once an allow-list entry exists somewhere."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_scratch_repo(tmp)
            denylist = repo / "scratch-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            (repo / ".theforge-denylist-allow").write_text("README.md:QuuxCorp-Zylotrex\n")
            (repo / "template").mkdir()
            target = repo / "template" / "some-doc.md"
            target.write_text("Credits: QuuxCorp-Zylotrex\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), "template/some-doc.md"],
                cwd=repo,
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_override_file_replaces_the_working_trees_allow_list(self):
        """THEFORGE_DENYLIST_ALLOW_FILE (set by check-merge-text.sh to the PR's
        base-commit list) wins over the tree's own file: an entry only in the
        tree's copy must not clear the hit."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_scratch_repo(tmp)
            denylist = repo / "scratch-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            (repo / ".theforge-denylist-allow").write_text("README.md:QuuxCorp-Zylotrex\n")
            override = Path(tmp) / "base-allow"
            override.write_text("# nothing allowed\n")
            (repo / "README.md").write_text("Credits: QuuxCorp-Zylotrex\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), "README.md"],
                cwd=repo,
                env={
                    "THEFORGE_DENYLIST_FILE": str(denylist),
                    "THEFORGE_DENYLIST_ALLOW_FILE": str(override),
                    "PATH": "/usr/bin:/bin",
                },
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_allow_list_does_not_apply_outside_any_git_repository(self):
        """This is exactly check-merge-text.sh's own scan directory: a scratch
        directory with no .git anywhere above it. An allow-list entry that would
        clear this same path inside a repository (the previous test) must not
        clear it here, which is what makes merge text get the strict,
        zero-allowance scan with no self-reference exception."""
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside-any-repo"
            outside.mkdir()
            denylist = outside / "scratch-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            (outside / ".theforge-denylist-allow").write_text("title:QuuxCorp-Zylotrex\n")
            target = outside / "title"
            target.write_text("Credits: QuuxCorp-Zylotrex\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), "title"],
                cwd=outside,
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                "an allow-list sitting outside any git repository must not be found or honoured",
            )


class MissingCommittedDenylistFailsOnlyInTheForgeStaging(unittest.TestCase):
    """A committed .theforge-denylist that's been deleted or renamed must fail
    specifically in forger88/TheForgeStaging (which commits a real one), but
    still skip cleanly for a checkout with no reason to carry it at all --
    e.g. a contributor working on the public TheForge template."""

    def _fake_repo(self, tmp: str, remote_url: str | None) -> Path:
        fake_repo = Path(tmp) / "fake-repo"
        (fake_repo / "scripts").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=fake_repo, check=True, env=clean_git_env())
        if remote_url:
            subprocess.run(
                ["git", "remote", "add", "origin", remote_url],
                cwd=fake_repo,
                check=True,
                env=clean_git_env(),
            )
        shutil.copy2(CHECK_DENYLIST, fake_repo / "scripts" / "check-denylist.sh")
        shutil.copy2(DENYLIST_PATH_SH, fake_repo / "scripts" / "denylist-path.sh")
        (fake_repo / "scripts" / "check-denylist.sh").chmod(0o755)
        # No .theforge-denylist written: the committed file is absent.
        return fake_repo

    def test_fails_when_the_remote_names_theforgestaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_repo = self._fake_repo(tmp, "https://github.com/forger88/TheForgeStaging.git")
            empty_home = Path(tmp) / "empty-home"
            empty_home.mkdir()
            target = fake_repo / "some-file.txt"
            target.write_text("nothing sensitive here\n")
            result = subprocess.run(
                [str(fake_repo / "scripts" / "check-denylist.sh"), str(target)],
                cwd=fake_repo,
                env={"HOME": str(empty_home), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                f"a missing committed denylist in TheForgeStaging must fail:\n{result.stdout}{result.stderr}",
            )

    def test_still_skips_cleanly_with_no_theforgestaging_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_repo = self._fake_repo(tmp, "https://github.com/someone-else/some-fork.git")
            empty_home = Path(tmp) / "empty-home"
            empty_home.mkdir()
            target = fake_repo / "some-file.txt"
            target.write_text("nothing sensitive here\n")
            result = subprocess.run(
                [str(fake_repo / "scripts" / "check-denylist.sh"), str(target)],
                cwd=fake_repo,
                env={"HOME": str(empty_home), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class PathStringsAreScannedTooNotJustContents(unittest.TestCase):
    """CLAUDE.md's project-neutrality rule names file and directory names
    explicitly; a denylisted term in a path must fail even when the file's
    own contents are clean."""

    def test_a_denylisted_term_in_the_filename_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "planted-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            target = Path(tmp) / "QuuxCorp-Zylotrex-notes.txt"
            target.write_text("nothing sensitive in the body\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("the path", result.stdout + result.stderr)

    def test_a_denylisted_term_in_a_directory_segment_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "planted-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            (Path(tmp) / "QuuxCorp-Zylotrex").mkdir()
            target = Path(tmp) / "QuuxCorp-Zylotrex" / "notes.txt"
            target.write_text("nothing sensitive in the body\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_a_clean_path_with_clean_contents_still_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "planted-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            target = Path(tmp) / "some-file.txt"
            target.write_text("nothing sensitive here\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class DenylistPathResolvesToTheScriptsOwnRepoNotTheCallersCwd(unittest.TestCase):
    """Tier 3 of denylist-path.sh (no env var, no ~/.theforge-denylist) must
    resolve relative to where denylist-path.sh itself lives, not to the
    caller's current directory: a back-port session often runs from a
    checkout of a different repository, which has its own git root and no
    reason to carry this repository's denylist."""

    def test_tier_3_finds_the_scripts_own_denylist_from_a_different_repos_cwd(self):
        sentinel = "zz-sentinel-term-only-the-fake-repos-denylist-names"
        with tempfile.TemporaryDirectory() as tmp:
            fake_repo = _make_fake_repo_with_its_own_scripts(tmp, sentinel)

            other_repo = Path(tmp) / "other-repo"
            other_repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=other_repo, check=True, env=clean_git_env())

            empty_home = Path(tmp) / "empty-home"
            empty_home.mkdir()

            target = other_repo / "some-file.txt"
            target.write_text(f"this line names {sentinel}\n")

            result = subprocess.run(
                [str(fake_repo / "scripts" / "check-denylist.sh"), str(target)],
                cwd=other_repo,
                env={"HOME": str(empty_home), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                "running from a different repository's checkout must still scan "
                f"against the fake repo's own denylist, not skip cleanly:\n{result.stdout}{result.stderr}",
            )


class OverrideUnionsWithCommittedDenylistNotReplacingIt(unittest.TestCase):
    """A post-merge review finding: an active override (tier 1/2) must not silently drop
    the owner's own committed terms -- both sets are checked together now,
    not one replacing the other (ADR-0005, amended)."""

    def test_override_term_is_still_caught(self):
        """The override's own term is caught, as before the fix."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_repo = _make_fake_repo_with_its_own_scripts(tmp, "zz-committed-term-owner-standing")
            home = Path(tmp) / "home"
            home.mkdir()
            override = Path(tmp) / "override-denylist"
            override.write_text("zz-override-term-source-project\n")
            target = fake_repo / "some-file.txt"
            target.write_text("this line names zz-override-term-source-project\n")
            result = subprocess.run(
                [str(fake_repo / "scripts" / "check-denylist.sh"), str(target)],
                cwd=fake_repo,
                env={"THEFORGE_DENYLIST_FILE": str(override), "HOME": str(home), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_committed_term_is_still_caught_even_with_an_override_active(self):
        """This is the gap a post-merge review run found: before this fix, an active override
        dropped the committed terms entirely. The committed term must still
        be caught while the override is active."""
        with tempfile.TemporaryDirectory() as tmp:
            committed_term = "zz-committed-term-owner-standing"
            fake_repo = _make_fake_repo_with_its_own_scripts(tmp, committed_term)
            home = Path(tmp) / "home"
            home.mkdir()
            override = Path(tmp) / "override-denylist"
            override.write_text("zz-override-term-source-project\n")
            target = fake_repo / "some-file.txt"
            target.write_text(f"this line names {committed_term}\n")
            result = subprocess.run(
                [str(fake_repo / "scripts" / "check-denylist.sh"), str(target)],
                cwd=fake_repo,
                env={"THEFORGE_DENYLIST_FILE": str(override), "HOME": str(home), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                "an active override must not drop the committed denylist's own terms",
            )

    def test_a_clean_line_still_passes_with_both_lists_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_repo = _make_fake_repo_with_its_own_scripts(tmp, "zz-committed-term-owner-standing")
            home = Path(tmp) / "home"
            home.mkdir()
            override = Path(tmp) / "override-denylist"
            override.write_text("zz-override-term-source-project\n")
            target = fake_repo / "some-file.txt"
            target.write_text("nothing sensitive here\n")
            result = subprocess.run(
                [str(fake_repo / "scripts" / "check-denylist.sh"), str(target)],
                cwd=fake_repo,
                env={"THEFORGE_DENYLIST_FILE": str(override), "HOME": str(home), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_stale_home_override_also_unions_with_committed(self):
        """A stale ~/.theforge-denylist left over from a prior back-port
        (tier 2) must likewise not drop the committed terms on an ordinary,
        later commit that never meant to override anything."""
        with tempfile.TemporaryDirectory() as tmp:
            committed_term = "zz-committed-term-owner-standing"
            fake_repo = _make_fake_repo_with_its_own_scripts(tmp, committed_term)
            home = Path(tmp) / "home"
            home.mkdir()
            (home / ".theforge-denylist").write_text("zz-stale-override-term\n")
            target = fake_repo / "some-file.txt"
            target.write_text(f"this line names {committed_term}\n")
            result = subprocess.run(
                [str(fake_repo / "scripts" / "check-denylist.sh"), str(target)],
                cwd=fake_repo,
                env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                "a stale ~/.theforge-denylist must still union with the committed denylist",
            )


def _utf8_locale_available() -> str | None:
    """The first installed locale (per `locale -a`) that looks like a
    UTF-8 one, or None if this environment has none -- used to skip the
    one test that needs a real UTF-8 locale to prove Unicode case
    folding survives this hook's content scan, rather than hand-assuming
    a specific locale name is installed everywhere this suite runs."""
    try:
        result = subprocess.run(["locale", "-a"], capture_output=True, text=True, timeout=10)
    except OSError:
        return None
    for line in result.stdout.splitlines():
        if "utf8" in line.lower() or "utf-8" in line.lower():
            return line.strip()
    return None


_UTF8_LOCALE = _utf8_locale_available() or ""


class BinaryFilesAreContentScannedLikeAnyOtherFile(unittest.TestCase):
    """`grep -niaF` (issue "check-merge-text.sh: additional fail-open /
    scope gaps", finding 4) scans a binary file's content as raw bytes
    rather than skipping it on grep's own binary heuristic, so a clean
    binary file still passes (nothing to flag), and a denylisted term in
    its content fails the same as in any text file -- see
    test_check_merge_text_scan.py's own NUL-byte and invalid-UTF-8 guard
    tests for the "still catches a hit" half of this, exercised through
    check-merge-text.sh's own PR-file-contents scan. Deliberately -a
    alone, not LC_ALL=C too: see test_unicode_case_folding_still_works_
    for_valid_utf8_content below for why forcing the locale is wrong."""

    def test_a_clean_binary_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            target = Path(tmp) / "icon.png"
            target.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff\xfe")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_denylisted_term_in_the_binary_file_s_path_still_fails(self):
        """The path-string check is independent of the content-grep flag --
        a denylisted term in a binary file's own name must still be caught
        regardless of what its content scan finds."""
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            target = Path(tmp) / "QuuxCorp-Zylotrex.png"
            target.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff\xfe")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_a_denylisted_term_in_a_nul_containing_file_s_content_fails(self):
        """The guard test for the fix itself, direct against this hook
        rather than through check-merge-text.sh's wrapper: a NUL byte
        elsewhere in the file must not stop the term after it from being
        caught -- the old --binary-files=without-match skipped this
        file's content entirely."""
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            target = Path(tmp) / "data.bin"
            target.write_bytes(b"\x00QuuxCorp-Zylotrex\n")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    @unittest.skipUnless(_UTF8_LOCALE, "no UTF-8 locale installed in this environment")
    def test_unicode_case_folding_still_works_for_valid_utf8_content(self):
        """The regression this fix must not reintroduce: forcing LC_ALL=C
        alongside -a (an earlier version of this fix) makes -i fold only
        ASCII case, so a denylisted term with a non-ASCII letter (here,
        "ÉclairCache") would stop matching a differently-cased variant
        ("eclaircache" cased as "éclaircache") in otherwise-valid UTF-8
        content -- -a alone, with the ambient locale left in place
        (BinaryFilesAreContentScannedLikeAnyOtherFile above), keeps
        Unicode-aware case folding working."""
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("ÉclairCache\n", encoding="utf-8")
            target = Path(tmp) / "notes.md"
            target.write_text("mentions éclaircache here\n", encoding="utf-8")
            result = subprocess.run(
                [str(CHECK_DENYLIST), str(target)],
                env={
                    "THEFORGE_DENYLIST_FILE": str(denylist),
                    "PATH": "/usr/bin:/bin",
                    "LC_ALL": _UTF8_LOCALE,
                    "LANG": _UTF8_LOCALE,
                },
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


class DenylistEncodingLocaleAndReadErrorGaps(unittest.TestCase):
    """UTF-16/32 content, ambient-locale case folding and grep errors are never read as clean."""

    def _run(self, target: Path, denylist: Path, env_extra=None, path="/usr/bin:/bin"):
        env = {"THEFORGE_DENYLIST_FILE": str(denylist), "PATH": path}
        env.update(env_extra or {})
        return subprocess.run(
            [str(CHECK_DENYLIST), str(target)], env=env, capture_output=True, text=True
        )

    def test_term_in_non_ascii_compatible_encodings_is_caught(self):
        for codec in ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-be"):
            with self.subTest(codec=codec), tempfile.TemporaryDirectory() as tmp:
                denylist = Path(tmp) / "denylist"
                denylist.write_text("secretterm\n")
                target = Path(tmp) / "notes.txt"
                target.write_bytes("first\nmentions SecretTerm here\n".encode(codec))
                result = self._run(target, denylist)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("notes.txt:2", result.stderr)
                self.assertNotIn("secretterm", result.stderr.lower().replace("denylisted term", ""))

    def test_clean_utf16_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("secretterm\n")
            target = Path(tmp) / "notes.txt"
            target.write_bytes("nothing to see\n".encode("utf-16"))
            self.assertEqual(self._run(target, denylist).returncode, 0)

    def test_non_ascii_case_folding_ignores_the_ambient_locale(self):
        for locale in ("C", "POSIX"):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as tmp:
                denylist = Path(tmp) / "denylist"
                denylist.write_text("ÉxampleTerm\n", encoding="utf-8")
                target = Path(tmp) / "notes.md"
                target.write_text("mentions éxampleterm here\n", encoding="utf-8")
                result = self._run(target, denylist, {"LC_ALL": locale, "LANG": locale})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_a_grep_read_error_is_not_read_as_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("secretterm\n")
            target = Path(tmp) / "notes.txt"
            target.write_text("harmless\n")
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            shim = bin_dir / "grep"
            # Real grep for the denylist/pattern handling; exit 2 only when asked to scan the target.
            shim.write_text(
                '#!/bin/bash\nfor a in "$@"; do case "$a" in *notes.txt) echo "grep: read error" >&2; exit 2;; esac; done\n'
                'exec /usr/bin/grep "$@"\n'
            )
            shim.chmod(0o755)
            result = self._run(target, denylist, path=f"{bin_dir}:/usr/bin:/bin")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("read error", result.stderr)

    def test_utf16_file_with_a_stray_trailing_byte_is_still_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("secretterm\n")
            target = Path(tmp) / "notes.txt"
            target.write_bytes("mentions SecretTerm\n".encode("utf-16-le") + b"\x41")
            result = self._run(target, denylist)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_a_failed_decode_is_not_read_as_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("secretterm\n")
            target = Path(tmp) / "notes.txt"
            target.write_text("harmless\n")
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            shim = bin_dir / "iconv"
            shim.write_text("#!/bin/bash\nexit 4\n")
            shim.chmod(0o755)
            result = self._run(target, denylist, path=f"{bin_dir}:/usr/bin:/bin")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("could not decode", result.stderr)

    def test_a_grep_error_on_the_path_check_is_not_read_as_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "denylist"
            denylist.write_text("secretterm\n")
            target = Path(tmp) / "notes.txt"
            target.write_text("harmless\n")
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            shim = bin_dir / "grep"
            shim.write_text(
                '#!/bin/bash\nfor a in "$@"; do case "$a" in -qiF) exit 2;; esac; done\nexec /usr/bin/grep "$@"\n'
            )
            shim.chmod(0o755)
            result = self._run(target, denylist, path=f"{bin_dir}:/usr/bin:/bin")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("grep error", result.stderr)


if __name__ == "__main__":
    unittest.main()
