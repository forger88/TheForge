#!/usr/bin/env python3
"""Shrink-only dead-code ratchet (.forge/code-shape-rules.md, "Dead code").

STUB until stage 0. The project chooses its dead-code finder (for example
vulture for Python, knip for TypeScript) and sets FINDER_COMMAND below to a
command that prints one finding per line as `<path>:<rest of the finding>`,
and FINDER_OK_EXIT_CODES to the exit codes that finder uses for a run that
completed, with or without findings; any other exit code fails the hook.
Names a framework calls by convention (route handlers, hooks, entry points)
go in the finder's own configuration (its whitelist or ignore setting), not
in the baseline.
Until then this hook prints that the check is not running and passes, so it
never blocks a commit for a tool the project has not picked yet.

Once configured, it counts findings per file and compares them with
`dead_code_baseline.json` ({"<path>": <count>}), which only shrinks: a new or
grown count fails, and so does a count that dropped without its entry being
lowered, or an entry with nothing left to match.
"""

from __future__ import annotations

import collections
import json
import subprocess
import sys
from pathlib import Path

FINDER_COMMAND: list[str] = []  # stage 0: for example ["vulture", "src", "--min-confidence", "80"]
FINDER_OK_EXIT_CODES: set[int] = {0}  # stage 0: the finder's own codes; for example vulture exits 3 when it finds something
BASELINE = Path(__file__).with_name("dead_code_baseline.json")


def main() -> int:
    if not FINDER_COMMAND:
        print("check_dead_code: NOT RUNNING: no dead-code finder configured yet; set FINDER_COMMAND at stage 0.")
        return 0
    result = subprocess.run(FINDER_COMMAND, capture_output=True, text=True)
    # Guard: a finder that crashes prints no findings, which would otherwise read as a clean run.
    if result.returncode not in FINDER_OK_EXIT_CODES:
        print(f"check_dead_code: finder failed (exit {result.returncode}):\n{result.stderr}", file=sys.stderr)
        return 1
    counts: collections.Counter[str] = collections.Counter()
    for line in result.stdout.splitlines():
        if ":" in line:
            counts[line.split(":", 1)[0]] += 1
    baseline: dict[str, int] = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    errors: list[str] = []
    for path in sorted(set(counts) | set(baseline)):
        found, allowed = counts.get(path, 0), baseline.get(path, 0)
        if found > allowed:
            errors.append(f"{path}: {found} dead-code findings, baseline allows {allowed}; remove the dead code")
        elif found < allowed:
            errors.append(f"{path}: {found} findings, baseline says {allowed}; lower the baseline entry to {found}")
    for line in errors:
        print(line, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
