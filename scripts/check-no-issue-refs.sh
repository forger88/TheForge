#!/usr/bin/env bash
# Fails when a file pre-commit hands us contains an issue/PR-style reference
# ("#" followed by 2-6 digits). TheForge is project-neutral (CLAUDE.md, "TheForge
# stays project-neutral"): no project's issue or PR numbers belong in shipped content.
#
# The one allowed exception is a THIRD_PARTY.md credits file, which may cite an
# upstream project's own references; it is skipped by path below and in
# .pre-commit-config.yaml. Single-digit "#3" (a list or hypothesis number) and
# hex colours like "#1a2b3c" do not match the pattern.
#
# Usage: check-no-issue-refs.sh [--warn] FILE...   (pre-commit passes the staged files;
# their working-tree content equals the staged content while pre-commit runs).
# --warn lists hits but exits 0, for commit and PR text that may cite this
# repository's own issues.
set -euo pipefail

warn=0
if [ "${1:-}" = "--warn" ]; then
  warn=1
  shift
fi

status=0
for f in "$@"; do
  case "$f" in
    THIRD_PARTY.md|*/THIRD_PARTY.md) continue ;;
  esac
  [ -f "$f" ] || continue
  if hits=$(grep -nE '#[0-9]{2,6}\b' -- "$f"); then
    echo "issue/PR-style reference in $f:" >&2
    printf '%s\n' "$hits" | sed 's/^/  /' >&2
    status=1
  fi
done

if [ "$status" -ne 0 ]; then
  echo >&2
  echo "Remove or genericise these references (use a template variable such as" >&2
  echo "post_merge_review_tracker, or write '#<n>' in an illustrative example)." >&2
  if [ "$warn" -eq 1 ]; then
    echo "Warning only: check that each number is this repository's own." >&2
    exit 0
  fi
fi
exit "$status"
