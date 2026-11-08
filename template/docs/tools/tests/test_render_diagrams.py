import base64
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from render_diagrams import (  # noqa: E402
    BuildError,
    ChromiumNotConfiguredError,
    render_d2,
    render_diagram_blocks,
    render_mermaid,
    render_svg_to_png,
)
from render_diagrams import _run  # noqa: E402

# A font already present on the filesystem of any environment that can run
# these tests (the one this repository's own font-matching tooling targets
# elsewhere), used as fixture data for the embedded-font-resolution test
# below -- no real diagram-rendering binary required.
_FIXTURE_FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _real_chromium_executable() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _code_block(classes: list[str], source: str, caption: str | None = None) -> dict:
    key_values = [["caption", caption]] if caption is not None else []
    return {"t": "CodeBlock", "c": [["", classes, key_values], source]}


class RenderDiagramBlocksTests(unittest.TestCase):
    def test_fenced_block_is_dispatched_by_class_to_a_rendered_image(self):
        document = {
            "pandoc-api-version": [1, 23, 1],
            "meta": {},
            "blocks": [
                _code_block(["d2"], "browser -> api", caption="Upload trust boundary")
            ],
        }
        rendered = []

        def fake_renderer(source, destination):
            rendered.append((source, destination.name))
            destination.write_bytes(b"fake-png")

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            first = render_diagram_blocks(document, output_dir, {"d2": fake_renderer})
            second = render_diagram_blocks(document, output_dir, {"d2": fake_renderer})

        image = first["blocks"][0]["c"][0]
        self.assertEqual("Image", image["t"])
        caption = "".join(
            " " if inline["t"] == "Space" else inline["c"] for inline in image["c"][1]
        )
        self.assertEqual("Upload trust boundary", caption)
        self.assertEqual([], image["c"][0][1])
        self.assertEqual(first, second)
        self.assertRegex(image["c"][2][0], r"^diagram-01-[0-9a-f]{12}\.png$")
        self.assertEqual("browser -> api", rendered[0][0])
        self.assertEqual(rendered[0][1], rendered[1][1])

    def test_a_second_renderer_class_dispatches_to_its_own_renderer(self):
        document = {
            "pandoc-api-version": [1, 23, 1],
            "meta": {},
            "blocks": [
                _code_block(["d2"], "a -> b"),
                _code_block(["mermaid"], "C4Context"),
            ],
        }
        calls: dict[str, list[str]] = {"d2": [], "mermaid": []}

        def make_renderer(name):
            def renderer(source, destination):
                calls[name].append(source)
                destination.write_bytes(b"fake-png")

            return renderer

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            result = render_diagram_blocks(
                document,
                output_dir,
                {"d2": make_renderer("d2"), "mermaid": make_renderer("mermaid")},
            )

        self.assertEqual(["a -> b"], calls["d2"])
        self.assertEqual(["C4Context"], calls["mermaid"])
        self.assertEqual("Image", result["blocks"][0]["c"][0]["t"])
        self.assertEqual("Image", result["blocks"][1]["c"][0]["t"])

    def test_a_code_block_with_no_matching_class_is_unchanged(self):
        code_block = _code_block(["python"], "print('hello')")
        document = {
            "pandoc-api-version": [1, 23, 1],
            "meta": {},
            "blocks": [code_block],
        }

        result = render_diagram_blocks(document, Path("unused"), {"d2": lambda *_: None})

        self.assertEqual([code_block], result["blocks"])

    def test_empty_renderers_table_leaves_every_diagram_block_as_code(self):
        """Guard test: this must go red if dispatch is ever bypassed -- e.g.
        a future change that special-cases one class again instead of going
        through the `renderers` table."""
        d2_block = _code_block(["d2"], "a -> b")
        mermaid_block = _code_block(["mermaid"], "C4Context")
        document = {
            "pandoc-api-version": [1, 23, 1],
            "meta": {},
            "blocks": [d2_block, mermaid_block],
        }

        result = render_diagram_blocks(document, Path("unused"), {})

        self.assertEqual([d2_block, mermaid_block], result["blocks"])
        self.assertTrue(all(block["t"] == "CodeBlock" for block in result["blocks"]))


def _captured_argv(overrides):
    """Render a document through `render_d2` with the real `_run` and
    `render_svg_to_png` steps replaced by fakes, and return the argv `_run`
    was actually called with -- lets a test assert on the D2 CLI flags
    without a real `d2` binary."""
    captured = {}

    def fake_run(command):
        captured["argv"] = command
        Path(command[-1]).write_text("<svg></svg>", encoding="utf-8")
        return mock.Mock()

    with tempfile.TemporaryDirectory() as temporary_directory:
        destination = Path(temporary_directory) / "diagram.png"
        with (
            mock.patch("render_diagrams._run", side_effect=fake_run),
            mock.patch("render_diagrams.render_svg_to_png"),
        ):
            render_d2("a -> b", destination, overrides=overrides)
    return captured["argv"]


class RenderD2OverridesTests(unittest.TestCase):
    def test_a_document_with_no_overrides_keeps_exactly_d2_render_args(self):
        from render_diagrams import D2_RENDER_ARGS

        argv = _captured_argv(None)
        self.assertEqual(D2_RENDER_ARGS, argv[1 : 1 + len(D2_RENDER_ARGS)])

    def test_an_override_replaces_its_flag_without_duplicating_it(self):
        argv = _captured_argv({"scale": 1.5})
        self.assertIn("--scale=1.5", argv)
        self.assertEqual(1, sum(1 for arg in argv if arg.startswith("--scale")))
        self.assertIn("--layout=dagre", argv)  # untouched default stays

    def test_several_overrides_each_replace_only_their_own_flag(self):
        argv = _captured_argv({"layout": "elk", "pad": 64})
        self.assertIn("--layout=elk", argv)
        self.assertIn("--pad=64", argv)
        self.assertIn("--theme=0", argv)  # untouched default stays
        self.assertNotIn("--layout=dagre", argv)


class RunHelperTests(unittest.TestCase):
    def test_a_command_not_on_path_raises_build_error(self):
        with self.assertRaises(BuildError):
            _run(["a-command-that-certainly-does-not-exist-anywhere"])

    def test_a_failing_command_raises_build_error_with_its_output(self):
        with self.assertRaises(BuildError) as context:
            _run(["false"])
        self.assertIn("Command failed", str(context.exception))


@unittest.skipUnless(_FIXTURE_FONT_PATH.is_file(), "fixture font is unavailable")
class RenderSvgToPngFontResolutionTests(unittest.TestCase):
    def test_an_invented_embedded_font_name_is_resolved_and_renders_text(self):
        font_bytes = _FIXTURE_FONT_PATH.read_bytes()
        encoded = base64.b64encode(font_bytes).decode("ascii")
        invented_name = "diagram-tool-9999-font"
        svg_text = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">'
            f"<style>@font-face {{ font-family: {invented_name}; "
            f'src: url("data:font/ttf;base64,{encoded}"); }}</style>'
            f'<text x="10" y="30" font-family="{invented_name}">hello</text>'
            "</svg>"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            svg_path = directory / "diagram.svg"
            png_path = directory / "diagram.png"
            svg_path.write_text(svg_text, encoding="utf-8")

            render_svg_to_png(svg_path, png_path)

            self.assertTrue(png_path.is_file())
            self.assertTrue(png_path.read_bytes().startswith(b"\x89PNG"))

    def test_two_font_face_rules_sharing_one_invented_name_are_resolved_once(self):
        """A single SVG can legitimately embed the same invented font-family
        name more than once (e.g. once per weight variant reusing the base
        name); the second occurrence must be skipped, not re-decoded."""
        font_bytes = _FIXTURE_FONT_PATH.read_bytes()
        encoded = base64.b64encode(font_bytes).decode("ascii")
        invented_name = "diagram-tool-repeated-font"
        svg_text = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">'
            f"<style>@font-face {{ font-family: {invented_name}; "
            f'src: url("data:font/ttf;base64,{encoded}"); }}'
            f"@font-face {{ font-family: {invented_name}; "
            f'src: url("data:font/ttf;base64,{encoded}"); }}</style>'
            f'<text x="10" y="30" font-family="{invented_name}">hello</text>'
            "</svg>"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            svg_path = directory / "diagram.svg"
            png_path = directory / "diagram.png"
            svg_path.write_text(svg_text, encoding="utf-8")

            render_svg_to_png(svg_path, png_path)

            self.assertTrue(png_path.read_bytes().startswith(b"\x89PNG"))

    def test_rendering_twice_in_one_process_resolves_the_same_invented_name_both_times(self):
        """Two diagrams embedding the same font under the same invented name
        must both still resolve: the shared font directory this relies on
        must outlive each individual call, not just the first."""
        font_bytes = _FIXTURE_FONT_PATH.read_bytes()
        encoded = base64.b64encode(font_bytes).decode("ascii")
        invented_name = "diagram-tool-shared-font"
        svg_text = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">'
            f"<style>@font-face {{ font-family: {invented_name}; "
            f'src: url("data:font/ttf;base64,{encoded}"); }}</style>'
            f'<text x="10" y="30" font-family="{invented_name}">hello</text>'
            "</svg>"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for index in (1, 2):
                svg_path = directory / f"diagram-{index}.svg"
                png_path = directory / f"diagram-{index}.png"
                svg_path.write_text(svg_text, encoding="utf-8")
                render_svg_to_png(svg_path, png_path)
                self.assertTrue(png_path.read_bytes().startswith(b"\x89PNG"))


@unittest.skipUnless(shutil.which("d2"), "d2 is not on PATH")
class RenderD2RealBinaryTests(unittest.TestCase):
    def test_renders_a_real_d2_diagram_to_a_valid_png(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "diagram.png"
            render_d2("browser -> api: upload", destination)
            self.assertTrue(destination.is_file())
            self.assertTrue(destination.read_bytes().startswith(b"\x89PNG"))


class RenderMermaidChromiumTests(unittest.TestCase):
    def test_an_unset_chromium_executable_raises_and_never_invokes_mmdc(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "diagram.png"
            with mock.patch("render_diagrams._run") as fake_run:
                with self.assertRaises(ChromiumNotConfiguredError) as context:
                    render_mermaid("flowchart TD\n    A --> B", destination)
            fake_run.assert_not_called()
        self.assertIn("CHROMIUM_EXECUTABLE_PATH", str(context.exception))

    def test_a_nonexistent_chromium_executable_path_raises_naming_it_and_never_invokes_mmdc(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "diagram.png"
            missing_path = str(Path(temporary_directory) / "no-such-chrome")
            with mock.patch("render_diagrams._run") as fake_run:
                with self.assertRaises(ChromiumNotConfiguredError) as context:
                    render_mermaid(
                        "flowchart TD\n    A --> B",
                        destination,
                        chromium_executable=missing_path,
                    )
            fake_run.assert_not_called()
        self.assertIn(missing_path, str(context.exception))

    def test_a_valid_chromium_executable_passes_a_puppeteer_config_with_no_sandbox(self):
        """Guard test: must go red if `render_mermaid` ever stops passing
        `-p <puppeteer config>` alongside the existing `-c <mermaid config>`,
        or stops setting `executablePath`/`--no-sandbox` in it -- Puppeteer's
        bundled Chromium refuses to launch as root without `--no-sandbox`
        (confirmed against a real end-to-end render)."""
        captured: dict[str, object] = {}

        def fake_run(command):
            captured["command"] = list(command)
            output_index = command.index("-o")
            Path(command[output_index + 1]).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
            )
            config_index = command.index("-p")
            captured["config"] = json.loads(
                Path(command[config_index + 1]).read_text(encoding="utf-8")
            )
            return mock.Mock()

        with tempfile.TemporaryDirectory() as temporary_directory:
            chromium_path = Path(temporary_directory) / "chrome"
            chromium_path.write_text("", encoding="utf-8")
            destination = Path(temporary_directory) / "diagram.png"
            with (
                mock.patch("render_diagrams._run", side_effect=fake_run),
                mock.patch("render_diagrams.render_svg_to_png"),
            ):
                render_mermaid(
                    "flowchart TD\n    A --> B",
                    destination,
                    chromium_executable=str(chromium_path),
                )

        self.assertIn("-c", captured["command"])
        self.assertEqual(
            {"executablePath": str(chromium_path), "args": ["--no-sandbox"]},
            captured["config"],
        )


@unittest.skipUnless(
    shutil.which("mmdc") and _real_chromium_executable(),
    "mmdc or a Chromium/Chrome binary is not on PATH",
)
class RenderMermaidRealBinaryTests(unittest.TestCase):
    def test_renders_a_real_c4_diagram_to_a_valid_png(self):
        c4_source = (
            "C4Context\n"
            '    Person(user, "User")\n'
            '    System(system, "System")\n'
            "    Rel(user, system, \"Uses\")\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "diagram.png"
            render_mermaid(
                c4_source, destination, chromium_executable=_real_chromium_executable()
            )
            self.assertTrue(destination.is_file())
            self.assertTrue(destination.read_bytes().startswith(b"\x89PNG"))

    def test_flowchart_node_labels_render_as_plain_svg_text_not_blank_html(self):
        """Guard test: must go red if `render_mermaid` ever drops the `-c
        <config>` argument, or the config's `htmlLabels: false`. Without
        it, `mmdc` writes each flowchart node's label as HTML inside an
        SVG <foreignObject>, which the resvg-based rasterizer in
        `render_svg_to_png` does not render at all -- the diagram comes
        out with every label silently blank (verified manually: a
        flowchart rendered with this config omitted produces a PNG with
        empty boxes, no node text drawn)."""
        flowchart_source = "flowchart TD\n    A[Start] --> B[End]\n"
        captured = {}

        def capturing_render(svg_path, png_path):
            captured["svg"] = svg_path.read_text(encoding="utf-8")
            render_svg_to_png(svg_path, png_path)

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "diagram.png"
            with mock.patch(
                "render_diagrams.render_svg_to_png", side_effect=capturing_render
            ):
                render_mermaid(
                    flowchart_source,
                    destination,
                    chromium_executable=_real_chromium_executable(),
                )

        self.assertNotIn("foreignObject", captured["svg"])
        self.assertIn("Start", captured["svg"])
        self.assertIn("End", captured["svg"])


if __name__ == "__main__":
    unittest.main()
