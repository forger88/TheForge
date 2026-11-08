#!/usr/bin/env bash
# Renders the template from this working tree into a scratch directory and
# runs a generated project's own guards against the render, so a broken
# guard (or a question with no answer) is caught here rather than shipped to
# every consumer who runs `copier copy` next (issue "Check that a freshly
# rendered project passes its own guards": a fresh render once failed its
# own module-size hook on its first commit, and nothing here noticed).
#
# Usage: scripts/check-render.sh   (run from the repo root; pre-commit runs
# it the same way, with no file arguments -- see .pre-commit-config.yaml's
# always_run/pass_filenames).
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Strip any git-hook-injected environment before touching anything else.
# When this script runs as a pre-commit hook invoked by `git commit` (rather
# than a standalone `pre-commit run`), git sets GIT_DIR/GIT_INDEX_FILE (and,
# with a hooksPath override, GIT_CONFIG_PARAMETERS and friends) to point at
# this repo, and they propagate to every subprocess -- including the
# render's own nested test fixtures that `git init`/`git add`/`git commit`
# their own throwaway repos. Left unstripped, those fixtures silently
# corrupt *this* repo's real index instead of their own temp one (found by
# running this script via `git commit`, not caught by a standalone
# `pre-commit run --all-files`, which never sets these).
while IFS='=' read -r name _; do
  unset "$name"
done < <(env | grep '^GIT_')

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/forge-check-render.XXXXXX")"
logdir="$(mktemp -d "${TMPDIR:-/tmp}/forge-check-render-logs.XXXXXX")"

cleanup() {
  rm -rf "$tmpdir" "$logdir"
}
trap cleanup EXIT

fail() {
  echo "check-render: $1" >&2
  exit 1
}

# This script's own static guard test, run first and fast (no render), so an
# edit to check-render.sh that drops one of its own safety properties (the
# GITHUB_TOKEN unset, the GIT_* strip, the fail-fast flags, the cleanup
# trap) is caught here even on a commit that touches only this file -- see
# test_check_render.py.
echo "check-render: running this script's own guard test"
if ! (cd "$repo_root/scripts" && python3 test_check_render.py) >"$logdir/self-test.log" 2>&1; then
  cat "$logdir/self-test.log" >&2
  fail "scripts/test_check_render.py failed -- see output above"
fi

# Every copier.yml question with no `default` needs an answer supplied here,
# or `copier copy --defaults` dies with "Question ... is required" in this
# non-interactive context. Read them from copier.yml itself, rather than
# hardcoding today's two (project_name, repo_owner), so a later question
# added the same way doesn't silently stop this script from rendering at
# all -- it would instead get a generic sample value, which is still a real
# render to check guards against.
answer_args=()
while IFS= read -r question; do
  answer_args+=(-d "${question}=Render Check Value")
done < <(
  python3 - "$repo_root/copier.yml" <<'PYEOF'
import sys
import yaml

with open(sys.argv[1]) as f:
    data = next(yaml.safe_load_all(f))

for name, spec in data.items():
    if name.startswith("_") or not isinstance(spec, dict):
        continue
    if spec.get("type", "str") == "str" and "default" not in spec:
        print(name)
PYEOF
)

echo "check-render: rendering into $tmpdir"
# --vcs-ref HEAD, not the default (ref unset): with no ref, Copier's
# vcs.clone() wraps any dirty working-tree changes into a WIP commit, then
# checkout_latest_tag() does a `git checkout --force <latest PEP440 tag>`
# that discards HEAD and those changes -- so once any tag exists, this
# would silently render the old tag instead of what's actually being
# checked. Copier treats ref in {None, "HEAD"} alike for picking up dirty
# changes, so HEAD keeps that behaviour while skipping the tag checkout.
if ! copier copy --trust --defaults --skip-tasks --vcs-ref HEAD "${answer_args[@]}" "$repo_root" "$tmpdir" >"$logdir/render.log" 2>&1; then
  cat "$logdir/render.log" >&2
  fail "render failed (copier copy) -- see output above"
fi

# Hooks that read the git index (and `git diff`-based checks a future guard
# might add) need a real repo and a staged tree, the same as a freshly
# generated project's own first commit.
(
  cd "$tmpdir"
  git init -q
  git add -A
) || fail "git init/add in the render failed"

echo "check-render: running the render's own guard-script tests"
# bootstrap.py (and its tests) treat an unset GITHUB_TOKEN as "nothing to do
# on GitHub" and skip cleanly; an ambient token in this shell (this machine's
# own GitHub access, unrelated to the render) must never leak in here, or a
# routine run of this script -- including every pre-commit run once it's
# wired in -- would make real, unwanted GitHub API calls on each commit.
if ! (cd "$tmpdir/scripts" && env -u GITHUB_TOKEN -u GH_TOKEN python3 -m unittest discover -s . -p 'test_*.py') >"$logdir/tests.log" 2>&1; then
  cat "$logdir/tests.log" >&2
  fail "the render's own guard-script tests failed -- see output above"
fi

# GitHub cannot load a workflow whose YAML does not parse and logs an empty
# failed run on every push instead; no other step here parses workflows.
echo "check-render: parsing the render's workflow files as YAML"
if ! python3 - "$tmpdir/.github/workflows" >"$logdir/workflows-yaml.log" 2>&1 <<'PYEOF'
import pathlib
import sys

import yaml

failed = False
for path in sorted([*pathlib.Path(sys.argv[1]).glob("*.yml"), *pathlib.Path(sys.argv[1]).glob("*.yaml")]):
    try:
        yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        print(f"{path.name}: {exc}")
        failed = True
sys.exit(1 if failed else 0)
PYEOF
then
  cat "$logdir/workflows-yaml.log" >&2
  fail "a rendered workflow file is not valid YAML -- see output above"
fi

echo "check-render: running the render's own pre-commit hooks"
if ! (cd "$tmpdir" && env -u GITHUB_TOKEN -u GH_TOKEN pre-commit run --all-files) >"$logdir/precommit.log" 2>&1; then
  cat "$logdir/precommit.log" >&2
  fail "the render's own pre-commit hooks failed -- see output above"
fi

# check_document_consistency.py ships in template/docs/tools/ unconditionally, but
# its pre-commit hook is added only by doc-build-setup's own opt-in step
# (.agents/skills/doc-build-setup/SKILL.md), so a bare render's own pre-commit
# run above never exercises it. Invoke it directly here against the
# template's shipped doc skeletons -- the document-build.json manifest's
# own `documents` plus the rendered ADRs -- so a broken cross-reference or
# D2 block in what every consumer gets is still caught before it merges.
echo "check-render: running check_document_consistency.py against the render's doc skeletons"
if ! (cd "$tmpdir" && python3 docs/tools/check_document_consistency.py --also 'docs/adr/*.md') >"$logdir/doc-consistency.log" 2>&1; then
  cat "$logdir/doc-consistency.log" >&2
  fail "check_document_consistency.py failed against the render -- see output above"
fi

echo "check-render: a freshly rendered project passes its own guards"
