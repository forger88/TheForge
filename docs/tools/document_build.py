#!/usr/bin/env python3
"""Build a project's screenshots and documents from one manifest.

One Pandoc AST is built per document and its diagrams are rendered exactly
once from that AST (`render_diagrams.render_diagram_blocks`), then every
output format the document's manifest entry requests is emitted from that
same AST -- a document that needs both a PDF and a slide deck is one
manifest entry, not two separate build scripts each re-deriving the same
diagrams.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from build_errors import BuildError, ChromiumNotConfiguredError
from render_diagrams import render_d2, render_diagram_blocks, render_mermaid

_SCHEMA_VERSION = 2
_VALID_OUTPUTS = {"pdf", "pptx"}

# A document's `diagram_overrides.d2` key -> the type it must have. Keep in
# step with `render_diagrams._D2_OVERRIDE_FLAGS`, which maps the same keys to
# D2 CLI flags; this table is what keeps a manifest from smuggling an
# arbitrary flag into that call (docs/security/threat-model.md T25).
_D2_OVERRIDE_TYPES: dict[str, type | tuple[type, ...]] = {
    "layout": str,
    "theme": int,
    "pad": int,
    "scale": (int, float),
}
_D2_LAYOUT_ENGINES = {"dagre", "elk"}

# Fenced-code-block class -> renderer, keyed the same way
# `render_diagram_blocks` keys its `renderers` table. Each renderer's
# toolchain entry name (the key `_check_toolchain` and `_build_renderers`
# below both read) -- not necessarily equal to the fence class name, since
# the toolchain command is `mmdc`, not `mermaid`.
_TOOLCHAIN_ENTRY_BY_CLASS = {"d2": "d2", "mermaid": "mmdc"}
# A fenced code block whose info string's first word names one of the keys
# above (```mermaid, ```d2), at the start of a line -- Pandoc classes a
# CodeBlock by exactly that first word. A lightweight text scan, not a full
# Pandoc parse: `--check` and `_validate_inputs` run with no guarantee
# pandoc has already been found on PATH.
_DIAGRAM_FENCE_RE = re.compile(
    r"^`{3,}("
    + "|".join(re.escape(name) for name in _TOOLCHAIN_ENTRY_BY_CLASS)
    + r")\b",
    re.MULTILINE,
)


def _run(
    command: list[str], *, cwd: Path, env: dict[str, str], capture: bool = False
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0])
    if executable is None:
        raise BuildError(f"Required command '{command[0]}' was not found on PATH.")
    resolved = [executable, *command[1:]]
    try:
        return subprocess.run(
            resolved,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=capture,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        suffix = f"\n{detail}" if detail else ""
        raise BuildError(f"Command failed ({' '.join(command)}).{suffix}") from error


def _version_from(output: str) -> str:
    match = re.search(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)", output)
    if not match:
        raise BuildError(f"Could not read a semantic version from: {output.strip()!r}")
    return match.group(1)


def _build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "SOURCE_DATE_EPOCH": "0",
            "PYTHONHASHSEED": "0",
        }
    )
    return environment


def _load_manifest(path: Path) -> tuple[dict[str, Any], Path]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BuildError(
            f"Could not read documentation manifest {path}: {error}"
        ) from error
    if manifest.get("schema_version") != _SCHEMA_VERSION:
        raise BuildError(
            f"document-build.json must have schema_version {_SCHEMA_VERSION}."
        )
    repository_root = (path.parent / manifest.get("repository_root", ".")).resolve()
    if not manifest.get("documents"):
        raise BuildError("document-build.json must list at least one document.")
    return manifest, repository_root


def _check_toolchain(manifest: dict[str, Any], root: Path, env: dict[str, str]) -> None:
    # Every toolchain entry present in the manifest is checked, not a fixed
    # list: a project that never uses `mermaid` fenced blocks has no `mmdc`
    # entry at all, and a future diagram tool needs no change here to be
    # checked too -- it only needs its own entry in the manifest.
    version_arguments_by_command = {
        "pandoc": ["--version"],
        "d2": ["version"],
        "mmdc": ["--version"],
        "weasyprint": ["--version"],
    }
    for name, settings in manifest["toolchain"].items():
        if not isinstance(settings, dict):
            continue  # `font` is a bare string, not a {command, version} pair.
        command = settings["command"]
        version_arguments = version_arguments_by_command.get(name, ["--version"])
        if shutil.which(command) is None:
            raise BuildError(
                f"Required {name} command '{command}' was not found on PATH. "
                "See docs/development/documentation-build.md for pinned setup instructions."
            )
        result = _run([command, *version_arguments], cwd=root, env=env, capture=True)
        actual = _version_from(result.stdout + result.stderr)
        expected = settings["version"]
        if actual != expected:
            raise BuildError(
                f"{name} {expected} is required, but {actual} is installed. "
                f"See docs/development/documentation-build.md for pinned setup instructions."
            )

    font = manifest["toolchain"]["font"]
    if shutil.which("fc-match") is None:
        raise BuildError(
            "Required fontconfig command 'fc-match' was not found on PATH. "
            "See docs/development/documentation-build.md for OS packages and font setup."
        )
    result = _run(
        ["fc-match", "--format=%{family}", font], cwd=root, env=env, capture=True
    )
    families = [item.strip() for item in result.stdout.split(",")]
    if font not in families:
        raise BuildError(
            f"Required font '{font}' is unavailable (fontconfig selected {result.stdout.strip()!r}). "
            f"Install the {font} font family and run 'fc-match \"{font}\"' to verify it."
        )
    print(f"Toolchain OK: {', '.join(sorted(manifest['toolchain']))}")


def _build_renderers(
    manifest: dict[str, Any], document: dict[str, Any], environment: dict[str, str]
) -> dict[str, Any]:
    """The `render_diagram_blocks` renderer table, bound to the exact
    commands `_check_toolchain` version-checked -- never the bare `d2`/
    `mmdc` names on PATH, which could resolve to a different, unchecked
    binary than the one the manifest pins. A class whose toolchain entry
    the manifest doesn't have (e.g. no `mmdc` entry) is simply absent from
    this table; `_check_diagram_toolchain_coverage` is what turns that
    absence into a `BuildError` instead of a silently un-rendered block.

    `document`'s own `diagram_overrides.d2`, if any, is bound here too, so
    every block in this one document's single render (`_render_document`)
    gets it -- there's no per-block override, only per-document.

    `mmdc`'s Chromium comes from `environment["CHROMIUM_EXECUTABLE_PATH"]`,
    never the manifest (design-exit resolution, docs/design/doc-build-setup.md
    "build-vs-buy"): the value is produced by whatever already installs a
    browser in that environment, not authored per-project.
    """
    renderers: dict[str, Any] = {}
    if "d2" in manifest["toolchain"]:
        renderers["d2"] = functools.partial(
            render_d2,
            command=manifest["toolchain"]["d2"]["command"],
            overrides=document.get("diagram_overrides", {}).get("d2"),
        )
    if "mmdc" in manifest["toolchain"]:
        renderers["mermaid"] = functools.partial(
            render_mermaid,
            command=manifest["toolchain"]["mmdc"]["command"],
            chromium_executable=environment.get("CHROMIUM_EXECUTABLE_PATH"),
        )
    return renderers


def _validate_inputs(manifest: dict[str, Any], root: Path) -> None:
    documents = manifest["documents"]
    needs_style = any("pdf" in document.get("outputs", []) for document in documents)
    if needs_style:
        style = root / manifest["style"]
        if not style.is_file():
            raise BuildError(f"PDF stylesheet does not exist: {style}")

    for document in documents:
        source = root / document["source"]
        if not source.is_file():
            raise BuildError(f"Document source does not exist: {source}")
        outputs = document.get("outputs") or []
        if not outputs:
            raise BuildError(f"Document has no outputs: {document['source']}")
        invalid = [item for item in outputs if item not in _VALID_OUTPUTS]
        if invalid:
            raise BuildError(
                f"Document {document['source']} has unsupported outputs {invalid}; "
                f"each entry must be one of {sorted(_VALID_OUTPUTS)}."
            )
        _check_diagram_toolchain_coverage(document, manifest, source)
        _validate_diagram_overrides(document)


def _validate_diagram_overrides(document: dict[str, Any]) -> None:
    """Allowlist and type-check `document["diagram_overrides"]["d2"]` before
    it ever reaches `render_d2`'s CLI argv (docs/security/threat-model.md
    T25): a manifest value is data, not a vector for smuggling an arbitrary
    flag (an output path, `--watch`) into the pinned `d2` binary.
    """
    overrides = document.get("diagram_overrides", {}).get("d2")
    if overrides is None:
        return
    source = document["source"]
    unknown = sorted(set(overrides) - set(_D2_OVERRIDE_TYPES))
    if unknown:
        raise BuildError(
            f"Document {source} has unknown diagram_overrides.d2 key(s) {unknown}; "
            f"each key must be one of {sorted(_D2_OVERRIDE_TYPES)}."
        )
    for key, value in overrides.items():
        expected = _D2_OVERRIDE_TYPES[key]
        if isinstance(value, bool) or not isinstance(value, expected):
            raise BuildError(
                f"Document {source} has diagram_overrides.d2.{key}={value!r}, "
                f"which is not a {expected}."
            )
    layout = overrides.get("layout")
    if layout is not None and layout not in _D2_LAYOUT_ENGINES:
        raise BuildError(
            f"Document {source} has diagram_overrides.d2.layout={layout!r}; "
            f"must be one of {sorted(_D2_LAYOUT_ENGINES)}."
        )


def _check_diagram_toolchain_coverage(
    document: dict[str, Any], manifest: dict[str, Any], source: Path
) -> None:
    """Fail the same way `--check` fails any other missing-toolchain gap,
    not by silently leaving a diagram block as plain code text in the
    output: a document with a fenced block of a diagram class whose
    toolchain entry the manifest doesn't have is a configuration error,
    caught here before any pandoc call, the same place `_check_toolchain`
    catches a missing or wrong-version binary.
    """
    text = source.read_text(encoding="utf-8")
    classes = {match.group(1) for match in _DIAGRAM_FENCE_RE.finditer(text)}
    missing = sorted(
        {
            _TOOLCHAIN_ENTRY_BY_CLASS[name]
            for name in classes
            if _TOOLCHAIN_ENTRY_BY_CLASS[name] not in manifest["toolchain"]
        }
    )
    if missing:
        raise BuildError(
            f"Document {document['source']} has a fenced block that needs "
            f"{', '.join(missing)}, but document-build.json's toolchain has no "
            f"entry for it."
        )


def _url_is_ready(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except urllib.error.HTTPError as error:
        return error.code < 500
    except (OSError, urllib.error.URLError):
        return False


class ManagedServices(AbstractContextManager["ManagedServices"]):
    def __init__(
        self,
        services: list[dict[str, Any]],
        root: Path,
        env: dict[str, str],
        logs_dir: Path,
    ):
        self.services = services
        self.root = root
        self.env = env
        self.logs_dir = logs_dir
        self.processes: list[tuple[str, subprocess.Popen[str], Any, Path]] = []

    def __enter__(self) -> ManagedServices:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        try:
            for service in self.services:
                self._start(service)
        except Exception:
            self._stop_all()
            raise
        return self

    def _start(self, service: dict[str, Any]) -> None:
        name = service["name"]
        ready_url = service["ready_url"]
        if _url_is_ready(ready_url):
            raise BuildError(
                f"Cannot start controlled {name}: {ready_url} is already in use. "
                "Stop the existing service before a release documentation build."
            )
        command = service["command"]
        executable = shutil.which(command[0])
        if executable is None:
            raise BuildError(
                f"Cannot start {name}: required command '{command[0]}' was not found on PATH."
            )
        service_env = self.env.copy()
        service_env.update(
            {key: str(value) for key, value in service.get("environment", {}).items()}
        )
        log_path = self.logs_dir / f"{name}.log"
        log = log_path.open("w", encoding="utf-8")
        process_options: dict[str, Any] = {}
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True
        try:
            process = subprocess.Popen(
                [executable, *command[1:]],
                cwd=self.root / service["cwd"],
                env=service_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                **process_options,
            )
        except Exception:
            log.close()
            raise
        self.processes.append((name, process, log, log_path))
        deadline = time.monotonic() + float(service.get("timeout_seconds", 60))
        while time.monotonic() < deadline:
            if process.poll() is not None:
                log.flush()
                detail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
                raise BuildError(
                    f"{name} exited before becoming ready. See {log_path}.\n{detail}"
                )
            if _url_is_ready(ready_url):
                print(f"Started controlled {name} at {ready_url}")
                return
            time.sleep(0.5)
        raise BuildError(
            f"Timed out waiting for {name} at {ready_url}. See {log_path}."
        )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._stop_all()

    def _stop_all(self) -> None:
        for _name, process, _log, _path in reversed(self.processes):
            if process.poll() is None:
                if os.name == "nt":
                    process.terminate()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
        for _name, process, log, _path in reversed(self.processes):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=5)
            log.close()
        self.processes.clear()


def _validate_screenshots(config: dict[str, Any], directory: Path) -> None:
    missing = [name for name in config["expected"] if not (directory / name).is_file()]
    if missing:
        raise BuildError(
            f"Missing expected screenshots in {directory}: {', '.join(missing)}"
        )


def _prepare_screenshots(
    config: dict[str, Any], root: Path, env: dict[str, str], reuse: bool
) -> None:
    output_directory = root / config["output_directory"]
    if reuse:
        _validate_screenshots(config, output_directory)
        print(
            f"Reusing {len(config['expected'])} committed screenshot(s) from {output_directory}"
        )
        return

    staging_parent = root / "docs" / "_build" / "screenshots"
    staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="capture-", dir=staging_parent
    ) as temporary_directory:
        staging = Path(temporary_directory)
        capture_env = env.copy()
        capture_env["SCREENSHOTS_DIR"] = str(staging)
        for key, value in config.get("environment", {}).items():
            capture_env[key] = str(value)
        services = ManagedServices(
            config.get("services", []),
            root,
            capture_env,
            root / "docs" / "_build" / "logs",
        )
        with services:
            _run(config["command"], cwd=root / config["cwd"], env=capture_env)
        _validate_screenshots(config, staging)
        output_directory.mkdir(parents=True, exist_ok=True)
        for name in config["expected"]:
            shutil.copy2(staging / name, output_directory / name)
    print(f"Regenerated {len(config['expected'])} screenshot(s) in {output_directory}")


def _emit_pdf(
    ast: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
    env: dict[str, str],
    source: Path,
    diagram_directory: Path,
    stem: str,
) -> Path:
    pandoc = manifest["toolchain"]["pandoc"]["command"]
    weasyprint = manifest["toolchain"]["weasyprint"]["command"]
    style = root / manifest["style"]
    output = root / "docs" / "_build" / "pdfs" / f"{stem}.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    resource_path = os.pathsep.join(
        (str(source.parent), str(diagram_directory), str(root))
    )
    with tempfile.TemporaryDirectory(
        prefix="document-", dir=root / "docs" / "_build"
    ) as work:
        work_directory = Path(work)
        ast_path = work_directory / "document.json"
        html_path = work_directory / "document.html"
        ast_path.write_text(json.dumps(ast, ensure_ascii=False), encoding="utf-8")
        _run(
            [
                pandoc,
                str(ast_path),
                "--from",
                "json",
                "--to",
                "html5",
                "--standalone",
                "--embed-resources",
                f"--resource-path={resource_path}",
                f"--css={style}",
                "--output",
                str(html_path),
            ],
            cwd=root,
            env=env,
        )
        _run([weasyprint, str(html_path), str(output)], cwd=root, env=env)
    if not output.is_file() or not output.read_bytes().startswith(b"%PDF"):
        raise BuildError(f"PDF engine did not create a valid PDF header at {output}")
    print(f"Wrote {output}")
    return output


def _emit_pptx(
    ast: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
    env: dict[str, str],
    source: Path,
    diagram_directory: Path,
    stem: str,
) -> Path:
    pandoc = manifest["toolchain"]["pandoc"]["command"]
    output = root / "docs" / "_build" / "pptx" / f"{stem}.pptx"
    output.parent.mkdir(parents=True, exist_ok=True)
    resource_path = os.pathsep.join(
        (str(source.parent), str(diagram_directory), str(root))
    )
    with tempfile.TemporaryDirectory(
        prefix="document-", dir=root / "docs" / "_build"
    ) as work:
        work_directory = Path(work)
        ast_path = work_directory / "document.json"
        ast_path.write_text(json.dumps(ast, ensure_ascii=False), encoding="utf-8")
        _run(
            [
                pandoc,
                str(ast_path),
                "--from",
                "json",
                "--to",
                "pptx",
                "--slide-level=2",
                f"--resource-path={resource_path}",
                "--output",
                str(output),
            ],
            cwd=root,
            env=env,
        )
    if not output.is_file() or output.read_bytes()[:2] != b"PK":
        raise BuildError(f"Pandoc did not create a valid pptx (zip) file at {output}")
    print(f"Wrote {output}")
    return output


_EMITTERS = {"pdf": _emit_pdf, "pptx": _emit_pptx}


def _render_document(
    document: dict[str, Any], manifest: dict[str, Any], root: Path, env: dict[str, str]
) -> list[Path]:
    source = root / document["source"]
    if not source.is_file():
        raise BuildError(f"Document source does not exist: {source}")
    stem = source.stem
    diagram_directory = root / "docs" / "_build" / "diagrams" / stem
    if diagram_directory.exists():
        shutil.rmtree(diagram_directory)
    diagram_directory.mkdir(parents=True)

    pandoc = manifest["toolchain"]["pandoc"]["command"]
    markdown = _run(
        [pandoc, str(source), "--from", "markdown", "--to", "json"],
        cwd=root,
        env=env,
        capture=True,
    )
    try:
        ast = json.loads(markdown.stdout)
    except json.JSONDecodeError as error:
        raise BuildError(
            f"Pandoc returned invalid JSON for {source}: {error}"
        ) from error

    # One render per document, never one per requested output -- this
    # slice's own guard test (a call-count check on `render_diagram_blocks`
    # itself) must go red if a future change moves this call inside the
    # `outputs` loop instead.
    transformed = render_diagram_blocks(
        ast, diagram_directory, _build_renderers(manifest, document, env)
    )

    return [
        _EMITTERS[output_format](
            transformed, manifest, root, env, source, diagram_directory, stem
        )
        for output_format in document["outputs"]
    ]


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parent / "document-build.json",
        help="path to the documentation build manifest",
    )
    parser.add_argument(
        "--reuse-screenshots",
        action="store_true",
        help="reuse committed screenshots instead of starting the app and recapturing them",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check the manifest and toolchain without building",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    try:
        manifest, root = _load_manifest(arguments.manifest.resolve())
        environment = _build_environment()
        _validate_inputs(manifest, root)
        _check_toolchain(manifest, root, environment)
        if arguments.check:
            return 0
        if "screenshots" in manifest:
            _prepare_screenshots(
                manifest["screenshots"], root, environment, arguments.reuse_screenshots
            )
        # ChromiumNotConfiguredError is caught here, per document, rather
        # than by the outer handler below: the owner's instruction is to
        # fail loudly and skip only the affected document, not abort the
        # whole build, when CHROMIUM_EXECUTABLE_PATH isn't configured.
        # Every other BuildError still aborts immediately via that handler.
        any_skipped = False
        for document in manifest["documents"]:
            try:
                _render_document(document, manifest, root, environment)
            except ChromiumNotConfiguredError as error:
                print(f"error: skipping {document['source']}: {error}", file=sys.stderr)
                any_skipped = True
        return 2 if any_skipped else 0
    except (BuildError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
