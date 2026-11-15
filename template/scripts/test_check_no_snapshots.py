"""Guard tests for check_no_snapshots.py, run standalone: python3 scripts/test_check_no_snapshots.py"""

from __future__ import annotations

import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_no_snapshots  # noqa: E402

def _pre_commit_config() -> Path:
    """The rendered `.pre-commit-config.yaml` this file ships at in a generated
    project, falling back to the unrendered `.jinja` source when run directly
    against the template tree (as this repo's own test suite does)."""
    root = Path(__file__).resolve().parent.parent
    for candidate in (root / ".pre-commit-config.yaml", root / ".pre-commit-config.yaml.jinja"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"no .pre-commit-config.yaml or .pre-commit-config.yaml.jinja under {root}")


PRE_COMMIT_CONFIG = _pre_commit_config()
PYPROJECT = """\
[project]
name = "example"
dependencies = [
    "httpx==0.28.1",
]

[dependency-groups]
dev = [
{entry}
    "pytest==8.4.2",
]
"""
LOCK = """\
[[package]]
name = "pytest"
version = "8.4.2"

[[package]]
{entry}
version = "4.9.1"
"""


def hook_files_pattern(hook_id: str) -> str:
    """The `files:` regex of one hook in the rendered pre-commit config, read without a YAML parser."""
    text = PRE_COMMIT_CONFIG.read_text(encoding="utf-8")
    block = text.split(f"- id: {hook_id}\n", 1)[1].split("- id: ", 1)[0]
    return re.search(r"^\s*files:\s*(\S+)\s*$", block, re.M).group(1)


class JsSnapshotAssertion(unittest.TestCase):
    """The JS/TS snapshot-assertion pattern, fed an actual .test.ts file."""

    def check(self, name: str, text: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(text, encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                return check_no_snapshots.main([str(path)])

    def test_each_snapshot_assertion_fails(self) -> None:
        for assertion in (
            "toMatchSnapshot",
            "toMatchInlineSnapshot",
            "toThrowErrorMatchingSnapshot",
            "toThrowErrorMatchingInlineSnapshot",
            "toMatchFileSnapshot",
            "toHaveScreenshot",
            "toMatchAriaSnapshot",
            "toMatchImageSnapshot",
        ):
            with self.subTest(assertion=assertion):
                self.assertEqual(self.check("widget.test.ts", f"expect(value).{assertion}();\n"), 1)

    def test_a_lookalike_assertion_passes(self) -> None:
        self.assertEqual(self.check("widget.test.ts", "expect(value).toMatchObject({});\n"), 0)


class DependencyFiles(unittest.TestCase):
    def check(self, name: str, text: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(text, encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                return check_no_snapshots.main([str(path)])

    def test_a_quoted_snapshot_dependency_in_pyproject_fails(self) -> None:
        for entry in (
            '    "syrupy==4.9.1",',
            '    "syrupy",',
            "    'syrupy>=4',",
            '    "syrupy[extra]==4.9.1",',
            '    "syrupy (>=4)",',
            '    "SnapshotTest==0.6.0",',
            '    "pytest-snapshot==0.9.0",',
            '    "pytest_snapshot",',
            '    "approvaltests ; python_version >= \'3.9\'",',
            '    "approvaltests-minimal==1.0",',
            '    "pytest-insta==0.3.0",',
            '    "inline-snapshot==0.20",',
            '    "inline_snapshot",',
            '    "pytest-image-snapshot==0.4",',
            '    "pytest-golden==0.2",',
            '    "pytest-regressions==2.5",',
            '    "pytest-approvaltests==0.2",',
            '    "pytest-approval==0.1",',
        ):
            with self.subTest(entry=entry):
                self.assertEqual(self.check("pyproject.toml", PYPROJECT.format(entry=entry)), 1)

    def test_a_snapshot_package_in_a_lock_file_fails(self) -> None:
        for lock in ("uv.lock", "poetry.lock", "pdm.lock"):
            for entry in ('name = "syrupy"', 'name = "inline-snapshot"', 'name = "pytest-regressions"'):
                with self.subTest(lock=lock, entry=entry):
                    self.assertEqual(self.check(lock, LOCK.format(entry=entry)), 1)

    def test_a_banned_name_in_another_packages_extras_passes(self) -> None:
        # A TOML lock file's own `[package.extras]` block can name a banned
        # package as another package's optional, never-installed extra,
        # quoted the same way a real pin would be. Only a package's own
        # `name = "..."` line is a real dependency.
        extras_lock = (
            '[[package]]\n'
            'name = "markdown-it-py"\n'
            'version = "3.0.0"\n\n'
            "[package.extras]\n"
            'testing = ["coverage", "pytest", "pytest-cov", "pytest-regressions"]\n'
        )
        for lock in ("uv.lock", "poetry.lock", "pdm.lock"):
            with self.subTest(lock=lock):
                self.assertEqual(self.check(lock, extras_lock), 0)

    def test_a_snapshot_package_in_a_pipfile_fails(self) -> None:
        self.assertEqual(self.check("Pipfile", '[dev-packages]\nsyrupy = "==4.9.1"\n'), 1)
        self.assertEqual(self.check("Pipfile.lock", '{"develop": {"syrupy": {"version": "==4.9.1"}}}\n'), 1)

    def test_a_quoted_key_pipfile_entry_fails(self) -> None:
        self.assertEqual(self.check("Pipfile", '[dev-packages]\n"syrupy" = "==4.9.1"\n'), 1)

    def test_a_quoted_snapshot_dependency_in_setup_py_fails(self) -> None:
        source = (
            "from setuptools import setup\n\n"
            "setup(\n"
            "    name='example',\n"
            "    extras_require={'test': ['syrupy==4.9.1']},\n"
            ")\n"
        )
        self.assertEqual(self.check("setup.py", source), 1)

    def test_a_snapshot_dependency_in_setup_cfg_fails(self) -> None:
        self.assertEqual(self.check("setup.cfg", "[options.extras_require]\ntest =\n    syrupy==4.9.1\n"), 1)

    def test_a_single_line_setup_cfg_dependency_fails(self) -> None:
        self.assertEqual(self.check("setup.cfg", "[options]\ninstall_requires = syrupy==4.9.1\n"), 1)

    def test_a_semicolon_separated_setup_cfg_dependency_fails(self) -> None:
        self.assertEqual(self.check("setup.cfg", "[options]\ninstall_requires = foo==1.0; syrupy==4.9.1\n"), 1)

    def test_an_ordinary_single_line_setup_cfg_dependency_passes(self) -> None:
        self.assertEqual(self.check("setup.cfg", "[options]\ninstall_requires = requests==2.32.5\n"), 0)

    def test_a_snapshot_dependency_in_constraints_file_fails(self) -> None:
        self.assertEqual(self.check("constraints-dev.txt", "pytest==8.4.2\nsyrupy==4.9.1\n"), 1)

    def test_a_js_snapshot_package_in_package_json_fails(self) -> None:
        for entry in ('"jest-image-snapshot": "^6.4.0"', '"jest-specific-snapshot": "^3.0.0"', '"snapshot-diff": "^0.10.0"'):
            with self.subTest(entry=entry):
                body = "{\n  \"devDependencies\": {\n    " + entry + "\n  }\n}\n"
                self.assertEqual(self.check("package.json", body), 1)

    def test_an_ordinary_package_json_dependency_passes(self) -> None:
        self.assertEqual(self.check("package.json", '{\n  "devDependencies": {\n    "jest": "^29.0.0"\n  }\n}\n'), 0)

    def test_a_comma_separated_import_fails(self) -> None:
        self.assertEqual(self.check("conftest.py", "import os, syrupy\n"), 1)

    def test_a_pip_editable_egg_reference_fails(self) -> None:
        # Built via concatenation: the unsplit fixture is itself a match for this hook.
        egg_line = "-e git+https://example.invalid/syrupy.git#egg=" + "syrupy\n"
        self.assertEqual(self.check("requirements-dev.txt", egg_line), 1)

    def test_a_pytest_plugins_registration_fails(self) -> None:
        # Split for the same reason as the egg reference above.
        plugins_line = "pytest" + "_plugins = [\"syrupy\"]\n"
        self.assertEqual(self.check("conftest.py", plugins_line), 1)

    def test_a_pytest_plugins_tuple_or_bare_string_registration_fails(self) -> None:
        # Split for the same reason as test_a_pytest_plugins_registration_fails above:
        # the unsplit fixture is itself a match for this hook's generic pattern.
        plugins = "pytest" + "_plugins"
        for suffix in (
            ' = ("syrupy",)\n',
            " = 'syrupy'\n",
            ' = "syrupy"\n',
            ' = ["other_plugin", "syrupy"]\n',
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.check("conftest.py", plugins + suffix), 1)

    def test_a_pytest_addopts_dash_p_registration_fails(self) -> None:
        # Built via concatenation: the unsplit fixture is itself a match for this hook.
        addopts_syrupy = "-p " + "syrupy"
        for name, prefix in (
            ("pytest.ini", "[pytest]\naddopts = "),
            ("tox.ini", "[pytest]\naddopts = "),
            ("pyproject.toml", '[tool.pytest.ini_options]\naddopts = "'),
            ("setup.cfg", "[tool:pytest]\naddopts = "),
        ):
            suffix = '"\n' if name == "pyproject.toml" else "\n"
            with self.subTest(name=name):
                self.assertEqual(self.check(name, prefix + addopts_syrupy + suffix), 1)

    def test_an_ordinary_addopts_line_passes(self) -> None:
        self.assertEqual(self.check("pytest.ini", "[pytest]\naddopts = -p no:cacheprovider\n"), 0)

    def test_a_snapshot_assertion_in_mts_or_cts_fails(self) -> None:
        # Same split JsSnapshotAssertion.test_each_snapshot_assertion_fails uses above,
        # for the same reason: the unsplit fixture is itself a match for this hook.
        assertion = "toMatchSnapshot"
        for name in ("spec.mts", "spec.cts"):
            with self.subTest(name=name):
                self.assertEqual(self.check(name, f"expect(value).{assertion}();\n"), 1)

    def test_ordinary_dependencies_pass(self) -> None:
        self.assertEqual(self.check("pyproject.toml", PYPROJECT.format(entry='    "requests==2.32.5",')), 0)
        for entry in ('name = "syrupy-free"', 'name = "pytest-snapshots-lookalike"'):
            with self.subTest(entry=entry):
                self.assertEqual(self.check("uv.lock", LOCK.format(entry=entry)), 0)

    def test_a_snapshot_requirement_line_fails(self) -> None:
        for entry in ("syrupy==4.9.1", "syrupy[extra]==4.9.1", "syrupy (>=4)", "pytest_insta", "inline-snapshot==0.20"):
            with self.subTest(entry=entry):
                self.assertEqual(self.check("requirements-dev.txt", f"pytest==8.4.2\n{entry}\n"), 1)

    def test_a_lookalike_requirement_line_passes(self) -> None:
        for entry in ("syrupy-free==1", "pytest-snapshots-lookalike==1", "pytest-datadir==1.5", "pytest-approvals==1"):
            with self.subTest(entry=entry):
                self.assertEqual(self.check("requirements-dev.txt", f"pytest==8.4.2\n{entry}\n"), 0)

    def test_a_snapshot_library_import_fails(self) -> None:
        for line in (
            "from syrupy import SnapshotAssertion",
            "import snapshottest",
            "from inline_snapshot import snapshot",
            "import pytest_regressions",
            "from pytest_golden.plugin import GoldenTestFixture",
            "from pytest_image_snapshot import image_snapshot",
            "from pytest_approval import verify",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.check("test_x.py", f"{line}\n"), 1)

    def test_a_quoted_package_name_in_source_code_passes(self) -> None:
        self.assertEqual(self.check("conftest.py", 'PLUGIN = "syrupy"\n'), 0)

    def test_the_hook_runs_on_every_dependency_file(self) -> None:
        files = hook_files_pattern("no-snapshot-assertions")
        for path in (
            "pyproject.toml", "app/pyproject.toml", "uv.lock", "app/poetry.lock", "pdm.lock", "Pipfile", "Pipfile.lock",
            "requirements-dev.txt", "constraints-dev.txt", "package.json", "tests/test_x.py",
            "setup.py", "setup.cfg", "app/setup.cfg", "spec.mts", "spec.cts", "pytest.ini", "tox.ini",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(re.search(files, path))

    def test_the_hook_does_not_pass_filenames(self) -> None:
        """pass_filenames: false, so the checker always runs its own full-tree
        scan instead of re-checking only whatever changed -- including only
        this checker's own source when its patterns are the edit."""
        text = PRE_COMMIT_CONFIG.read_text(encoding="utf-8")
        block = text.split("- id: no-snapshot-assertions\n", 1)[1].split("- id: ", 1)[0]
        self.assertIn("pass_filenames: false", block)


class FullTreeMode(unittest.TestCase):
    """With no argv (as pass_filenames: false always supplies), main() checks every
    git-tracked file, not just whatever file triggered the hook -- so widening a
    pattern here is checked against the whole tree on the very commit that widens it."""

    def check_full_tree(self, sources: dict[str, str]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, body in sources.items():
                path = Path(tmp) / name
                path.write_text(body, encoding="utf-8")
                paths.append(str(path))
            stderr = io.StringIO()
            with (
                mock.patch.object(check_no_snapshots, "tracked_files", return_value=paths),
                contextlib.redirect_stderr(stderr),
            ):
                return check_no_snapshots.main([]), stderr.getvalue()

    def test_no_argv_scans_every_tracked_file(self) -> None:
        code, err = self.check_full_tree({"conftest.py": "import syrupy\n"})
        self.assertEqual(code, 1)
        self.assertIn("conftest.py", err)

    def test_no_argv_with_no_matches_passes(self) -> None:
        code, _ = self.check_full_tree({"conftest.py": "import pytest\n"})
        self.assertEqual(code, 0)

    def test_tracked_files_runs_git_ls_files(self) -> None:
        listing = "scripts/check_no_snapshots.py\nsrc/app/export.py\n"
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout=listing, stderr="")
        with mock.patch.object(check_no_snapshots.subprocess, "run", return_value=done):
            self.assertEqual(
                check_no_snapshots.tracked_files(), ["scripts/check_no_snapshots.py", "src/app/export.py"]
            )

    def test_tracked_files_skips_file_types_the_hook_does_not_trigger_on(self) -> None:
        # A doc that quotes a banned API as an illustrative example (as
        # .agents/skills/tdd/tests.md does) must not trip a full-tree run,
        # since the hook never triggers on it in the first place.
        listing = "docs/guide.md\nscripts/check_no_snapshots.py\nREADME\n"
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout=listing, stderr="")
        with mock.patch.object(check_no_snapshots.subprocess, "run", return_value=done):
            self.assertEqual(check_no_snapshots.tracked_files(), ["scripts/check_no_snapshots.py"])

    def test_tracked_files_skips_vendored_skill_files(self) -> None:
        # Mirrors check_module_size.py.jinja's own VENDORED_PREFIXES exclusion:
        # vendored skill files are third-party code this checker has no
        # allowlist to park a false positive against.
        listing = ".agents/skills/some-skill/scripts/vendored.js\nscripts/check_no_snapshots.py\n"
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout=listing, stderr="")
        with mock.patch.object(check_no_snapshots.subprocess, "run", return_value=done):
            self.assertEqual(check_no_snapshots.tracked_files(), ["scripts/check_no_snapshots.py"])

    def test_tracked_file_filter_matches_the_hook_files_pattern(self) -> None:
        """The full-tree filter's shape mirrors the hook's own `files:` regex
        (self-review part 6: the enforcement scope must stay inside the trigger
        scope); this checks the two haven't drifted apart."""
        files = hook_files_pattern("no-snapshot-assertions")
        for path in (
            "conftest.py", "widget.test.ts", "pyproject.toml", "setup.cfg", "uv.lock", "poetry.lock",
            "pdm.lock", "Pipfile", "Pipfile.lock", "pytest.ini", "tox.ini", "package.json",
            "requirements-dev.txt", "constraints-dev.txt", "spec.mts", "spec.cts",
        ):
            with self.subTest(path=path):
                self.assertEqual(bool(re.search(files, path)), check_no_snapshots._is_scannable(path))
        for path in ("docs/guide.md", "README", "image.png"):
            with self.subTest(path=path):
                self.assertFalse(re.search(files, path))
                self.assertFalse(check_no_snapshots._is_scannable(path))


class SelfCheck(unittest.TestCase):
    """This file itself, run through the hook it tests, must pass: the hook's `files:`
    filter matches every .py file, so an unsplit fixture literal here would trip itself."""

    def test_this_test_file_passes_its_own_hook(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_no_snapshots.main([__file__]), 0)


if __name__ == "__main__":
    unittest.main()
