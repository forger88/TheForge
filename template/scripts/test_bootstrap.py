"""Guard tests for bootstrap.py's token check.

Stage 0 has not yet wired a project test runner into this generated project
(`.forge/feature-pipeline.md`, "Stage 0: project inception (once per repo)"), so this uses only the
standard library and runs standalone:

    python3 scripts/test_bootstrap.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap  # noqa: E402


def _http_error(path: str, code: int, message: str | None = None) -> urllib.error.HTTPError:
    """An HTTPError with a real, readable JSON body, for the cases that read one."""
    fp = io.BytesIO(json.dumps({"message": message}).encode()) if message is not None else None
    return urllib.error.HTTPError(path, code, "error", {}, fp)


class FakeGitHub:
    """A GitHub stand-in that answers only the calls check_token makes."""

    def __init__(
        self,
        token: str,
        oauth_scopes: str = "",
        other_repos: list[tuple[str, bool]] | None = None,
        installation_repos: int = 1,
        has_contents_access: bool = False,
        has_administration_access: bool = False,
        has_secrets_access: bool = False,
        repo_is_empty: bool = False,
        repo_is_public: bool = False,
    ) -> None:
        self.token = token
        self.repo = "owner/repo"
        self._oauth_scopes = oauth_scopes
        self._other_repos = other_repos or []
        self._installation_repos = installation_repos
        self._has_contents_access = has_contents_access
        self._has_administration_access = has_administration_access
        self._has_secrets_access = has_secrets_access
        self._repo_is_empty = repo_is_empty
        self._repo_is_public = repo_is_public

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[object, dict]:
        if path == f"/repos/{self.repo}/contents/":
            if self._repo_is_empty:
                raise _http_error(path, 404, "This repository is empty.")
            if self._has_contents_access:
                return {}, {}
            raise _http_error(path, 403)
        if path == f"/repos/{self.repo}/actions/permissions":
            if self._has_administration_access:
                return {}, {}
            raise _http_error(path, 403)
        if path == f"/repos/{self.repo}/actions/secrets":
            if self._has_secrets_access:
                return {}, {}
            raise _http_error(path, 403)
        if path == f"/repos/{self.repo}":
            headers = {"X-OAuth-Scopes": self._oauth_scopes} if self._oauth_scopes else {}
            return {"private": not self._repo_is_public}, headers
        if path.startswith("/user/repos"):
            # Only the first page: the other repositories sit on later pages (see paged).
            return [{"full_name": "owner/repo", "private": True}], {}
        if path.startswith("/installation/repositories"):
            return {"total_count": self._installation_repos}, {}
        raise AssertionError(f"unexpected call: {method} {path}")

    def paged(self, path: str) -> list:
        """Every page of the listing; a check that reads only the first page (call) misses the other repositories."""
        if not path.startswith("/user/repos"):
            raise AssertionError(f"unexpected paged call: {path}")
        return [{"full_name": "owner/repo", "private": True}] + [
            {"full_name": name, "private": is_private} for name, is_private in self._other_repos
        ]


class CheckTokenDefaultsToRefusing(unittest.TestCase):
    """The guard test: removing the refusal must go red here."""

    def test_classic_token_refused_by_default(self):
        gh = FakeGitHub(token="ghp_classic")
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_oauth_scoped_fine_grained_token_refused_by_default(self):
        gh = FakeGitHub(token="github_pat_x", oauth_scopes="repo")
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_broad_fine_grained_token_refused_by_default(self):
        gh = FakeGitHub(token="github_pat_x", other_repos=[("owner/other-private", True)])
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_fine_grained_token_reaching_a_public_repository_refused_by_default(self):
        gh = FakeGitHub(token="github_pat_x", other_repos=[("owner/other-public", False)])
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_fine_grained_token_with_contents_access_refused_by_default(self):
        gh = FakeGitHub(token="github_pat_x", has_contents_access=True)
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_installation_token_with_contents_access_refused_by_default(self):
        gh = FakeGitHub(token="ghs_x", has_contents_access=True)
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_fine_grained_token_with_administration_access_refused_by_default(self):
        gh = FakeGitHub(token="github_pat_x", has_administration_access=True)
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_fine_grained_token_with_secrets_access_refused_by_default(self):
        gh = FakeGitHub(token="github_pat_x", has_secrets_access=True)
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_scoped_fine_grained_token_passes_by_default(self):
        gh = FakeGitHub(token="github_pat_x")
        bootstrap.check_token(gh, allow_broad=False)  # must not raise

    def test_scoped_fine_grained_token_on_empty_repo_passes_by_default(self):
        """An empty repo's inconclusive Contents probe must not itself cause a refusal."""
        gh = FakeGitHub(token="github_pat_x", repo_is_empty=True)
        bootstrap.check_token(gh, allow_broad=False)  # must not raise

    def test_scoped_fine_grained_token_on_public_repo_passes_by_default(self):
        """A public repo's inconclusive Contents probe must not itself cause a refusal."""
        gh = FakeGitHub(token="github_pat_x", repo_is_public=True)
        bootstrap.check_token(gh, allow_broad=False)  # must not raise

    def test_fine_grained_token_with_administration_access_on_public_repo_refused_by_default(self):
        """A public repo makes the Contents probe inconclusive, but Administration access is still caught."""
        gh = FakeGitHub(token="github_pat_x", repo_is_public=True, has_administration_access=True)
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_broad_installation_token_refused_by_default(self):
        gh = FakeGitHub(token="ghs_x", installation_repos=2)
        with self.assertRaises(bootstrap.Refused):
            bootstrap.check_token(gh, allow_broad=False)

    def test_single_repository_installation_token_passes_by_default(self):
        gh = FakeGitHub(token="ghs_x", installation_repos=1)
        bootstrap.check_token(gh, allow_broad=False)  # must not raise


class ExcessPermissions(unittest.TestCase):
    """The guard test: a probe that stops distinguishing 403 from 200 must go red here."""

    def test_contents_excess_when_readable_on_a_private_repo(self):
        gh = FakeGitHub(token="github_pat_x", has_contents_access=True)
        excess, inconclusive = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertIn("Contents", excess)
        self.assertEqual(inconclusive, [])

    def test_contents_no_excess_when_forbidden(self):
        gh = FakeGitHub(token="github_pat_x", has_contents_access=False)
        excess, inconclusive = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertEqual(excess, [])
        self.assertEqual(inconclusive, [])

    def test_contents_no_excess_when_not_found_without_an_empty_repo_message(self):
        """A plain 404 with no message (the common no-access case) is not mistaken for an empty repo."""
        gh = FakeGitHub(token="github_pat_x")
        gh.call = mock.Mock(side_effect=_http_error("url", 404))
        excess, inconclusive = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertEqual(excess, [])
        self.assertEqual(inconclusive, [])

    def test_contents_inconclusive_when_repo_is_empty(self):
        """An empty repository 404s on the Contents probe regardless of what the token can do."""
        gh = FakeGitHub(token="github_pat_x", has_contents_access=True, repo_is_empty=True)
        excess, inconclusive = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertNotIn("Contents", excess)
        self.assertTrue(any("Contents" in item for item in inconclusive))

    def test_contents_inconclusive_and_not_probed_when_repo_is_public(self):
        """A public repo's contents are readable by any token, so the probe can't be trusted either way."""
        gh = FakeGitHub(token="github_pat_x", has_contents_access=False)
        excess, inconclusive = bootstrap._excess_permissions(gh, repo_is_public=True)
        self.assertNotIn("Contents", excess)
        self.assertTrue(any("Contents" in item for item in inconclusive))

    def test_administration_excess_when_actions_permissions_readable(self):
        gh = FakeGitHub(token="github_pat_x", has_administration_access=True)
        excess, _ = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertIn("Administration", excess)

    def test_administration_no_excess_when_forbidden(self):
        gh = FakeGitHub(token="github_pat_x", has_administration_access=False)
        excess, _ = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertNotIn("Administration", excess)

    def test_secrets_excess_when_actions_secrets_readable(self):
        gh = FakeGitHub(token="github_pat_x", has_secrets_access=True)
        excess, _ = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertIn("Secrets", excess)

    def test_secrets_no_excess_when_forbidden(self):
        gh = FakeGitHub(token="github_pat_x", has_secrets_access=False)
        excess, _ = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertNotIn("Secrets", excess)

    def test_all_three_probes_fail_open_to_excess_on_an_unrelated_error(self):
        """A probe that fails open on a surprising status would hide excess access, not just this repo's absence."""
        gh = FakeGitHub(token="github_pat_x")
        gh.call = mock.Mock(side_effect=_http_error("url", 500))
        excess, _ = bootstrap._excess_permissions(gh, repo_is_public=False)
        self.assertEqual(set(excess), {"Contents", "Administration", "Secrets"})


class HttpErrorMessage(unittest.TestCase):
    """The guard test: losing the "can't read a body" fallback must go red here, not crash."""

    def test_reads_the_message_field(self):
        err = _http_error("url", 404, "This repository is empty.")
        self.assertEqual(bootstrap._http_error_message(err), "This repository is empty.")

    def test_empty_string_when_body_is_unreadable(self):
        err = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        self.assertEqual(bootstrap._http_error_message(err), "")


class CommandLineDefaultsToRefusing(unittest.TestCase):
    """The guard test: flipping --allow-broad-token's default must go red here."""

    def run_main(self, argv: list[str]) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / ".copier-answers.yml"
            answers.write_text("repo_owner: owner\nrepo_name: repo\n")
            with (
                mock.patch.object(sys, "argv", ["bootstrap.py", *argv]),
                mock.patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_classic"}),
                mock.patch.object(bootstrap, "ANSWERS", answers),
                mock.patch.object(bootstrap, "GitHub", lambda token, repo, dry_run: FakeGitHub(token)),
                mock.patch.object(bootstrap, "ensure_labels", side_effect=RuntimeError("past the token check")),
            ):
                bootstrap.main()

    def test_broad_token_refused_without_flag(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_main([])
        self.assertNotIn(cm.exception.code, (0, None))

    def test_broad_token_passes_check_with_flag(self):
        with self.assertRaisesRegex(RuntimeError, "past the token check"):
            self.run_main(["--allow-broad-token"])


class FromCopierSkipsCleanlyInsteadOfDeletingTheProject(unittest.TestCase):
    """The guard test: dropping --from-copier's exit-0 handling must go red here.

    Without --from-copier, main() must still exit non-zero on these same failures
    (a human running the script by hand should see a failure), which is what makes
    the --from-copier branch a deliberate opt-in rather than swallowing every error.
    """

    def run_main(self, argv: list[str], github_factory) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / ".copier-answers.yml"
            answers.write_text("repo_owner: owner\nrepo_name: repo\n")
            with (
                mock.patch.object(sys, "argv", ["bootstrap.py", *argv]),
                mock.patch.dict(os.environ, {"GITHUB_TOKEN": "github_pat_x"}),
                mock.patch.object(bootstrap, "ANSWERS", answers),
                mock.patch.object(bootstrap, "GitHub", github_factory),
            ):
                return bootstrap.main()

    def test_refused_token_exits_zero_with_from_copier(self):
        result = self.run_main(["--from-copier"], lambda token, repo, dry_run: FakeGitHub(token, oauth_scopes="repo"))
        self.assertEqual(result, 0)

    def test_refused_token_exits_non_zero_without_from_copier(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_main([], lambda token, repo, dry_run: FakeGitHub(token, oauth_scopes="repo"))
        self.assertNotIn(cm.exception.code, (0, None))

    def test_repository_not_found_exits_zero_with_from_copier(self):
        def raise_404(token: str, repo: str, dry_run: bool):
            gh = FakeGitHub(token)
            gh.call = mock.Mock(side_effect=bootstrap.urllib.error.HTTPError("url", 404, "Not Found", {}, None))
            return gh

        result = self.run_main(["--from-copier"], raise_404)
        self.assertEqual(result, 0)

    def test_repository_not_found_exits_non_zero_without_from_copier(self):
        def raise_404(token: str, repo: str, dry_run: bool):
            gh = FakeGitHub(token)
            gh.call = mock.Mock(side_effect=bootstrap.urllib.error.HTTPError("url", 404, "Not Found", {}, None))
            return gh

        with self.assertRaises(SystemExit) as cm:
            self.run_main([], raise_404)
        self.assertNotIn(cm.exception.code, (0, None))

    def _raising(self, exc: Exception):
        def factory(token: str, repo: str, dry_run: bool):
            gh = FakeGitHub(token)
            gh.call = mock.Mock(side_effect=exc)
            return gh

        return factory

    def test_network_error_exits_zero_with_from_copier(self):
        for exc in (
            bootstrap.urllib.error.URLError("DNS failure"),
            TimeoutError("timed out"),
            OSError("connection refused"),
            bootstrap.json.JSONDecodeError("Expecting value", "", 0),
        ):
            with self.subTest(exc=type(exc).__name__):
                result = self.run_main(["--from-copier"], self._raising(exc))
                self.assertEqual(result, 0)

    def test_network_error_exits_non_zero_without_from_copier(self):
        for exc in (
            bootstrap.urllib.error.URLError("DNS failure"),
            TimeoutError("timed out"),
            OSError("connection refused"),
            bootstrap.json.JSONDecodeError("Expecting value", "", 0),
        ):
            with self.subTest(exc=type(exc).__name__):
                with self.assertRaises(SystemExit) as cm:
                    self.run_main([], self._raising(exc))
                self.assertNotIn(cm.exception.code, (0, None))


class CheckTokenAllowBroadOptsOut(unittest.TestCase):
    def test_classic_token_allowed_with_flag(self):
        gh = FakeGitHub(token="ghp_classic")
        bootstrap.check_token(gh, allow_broad=True)  # must not raise

    def test_oauth_scoped_fine_grained_token_allowed_with_flag(self):
        gh = FakeGitHub(token="github_pat_x", oauth_scopes="repo")
        bootstrap.check_token(gh, allow_broad=True)  # must not raise

    def test_broad_fine_grained_token_allowed_with_flag(self):
        gh = FakeGitHub(token="github_pat_x", other_repos=[("owner/other-private", True)])
        bootstrap.check_token(gh, allow_broad=True)  # must not raise

    def test_fine_grained_token_with_contents_access_allowed_with_flag(self):
        gh = FakeGitHub(token="github_pat_x", has_contents_access=True)
        bootstrap.check_token(gh, allow_broad=True)  # must not raise

    def test_fine_grained_token_with_administration_access_allowed_with_flag(self):
        gh = FakeGitHub(token="github_pat_x", has_administration_access=True)
        bootstrap.check_token(gh, allow_broad=True)  # must not raise

    def test_fine_grained_token_with_secrets_access_allowed_with_flag(self):
        gh = FakeGitHub(token="github_pat_x", has_secrets_access=True)
        bootstrap.check_token(gh, allow_broad=True)  # must not raise

    def test_broad_installation_token_allowed_with_flag(self):
        gh = FakeGitHub(token="ghs_x", installation_repos=2)
        bootstrap.check_token(gh, allow_broad=True)  # must not raise


if __name__ == "__main__":
    unittest.main()
