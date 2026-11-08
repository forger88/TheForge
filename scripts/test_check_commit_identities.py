"""Guard tests for check-commit-identities.sh.

Standalone, standard-library-only:

    python3 scripts/test_check_commit_identities.py
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check-commit-identities.sh"


def run_check(text: str, filename: str = "identities") -> subprocess.CompletedProcess:
    """filename="identities" exercises strict mode (every non-blank line must be a
    no-reply-shaped "Name <email>" identity); any other name exercises the lenient
    mode used for free-form commit/PR text, where only Co-authored-by trailers are
    checked and other prose is left alone."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / filename
        target.write_text(text)
        return subprocess.run(
            [str(CHECK), str(target)],
            env={"PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
        )


class StrictModeNoReplyIdentitiesPass(unittest.TestCase):
    """filename "identities": every non-blank line must be a no-reply-shaped identity."""

    def test_platform_committer_passes(self) -> None:
        result = run_check("GitHub <noreply@github.com>\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_merging_accounts_github_alias_passes(self) -> None:
        # 12345 is an invented placeholder ID, not a real GitHub account.
        result = run_check("Example Owner <12345+exampleowner@users.noreply.github.com>\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_users_noreply_without_numeric_prefix_passes(self) -> None:
        result = run_check("Example Owner <exampleowner@users.noreply.github.com>\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_harness_bot_identity_passes(self) -> None:
        result = run_check("Claude <noreply@anthropic.com>\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_two_good_identity_lines_pass(self) -> None:
        result = run_check(
            "Example Owner <12345+exampleowner@users.noreply.github.com>\nGitHub <noreply@github.com>\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class StrictModePersonalOrMalformedLinesFail(unittest.TestCase):
    def test_a_personal_address_identity_line_fails(self) -> None:
        result = run_check("Jane Doe <jane.doe@gmail.com>\n")
        self.assertEqual(result.returncode, 1)

    def test_a_github_noreply_lookalike_domain_fails(self) -> None:
        """A personal address at a domain that merely contains the GitHub no-reply
        shape as a substring must not pass -- the match has to be the full domain."""
        result = run_check("Jane Doe <jane@users.noreply.github.com.evil.example>\n")
        self.assertEqual(result.returncode, 1)

    def test_a_noreply_lookalike_local_part_fails(self) -> None:
        """"noreply" has to be the whole local part, not merely a prefix of it."""
        result = run_check("Jane Doe <noreply.jane@example.com>\n")
        self.assertEqual(result.returncode, 1)

    def test_a_line_with_no_email_at_all_fails_closed(self) -> None:
        """The identities file is machine-generated, one "Name <email>" line per
        commit author/committer; a line that doesn't even have that shape is a
        finding, not something to silently skip."""
        result = run_check("malformed line with no angle brackets at all\n")
        self.assertEqual(result.returncode, 1)

    def test_an_empty_email_fails_closed(self) -> None:
        result = run_check("Jane Doe <>\n")
        self.assertEqual(result.returncode, 1)

    def test_output_never_prints_the_matched_address(self) -> None:
        result = run_check("Jane Doe <jane.doe@gmail.com>\n")
        self.assertNotIn("jane.doe@gmail.com", result.stdout + result.stderr)
        self.assertIn("identities:1", result.stdout + result.stderr)


class LenientModeForFreeFormText(unittest.TestCase):
    """Any filename other than "identities": only Co-authored-by trailers are
    checked; other prose, including a line that merely contains "<...>", passes."""

    def test_ordinary_prose_line_passes(self) -> None:
        result = run_check("This commit fixes a bug in the merge-text scanner.\n", filename="commits")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prose_with_an_unrelated_angle_bracket_tag_passes(self) -> None:
        """A commit message or PR body is not held to the strict identity shape:
        it may legitimately contain "<...>" that is not an identity at all."""
        result = run_check("See the <placeholder> tag in the rendered template.\n", filename="squash-scanned")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_noreply_co_authored_by_trailer_passes(self) -> None:
        result = run_check("Co-authored-by: Claude <noreply@anthropic.com>\n", filename="commits")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_lowercase_co_authored_by_trailer_passes(self) -> None:
        result = run_check("co-authored-by: Claude <noreply@anthropic.com>\n", filename="commits")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_personal_address_in_a_co_authored_by_trailer_fails(self) -> None:
        result = run_check("Co-authored-by: Jane Doe <jane.doe@gmail.com>\n", filename="commits")
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
