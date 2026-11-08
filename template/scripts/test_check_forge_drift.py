"""Guard tests for check_forge_drift.py.

Every test builds its own local git repository as the upstream and a
plain directory as the consumer project, so the drift check is exercised
with no network and no dependency on this repository's own history.
This test no longer ships to consumers; it runs only here, and
directly against `template/scripts/` via `template-scripts-tests`.

Standalone: python3 scripts/test_check_forge_drift.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_forge_drift  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env()
    )


def _git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env()
    )
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class RepoFixture(unittest.TestCase):
    """A local, non-bare upstream repo plus a consumer project directory.
    `_src_path` is the upstream's local filesystem path, so `source_url()`
    passes it through unchanged and the drift check needs no network."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.upstream = root / "upstream"
        self.upstream.mkdir()
        self.project = root / "project"
        self.project.mkdir()
        _git(self.upstream, "init", "-q")
        _git(self.upstream, "config", "user.email", "test@example.com")
        _git(self.upstream, "config", "user.name", "Test")
        self._old_cwd = Path.cwd()

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)

    def commit(self, message: str = "commit") -> str:
        name = f"{message.replace(' ', '_')}.txt"
        _write(self.upstream / name, message)
        _git(self.upstream, "add", name)
        _git(self.upstream, "commit", "-q", "-m", message)
        return _git_output(self.upstream, "rev-parse", "HEAD")

    def commit_path(self, relpath: str, content: str, message: str | None = None) -> str:
        """Like `commit`, but the touched file is `relpath` with `content`,
        so a test can commit to a specific location (e.g. `template/a.md`
        versus `docs/adr/x.md`) with a chosen commit subject."""
        _write(self.upstream / relpath, content)
        _git(self.upstream, "add", relpath)
        _git(self.upstream, "commit", "-q", "-m", message or relpath)
        return _git_output(self.upstream, "rev-parse", "HEAD")

    def set_subdirectory(self, value: str | None, filename: str = "copier.yml") -> str:
        """Commit a `copier.yml` (or `copier.yaml`) to the upstream naming
        `value` as `_subdirectory`; `None` writes a file with no such key
        at all, the "missing" case."""
        content = f"_subdirectory: {value}\n" if value is not None else "other_key: x\n"
        return self.commit_path(filename, content, f"set _subdirectory to {value!r}")

    def write_project(self, commit: str, entrypoint_ok: bool = True) -> None:
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: '{self.upstream}'\n_commit: '{commit}'\n",
        )
        _write(self.project / ".forge" / "entrypoint.md", "The entrypoint.\n")
        if entrypoint_ok:
            _write(self.project / "CLAUDE.md", "@.forge/entrypoint.md\n")
        else:
            _write(self.project / "CLAUDE.md", "No entrypoint import here.\n")

    def run_drift(self, **kwargs: int) -> check_forge_drift.Drift:
        os.chdir(self.project)
        return check_forge_drift.drift(**kwargs)

    def run_main(self, argv: list[str] | None = None) -> int:
        os.chdir(self.project)
        return check_forge_drift.main(argv or [])


class CurrentProjectIsNotBehind(RepoFixture):
    def test_commit_equal_to_upstream_head_is_not_behind_and_skips_the_clone(self) -> None:
        sha = self.commit("base")
        self.write_project(sha)
        real_run_git = check_forge_drift.run_git

        def guarded_run_git(args, *a, **kw):
            if "clone" in args:
                raise AssertionError("the prefix short-circuit should skip the clone entirely")
            return real_run_git(args, *a, **kw)

        with mock.patch("check_forge_drift.run_git", side_effect=guarded_run_git):
            result = self.run_drift()
        self.assertEqual(result.behind, 0, "the prefix short-circuit (the both-sides case)")
        self.assertEqual(result.subjects, [])
        self.assertIsNone(result.error)
        self.assertTrue(result.entrypoint_ok)


class RootOnlyCommitsAreNotDrift(RepoFixture):
    def test_commits_outside_the_subdirectory_and_config_do_not_count(self) -> None:
        sha = self.set_subdirectory("template")
        self.write_project(sha)
        self.commit_path("docs/adr/x.md", "adr one")
        self.commit_path("docs/adr/y.md", "adr two")
        self.commit_path("README.md", "root readme")
        result = self.run_drift()
        self.assertEqual(result.behind, 0, "none of these commits can change a render")
        self.assertEqual(result.subjects, [])
        self.assertIsNone(result.error)


class TemplateAndConfigCommitsAreDrift(RepoFixture):
    def test_a_template_commit_and_a_config_commit_are_both_counted(self) -> None:
        sha = self.set_subdirectory("template")
        self.write_project(sha)
        self.commit_path("docs/adr/x.md", "adr one", "adr one")
        self.commit_path("template/a.md", "template change", "template change")
        self.commit_path("copier.yml", "_subdirectory: template\nextra: 1\n", "config change")
        result = self.run_drift()
        self.assertEqual(result.behind, 2, "only the template/ and copier.yml commits")
        self.assertEqual(set(result.subjects), {"template change", "config change"})
        self.assertIsNone(result.error)


class UnfilterableSubdirectoryCountsEverything(RepoFixture):
    def test_a_templated_subdirectory_counts_every_commit(self) -> None:
        sha = self.set_subdirectory("{{ _copier_conf.answers_relpath }}")
        self.write_project(sha)
        self.commit_path("docs/adr/x.md", "adr one")
        result = self.run_drift()
        self.assertEqual(result.behind, 1, "a templated value falls back to counting everything")

    def test_a_missing_subdirectory_counts_every_commit(self) -> None:
        sha = self.set_subdirectory(None)
        self.write_project(sha)
        self.commit_path("docs/adr/x.md", "adr one")
        result = self.run_drift()
        self.assertEqual(result.behind, 1, "no _subdirectory key falls back to counting everything")

    def test_an_unreadable_copier_yml_counts_every_commit(self) -> None:
        sha = self.commit("base")
        self.write_project(sha)
        self.commit_path("docs/adr/x.md", "adr one")
        result = self.run_drift()
        self.assertEqual(result.behind, 1, "no copier.yml at all falls back to counting everything")


class PathspecFollowsTheSeparator(RepoFixture):
    """Extends SeparatorPrecedesTheUrlInEveryGitInvocation's check to the
    rev-list and log calls: the pathspec entries must appear only after
    the `--` that already guards the revision range."""

    def test_pathspec_entries_follow_the_separator_in_rev_list_and_log(self) -> None:
        sha = self.set_subdirectory("template")
        self.write_project(sha)
        self.commit_path("template/a.md", "template change", "template change")
        captured: list[list[str]] = []
        real_run_git = check_forge_drift.run_git

        def capturing_run_git(args, *a, **kw):
            captured.append(args)
            return real_run_git(args, *a, **kw)

        with mock.patch("check_forge_drift.run_git", side_effect=capturing_run_git):
            result = self.run_drift()
        self.assertEqual(result.behind, 1)

        checked = [args for args in captured if "rev-list" in args or (len(args) > 3 and args[3] == "log")]
        self.assertGreaterEqual(len(checked), 2, f"expected both rev-list and log calls: {captured}")
        for args in checked:
            sep_index = args.index("--")
            tail = args[sep_index + 1 :]
            self.assertIn("template/", tail)
            self.assertIn("copier.yml", tail)
            self.assertIn("copier.yaml", tail)
            for entry in ("template/", "copier.yml", "copier.yaml"):
                self.assertNotIn(entry, args[:sep_index], f"pathspec entry {entry!r} appeared before '--': {args}")


class CountsCommitsBehind(RepoFixture):
    def test_three_commits_after_commit_are_counted(self) -> None:
        sha = self.commit("base")
        self.write_project(sha)
        self.commit("second")
        self.commit("third")
        self.commit("fourth")
        result = self.run_drift()
        self.assertEqual(result.behind, 3, "the rev-list count")
        self.assertEqual(len(result.subjects), 3)
        self.assertIsNone(result.error)


class SubjectsAreCappedAndSanitised(RepoFixture):
    def test_twenty_five_commits_cap_at_twenty_and_sanitise(self) -> None:
        sha = self.commit("base")
        self.write_project(sha)
        for i in range(24):
            self.commit(f"filler{i}")
        dirty_subject = "control\x01char" + "x" * 200
        self.commit(dirty_subject)
        result = self.run_drift(max_subjects=20)
        self.assertEqual(result.behind, 25)
        self.assertEqual(len(result.subjects), 20, "the cap")
        newest = result.subjects[0]
        self.assertNotIn("\x01", newest, "the strip")
        self.assertLessEqual(len(newest), 120, "the cut")


class DescribeFormParsed(unittest.TestCase):
    def test_describe_form_extracts_the_sha(self) -> None:
        self.assertEqual(check_forge_drift.commit_sha("v1.0-3-gabc1234"), "abc1234")


class BareTagResolved(RepoFixture):
    def test_a_bare_tag_is_resolved_against_the_remote(self) -> None:
        sha = self.commit("base")
        _git(self.upstream, "tag", "v1.0", sha)
        released = self.commit("second")
        _git(self.upstream, "tag", "v1.1", released)
        self.commit("third")
        self.write_project("v1.0")
        result = self.run_drift()
        self.assertEqual(result.behind, 1, "the tag resolution, counted against v1.1")
        self.assertIsNone(result.error)


class SyncTargetIsTheLatestReleaseTag(RepoFixture):
    """`behind` is counted against the ref `copier update` would sync to by
    default, so a held sync ticket never reports commits a default sync
    would not deliver. Each test fails if resolve_sync_target is reverted to
    always answer HEAD."""

    def test_no_tags_targets_head_and_reports_no_unreleased_count(self) -> None:
        base = self.commit("base")
        self.commit("second")
        self.write_project(base)
        result = self.run_drift()
        self.assertEqual((result.target, result.behind, result.unreleased), ("HEAD", 1, None))

    def test_with_tags_behind_stops_at_the_latest_tag_and_unreleased_counts_past_it(self) -> None:
        base = self.commit("base")
        _git(self.upstream, "tag", "v1.0", base)
        self.commit("second")
        released = self.commit("third")
        _git(self.upstream, "tag", "v1.1", released)
        self.commit("fourth")
        self.write_project(base)
        result = self.run_drift()
        self.assertEqual((result.target, result.behind, result.unreleased), ("v1.1", 2, 1))

    def test_a_project_at_the_latest_tag_is_current_even_with_commits_past_it(self) -> None:
        base = self.commit("base")
        _git(self.upstream, "tag", "v1.0", base)
        self.commit("second")
        self.write_project(base)
        result = self.run_drift()
        self.assertEqual((result.behind, result.unreleased), (0, 1))
        self.assertEqual(self.run_main(), 0)

    def test_prerelease_only_tags_fall_back_to_head(self) -> None:
        base = self.commit("base")
        _git(self.upstream, "tag", "v2.0.0rc1", base)
        self.commit("second")
        self.write_project(base)
        result = self.run_drift()
        self.assertEqual((result.target, result.behind), ("HEAD", 1))

    def test_a_prerelease_never_outranks_a_final_release(self) -> None:
        base = self.commit("base")
        _git(self.upstream, "tag", "v1.0.0", base)
        pre = self.commit("second")
        _git(self.upstream, "tag", "v2.0.0b1", pre)
        self.write_project(base)
        result = self.run_drift()
        self.assertEqual((result.target, result.behind), ("v1.0.0", 0))

    def test_tags_compare_numerically_and_non_release_names_are_ignored(self) -> None:
        base = self.commit("base")
        _git(self.upstream, "tag", "v1.9.0", base)
        _git(self.upstream, "tag", "not-a-version", base)
        newest = self.commit("second")
        _git(self.upstream, "tag", "v1.10.0", newest)
        self.commit("third")
        self.write_project(base)
        self.assertEqual(self.run_drift().target, "v1.10.0")

    def test_an_annotated_tag_resolves_to_its_commit(self) -> None:
        base = self.commit("base")
        _git(self.upstream, "tag", "-a", "v1.0.0", "-m", "release", base)
        self.write_project(base)
        result = self.run_drift()
        self.assertEqual((result.target, result.behind), ("v1.0.0", 0))

    def test_the_result_line_carries_target_and_unreleased_only_when_tagged(self) -> None:
        import contextlib
        import io

        base = self.commit("base")
        self.write_project(base)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.run_main()
        self.assertIn("target=HEAD behind=0", out.getvalue())
        self.assertNotIn("unreleased=", out.getvalue())
        _git(self.upstream, "tag", "v1.0", base)
        self.commit("second")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.run_main()
        self.assertIn("target=v1.0 behind=0 entrypoint=ok unreleased=1", out.getvalue())


class UnknownCommitIsUnknownNotCurrent(RepoFixture):
    def test_a_commit_not_in_upstream_history_is_unknown(self) -> None:
        self.commit("base")
        fake_sha = "0123456789abcdef0123456789abcdef01234567"
        self.write_project(fake_sha)
        result = self.run_drift()
        self.assertIsNone(result.behind, "must not report behind=0")
        self.assertIsNotNone(result.error)


class MissingEntrypointWins(RepoFixture):
    def test_missing_entrypoint_exits_3_but_still_reports_behind(self) -> None:
        sha = self.commit("base")
        self.write_project(sha, entrypoint_ok=False)
        self.commit("second")
        result = self.run_drift()
        self.assertFalse(result.entrypoint_ok)
        self.assertEqual(result.behind, 1, "behind is still reported so the ticket step runs")

        exit_code = self.run_main()
        self.assertEqual(exit_code, 3, "exit 3 precedence over behind/unknown")


class CredentialNeverLeaks(RepoFixture):
    def test_an_unreachable_url_with_embedded_credential_never_prints_it(self) -> None:
        secret = "SECRET-TOKEN-abc123"
        unreachable_url = f"https://u:{secret}@127.0.0.1:9/x"
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: '{unreachable_url}'\n_commit: 'abc1234'\n",
        )
        _write(self.project / ".forge" / "entrypoint.md", "The entrypoint.\n")
        _write(self.project / "CLAUDE.md", "@.forge/entrypoint.md\n")

        os.chdir(self.project)
        result = check_forge_drift.drift()
        self.assertIsNotNone(result.error)
        self.assertNotIn(secret, result.error or "", "the error must not carry the credential")

        buf_out, buf_err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("sys.stderr", buf_err):
            check_forge_drift.main([])
        self.assertNotIn(secret, buf_out.getvalue(), "stdout must not carry the credential")
        self.assertNotIn(secret, buf_err.getvalue(), "stderr must not carry the credential")

    def test_an_unresolvable_tag_never_prints_the_credential(self) -> None:
        secret = "SECRET-TAG-abc123"
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: 'https://u:{secret}@127.0.0.1:9/x'\n_commit: 'release-1'\n",
        )
        _write(self.project / ".forge" / "entrypoint.md", "The entrypoint.\n")
        _write(self.project / "CLAUDE.md", "@.forge/entrypoint.md\n")

        def fake_run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            self.assertEqual(args[1], "ls-remote", f"only the tag-resolution call site should run: {args}")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        os.chdir(self.project)
        with mock.patch("check_forge_drift.run_git", side_effect=fake_run_git):
            result = check_forge_drift.drift()
        self.assertIsNotNone(result.error)
        self.assertIn("could not resolve tag", result.error or "")
        self.assertNotIn(secret, result.error or "", "the error must not carry the credential")

    def test_a_failed_clone_never_prints_the_credential(self) -> None:
        secret = "SECRET-CLONE-abc123"
        sha = "0123456789abcdef0123456789abcdef01234567"
        upstream_sha = "fedcba9876543210fedcba9876543210fedcba98"
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: 'https://u:{secret}@127.0.0.1:9/x'\n_commit: '{sha}'\n",
        )
        _write(self.project / ".forge" / "entrypoint.md", "The entrypoint.\n")
        _write(self.project / "CLAUDE.md", "@.forge/entrypoint.md\n")

        def fake_run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            if args[1] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, stdout=f"{upstream_sha} HEAD\n", stderr="")
            if args[1] == "clone":
                return subprocess.CompletedProcess(args, 128, stdout="", stderr="fatal: could not read from remote")
            raise AssertionError(f"unexpected git call reached rev-list after a failed clone: {args}")

        os.chdir(self.project)
        with mock.patch("check_forge_drift.run_git", side_effect=fake_run_git):
            result = check_forge_drift.drift()
        self.assertIsNotNone(result.error)
        self.assertIn("could not clone", result.error or "")
        self.assertNotIn(secret, result.error or "", "the error must not carry the credential")

    def test_a_sha_not_in_upstream_history_never_prints_the_credential(self) -> None:
        secret = "SECRET-HISTORY-abc123"
        sha = "0123456789abcdef0123456789abcdef01234567"
        upstream_sha = "fedcba9876543210fedcba9876543210fedcba98"
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: 'https://u:{secret}@127.0.0.1:9/x'\n_commit: '{sha}'\n",
        )
        _write(self.project / ".forge" / "entrypoint.md", "The entrypoint.\n")
        _write(self.project / "CLAUDE.md", "@.forge/entrypoint.md\n")

        def fake_run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            if args[1] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, stdout=f"{upstream_sha} HEAD\n", stderr="")
            if args[1] == "clone":
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if "show" in args:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="fatal: path not found")
            if "rev-list" in args:
                return subprocess.CompletedProcess(args, 128, stdout="", stderr="fatal: bad revision")
            raise AssertionError(f"unexpected git call: {args}")

        os.chdir(self.project)
        with mock.patch("check_forge_drift.run_git", side_effect=fake_run_git):
            result = check_forge_drift.drift()
        self.assertIsNotNone(result.error)
        self.assertIn("is not in", result.error or "")
        self.assertNotIn(secret, result.error or "", "the error must not carry the credential")

    def test_ssh_style_credential_is_also_stripped(self) -> None:
        self.assertEqual(
            check_forge_drift.display_url("https://u:SECRET@host/path.git"),
            "https://host/path.git",
        )
        self.assertEqual(
            check_forge_drift.display_url("deploy@host:owner/repo.git"),
            "host:owner/repo.git",
        )
        self.assertEqual(
            check_forge_drift.display_url("https://host/path.git"),
            "https://host/path.git",
            "a URL with no credential is unchanged",
        )


class MalformedUrlDisplayIsTotal(unittest.TestCase):
    def test_an_unparsable_url_is_redacted_wholesale_instead_of_raising(self) -> None:
        secret = "s3cret"
        malformed = f"https://user:{secret}@[::1/x.git"
        with self.assertRaises(ValueError):
            # Confirms the failure mode this guards against still exists in
            # urlsplit itself; display_url must not propagate it.
            urlsplit(malformed)
        display = check_forge_drift.display_url(malformed)
        self.assertNotIn(secret, display)


class NonUtf8AnswersFileReportsUnknownNotACrash(RepoFixture):
    def test_a_non_utf8_copier_answers_yml_is_caught_not_raised(self) -> None:
        _write(self.project / ".forge" / "entrypoint.md", "The entrypoint.\n")
        _write(self.project / "CLAUDE.md", "@.forge/entrypoint.md\n")
        (self.project / ".copier-answers.yml").write_bytes(b"_src_path: '\xff\xfe invalid utf-8'\n")

        os.chdir(self.project)
        result = check_forge_drift.drift()
        self.assertIsNone(result.behind)
        self.assertIsNotNone(result.error)

        exit_code = self.run_main()
        self.assertEqual(exit_code, 2)


class NonNumericRevListCountIsCaughtByTheFallback(RepoFixture):
    def test_an_unparsable_rev_list_count_is_reported_not_raised(self) -> None:
        sha = "0123456789abcdef0123456789abcdef01234567"
        upstream_sha = "fedcba9876543210fedcba9876543210fedcba98"
        self.write_project(sha)

        def fake_run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            if args[1] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, stdout=f"{upstream_sha} HEAD\n", stderr="")
            if args[1] == "clone":
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if "show" in args:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="fatal: path not found")
            if "rev-list" in args:
                return subprocess.CompletedProcess(args, 0, stdout="not-a-number\n", stderr="")
            raise AssertionError(f"unexpected git call: {args}")

        with mock.patch("check_forge_drift.run_git", side_effect=fake_run_git):
            result = self.run_drift()
        self.assertIsNone(result.behind, "the catch-all reports unknown, not a crash")
        self.assertIsNotNone(result.error)
        self.assertIn("ValueError", result.error or "", "type(exc).__name__, never str(exc)")

        with mock.patch("check_forge_drift.run_git", side_effect=fake_run_git):
            exit_code = self.run_main()
        self.assertEqual(exit_code, 2)


class FlagLikeSrcPathIsRejected(RepoFixture):
    def test_a_dash_prefixed_src_path_is_rejected_with_no_subprocess_run(self) -> None:
        sha = self.commit("base")
        self.write_project(sha)
        payload_marker = Path(self.tmp.name) / "PWNED"
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: '--upload-pack=touch {payload_marker}'\n_commit: '{sha}'\n",
        )
        real_run_git = check_forge_drift.run_git

        def guarded_run_git(args, *a, **kw):
            if args[:2] == ["git", "ls-remote"] or args[:2] == ["git", "clone"]:
                raise AssertionError("a flag-like _src_path must never reach a git invocation")
            return real_run_git(args, *a, **kw)

        with mock.patch("check_forge_drift.run_git", side_effect=guarded_run_git):
            result = self.run_drift()
        self.assertIsNone(result.behind)
        self.assertIsNotNone(result.error)
        self.assertFalse(payload_marker.exists(), "no subprocess side effect occurred")


class SeparatorPrecedesTheUrlInEveryGitInvocation(RepoFixture):
    """With `looks_like_flag` forced to always pass, every argv the script
    builds for `run_git` must still place `--` immediately before the url."""

    def test_every_captured_argv_places_dash_dash_immediately_before_the_url(self) -> None:
        # A bare-tag `_commit` (not a hex sha) is required to reach all
        # four "--", url call sites: a hex sha short-circuits commit_sha()
        # and skips the tag-resolution ls-remote entirely.
        self.write_project("release-1")
        payload = "--upload-pack=touch /tmp/should-not-run-from-drift-test"
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: '{payload}'\n_commit: 'release-1'\n",
        )
        captured: list[list[str]] = []

        def fake_run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            captured.append(args)
            if args[1] == "ls-remote" and any("refs/tags/" in a for a in args):
                return subprocess.CompletedProcess(args, 0, stdout="deadbeef00 refs/tags/release-1\n", stderr="")
            if args[1] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, stdout="cafef00d00 HEAD\n", stderr="")
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="clone refused in test")

        with (
            mock.patch("check_forge_drift.looks_like_flag", return_value=False),
            mock.patch("check_forge_drift.run_git", side_effect=fake_run_git),
        ):
            self.run_drift()

        argv_with_payload = [args for args in captured if payload in args]
        self.assertEqual(
            len(argv_with_payload),
            4,
            "expected all four call sites (tag-resolution ls-remote, HEAD "
            f"ls-remote, tag-list ls-remote, clone) to carry the payload: {captured}",
        )
        for args in argv_with_payload:
            index = args.index(payload)
            self.assertGreater(index, 0, f"payload is argv[0] with nothing before it: {args}")
            self.assertEqual(
                args[index - 1],
                "--",
                "the token immediately before the attacker-controlled value must be "
                f"'--', not {args[index - 1]!r}: {args}",
            )


class SeparatorBlocksAFlagLikeUrlEvenWithoutTheExplicitCheck(unittest.TestCase):
    # Sanity check on git's own behaviour only; it never calls
    # check_forge_drift, so SeparatorPrecedesTheUrlInEveryGitInvocation
    # (above) is what actually guards the script.
    def test_ls_remote_refuses_a_flag_like_positional_after_dash_dash(self) -> None:
        result = subprocess.run(
            ["git", "ls-remote", "--", "--upload-pack=touch /tmp/should-not-run", "HEAD"],
            capture_output=True,
            text=True,
            env=clean_git_env(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("strange pathname", result.stderr.lower())

    def test_clone_refuses_a_flag_like_positional_after_dash_dash(self) -> None:
        marker = Path(tempfile.gettempdir()) / "should-not-run-from-clone-test"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["git", "clone", "--bare", "--filter=blob:none", "--quiet", "--",
                 f"--upload-pack=touch {marker}", tmpdir],
                capture_output=True,
                text=True,
                env=clean_git_env(),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr.lower(), "-- makes git treat the value as a repository name, not an option")
        self.assertFalse(marker.exists(), "no subprocess side effect occurred")


class SlowGitTimesOutCleanly(RepoFixture):
    def test_a_git_call_past_its_timeout_reports_unknown_not_a_crash(self) -> None:
        sha = self.commit("base")
        secret = "SECRET-IN-TIMEOUT-PATH"
        self.write_project(sha)
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: 'https://u:{secret}@127.0.0.1:9/x'\n_commit: '{sha}'\n",
        )

        def slow_run(args, *a, **kw):
            raise subprocess.TimeoutExpired(cmd=args, timeout=kw.get("timeout", 1))

        with mock.patch("check_forge_drift.subprocess.run", side_effect=slow_run):
            result = self.run_drift()
        self.assertIsNone(result.behind, "a timeout is reported as unknown, not current or a crash")
        self.assertIsNotNone(result.error)
        self.assertNotIn(secret, result.error or "", "TimeoutExpired's own message embeds the full argv")

        buf_out, buf_err = io.StringIO(), io.StringIO()
        with mock.patch("check_forge_drift.subprocess.run", side_effect=slow_run), \
                mock.patch("sys.stdout", buf_out), mock.patch("sys.stderr", buf_err):
            exit_code = self.run_main()
        self.assertEqual(exit_code, 2, "the defined 'unknown' exit code, not an uncaught-exception exit of 1")
        self.assertNotIn(secret, buf_out.getvalue())
        self.assertNotIn(secret, buf_err.getvalue())


class MissingGitBinaryReportsUnknown(RepoFixture):
    def test_an_oserror_from_a_missing_git_binary_is_caught(self) -> None:
        sha = self.commit("base")
        self.write_project(sha)

        def missing_binary(args, *a, **kw):
            raise FileNotFoundError(2, "No such file or directory", "git")

        with mock.patch("check_forge_drift.subprocess.run", side_effect=missing_binary):
            result = self.run_drift()
        self.assertIsNone(result.behind)
        self.assertIsNotNone(result.error)

        with mock.patch("check_forge_drift.subprocess.run", side_effect=missing_binary):
            exit_code = self.run_main()
        self.assertEqual(exit_code, 2)


class MissingAnswersFileReportsUnknown(RepoFixture):
    def test_no_copier_answers_yml_is_caught_not_raised(self) -> None:
        # No write_project(): the project directory has no .copier-answers.yml at all.
        _write(self.project / ".forge" / "entrypoint.md", "The entrypoint.\n")
        _write(self.project / "CLAUDE.md", "@.forge/entrypoint.md\n")
        result = self.run_drift()
        self.assertIsNone(result.behind)
        self.assertIsNotNone(result.error)
        self.assertTrue(result.entrypoint_ok, "entrypoint_ok is still computed independently of the answers file")

        exit_code = self.run_main()
        self.assertEqual(exit_code, 2)


class GhShorthandMapped(unittest.TestCase):
    def test_gh_shorthand_expands_to_the_clone_url(self) -> None:
        self.assertEqual(check_forge_drift.source_url("gh:a/b"), "https://github.com/a/b.git")
        self.assertEqual(check_forge_drift.source_url("gl:a/b"), "https://gitlab.com/a/b.git")
        self.assertEqual(check_forge_drift.source_url("https://example.com/a/b.git"), "https://example.com/a/b.git")


if __name__ == "__main__":
    unittest.main()
