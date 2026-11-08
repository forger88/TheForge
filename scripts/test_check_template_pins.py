"""Guard tests for scripts/check_template_pins.py.

Standalone: python3 scripts/test_check_template_pins.py

Each test here proves the checker actually fails when a pin in
template/.devcontainer/devcontainer.json.jinja or
template/.github/workflows/*.yml(.jinja) is dropped or weakened to a
floating tag, not only that it passes on the clean tree today.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_template_pins  # noqa: E402

import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_template_pins.py"


class RealTreeIsClean(unittest.TestCase):
    """The checker must pass against this repository's own template/ as it stands."""

    def test_real_template_passes(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class DevcontainerDigestPin(unittest.TestCase):
    """The guard test: a devcontainer image losing its @sha256: pin must go red here."""

    def test_digest_pinned_image_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "devcontainer.json.jinja"
            path.write_text('{\n  "image": "mcr.microsoft.com/devcontainers/base:ubuntu-24.04@sha256:' + "a" * 64 + '"\n}\n')
            with mock.patch.object(check_template_pins, "DEVCONTAINER", path):
                self.assertEqual(check_template_pins.check_devcontainer(), [])

    def test_floating_tag_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "devcontainer.json.jinja"
            path.write_text('{\n  "image": "mcr.microsoft.com/devcontainers/base:ubuntu-24.04"\n}\n')
            with mock.patch.object(check_template_pins, "DEVCONTAINER", path):
                self.assertNotEqual(check_template_pins.check_devcontainer(), [])

    def test_short_or_malformed_digest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "devcontainer.json.jinja"
            path.write_text('{\n  "image": "mcr.microsoft.com/devcontainers/base:ubuntu-24.04@sha256:deadbeef"\n}\n')
            with mock.patch.object(check_template_pins, "DEVCONTAINER", path):
                self.assertNotEqual(check_template_pins.check_devcontainer(), [])

    def test_missing_file_fails(self):
        with mock.patch.object(check_template_pins, "DEVCONTAINER", Path("/nonexistent/devcontainer.json.jinja")):
            self.assertNotEqual(check_template_pins.check_devcontainer(), [])


class WorkflowActionPin(unittest.TestCase):
    """The guard test: a workflow action losing its full-SHA pin must go red here."""

    def test_full_sha_pinned_action_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflows = Path(tmp)
            (workflows / "ci.yml").write_text("steps:\n  - uses: actions/checkout@" + "1" * 40 + " # v4.2.2\n")
            with mock.patch.object(check_template_pins, "WORKFLOWS_DIR", workflows):
                self.assertEqual(check_template_pins.check_workflows(), [])

    def test_floating_tag_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflows = Path(tmp)
            (workflows / "ci.yml").write_text("steps:\n  - uses: actions/checkout@v4\n")
            with mock.patch.object(check_template_pins, "WORKFLOWS_DIR", workflows):
                self.assertNotEqual(check_template_pins.check_workflows(), [])

    def test_short_sha_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflows = Path(tmp)
            (workflows / "ci.yml").write_text("steps:\n  - uses: actions/checkout@11bd719\n")
            with mock.patch.object(check_template_pins, "WORKFLOWS_DIR", workflows):
                self.assertNotEqual(check_template_pins.check_workflows(), [])

    def test_no_ref_at_all_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflows = Path(tmp)
            (workflows / "ci.yml").write_text("steps:\n  - uses: actions/checkout\n")
            with mock.patch.object(check_template_pins, "WORKFLOWS_DIR", workflows):
                self.assertNotEqual(check_template_pins.check_workflows(), [])

    def test_jinja_workflow_files_are_scanned_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflows = Path(tmp)
            (workflows / "tests.yml.jinja").write_text("steps:\n  - uses: actions/checkout@v4\n")
            with mock.patch.object(check_template_pins, "WORKFLOWS_DIR", workflows):
                self.assertNotEqual(check_template_pins.check_workflows(), [])

    def test_missing_directory_fails(self):
        with mock.patch.object(check_template_pins, "WORKFLOWS_DIR", Path("/nonexistent/workflows")):
            self.assertNotEqual(check_template_pins.check_workflows(), [])


class MainReturnsExitCode(unittest.TestCase):
    def test_main_returns_zero_on_clean_tree(self):
        self.assertEqual(check_template_pins.main(), 0)

    def test_main_returns_one_on_failure(self):
        with mock.patch.object(check_template_pins, "check_devcontainer", return_value=["fake failure"]):
            self.assertEqual(check_template_pins.main(), 1)


if __name__ == "__main__":
    unittest.main()
