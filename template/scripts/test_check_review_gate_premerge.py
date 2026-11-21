"""Guard tests for check_review_gate_premerge.sh.

A fake `gh` on PATH stands in for the real CLI, so these tests need no
network access or authentication: it serves canned PR body/files/head-sha
JSON instead of a real PR's, and the real `scripts/check_review_gate.py`
content for the `contents/.../ref=main` fetch, so the script under test
exercises the real checker end to end.

Standalone, standard-library-only:

    python3 scripts/test_check_review_gate_premerge.py
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import clean_git_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check_review_gate_premerge.sh"
CHECKER = ROOT / "scripts" / "check_review_gate.py"

REAL_STANDARDS = "clean sub-agent, build-tier -- no findings"
REAL_SPEC = "clean sub-agent, build-tier -- matches issue #1, no findings"
REAL_SELF_REVIEW = "build-tier (builder's own) -- covered everything; no findings"

PASSING_BODY = (
    "Ticket: Closes #1\n\n"
    f"Review: Standards: {REAL_STANDARDS}. Spec: {REAL_SPEC}. Self-review: {REAL_SELF_REVIEW}."
)
FAILING_BODY = "Ticket: Closes #1\n\nReview: Standards: <performer, tier[, model]>. Spec: n/a. Self-review: n/a."

# A fake `gh` dispatching on the endpoint path (argv after "api"), ignoring
# --jq (it already returns the filtered shape that flag would produce), but
# enforcing the two invariants the script exists for, so weakening either in
# the script under test goes red here instead of passing silently:
#   - the contents fetch must ask for `ref=main`, never a different ref (the
#     PR branch's own, possibly weakened, copy of the checker);
#   - the files-list fetch must pass `--paginate`; without it, this fake
#     mimics a truncating single-page endpoint by returning only the first
#     file, the exact failure mode this script exists to close.
# Reads the PR body, files and head SHA it serves from env vars so each test
# can vary them without touching the script under test.
_FAKE_GH = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import base64
    import json
    import os
    import sys

    args = sys.argv[1:]
    assert args and args[0] == "api", args
    path = args[1]
    flags = args[2:]

    if path.split("?")[0].endswith("/files"):
        files = [name for name in os.environ.get("FAKE_PR_FILES", "").splitlines() if name]
        if "--paginate" not in flags:
            files = files[:1]
        for name in files:
            print(name)
    elif "/pulls?head=" in path:
        print(os.environ.get("FAKE_PR_NUMBER", ""))
    elif "/contents/scripts/check_review_gate.py" in path:
        query = path.split("?", 1)[1] if "?" in path else ""
        if "ref=main" not in query:
            print(f"fake gh: contents fetch did not ask for ref=main: {path!r}", file=sys.stderr)
            sys.exit(1)
        with open(os.environ["FAKE_CHECKER_PATH"], "rb") as f:
            print(base64.b64encode(f.read()).decode("ascii"))
    elif "/pulls/" in path:
        print(
            json.dumps(
                {
                    "body": os.environ.get("FAKE_PR_BODY"),
                    "head": {"sha": os.environ.get("FAKE_PR_HEAD_SHA", "deadbeef")},
                }
            )
        )
    else:
        print(f"fake gh: unrecognised path {path!r}", file=sys.stderr)
        sys.exit(1)
    """
)


def _make_fake_gh(tmp: Path) -> Path:
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _repo_with_origin(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    env = clean_git_env()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test-owner/test-repo.git"],
        cwd=repo,
        env=env,
        check=True,
    )
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, env=env, check=True)
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, env=env, check=True)
    return repo


def _run(
    repo: Path, bin_dir: Path, *, body: str, files: list[str], head_sha: str = "cafef00d", pr_number: str | None = "7"
) -> subprocess.CompletedProcess:
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "FAKE_PR_BODY": body,
        "FAKE_PR_FILES": "\n".join(files),
        "FAKE_PR_HEAD_SHA": head_sha,
        "FAKE_CHECKER_PATH": str(CHECKER),
    }
    argv = [str(CHECK)]
    if pr_number is not None:
        argv.append(pr_number)
    else:
        env["FAKE_PR_NUMBER"] = ""
    return subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True)


class ChecksAgainstTheRealChecker(unittest.TestCase):
    """The guard test: dropping the paginated-files fetch, the origin/main
    fetch of check_review_gate.py, or the head-SHA print must go red here."""

    def test_passing_review_field_and_only_md_files_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _repo_with_origin(tmp)
            bin_dir = _make_fake_gh(tmp)
            result = _run(repo, bin_dir, body=PASSING_BODY, files=["docs/guide.md"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cafef00d", result.stdout)
        self.assertIn("review gate clears", result.stdout)

    def test_placeholder_review_field_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _repo_with_origin(tmp)
            bin_dir = _make_fake_gh(tmp)
            result = _run(repo, bin_dir, body=FAILING_BODY, files=["backend/thing.py"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Review:", result.stderr)

    def test_a_disqualifying_doc_path_blocks_the_light_gate(self) -> None:
        light_gate_body = "Ticket: Closes #1\n\nReview: Standards: n/a (light gate: prose-only doc edit). Spec: n/a (light gate: prose-only doc edit). Self-review: build-tier -- checked wording; no findings."
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _repo_with_origin(tmp)
            bin_dir = _make_fake_gh(tmp)
            # CLAUDE.md is a disqualifying path even though it's a .md file.
            # It's listed second, not first: the fake gh's --paginate guard
            # (see _FAKE_GH) truncates to the first file when the script
            # drops --paginate, so this only catches a dropped flag because
            # the disqualifying path isn't the one truncation would keep
            # (the exact failure mode this script exists to close).
            result = _run(repo, bin_dir, body=light_gate_body, files=["docs/other.md", "CLAUDE.md"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a prose-only doc", result.stderr)

    def test_no_pr_number_given_and_none_found_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _repo_with_origin(tmp)
            bin_dir = _make_fake_gh(tmp)
            result = _run(repo, bin_dir, body=PASSING_BODY, files=["docs/guide.md"], pr_number=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no open PR found", result.stderr)


if __name__ == "__main__":
    unittest.main()
