#!/usr/bin/env bash
# Reject branch names shaped like a chat or session title (.forge/tickets-and-branches.md, "Branch names").
# A branch is named for what the change does; a session title tells a reviewer nothing.
set -euo pipefail

branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
# Detached HEAD (a rebase, a bisect) has no branch name to check.
[ -z "$branch" ] && exit 0

case "$branch" in
  main|green|prototype/*) exit 0 ;;
esac

# The shape agents produce from a session title: a tool prefix, a slash, words, and a random suffix.
if printf '%s' "$branch" | grep -Eq '^(claude|codex|copilot|cursor|agent|session|chat)/'; then
  echo "Branch '$branch' looks like a session title, not a description of the change." >&2
  echo "Rename it after what the change does, for example: git branch -m fix-invoice-rounding" >&2
  exit 1
fi
# A random suffix mixes letters and digits; a real last word ("-header", "-2024") does not.
suffix="${branch##*-}"
if [ "$suffix" != "$branch" ] && [ "${#suffix}" -eq 6 ] \
  && printf '%s' "$suffix" | grep -Eq '^[a-z0-9]+$' \
  && printf '%s' "$suffix" | grep -q '[0-9]' && printf '%s' "$suffix" | grep -q '[a-z]'; then
  echo "Branch '$branch' ends in what looks like a random session suffix." >&2
  echo "Rename it after what the change does, for example: git branch -m add-export-retry" >&2
  exit 1
fi
exit 0
