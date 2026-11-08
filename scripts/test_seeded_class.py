"""Guard test for the seeded ownership class in template/.forge/forge-overrides.md.

Root-only (not shipped). Every shipped baseline or allowlist data file must be
listed under "Seeded files", and every listed path must exist in the template,
so a new baseline cannot silently default to forge-owned (and land in a
project's override log on its first edit).

Only names matching baseline/allowlist are discoverable; other seeded
data files (e.g. .gitignore) are checked for existence only.

Standalone: python3 scripts/test_seeded_class.py
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "template"
OVERRIDES = Path(".forge") / "forge-overrides.md"
DATA_FILE = re.compile(r"(baseline|allowlist)[^/]*\.json(\.jinja)?$")


def seeded_paths(text: str) -> set[str]:
    section = re.search(r"^## Seeded files\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if section is None:
        return set()
    return set(re.findall(r"^- `([^`]+)`$", section.group(1), re.M))


def problems(template: Path) -> list[str]:
    listed = seeded_paths((template / OVERRIDES).read_text())
    found: list[str] = []
    if not listed:
        found.append(f"no 'Seeded files' list in {OVERRIDES}")
    for path in sorted(p for p in template.rglob("*") if p.is_file() and DATA_FILE.search(p.name)):
        rel = path.relative_to(template).as_posix().removesuffix(".jinja")
        if rel not in listed:
            found.append(f"{rel} is a baseline or allowlist but is not listed as seeded")
    for rel in sorted(listed):
        if not ((template / rel).is_file() or (template / f"{rel}.jinja").is_file()):
            found.append(f"seeded path {rel} does not exist in the template")
    return found


def _fixture(listed: list[str], files: list[str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for rel in files:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("{}\n")
    body = "".join(f"- `{p}`\n" for p in listed)
    (root / OVERRIDES).parent.mkdir(parents=True, exist_ok=True)
    (root / OVERRIDES).write_text(f"# x\n\n## Seeded files\n\n{body}\n## Next\n")
    return root


class RealTemplate(unittest.TestCase):
    def test_real_template_is_consistent(self):
        self.assertEqual(problems(TEMPLATE), [])


class Fixture(unittest.TestCase):
    def test_consistent_passes(self):
        root = _fixture(["scripts/a_baseline.json"], ["scripts/a_baseline.json"])
        self.assertEqual(problems(root), [])

    def test_unlisted_baseline_fails(self):
        root = _fixture([], ["scripts/a_baseline.json"])
        self.assertEqual(len(problems(root)), 2)  # no list, and the file unlisted

    def test_removed_entry_fails(self):
        root = _fixture(["scripts/b_allowlist.json"], ["scripts/a_baseline.json", "scripts/b_allowlist.json"])
        self.assertEqual(problems(root), ["scripts/a_baseline.json is a baseline or allowlist but is not listed as seeded"])

    def test_listed_but_missing_fails(self):
        root = _fixture(["scripts/gone.json"], [])
        self.assertEqual(problems(root), ["seeded path scripts/gone.json does not exist in the template"])

    def test_jinja_suffixed_data_file_matches_unsuffixed_entry(self):
        root = _fixture(["scripts/a_baseline.json"], ["scripts/a_baseline.json.jinja"])
        self.assertEqual(problems(root), [])


if __name__ == "__main__":
    unittest.main()
