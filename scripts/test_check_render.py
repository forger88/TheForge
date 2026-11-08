"""Guard test for scripts/check-render.sh.

Standalone: python3 scripts/test_check_render.py

check-render.sh is a shell script that renders the template and runs a
generated project's own guards against it; a real end-to-end run takes
around 15-20 seconds (a full `copier copy` plus the render's own test suite
and pre-commit hooks), too slow to re-run on every guard-script-tests pass
alongside everything else under scripts/. This test instead pins the
script's safety-critical properties statically (issue "Check that a freshly
rendered project passes its own guards"): the manual guard-removal proof
(red on a deliberately broken guard, green once reverted) is recorded on
this fix's own PR instead of repeated here on every run.
"""

from __future__ import annotations

import stat
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-render.sh"


class CheckRenderScript(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_script_exists_and_is_executable(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} must exist")
        mode = SCRIPT.stat().st_mode
        self.assertTrue(
            mode & stat.S_IXUSR, f"{SCRIPT} must be executable (chmod +x), got mode {oct(mode)}"
        )

    def test_fails_fast_on_any_error(self) -> None:
        self.assertIn(
            "set -euo pipefail",
            self.text,
            "check-render.sh must fail fast (set -euo pipefail), or a step that "
            "errors silently could let a later step report a false pass",
        )

    def test_cleans_up_its_temp_directories_on_exit(self) -> None:
        self.assertIn(
            "trap cleanup EXIT",
            self.text,
            "check-render.sh must remove its scratch render and logs on every "
            "exit path, not just a clean one, or repeated runs leak /tmp",
        )

    def test_strips_inherited_git_env_before_rendering(self) -> None:
        # Anchored on the real loop, not a bare substring: when check-render.sh
        # runs as a pre-commit hook invoked by `git commit` (rather than a
        # standalone `pre-commit run`), git sets GIT_DIR/GIT_INDEX_FILE in the
        # hook's environment, and they propagate to every subprocess -- including
        # the render's own nested test fixtures that `git init`/`git add`/`git
        # commit` their own throwaway repos, corrupting this repo's real index
        # instead of their own temp one unless stripped first.
        self.assertIn(
            "done < <(env | grep '^GIT_')",
            self.text,
            "check-render.sh must strip every inherited GIT_* environment "
            "variable before rendering or running any nested git command, or "
            "a pre-commit-hook invocation (git commit) leaks GIT_DIR/"
            "GIT_INDEX_FILE into the render's own test fixtures and corrupts "
            "this repo's real index",
        )
        strip_index = self.text.index("done < <(env | grep '^GIT_')")
        render_index = self.text.index('echo "check-render: rendering into')
        self.assertLess(
            strip_index,
            render_index,
            "the GIT_* strip must run before the render (copier copy) and "
            "everything after it, or a leaked GIT_DIR could still reach a "
            "nested git command",
        )

    def test_unsets_github_token_before_running_the_render_s_tests_and_hooks(self) -> None:
        # Anchored on the real invocation lines, not a bare substring: a
        # comment or message could repeat "env -u GITHUB_TOKEN -u GH_TOKEN"
        # without it actually prefixing the subprocess call (the fresh-review
        # finding this guards against).
        self.assertIn(
            'env -u GITHUB_TOKEN -u GH_TOKEN python3 -m unittest discover',
            self.text,
            "check-render.sh must run the render's guard-script tests with "
            "GITHUB_TOKEN/GH_TOKEN unset, so an ambient token in this "
            "machine's own shell can never make a real GitHub API call",
        )
        self.assertIn(
            "env -u GITHUB_TOKEN -u GH_TOKEN pre-commit run --all-files",
            self.text,
            "check-render.sh must run the render's pre-commit hooks with "
            "GITHUB_TOKEN/GH_TOKEN unset, for the same reason",
        )

    def test_renders_at_head_not_the_latest_tag(self) -> None:
        # Anchored on the real invocation line, not a bare substring: a nearby
        # comment could mention --vcs-ref HEAD without it actually being
        # passed to copier copy. With no --vcs-ref (the default), Copier
        # wraps a dirty working tree into a WIP commit and then checks out
        # the latest PEP 440 tag over it, silently rendering that old tag
        # instead of what's actually being checked, once any tag exists.
        render_line = next(
            line for line in self.text.splitlines() if line.strip().startswith("if ! copier copy")
        )
        self.assertIn(
            "--vcs-ref HEAD",
            render_line,
            "check-render.sh's copier copy invocation must pass --vcs-ref "
            "HEAD, or once any tag exists Copier silently renders that tag "
            "instead of the working tree being checked",
        )

    def test_reads_required_questions_from_copier_yml_rather_than_hardcoding_them(self) -> None:
        self.assertIn(
            '"default" not in spec',
            self.text,
            "check-render.sh must answer every copier.yml question that has no "
            "default by reading copier.yml itself, not a hardcoded list, so a "
            "new required question added later doesn't stop the render",
        )

    def test_parses_rendered_workflows_as_yaml_before_pre_commit(self) -> None:
        # GitHub cannot load a workflow whose YAML does not parse, and no
        # pre-commit hook in the render parses one.
        parse_idx = self.text.find('echo "check-render: parsing the render')
        precommit_idx = self.text.find("running the render's own pre-commit hooks")
        self.assertNotEqual(parse_idx, -1, "check-render.sh must parse rendered workflows as YAML")
        self.assertIn("yaml.safe_load(path.read_text())", self.text)
        self.assertIn("/.github/workflows", self.text)
        self.assertLess(parse_idx, precommit_idx)

    def test_runs_check_document_consistency_against_the_render_after_pre_commit(self) -> None:
        # check_document_consistency.py ships in template/docs/tools/
        # unconditionally, but its pre-commit hook is added only by
        # doc-build-setup's own opt-in step, so a bare render's pre-commit run
        # never exercises it -- this direct invocation is the only thing that
        # catches a broken cross-reference or D2 block in what every consumer
        # actually gets.
        #
        # Both anchors below are the real invocation lines, not bare
        # substrings: "pre-commit run --all-files" also appears in a header
        # comment (line ~25) that sits above both real invocations, which
        # made the ordering assertion vacuously true regardless of actual
        # order, and a plain substring match on the doc-consistency line
        # would also match a commented-out invocation.
        precommit_line = 'env -u GITHUB_TOKEN -u GH_TOKEN pre-commit run --all-files'
        doc_consistency_line = (
            'cd "$tmpdir" && python3 docs/tools/check_document_consistency.py'
        )
        matches = [
            line
            for line in self.text.splitlines()
            if doc_consistency_line in line and not line.strip().startswith("#")
        ]
        self.assertTrue(
            matches,
            "check-render.sh must run check_document_consistency.py directly against "
            "the render, since the hook that would otherwise run it is "
            "opt-in and absent from a bare render",
        )
        precommit_index = self.text.index(precommit_line)
        doc_consistency_index = self.text.index(doc_consistency_line)
        self.assertLess(
            precommit_index,
            doc_consistency_index,
            "check_document_consistency.py must run after the render's own "
            "pre-commit hooks, matching the order check-render.sh already "
            "runs its other guard-script-test and pre-commit steps in",
        )

    def test_is_referenced_from_claude_md_and_agents_md(self) -> None:
        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(
                "check-render.sh",
                text,
                f"{name} must say to run scripts/check-render.sh before a push "
                "touching template/ or copier.yml, or a contributor has no way "
                "to know this check exists",
            )


if __name__ == "__main__":
    sys.exit(unittest.main())
