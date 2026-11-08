#!/usr/bin/env python3
"""Cross-document consistency checks for a project's built documentation.

A single-document review misses a class of error that only shows up
across documents: a dangling cross-reference, a screenshot or diagram
path that no longer exists, a D2 block that no longer renders, or the
same requirement ID defined twice. This script runs those checks over
every document docs/tools/document-build.json lists (plus any extra
paths given on the command line) and exits non-zero if it finds one, so
it can gate a build the same way document_build.py's own toolchain/input
checks do.

What it deliberately does NOT do: verify a `#<n>`-style issue reference
actually exists. That would need a live call to a hosting platform's API
(rate limits, a token, network access) inside what is otherwise a fully
offline, reproducible check. ADR references are checked instead: the
same shape of cross-reference, but one that resolves against files
already in the checkout, so verifying it is free and fully offline.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import document_build  # noqa: E402
from build_errors import BuildError  # noqa: E402
from render_diagrams import render_d2  # noqa: E402

# This project's own requirement-ID convention (`.forge/requirements-driven-changes.md`):
# `FR-NNN` (functional) / `NF-NNN` (non-functional), at least three digits, never reused.
REQUIREMENT_ID = re.compile(r"\b(?:FR|NF)-\d{3,}\b")
# A definition is a full requirements-table row: `| FR-001 | <shall ...> |
# <status> |` (`.forge/requirements-driven-changes.md`'s statuses, plus
# `N/A` for a retired ID's row). Anchoring on the trailing status column,
# not just the leading `| FR-NNN |`, is what tells a real definition apart
# from a citation that happens to open a table row too -- a "known gaps"
# table's row also starts `| FR-NNN |`, but its own last column is a gap
# description or a tracking ref, never a status.
_REQUIREMENT_STATUS = r"Satisfied|Partially Satisfied|Not yet Satisfied|N/A"
REQUIREMENT_DEFINITION = re.compile(
    rf"^\|\s*((?:FR|NF)-\d{{3,}})\s*\|\s*(?:.*?)\s*\|\s*(?:{_REQUIREMENT_STATUS})\s*\|\s*$",
    re.MULTILINE,
)
ADR_REFERENCE = re.compile(r"\bADR-(\d{4})\b")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Fenced blocks and inline code spans are literal text to Pandoc, never
# images, so an image-shaped example inside them must not be checked.
FENCED_CODE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)", re.DOTALL)


class CheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class Issue:
    check: str
    document: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"[{self.check}] {self.document}: {self.detail}"


def _without_code(text: str) -> str:
    return INLINE_CODE.sub("", FENCED_CODE.sub("", text))


def _walk_d2_code_blocks(node: Any) -> list[str]:
    """Return every fenced code block's source that Pandoc classes as `d2`.

    Walks Pandoc's own AST (as `document_build.py`'s `render_diagram_blocks`
    does), rather than a hand-rolled regex on raw Markdown -- a regex
    anchored on `{.d2 ...}` would miss `{caption="x" .d2}` (attribute order
    Pandoc itself doesn't care about), silently under-covering the exact
    "failed D2 render" class of bug this script exists to catch.
    """
    found: list[str] = []
    if isinstance(node, list):
        for item in node:
            found.extend(_walk_d2_code_blocks(item))
    elif isinstance(node, dict):
        if node.get("t") == "CodeBlock":
            (_identifier, classes, _key_values), source = node["c"]
            if "d2" in classes:
                found.append(source)
        else:
            for value in node.values():
                found.extend(_walk_d2_code_blocks(value))
    return found


def _load_manifest(path: Path) -> tuple[dict[str, Any], Path]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CheckError(f"Could not read documentation manifest {path}: {error}") from error
    repository_root = (path.parent / manifest.get("repository_root", ".")).resolve()
    return manifest, repository_root


def _markdown_documents(
    manifest: dict[str, Any], root: Path, extra_globs: list[str]
) -> list[Path]:
    sources = {
        root / document["source"]
        for document in manifest.get("documents", [])
        if Path(document["source"]).suffix.lower() == ".md"
    }
    for pattern in extra_globs:
        sources.update(path for path in root.glob(pattern) if path.suffix.lower() == ".md")
    return sorted(sources)


def _manifest_documents_by_source(manifest: dict[str, Any], root: Path) -> dict[Path, dict[str, Any]]:
    """Every manifest document, keyed by its resolved source path, so a
    check can look up a document's own `diagram_overrides` the same way
    `document_build.py` binds it per-document -- a hand-written doc added
    only via `--also` has no entry here, which callers must treat as "no
    overrides", not as an error."""
    return {root / document["source"]: document for document in manifest.get("documents", [])}


def check_images(documents: list[Path], root: Path) -> list[Issue]:
    """Every Markdown image reference must resolve to a real file.

    Pandoc resolves a relative image path against the source document's
    own directory first, then falls back to a resource path that includes
    the repository root (`document_build.py`'s `_render_document`) -- so
    this check mirrors that same two-place lookup rather than only
    checking relative-to-document, which would flag real, working
    references as broken.
    """
    issues: list[Issue] = []
    for document in documents:
        text = _without_code(document.read_text(encoding="utf-8"))
        for match in MARKDOWN_IMAGE.finditer(text):
            target = match.group(1)
            if re.match(r"^[a-z][a-z0-9+.-]*://", target):
                continue  # remote URL, not a local path this build controls
            candidates = [document.parent / target, root / target]
            if not any(candidate.is_file() for candidate in candidates):
                issues.append(
                    Issue(
                        "missing-image",
                        str(document.relative_to(root)),
                        f"referenced image does not exist: {target}",
                    )
                )
    return issues


def check_screenshot_manifest(
    documents: list[Path], manifest: dict[str, Any], root: Path
) -> list[Issue]:
    """`document-build.json`'s `screenshots.expected` list must stay in sync
    with what the documents actually reference under that directory.

    A screenshot a document references but the manifest doesn't list in
    `expected` is invisible to `document_build.py`'s own
    `_validate_screenshots` -- if the capture step silently failed to
    produce it, the build would proceed and only fail later, deep inside
    pandoc/WeasyPrint resource resolution, rather than with a clear
    "missing expected screenshot" error. A name listed in `expected` but
    that no document actually references is the mirror-image problem: a
    screenshot the manifest still verifies but nothing needs any more.
    """
    screenshots = manifest.get("screenshots")
    if not screenshots:
        return []
    output_directory = (root / screenshots["output_directory"]).resolve()
    expected = set(screenshots.get("expected", []))

    referenced: dict[str, str] = {}
    for document in documents:
        text = _without_code(document.read_text(encoding="utf-8"))
        for match in MARKDOWN_IMAGE.finditer(text):
            target = match.group(1)
            if re.match(r"^[a-z][a-z0-9+.-]*://", target):
                continue
            resolved = (document.parent / target).resolve()
            if resolved.parent != output_directory:
                resolved = (root / target).resolve()
                if resolved.parent != output_directory:
                    continue
            referenced.setdefault(resolved.name, str(document.relative_to(root)))

    issues: list[Issue] = []
    for name, relative in sorted(referenced.items()):
        if name not in expected:
            issues.append(
                Issue(
                    "stale-screenshot-manifest",
                    relative,
                    f"references {output_directory.name}/{name}, which "
                    "docs/tools/document-build.json's screenshots.expected does not list",
                )
            )
    referenced_names = set(referenced)
    for name in sorted(expected - referenced_names):
        issues.append(
            Issue(
                "stale-screenshot-manifest",
                "docs/tools/document-build.json",
                f"lists {output_directory.name}/{name} as expected, but no document references it",
            )
        )
    return issues


def _render_one_d2_block(
    source: str, index: int, document: Path, d2_command: str, overrides: dict[str, Any] | None
) -> Issue | None:
    with tempfile.TemporaryDirectory(prefix="d2-check-") as work:
        destination = Path(work) / "diagram.png"
        try:
            render_d2(source, destination, command=d2_command, overrides=overrides)
        except BuildError as error:
            return Issue(
                "failed-d2-render",
                str(document),
                f"block #{index} failed to render: {error}",
            )
    return None


def check_d2_blocks(
    documents: list[Path],
    root: Path,
    pandoc_command: str,
    d2_command: str,
    manifest_documents: dict[Path, dict[str, Any]] | None = None,
) -> list[Issue]:
    """Every fenced ``d2`` block must actually render.

    Blocks are found the same way `document_build.py` finds them for the
    real build -- via Pandoc's own AST, not a regex on raw Markdown -- and
    rendered through `render_diagrams.render_d2`, the one place in the
    project that knows how to invoke `d2`, with the same per-document
    `diagram_overrides.d2` the real build binds (`document_build.py`'s
    `_build_renderers`), allowlisted and type-checked the same way
    (`document_build._validate_diagram_overrides`) -- so a failure here
    means the real build would fail too, not a stricter or looser
    stand-in check. A document reached only via `--also` (no manifest
    entry) has no overrides to apply, the same as the real build would
    never see it at all.
    """
    issues: list[Issue] = []
    manifest_documents = manifest_documents or {}
    for document in documents:
        relative = document.relative_to(root)
        manifest_document = manifest_documents.get(document)
        overrides = None
        if manifest_document is not None:
            try:
                document_build._validate_diagram_overrides(manifest_document)
            except BuildError as error:
                issues.append(Issue("failed-d2-render", str(relative), str(error)))
                continue
            overrides = manifest_document.get("diagram_overrides", {}).get("d2")
        ast_result = subprocess.run(
            [pandoc_command, str(document), "--from", "markdown", "--to", "json"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if ast_result.returncode != 0:
            issues.append(
                Issue(
                    "failed-d2-render",
                    str(relative),
                    "pandoc could not parse this document to look for d2 blocks: "
                    f"{(ast_result.stderr or ast_result.stdout).strip()}",
                )
            )
            continue
        ast = json.loads(ast_result.stdout)
        for index, source in enumerate(_walk_d2_code_blocks(ast.get("blocks", [])), start=1):
            issue = _render_one_d2_block(source, index, relative, d2_command, overrides)
            if issue is not None:
                issues.append(issue)
    return issues


def _is_inside_code(span: tuple[int, int], code_spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(code_start <= start and end <= code_end for code_start, code_end in code_spans)


def check_requirement_ids(documents: list[Path], root: Path) -> list[Issue]:
    """No requirement ID is defined twice, and no citation is dangling.

    Definitions and citations are collected across *every* document this
    run covers, not just the requirements spec, because another document
    (a design doc, an ADR) can cite an ID the spec defines -- a citation
    with no matching definition anywhere is exactly the kind of drift a
    single-document review would miss.

    An ID written inside inline or fenced code (an illustrative example of
    the ID *shape*, such as the convention note's `` `FR-001` ``..`` `FR-099` ``
    range) is never a real citation or definition. Spans are found against
    the original text, not a code-stripped copy, so a fenced block's own
    newlines don't shift the line numbers reported below.
    """
    issues: list[Issue] = []
    definitions: dict[str, list[str]] = {}
    citations: list[tuple[str, str, int]] = []

    for document in documents:
        relative = str(document.relative_to(root))
        text = document.read_text(encoding="utf-8")
        code_spans = [match.span() for match in FENCED_CODE.finditer(text)]
        code_spans += [match.span() for match in INLINE_CODE.finditer(text)]

        definition_matches = [
            match
            for match in REQUIREMENT_DEFINITION.finditer(text)
            if not _is_inside_code(match.span(), code_spans)
        ]
        for match in definition_matches:
            definitions.setdefault(match.group(1), []).append(relative)
        defined_spans = {match.span(1) for match in definition_matches}
        for match in REQUIREMENT_ID.finditer(text):
            if match.span() in defined_spans or _is_inside_code(match.span(), code_spans):
                continue
            citations.append((match.group(0), relative, text.count("\n", 0, match.start()) + 1))

    for requirement_id, locations in sorted(definitions.items()):
        if len(locations) > 1:
            issues.append(
                Issue(
                    "duplicate-requirement-id",
                    ", ".join(sorted(set(locations))),
                    f"{requirement_id} is defined {len(locations)} times",
                )
            )

    for requirement_id, relative, line in citations:
        if requirement_id not in definitions:
            issues.append(
                Issue(
                    "dangling-requirement-reference",
                    relative,
                    f"{requirement_id} is cited at line {line} but never defined",
                )
            )
    return issues


def check_adr_references(documents: list[Path], root: Path) -> list[Issue]:
    """Every ``ADR-NNNN`` citation must have a matching file under docs/adr/."""
    issues: list[Issue] = []
    adr_dir = root / "docs" / "adr"
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for match in ADR_REFERENCE.finditer(text):
            number = match.group(1)
            if not any(adr_dir.glob(f"{number}-*.md")):
                issues.append(
                    Issue(
                        "broken-adr-reference",
                        str(document.relative_to(root)),
                        f"cites ADR-{number}, which has no docs/adr/{number}-*.md",
                    )
                )
    return sorted(set(issues), key=lambda issue: (issue.document, issue.detail))


def check_toolchain(manifest: dict[str, Any], root: Path) -> list[Issue]:
    """The manifest's pinned toolchain versions must actually be what's on
    PATH -- the same check `document_build.py` runs before a real build
    (`document_build._check_toolchain`) -- so a version mismatch (or a
    missing command) is a consistency-check failure too, not something
    only the real build catches."""
    if "toolchain" not in manifest:
        return []  # same as main()'s own tolerant pandoc_command/d2_command lookup below
    try:
        document_build._check_toolchain(manifest, root, document_build._build_environment())
    except BuildError as error:
        return [Issue("toolchain-mismatch", "docs/tools/document-build.json", str(error))]
    return []


def run_all_checks(
    manifest: dict[str, Any],
    root: Path,
    pandoc_command: str,
    d2_command: str,
    extra_globs: list[str],
) -> list[Issue]:
    documents = _markdown_documents(manifest, root, extra_globs)
    manifest_documents = _manifest_documents_by_source(manifest, root)
    issues: list[Issue] = []
    issues.extend(check_toolchain(manifest, root))
    issues.extend(check_images(documents, root))
    issues.extend(check_screenshot_manifest(documents, manifest, root))
    issues.extend(check_d2_blocks(documents, root, pandoc_command, d2_command, manifest_documents))
    issues.extend(check_requirement_ids(documents, root))
    issues.extend(check_adr_references(documents, root))
    return issues


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parent / "document-build.json",
        help="path to the documentation build manifest",
    )
    parser.add_argument(
        "--also",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "an extra glob (relative to the manifest's repository_root), checked in addition "
            "to the manifest's own documents -- for a hand-written doc the manifest doesn't "
            "build (an ADR, README.md), repeatable"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    try:
        manifest, root = _load_manifest(arguments.manifest.resolve())
    except CheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    pandoc_command = manifest.get("toolchain", {}).get("pandoc", {}).get("command", "pandoc")
    d2_command = manifest.get("toolchain", {}).get("d2", {}).get("command", "d2")
    issues = run_all_checks(manifest, root, pandoc_command, d2_command, arguments.also)

    if not issues:
        print(
            "Cross-document consistency checks passed: no broken references, "
            "missing images, failed D2 renders, or duplicate requirement IDs."
        )
        return 0

    print(f"Cross-document consistency checks found {len(issues)} issue(s):", file=sys.stderr)
    for issue in issues:
        print(f"  {issue}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
