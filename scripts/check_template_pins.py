#!/usr/bin/env python3
"""Check that TheForge's own shipped template/ files keep their dependency pins
(.forge/code-shape-rules.md, "Pinned dependencies").

template/scripts/check_pins.py is a stub until a consuming project's stage 0
fills it in, and the render check (scripts/check-render.sh) only runs a
render's own pre-commit hooks -- so neither one checks that the devcontainer
image or workflow actions this repository ships to every consumer stay
pinned. This script is the one guard that does, scanning the template's own
source files directly rather than a render.

Usage: check_template_pins.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEVCONTAINER = ROOT / "template" / ".devcontainer" / "devcontainer.json.jinja"
WORKFLOWS_DIR = ROOT / "template" / ".github" / "workflows"
# DIGEST_PIN's literal 64-hex-digit suffix can never match an unrendered
# `{{ ... }}` expression, so a future templated image value fails closed here.
IMAGE_LINE = re.compile(r'"image"\s*:\s*"([^"]+)"')
DIGEST_PIN = re.compile(r"@sha256:[0-9a-f]{64}$")
USES_LINE = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.M)
FULL_SHA_PIN = re.compile(r"@([0-9a-f]{40})(\s|$)")


def check_devcontainer() -> list[str]:
    if not DEVCONTAINER.is_file():
        return [f"{DEVCONTAINER}: file not found"]
    text = DEVCONTAINER.read_text(encoding="utf-8")
    match = IMAGE_LINE.search(text)
    if not match:
        return [f"{DEVCONTAINER}: no \"image\" line found"]
    image = match.group(1)
    if not DIGEST_PIN.search(image):
        return [f"{DEVCONTAINER}: image {image!r} is not pinned by @sha256: digest"]
    return []


def check_workflows() -> list[str]:
    if not WORKFLOWS_DIR.is_dir():
        return [f"{WORKFLOWS_DIR}: directory not found"]
    failures = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml*")):
        text = path.read_text(encoding="utf-8")
        for match in USES_LINE.finditer(text):
            ref = match.group(1)
            if "@" not in ref:
                failures.append(f"{path}: uses: {ref!r} has no @ref at all")
                continue
            if not FULL_SHA_PIN.search(ref + " "):
                failures.append(f"{path}: uses: {ref!r} is not pinned to a full 40-character commit SHA")
    return failures


def main() -> int:
    failures = check_devcontainer() + check_workflows()
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
