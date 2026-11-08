#!/usr/bin/env python3
"""Ban golden and snapshot tests (.forge/code-shape-rules.md, "No goldens or snapshots").

Usage:
    check_no_snapshots.py [FILE ...]

Fails when a given file uses a snapshot-assertion API or depends on a snapshot
library. Extend PATTERNS at stage 0 for the project's own stack.

With no arguments, checks every git-tracked file instead of the files pre-commit
passed. A pre-commit hook that passes only changed filenames would re-scan just
this file's own source when a pattern here is widened, and this checker skips
itself (SELF); a full-tree run on every invocation is what actually checks a
widened pattern against the whole tree (matching check_module_size.py).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import clean_git_env  # noqa: E402

# Package names as PEP 503 spells them apart: `-`, `_` and `.` are interchangeable.
# The pytest-*snapshot* form covers the family of plugins named that way.
_SEP = r"[-_.]"
_SNAPSHOT_PACKAGES = (
    rf"(syrupy|snapshottest|inline{_SEP}snapshot|approvaltests(?:{_SEP}minimal)?|pytest{_SEP}insta|pytest{_SEP}golden"
    rf"|pytest{_SEP}regressions|pytest{_SEP}approval(?:tests)?(?:{_SEP}[a-z0-9]+)*"
    rf"|pytest(?:{_SEP}[a-z0-9]+)*?{_SEP}snapshot(?:{_SEP}[a-z0-9]+)*)"
)
# Python identifiers only use `_`, never `-`, so an import/plugin-registration match needs its
# own underscore-only list rather than _SNAPSHOT_PACKAGES's PEP 503 separator class.
_PY_SNAPSHOT_PACKAGES = (
    r"(syrupy|snapshottest|inline_snapshot|approvaltests|pytest_insta|pytest_golden"
    r"|pytest_regressions|pytest_approval\w*|pytest(?:_[a-z0-9]+)*?_snapshot(?:_[a-z0-9]+)*)"
)
# JS/TS snapshot-testing packages whose name doesn't end in the pytest-style "*snapshot*" shape
# PEP 503 matching would catch; named individually instead.
_JS_SNAPSHOT_PACKAGES = r"(jest-image-snapshot|jest-specific-snapshot|snapshot-diff)"
PATTERNS = {
    "JS/TS snapshot assertion": re.compile(
        r"\.(toMatchSnapshot|toMatchInlineSnapshot|toThrowErrorMatchingSnapshot|toThrowErrorMatchingInlineSnapshot"
        r"|toMatchFileSnapshot|toHaveScreenshot|toMatchAriaSnapshot|toMatchImageSnapshot)\s*\("
    ),
    "Python snapshot library": re.compile(
        rf"^\s*(?:from\s+{_PY_SNAPSHOT_PACKAGES}\b|import\s+(?:[\w.]+\s*,\s*)*{_PY_SNAPSHOT_PACKAGES}\b)",
        re.M,
    ),
    "snapshot library requirement": re.compile(rf"^\s*{_SNAPSHOT_PACKAGES}\s*([\[(=<>~!;@]|$)", re.M | re.I),
    "pip editable install egg reference": re.compile(rf"#egg={_SNAPSHOT_PACKAGES}\b", re.I),
    # Covers the list form (`pytest_plugins = ["syrupy"]`, possibly with other
    # entries before it), the tuple form (`("syrupy",)`), and the bare-string
    # form pytest also accepts (`pytest_plugins = "syrupy"`): the optional
    # bracket is non-capturing and the quoted name can follow it directly or
    # after other list/tuple entries.
    "pytest_plugins registration": re.compile(
        rf"pytest_plugins\s*=\s*(?:[\[(][^\]\)]*?)?[\"']{_SNAPSHOT_PACKAGES}[\"']", re.I
    ),
    # `-p <plugin>` on pytest's own command line or in an `addopts` value
    # (pytest.ini, tox.ini, pyproject.toml's [tool.pytest.ini_options], or
    # setup.cfg's [tool:pytest]) registers a plugin the same as pytest_plugins.
    "pytest -p plugin registration": re.compile(rf"-p\s+{_SNAPSHOT_PACKAGES}\b", re.I),
}
# These files name a dependency inside a quoted string: a PEP 508 entry in pyproject.toml or
# setup.py's extras_require, an ini-quoted Pipfile entry, a lock file's `name = "..."`, a
# Pipfile.lock key. Only these, because a quoted package name in source code is not a
# dependency. setup.cfg is deliberately not here: it quotes nothing, so this pattern never
# matches it (confirmed by mutation) — SETUP_CFG_DEPENDENCY below is its real pattern.
QUOTED_DEPENDENCY_FILES = {"pyproject.toml", "setup.py", "uv.lock", "poetry.lock", "pdm.lock", "Pipfile", "Pipfile.lock"}
QUOTED_DEPENDENCY = re.compile(rf"[\"']{_SNAPSHOT_PACKAGES}\s*([\[(=<>~!;@\"']|$)", re.M | re.I)
# setup.cfg's ini values aren't quoted, and a dependency can sit on the same line as its
# `key =`, not only on its own continuation line (which "snapshot library requirement" above
# already catches): `install_requires = syrupy==4.9.1`, or several entries on one line
# separated by `;` as setup.cfg allows: `install_requires = foo==1; syrupy==4.9.1`.
SETUP_CFG_FILES = {"setup.cfg"}
SETUP_CFG_DEPENDENCY = re.compile(rf"[=;]\s*{_SNAPSHOT_PACKAGES}\s*([\[(=<>~!;]|$)", re.M | re.I)
# package.json names a JS dependency as a quoted key; its name doesn't pass through PEP 503
# matching (JS package names aren't PyPI-normalised), so it gets its own pattern and file set.
QUOTED_JS_DEPENDENCY_FILES = {"package.json"}
QUOTED_JS_DEPENDENCY = re.compile(rf'["\']{_JS_SNAPSHOT_PACKAGES}["\']', re.I)
SELF = Path(__file__).resolve()
# Mirrors .pre-commit-config.yaml.jinja's no-snapshot-assertions `files:` regex, so a
# full-tree run (no argv) scans the same file shapes the hook triggers on -- not every
# tracked file regardless of type. Without this, a doc that quotes a banned API as an
# illustrative example (a .md file, say) would trip the checker on itself.
_SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".mts", ".cts"}
_NAMED_FILES = {
    "package.json", "pyproject.toml", "setup.cfg", "uv.lock", "poetry.lock", "pdm.lock",
    "Pipfile", "Pipfile.lock", "pytest.ini", "tox.ini",
}
_REQUIREMENTS_FILE = re.compile(r"(requirements|constraints).*\.(txt|in)$")
# Vendored skill files are third-party code the project doesn't own or fix, the same
# reason check_module_size.py.jinja's tracked_sources() excludes them via its own
# VENDORED_PREFIXES; this checker has no allowlist to park a vendored false positive
# against, so excluding the prefix is the only way a full-tree run stays clean.
_VENDORED_PREFIXES = (".agents/skills/",)


def _is_scannable(path_str: str) -> bool:
    if path_str.startswith(_VENDORED_PREFIXES):
        return False
    path = Path(path_str)
    return path.suffix in _SOURCE_SUFFIXES or path.name in _NAMED_FILES or bool(_REQUIREMENTS_FILE.search(path.name))


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True, env=clean_git_env()
    ).stdout
    return [p for p in out.splitlines() if _is_scannable(p)]


def main(argv: list[str]) -> int:
    failures = 0
    for name in argv if argv else tracked_files():
        path = Path(name)
        if not path.is_file() or path.resolve() == SELF:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        patterns = dict(PATTERNS)
        if path.name in QUOTED_DEPENDENCY_FILES:
            patterns["snapshot library dependency"] = QUOTED_DEPENDENCY
        if path.name in SETUP_CFG_FILES:
            patterns["snapshot library dependency (setup.cfg)"] = SETUP_CFG_DEPENDENCY
        if path.name in QUOTED_JS_DEPENDENCY_FILES:
            patterns["JS snapshot package dependency"] = QUOTED_JS_DEPENDENCY
        for label, pattern in patterns.items():
            for match in pattern.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                print(f"{path}:{lineno}: {label} ({match.group(0).strip()}); assert what the behaviour promises instead", file=sys.stderr)
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
