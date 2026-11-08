#!/usr/bin/env bash
# Local counterpart to .github/workflows/review-gate-check.yml, which runs
# automatically on every PR event (unlike this project's other workflows,
# manual-dispatch-only to control Actions-minute spend). Checks the current
# branch's open PR, if any, against the review gate its changed files
# require, using the same scripts/check_review_gate.py the workflow runs.
# No open PR for this branch is not a failure: there's nothing to check yet
# (for example a run against main itself, or a branch before its PR opens).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Resolved from the checkout's own remote, never hardcoded (this script also
# ships as a pattern other projects can copy, and this repository's own
# denylist bans its owner account in a hand-written file).
REPO="$(git remote get-url origin | sed -E 's#^(https://[^/]+/|git@[^:]+:)##; s/\.git$//')"
owner="${REPO%%/*}"
branch="$(git rev-parse --abbrev-ref HEAD)"
# REST only (`gh api`), never `gh pr list`/`gh pr view`: this sandbox's `gh` refuses GraphQL,
# which those subcommands use internally for `--json`/filtered output.
pr_number="$(gh api "repos/$REPO/pulls?head=$owner:$branch&state=open" --jq '.[0].number // empty')"

if [ -z "$pr_number" ]; then
  echo "check_review_gate_local: no open PR for branch '$branch'; nothing to check yet"
  exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
gh api "repos/$REPO/pulls/$pr_number" --jq .body > "$tmp/pr_body.txt"
gh api "repos/$REPO/pulls/$pr_number/files" --paginate --jq '.[].filename' > "$tmp/pr_files.txt"
python3 scripts/check_review_gate.py "$tmp/pr_body.txt" "$tmp/pr_files.txt"
