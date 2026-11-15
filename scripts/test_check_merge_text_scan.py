"""Guard tests for check-merge-text.sh's own scanning and identity-masking
logic -- the parts test_check_denylist.py's empty-denylist preflight tests
don't reach, since they return before any `gh api` call.

A fake `gh` on PATH stands in for the real CLI, so these tests need no
network access or authentication; it serves canned title/body/commit/identity
text instead of a real PR's.

Standalone, standard-library-only:

    python3 scripts/test_check_merge_text_scan.py
"""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from _check_merge_text_harness import (
    CLEAN_BODY,
    DEFAULT_COMMITS,
    REF2,
    _FAKE_CURL_TWO_PAGES,
    _FAKE_GREP_NO_DASH_P,
    _UTF8_LOCALE,
    _extract_function,
    _files_select_predicate,
    run_check_merge_text,
)
from _git_env import clean_git_env


def _upstream_repo_with_release(root: Path, release_notes: str, tag: str) -> tuple[str, str, str]:
    """A throwaway upstream git repo with an initial empty commit (`old`) and
    a second commit (`new`, tagged `tag`) that adds `docs/release-notes.md`
    at repo root -- the local stand-in for the clone
    check-merge-text.sh's own integrator-steps guard reads. Returns
    (repo_path, old_sha, new_sha)."""
    repo = root / "upstream-repo"
    repo.mkdir()
    env = clean_git_env()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, env=env, check=True)
    (repo / "README.md").write_text("placeholder\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "old"], cwd=repo, env=env, check=True)
    old_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()
    (repo / "docs").mkdir()
    (repo / "docs" / "release-notes.md").write_text(release_notes)
    subprocess.run(["git", "add", "-A"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "new"], cwd=repo, env=env, check=True)
    new_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(["git", "tag", tag], cwd=repo, env=env, check=True)
    return str(repo), old_sha, new_sha


def _upstream_repo(root: Path, old_doc: str, new_doc: str) -> tuple[str, str, str]:
    """A throwaway upstream git repo with two commits, each setting
    template/docs/software-development-lifecycle.md -- the local stand-in
    for `_src_path` that check-merge-text.sh's own `git clone`/`git show`
    reads from. Returns (repo_path, old_sha, new_sha)."""
    repo = root / "upstream-repo"
    repo.mkdir()
    env = clean_git_env()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, env=env, check=True)
    doc = repo / "template" / "docs" / "software-development-lifecycle.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(old_doc)
    subprocess.run(["git", "add", "-A"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "old"], cwd=repo, env=env, check=True)
    old_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()
    doc.write_text(new_doc)
    subprocess.run(["git", "add", "-A"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "new"], cwd=repo, env=env, check=True)
    new_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()
    return str(repo), old_sha, new_sha


class ChecksMergeTextScan(unittest.TestCase):
    """The guard test: removing any of check-merge-text.sh's own scan calls
    (title, body, commits, identities) or its identity masking must go red here."""

    def test_clean_pr_text_passes(self) -> None:
        result = run_check_merge_text()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_denylisted_term_in_the_title_fails(self) -> None:
        result = run_check_merge_text(title="Ship QuuxCorp-Zylotrex support")
        self.assertNotEqual(result.returncode, 0)

    def test_a_denylisted_term_in_the_body_fails(self) -> None:
        result = run_check_merge_text(body="Uses QuuxCorp-Zylotrex internally.\n")
        self.assertNotEqual(result.returncode, 0)

    def test_a_denylisted_term_in_a_commit_message_fails(self) -> None:
        commits = [{**DEFAULT_COMMITS[0], "message": "mentions QuuxCorp-Zylotrex\n"}]
        result = run_check_merge_text(commits=commits)
        self.assertNotEqual(result.returncode, 0)

    def test_a_denylisted_term_in_a_co_authored_by_trailer_fails(self) -> None:
        commits = [
            {
                **DEFAULT_COMMITS[0],
                "message": "A commit.\n\nCo-authored-by: QuuxCorp-Zylotrex <dev@example.com>\n",
            }
        ]
        result = run_check_merge_text(commits=commits)
        self.assertNotEqual(result.returncode, 0)

    def test_a_non_no_reply_commit_identity_fails(self) -> None:
        """check-commit-identities.sh's own check, invoked as part of this
        script -- a personal address in the identities file must still fail
        the overall merge-text check."""
        commits = [
            {
                "message": "A clean commit message.\n",
                "author_name": "A Person",
                "author_email": "a.person@example.com",
                "committer_name": "A Person",
                "committer_email": "a.person@example.com",
            }
        ]
        result = run_check_merge_text(commits=commits)
        self.assertNotEqual(result.returncode, 0)

    def test_a_self_referential_no_reply_identity_is_masked_and_passes(self) -> None:
        """mask_noreply's own job: a GitHub no-reply identity whose Name
        matches the login its email encodes is masked out of the denylist
        scan entirely, even when that login happens to collide with a
        denylisted term -- it can never itself trigger a false denylist hit."""
        commits = [
            {
                "message": "A clean commit message.\n",
                "author_name": "QuuxCorp-Zylotrex",
                "author_email": "12345+QuuxCorp-Zylotrex@users.noreply.github.com",
                "committer_name": "QuuxCorp-Zylotrex",
                "committer_email": "12345+QuuxCorp-Zylotrex@users.noreply.github.com",
            }
        ]
        result = run_check_merge_text(commits=commits)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_non_self_referential_identity_matching_the_denylist_still_fails(self) -> None:
        """The guard test for the test above: masking is scoped to a
        self-referential no-reply identity, not to any no-reply-shaped
        address -- a mismatched Name/login still gets scanned (and here
        happens to collide with the denylist), proving masking isn't a
        blanket exemption for every no-reply address."""
        commits = [
            {
                "message": "A clean commit message.\n",
                "author_name": "QuuxCorp-Zylotrex",
                "author_email": "12345+someoneelse@users.noreply.github.com",
                "committer_name": "QuuxCorp-Zylotrex",
                "committer_email": "12345+someoneelse@users.noreply.github.com",
            }
        ]
        result = run_check_merge_text(commits=commits)
        self.assertNotEqual(result.returncode, 0)

    def test_a_self_referential_no_reply_identity_without_a_digit_prefix_is_masked_and_passes(
        self,
    ) -> None:
        """GitHub also issues `login@users.noreply.github.com` with no numeric
        ID prefix; github_noreply_login's prefix is optional so that shape is
        masked the same way. Making the prefix mandatory turns this red."""
        commits = [
            {
                "message": "A clean commit message.\n",
                "author_name": "QuuxCorp-Zylotrex",
                "author_email": "QuuxCorp-Zylotrex@users.noreply.github.com",
                "committer_name": "QuuxCorp-Zylotrex",
                "committer_email": "QuuxCorp-Zylotrex@users.noreply.github.com",
            }
        ]
        result = run_check_merge_text(commits=commits)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_non_self_referential_no_digit_no_reply_identity_matching_the_denylist_still_fails(
        self,
    ) -> None:
        """Guard for the test above: a no-digit no-reply address whose Name
        differs from its login is still scanned, not exempted."""
        commits = [
            {
                "message": "A clean commit message.\n",
                "author_name": "QuuxCorp-Zylotrex",
                "author_email": "someoneelse@users.noreply.github.com",
                "committer_name": "QuuxCorp-Zylotrex",
                "committer_email": "someoneelse@users.noreply.github.com",
            }
        ]
        result = run_check_merge_text(commits=commits)
        self.assertNotEqual(result.returncode, 0)

    def test_message_file_scans_that_file_instead_of_the_guessed_squash_text(self) -> None:
        """The PR's own title and body are always scanned independently
        (they land on GitHub regardless of what's merged with); --message-file
        only replaces the *squash* text this script would otherwise guess as
        title-plus-body -- a clean file there still passes even though the
        guessed squash text (title plus body) would itself have been clean
        too, confirming the file's content is what actually gets used."""
        with tempfile.TemporaryDirectory() as tmp_str:
            message_file = Path(tmp_str) / "message.txt"
            message_file.write_text("A clean hand-written merge message.\n")
            result = run_check_merge_text(message_file=message_file)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("hand-written merge message", result.stdout)

    def test_a_denylisted_term_only_in_the_pr_title_still_fails_with_message_file(self) -> None:
        """--message-file governs only the squash text; the real PR title is
        scanned on its own regardless, since it reaches GitHub either way."""
        with tempfile.TemporaryDirectory() as tmp_str:
            message_file = Path(tmp_str) / "message.txt"
            message_file.write_text("A clean hand-written merge message.\n")
            result = run_check_merge_text(
                title="mentions QuuxCorp-Zylotrex",
                message_file=message_file,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_a_denylisted_term_only_in_the_pr_body_still_fails_with_message_file(self) -> None:
        """The guard test for check-merge-text.sh's own scan-piece loop
        (`for piece in title body commits-scanned ...`): with --message-file
        set, the guessed squash text (title plus body) is never built, so
        the body's own independent scan via the loop's "body" piece is the
        *only* thing that can still catch a term living there -- without
        --message-file, the same removal would be masked, since the body
        is also scanned a second time inside the guessed squash text."""
        with tempfile.TemporaryDirectory() as tmp_str:
            message_file = Path(tmp_str) / "message.txt"
            message_file.write_text("A clean hand-written merge message.\n")
            result = run_check_merge_text(
                body="mentions QuuxCorp-Zylotrex\n",
                message_file=message_file,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_message_file_content_is_still_scanned(self) -> None:
        """The guard test for the test above: --message-file must not bypass
        scanning altogether -- a denylisted term inside the given file itself
        still fails."""
        with tempfile.TemporaryDirectory() as tmp_str:
            message_file = Path(tmp_str) / "message.txt"
            message_file.write_text("mentions QuuxCorp-Zylotrex\n")
            result = run_check_merge_text(message_file=message_file)
            self.assertNotEqual(result.returncode, 0)

    def test_a_denylisted_term_in_a_pr_file_content_fails(self) -> None:
        """The guard test for this script's own file-contents scan: a term
        that appears nowhere in the title/body/commits/identities, only
        inside a changed file's content, must still fail the merge."""
        result = run_check_merge_text(pr_files={"docs/notes.md": b"mentions QuuxCorp-Zylotrex\n"})
        self.assertNotEqual(result.returncode, 0)

    def test_a_failed_blob_fetch_for_one_changed_file_fails_the_merge(self) -> None:
        """Guard test: the blob-fetch line that writes each changed file's
        content to disk must stay fail-fast (no `|| true` or similar
        swallowing a lone blob-fetch failure) -- a PR where only ONE of
        several changed files' blob content can't be fetched must abort
        the merge outright, not silently write that file empty/partial and
        scan it as clean."""
        result = run_check_merge_text(
            pr_files={
                "docs/notes.md": b"nothing sensitive here\n",
                "src/other.py": b"print('hello')\n",
            },
            blob_fail_paths=frozenset({"src/other.py"}),
        )
        self.assertNotEqual(result.returncode, 0)

    def test_a_denylisted_term_in_a_pr_file_path_fails(self) -> None:
        """check-denylist.sh's path-string check applies to a PR file's real
        path too, not just its content."""
        result = run_check_merge_text(pr_files={"QuuxCorp-Zylotrex/notes.md": b"nothing sensitive here\n"})
        self.assertNotEqual(result.returncode, 0)

    def test_clean_pr_files_pass(self) -> None:
        result = run_check_merge_text(
            pr_files={"docs/notes.md": b"nothing sensitive here\n", "src/app.py": b"print('hello')\n"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_filename_containing_a_tab_is_not_corrupted(self) -> None:
        """A git tree entry name can legally contain a tab or a newline
        (rare, but real); the filename/blob-sha pairing is NUL-delimited
        specifically so a tab inside a filename can't be misread as the
        field separator and corrupt the pairing. The denylisted term lives
        only in the filename (after the tab), proving it was read as part
        of the filename, not split off as if it were the blob sha."""
        result = run_check_merge_text(pr_files={"docs/notes\tQuuxCorp-Zylotrex.md": b"nothing sensitive here\n"})
        self.assertNotEqual(result.returncode, 0)

    def test_an_allow_listed_term_in_its_named_pr_file_passes(self) -> None:
        """The guard test for the fix found by dry-running this very script
        against its own PR: without honoring the PR's own
        .theforge-denylist-allow, a file that legitimately self-references
        (the same way check-denylist.sh's own header comments do) would
        fail every PR that ever touches it, including this one."""
        result = run_check_merge_text(
            pr_files={"README.md": b"Credits: QuuxCorp-Zylotrex\n"},
            allowlist="README.md:QuuxCorp-Zylotrex\n",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_allow_listed_term_still_fails_in_a_different_pr_file(self) -> None:
        """Scoping, not a blanket exemption: check-denylist.sh's own
        per-file allow-list scoping still applies here."""
        result = run_check_merge_text(
            pr_files={"src/other.py": b"# Credits: QuuxCorp-Zylotrex\n"},
            allowlist="README.md:QuuxCorp-Zylotrex\n",
        )
        self.assertNotEqual(result.returncode, 0)

    def test_a_path_the_ordinary_denylist_hook_never_scans_is_skipped_here_too(self) -> None:
        """NOTICE.md matches .pre-commit-config.yaml's own denylist-hook
        `exclude:` pattern, so the ordinary commit-time hook never scans it
        at all (vendored third-party content and similar deliberately
        out-of-scope paths). Scanning it anyway at merge time would fail
        every PR that ever touches it on a check the normal hook never
        even runs there -- the same shape of bug as the allow-list gap
        above, caught by review rather than by dry-running this time."""
        result = run_check_merge_text(pr_files={"NOTICE.md": b"Credits: QuuxCorp-Zylotrex\n"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_path_not_matching_the_exclude_pattern_still_fails_normally(self) -> None:
        """The guard test for the test above: the exclude pattern is
        specific, not a broad bypass -- an ordinary file in the same PR
        still gets scanned."""
        result = run_check_merge_text(pr_files={"docs/notes.md": b"Credits: QuuxCorp-Zylotrex\n"})
        self.assertNotEqual(result.returncode, 0)

    def test_the_allow_list_never_applies_to_merge_text_itself(self) -> None:
        """The guard test for the other half of the design: a PR's own
        .theforge-denylist-allow must still never grant an exception to the
        title/body/commits/identities scan, which deliberately runs outside
        any git tree -- only the file-contents scan (this PR's own fix) gets
        the allow-list."""
        result = run_check_merge_text(
            title="Ship QuuxCorp-Zylotrex support",
            allowlist="title:QuuxCorp-Zylotrex\n",
        )
        self.assertNotEqual(result.returncode, 0)

    def test_a_binary_pr_file_still_lets_a_clean_pr_pass(self) -> None:
        """A PR adding a binary file (here, bytes including a NUL) with no
        denylisted content must not make an otherwise-clean PR's
        file-contents scan fail or error -- check-denylist.sh's
        `LC_ALL=C grep -niaF` scans it as raw bytes rather than skipping it
        (see check-denylist.sh's own guard tests for that detail), but
        finds nothing to flag here."""
        result = run_check_merge_text(pr_files={"assets/icon.png": b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff\xfe"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_denylisted_term_next_to_a_nul_byte_still_fails(self) -> None:
        """Finding 4 of issue 'check-merge-text.sh: additional fail-open /
        scope gaps': the previous --binary-files=without-match skipped a
        NUL-containing file's content entirely, silently letting a
        denylisted term through right next to the NUL byte. The guard test
        for the fix above: a binary file now content-scanned must still
        catch a denylisted term inside it."""
        result = run_check_merge_text(pr_files={"assets/data.bin": b"\x00QuuxCorp-Zylotrex\n"})
        self.assertNotEqual(result.returncode, 0)

    @unittest.skipUnless(_UTF8_LOCALE, "no UTF-8 locale installed in this environment")
    def test_a_denylisted_term_next_to_invalid_utf8_still_fails(self) -> None:
        """Same finding, the other half: a byte sequence invalid as UTF-8
        (not a NUL byte) must not make grep's own binary heuristic treat
        the file as binary under a UTF-8 locale and skip it either --
        check-denylist.sh's LC_ALL=C avoids that locale-dependent
        misdetection. This sandbox's own ambient locale is POSIX, which
        doesn't reproduce grep's UTF-8-decode-based binary heuristic at
        all regardless of the fix, so the subprocess locale is forced to
        a real UTF-8 one here -- the actual environment this finding is
        about."""
        result = run_check_merge_text(
            pr_files={"docs/notes.md": b"\xff\xfeQuuxCorp-Zylotrex\n"},
            extra_env={"LC_ALL": _UTF8_LOCALE, "LANG": _UTF8_LOCALE},
        )
        self.assertNotEqual(result.returncode, 0)

    def test_a_path_traversal_segment_in_the_pr_files_list_is_refused(self) -> None:
        """Guard test for the path-traversal check: a changed-file path
        carrying a ".." segment must refuse the merge outright rather than
        write outside the scratch directory -- a git tree entry can't
        actually hold one, but pr_file_path is still attacker-influenced
        (any PR author controls their own file list), so this is checked
        explicitly rather than trusted to upstream's own invariant."""
        result = run_check_merge_text(pr_files={"../outside.txt": b"nothing sensitive here\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the repository", result.stdout + result.stderr)

    def test_an_absolute_pr_file_path_is_refused(self) -> None:
        result = run_check_merge_text(pr_files={"/etc/passwd": b"nothing sensitive here\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the repository", result.stdout + result.stderr)

    def test_an_issue_reference_in_the_title_only_warns(self) -> None:
        """check-no-issue-refs.sh runs in --warn mode here (PR text may cite
        this repository's own issues): a reference must not fail the merge,
        but must still be visible in the output for the merger to check."""
        result = run_check_merge_text(title=f"Fix the thing (closes {REF2})")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(REF2, result.stdout + result.stderr)


class FetchedCountsAreValidatedAgainstThePr(unittest.TestCase):
    """Findings 1 and 2 of issue 'check-merge-text.sh: additional fail-open
    / scope gaps': GitHub's /commits and /files listings silently cap at
    250 and 3000 entries respectively, with no further pagination past
    that -- a PR past either cap would otherwise have its remaining
    commits or files never fetched or scanned, with nothing to say so.
    pr_commits_count/pr_changed_files_count simulate exactly that: the PR
    resource reports more than this fixture's fake gh/curl actually serve,
    the same shape a real truncated listing would produce."""

    def test_a_commits_count_mismatch_refuses_the_merge(self) -> None:
        result = run_check_merge_text(pr_commits_count=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PR reports 5", result.stdout + result.stderr)

    def test_a_matching_commits_count_of_more_than_one_still_passes(self) -> None:
        """The guard test for the test above: the check compares actual
        counts, not just "is there a mismatch" on a hardcoded single
        commit -- three real, matching commits must still pass."""
        commits = [
            {**DEFAULT_COMMITS[0], "message": f"Commit {i}.\n"} for i in range(3)
        ]
        result = run_check_merge_text(commits=commits)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_changed_files_count_mismatch_refuses_the_merge(self) -> None:
        result = run_check_merge_text(
            pr_files={"a.py": b"print('hello')\n"}, pr_changed_files_count=5
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PR reports 5", result.stdout + result.stderr)


class ScanIsPinnedToTheHeadCommitItCovered(unittest.TestCase):
    """Finding 5 of the same issue: the scan's success output names the
    exact head commit it covered, so the merge can be pinned to it (e.g.
    `gh pr merge --match-head-commit`) instead of silently merging
    whatever the PR's head happens to be by the time the merge call runs."""

    def test_success_output_names_the_scanned_head_sha(self) -> None:
        result = run_check_merge_text(head_sha="cafef00d")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("cafef00d", result.stdout)
        self.assertIn("match-head-commit", result.stdout)

    def test_head_moving_during_the_scan_itself_is_refused(self) -> None:
        # A force-push between the initial PR fetch (head_sha) and the later
        # commits/files fetches could leave the *reported* head_sha naming a
        # commit whose content was never actually scanned, even though
        # commit/file counts still matched -- a merge-time review finding.
        # drift_head_sha_to simulates exactly that: the gh/REST path answers
        # with a different head.sha on the script's own re-check call.
        result = run_check_merge_text(head_sha="cafef00d", drift_head_sha_to="facefeed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cafef00d", result.stderr + result.stdout)
        self.assertIn("facefeed", result.stderr + result.stdout)

    def test_head_unchanged_across_the_rest_path_s_recheck_still_passes(self) -> None:
        result = run_check_merge_text(head_sha="cafef00d", use_rest=True, require_owner_repo="fake-owner/fake-repo")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class OwnerRepoParsesNonGithubLiteralRemoteForms(unittest.TestCase):
    """Finding 7 of the same issue: owner_repo resolution was limited to
    the literal 'git@github.com:'/'https://github.com/' forms, which
    cancelled the REST-first fix (and its page=N pagination, findings
    3/6) in exactly the non-github.com-remote environments it was meant
    to help. Each test gives the REST and gh-fallback paths *different*
    title data (the same technique RestPathIsTriedBeforeGhApi uses) and
    also pins require_owner_repo to the exact correct value, so a pass
    proves owner_repo resolved to precisely "fake-owner/fake-repo" and
    REST was used -- not merely that some non-empty (possibly garbage)
    string made the script choose the REST branch at all."""

    def test_scp_style_remote_on_a_non_github_host_still_uses_rest(self) -> None:
        result = run_check_merge_text(
            title="Ship QuuxCorp-Zylotrex support",  # gh fallback data; denylisted
            use_rest=True,
            rest_title="A clean PR title",  # REST data; clean
            origin_url="git@mirror.example.com:fake-owner/fake-repo.git",
            require_owner_repo="fake-owner/fake-repo",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ssh_scheme_remote_on_a_non_github_host_still_uses_rest(self) -> None:
        result = run_check_merge_text(
            title="Ship QuuxCorp-Zylotrex support",
            use_rest=True,
            rest_title="A clean PR title",
            origin_url="ssh://git@mirror.example.com/fake-owner/fake-repo.git",
            require_owner_repo="fake-owner/fake-repo",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scp_style_remote_with_no_username_still_uses_rest(self) -> None:
        """Git's scp-like syntax doesn't require a "user@" prefix -- an
        earlier version of this fix required one in its own stripping
        pattern, so a userless remote like this one left "mirror.example.
        com:fake-owner/fake-repo" unstripped, a value non-empty enough to
        choose the REST branch but wrong enough to request the wrong
        path."""
        result = run_check_merge_text(
            title="Ship QuuxCorp-Zylotrex support",
            use_rest=True,
            rest_title="A clean PR title",
            origin_url="mirror.example.com:fake-owner/fake-repo.git",
            require_owner_repo="fake-owner/fake-repo",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ApiGetPaginatedPagesExplicitly(unittest.TestCase):
    """Findings 3 and 6 of the same issue, exercised directly against the
    live api_get_paginated() function body (pulled from the real script,
    not hand-copied -- the same technique _files_select_predicate uses):

    - finding 6: each page is requested by this function's own
      "...&page=N" URL, not by following the response's Link `rel="next"`
      URL -- some proxy-sandbox network policies 403 exactly that URL's
      shape (a numeric repository id), while allowing the owner/repo-path
      URL this function builds itself;
    - finding 3: whether to keep paging is read off the Link header with
      a plain `grep -qi` (no `-P`), so a sandbox whose grep lacks PCRE
      support can't silently stop pagination one page early.

    A fake curl here serves two real pages, each only in response to its
    own exact "&page=N" query parameter, and returns a real
    'Link: <...>; rel="next"' header only on page 1 -- so a pass actually
    proves both the request shape and the termination logic, not just
    that some data came back."""

    def _run(self, grep_shim: str | None = None) -> subprocess.CompletedProcess:
        function_source = _extract_function("api_get_paginated")
        wrapper = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'owner_repo="fake-owner/fake-repo"\n'
            'gh_token="fake-token"\n'
            'json_rest_headers=(-H "Accept: application/vnd.github+json")\n'
            f"{_extract_function('rest_curl')}\n"
            f"{function_source}\n"
            'api_get_paginated "pulls/1/commits"\n'
        )
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            curl = bin_dir / "curl"
            curl.write_text(_FAKE_CURL_TWO_PAGES)
            curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
            if grep_shim is not None:
                grep = bin_dir / "grep"
                grep.write_text(grep_shim)
                grep.chmod(grep.stat().st_mode | stat.S_IEXEC)
            script = tmp / "run.sh"
            script.write_text(wrapper)
            script.chmod(script.stat().st_mode | stat.S_IEXEC)
            return subprocess.run(
                ["bash", str(script)],
                env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
                capture_output=True,
                text=True,
                timeout=10,
            )

    def test_two_pages_are_fetched_via_explicit_page_params_and_pagination_stops(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # jq -s-friendly concatenated JSON: parse back-to-back arrays the
        # same way the real script's own `jq -s` would.
        parsed = subprocess.run(
            ["jq", "-s", "-c", "[.[][]]"], input=result.stdout, capture_output=True, text=True, timeout=10
        )
        self.assertEqual(parsed.returncode, 0, parsed.stderr)
        self.assertEqual(json.loads(parsed.stdout), [{"page": 1}, {"page": 2}])

    def test_pagination_still_works_without_grep_dash_p_support(self) -> None:
        """A grep lacking PCRE support (exits 2 on -P) must not break
        pagination at all -- this function no longer passes -P anywhere,
        so a shim that rejects it is only ever exercised by its fallback
        to the real grep, proving no code path here depends on -P."""
        result = self._run(grep_shim=_FAKE_GREP_NO_DASH_P)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        parsed = subprocess.run(
            ["jq", "-s", "-c", "[.[][]]"], input=result.stdout, capture_output=True, text=True, timeout=10
        )
        self.assertEqual(parsed.returncode, 0, parsed.stderr)
        self.assertEqual(json.loads(parsed.stdout), [{"page": 1}, {"page": 2}])


class RestPathIsTriedBeforeGhApi(unittest.TestCase):
    """Guard tests for issue 'scripts/check-merge-text.sh can't run in some
    cloud sandboxes (gh auth invalid)': when GH_TOKEN is set, the REST API
    (fake curl here) is tried first and its own response is what gets
    scanned -- not merely tolerated alongside gh's. Each test gives the
    REST and gh-fallback paths *different* data, so a pass actually proves
    which one was used, rather than just that the run didn't crash."""

    def test_a_denylisted_term_only_in_the_rest_response_fails(self) -> None:
        """Proves the REST title is the one scanned: gh's own fallback
        title is clean, but the run still fails, so it can only have been
        the REST response that was actually used."""
        result = run_check_merge_text(
            title="A clean PR title",
            use_rest=True,
            rest_title="Ship QuuxCorp-Zylotrex support",
        )
        self.assertNotEqual(result.returncode, 0)

    def test_a_clean_rest_response_passes_even_with_a_denylisted_gh_fallback(self) -> None:
        """The mirror of the test above: gh's own (unused) fallback data is
        denylisted, but the run still passes, proving the REST path's clean
        data is what was actually scanned, not gh's."""
        result = run_check_merge_text(
            title="Ship QuuxCorp-Zylotrex support",
            use_rest=True,
            rest_title="A clean PR title",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rest_commits_and_files_are_the_ones_scanned(self) -> None:
        """Same proof as the title tests above, but for the paginated
        commits and files endpoints: REST-only denylisted content in each
        must still be caught, confirming api_get_paginated's REST branch
        (not just api_get's) is exercised and actually used."""
        rest_commits = [{**DEFAULT_COMMITS[0], "message": "mentions QuuxCorp-Zylotrex\n"}]
        result = run_check_merge_text(use_rest=True, rest_commits=rest_commits)
        self.assertNotEqual(result.returncode, 0)

        result = run_check_merge_text(
            use_rest=True,
            rest_pr_files={"notes.md": b"mentions QuuxCorp-Zylotrex\n"},
        )
        self.assertNotEqual(result.returncode, 0)

    def test_a_rest_failure_falls_back_to_gh_and_still_scans_correctly(self) -> None:
        """rest_fails=True makes the fake curl fail outright on every call
        (the scenario this ticket is about: the REST path is unusable for
        some reason). The real check-merge-text.sh must fall back to
        `gh api` and still produce a correct scan -- a denylisted term in
        the gh fallback data is still caught, and a clean PR still passes."""
        result = run_check_merge_text(
            title="Ship QuuxCorp-Zylotrex support", use_rest=True, rest_fails=True
        )
        self.assertNotEqual(result.returncode, 0)

        result = run_check_merge_text(use_rest=True, rest_fails=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rest_allow_list_fetch_is_honored(self) -> None:
        """The allow-list fetch (api_get_raw_file) is a third, separately
        pattern-matched REST endpoint from api_get/api_get_paginated's --
        a regression here (e.g. a path-matching bug in the REST branch
        specific to this endpoint shape) would otherwise show up only as
        a false denylist failure on a real PR, the exact failure mode the
        allow-list exists to prevent."""
        result = run_check_merge_text(
            use_rest=True,
            allowlist="notes.md:QuuxCorp-Zylotrex\n",
            pr_files={"notes.md": b"mentions QuuxCorp-Zylotrex\n"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_no_token_never_tries_rest_at_all(self) -> None:
        """With no GH_TOKEN/GITHUB_TOKEN (the default in every other test in
        this file), the REST path must not even be attempted -- a clean run
        succeeds on the fake gh fixture data alone, which this test's fake
        curl (installed on PATH, but never set up with any response data)
        would not itself supply if it were invoked."""
        result = run_check_merge_text()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_total_failure_aborts_with_no_scan_result(self) -> None:
        """The policy this ticket exists for: when neither the REST path
        nor the `gh api` fallback can produce a scan at all, the script
        must abort outright rather than silently continue to a "clean"
        result (CLAUDE.md, "TheForge stays project-neutral" check 3 --
        no manual-scan fallback). Nothing less than both paths failing
        proves this: test_a_rest_failure_falls_back_to_gh_and_still_scans_
        correctly above already proves a single-path failure still scans
        correctly via the other path."""
        result = run_check_merge_text(use_rest=True, rest_fails=True, gh_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("clean", result.stdout)


@unittest.skipUnless(shutil.which("jq"), "jq is not installed in this environment")
class FilesEndpointFilterExcludesRemovedFiles(unittest.TestCase):
    """Runs check-merge-text.sh's own `select(.status != "removed")`
    predicate, pulled from its live source, in isolation through the real
    `jq` binary: a direct guard on that exact predicate text, so a typo or
    a weakening of it (e.g. dropping the `!=` or the status check
    entirely) is caught here even though every fake-`gh` fixture above
    only ever supplies "modified" files and so never exercises the
    "removed" branch itself."""

    def test_a_removed_file_is_filtered_out(self) -> None:
        predicate = _files_select_predicate()
        files = [
            {"filename": "kept.py", "sha": "sha1", "status": "modified"},
            {"filename": "gone.py", "sha": "sha2", "status": "removed"},
            {"filename": "renamed.py", "sha": "sha3", "status": "renamed"},
        ]
        result = subprocess.run(
            ["jq", "-c", f".[] | select({predicate})"],
            input=json.dumps(files),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        kept_filenames = {json.loads(line)["filename"] for line in result.stdout.splitlines() if line}
        self.assertEqual(kept_filenames, {"kept.py", "renamed.py"})


PAGINATED_FAKE_CURL = """#!/usr/bin/env bash
set -euo pipefail
url=""
hdrfile=""
expect=""
for arg in "$@"; do
  if [ -n "$expect" ]; then
    case "$expect" in
      hdrfile) hdrfile="$arg" ;;
    esac
    expect=""
    continue
  fi
  case "$arg" in
    -D) expect=hdrfile; continue ;;
    -H) expect=header; continue ;;
    -*) continue ;;
    *) url="$arg" ;;
  esac
done
[ -z "$hdrfile" ] || : > "$hdrfile"
case "$url" in
  *'page=2'*)
    if [ "${FAKE_CURL_FAIL_PAGE2:-0}" = "1" ]; then
      echo "fake curl: simulated page-2 REST failure" >&2
      exit 22
    fi
    printf '%s' "${FAKE_CURL_PAGE2_BODY:-[]}"
    ;;
  *)
    if [ -n "${FAKE_CURL_PAGE2_BODY:-}" ] || [ "${FAKE_CURL_FAIL_PAGE2:-0}" = "1" ]; then
      if [ -n "$hdrfile" ]; then
        printf 'Link: <%s&page=2>; rel="next"' "$url" > "$hdrfile"
      fi
    fi
    printf '%s' "${FAKE_CURL_PAGE1_BODY:-[]}"
    ;;
esac
"""

# Stands in for `gh`'s `api ... --paginate` fallback call in the harness below.
# Requires `--paginate` among its arguments, since a fake that answered without it would hide that call silently returning only page one.
PAGINATED_FAKE_GH = """#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do
  if [ "$arg" = "--paginate" ]; then
    printf '%s' "${FAKE_GH_PAGINATE_BODY:-[]}"
    exit 0
  fi
done
echo "PAGINATED_FAKE_GH: called without --paginate: $*" >&2
exit 1
"""


def _run_api_get_paginated(
    *,
    page1_body: str,
    page2_body: str | None = None,
    fail_page2: bool = False,
    gh_paginate_body: str | None = None,
) -> subprocess.CompletedProcess:
    """Runs check-merge-text.sh's own api_get_paginated() function in
    isolation (extracted from the live source via _extract_function),
    against a minimal fake curl/gh pair, to test its own
    pagination/buffering/fallback behaviour directly. The full-script
    harness above (run_check_merge_text) can't observe this: its tempdir
    is removed before a caller could inspect it, and a clean multi-page
    run with no failure produces the same final output whether or not
    the pages were buffered along the way."""
    function_src = _extract_function("api_get_paginated")
    script = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'owner_repo="fake-owner/fake-repo"',
            'gh_token="fake-token"',
            'json_rest_headers=(-H "Accept: application/vnd.github+json" '
            '-H "X-GitHub-Api-Version: 2022-11-28")',
            _extract_function("rest_curl"),
            function_src,
            'api_get_paginated "pulls/999999/commits"',
        ]
    )
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        curl = bin_dir / "curl"
        curl.write_text(PAGINATED_FAKE_CURL)
        curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
        gh = bin_dir / "gh"
        gh.write_text(PAGINATED_FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        script_path = tmp / "harness.sh"
        script_path.write_text(script)
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
        env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "FAKE_CURL_PAGE1_BODY": page1_body}
        if page2_body is not None:
            env["FAKE_CURL_PAGE2_BODY"] = page2_body
        if fail_page2:
            env["FAKE_CURL_FAIL_PAGE2"] = "1"
        if gh_paginate_body is not None:
            env["FAKE_GH_PAGINATE_BODY"] = gh_paginate_body
        return subprocess.run(
            [str(script_path)], env=env, capture_output=True, text=True, timeout=10
        )


class BearerTokenStaysOutOfCurlArgv(unittest.TestCase):
    """The token must reach curl on stdin (-K -), never as an argv `-H`."""

    def test_token_is_in_stdin_config_and_not_in_any_curl_argument(self) -> None:
        wrapper = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'owner_repo="fake-owner/fake-repo"',
                'gh_token="tok_SECRET123"',
                'json_rest_headers=(-H "Accept: application/vnd.github+json")',
                _extract_function("rest_curl"),
                _extract_function("api_get"),
                'api_get "pulls/1"',
            ]
        )
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            curl = bin_dir / "curl"
            curl.write_text(
                '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$LOG_ARGV"\ncat > "$LOG_STDIN"\necho \'{}\'\n'
            )
            curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
            script = tmp / "run.sh"
            script.write_text(wrapper)
            result = subprocess.run(
                ["bash", str(script)],
                env={
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "LOG_ARGV": str(tmp / "argv"),
                    "LOG_STDIN": str(tmp / "stdin"),
                },
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("tok_SECRET123", (tmp / "argv").read_text())
            self.assertIn("Bearer tok_SECRET123", (tmp / "stdin").read_text())

    def test_a_token_that_could_break_the_curl_config_line_is_refused(self) -> None:
        for token, expected in (("ghp_abc-123.x", 0), ('a"b', 1), ("a\\b", 1), ("a\nb", 1), ("a b", 1), ("", 0)):
            with self.subTest(token=token):
                script = "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        _extract_function("token_is_curl_safe"),
                        'token_is_curl_safe "$TOKEN"',
                    ]
                )
                result = subprocess.run(
                    ["bash", "-c", script], env={"TOKEN": token, "PATH": "/usr/bin:/bin"}, capture_output=True
                )
                self.assertEqual(result.returncode, expected)


class UnsafeTokenDisablesRestAtTheTopLevel(unittest.TestCase):
    """BearerTokenStaysOutOfCurlArgv above only tests token_is_curl_safe as a
    predicate in isolation; this runs the real script end-to-end with an
    unsafe GH_TOKEN and proves the top-level `if ! token_is_curl_safe ...`
    gate actually routes every api_get/api_get_paginated/api_get_raw_file
    call to `gh api` -- curl is never invoked at all, not attempted and
    then fallen back from."""

    def test_an_unsafe_token_never_reaches_curl_and_the_scan_still_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            curl_log = Path(tmp_str) / "curl-log"
            result = run_check_merge_text(
                use_rest=True,
                extra_env={"GH_TOKEN": 'tok"unsafe', "FAKE_CURL_LOG": str(curl_log)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("token has characters unsafe for the curl config; using 'gh api' only.", result.stderr)
            self.assertFalse(curl_log.exists(), curl_log.read_text() if curl_log.exists() else "")


class ApiGetPaginatedBuffersAndFallsBackWithoutDuplication(unittest.TestCase):
    """Runs check-merge-text.sh's own api_get_paginated() function
    directly, covering what the full-script harness above can't observe:
    whether every Link-header page actually gets followed (rather than
    stopping after page 1), and whether a mid-pagination REST failure
    falls back to a full `gh api --paginate` re-fetch without first
    having printed -- and so duplicated -- the page(s) that already
    succeeded before the failure."""

    def test_pagination_follows_the_link_header_to_a_second_page(self) -> None:
        result = _run_api_get_paginated(page1_body='[{"id":1}]', page2_body='[{"id":2}]')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, '[{"id":1}][{"id":2}]')

    def test_a_mid_pagination_failure_falls_back_to_a_full_regetch_without_duplicating_the_first_page(
        self,
    ) -> None:
        """If a mid-pagination REST failure didn't fall back at all (this
        ticket's guard #2), the output would be empty or just page 1's
        body, never the gh fallback's own data. If page 1 had already
        been printed as it arrived instead of buffered (guard #3), the
        output would be page 1's body *plus* the gh fallback's full
        re-fetch, which already includes an equivalent of page 1 itself.
        Either bug changes this exact-equality assertion; only a
        buffered, whole-fallback implementation produces exactly the gh
        fallback's own body, with nothing prepended."""
        result = _run_api_get_paginated(
            page1_body='[{"id":1}]',
            fail_page2=True,
            gh_paginate_body='[{"id":1},{"id":2}]',
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, '[{"id":1},{"id":2}]')


class RunsTheReviewGuardsAtTheMerge(unittest.TestCase):
    """check-merge-text.sh runs the PR-time review guards; removing any call must go red here."""

    def test_a_pr_with_no_review_field_is_refused(self) -> None:
        result = run_check_merge_text(body="No review field here.\n", pr_files={"README.md": b"x"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("review-gate guard failed", result.stderr)

    def test_a_light_gate_claim_on_a_code_file_is_refused(self) -> None:
        body = (
            "Review: Standards: n/a (light gate: prose only). Spec: n/a (light gate: prose only). "
            "Self-review: builder's own, build-tier - checked.\n"
        )
        result = run_check_merge_text(body=body, pr_files={"scripts/x.py": b"x = 1\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("review-gate guard failed", result.stderr)

    def test_a_light_gate_claim_on_a_plain_doc_passes(self) -> None:
        body = (
            "Review: Standards: n/a (light gate: prose only). Spec: n/a (light gate: prose only). "
            "Self-review: builder's own, build-tier - checked.\n"
        )
        result = run_check_merge_text(body=body, pr_files={"docs/notes.md": b"hello\n"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_failed_contents_fetch_for_a_guard_refuses_loudly(self) -> None:
        # .copier-answers.yml, not the lifecycle doc, is the trigger now --
        # its own fetch is what fails here, with no FAKE_GH_CONTENTS_DIR set.
        result = run_check_merge_text(pr_files={".copier-answers.yml": b"x\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not fetch", result.stderr)

    def test_the_guards_no_op_when_the_answers_file_is_unchanged_across_the_sync(self) -> None:
        # Same _commit at both refs: not a sync, so neither guard has
        # anything to verify, even though .copier-answers.yml is (somehow)
        # in the PR's file list.
        with tempfile.TemporaryDirectory() as tmp:
            for ref in ("basesha", "deadbeef"):
                d = Path(tmp) / ref
                d.mkdir(parents=True)
                (d / ".copier-answers.yml").write_text("_commit: v1.0.0\n")
            result = run_check_merge_text(
                pr_files={".copier-answers.yml": b"x\n"},
                extra_env={"FAKE_GH_CONTENTS_DIR": tmp},
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_trust_record_guard_runs_when_the_answers_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for ref, commit in (("basesha", "v1.0.0"), ("deadbeef", "v1.1.0")):
                d = Path(tmp) / ref
                d.mkdir(parents=True)
                (d / ".copier-answers.yml").write_text(f"_commit: {commit}\n")
            result = run_check_merge_text(
                body=CLEAN_BODY.replace("A clean PR body.", "Trust diff: v1.0.0..v1.1.0 changed: scripts/x.py"),
                pr_files={".copier-answers.yml": b"x\n"},
                extra_env={"FAKE_GH_CONTENTS_DIR": tmp},
            )
        self.assertIn("forge-sync trust record guard", result.stderr + result.stdout)

    def test_an_unheld_sdlc_wording_change_in_a_sync_pr_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            upstream_path, old_sha, new_sha = _upstream_repo(
                Path(tmp),
                "- **SDLC-001**: a.\n",
                "- **SDLC-001**: b.\n",
            )
            for ref, commit in (("basesha", old_sha), ("deadbeef", new_sha)):
                d = Path(tmp) / ref
                d.mkdir(parents=True)
                (d / ".copier-answers.yml").write_text(
                    f"_commit: {commit}\n_src_path: '{upstream_path}'\n"
                )
                doc_dir = d / "docs"
                doc_dir.mkdir()
                (doc_dir / "software-development-lifecycle.md").write_text(f"- **SDLC-001**: {commit}.\n")
            result = run_check_merge_text(
                body=CLEAN_BODY.replace(
                    "A clean PR body.", f"Trust diff: {old_sha}..{new_sha} clean"
                ),
                pr_files={".copier-answers.yml": b"x\n"},
                extra_env={"FAKE_GH_CONTENTS_DIR": tmp},
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SDLC wording hold guard failed", result.stderr)

    def test_an_upstream_change_the_lifecycle_doc_never_shows_in_the_file_list_is_still_caught(self) -> None:
        # The exact regression this fix targets: the project's own
        # lifecycle doc is not itself in the PR's changed-file list (it
        # never appears in pr_files below), but upstream changed a
        # statement between the two _commits and the project's own doc
        # let the new wording through unreverted. A file-list-gated
        # trigger would see nothing to check here; the .copier-answers.yml
        # trigger still catches it.
        with tempfile.TemporaryDirectory() as tmp:
            old_text = "- **SDLC-001**: Old wording.\n"
            new_text = "- **SDLC-001**: New wording that slipped through.\n"
            upstream_path, old_sha, new_sha = _upstream_repo(Path(tmp), old_text, new_text)
            for ref, commit, doc_text in (("basesha", old_sha, old_text), ("deadbeef", new_sha, new_text)):
                d = Path(tmp) / ref
                d.mkdir(parents=True)
                (d / ".copier-answers.yml").write_text(
                    f"_commit: {commit}\n_src_path: '{upstream_path}'\n"
                )
                doc_dir = d / "docs"
                doc_dir.mkdir()
                (doc_dir / "software-development-lifecycle.md").write_text(doc_text)
            result = run_check_merge_text(
                body=CLEAN_BODY.replace(
                    "A clean PR body.", f"Trust diff: {old_sha}..{new_sha} clean"
                ),
                pr_files={".copier-answers.yml": b"x\n"},  # the doc itself is NOT in this list
                extra_env={"FAKE_GH_CONTENTS_DIR": tmp},
            )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SDLC wording hold guard failed", result.stderr)

    def test_a_missing_base_sha_refuses_rather_than_fetching_the_default_branch(self) -> None:
        result = run_check_merge_text(
            base_sha="", pr_files={".copier-answers.yml": b"x\n"}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("names no commit", result.stderr)

    def test_an_unaddressed_integrator_step_in_a_sync_pr_is_refused(self) -> None:
        release_notes = (
            "# Release notes\n\n"
            "## v1.0.0 (2026-01-01)\n\n"
            "A release.\n\n"
            "### For integrators\n\n"
            "**Breaking changes: none**\n\n"
            "- Create the `example` label before the next commit. (#1)\n\n"
            "Plus 0 internal changes.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            upstream_path, old_sha, new_sha = _upstream_repo_with_release(Path(tmp), release_notes, "v1.0.0")
            for ref, commit in (("basesha", old_sha), ("deadbeef", new_sha)):
                d = Path(tmp) / ref
                d.mkdir(parents=True)
                (d / ".copier-answers.yml").write_text(f"_commit: {commit}\n_src_path: '{upstream_path}'\n")
            result = run_check_merge_text(
                body=CLEAN_BODY.replace(
                    "A clean PR body.",
                    f"Trust diff: {old_sha}..{new_sha} clean\n"
                    f"SDLC upstream changes: {old_sha}..{new_sha} held: none; current: none\n"
                    "SDLC wording held: none",
                ),
                pr_files={".copier-answers.yml": b"x\n"},
                extra_env={"FAKE_GH_CONTENTS_DIR": tmp},
            )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("integrator steps guard failed", result.stderr)

    def test_an_addressed_integrator_step_in_a_sync_pr_passes(self) -> None:
        release_notes = (
            "# Release notes\n\n"
            "## v1.0.0 (2026-01-01)\n\n"
            "A release.\n\n"
            "### For integrators\n\n"
            "**Breaking changes: none**\n\n"
            "- Create the `example` label before the next commit. (#1)\n\n"
            "Plus 0 internal changes.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            upstream_path, old_sha, new_sha = _upstream_repo_with_release(Path(tmp), release_notes, "v1.0.0")
            for ref, commit in (("basesha", old_sha), ("deadbeef", new_sha)):
                d = Path(tmp) / ref
                d.mkdir(parents=True)
                (d / ".copier-answers.yml").write_text(f"_commit: {commit}\n_src_path: '{upstream_path}'\n")
            body = CLEAN_BODY.replace(
                "A clean PR body.",
                f"Trust diff: {old_sha}..{new_sha} clean\n"
                f"SDLC upstream changes: {old_sha}..{new_sha} held: none; current: none\n"
                "SDLC wording held: none\n"
                f"Integrator steps: {old_sha}..{new_sha} 1: 1\n#1: created the label.",
            )
            result = run_check_merge_text(
                body=body,
                pr_files={".copier-answers.yml": b"x\n"},
                extra_env={"FAKE_GH_CONTENTS_DIR": tmp},
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
