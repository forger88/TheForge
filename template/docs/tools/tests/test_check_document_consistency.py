import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import document_build  # noqa: E402
from build_errors import BuildError  # noqa: E402
from check_document_consistency import (  # noqa: E402
    _manifest_documents_by_source,
    _markdown_documents,
    check_adr_references,
    check_d2_blocks,
    check_images,
    check_requirement_ids,
    check_screenshot_manifest,
    check_toolchain,
)


D2_AVAILABLE = shutil.which("d2") is not None and shutil.which("pandoc") is not None


class MarkdownDocumentsTests(unittest.TestCase):
    def test_extra_globs_add_to_the_manifests_own_documents(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs" / "adr").mkdir(parents=True)
            (root / "docs" / "spec.md").write_text("x", encoding="utf-8")
            (root / "docs" / "adr" / "0001-x.md").write_text("x", encoding="utf-8")
            manifest = {"documents": [{"source": "docs/spec.md"}]}

            documents = _markdown_documents(manifest, root, ["docs/adr/*.md"])

            self.assertEqual(
                [root / "docs" / "adr" / "0001-x.md", root / "docs" / "spec.md"],
                documents,
            )

    def test_a_non_markdown_source_in_the_manifest_is_skipped(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            (root / "docs" / "notes.txt").write_text("x", encoding="utf-8")
            manifest = {"documents": [{"source": "docs/notes.txt"}]}

            documents = _markdown_documents(manifest, root, [])

            self.assertEqual([], documents)


class CheckImagesTests(unittest.TestCase):
    def test_flags_an_image_that_does_not_exist_anywhere(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "guide.md"
            doc.write_text("![missing](does-not-exist.png)\n", encoding="utf-8")

            issues = check_images([doc], root)

            self.assertEqual(1, len(issues))
            self.assertEqual("missing-image", issues[0].check)
            self.assertIn("does-not-exist.png", issues[0].detail)

    def test_resolves_relative_to_the_document_and_to_the_repository_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs" / "sub").mkdir(parents=True)
            (root / "assets").mkdir()
            (root / "docs" / "sub" / "local.png").write_bytes(b"png")
            (root / "assets" / "shared.png").write_bytes(b"png")
            doc = root / "docs" / "sub" / "guide.md"
            doc.write_text(
                "![local](local.png)\n\n![shared](assets/shared.png)\n",
                encoding="utf-8",
            )

            issues = check_images([doc], root)

            self.assertEqual([], issues)

    def test_ignores_remote_urls(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "guide.md"
            doc.write_text("![remote](https://example.com/pic.png)\n", encoding="utf-8")

            issues = check_images([doc], root)

            self.assertEqual([], issues)

    def test_ignores_image_syntax_inside_code(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "guide.md"
            doc.write_text(
                "| a | a model-authored `![](url)` fetches |\n\n"
                "```markdown\n![example](not-real.png)\n```\n\n"
                "``![x](also-not-real.png)``\n",
                encoding="utf-8",
            )

            issues = check_images([doc], root)

            self.assertEqual([], issues)

    def test_still_checks_an_image_after_a_code_span(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "guide.md"
            doc.write_text("Use `x` here: ![missing](gone.png)\n", encoding="utf-8")

            issues = check_images([doc], root)

            self.assertEqual(1, len(issues))
            self.assertIn("gone.png", issues[0].detail)


class CheckRequirementIdsTests(unittest.TestCase):
    def test_flags_a_requirement_id_defined_twice(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "spec.md"
            doc.write_text(
                "| FR-201 | Shall do one thing | Satisfied |\n"
                "| FR-201 | Shall do another | Not yet Satisfied |\n",
                encoding="utf-8",
            )

            issues = check_requirement_ids([doc], root)

            self.assertEqual(1, len(issues))
            self.assertEqual("duplicate-requirement-id", issues[0].check)
            self.assertIn("FR-201", issues[0].detail)

    def test_flags_a_citation_with_no_matching_definition(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "spec.md"
            doc.write_text("See NF-999 for details.\n", encoding="utf-8")

            issues = check_requirement_ids([doc], root)

            self.assertEqual(1, len(issues))
            self.assertEqual("dangling-requirement-reference", issues[0].check)
            self.assertIn("NF-999", issues[0].detail)

    def test_a_known_gaps_row_is_a_citation_not_a_redefinition(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "spec.md"
            doc.write_text(
                "| NF-103 | Shall use mTLS | Not yet Satisfied |\n\n"
                "| Requirement | Gap | Tracking |\n"
                "| NF-103 | Channel is plaintext | #1 |\n",
                encoding="utf-8",
            )

            issues = check_requirement_ids([doc], root)

            self.assertEqual([], issues)

    def test_an_id_shown_as_an_inline_code_example_is_not_a_citation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "spec.md"
            doc.write_text(
                "Functional requirements are `FR-NNN`, for example `FR-001`..`FR-099`.\n",
                encoding="utf-8",
            )

            issues = check_requirement_ids([doc], root)

            self.assertEqual([], issues)

    def test_an_id_inside_a_fenced_code_block_is_not_a_citation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "spec.md"
            doc.write_text(
                "```\nSee FR-301 in the example payload below.\n```\n",
                encoding="utf-8",
            )

            issues = check_requirement_ids([doc], root)

            self.assertEqual([], issues)

    def test_a_definition_in_one_document_satisfies_a_citation_in_another(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            spec = root / "docs" / "spec.md"
            spec.write_text(
                "| FR-101 | Shall be defined here | Satisfied |\n", encoding="utf-8"
            )
            other = root / "docs" / "sad.md"
            other.write_text("Cites FR-101 without redefining it.\n", encoding="utf-8")

            issues = check_requirement_ids([spec, other], root)

            self.assertEqual([], issues)


class CheckAdrReferencesTests(unittest.TestCase):
    def test_flags_an_adr_reference_with_no_matching_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs" / "adr").mkdir(parents=True)
            (root / "docs" / "adr" / "0001-real-decision.md").write_text(
                "# ADR", encoding="utf-8"
            )
            doc = root / "docs" / "sad.md"
            doc.write_text("See ADR-0001 and the non-existent ADR-0099.\n", encoding="utf-8")

            issues = check_adr_references([doc], root)

            self.assertEqual(1, len(issues))
            self.assertEqual("broken-adr-reference", issues[0].check)
            self.assertIn("ADR-0099", issues[0].detail)


class CheckScreenshotManifestTests(unittest.TestCase):
    def _manifest(self, expected):
        return {"screenshots": {"output_directory": "screenshots", "expected": expected}}

    def test_no_screenshots_section_is_clean(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "guide.md"
            doc.write_text("no screenshots here\n", encoding="utf-8")

            issues = check_screenshot_manifest([doc], {}, root)

            self.assertEqual([], issues)

    def test_a_referenced_screenshot_missing_from_expected_is_flagged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            (root / "screenshots").mkdir()
            doc = root / "docs" / "deck.md"
            doc.write_text("![](../screenshots/new.png)\n", encoding="utf-8")

            issues = check_screenshot_manifest([doc], self._manifest([]), root)

            self.assertEqual(1, len(issues))
            self.assertEqual("stale-screenshot-manifest", issues[0].check)
            self.assertIn("new.png", issues[0].detail)

    def test_an_expected_screenshot_nothing_references_is_flagged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            (root / "screenshots").mkdir()
            doc = root / "docs" / "deck.md"
            doc.write_text("no screenshots referenced here\n", encoding="utf-8")

            issues = check_screenshot_manifest([doc], self._manifest(["orphan.png"]), root)

            self.assertEqual(1, len(issues))
            self.assertEqual("stale-screenshot-manifest", issues[0].check)
            self.assertIn("orphan.png", issues[0].detail)

    def test_a_matching_reference_and_expected_entry_is_clean(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            (root / "screenshots").mkdir()
            doc = root / "docs" / "deck.md"
            doc.write_text("![](../screenshots/shot.png)\n", encoding="utf-8")

            issues = check_screenshot_manifest([doc], self._manifest(["shot.png"]), root)

            self.assertEqual([], issues)


class ManifestDocumentsBySourceTests(unittest.TestCase):
    def test_maps_each_document_by_its_resolved_source_path(self):
        root = Path("/repo")
        manifest = {
            "documents": [
                {"source": "docs/a.md", "diagram_overrides": {"d2": {"pad": 10}}},
                {"source": "docs/b.md"},
            ]
        }

        result = _manifest_documents_by_source(manifest, root)

        self.assertEqual(manifest["documents"][0], result[root / "docs" / "a.md"])
        self.assertEqual(manifest["documents"][1], result[root / "docs" / "b.md"])

    def test_a_document_reached_only_via_also_has_no_entry(self):
        root = Path("/repo")
        manifest = {"documents": [{"source": "docs/a.md"}]}

        result = _manifest_documents_by_source(manifest, root)

        self.assertNotIn(root / "docs" / "hand-written.md", result)


class CheckToolchainTests(unittest.TestCase):
    def test_a_manifest_with_no_toolchain_key_is_tolerated_not_crashed(self):
        # main()'s own pandoc_command/d2_command lookups two lines away are
        # already tolerant of a toolchain-less manifest
        # (`manifest.get("toolchain", {})`); this must degrade the same way,
        # not raise the bare KeyError document_build._check_toolchain's own
        # `manifest["toolchain"].items()` would.
        issues = check_toolchain({"documents": []}, Path("/repo"))
        self.assertEqual([], issues)

    def test_a_passing_toolchain_check_reports_no_issue(self):
        with mock.patch.object(document_build, "_check_toolchain", return_value=None):
            issues = check_toolchain({"toolchain": {}}, Path("/repo"))
        self.assertEqual([], issues)

    def test_a_version_mismatch_is_reported_as_an_issue_not_raised(self):
        with mock.patch.object(
            document_build, "_check_toolchain", side_effect=BuildError("d2 0.9.0 is required, but 0.8.0 is installed.")
        ):
            issues = check_toolchain({"toolchain": {}}, Path("/repo"))
        self.assertEqual(1, len(issues))
        self.assertEqual("toolchain-mismatch", issues[0].check)
        self.assertIn("0.9.0", issues[0].detail)


class CheckD2BlocksOverridesTests(unittest.TestCase):
    """`check_d2_blocks` must forward a document's own `diagram_overrides.d2`
    to `render_d2` the same way `document_build.py`'s real build does
    (`_build_renderers`), and reject an invalid one the same way
    (`document_build._validate_diagram_overrides`) -- exercised with
    `render_d2` mocked out, since this sandbox has no `d2`/`pandoc` on PATH
    for the real-render path `CheckD2BlocksTests` below covers."""

    def _ast_result(self, source: str) -> mock.Mock:
        ast = {"blocks": [{"t": "CodeBlock", "c": [["", ["d2"], []], source]}]}
        result = mock.Mock()
        result.returncode = 0
        result.stdout = json.dumps(ast)
        result.stderr = ""
        return result

    def test_a_documents_overrides_are_forwarded_to_render_d2(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "sad.md"
            doc.write_text("```d2\na -> b\n```\n", encoding="utf-8")
            manifest_documents = {doc: {"source": "docs/sad.md", "diagram_overrides": {"d2": {"pad": 10}}}}

            with mock.patch(
                "check_document_consistency.subprocess.run", return_value=self._ast_result("a -> b")
            ), mock.patch("check_document_consistency.render_d2") as render_d2:
                issues = check_d2_blocks([doc], root, "pandoc", "d2", manifest_documents)

        self.assertEqual([], issues)
        render_d2.assert_called_once_with(
            "a -> b", mock.ANY, command="d2", overrides={"pad": 10}
        )

    def test_an_unknown_override_key_is_flagged_without_attempting_a_render(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "sad.md"
            doc.write_text("```d2\na -> b\n```\n", encoding="utf-8")
            manifest_documents = {doc: {"source": "docs/sad.md", "diagram_overrides": {"d2": {"bogus": 1}}}}

            with mock.patch("check_document_consistency.render_d2") as render_d2:
                issues = check_d2_blocks([doc], root, "pandoc", "d2", manifest_documents)

        self.assertEqual(1, len(issues))
        self.assertEqual("failed-d2-render", issues[0].check)
        self.assertIn("bogus", issues[0].detail)
        render_d2.assert_not_called()

    def test_a_document_with_no_manifest_entry_gets_no_overrides(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "hand-written.md"
            doc.write_text("```d2\na -> b\n```\n", encoding="utf-8")

            with mock.patch(
                "check_document_consistency.subprocess.run", return_value=self._ast_result("a -> b")
            ), mock.patch("check_document_consistency.render_d2") as render_d2:
                issues = check_d2_blocks([doc], root, "pandoc", "d2", {})

        self.assertEqual([], issues)
        render_d2.assert_called_once_with("a -> b", mock.ANY, command="d2", overrides=None)


@unittest.skipUnless(D2_AVAILABLE, "d2 and/or pandoc is not installed on PATH")
class CheckD2BlocksTests(unittest.TestCase):
    def test_a_valid_d2_block_renders_with_no_issues(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "sad.md"
            doc.write_text("```d2\na -> b\n```\n", encoding="utf-8")

            issues = check_d2_blocks([doc], root, "pandoc", "d2")

            self.assertEqual([], issues)

    def test_an_invalid_d2_block_is_flagged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "sad.md"
            doc.write_text(
                textwrap.dedent(
                    """
                    ```d2
                    a -> -> not valid d2 syntax
                    ```
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            issues = check_d2_blocks([doc], root, "pandoc", "d2")

            self.assertEqual(1, len(issues))
            self.assertEqual("failed-d2-render", issues[0].check)

    def test_attribute_order_does_not_matter_for_d2_block_detection(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            doc = root / "docs" / "sad.md"
            # `.d2` last, not first -- Pandoc doesn't care about attribute
            # order; this block must still be found and rendered, not
            # silently skipped by an attribute-order-sensitive regex.
            doc.write_text(
                '```{caption="x" .d2}\na -> -> not valid d2 syntax\n```\n',
                encoding="utf-8",
            )

            issues = check_d2_blocks([doc], root, "pandoc", "d2")

            self.assertEqual(1, len(issues))
            self.assertEqual("failed-d2-render", issues[0].check)


if __name__ == "__main__":
    unittest.main()
