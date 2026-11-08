#!/usr/bin/env bash
# Session start: make sure the pre-commit hook (the real lint gate) is installed.
# Idempotent and quiet; never fails the session. Stage 0 extends it to prepare
# the project's own dependencies by scope (docs/agents/build-thread-setup.md).
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}" || exit 0

# Pinned: moving this version is its own ticketed PR (.forge/code-shape-rules.md, "Pinned dependencies").
PRE_COMMIT_VERSION="4.3.0"

if [ -f .git/hooks/pre-commit ] && grep -q pre-commit .git/hooks/pre-commit 2>/dev/null; then
  echo "pre-commit hook: already installed"
  exit 0
fi

if ! command -v pre-commit >/dev/null 2>&1; then
  python3 -m pip install --quiet "pre-commit==${PRE_COMMIT_VERSION}" >/dev/null 2>&1 \
    || { echo "pre-commit hook: could not install pre-commit; run: pip install pre-commit==${PRE_COMMIT_VERSION} && pre-commit install --install-hooks"; exit 0; }
fi

if pre-commit install --install-hooks >/dev/null 2>&1; then
  echo "pre-commit hook: installed"
else
  echo "pre-commit hook: install failed; run: pre-commit install --install-hooks"
fi
exit 0
