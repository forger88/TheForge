#!/usr/bin/env python3
"""Pinned-dependency guard (.forge/code-shape-rules.md, "Pinned dependencies").

STUB until stage 0. The project replaces CHECKS below with checks that fail on
any dependency it consumes at a floating version: a manifest line that is not
an exact version, a missing lock file, an image reference without an
`@sha256:` digest (devcontainer, workflow container or service, Dockerfile
`FROM`), a workflow `uses:` or pre-commit `rev:` not at a full commit SHA, and
an unpinned install in a workflow `run` step or Dockerfile `RUN`.
Until then this prints that the check is not running, and passes.

The pre-commit hook runs it on every commit, never behind a file filter: a
commit that only deletes a lock file passes no file a filter could match.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

# stage 0: each check returns a list of "<file>: <what is unpinned>" lines.
CHECKS: list[Callable[[], list[str]]] = []


def main() -> int:
    if not CHECKS:
        print("check_pins: NOT RUNNING: no pin checks configured yet; add them at stage 0.")
        return 0
    errors = [line for check in CHECKS for line in check()]
    for line in errors:
        print(line, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
