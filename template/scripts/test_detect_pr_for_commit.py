"""Guard tests for detect_pr_for_commit.py.

The guard test: removing the merge_commit_sha lookup (classify_commit
falling back to, say, parsing the commit message for a `(#N)` suffix
instead) must go red here, on both of the acceptance-criteria cases this
script was written to cover.

Standalone, standard-library-only: python3 scripts/test_detect_pr_for_commit.py
"""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_pr_for_commit  # noqa: E402

EXAMPLE_REPO = "example-org/widgets"


def _fake_run_gh_json(pulls, commit):
    """Builds a run_gh_json stand-in: routes a `.../pulls` call to `pulls`
    (a list of PR objects, as the real `/commits/{sha}/pulls` endpoint
    returns them) and a plain `.../commits/<sha>` call to `commit` (the
    commit object), the same two calls classify_commit makes -- no real
    `gh` or network needed."""

    def run(args: list[str]):
        path = args[1]
        if path.endswith("/pulls"):
            return pulls
        return commit

    return run


def _pr(number: int, *, merge_commit_sha: str, merged: bool = True) -> dict:
    return {
        "number": number,
        "merge_commit_sha": merge_commit_sha,
        "merged_at": "2026-01-01T00:00:00Z" if merged else None,
    }


def _commit(*, login: str | None, name: str, email: str, sha: str | None = None) -> dict:
    commit = {
        "committer": {"login": login} if login else None,
        "commit": {"committer": {"name": name, "email": email}},
    }
    if sha is not None:
        commit["sha"] = sha
    return commit


class ClassifiesCommitPrStatus(unittest.TestCase):
    def test_a_real_pr_merge_with_a_custom_squash_title_is_not_flagged(self) -> None:
        """A custom squash title with no auto-appended `(#N)` suffix is still
        a real PR merge: the merge_commit_sha lookup finds it regardless, so
        title text is never even consulted."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
            run_gh_json=_fake_run_gh_json(
                [_pr(304, merge_commit_sha="a1b2c3d4e5f60718293a4b5c6d7e8f9012345678")],
                _commit(login="web-flow", name="GitHub", email="noreply@github.com"),
            ),
        )
        self.assertTrue(status.has_pr)
        self.assertFalse(status.flagged)

    def test_an_abbreviated_sha_resolves_to_its_merged_pr(self) -> None:
        """`/commits/{sha}/pulls` accepts an abbreviated sha, but each PR's own
        `merge_commit_sha` is always the full 40 characters: the comparison must
        use the commit's full sha, or every short-sha lookup reads as unresolved."""
        full = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            full[:7],
            run_gh_json=_fake_run_gh_json(
                [_pr(304, merge_commit_sha=full)],
                _commit(login="web-flow", name="GitHub", email="noreply@github.com", sha=full),
            ),
        )
        self.assertEqual(status.pr_numbers, (304,))
        self.assertEqual(status.sha, full)
        self.assertFalse(status.unresolved)

    def test_a_commit_with_no_matching_pr_and_a_non_github_committer_is_flagged(self) -> None:
        """No PR's merge_commit_sha matches, and the committer is an agent's
        own no-reply identity, not GitHub's web-flow merge identity: a
        direct-to-main bypass."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "b2c3d4e5f60718293a4b5c6d7e8f90123456789a",
            run_gh_json=_fake_run_gh_json(
                [],
                _commit(login="an-agent", name="An Agent", email="noreply@example.com"),
            ),
        )
        self.assertFalse(status.has_pr)
        self.assertTrue(status.flagged)

    def test_a_commit_with_no_matching_pr_and_a_human_noreply_committer_is_flagged(self) -> None:
        """A committer's own GitHub no-reply alias is still no-reply-shaped
        and still an accepted commit identity, but it is not GitHub's own
        web-flow merge identity, so this is still a direct-to-main bypass,
        not a merge."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "c3d4e5f60718293a4b5c6d7e8f90123456789ab2",
            run_gh_json=_fake_run_gh_json(
                [],
                _commit(
                    login="a-maintainer",
                    name="a-maintainer",
                    email="99999999+a-maintainer@users.noreply.github.com",
                ),
            ),
        )
        self.assertFalse(status.has_pr)
        self.assertTrue(status.flagged)

    def test_no_matching_pr_but_github_merge_identity_is_unresolved_not_clean(self) -> None:
        """The guard test for the flagging rule itself: absence of a PR match
        alone is not sufficient to flag as a bypass -- only paired with a
        non-GitHub committer. But GitHub's own identity with no PR match is
        not clean either: it's either a lagging API response on a real merge,
        or a web-UI direct-to-main commit, which carries this exact identity
        with no PR of its own to ever appear. Neither case may be folded into
        "clean"; both report as unresolved."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "0000000000000000000000000000000000000000",
            run_gh_json=_fake_run_gh_json(
                [],
                _commit(login="web-flow", name="GitHub", email="noreply@github.com"),
            ),
        )
        self.assertFalse(status.has_pr)
        self.assertFalse(status.flagged)
        self.assertTrue(status.unresolved)

    def test_a_real_pr_merge_is_not_unresolved(self) -> None:
        """Guards the other direction: a confirmed PR match must not also be
        marked unresolved, even though its committer carries the same
        GitHub identity the unresolved case keys off."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "d4e5f60718293a4b5c6d7e8f90123456789ab2c3",
            run_gh_json=_fake_run_gh_json(
                [_pr(304, merge_commit_sha="d4e5f60718293a4b5c6d7e8f90123456789ab2c3")],
                _commit(login="web-flow", name="GitHub", email="noreply@github.com"),
            ),
        )
        self.assertTrue(status.has_pr)
        self.assertFalse(status.flagged)
        self.assertFalse(status.unresolved)

    def test_a_flagged_bypass_is_not_also_unresolved(self) -> None:
        """Guards the third combination: a confirmed non-GitHub-identity
        bypass must report as flagged, not unresolved -- the two are
        mutually exclusive outcomes, not a flagged case that also happens to
        set unresolved."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "e5f60718293a4b5c6d7e8f90123456789ab2c3d4",
            run_gh_json=_fake_run_gh_json(
                [],
                _commit(login="an-agent", name="An Agent", email="noreply@example.com"),
            ),
        )
        self.assertTrue(status.flagged)
        self.assertFalse(status.unresolved)

    def test_an_associated_pr_that_is_open_is_not_proof_of_a_merge(self) -> None:
        """`/commits/{sha}/pulls` returns every PR merely associated with
        the commit, not only the one it's the actual merge of. An open PR
        that happens to share this commit (e.g. the commit also sits on an
        open PR's branch) must not count as `has_pr`."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "f60718293a4b5c6d7e8f90123456789ab2c3d4e5",
            run_gh_json=_fake_run_gh_json(
                [_pr(305, merge_commit_sha="f60718293a4b5c6d7e8f90123456789ab2c3d4e5", merged=False)],
                _commit(login="an-agent", name="An Agent", email="noreply@example.com"),
            ),
        )
        self.assertFalse(status.has_pr)
        self.assertTrue(status.flagged)

    def test_an_associated_pr_merged_into_a_different_commit_is_not_proof_of_a_merge(self) -> None:
        """A merged PR is associated with this commit (e.g. it was once on
        that branch) but its own `merge_commit_sha` points elsewhere: this
        sha is not that PR's merge, so it still isn't proof of a merge."""
        status = detect_pr_for_commit.classify_commit(
            EXAMPLE_REPO,
            "0718293a4b5c6d7e8f90123456789ab2c3d4e5f6",
            run_gh_json=_fake_run_gh_json(
                [_pr(306, merge_commit_sha="ffffffffffffffffffffffffffffffffffffffff", merged=True)],
                _commit(login="an-agent", name="An Agent", email="noreply@example.com"),
            ),
        )
        self.assertFalse(status.has_pr)
        self.assertTrue(status.flagged)

    def test_is_github_merge_identity_checks_login_or_email_independently(self) -> None:
        self.assertTrue(detect_pr_for_commit.is_github_merge_identity("web-flow", "someone@example.com"))
        self.assertTrue(detect_pr_for_commit.is_github_merge_identity(None, "noreply@github.com"))
        self.assertFalse(
            detect_pr_for_commit.is_github_merge_identity("a-maintainer", "a@users.noreply.github.com")
        )
        self.assertFalse(detect_pr_for_commit.is_github_merge_identity(None, None))


def _fake_subprocess_run(pulls_stdout: str, commit_stdout: str):
    """Stands in for subprocess.run itself, one level below run_gh_json, so
    _run_gh_json's own JSON-decoding and `gh` invocation are exercised too."""

    def run(args, **kwargs):
        path = args[2]
        stdout = pulls_stdout if path.endswith("/pulls") else commit_stdout
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    return run


class MainCli(unittest.TestCase):
    def test_main_rejects_wrong_argument_count(self) -> None:
        self.assertEqual(detect_pr_for_commit.main(["only-one-arg"]), 2)
        self.assertEqual(detect_pr_for_commit.main([]), 2)

    def test_main_exits_zero_and_prints_json_for_a_real_pr_merge(self) -> None:
        with mock.patch(
            "subprocess.run",
            side_effect=_fake_subprocess_run(
                '[{"number": 304, "merge_commit_sha": "a1b2c3d", "merged_at": "2026-01-01T00:00:00Z"}]',
                '{"committer": {"login": "web-flow"}, "commit": {"committer": {"email": "noreply@github.com"}}}',
            ),
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = detect_pr_for_commit.main([EXAMPLE_REPO, "a1b2c3d"])
        self.assertEqual(rc, 0)
        self.assertIn('"flagged": false', out.getvalue())

    def test_main_exits_one_for_a_flagged_bypass(self) -> None:
        with mock.patch(
            "subprocess.run",
            side_effect=_fake_subprocess_run(
                "[]", '{"committer": {"login": "an-agent"}, "commit": {"committer": {"email": "noreply@example.com"}}}'
            ),
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = detect_pr_for_commit.main([EXAMPLE_REPO, "b2c3d4e"])
        self.assertEqual(rc, 1)
        self.assertIn('"flagged": true', out.getvalue())

    def test_main_exits_three_for_an_unresolved_web_flow_identity_with_no_pr(self) -> None:
        with mock.patch(
            "subprocess.run",
            side_effect=_fake_subprocess_run(
                "[]", '{"committer": {"login": "web-flow"}, "commit": {"committer": {"email": "noreply@github.com"}}}'
            ),
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = detect_pr_for_commit.main([EXAMPLE_REPO, "0000000000000000000000000000000000000000"])
        self.assertEqual(rc, 3)
        self.assertIn('"unresolved": true', out.getvalue())
        self.assertIn('"flagged": false', out.getvalue())

    def test_main_exits_two_and_reports_a_gh_failure(self) -> None:
        def raise_called_process_error(args, **kwargs):
            raise subprocess.CalledProcessError(1, args, stderr="gh: not authenticated\n")

        with mock.patch("subprocess.run", side_effect=raise_called_process_error):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = detect_pr_for_commit.main([EXAMPLE_REPO, "c3d4e5f"])
        self.assertEqual(rc, 2)
        self.assertIn("gh: not authenticated", err.getvalue())

    def test_main_exits_two_when_gh_binary_is_missing(self) -> None:
        def raise_file_not_found(args, **kwargs):
            raise FileNotFoundError("[Errno 2] No such file or directory: 'gh'")

        with mock.patch("subprocess.run", side_effect=raise_file_not_found):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = detect_pr_for_commit.main([EXAMPLE_REPO, "c3d4e5f"])
        self.assertEqual(rc, 2)
        self.assertIn("could not run gh", err.getvalue())

    def test_main_exits_two_on_non_json_gh_output(self) -> None:
        with mock.patch(
            "subprocess.run",
            side_effect=_fake_subprocess_run("<html>rate limited</html>", "<html>rate limited</html>"),
        ):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = detect_pr_for_commit.main([EXAMPLE_REPO, "c3d4e5f"])
        self.assertEqual(rc, 2)
        self.assertIn("non-JSON", err.getvalue())


if __name__ == "__main__":
    unittest.main()
