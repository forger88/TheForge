"""Guard test: the stage-0 `project-lint` placeholder hook in
`.pre-commit-config.yaml[.jinja]` must never be able to invoke `pre-commit`
itself, however any copier answer might render.

The hook is `always_run: true`, so any top-level `pre-commit run --all-files`
(or any `pre-commit run <id>` that includes it) runs it. If its executable
fields (`entry`/`args`) ever shell back out to `pre-commit` -- directly, or
indirectly by being wired to a copier variable such as `lint_command` whose
natural answer for a project that enforces lint through its own pre-commit
hook is itself `pre-commit run --all-files` -- it recurses with no base case.
Confirmed in the sandbox: an unguarded version of this hook spawned roughly
150 zombie processes before being killed by hand.

This checks the hook's own executable fields only (not its surrounding
comments, which legitimately mention both terms as explanation), so the
placeholder stays free to describe the hazard in prose without tripping
itself.

Standalone: python3 scripts/test_project_lint_placeholder_no_recursion.py
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


def _pre_commit_config() -> Path:
    """The rendered `.pre-commit-config.yaml` this file ships at in a generated
    project, falling back to the unrendered `.jinja` source when run directly
    against the template tree (as this repo's own test suite does)."""
    root = Path(__file__).resolve().parent.parent
    for candidate in (root / ".pre-commit-config.yaml", root / ".pre-commit-config.yaml.jinja"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"no .pre-commit-config.yaml or .pre-commit-config.yaml.jinja under {root}")


def _project_lint_block(text: str) -> str:
    """The `project-lint` hook's own YAML block: from its `- id:` line up to
    (not including) the next `- id:` line, or the end of the file."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(r"^\s*- id:\s*project-lint\s*$", line)), None)
    if start is None:
        raise AssertionError("no 'project-lint' hook found in .pre-commit-config.yaml[.jinja]")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^\s*- id:", lines[i])),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _executable_lines(block: str) -> list[str]:
    """Non-comment lines of the block -- its actual YAML fields, excluding the
    prose above/around them that may legitimately name `pre-commit` or
    `lint_command` as explanation."""
    return [line for line in block.splitlines() if line.strip() and not line.strip().startswith("#")]


class ProjectLintPlaceholderNeverRecurses(unittest.TestCase):
    def setUp(self) -> None:
        self.block = _project_lint_block(_pre_commit_config().read_text())
        self.executable = _executable_lines(self.block)

    def test_the_hook_block_exists_and_is_nonempty(self) -> None:
        # Guards the extractor itself: an empty result here would make every
        # other assertion in this class pass vacuously.
        self.assertTrue(self.executable, "project-lint hook has no non-comment fields to check")

    def test_no_executable_field_shells_out_to_pre_commit(self) -> None:
        offenders = [line for line in self.executable if "pre-commit" in line.lower()]
        self.assertEqual(
            offenders,
            [],
            "project-lint's own entry/args must never invoke pre-commit itself, or it recurses "
            f"with no base case once pre-commit runs it; found: {offenders}",
        )

    def test_no_executable_field_is_driven_by_the_lint_command_answer(self) -> None:
        # However safe today's `lint_command` default is, wiring the hook to
        # it at all re-opens the hazard the moment a project answers that
        # question with its own pre-commit invocation -- exactly what a
        # project whose lint IS its pre-commit hook naturally answers.
        offenders = [line for line in self.executable if "lint_command" in line.lower()]
        self.assertEqual(
            offenders,
            [],
            f"project-lint's own entry/args must not reference lint_command; found: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
