"""Guard tests for _git_subprocess.py's clean_git_env().

Standalone: python3 scripts/test__git_subprocess.py

The regression this guards: a pre-commit hook invoked by `git commit`
(rather than a standalone `pre-commit run`) has GIT_DIR/GIT_INDEX_FILE
(and, under a core.hooksPath override, the GIT_CONFIG_* family) set in
its own environment by git, and these propagate to every subprocess the
hook spawns -- including a nested git command meant for an unrelated
throwaway repository. Found building TheForge's own render-check script:
a standalone `pre-commit run --all-files` passed cleanly, but the same
hook triggered by a real `git commit` corrupted the invoking repository's
real index and local git identity, because check_forge_drift.py's and
check_sync_duplicates.py's own test fixtures (which `git init`/`git
add`/`git commit` their own temp repos) inherited the leaked variables.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import (  # noqa: E402
    authenticated_url,
    clean_git_env,
    copier_yml_at,
    resolve_sync_target,
)

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SUBPROCESS_CALL_NAMES = frozenset(("run", "Popen", "check_call", "check_output", "call"))


class CleanGitEnv(unittest.TestCase):
    def test_strips_git_dir_and_index_file(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"GIT_DIR": "/some/repo/.git", "GIT_INDEX_FILE": "/some/repo/.git/index"},
        ):
            env = clean_git_env()
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("GIT_INDEX_FILE", env)

    def test_strips_work_tree_object_dir_common_dir_and_prefix(self) -> None:
        leaked = {
            "GIT_WORK_TREE": "/some/repo",
            "GIT_OBJECT_DIRECTORY": "/some/repo/.git/objects",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/other/objects",
            "GIT_COMMON_DIR": "/some/repo/.git",
            "GIT_PREFIX": "sub/dir/",
        }
        with mock.patch.dict("os.environ", leaked):
            env = clean_git_env()
        for name in leaked:
            self.assertNotIn(name, env, f"{name} must be stripped")

    def test_strips_a_core_hookspath_overrides_numbered_config_family(self) -> None:
        # The exact shape git sets when a core.hooksPath override is in
        # effect: a count plus one GIT_CONFIG_KEY_<n>/GIT_CONFIG_VALUE_<n>
        # pair per overridden setting.
        with mock.patch.dict(
            "os.environ",
            {
                "GIT_CONFIG_PARAMETERS": "'core.hooksPath'='/some/hooks'",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.hooksPath",
                "GIT_CONFIG_VALUE_0": "/some/hooks",
            },
        ):
            env = clean_git_env()
        self.assertNotIn("GIT_CONFIG_PARAMETERS", env)
        self.assertNotIn("GIT_CONFIG_COUNT", env)
        self.assertNotIn("GIT_CONFIG_KEY_0", env)
        self.assertNotIn("GIT_CONFIG_VALUE_0", env)

    def test_keeps_benign_git_variables(self) -> None:
        # GIT_SSL_CAINFO (a corporate CA bundle), GIT_ASKPASS and
        # GIT_TERMINAL_PROMPT don't redirect a command at a different
        # repository, so a nested git command run through run_git or a
        # test fixture still needs them.
        kept = {
            "GIT_SSL_CAINFO": "/etc/ssl/ca-bundle.crt",
            "GIT_ASKPASS": "",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "Test",
        }
        with mock.patch.dict("os.environ", kept):
            env = clean_git_env()
        for name, value in kept.items():
            self.assertEqual(env.get(name), value, f"{name} must be kept as-is")

    def test_keeps_non_git_variables(self) -> None:
        with mock.patch.dict("os.environ", {"PATH": "/usr/bin", "HOME": "/root"}):
            env = clean_git_env()
        self.assertIn("PATH", env)
        self.assertIn("HOME", env)


_JINJA_EXPR_RE = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_JINJA_STMT_RE = re.compile(r"\{%.*?%\}", re.DOTALL)


def _strip_jinja(source: str) -> str:
    """A `.py.jinja` script source is otherwise-valid Python with Jinja
    expressions/statements spliced in (e.g. `MAX = {{ max_module_lines }}`);
    swap each for a same-length-irrelevant placeholder so `ast.parse` can
    still read the surrounding Python. Only `*.py.jinja` files in this
    directory go through this path -- good enough for them without being a
    general Jinja-in-Python parser."""
    source = _JINJA_EXPR_RE.sub("0", source)
    return _JINJA_STMT_RE.sub("", source)


def _bare_git_subprocess_calls(path: Path) -> list[int]:
    """Line numbers of every `subprocess.run(["git", ...], ...)`-shaped call
    in `path` with no `env=` keyword at all -- the shape that silently
    inherits a leaked GIT_DIR/GIT_INDEX_FILE from a `git commit`-triggered
    pre-commit hook (see this file's module docstring). A call that does
    pass `env=` is left to the reviewer: it might pass `clean_git_env()`
    directly, or build on it (`{**clean_git_env(), ...}`, as `run_git`
    does), and distinguishing those from a replacement bare dict by syntax
    alone would be unreliable -- this check's job is to catch the *no env
    at all* case a new script can reintroduce, not to re-review every env
    expression.
    """
    text = path.read_text(encoding="utf-8")
    if path.name.endswith(".py.jinja"):
        text = _strip_jinja(text)
    tree = ast.parse(text, filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name not in _SUBPROCESS_CALL_NAMES:
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if not isinstance(first_arg, ast.List) or not first_arg.elts:
            continue
        first_elt = first_arg.elts[0]
        if not (isinstance(first_elt, ast.Constant) and first_elt.value == "git"):
            continue
        if not any(kw.arg == "env" for kw in node.keywords):
            lines.append(node.lineno)
    return lines


class EveryGitSubprocessCallPassesAnEnv(unittest.TestCase):
    """A consumer-project incident, this module's own docstring, traced to a
    script or test fixture under scripts/ that spawned `git` with no `env=`
    at all: it inherited leaked GIT_* variables a `git commit`-triggered
    pre-commit hook set, and silently corrupted the invoking repository
    instead of its own throwaway fixture. This doesn't require every call
    to use `clean_git_env()` specifically (`run_git` builds on it, for
    instance) -- only that no call is left with no `env=` at all, which is
    the gap that actually caused that incident."""

    def test_no_script_spawns_git_with_the_ambient_environment(self) -> None:
        offenders = {}
        paths = sorted(_SCRIPTS_DIR.glob("*.py")) + sorted(_SCRIPTS_DIR.glob("*.py.jinja"))
        for path in paths:
            lines = _bare_git_subprocess_calls(path)
            if lines:
                offenders[path.name] = lines
        self.assertEqual(
            offenders,
            {},
            "these subprocess.run(['git', ...]) calls pass no env= at all, so they "
            "inherit any leaked GIT_DIR/GIT_INDEX_FILE from a git-commit-triggered "
            "pre-commit hook: pass env=clean_git_env() (or build on it, as run_git "
            "does) at each line listed above.",
        )


class ResolveSyncTargetFailsClosed(unittest.TestCase):
    """An unreachable remote is None, never a silent fall back to HEAD."""

    def _run(self, head_rc: int, tags_rc: int):
        import subprocess

        def fake(args, timeout):
            if "--tags" in args:
                return subprocess.CompletedProcess(args, tags_rc, stdout="", stderr="")
            return subprocess.CompletedProcess(args, head_rc, stdout="abc123 HEAD\n" if head_rc == 0 else "", stderr="")

        return resolve_sync_target("u", 1, fake)

    def test_unreachable_head_is_none(self):
        self.assertIsNone(self._run(head_rc=1, tags_rc=0))

    def test_failed_tag_listing_is_none_not_head(self):
        self.assertIsNone(self._run(head_rc=0, tags_rc=1))

    def test_reachable_with_no_tags_is_head(self):
        target = self._run(head_rc=0, tags_rc=0)
        self.assertEqual((target.ref, target.sha, target.tagged), ("HEAD", "abc123", False))


class CopierYmlAt(unittest.TestCase):
    """The shared `copier.yml`/`copier.yaml`-at-a-rev primitive both
    check_forge_drift.py and check_forge_sync_trust_diff.py read through
    their own module-level `run_git`, via `runner`."""

    def _fake(self, found_under: str | None):
        import subprocess

        calls = []

        def fake_runner(args, timeout):
            calls.append(args)
            config_name = args[-1].split(":", 1)[1]
            if config_name == found_under:
                return subprocess.CompletedProcess(args, 0, stdout="_tasks: []\n", stderr="")
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="fatal: not found")

        return fake_runner, calls

    def test_found_under_copier_yml(self):
        fake_runner, calls = self._fake("copier.yml")
        text = copier_yml_at("/repo", "abc123", 5, fake_runner)
        self.assertEqual(text, "_tasks: []\n")
        self.assertEqual(calls[0][-1], "abc123:copier.yml")

    def test_found_under_copier_yaml_when_copier_yml_is_absent(self):
        fake_runner, calls = self._fake("copier.yaml")
        text = copier_yml_at("/repo", "abc123", 5, fake_runner)
        self.assertEqual(text, "_tasks: []\n")
        self.assertEqual([c[-1] for c in calls], ["abc123:copier.yml", "abc123:copier.yaml"])

    def test_none_when_neither_exists(self):
        fake_runner, _ = self._fake(None)
        self.assertIsNone(copier_yml_at("/repo", "abc123", 5, fake_runner))

    def test_end_of_options_precedes_the_rev(self):
        fake_runner, calls = self._fake("copier.yml")
        copier_yml_at("/repo", "abc123", 5, fake_runner)
        args = calls[0]
        self.assertEqual(args[args.index("--end-of-options") + 1], "abc123:copier.yml")


class AuthenticatedUrl(unittest.TestCase):
    def test_embeds_token_as_https_userinfo(self):
        self.assertEqual(
            authenticated_url("https://github.com/forger88/TheForgeStaging.git", "tok"),
            "https://x-access-token:tok@github.com/forger88/TheForgeStaging.git",
        )

    def test_empty_token_returns_url_unchanged(self):
        url = "https://github.com/forger88/TheForgeStaging.git"
        self.assertEqual(authenticated_url(url, ""), url)

    def test_ssh_url_is_unchanged(self):
        url = "git@github.com:forger88/TheForgeStaging.git"
        self.assertEqual(authenticated_url(url, "tok"), url)

    def test_local_path_is_unchanged(self):
        self.assertEqual(authenticated_url("/tmp/some/clone", "tok"), "/tmp/some/clone")

    def test_url_already_carrying_userinfo_is_unchanged(self):
        url = "https://x-access-token:other@github.com/forger88/TheForgeStaging.git"
        self.assertEqual(authenticated_url(url, "tok"), url)

    def test_unparsable_url_is_unchanged(self):
        # A malformed IPv6-shaped host urlsplit rejects outright, same
        # trigger display_url's own "unparsable" branch guards against.
        url = "https://[::1/repo.git"
        self.assertEqual(authenticated_url(url, "tok"), url)

    def test_round_trips_through_display_url(self):
        from _git_subprocess import display_url

        url = "https://github.com/forger88/TheForgeStaging.git"
        self.assertEqual(display_url(authenticated_url(url, "tok")), url)


if __name__ == "__main__":
    sys.exit(unittest.main())
