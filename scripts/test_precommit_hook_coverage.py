"""Guard tests for .pre-commit-config.yaml's security-relevant hooks: each
must still fire on an ordinary file it is meant to cover.

Standalone, standard-library-only: python3 scripts/test_precommit_hook_coverage.py

docs/security/threat-model.md row T4 covers a change that weakens a guard
by "widens an exclude, makes a hook skip." test_check_denylist.py already
guards the denylist-file-specific parts of that threat (an emptied
denylist, an allow-list entry leaking past its own file); nothing guarded
the other two shapes until this file: a widened `exclude:` pattern quietly
excusing an ordinary file from `denylist` or `no-issue-refs`, or a hook
definition changed to skip outright (`stages: [manual]`, a tautological
`files:` regex) like `denylist-not-shipped`. Each test here runs the real,
committed `.pre-commit-config.yaml` against a path that must stay covered;
widening the exclude enough to catch that path, or disabling the hook,
turns the assertion red.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".pre-commit-config.yaml"
CONFIG_TEXT = CONFIG.read_text()

# Every `- id: <id>` line's id, in order, duplicates included -- used by
# NoHookIdCollidesAcrossForgeSourceAndRenderedConsumer below, which needs
# the raw count, not a hook's block contents.
_ID_LINE_RE = re.compile(r"^\s*- id:\s*(\S+)\s*$", re.M)


def _ids_in(text: str) -> list[str]:
    return _ID_LINE_RE.findall(text)


# Each hook is a local-repo `- id: <id>` block up to the next `- id:` or EOF;
# regex, not a YAML library, to match check_template_pins.py's stdlib-only
# convention for this family of guard scripts.
def _hook_block(hook_id: str) -> str:
    pattern = re.compile(rf"- id:\s*{re.escape(hook_id)}\s*\n((?:(?!\s*- id:).*\n)*)")
    match = pattern.search(CONFIG_TEXT)
    if match is None:
        raise AssertionError(f"no hook with id {hook_id!r} in {CONFIG}")
    return match.group(1)


def _field(block: str, name: str) -> str | None:
    match = re.search(rf"^\s*{name}:\s*(.+)$", block, re.M)
    return match.group(1).strip() if match else None


def _run_pre_commit(hook_id: str, *, files: list[str] | None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    cmd = ["pre-commit", "run", hook_id]
    if files is not None:
        cmd += ["--files", *files]
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(cmd, cwd=ROOT, env=full_env, capture_output=True, text=True)


def _skip_if_no_pre_commit() -> None:
    if subprocess.run(["which", "pre-commit"], capture_output=True).returncode != 0:
        raise unittest.SkipTest("pre-commit is not installed in this environment")


class _ScratchProbeFile:
    """A probe file under a .gitignore'd scratch directory inside this
    repository (pre-commit resolves --files paths against the repo
    toplevel, so the probe can't live in a tempdir outside it), cleaned up
    even if the body raises or the process is interrupted mid-test.

    `directory` lets a probe sit next to a specific excluded path (e.g.
    `docs/agents/`) rather than only under the default scratch dir, so a
    test can prove an *adjacent* ordinary file stays covered."""

    SCRATCH_DIR = ROOT / "scripts" / ".precommit_probe_scratch"

    def __init__(self, name: str, content: str, directory: Path | None = None) -> None:
        self.directory = directory or self.SCRATCH_DIR
        self.path = self.directory / name
        self.content = content
        self._created_dir = not self.directory.exists()

    def __enter__(self) -> Path:
        self.directory.mkdir(exist_ok=True)
        self.path.write_text(self.content)
        return self.path

    def __exit__(self, *exc_info: object) -> None:
        self.path.unlink(missing_ok=True)
        if self._created_dir:
            try:
                self.directory.rmdir()
            except OSError:
                pass  # another probe in this run still owns the directory


class DenylistStillFiresOnAnOrdinaryFile(unittest.TestCase):
    """The guard test: widening `denylist`'s exclude to cover an ordinary
    path (or past patterns in it) must go red here."""

    def test_denylist_catches_a_planted_term_outside_its_exclude(self):
        _skip_if_no_pre_commit()
        exclude = _field(_hook_block("denylist"), "exclude") or ""
        probe_name = "probe_denylist.md"
        relpath = str((_ScratchProbeFile.SCRATCH_DIR / probe_name).relative_to(ROOT))
        self.assertNotRegex(
            relpath,
            exclude,
            "the probe path must not already be excluded, or this test proves nothing",
        )
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "scratch-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            with _ScratchProbeFile(probe_name, "Credits: QuuxCorp-Zylotrex\n"):
                result = _run_pre_commit(
                    "denylist",
                    files=[relpath],
                    env={"THEFORGE_DENYLIST_FILE": str(denylist)},
                )
                output = result.stdout + result.stderr
                # A hook moved to `stages: [manual]` also exits non-zero
                # ("No hook with id `denylist` in stage `pre-commit`"), so
                # a bare returncode check can't tell a real firing from a
                # skipped hook -- assert the hook's own failure text too.
                self.assertNotIn(
                    "No hook with id",
                    output,
                    f"denylist must still run at the default stage, not be skipped by a stage restriction:\n{output}",
                )
                self.assertIn(
                    "denylisted term in",
                    output,
                    f"denylist must still fire on an ordinary file outside its exclude:\n{output}",
                )
                self.assertNotEqual(
                    result.returncode,
                    0,
                    f"denylist must still fire on an ordinary file outside its exclude:\n{output}",
                )


class NoIssueRefsStillFiresOnAnOrdinaryFile(unittest.TestCase):
    """The guard test: widening `no-issue-refs`'s exclude to cover an
    ordinary path must go red here."""

    def test_no_issue_refs_catches_a_reference_outside_its_exclude(self):
        _skip_if_no_pre_commit()
        exclude = _field(_hook_block("no-issue-refs"), "exclude") or ""
        probe_name = "probe_issue_refs.md"
        relpath = str((_ScratchProbeFile.SCRATCH_DIR / probe_name).relative_to(ROOT))
        self.assertNotRegex(
            relpath,
            exclude,
            "the probe path must not already be excluded, or this test proves nothing",
        )
        # Built from parts at runtime, not as one literal string, so this
        # test file's own source doesn't trip the hook it's testing.
        number = "9" * 6
        with _ScratchProbeFile("probe_issue_refs.md", "See issue #" + number + " for details.\n"):
            result = _run_pre_commit("no-issue-refs", files=[relpath])
            output = result.stdout + result.stderr
            # Same vacuous-pass risk as the denylist test above: a hook
            # moved to `stages: [manual]` also exits non-zero, so check
            # the hook's own failure text, not just the return code.
            self.assertNotIn(
                "No hook with id",
                output,
                f"no-issue-refs must still run at the default stage, not be skipped by a stage restriction:\n{output}",
            )
            self.assertIn(
                "issue/PR-style reference",
                output,
                f"no-issue-refs must still fire on an ordinary file outside its exclude:\n{output}",
            )
            self.assertNotEqual(
                result.returncode,
                0,
                f"no-issue-refs must still fire on an ordinary file outside its exclude:\n{output}",
            )


class RenderedPathExclusionStaysNarrow(unittest.TestCase):
    """T4 amendment guard test: the self-retrofit exclude patterns added to
    `denylist` and `no-issue-refs` for the rendered paths (`.copier-answers.yml`,
    `.forge/`, `.agents/skills/`, `NOTICE.md`, every direct markdown file under
    `docs/agents/` except `lessons.md` and `operational-constants.md`, and
    `scripts/project_init_checklist.md`) must stay exact. An ordinary file
    sitting right next to one of those paths -- not under it -- must still be
    scanned by both hooks; a pattern widened to a bare prefix or a missing
    anchor would excuse it too.

    Each probe location below targets a specific widening a regex edit
    could introduce without this test class failing on the root/sibling
    probes alone: a dropped trailing-slash anchor (`.forgex/`, lexically
    close to `.forge/`) or a trimmed path segment (`.agents/` alone, missing
    the `/skills/` this exclude actually names)."""

    PROBES: list[tuple[str, Path]] = [
        ("probe_rendered_root.md", ROOT),
        ("probe_agents_sibling.md", ROOT / ".agents"),
        ("probe.md", ROOT / ".forgex"),
    ]

    def _assert_no_issue_refs_still_covers(self, name: str, directory: Path) -> None:
        relpath = str((directory / name).relative_to(ROOT))
        number = "9" * 6
        with _ScratchProbeFile(name, "See issue #" + number + " for details.\n", directory=directory):
            exclude = _field(_hook_block("no-issue-refs"), "exclude") or ""
            self.assertNotRegex(relpath, exclude, f"{relpath} must not already be excluded from no-issue-refs, or this test proves nothing")
            result = _run_pre_commit("no-issue-refs", files=[relpath])
            output = result.stdout + result.stderr
            self.assertNotIn("No hook with id", output, output)
            self.assertIn("issue/PR-style reference", output, f"no-issue-refs must still fire on {relpath}, next to an excluded rendered path:\n{output}")
            self.assertNotEqual(result.returncode, 0, output)

    def _assert_denylist_still_covers(self, name: str, directory: Path) -> None:
        relpath = str((directory / name).relative_to(ROOT))
        with tempfile.TemporaryDirectory() as tmp:
            denylist = Path(tmp) / "scratch-denylist"
            denylist.write_text("QuuxCorp-Zylotrex\n")
            with _ScratchProbeFile(name, "Credits: QuuxCorp-Zylotrex\n", directory=directory):
                exclude = _field(_hook_block("denylist"), "exclude") or ""
                self.assertNotRegex(relpath, exclude, f"{relpath} must not already be excluded from denylist, or this test proves nothing")
                result = _run_pre_commit("denylist", files=[relpath], env={"THEFORGE_DENYLIST_FILE": str(denylist)})
                output = result.stdout + result.stderr
                self.assertNotIn("No hook with id", output, output)
                self.assertIn("denylisted term in", output, f"denylist must still fire on {relpath}, next to an excluded rendered path:\n{output}")
                self.assertNotEqual(result.returncode, 0, output)

    def test_no_issue_refs_still_covers_every_probe(self):
        _skip_if_no_pre_commit()
        for name, directory in self.PROBES:
            with self.subTest(probe=str(directory / name)):
                self._assert_no_issue_refs_still_covers(name, directory)

    def test_denylist_still_covers_every_probe(self):
        _skip_if_no_pre_commit()
        for name, directory in self.PROBES:
            with self.subTest(probe=str(directory / name)):
                self._assert_denylist_still_covers(name, directory)

    def test_docs_agents_carve_out_stays_exactly_two_files(self):
        """The negative lookahead inside the `docs/agents/` branch of both
        excludes must keep naming exactly `lessons.md` and
        `operational-constants.md`, not a widened set. Checked by regex
        alone, against both repository-owned paths and a sibling probe --
        never by writing into the two real tracked files themselves."""
        for hook_id in ("no-issue-refs", "denylist"):
            exclude = _field(_hook_block(hook_id), "exclude") or ""
            with self.subTest(hook=hook_id):
                self.assertNotRegex("docs/agents/lessons.md", exclude, f"{hook_id} must still cover (not exclude) docs/agents/lessons.md")
                self.assertNotRegex("docs/agents/operational-constants.md", exclude, f"{hook_id} must still cover (not exclude) docs/agents/operational-constants.md")
                self.assertRegex("docs/agents/issue-tracker.md", exclude, f"{hook_id} must exclude docs/agents/issue-tracker.md, a forge-generated doc")


class DenylistNotShippedStillRunsAtTheDefaultStage(unittest.TestCase):
    """The guard test: changing this hook to skip outright (`stages:
    [manual]`, `always_run: false` with no `files:`, or a `files:` regex
    that never matches) must go red here."""

    def test_config_still_marks_it_always_run_with_no_narrowing_files_pattern(self):
        block = _hook_block("denylist-not-shipped")
        self.assertEqual(_field(block, "always_run"), "true", "denylist-not-shipped must stay always_run, or it can silently stop covering a commit")
        self.assertIsNone(_field(block, "files"), "a files: pattern on an always_run, pass_filenames:false hook can only narrow it away from always running")
        stages = _field(block, "stages")
        if stages is not None:
            self.assertIn("pre-commit", stages, "denylist-not-shipped must still run at the default pre-commit stage")

    def test_it_actually_executes_at_the_default_stage(self):
        _skip_if_no_pre_commit()
        result = _run_pre_commit("denylist-not-shipped", files=None)
        self.assertNotIn(
            "No hook with id",
            result.stdout + result.stderr,
            f"denylist-not-shipped must run at the default stage, not be skipped by a stage restriction:\n{result.stdout}\n{result.stderr}",
        )
        self.assertEqual(
            result.returncode,
            0,
            f"denylist-not-shipped should pass cleanly on this repository's own tree:\n{result.stdout}\n{result.stderr}",
        )


class EveryMetaGuardHookIsPresent(unittest.TestCase):
    """I3 (docs/design/theforge-self-governance.md, "Invariants"): every hook
    that governs `template/` as forge-source stays active once this
    repository also renders and runs its own consumer hooks side by side
    (self-retrofit part 2, slice 4). Each entry below is this hook's scope
    as of that slice; a PR that narrows, skips, or drops one of these ids
    updates this baseline deliberately, the same shrink-only-with-a-reason
    shape as `module_size_allowlist.json` and `dead_code_baseline.json`."""

    # id -> (always_run, files pattern or None, stages or None). A hook
    # with always_run True must stay always_run; one with a files: pattern
    # must keep exactly this pattern (or wider), never narrower; a hook
    # with no stages: override must gain none (moving to `stages: [manual]`
    # is exactly the skip this test exists to catch).
    META_GUARD_HOOKS: dict[str, tuple[bool, str | None, str | None]] = {
        "no-issue-refs": (False, None, None),
        "denylist": (False, None, None),
        "no-issue-refs-commit-msg": (False, None, "commit-msg"),
        "denylist-commit-msg": (False, None, "commit-msg"),
        "one-sentence-per-line-template": (False, r"^template/\.forge/.*\.md(\.jinja)?$", None),
        "not-raw-clone": (True, None, None),
        "denylist-not-shipped": (True, None, None),
        "denylist-not-shipped-render": (False, r"^(copier\.yml|\.theforge-denylist(-allow)?|template/.*|scripts/(denylist-path\.sh|check-denylist(-not-shipped)?\.sh|test_denylist_not_shipped\.py))$", None),
        "skills-lock-template": (True, None, None),
        "forge-entrypoint-template": (True, None, None),
        "check-render": (True, None, None),
        "template-pins": (False, r"^(template/\.devcontainer/devcontainer\.json\.jinja|template/\.github/workflows/.*|scripts/check_template_pins\.py|scripts/test_check_template_pins\.py)$", None),
    }

    def test_every_meta_guard_hook_keeps_its_scope(self):
        for hook_id, (always_run, files, stages) in self.META_GUARD_HOOKS.items():
            with self.subTest(hook=hook_id):
                block = _hook_block(hook_id)  # raises if the hook is gone
                self.assertEqual(
                    _field(block, "always_run") == "true",
                    always_run,
                    f"{hook_id} must stay always_run: {always_run}, not be narrowed to a files: trigger",
                )
                self.assertEqual(
                    _field(block, "files"),
                    files,
                    f"{hook_id}'s files: pattern must not narrow from what I3 recorded",
                )
                actual_stages = _field(block, "stages")
                if stages is None:
                    self.assertIsNone(actual_stages, f"{hook_id} must keep running at the default pre-commit stage, not gain a stages: restriction")
                else:
                    self.assertIsNotNone(actual_stages, f"{hook_id} must keep its {stages!r} stage")
                    self.assertIn(stages, actual_stages, f"{hook_id} must keep its {stages!r} stage")

    def test_every_meta_guard_hook_actually_runs(self):
        """Presence in the config isn't enough on its own: confirm pre-commit
        itself still recognises each id at the default stage (catches a
        `stages: [manual]` override `_field` alone can't see as a skip)."""
        _skip_if_no_pre_commit()
        for hook_id in self.META_GUARD_HOOKS:
            if self.META_GUARD_HOOKS[hook_id][2] == "commit-msg":
                continue  # exercised at the commit-msg stage, not pre-commit
            with self.subTest(hook=hook_id):
                result = _run_pre_commit(hook_id, files=[])
                output = result.stdout + result.stderr
                self.assertNotIn(
                    "No hook with id",
                    output,
                    f"{hook_id} must still run at the default pre-commit stage:\n{output}",
                )


class NoHookIdCollidesAcrossForgeSourceAndRenderedConsumer(unittest.TestCase):
    """This repository runs both its forge-source meta-guard hooks (govern
    `template/` as source) and a rendered copy of its own shipped consumer
    hooks (govern root) side by side in one `.pre-commit-config.yaml`
    (I3). The rendered copy always reproduces every id from
    `template/.pre-commit-config.yaml.jinja` unchanged, so a *new*
    forge-source hook whose id collides with one of those is a literal
    duplicate `- id:` in this one file -- not a second file to diff
    against. The convention (docs/forge-overrides.md, "TheForge meta-guard
    hooks") is to rename the forge-source side `<id>-template`; this is the
    mechanical check the convention itself was missing, after the
    `coordinator-core-template` collision shipped unrenamed for a time
    because nothing caught it before merge."""

    def test_no_hook_id_is_defined_more_than_once(self) -> None:
        ids = _ids_in(CONFIG_TEXT)
        counts: dict[str, int] = {}
        for hook_id in ids:
            counts[hook_id] = counts.get(hook_id, 0) + 1
        dupes = {hook_id: n for hook_id, n in counts.items() if n > 1}
        self.assertEqual(
            dupes,
            {},
            "a hook id is defined more than once in .pre-commit-config.yaml: "
            f"{sorted(dupes)}. If this is a new forge-source hook colliding with a "
            "rendered consumer hook of the same name, rename the forge-source side "
            "<id>-template (docs/forge-overrides.md, \"TheForge meta-guard hooks\").",
        )

    def test_detects_a_planted_duplicate_id(self) -> None:
        """Guard-removal proof: the detection logic itself, exercised against a
        synthetic config text rather than the real file, so this test stays red
        if someone narrows `_ids_in` or the duplicate check above rather than
        just happening to pass because the real file has no collision today."""
        planted = CONFIG_TEXT + "\n      - id: coordinator-core\n        name: planted duplicate\n"
        ids = _ids_in(planted)
        counts: dict[str, int] = {}
        for hook_id in ids:
            counts[hook_id] = counts.get(hook_id, 0) + 1
        dupes = {hook_id: n for hook_id, n in counts.items() if n > 1}
        self.assertEqual(dupes, {"coordinator-core": 2})


if __name__ == "__main__":
    sys.exit(unittest.main())
