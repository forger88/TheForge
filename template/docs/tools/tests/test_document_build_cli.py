import contextlib
import io
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import document_build


def _manifest(documents, **overrides):
    manifest = {
        "schema_version": 2,
        "repository_root": ".",
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


class DocumentBuildCliTests(unittest.TestCase):
    """Runs document_build.main() itself in-process (so coverage sees its
    own code), while every external tool it shells out to (pandoc, d2,
    weasyprint) is still a real, separate OS process -- a fake one on a
    scratch PATH, faithful to how main() actually invokes them."""

    def _run_main(self, root, argv):
        tools = root / "bin"
        tools.mkdir()
        self._write_fake_tools(tools)
        environment = {"PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")}
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(os.environ, environment),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            returncode = document_build.main(argv)
        return returncode, stdout.getvalue(), stderr.getvalue()

    def test_one_document_requesting_pdf_and_pptx_builds_both_from_one_diagram_render(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text(
                "# Test\n\n```d2\na -> b\n```\n", encoding="utf-8"
            )
            (root / "style.css").write_text(
                "body { font-family: 'DejaVu Sans'; }\n", encoding="utf-8"
            )
            manifest = _manifest(
                [{"source": "source.md", "outputs": ["pdf", "pptx"]}],
                style="style.css",
            )
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            returncode, _stdout, stderr = self._run_main(
                root, ["--manifest", str(manifest_path)]
            )

            self.assertEqual(0, returncode, stderr)
            self.assertTrue(
                (root / "docs" / "_build" / "pdfs" / "source.pdf").is_file()
            )
            self.assertTrue(
                (root / "docs" / "_build" / "pptx" / "source.pptx").is_file()
            )
            diagrams = list(
                (root / "docs" / "_build" / "diagrams" / "source").glob("*.png")
            )
            # Exactly one diagram image, not one per requested output format.
            self.assertEqual(1, len(diagrams))

    def test_check_validates_without_building_anything(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text("# Test\n", encoding="utf-8")
            manifest = _manifest([{"source": "source.md", "outputs": ["pptx"]}])
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            returncode, _stdout, stderr = self._run_main(
                root, ["--manifest", str(manifest_path), "--check"]
            )

            self.assertEqual(0, returncode, stderr)
            self.assertFalse((root / "docs" / "_build").exists())

    def test_check_fails_on_a_mermaid_block_when_the_manifest_has_no_mmdc_entry(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text(
                "# Test\n\n```mermaid\nflowchart TD\n```\n", encoding="utf-8"
            )
            manifest = _manifest([{"source": "source.md", "outputs": ["pptx"]}])
            self.assertNotIn("mmdc", manifest["toolchain"])
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            returncode, _stdout, stderr = self._run_main(
                root, ["--manifest", str(manifest_path), "--check"]
            )

            self.assertEqual(2, returncode)
            self.assertIn("mmdc", stderr)
            self.assertFalse((root / "docs" / "_build").exists())

    def test_mermaid_document_is_skipped_when_chromium_executable_path_is_unset_other_documents_still_build(
        self,
    ):
        """Guard test: a document whose render needs Chromium and can't get
        it is skipped (logged, no output file) while every other document
        in the same build still produces its output, and `main` still
        returns non-zero overall -- "fail loudly" means the build reports
        failure, not a quiet partial success (owner decision, 2026-11-01)."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "mermaid.md").write_text(
                "# Test\n\n```mermaid\nflowchart TD\n    A --> B\n```\n",
                encoding="utf-8",
            )
            (root / "plain.md").write_text("# Plain\n", encoding="utf-8")
            manifest = _manifest(
                [
                    {"source": "mermaid.md", "outputs": ["pptx"]},
                    {"source": "plain.md", "outputs": ["pptx"]},
                ],
                toolchain={
                    "pandoc": {"command": "pandoc", "version": "3.11"},
                    "mmdc": {"command": "mmdc", "version": "11.0.0"},
                    "weasyprint": {"command": "weasyprint", "version": "70.0"},
                    "font": "DejaVu Sans",
                },
            )
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            tools = root / "bin"
            tools.mkdir()
            self._write_fake_tools(tools)
            # Explicitly "" (falsy), not merely absent: mock.patch.dict only
            # adds/overrides keys, so an ambient CHROMIUM_EXECUTABLE_PATH in
            # the real test-running environment could otherwise leak in.
            environment = {
                "PATH": str(tools) + os.pathsep + os.environ.get("PATH", ""),
                "CHROMIUM_EXECUTABLE_PATH": "",
            }
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                mock.patch.dict(os.environ, environment),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                returncode = document_build.main(["--manifest", str(manifest_path)])

            self.assertEqual(2, returncode)
            self.assertIn("error: skipping mermaid.md", stderr.getvalue())
            self.assertIn("CHROMIUM_EXECUTABLE_PATH", stderr.getvalue())
            self.assertFalse(
                (root / "docs" / "_build" / "pptx" / "mermaid.pptx").is_file()
            )
            self.assertTrue(
                (root / "docs" / "_build" / "pptx" / "plain.pptx").is_file()
            )

    def test_an_unsupported_output_format_fails_before_any_toolchain_call(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text("# Test\n", encoding="utf-8")
            manifest = _manifest([{"source": "source.md", "outputs": ["docx"]}])
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            returncode, _stdout, stderr = self._run_main(
                root, ["--manifest", str(manifest_path)]
            )

            self.assertEqual(2, returncode)
            self.assertIn("source.md", stderr)
            self.assertIn("docx", stderr)

    def test_a_renderer_failure_is_caught_as_a_build_error_not_an_uncaught_exception(
        self,
    ):
        """Guard test: before `render_diagrams.py` and `document_build.py`
        shared one `BuildError` class, this scenario raised an uncaught
        `render_diagrams.BuildError` -- `main`'s `except (BuildError, ...)`
        only ever caught its own, different, class -- and the process
        exited 1 with a Python traceback instead of 2 with `error: ...`.
        The fake `d2`'s version check still succeeds, so `_check_toolchain`
        passes; only the later render invocation fails, isolating this to
        the renderer's own failure path, not toolchain validation."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text(
                "# Test\n\n```d2\na -> b\n```\n", encoding="utf-8"
            )
            manifest = _manifest([{"source": "source.md", "outputs": ["pptx"]}])
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            tools = root / "bin"
            tools.mkdir()
            self._write_fake_tools(tools)
            d2_wrapper = tools / "d2"
            d2_wrapper.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "version" ]; then echo v0.9.0; exit 0; fi\n'
                'echo "d2: simulated render failure" >&2\n'
                "exit 1\n",
                encoding="utf-8",
            )
            d2_wrapper.chmod(0o755)
            environment = {"PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")}
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                mock.patch.dict(os.environ, environment),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                returncode = document_build.main(["--manifest", str(manifest_path)])

            self.assertEqual(2, returncode)
            self.assertIn("error:", stderr.getvalue())

    def test_a_pinned_renderer_command_is_invoked_instead_of_the_bare_name(self):
        """Guard test: `_build_renderers` must bind the manifest's pinned
        `toolchain.d2.command`, not the literal `"d2"`. The fake tools
        directory below provides no `d2` executable at all, only one named
        `d2-pinned` -- if the renderer ever falls back to the bare name,
        `shutil.which("d2")` finds nothing and the build fails with
        "command ... not found", not a successful render."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text(
                "# Test\n\n```d2\na -> b\n```\n", encoding="utf-8"
            )
            manifest = _manifest(
                [{"source": "source.md", "outputs": ["pptx"]}],
                toolchain={
                    "pandoc": {"command": "pandoc", "version": "3.11"},
                    "d2": {"command": "d2-pinned", "version": "0.9.0"},
                    "weasyprint": {"command": "weasyprint", "version": "70.0"},
                    "font": "DejaVu Sans",
                },
            )
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            tools = root / "bin"
            tools.mkdir()
            self._write_fake_tools(tools)
            driver = tools / "fake_tool.py"
            if os.name == "nt":
                (tools / "d2.cmd").unlink()
                wrapper = tools / "d2-pinned.cmd"
                wrapper.write_text(
                    f'@"{sys.executable}" "{driver}" d2 %*\n', encoding="utf-8"
                )
            else:
                (tools / "d2").unlink()
                wrapper = tools / "d2-pinned"
                wrapper.write_text(
                    f'#!/bin/sh\nexec "{sys.executable}" "{driver}" d2 "$@"\n',
                    encoding="utf-8",
                )
                wrapper.chmod(0o755)

            environment = {"PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")}
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                mock.patch.dict(os.environ, environment),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                returncode = document_build.main(["--manifest", str(manifest_path)])

            self.assertEqual(0, returncode, stderr.getvalue())
            self.assertTrue(
                (root / "docs" / "_build" / "pptx" / "source.pptx").is_file()
            )

    def test_reuse_screenshots_and_pdf_only_document(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text("# Test\n", encoding="utf-8")
            (root / "style.css").write_text(
                "body { font-family: 'DejaVu Sans'; }\n", encoding="utf-8"
            )
            (root / "screenshots").mkdir()
            (root / "screenshots" / "screen.png").write_bytes(b"png")
            manifest = _manifest(
                [{"source": "source.md", "outputs": ["pdf"]}],
                style="style.css",
                screenshots={
                    "cwd": ".",
                    "command": ["unused-in-fast-mode"],
                    "output_directory": "screenshots",
                    "expected": ["screen.png"],
                    "services": [],
                },
            )
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            returncode, stdout, stderr = self._run_main(
                root, ["--manifest", str(manifest_path), "--reuse-screenshots"]
            )

            self.assertEqual(0, returncode, stderr)
            self.assertTrue(
                (root / "docs" / "_build" / "pdfs" / "source.pdf").is_file()
            )
            self.assertIn("Reusing 1 committed screenshot", stdout)

    def test_default_build_regenerates_screenshots_via_the_capture_command(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text("# Test\n", encoding="utf-8")
            (root / "style.css").write_text(
                "body { font-family: 'DejaVu Sans'; }\n", encoding="utf-8"
            )
            (root / "screenshots").mkdir()
            (root / "screenshots" / "screen.png").write_bytes(b"old")
            capture = root / "capture.py"
            capture.write_text(
                "import os\nfrom pathlib import Path\n"
                "Path(os.environ['SCREENSHOTS_DIR'], 'screen.png').write_bytes(b'new')\n",
                encoding="utf-8",
            )
            manifest = _manifest(
                [{"source": "source.md", "outputs": ["pdf"]}],
                style="style.css",
                screenshots={
                    "cwd": ".",
                    "command": [sys.executable, str(capture)],
                    "output_directory": "screenshots",
                    "expected": ["screen.png"],
                    "services": [],
                },
            )
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            returncode, stdout, stderr = self._run_main(
                root, ["--manifest", str(manifest_path)]
            )

            self.assertEqual(0, returncode, stderr)
            self.assertEqual(b"new", (root / "screenshots" / "screen.png").read_bytes())
            self.assertIn("Regenerated 1 screenshot", stdout)

    def test_a_manifest_with_no_screenshots_key_is_valid(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.md").write_text("# Test\n", encoding="utf-8")
            manifest = _manifest([{"source": "source.md", "outputs": ["pptx"]}])
            self.assertNotIn("screenshots", manifest)
            manifest_path = root / "document-build.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            returncode, _stdout, stderr = self._run_main(
                root, ["--manifest", str(manifest_path)]
            )

            self.assertEqual(0, returncode, stderr)
            self.assertTrue(
                (root / "docs" / "_build" / "pptx" / "source.pptx").is_file()
            )

    def _write_fake_tools(self, directory):
        driver = directory / "fake_tool.py"
        driver.write_text(
            textwrap.dedent(
                """
                import json
                import pathlib
                import sys

                tool, *args = sys.argv[1:]
                if tool == "pandoc" and "--version" in args:
                    print("pandoc 3.11")
                elif tool == "d2" and args == ["version"]:
                    print("v0.9.0")
                elif tool == "weasyprint" and "--version" in args:
                    print("WeasyPrint version 70.0")
                elif tool == "mmdc" and "--version" in args:
                    print("11.0.0")
                elif tool == "fc-match":
                    print("DejaVu Sans")
                elif tool == "pandoc" and args[args.index("--to") + 1] == "json":
                    # The fixture source files below never actually drive
                    # pandoc's own parse (that's exactly what's faked here);
                    # which diagram class comes back is keyed on the source
                    # filename so a test can ask for a "mermaid" document
                    # without this canned response always returning "d2".
                    if "mermaid" in pathlib.Path(args[0]).stem:
                        block = {
                            "t": "CodeBlock",
                            "c": [["", ["mermaid"], []], "flowchart TD\\n    A --> B"],
                        }
                    else:
                        block = {"t": "CodeBlock", "c": [["", ["d2"], []], "a -> b"]}
                    print(json.dumps({
                        "pandoc-api-version": [1, 23, 1],
                        "meta": {},
                        "blocks": [block],
                    }))
                elif tool == "pandoc" and args[args.index("--to") + 1] == "html5":
                    output = pathlib.Path(args[args.index("--output") + 1])
                    output.write_text("<html><body>document</body></html>", encoding="utf-8")
                elif tool == "pandoc" and args[args.index("--to") + 1] == "pptx":
                    output = pathlib.Path(args[args.index("--output") + 1])
                    # A pptx file is a zip archive; a bare "PK" signature is
                    # enough for document_build.py's own file-shape check.
                    output.write_bytes(b"PK\\x03\\x04fake-pptx")
                elif tool == "d2":
                    # vl_convert.svg_to_png needs valid SVG, not arbitrary bytes.
                    pathlib.Path(args[-1]).write_text(
                        '<svg xmlns="http://www.w3.org/2000/svg" '
                        'width="10" height="10"></svg>',
                        encoding="utf-8",
                    )
                elif tool == "weasyprint":
                    pathlib.Path(args[-1]).write_bytes(b"%PDF-1.7 fake")
                else:
                    raise SystemExit(f"unexpected fake tool invocation: {tool} {args}")
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        for tool in ("pandoc", "d2", "weasyprint", "fc-match", "mmdc"):
            if os.name == "nt":
                wrapper = directory / f"{tool}.cmd"
                wrapper.write_text(
                    f'@"{sys.executable}" "{driver}" {tool} %*\n', encoding="utf-8"
                )
            else:
                wrapper = directory / tool
                wrapper.write_text(
                    f'#!/bin/sh\nexec "{sys.executable}" "{driver}" {tool} "$@"\n',
                    encoding="utf-8",
                )
                wrapper.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
