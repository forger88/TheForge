"""Guard test: every documented `copier update ... --data <answer>=<value>`
command carries `--defaults`.

Run standalone: python3 template/scripts/test_copier_update_defaults.py

Without `--defaults`, Copier re-asks every other question when it updates a
project, and a non-interactive agent session has no TTY to answer them, so
the command dies with `EOFError` instead of applying the one change it
documents. This is prose an agent reads and a human copies, not executable
code, so this test pins the exact command text in each file that documents
one, so a later edit can't silently drop the flag again.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jinja_paths import rendered_or_jinja  # noqa: E402

# Each file known to document a copier update --data command.
FILES_WITH_DATA_COMMANDS = (
    rendered_or_jinja(".forge", "ci-and-checks.md"),
    rendered_or_jinja(".forge", "code-shape-rules.md"),
)

FORGE_SYNC_SKILL = rendered_or_jinja(".agents", "skills", "forge-sync", "SKILL.md")

# A documented copier update invocation: the literal command, not prose that
# merely mentions "copier update" in passing (those don't need --defaults).
COPIER_UPDATE_COMMAND = re.compile(r"`?copier update --trust\b[^`\n]*`?")

# A same-line double-quoted span, e.g. a quoted title in prose like
# `The note "...copier update --trust needs a pre-run check" explains why.`
# Such a title can mention the bare command conceptually, with no flags at
# all, without documenting it as something to run -- stripped before the
# scan so it can't be mistaken for one (it isn't inside backticks, so
# COPIER_UPDATE_COMMAND's own quoting marker can't tell the two apart).
QUOTED_SPAN = re.compile(r'"[^"\n]*"')


def _unquoted(text: str) -> str:
    return QUOTED_SPAN.sub("", text)


class UnquotedStripsSameLineDoubleQuotedSpans(unittest.TestCase):
    def test_a_quoted_issue_title_mentioning_the_bare_command_is_stripped(self) -> None:
        text = (
            'The note "some-skill: add a pre-run check before copier update '
            '--trust runs upstream tasks" explains why none exists yet.'
        )
        self.assertEqual(COPIER_UPDATE_COMMAND.findall(_unquoted(text)), [])

    def test_a_real_fenced_command_with_no_quotes_on_its_line_is_kept(self) -> None:
        text = "copier update --trust --defaults --skip-tasks --conflict inline"
        self.assertEqual(
            COPIER_UPDATE_COMMAND.findall(_unquoted(text)),
            ["copier update --trust --defaults --skip-tasks --conflict inline"],
        )


class DocumentedCopierUpdateCommandsCarryDefaults(unittest.TestCase):
    def test_data_commands_carry_defaults(self) -> None:
        for path in FILES_WITH_DATA_COMMANDS:
            text = _unquoted(path.read_text(encoding="utf-8"))
            commands = [
                m.group(0) for m in COPIER_UPDATE_COMMAND.finditer(text) if "--data" in m.group(0)
            ]
            self.assertTrue(
                commands,
                f"{path.name} no longer documents a `copier update ... --data` "
                "command; update this test if that command moved or was removed "
                "deliberately",
            )
            for command in commands:
                self.assertIn(
                    "--defaults",
                    command,
                    f"{path.name}: {command!r} is missing --defaults, so it dies "
                    "with EOFError in a non-interactive session instead of "
                    "applying the documented change",
                )

    def test_forge_sync_skill_carries_defaults(self) -> None:
        text = _unquoted(FORGE_SYNC_SKILL.read_text(encoding="utf-8"))
        commands = [m.group(0) for m in COPIER_UPDATE_COMMAND.finditer(text)]
        self.assertTrue(
            commands, "forge-sync's SKILL.md no longer documents a `copier update` command"
        )
        for command in commands:
            self.assertIn(
                "--defaults",
                command,
                f"forge-sync: {command!r} is missing --defaults, so the sync "
                "dies with EOFError in a non-interactive session",
            )


if __name__ == "__main__":
    sys.exit(unittest.main())
