"""Guard tests for check_forge_sync_trust_diff.py.

Every test builds its own local git repository as the upstream and a plain
directory as the consumer project, so the check is exercised with no network
and no dependency on this repository's own history. This test no
longer ships to consumers; it runs only here, and directly against
`template/scripts/` via `template-scripts-tests`.

Standalone: python3 scripts/test_check_forge_sync_trust_diff.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_forge_sync_trust_diff  # noqa: E402
import check_forge_sync_trust_record  # noqa: E402
from _git_subprocess import clean_git_env  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env())


def _git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=clean_git_env())
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class RepoFixture(unittest.TestCase):
    """A local, non-bare upstream repo (seeded with a harmless `copier.yml`
    and the executable-content paths) plus a consumer project directory.
    `_src_path` is the upstream's local filesystem path, so `source_url()`
    passes it through unchanged and the check needs no network."""

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
        _write(self.upstream / "copier.yml", "_tasks: []\n")
        _write(self.upstream / "template" / "scripts" / "bootstrap.py", "pass\n")
        _write(self.upstream / "template" / ".pre-commit-config.yaml.jinja", "repos: []\n")
        _write(self.upstream / "template" / "README.md", "docs only\n")
        _git(self.upstream, "add", "-A")
        _git(self.upstream, "commit", "-q", "-m", "seed")
        self._old_cwd = Path.cwd()

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)

    def commit(self, message: str) -> str:
        _git(self.upstream, "commit", "-q", "-m", message, "--allow-empty")
        return _git_output(self.upstream, "rev-parse", "HEAD")

    def seed_commit(self) -> str:
        return _git_output(self.upstream, "rev-parse", "HEAD")

    def write_project(self, commit: str) -> None:
        _write(
            self.project / ".copier-answers.yml",
            f"_src_path: '{self.upstream}'\n_commit: '{commit}'\n",
        )

    def run_main(self, argv: list[str] | None = None) -> tuple[int, str]:
        os.chdir(self.project)
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = check_forge_sync_trust_diff.main(argv or [])
        return code, buf.getvalue()


class NoChangeIsClean(RepoFixture):
    def test_old_equal_to_new_reports_nothing_changed(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        code, output = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("no change", output)


class RecordLineRoundTripsThroughTheTrustRecordGuard(RepoFixture):
    """The two scripts must agree on one line's shape: the record guard
    accepts a clean scan's own output as-is and rejects a changed one."""

    def _record_endpoints(self, output: str) -> tuple[str, str]:
        match = check_forge_sync_trust_record.TRUST_DIFF_RE.search(output)
        self.assertIsNotNone(match, output)
        return match["old"], match["new"]

    def test_a_clean_scan_s_record_line_passes_the_record_guard_unmodified(self) -> None:
        old_sha = self.seed_commit()
        self.write_project(old_sha)
        code, output = self.run_main()
        self.assertEqual(code, 0)
        old_endpoint, new_endpoint = self._record_endpoints(output)
        # Different strings (full sha vs. git describe's abbreviated form of
        # the same commit) so the old != new trigger fires, while the prefix
        # rule in _endpoints_match still accepts them as equal.
        old_answers = f"_commit: '{old_endpoint}'\n"
        new_answers = f"_commit: '{new_endpoint}'\n"
        self.assertEqual(check_forge_sync_trust_record.check(output, old_answers, new_answers), [])

    def test_a_changed_scan_s_record_line_is_rejected_as_unreviewed(self) -> None:
        old_sha = self.seed_commit()
        self.write_project(old_sha)
        _write(self.upstream / "template" / "scripts" / "bootstrap.py", "print('changed')\n")
        _git(self.upstream, "add", "-A")
        self.commit("scripts change")
        code, output = self.run_main()
        self.assertEqual(code, 1)
        old_endpoint, new_endpoint = self._record_endpoints(output)
        old_answers = f"_commit: '{old_endpoint}'\n"
        new_answers = f"_commit: '{new_endpoint}'\n"
        failures = check_forge_sync_trust_record.check(output, old_answers, new_answers)
        self.assertEqual(len(failures), 1)
        self.assertIn("changed:", failures[0])


class DefaultTargetIsTheLatestReleaseTag(RepoFixture):
    """With no --new the diff covers the ref `copier update` syncs to, so the
    reviewed diff is the one that will run. Each test fails if
    resolve_sync_target is reverted to always answer HEAD."""

    def _past_tag_fixture(self, tag: str) -> None:
        self.write_project(self.seed_commit())
        _write(self.upstream / "template" / "scripts" / "released.py", "x = 1\n")
        _git(self.upstream, "add", "-A")
        released = self.commit("released script")
        _git(self.upstream, "tag", tag, released)
        _write(self.upstream / "template" / ".claude" / "hook.sh", "echo unreleased\n")
        _git(self.upstream, "add", "-A")
        self.commit("unreleased hook")

    def test_with_a_tag_the_unreleased_commit_past_it_is_not_in_the_diff(self) -> None:
        self._past_tag_fixture("v1.0.0")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("template/scripts/", output)
        self.assertNotIn("template/.claude/", output)

    def test_with_no_tag_head_is_diffed(self) -> None:
        self.write_project(self.seed_commit())
        _write(self.upstream / "template" / ".claude" / "hook.sh", "echo head\n")
        _git(self.upstream, "add", "-A")
        self.commit("hook")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("template/.claude/", output)

    def test_a_prerelease_only_tag_still_diffs_head(self) -> None:
        self._past_tag_fixture("v1.0.0rc1")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("template/.claude/", output)

    def test_an_explicit_new_overrides_the_tag_default(self) -> None:
        self._past_tag_fixture("v1.0.0")
        code, output = self.run_main(["--new", "HEAD"])
        self.assertEqual(code, 1, output)
        self.assertIn("template/.claude/", output)


class UnrelatedFileChangeIsClean(RepoFixture):
    def test_a_change_outside_the_executable_paths_is_not_flagged(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "template" / "docs" / "guide.md", "more docs\n")
        _git(self.upstream, "add", "-A")
        self.commit("docs change")
        code, output = self.run_main()
        self.assertEqual(code, 0, output)


class ExecutablePathChangeIsFlagged(RepoFixture):
    def test_a_change_under_scripts_is_flagged_with_its_diff(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "template" / "scripts" / "bootstrap.py", "print('changed')\n")
        _git(self.upstream, "add", "-A")
        self.commit("scripts change")
        code, output = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("template/scripts/", output)
        self.assertIn("changed", output)


class DocToolsPathChangeIsFlagged(RepoFixture):
    def test_a_change_under_docs_tools_is_flagged_with_its_diff(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "template" / "docs" / "tools" / "process_map.py", "print('changed')\n")
        _git(self.upstream, "add", "-A")
        self.commit("docs/tools change")
        code, output = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("template/docs/tools/", output)
        self.assertIn("changed", output)


class PreCommitConfigChangeIsFlagged(RepoFixture):
    def test_a_change_to_the_pre_commit_config_is_flagged(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "template" / ".pre-commit-config.yaml.jinja", "repos: [new]\n")
        _git(self.upstream, "add", "-A")
        self.commit("pre-commit change")
        code, output = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn(".pre-commit-config.yaml.jinja", output)


class NewMigrationsKeyIsFlaggedByName(RepoFixture):
    def test_adding_migrations_to_copier_yml_is_named_as_a_finding(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "copier.yml", "_tasks: []\n_migrations:\n  - 'echo hi'\n")
        _git(self.upstream, "add", "-A")
        self.commit("add migrations")
        code, output = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("_migrations", output)
        self.assertIn("finding:", output)


class NewJinjaExtensionsKeyIsFlaggedByName(RepoFixture):
    def test_adding_jinja_extensions_to_copier_yml_is_named_as_a_finding(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "copier.yml", "_tasks: []\n_jinja_extensions:\n  - 'evil.Extension'\n")
        _git(self.upstream, "add", "-A")
        self.commit("add jinja extensions")
        code, output = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("_jinja_extensions", output)


class CopierYamlOnlyUpstreamIsStillChecked(RepoFixture):
    """Regression for the fail-open gap closed by sharing `copier_yml_at`
    with check_forge_drift.py: before, this check only ever read
    `copier.yml`, so a `copier.yaml`-named upstream would silently report
    zero unsafe-key findings. `copier_yml_at`'s `copier.yml`/`copier.yaml`
    fallback (shared from _git_subprocess.py) keeps the check working when
    upstream's config uses the `.yaml` spelling."""

    def test_adding_migrations_to_copier_yaml_is_still_flagged(self) -> None:
        (self.upstream / "copier.yml").unlink()
        _write(self.upstream / "copier.yaml", "_tasks: []\n")
        _git(self.upstream, "add", "-A")
        self.commit("rename copier.yml to copier.yaml")
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "copier.yaml", "_tasks: []\n_migrations:\n  - 'echo hi'\n")
        _git(self.upstream, "add", "-A")
        self.commit("add migrations under copier.yaml")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("_migrations", output)
        self.assertIn("finding:", output)


class UnchangedUnsafeKeyIsNotReflagged(RepoFixture):
    def test_a_migrations_key_present_at_both_commits_is_not_a_new_finding(self) -> None:
        _write(self.upstream / "copier.yml", "_tasks: []\n_migrations:\n  - 'echo hi'\n")
        _git(self.upstream, "add", "-A")
        self.commit("add migrations")
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "template" / "README.md", "unrelated change\n")
        _git(self.upstream, "add", "-A")
        self.commit("unrelated change")
        code, output = self.run_main()
        self.assertEqual(code, 0, output)
        self.assertNotIn("finding:", output)


class UnsafeKeyValueOnlyChangeIsFlaggedByName(RepoFixture):
    def test_a_changed_migrations_list_item_is_named_even_with_the_header_line_unchanged(self) -> None:
        _write(self.upstream / "copier.yml", "_tasks: []\n_migrations:\n  - 'echo hi'\n")
        _git(self.upstream, "add", "-A")
        self.commit("add migrations")
        sha = self.seed_commit()
        self.write_project(sha)
        _write(self.upstream / "copier.yml", "_tasks: []\n_migrations:\n  - 'echo pwned'\n")
        _git(self.upstream, "add", "-A")
        self.commit("change the migration's own command, header line untouched")
        code, output = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("finding:", output)
        self.assertIn("_migrations", output)


class ExplicitNewRefIsRespected(RepoFixture):
    def test_new_flag_diffs_against_the_named_ref_not_head(self) -> None:
        sha = self.seed_commit()
        self.write_project(sha)
        self.commit("tagged release")
        _git(self.upstream, "tag", "v1.0.0")
        _write(self.upstream / "template" / "scripts" / "bootstrap.py", "print('after tag')\n")
        _git(self.upstream, "add", "-A")
        self.commit("after the tag")
        code, output = self.run_main(["--new", "v1.0.0"])
        self.assertEqual(code, 0, f"diffing to the tag must not see the commit made after it: {output}")


class MissingAnswersFileIsAnError(RepoFixture):
    def test_no_copier_answers_file_exits_two(self) -> None:
        code, output = self.run_main()
        self.assertEqual(code, 2)


class FlagLikeSrcPathIsRejected(RepoFixture):
    def test_a_src_path_beginning_with_dash_is_refused(self) -> None:
        _write(self.project / ".copier-answers.yml", "_src_path: '--upload-pack=evil'\n_commit: 'deadbeef'\n")
        os.chdir(self.project)
        code = check_forge_sync_trust_diff.main([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
