"""Guard test: the always_run hooks guarding a tracked file's *deletion*
(`forge-entrypoint`, which guards `.forge/entrypoint.md`/`CLAUDE.md`, and its
sibling `skills-lock`, which guards `.agents/skills/`/`skills-lock.json`)
still fire when a commit deletes the file instead of editing it.

pre-commit's own staged-file list uses `--diff-filter=ACMRTUXB`, which
excludes deletions. A hook gated only by a `files:` regex therefore sees no
staged file to match and silently skips ("(no files to check) Skipped") on
exactly the commit each hook exists to catch -- deleting the forge entrypoint
disables every forge rule including the review gate itself; deleting a
vendored skill's directory, or `skills-lock.json` itself, defeats the
tamper check the same way. Both hooks carry `always_run: true` specifically
for this, the same lesson `pinned-dependencies` already applied to its own
target file.

This runs each hook for real, through `pre-commit run`, against a throwaway
git repository with a staged deletion -- not just the underlying check
script directly (neither script's own exit code was ever the bug;
`test_check_forge_entrypoint.py` and `test_check_skills_lock.py` already
cover those). `always_run: true` is what this test isolates: stripping it
from the extracted hook block reproduces the exact "Skipped" false pass each
hook was fixed to prevent.

Standalone: python3 scripts/test_forge_entrypoint_hook_fires_on_deletion.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import clean_git_env  # noqa: E402
from jinja_paths import rendered_or_jinja  # noqa: E402

PRE_COMMIT_CONFIG = rendered_or_jinja(".pre-commit-config.yaml")
SCRIPTS_DIR = Path(__file__).resolve().parent


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _hook_block(text: str, hook_id: str) -> str:
    """The named hook's own YAML block: from its `- id:` line up to (not
    including) the next `- id:` line, or the end of the file."""
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.match(rf"^\s*- id:\s*{re.escape(hook_id)}\s*$", line)),
        None,
    )
    if start is None:
        raise AssertionError(f"no {hook_id!r} hook found in .pre-commit-config.yaml[.jinja]")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^\s*- id:", lines[i])), len(lines))
    # Trim trailing comment/blank lines: they're the *next* hook's leading
    # doc-comment, not this one's -- left in, a neighbour's prose (which may
    # itself legitimately say "always_run", as skills-lock's does) would
    # leak into this block and defeat an always_run presence/absence check.
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].strip().startswith("#")):
        end -= 1
    return "\n".join(lines[start:end])


def _init_git_repo(root: Path) -> None:
    env = clean_git_env()
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, env=env)


def _build_forge_entrypoint_fixture(root: Path, hook_block: str) -> None:
    """A minimal compliant consumer tree, plus a `.pre-commit-config.yaml`
    carrying only the one extracted hook (so this test exercises that exact
    hook's own trigger, never a copy reinvented here that could drift from
    it), committed as a real git history."""
    _init_git_repo(root)
    _write(root / "CLAUDE.md", "# Working on example\n\n@.forge/entrypoint.md\n\n## This project's own rules\n")
    _write(root / "AGENTS.md", "Read .forge/entrypoint.md and every file it imports.\n")
    _write(root / ".forge" / "entrypoint.md", "Framing sentence.\n\n@.forge/review-gate.md\n")
    _write(root / ".forge" / "review-gate.md", "The review gate rule.\n")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPTS_DIR / "check_forge_entrypoint.py", root / "scripts" / "check_forge_entrypoint.py")
    _write(root / ".pre-commit-config.yaml", f"repos:\n  - repo: local\n    hooks:\n{hook_block}\n")
    env = clean_git_env()
    subprocess.run(["git", "add", "."], cwd=root, check=True, env=env)
    subprocess.run(["git", "commit", "--quiet", "-m", "init"], cwd=root, check=True, env=env)


def _build_skills_lock_fixture(root: Path, hook_block: str) -> None:
    """A minimal vendored-skill tree with one lock entry, plus a
    `.pre-commit-config.yaml` carrying only the extracted `skills-lock`
    hook, committed as a real git history. The lock entry's `computedHash`
    is deliberately wrong -- irrelevant here, since deleting the whole
    skill directory it names fails the "does not exist" check before any
    hash is ever compared."""
    _init_git_repo(root)
    _write(
        root / ".agents" / "skills" / "example-skill" / "SKILL.md",
        "---\nname: example-skill\n---\n\n<!-- Source: https://example.invalid/example-skill -->\n",
    )
    _write(
        root / "skills-lock.json",
        '{\n  "skills": {\n    "example-skill": {\n      "computedHash": "0" }\n  }\n}\n',
    )
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPTS_DIR / "check_skills_lock.py", root / "scripts" / "check_skills_lock.py")
    _write(root / ".pre-commit-config.yaml", f"repos:\n  - repo: local\n    hooks:\n{hook_block}\n")
    env = clean_git_env()
    subprocess.run(["git", "add", "."], cwd=root, check=True, env=env)
    subprocess.run(["git", "commit", "--quiet", "-m", "init"], cwd=root, check=True, env=env)


def _run_hook_on_staged_deletion(root: Path, hook_id: str, delete: Path) -> subprocess.CompletedProcess[str]:
    """Delete `delete`, stage the deletion (so nothing is left unstaged for
    pre-commit to stash away before running), and run the named hook the
    way `git commit` would."""
    env = clean_git_env()
    if delete.is_dir():
        shutil.rmtree(delete)
    else:
        delete.unlink()
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    return subprocess.run(
        ["pre-commit", "run", hook_id, "--hook-stage", "pre-commit"],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


# (hook id, fixture builder, path under root to delete), one case per
# always_run hook this test guards.
CASES = (
    ("forge-entrypoint", _build_forge_entrypoint_fixture, Path(".forge", "entrypoint.md")),
    ("forge-entrypoint", _build_forge_entrypoint_fixture, Path("CLAUDE.md")),
    ("skills-lock", _build_skills_lock_fixture, Path(".agents", "skills", "example-skill")),
)


class HookFiresOnDeletion(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_every_case_declares_always_run(self) -> None:
        for hook_id, _builder, delete in CASES:
            with self.subTest(hook=hook_id, delete=delete):
                block = _hook_block(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"), hook_id)
                # The cheap half of this guard: if a future edit drops
                # always_run from a shipped hook, this fails with no
                # pre-commit invocation needed at all.
                self.assertRegex(block, r"always_run:\s*true", f"{hook_id} must declare always_run: true")

    def test_each_hook_fails_a_staged_deletion_of_its_own_guarded_path(self) -> None:
        for hook_id, builder, delete in CASES:
            with self.subTest(hook=hook_id, delete=delete):
                root = self.root / f"{hook_id}-{delete.name}"
                root.mkdir()
                block = _hook_block(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"), hook_id)
                builder(root, block)
                result = _run_hook_on_staged_deletion(root, hook_id, root / delete)
                self.assertNotEqual(
                    result.returncode,
                    0,
                    f"{hook_id} must fail on a staged deletion of {delete}; got:\n"
                    f"stdout={result.stdout}\nstderr={result.stderr}",
                )
                self.assertNotIn(
                    "Skipped", result.stdout, "a Skipped result means the deletion was never passed to the check"
                )

    def test_guard_removal_without_always_run_the_same_deletions_are_skipped(self) -> None:
        # Confirms this test can tell the fix from the bug: strip
        # always_run from each extracted block and the exact pre-fix false
        # pass returns.
        for hook_id, builder, delete in CASES:
            with self.subTest(hook=hook_id, delete=delete):
                root = self.root / f"{hook_id}-{delete.name}-guard-removal"
                root.mkdir()
                block = _hook_block(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"), hook_id)
                without_always_run = re.sub(r"^\s*always_run:\s*true\s*$\n?", "", block, flags=re.MULTILINE)
                self.assertNotIn("always_run", without_always_run)
                builder(root, without_always_run)
                result = _run_hook_on_staged_deletion(root, hook_id, root / delete)
                self.assertEqual(
                    result.returncode, 0, "without always_run, pre-commit must see no staged file to check"
                )
                self.assertIn("Skipped", result.stdout)


if __name__ == "__main__":
    unittest.main()
