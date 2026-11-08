"""Guard tests for check_skills_lock.py, run standalone: python3 scripts/test_check_skills_lock.py"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_skills_lock  # noqa: E402

SOURCE_NOTE = "<!-- Source: example/skills (https://example.invalid/skills), skills/example/SKILL.md @ abc123 (2026-01-01), MIT. See ../THIRD_PARTY.md. -->\n"


class SkillsLockFixture(unittest.TestCase):
    """Builds a scratch .agents/skills tree plus skills-lock.json, pointed to by the module's globals."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skills_dir = self.root / ".agents" / "skills"
        self.skills_dir.mkdir(parents=True)
        self.lock_path = self.root / "skills-lock.json"
        self.patchers = [
            mock.patch.object(check_skills_lock, "ROOT", self.root),
            mock.patch.object(check_skills_lock, "LOCK_PATH", self.lock_path),
            mock.patch.object(check_skills_lock, "SKILLS_DIR", self.skills_dir),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_skill(self, name: str, text: str, source_note: bool = True) -> Path:
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        content = (SOURCE_NOTE if source_note else "") + text
        (skill_dir / "SKILL.md").write_text(content)
        return skill_dir / "SKILL.md"

    def write_lock(self, skills: dict) -> None:
        self.lock_path.write_text(json.dumps({"version": 1, "skills": skills}))

    def run_guard(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = check_skills_lock.main([])
        return code, out.getvalue()


class LockEntryChecks(SkillsLockFixture):
    def test_matching_content_passes(self) -> None:
        skill_file = self.write_skill("ask-matt", "Body text.\n")
        digest = check_skills_lock.hash_target(skill_file.parent)
        self.write_lock({"ask-matt": {"skillPath": "SKILL.md", "computedHash": digest}})
        code, _ = self.run_guard()
        self.assertEqual(code, 0)

    def test_dangling_lock_entry_fails(self) -> None:
        self.write_lock({"ghost-skill": {"skillPath": "SKILL.md", "computedHash": "ab" * 32}})
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("ghost-skill", err)
        self.assertIn("does not exist", err)

    def test_edited_unmodified_skill_fails(self) -> None:
        """The case the issue names: an "unmodified" skill drifts from its recorded hash."""
        skill_file = self.write_skill("ask-matt", "Original body.\n")
        digest = check_skills_lock.hash_target(skill_file.parent)
        self.write_lock({"ask-matt": {"skillPath": "SKILL.md", "computedHash": digest}})
        self.assertEqual(self.run_guard()[0], 0, "guard must pass before the edit")

        skill_file.write_text("Edited body, never recorded in the lock.\n")
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("ask-matt", err)
        self.assertIn("no longer matches", err)

    def test_missing_hash_fails(self) -> None:
        self.write_skill("ask-matt", "Body text.\n")
        self.write_lock({"ask-matt": {"skillPath": "SKILL.md", "computedHash": None}})
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("no computedHash", err)

    def test_directory_skill_hashes_the_whole_tree(self) -> None:
        skill_dir = self.skills_dir / "multi-file"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(SOURCE_NOTE + "Body.\n")
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "run.sh").write_text("#!/bin/sh\necho hi\n")
        digest = check_skills_lock.hash_target(skill_dir)
        self.write_lock({"multi-file": {"skillPath": ".", "computedHash": digest}})
        self.assertEqual(self.run_guard()[0], 0)

        (skill_dir / "scripts" / "run.sh").write_text("#!/bin/sh\necho changed\n")
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("multi-file", err)

    def test_single_file_skill_also_hashes_its_supporting_files(self) -> None:
        """skillPath pointing at SKILL.md must still guard scripts/ etc. in that skill's directory."""
        skill_file = self.write_skill("ask-matt", "Body text.\n")
        skill_dir = skill_file.parent
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "run.sh").write_text("#!/bin/sh\necho hi\n")
        digest = check_skills_lock.hash_target(skill_dir)
        self.write_lock({"ask-matt": {"skillPath": "SKILL.md", "computedHash": digest}})
        self.assertEqual(self.run_guard()[0], 0)

        (skill_dir / "scripts" / "run.sh").write_text("#!/bin/sh\necho tampered\n")
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("ask-matt", err)
        self.assertIn("no longer matches", err)


class TemplatedSkillChecks(SkillsLockFixture):
    """A templated entry's `computedHash` excludes the primary file on both sides of a render.

    Its own content is covered separately by `templateHash`, checked only
    against the `.jinja` source here, never against a rendered `SKILL.md`.
    """

    def test_jinja_source_content_is_checked_via_template_hash(self) -> None:
        skill_dir = self.skills_dir / "triage"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md.jinja"
        skill_md.write_text(SOURCE_NOTE + "Body for {{ repo_owner }}.\n")
        computed = check_skills_lock.hash_target(skill_dir, exclude=skill_md)
        template = check_skills_lock.hash_target(skill_md)
        self.write_lock(
            {
                "triage": {
                    "skillPath": "SKILL.md",
                    "computedHash": computed,
                    "templateHash": template,
                    "templated": True,
                }
            }
        )
        self.assertEqual(self.run_guard()[0], 0)

        skill_md.write_text(SOURCE_NOTE + "Edited, never relocked.\n")
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("triage", err)
        self.assertIn("templateHash", err)

    def test_missing_template_hash_fails(self) -> None:
        skill_dir = self.skills_dir / "triage"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md.jinja"
        skill_md.write_text(SOURCE_NOTE + "Body for {{ repo_owner }}.\n")
        computed = check_skills_lock.hash_target(skill_dir, exclude=skill_md)
        self.write_lock({"triage": {"skillPath": "SKILL.md", "computedHash": computed, "templated": True}})
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("no templateHash", err)

    def test_rendered_plain_skill_md_is_not_hash_checked(self) -> None:
        """Once Copier renders SKILL.md.jinja to SKILL.md, no single hash can match that one file."""
        skill_dir = self.skills_dir / "triage"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(SOURCE_NOTE + "Body for sample-owner, rendered.\n")
        # Same scheme as the source repo: directory hash excluding the
        # primary file, which with no other files is an empty file set.
        digest = check_skills_lock.hash_target(skill_dir, exclude=skill_dir / "SKILL.md")
        self.write_lock({"triage": {"skillPath": "SKILL.md", "computedHash": digest, "templated": True}})
        code, err = self.run_guard()
        self.assertEqual(code, 0, err)

    def test_rendered_skill_still_hashes_its_other_files(self) -> None:
        """Even once SKILL.md.jinja is rendered, the rest of the directory stays guarded."""
        skill_dir = self.skills_dir / "triage"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(SOURCE_NOTE + "Body for sample-owner, rendered.\n")
        (skill_dir / "AGENT-BRIEF.md").write_text("Brief.\n")
        digest = check_skills_lock.hash_target(skill_dir, exclude=skill_dir / "SKILL.md")
        self.write_lock({"triage": {"skillPath": "SKILL.md", "computedHash": digest, "templated": True}})
        self.assertEqual(self.run_guard()[0], 0)

        (skill_dir / "AGENT-BRIEF.md").write_text("Tampered.\n")
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("triage", err)

    def test_same_lock_entry_passes_in_both_source_and_rendered_contexts(self) -> None:
        """The one shipped lock entry must validate both this repo's .jinja and a render's plain file."""
        skill_dir = self.skills_dir / "triage"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md.jinja"
        skill_md.write_text(SOURCE_NOTE + "Body for {{ repo_owner }}.\n")
        (skill_dir / "AGENT-BRIEF.md").write_text("Brief.\n")
        computed = check_skills_lock.hash_target(skill_dir, exclude=skill_md)
        template = check_skills_lock.hash_target(skill_md)
        lock_entry = {
            "skillPath": "SKILL.md",
            "computedHash": computed,
            "templateHash": template,
            "templated": True,
        }
        self.write_lock({"triage": lock_entry})
        self.assertEqual(self.run_guard()[0], 0, "must pass against the .jinja source")

        # Simulate a render: the rendered SKILL.md replaces SKILL.md.jinja;
        # AGENT-BRIEF.md, untemplated, carries over unchanged.
        skill_md.unlink()
        (skill_dir / "SKILL.md").write_text(SOURCE_NOTE + "Body for sample-owner, rendered.\n")
        self.write_lock({"triage": lock_entry})
        self.assertEqual(self.run_guard()[0], 0, "the same lock entry must also pass against the render")


class UnlockedVendoredSkillChecks(SkillsLockFixture):
    def test_source_note_with_no_lock_entry_fails(self) -> None:
        self.write_skill("unlocked", "Body.\n", source_note=True)
        self.write_lock({})
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("unlocked", err)
        self.assertIn("Source note", err)

    def test_no_source_note_with_no_lock_entry_passes(self) -> None:
        """A skill written for this project, not vendored, needs no lock entry."""
        self.write_skill("homegrown", "Body.\n", source_note=False)
        self.write_lock({})
        self.assertEqual(self.run_guard()[0], 0)

    def test_jinja_variant_is_also_checked_for_a_source_note(self) -> None:
        skill_dir = self.skills_dir / "templated"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.jinja").write_text(SOURCE_NOTE + "Body for {{ project_name }}.\n")
        self.write_lock({})
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("templated", err)


class NoLockFile(unittest.TestCase):
    def test_absent_lock_file_passes_quietly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = io.StringIO()
            with (
                mock.patch.object(check_skills_lock, "ROOT", root),
                mock.patch.object(check_skills_lock, "LOCK_PATH", root / "skills-lock.json"),
                mock.patch.object(check_skills_lock, "SKILLS_DIR", root / ".agents" / "skills"),
                contextlib.redirect_stdout(out),
            ):
                self.assertEqual(check_skills_lock.main([]), 0)
            self.assertIn("NOT RUNNING", out.getvalue())


class TemplateRepoFixture(SkillsLockFixture):
    """Runs the guard with `--template`, the flag the root-side `skills-lock` pre-commit hook passes for this repository's own copy."""

    def run_guard(self, *extra_args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = check_skills_lock.main(["--template", *extra_args])
        return code, out.getvalue()


class MissingLockFileInTemplateRepo(TemplateRepoFixture):
    """The issue's repro (a): deleting template/skills-lock.json entirely must not pass silently."""

    def test_missing_lock_file_fails_inside_the_template_repo(self) -> None:
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("skills-lock.json", err)
        self.assertIn(str(self.lock_path), err)

    def test_missing_lock_file_still_passes_outside_the_template_repo(self) -> None:
        """A generated project (no --template) may legitimately vendor no skills at all."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(check_skills_lock.main([]), 0)
        self.assertIn("NOT RUNNING", out.getvalue())


class TemplatedEntryRequiresJinjaInTemplateRepo(TemplateRepoFixture):
    """The issue's repro (b): "templated": true on a plain SKILL.md must not skip its hash check."""

    def test_templated_entry_with_plain_skill_md_fails(self) -> None:
        skill_dir = self.skills_dir / "grill-me"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(SOURCE_NOTE + "Original body.\n")
        # Same digest a tampered file would also produce, since the bug was
        # that this file was excluded from the hash entirely.
        digest = check_skills_lock.hash_target(skill_dir, exclude=skill_dir / "SKILL.md")
        self.write_lock({"grill-me": {"skillPath": "SKILL.md", "computedHash": digest, "templated": True}})
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("grill-me", err)
        self.assertIn("not a SKILL.md.jinja", err)

        # The content check this flag was meant to skip (templateHash exists
        # for the real .jinja, never for this case) stays bypassed either
        # way: this guard catches the misconfiguration itself, not content
        # drift, so tampering the file further still reports the same error.
        (skill_dir / "SKILL.md").write_text(SOURCE_NOTE + "Tampered body, still unnoticed by computedHash.\n")
        code, err = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn("grill-me", err)

    def test_templated_entry_with_jinja_source_still_passes(self) -> None:
        skill_dir = self.skills_dir / "grill-me"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md.jinja"
        skill_md.write_text(SOURCE_NOTE + "Body for {{ repo_owner }}.\n")
        computed = check_skills_lock.hash_target(skill_dir, exclude=skill_md)
        template = check_skills_lock.hash_target(skill_md)
        self.write_lock(
            {
                "grill-me": {
                    "skillPath": "SKILL.md",
                    "computedHash": computed,
                    "templateHash": template,
                    "templated": True,
                }
            }
        )
        self.assertEqual(self.run_guard()[0], 0)


if __name__ == "__main__":
    unittest.main()
