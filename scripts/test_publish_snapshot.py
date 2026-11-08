"""Guard tests for publish_snapshot.py: each one goes red if the check it names is removed.

Standalone, standard-library-only:

    python3 scripts/test_publish_snapshot.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_snapshot as ps  # noqa: E402
from _git_env import clean_git_env  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "publish_snapshot.py"
PLANTED = "zzplantedterm9"
NOTES = "# Release notes\n\nThe first release.\n"


def git(cwd: Path, *args: str) -> str:
    env = dict(clean_git_env(), GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", TZ="Asia/Tokyo")
    out = subprocess.run(["git", "-C", str(cwd), *args], env=env, capture_output=True, text=True, check=True)
    return out.stdout


class Fixture:
    """A scratch staging repository with a tagged release, and an empty bare public repository."""

    def __init__(self, tmp: str, files: dict[str, str] | None = None) -> None:
        self.tmp = Path(tmp)
        self.staging = self.tmp / "staging"
        self.public = self.tmp / "public.git"
        self.denylist = self.tmp / "denylist.txt"
        self.denylist.write_text(f"{PLANTED}\n")
        self.staging.mkdir()
        git(self.staging, "init", "-q", "-b", "main")
        self.write(files or {
            "README.md": "staging readme\n",
            "docs/release-notes.md": NOTES,
            ".theforge-denylist": "secret-list\n",
            "nested/.theforge-denylist-allow": "x:y\n",
            "template/file.txt": "template\n",
        })
        self.commit_and_tag("v0.1.0")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.public)], check=True, env=clean_git_env())

    def write(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            path = self.staging / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def commit_and_tag(self, tag: str) -> None:
        git(self.staging, "add", "-A", "-f")
        git(self.staging, "commit", "-q", "-m", "release")
        git(self.staging, "tag", tag)

    def publish(self, *extra: str, version: str = "v0.1.0", denylist: Path | None = None,
                env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        env = dict(clean_git_env(), THEFORGE_DENYLIST_FILE=str(denylist or self.denylist), TZ="Asia/Tokyo", **(env_extra or {}))
        cmd = [sys.executable, str(SCRIPT), "--version", version, "--remote", str(self.public),
               "--repo", str(self.staging), "--require-ancestor-of", "HEAD", *extra]
        return subprocess.run(cmd, env=env, capture_output=True, text=True)

    def public_commits(self) -> list[str]:
        out = subprocess.run(["git", "-C", str(self.public), "log", "--format=%H", "main"],
                             env=clean_git_env(), capture_output=True, text=True)
        return out.stdout.split()

    def public_files(self) -> list[str]:
        return git(self.public, "ls-tree", "-r", "--name-only", "main").split()

    def public_show(self, path: str) -> str:
        return git(self.public, "show", f"main:{path}")


class PublishesCleanSnapshots(unittest.TestCase):
    def test_first_publish_is_one_commit_with_the_fixed_identity_at_utc(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            result = fx.publish()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(fx.public_commits()), 1)
            fmt = git(fx.public, "log", "-1", "--format=%an|%ae|%cn|%ce|%ad|%cd|%B", "--date=raw", "main")
            name, email, cname, cemail, date, cdate, body = fmt.split("|", 6)
            self.assertEqual((name, email), (ps.DEFAULT_AUTHOR_NAME, ps.DEFAULT_AUTHOR_EMAIL))
            self.assertEqual((cname, cemail), (name, email))
            self.assertTrue(date.endswith(" +0000") and cdate.endswith(" +0000"), (date, cdate))
            self.assertIn("TheForge v0.1.0", body)

    def test_denylist_files_are_never_published_wherever_they_sit(self):
        """Goes red if the exclude is removed or narrowed to the repository root."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assertEqual(fx.publish().returncode, 0)
            files = fx.public_files()
            self.assertIn("README.md", files)
            self.assertIn("template/file.txt", files)
            self.assertEqual([f for f in files if ".theforge-denylist" in f], [])

    def test_release_notes_get_the_notice_inserted_and_keep_their_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assertEqual(fx.publish().returncode, 0)
            notes = fx.public_show("docs/release-notes.md")
            self.assertTrue(notes.startswith("# Release notes\n\n> **Ticket numbers.**"))
            self.assertTrue(notes.endswith("\nThe first release.\n"))
            self.assertEqual(fx.staging.joinpath("docs/release-notes.md").read_text(), NOTES)

    def test_later_snapshot_is_a_child_commit_and_an_unchanged_one_adds_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assertEqual(fx.publish().returncode, 0)
            self.assertEqual(fx.publish().returncode, 0)
            self.assertEqual(len(fx.public_commits()), 1)
            fx.write({"README.md": "changed\n"})
            fx.commit_and_tag("v0.2.0")
            result = fx.publish(version="v0.2.0")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(fx.public_commits()), 2)
            self.assertEqual(fx.public_show("README.md"), "changed\n")

    def test_a_file_deleted_in_staging_disappears_from_public(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assertEqual(fx.publish().returncode, 0)
            git(fx.staging, "rm", "-q", "template/file.txt")
            fx.commit_and_tag("v0.2.0")
            self.assertEqual(fx.publish(version="v0.2.0").returncode, 0)
            self.assertNotIn("template/file.txt", fx.public_files())

    def test_tag_is_pushed_only_when_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assertEqual(fx.publish().returncode, 0)
            self.assertEqual(git(fx.public, "tag", "--list").split(), [])
            fx.write({"README.md": "two\n"})
            fx.commit_and_tag("v0.2.0")
            self.assertEqual(fx.publish("--tag", version="v0.2.0").returncode, 0)
            self.assertEqual(git(fx.public, "tag", "--list").split(), ["v0.2.0"])

    def test_a_gitignored_file_in_the_snapshot_is_still_published(self):
        """Goes red if `git add -f` is dropped: the scan passed that file, so it must ship."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.write({".gitignore": "ignored.txt\n", "ignored.txt": "kept\n"})
            fx.commit_and_tag("v0.2.0")
            self.assertEqual(fx.publish(version="v0.2.0").returncode, 0)
            self.assertIn("ignored.txt", fx.public_files())

    def test_user_git_config_cannot_change_the_commit(self):
        """Goes red if user and system git config are no longer isolated: a hooksPath hook here would fail the commit."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            hooks = Path(tmp) / "hooks"
            hooks.mkdir()
            hook = hooks / "commit-msg"
            hook.write_text("#!/bin/sh\nexit 1\n")
            hook.chmod(0o755)
            config = Path(tmp) / "gitconfig"
            config.write_text(f"[core]\n\thooksPath = {hooks}\n")
            result = fx.publish(env_extra={"GIT_CONFIG_GLOBAL": str(config)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(fx.public_commits()), 1)

    def test_the_scan_names_the_denylist_it_uses(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            result = fx.publish("--dry-run")
            self.assertIn(str(fx.denylist), result.stdout)

    def test_dry_run_pushes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            result = fx.publish("--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(fx.public_commits(), [])


class RefusesBeforePushing(unittest.TestCase):
    """Each case must leave the public repository empty. Goes red if the named check is removed."""

    def assert_refused_and_empty(
        self, fx: Fixture, result: subprocess.CompletedProcess, code: int = 1, term_may_show: bool = False
    ) -> None:
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertEqual(fx.public_commits(), [])
        if not term_may_show:  # a path hit necessarily shows the path, which is the term
            self.assertNotIn(PLANTED, result.stdout + result.stderr)

    def test_a_term_in_file_contents_stops_the_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.write({"template/leak.txt": f"see {PLANTED} here\n"})
            fx.commit_and_tag("v0.2.0")
            self.assert_refused_and_empty(fx, fx.publish(version="v0.2.0"))

    def test_a_term_in_a_path_stops_the_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.write({f"template/{PLANTED}.txt": "clean contents\n"})
            fx.commit_and_tag("v0.2.0")
            self.assert_refused_and_empty(fx, fx.publish(version="v0.2.0"), term_may_show=True)

    def test_a_term_in_the_commit_identity_stops_the_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assert_refused_and_empty(fx, fx.publish("--author-name", PLANTED))

    def test_a_personal_email_is_refused_as_the_commit_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            result = fx.publish("--author-email", "someone@example.org")
            self.assert_refused_and_empty(fx, result, code=2)

    def test_a_missing_denylist_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            result = fx.publish(denylist=Path(tmp) / "no-such-list")
            self.assert_refused_and_empty(fx, result)

    def test_an_empty_denylist_fails_closed(self):
        """A list with no terms must not read as 'scanned and clean'."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            empty = Path(tmp) / "empty-list"
            empty.write_text("# no terms\n")
            fx.write({"template/leak.txt": f"{PLANTED}\n"})
            fx.commit_and_tag("v0.2.0")
            result = fx.publish(version="v0.2.0", denylist=empty)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(fx.public_commits(), [])

    def test_a_release_not_on_main_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            git(fx.staging, "checkout", "-q", "-b", "side")
            fx.write({"README.md": "unreleased\n"})
            fx.commit_and_tag("v0.2.0")
            git(fx.staging, "checkout", "-q", "main")
            result = fx.publish("--require-ancestor-of", "main", version="v0.2.0")
            self.assert_refused_and_empty(fx, result, code=2)

    def test_a_moved_release_notes_heading_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.write({"docs/release-notes.md": "Release notes\n"})
            fx.commit_and_tag("v0.2.0")
            self.assert_refused_and_empty(fx, fx.publish(version="v0.2.0"), code=2)

    def test_a_missing_release_notes_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, {"README.md": "only\n"})
            self.assert_refused_and_empty(fx, fx.publish(), code=2)

    def test_a_symlink_in_the_release_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            os.symlink("README.md", fx.staging / "link")
            fx.commit_and_tag("v0.2.0")
            self.assert_refused_and_empty(fx, fx.publish(version="v0.2.0"), code=2)

    def test_a_bad_version_label_is_refused(self):
        """--ref names a real commit, so only the label check can refuse this."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assert_refused_and_empty(fx, fx.publish("--ref", "HEAD", version="0.1"), code=2)

    def test_a_failed_tag_push_leaves_main_where_it_was(self):
        """Goes red if the push stops being atomic: main would move although the tag was rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            hook = fx.public / "hooks" / "update"
            hook.write_text('#!/bin/sh\ncase "$1" in refs/tags/*) exit 1;; esac\n')
            hook.chmod(0o755)
            result = fx.publish("--tag")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(fx.public_commits(), [])

    def test_publish_runs_the_post_push_scan(self):
        """Goes red if publish stops calling verify_remote: old public history holding a term is only seen after the push."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            seed = Path(tmp) / "seed"
            seed.mkdir()
            git(seed, "init", "-q", "-b", "main")
            (seed / "old.txt").write_text("clean\n")
            git(seed, "add", "-A")
            git(seed, "commit", "-q", "-m", f"old message with {PLANTED}")
            git(seed, "push", "-q", str(fx.public), "main")
            result = fx.publish()
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("POST-PUSH SCAN", result.stderr)


class ScanUnits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.denylist = Path(self.tmp.name) / "list.txt"
        self.denylist.write_text(f"{PLANTED}\n")
        os.environ["THEFORGE_DENYLIST_FILE"] = str(self.denylist)
        self.addCleanup(os.environ.pop, "THEFORGE_DENYLIST_FILE", None)

    def test_scan_refuses_to_run_inside_a_git_work_tree(self):
        """The allow-list applies inside a work tree; a publish scan must never get one."""
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        (repo / "a.txt").write_text("clean\n")
        with self.assertRaises(ps.PublishError):
            ps.scan(["a.txt"], repo)

    def test_scan_reports_a_planted_term_and_a_clean_file(self):
        outside = Path(self.tmp.name) / "tree"
        outside.mkdir()
        (outside / "clean.txt").write_text("fine\n")
        (outside / "dirty.txt").write_text(f"{PLANTED}\n")
        self.assertTrue(ps.scan(["clean.txt"], outside))
        self.assertFalse(ps.scan(["dirty.txt"], outside))

    def test_verify_remote_fails_on_a_public_repository_holding_a_term(self):
        """The post-push scan: goes red if verify_remote stops scanning the clone's files or its log."""
        work = Path(self.tmp.name) / "work"
        work.mkdir()
        git(work, "init", "-q", "-b", "main")
        (work / "a.txt").write_text(f"{PLANTED}\n")
        git(work, "add", "-A")
        git(work, "commit", "-q", "-m", "x")
        scratch = Path(self.tmp.name) / "verify-scratch"
        scratch.mkdir()
        with self.assertRaises(ps.PublishError):
            ps.verify_remote(str(work), scratch)

    def test_verify_remote_fails_on_a_term_only_in_a_commit_message(self):
        work = Path(self.tmp.name) / "work2"
        work.mkdir()
        git(work, "init", "-q", "-b", "main")
        (work / "a.txt").write_text("clean\n")
        git(work, "add", "-A")
        git(work, "commit", "-q", "-m", f"message with {PLANTED}")
        scratch = Path(self.tmp.name) / "verify-scratch2"
        scratch.mkdir()
        with self.assertRaises(ps.PublishError):
            ps.verify_remote(str(work), scratch)

    def test_verify_remote_passes_a_clean_repository(self):
        work = Path(self.tmp.name) / "work3"
        work.mkdir()
        git(work, "init", "-q", "-b", "main")
        (work / "a.txt").write_text("clean\n")
        git(work, "add", "-A")
        git(work, "commit", "-q", "-m", "clean message")
        scratch = Path(self.tmp.name) / "verify-scratch3"
        scratch.mkdir()
        ps.verify_remote(str(work), scratch)


if __name__ == "__main__":
    unittest.main()
