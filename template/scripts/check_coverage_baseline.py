#!/usr/bin/env python3
"""Shape and growth check for the per-module coverage baseline (.forge/code-shape-rules.md; SDLC-100).

The baseline file (`coverage_baseline.json`, `{"<module>": <pct>}`) is not a CI
gate on its own: it only backs `implement-with-merge`'s per-PR `Tests:` field.
A PR records `<module>: baseline <pct> -> branch <pct>` for each module it
touches, running coverage once on the branch and raising the baseline entry
in the same PR when the branch's coverage is higher. Whether a given PR's
coverage actually held is checked by that PR's own self-review, not by this
script — this script just keeps the file itself honest:

- every key names a real module under MODULE_ROOT (stage 0 sets this to the
  project's own source root, for example "backend/src/myproject" or
  "frontend/src");
- every value is a plausible 0-100 coverage percentage;
- no entry falls below what `origin/main`'s own copy of the file records (the
  growth check skips, rather than fails, when `origin/main` isn't reachable,
  e.g. a shallow clone).

Usage: check_coverage_baseline.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import clean_git_env  # noqa: E402

MODULE_ROOT = Path(__file__).resolve().parent.parent  # stage 0: set to the project's source root
BASELINE = Path(__file__).with_name("coverage_baseline.json")
BASELINE_REL_PATH = "scripts/coverage_baseline.json"  # stage 0: update if the file moves


def _load_baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))["modules"] if BASELINE.exists() else {}


def _origin_main_modules() -> dict | None:
    result = subprocess.run(
        ["git", "show", f"origin/main:{BASELINE_REL_PATH}"],
        capture_output=True,
        text=True,
        env=clean_git_env(),
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout).get("modules", {})


def main() -> int:
    current = _load_baseline()
    errors: list[str] = []

    for module, pct in current.items():
        if not (MODULE_ROOT / module).is_file():
            errors.append(f"{module}: not found under {MODULE_ROOT}; fix or remove the entry")
        if not isinstance(pct, (int, float)) or not (0 <= pct <= 100):
            errors.append(f"{module}: {pct!r} is not a 0-100 coverage percentage")

    origin_modules = _origin_main_modules()
    if origin_modules is None:
        print("check_coverage_baseline: origin/main not reachable; skipping the growth check.")
    else:
        for module, origin_pct in origin_modules.items():
            if module not in current:
                continue
            if current[module] < origin_pct:
                errors.append(
                    f"{module}: fell from {origin_pct} (origin/main) to {current[module]} -- "
                    f"a PR touching this module records `{module}: baseline {origin_pct} -> "
                    f"branch {current[module]}` and either fixes the coverage drop or gets an "
                    "owner-approved exception (SDLC-054)"
                )

    for line in errors:
        print(line, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
