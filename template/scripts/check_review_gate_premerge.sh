#!/usr/bin/env bash
# The fetch-and-run step `implement-with-merge` step 3's "Immediately
# before merging" bullet names, written once here instead of assembled
# fresh by every merger (`.forge/review-gate.md`).
#
# Fetches the PR's current body and its full changed-file list from the
# paginated "list pull request files" endpoint -- never `gh pr diff
# --name-only`, which truncates on a large diff and could silently drop
# a disqualifying file, letting a light-gate claim through unchecked
# instead of failing the check -- together with `origin/main`'s own copy
# of scripts/check_review_gate.py (never the PR branch's copy, which a
# weakened check could have edited). Runs the check against them, and
# prints the head SHA to pin the merge to.
#
# Usage: check_review_gate_premerge.sh [PR_NUMBER]
# With no PR_NUMBER, checks the current branch's open PR against `origin`.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

REPO="$(git remote get-url origin | sed -E 's#^(https://[^/]+/|git@[^:]+:)##; s/\.git$//')"

pr_number="${1:-}"
if [ -z "$pr_number" ]; then
  owner="${REPO%%/*}"
  branch="$(git rev-parse --abbrev-ref HEAD)"
  # REST only (`gh api`), never `gh pr list`/`gh pr view`: some sandboxes'
  # `gh` refuses GraphQL, which those subcommands use internally for
  # `--json`/filtered output (scripts/check_review_gate_local.sh, same note).
  pr_number="$(gh api "repos/$REPO/pulls?head=$owner:$branch&state=open" --jq '.[0].number // empty')"
fi

if [ -z "$pr_number" ]; then
  echo "check_review_gate_premerge: no PR number given, and no open PR found for the current branch" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# One request for both the body and the head SHA, so they describe the
# same fetch (never two separate round-trips that could straddle a push).
pr_json="$(gh api "repos/$REPO/pulls/$pr_number")"
printf '%s' "$pr_json" | python3 -c 'import json, sys; sys.stdout.write(json.load(sys.stdin)["body"] or "")' > "$tmp/pr_body.txt"
head_sha="$(printf '%s' "$pr_json" | python3 -c 'import json, sys; print(json.load(sys.stdin)["head"]["sha"])')"

gh api "repos/$REPO/pulls/$pr_number/files" --paginate --jq '.[].filename' > "$tmp/pr_files.txt"

gh api "repos/$REPO/contents/scripts/check_review_gate.py?ref=main" --jq '.content' | base64 -d > "$tmp/check_review_gate.py"

echo "check_review_gate_premerge: PR #$pr_number, head SHA $head_sha"

if python3 "$tmp/check_review_gate.py" "$tmp/pr_body.txt" "$tmp/pr_files.txt"; then
  echo "check_review_gate_premerge: review gate clears. Pin the merge to head SHA $head_sha."
  exit 0
fi
echo "check_review_gate_premerge: review gate check failed against head SHA $head_sha; do not merge." >&2
exit 1
