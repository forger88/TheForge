import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import document_build


def _manifest(documents, **overrides):
    manifest = {
        "schema_version": 2,
        "toolchain": {
            "pandoc": {"command": "pandoc", "version": "3.11"},
            "d2": {"command": "d2", "version": "0.9.0"},
            "weasyprint": {"command": "weasyprint", "version": "70.0"},
            "font": "DejaVu Sans",
        },
        "documents": documents,
    }
    manifest.update(overrides)
    return manifest


class ValidateInputsTests(unittest.TestCase):
    def test_a_document_requesting_only_pptx_needs_no_style(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "a.md").write_text("# Test\n", encoding="utf-8")
            manifest = _manifest([{"source": "a.md", "outputs": ["pptx"]}])
            document_build._validate_inputs(manifest, root)  # no BuildError

    def test_a_document_requesting_pdf_requires_a_style_that_exists(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "a.md").write_text("# Test\n", encoding="utf-8")
            manifest = _manifest(
                [{"source": "a.md", "outputs": ["pdf"]}], style="missing.css"
            )
            with self.assertRaises(document_build.BuildError) as context:
                document_build._validate_inputs(manifest, root)
            self.assertIn("stylesheet", str(context.exception))

    def test_a_document_requesting_pdf_passes_when_its_style_exists(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "a.md").write_text("# Test\n", encoding="utf-8")
            (root / "style.css").write_text("body {}\n", encoding="utf-8")
            manifest = _manifest(
                [{"source": "a.md", "outputs": ["pdf"]}], style="style.css"
            )
            document_build._validate_inputs(manifest, root)  # no BuildError

    def test_an_unsupported_output_fails_validation_naming_the_document(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "a.md").write_text("# Test\n", encoding="utf-8")
            manifest = _manifest([{"source": "a.md", "outputs": ["docx"]}])
            with self.assertRaises(document_build.BuildError) as context:
                document_build._validate_inputs(manifest, root)
            self.assertIn("a.md", str(context.exception))
            self.assertIn("docx", str(context.exception))

    def test_a_document_with_no_outputs_at_all_fails_validation(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "a.md").write_text("# Test\n", encoding="utf-8")
            manifest = _manifest([{"source": "a.md", "outputs": []}])
            with self.assertRaises(document_build.BuildError) as context:
                document_build._validate_inputs(manifest, root)
            self.assertIn("a.md", str(context.exception))

    def test_a_missing_document_source_fails_validation(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            manifest = _manifest([{"source": "missing.md", "outputs": ["pptx"]}])
            with self.assertRaises(document_build.BuildError) as context:
                document_build._validate_inputs(manifest, root)
            self.assertIn("missing.md", str(context.exception))


class BuildRenderersBindsThePinnedCommandTests(unittest.TestCase):
    def test_d2_renderer_is_bound_to_the_manifests_pinned_command(self):
        manifest = _manifest(
            [],
            toolchain={
                "pandoc": {"command": "pandoc", "version": "3.11"},
                "d2": {"command": "/opt/pinned/d2", "version": "0.9.0"},
                "weasyprint": {"command": "weasyprint", "version": "70.0"},
                "font": "DejaVu Sans",
            },
        )
        renderers = document_build._build_renderers(manifest, {}, {})
        self.assertEqual("/opt/pinned/d2", renderers["d2"].keywords["command"])

    def test_mermaid_renderer_is_bound_to_the_manifests_pinned_mmdc_command(self):
        manifest = _manifest(
            [],
            toolchain={
                "pandoc": {"command": "pandoc", "version": "3.11"},
                "mmdc": {"command": "/opt/pinned/mmdc", "version": "11.0.0"},
                "weasyprint": {"command": "weasyprint", "version": "70.0"},
                "font": "DejaVu Sans",
            },
        )
        renderers = document_build._build_renderers(manifest, {}, {})
        self.assertEqual("/opt/pinned/mmdc", renderers["mermaid"].keywords["command"])

    def test_mermaid_renderer_binds_chromium_executable_from_the_environment(self):
        manifest = _manifest(
            [],
            toolchain={
                "pandoc": {"command": "pandoc", "version": "3.11"},
                "mmdc": {"command": "mmdc", "version": "11.0.0"},
                "weasyprint": {"command": "weasyprint", "version": "70.0"},
                "font": "DejaVu Sans",
            },
        )
        renderers = document_build._build_renderers(
            manifest, {}, {"CHROMIUM_EXECUTABLE_PATH": "/opt/chromium/chrome"}
        )
        self.assertEqual(
            "/opt/chromium/chrome", renderers["mermaid"].keywords["chromium_executable"]
        )

    def test_mermaid_renderer_has_no_chromium_executable_when_unset_in_the_environment(
        self,
    ):
        manifest = _manifest(
            [],
            toolchain={
                "pandoc": {"command": "pandoc", "version": "3.11"},
                "mmdc": {"command": "mmdc", "version": "11.0.0"},
                "weasyprint": {"command": "weasyprint", "version": "70.0"},
                "font": "DejaVu Sans",
            },
        )
        renderers = document_build._build_renderers(manifest, {}, {})
        self.assertIsNone(renderers["mermaid"].keywords["chromium_executable"])

    def test_mermaid_is_absent_from_the_table_when_the_manifest_has_no_mmdc_entry(self):
        manifest = _manifest([])  # the shared _manifest() helper's toolchain has no mmdc
        renderers = document_build._build_renderers(manifest, {}, {})
        self.assertNotIn("mermaid", renderers)
        self.assertIn("d2", renderers)

    def test_d2_renderer_binds_the_documents_own_overrides(self):
        manifest = _manifest([])
        document = {"source": "a.md", "diagram_overrides": {"d2": {"scale": 1.5}}}
        renderers = document_build._build_renderers(manifest, document, {})
        self.assertEqual({"scale": 1.5}, renderers["d2"].keywords["overrides"])

    def test_d2_renderer_has_no_overrides_when_the_document_names_none(self):
        manifest = _manifest([])
        renderers = document_build._build_renderers(manifest, {"source": "a.md"}, {})
        self.assertIsNone(renderers["d2"].keywords["overrides"])


class ValidateDiagramOverridesTests(unittest.TestCase):
    def test_a_document_with_no_diagram_overrides_key_passes(self):
        document_build._validate_diagram_overrides({"source": "a.md"})  # no BuildError

    def test_a_document_with_valid_overrides_passes(self):
        document = {
            "source": "a.md",
            "diagram_overrides": {"d2": {"layout": "elk", "theme": 1, "pad": 8, "scale": 1.5}},
        }
        document_build._validate_diagram_overrides(document)  # no BuildError

    def test_an_unknown_override_key_is_rejected_naming_the_document(self):
        document = {"source": "a.md", "diagram_overrides": {"d2": {"font_size": 12}}}
        with self.assertRaises(document_build.BuildError) as context:
            document_build._validate_diagram_overrides(document)
        self.assertIn("a.md", str(context.exception))
        self.assertIn("font_size", str(context.exception))

    def test_a_wrong_typed_value_is_rejected(self):
        document = {"source": "a.md", "diagram_overrides": {"d2": {"theme": "zero"}}}
        with self.assertRaises(document_build.BuildError) as context:
            document_build._validate_diagram_overrides(document)
        self.assertIn("theme", str(context.exception))

    def test_a_bool_is_rejected_for_an_int_typed_key(self):
        # isinstance(True, int) is True in Python, so the bool check must be
        # explicit or a bool would silently pass as a valid theme/pad value.
        document = {"source": "a.md", "diagram_overrides": {"d2": {"theme": True}}}
        with self.assertRaises(document_build.BuildError) as context:
            document_build._validate_diagram_overrides(document)
        self.assertIn("theme", str(context.exception))

    def test_an_unrecognized_layout_engine_is_rejected(self):
        document = {"source": "a.md", "diagram_overrides": {"d2": {"layout": "tree"}}}
        with self.assertRaises(document_build.BuildError) as context:
            document_build._validate_diagram_overrides(document)
        self.assertIn("layout", str(context.exception))

    def test_a_float_is_accepted_for_scale(self):
        document = {"source": "a.md", "diagram_overrides": {"d2": {"scale": 2.0}}}
        document_build._validate_diagram_overrides(document)  # no BuildError


class CheckDiagramToolchainCoverageTests(unittest.TestCase):
    def test_a_mermaid_fence_with_no_mmdc_toolchain_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "a.md"
            source.write_text("# Test\n\n```mermaid\nflowchart TD\n```\n", encoding="utf-8")
            manifest = _manifest([{"source": "a.md", "outputs": ["pptx"]}])
            self.assertNotIn("mmdc", manifest["toolchain"])
            with self.assertRaises(document_build.BuildError) as context:
                document_build._check_diagram_toolchain_coverage(
                    manifest["documents"][0], manifest, source
                )
            self.assertIn("mmdc", str(context.exception))
            self.assertIn("a.md", str(context.exception))

    def test_a_mermaid_fence_with_an_mmdc_toolchain_entry_passes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "a.md"
            source.write_text("# Test\n\n```mermaid\nflowchart TD\n```\n", encoding="utf-8")
            manifest = _manifest(
                [{"source": "a.md", "outputs": ["pptx"]}],
                toolchain={
                    "pandoc": {"command": "pandoc", "version": "3.11"},
                    "mmdc": {"command": "mmdc", "version": "11.0.0"},
                    "weasyprint": {"command": "weasyprint", "version": "70.0"},
                    "font": "DejaVu Sans",
                },
            )
            document_build._check_diagram_toolchain_coverage(
                manifest["documents"][0], manifest, source
            )  # no BuildError

    def test_a_document_with_no_diagram_fences_passes_regardless_of_toolchain(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "a.md"
            source.write_text("# Test\n\nno diagrams here.\n", encoding="utf-8")
            manifest = _manifest([{"source": "a.md", "outputs": ["pptx"]}])
            document_build._check_diagram_toolchain_coverage(
                manifest["documents"][0], manifest, source
            )  # no BuildError


class RenderDocumentDispatchesDiagramsOnceTests(unittest.TestCase):
    """Guard test: a document requesting several outputs must render its
    diagrams exactly once. This must go red if a future change moves the
    `render_diagram_blocks` call inside the per-output-format loop instead
    of calling it once, up front, for the whole document."""

    def _build(self, outputs):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (root / "a.md").write_text("# Test\n", encoding="utf-8")
        manifest = _manifest([{"source": "a.md", "outputs": outputs}])
        calls = []

        def fake_render_diagram_blocks(ast, output_dir, renderers):
            calls.append(ast)
            return ast

        emitters = {
            output_format: (lambda *args, _fmt=output_format: Path(f"fake.{_fmt}"))
            for output_format in outputs
        }

        with (
            mock.patch(
                "document_build.render_diagram_blocks",
                side_effect=fake_render_diagram_blocks,
            ),
            mock.patch.object(document_build, "_run") as fake_run,
            mock.patch.object(document_build, "_EMITTERS", emitters),
        ):
            fake_run.return_value = mock.Mock(stdout="{}", stderr="")
            result = document_build._render_document(
                manifest["documents"][0], manifest, root, {}
            )
        return calls, result

    def test_render_diagram_blocks_is_called_exactly_once_for_two_requested_outputs(
        self,
    ):
        calls, outputs = self._build(["pdf", "pptx"])
        self.assertEqual(1, len(calls))
        self.assertEqual(2, len(outputs))

    def test_render_diagram_blocks_is_called_exactly_once_for_one_requested_output(
        self,
    ):
        calls, outputs = self._build(["pptx"])
        self.assertEqual(1, len(calls))
        self.assertEqual(1, len(outputs))


class LoadManifestTests(unittest.TestCase):
    def test_wrong_schema_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            manifest_path = root / "document-build.json"
            manifest_path.write_text(
                json.dumps({"schema_version": 1, "documents": [{}]}), encoding="utf-8"
            )
            with self.assertRaises(document_build.BuildError) as context:
                document_build._load_manifest(manifest_path)
            self.assertIn("schema_version 2", str(context.exception))


if __name__ == "__main__":
    unittest.main()
