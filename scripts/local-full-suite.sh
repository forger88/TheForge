#!/usr/bin/env bash
# Local stand-in for the scheduled CI pass (.agents/skills/watch-main-ci/SKILL.md, "Routine 2").
# Runs every check this sandbox can run against the checked-out HEAD, one named step each:
# every hook in .pre-commit-config.yaml (read from the file, so a new hook needs no edit here),
# both test trees (root scripts/ and template/scripts/, which `unittest discover` can't merge in
# one call since they share module names), and the review-gate check against the current
# branch's open PR.
#
# Usage: scripts/local-full-suite.sh [--is-running | [WORKTREE [LOG_DIR]]]
#   --is-running             exit 0 if a run holds the lock or the lock cannot be opened, 1 otherwise
#                            (works from any directory)
#   WORKTREE                 the checkout to test (default: the one holding this script)
#   LOG_DIR                  per-step logs (default: $LOCAL_FULL_SUITE_LOG_DIR or .scratch/local-full-suite)
#   SKIP=step1,step2         skip named steps (a resumed or partial run; never counts as clean)
#   LOCAL_FULL_SUITE_PUBLISH=1  on a full run, post the evidence comment (a marker line and a
#                            per-step table) on the tracker named by local_full_suite_evidence_tracker
#                            in .copier-answers.yml; try a commit status per step plus an aggregate
#                            `local-full-suite` status on HEAD (none on a SKIP run); and on a fully
#                            clean run whose sha still matches origin/main's current head, fast-forward
#                            refs/heads/green to it (needs an authenticated `gh` and a clean working
#                            tree; a non-fast-forward rejection or a platform policy block (e.g. GH007)
#                            is logged as GREEN-PUSH-REFUSED, any other push failure as GREEN-PUSH-FAILED,
#                            and a sha mismatch as GREEN-PUSH-SKIPPED-STALE; never force-pushed, SDLC-109)
#   LOCAL_FULL_SUITE_LOCK_DIR  the private directory holding the lock (default
#                            /var/tmp/theforgestaging-local-full-suite)
# Exit codes: 0 every step that ran passed, 1 a step failed or the run was refused,
#   75 another run holds the lock.
set -uo pipefail

# Fixed rather than under $TMPDIR: sessions on one machine set different TMPDIRs, and the lock
# must be the same file for every one of them.
LOCK_DIR="${LOCAL_FULL_SUITE_LOCK_DIR:-/var/tmp/theforgestaging-local-full-suite}"
LOCK_FILE="$LOCK_DIR/lock"

# Inlined rather than a separate sourced file: unlike a project that also shares this check with a
# local-services script, this repository has only this one caller.
# Guard reason: this keeps a fixed-path lock file under world-writable /var/tmp, often as root, so
# a directory another account made or can write could hold the lock or plant a symlink the writes
# below would follow; a directory that is ours and private can't. stat reads a symlink itself, not
# its target, so one swapped in after the -L test still fails the owner or mode check.
private_dir_ok() {  # tag dir uid...
  local tag="$1" dir="$2"
  shift 2
  if [ -L "$dir" ]; then
    echo "$tag: $dir is a symlink; refusing to use it" >&2
    return 1
  fi
  if ! mkdir -p -m 700 "$dir" 2>/dev/null; then
    echo "$tag: cannot create $dir" >&2
    return 1
  fi
  local owner
  owner="$(stat -c %u "$dir")"
  if ! [[ " $* " == *" $owner "* ]]; then
    echo "$tag: $dir is owned by uid $owner, not by this user; refusing to use it" >&2
    return 1
  fi
  # A literal with a leading 0 is already octal in bash arithmetic; no base prefix needed, which
  # also avoids writing a `#`-adjacent digit run this repository's own no-issue-refs hook would
  # otherwise flag as an issue-style reference.
  if (( 0$(stat -c %a "$dir") & 022 )); then
    echo "$tag: $dir is writable by others; refusing to use it" >&2
    return 1
  fi
}

# Before any cd: --is-running answers from wherever it is called, checkout or not.
if [ "${1:-}" = "--is-running" ]; then
  # Callers start work that must not overlap a run only on exit 1, so an unknown answers "running".
  if ! private_dir_ok local-full-suite "$LOCK_DIR" "$(id -u)" || ! exec 9>>"$LOCK_FILE"; then
    echo "local-full-suite: cannot open $LOCK_FILE; reporting a run in progress" >&2
    exit 0
  fi
  if flock -n 9; then exit 1; else exit 0; fi
fi

if [ -n "${1:-}" ]; then
  cd "$1" || exit 1
fi
cd "$(git rev-parse --show-toplevel)" || exit 1

LOG_DIR="${2:-${LOCAL_FULL_SUITE_LOG_DIR:-.scratch/local-full-suite}}"
# Resolved from the checkout's own remote, never hardcoded (this repository's own denylist bans
# its owner account in a hand-written file, the same reason scripts/check_review_gate_local.sh is).
REPO="$(git remote get-url origin | sed -E 's#^(https://[^/]+/|git@[^:]+:)##; s/\.git$//')"
TRACKER="$(sed -n "s/^local_full_suite_evidence_tracker: '\{0,1\}\([0-9]*\)'\{0,1\}$/\1/p" .copier-answers.yml)"
# Meaningless on a checkout of main: it checks the current branch's name.
SKIP_ALWAYS="check-branch-name,no-issue-refs-commit-msg,denylist-commit-msg"

private_dir_ok local-full-suite "$LOCK_DIR" "$(id -u)" || exit 1
exec 9>>"$LOCK_FILE" || exit 1
if ! flock -n 9; then
  echo "local-full-suite: another run holds $LOCK_FILE" >&2
  exit 75
fi

sha="$(git rev-parse HEAD)"
publish="${LOCAL_FULL_SUITE_PUBLISH:-0}"
# The evidence comment, statuses and green push name HEAD's sha, so they must describe HEAD's tree.
if [ "$publish" = "1" ] && [ -n "$(git status --porcelain)" ]; then
  echo "local-full-suite: refusing to publish from a dirty working tree" >&2
  exit 1
fi
mkdir -p "$LOG_DIR"
skip=",${SKIP:-},"
failed=0
# Any SKIP makes the run partial, even one naming no real step (Routine 2: "SKIP non-empty").
skipped_any=0
[ -n "${SKIP:-}" ] && skipped_any=1

results=""  # the evidence comment's table rows, one per step that ran

# Best effort: the tracker comment is the run's evidence (SDLC-099), and some sandboxes' GitHub
# proxies refuse status writes outright, which is expected there.
post_status() {  # context state description
  [ "$publish" = "1" ] || return 0
  local err
  if ! err="$(gh api --silent "repos/$REPO/statuses/$sha" \
    -f state="$2" -f context="$1" -f description="$3" 2>&1)"; then
    if [[ "$err" == *"HTTP 403"* || "$err" == *"HTTP 405"* ]]; then
      echo "STATUS-POST-REFUSED $1" >&2
    else
      echo "STATUS-POST-FAILED $1: $err" >&2
    fi
  fi
}

# Hazard: queue-sweep check 11(b) parses the marker line; keep its format in step with that check.
post_evidence() {  # aggregate (pass|fail)
  [ "$publish" = "1" ] || return 0
  local body
  body="<!-- local-full-suite-evidence sha=$sha finished=$(date -u +%Y-%m-%dT%H:%M:%SZ) aggregate=$1 -->
Local full-suite run on \`$sha\`: **$1**

| Step | Result | Time |
|---|---|---|
$results"
  if [ -z "$TRACKER" ] \
    || ! gh api --silent "repos/$REPO/issues/$TRACKER/comments" -f body="$body"; then
    echo "ISSUE-POST-FAILED $sha" >&2
  fi
}

run_step() {  # name command...
  local name="$1"; shift
  if [[ "$skip" == *",$name,"* ]]; then
    echo "SKIP  $name"
    return
  fi
  local start=$SECONDS log="$LOG_DIR/$name.log"
  if "$@" >"$log" 2>&1; then
    echo "PASS  $name $((SECONDS - start))s"
    results+="| $name | PASS | $((SECONDS - start))s |"$'\n'
    post_status "local-full-suite/$name" success "PASS $((SECONDS - start))s"
  else
    echo "FAIL  $name $((SECONDS - start))s (log: $log)"
    results+="| $name | FAIL | $((SECONDS - start))s |"$'\n'
    post_status "local-full-suite/$name" failure "FAIL $((SECONDS - start))s"
    failed=1
  fi
}

# A failure before the first step still ends a full run, which still posts its evidence.
fail_before_steps() {  # step message
  echo "FAIL  $2"
  if [ "$skipped_any" = "0" ]; then
    results+="| $1 | FAIL | |"$'\n'
    post_evidence fail
    post_status local-full-suite failure "$1 failed"
  fi
  exit 1
}

hook_ids="$(python3 -c '
import yaml
for repo in yaml.safe_load(open(".pre-commit-config.yaml"))["repos"]:
    for hook in repo["hooks"]:
        print(hook["id"])
')" || fail_before_steps read-hooks "reading .pre-commit-config.yaml"

for id in $hook_ids; do
  [[ ",$SKIP_ALWAYS," == *",$id,"* ]] && continue
  # pre-commit reads SKIP itself; this script has already applied it by step name.
  run_step "$id" env -u SKIP pre-commit run "$id" --all-files
done
run_step tests-scripts python3 -m unittest discover -s scripts -p 'test_*.py'
run_step tests-template-scripts python3 -m unittest discover -s template/scripts -p 'test_*.py'
run_step review-gate scripts/check_review_gate_local.sh

# A partial run (SKIP set) speaks only for the steps it ran: no evidence comment, no aggregate
# status, no green push.
if [ "$skipped_any" = "0" ]; then
  if [ "$failed" = "0" ]; then
    post_evidence pass
    post_status local-full-suite success "all steps passed"
    if [ "$publish" = "1" ]; then
      # A run from a HEAD already behind origin/main can never fast-forward green once it moves
      # there, so only push when this run's sha is still origin/main's current head.
      if ! fetch_err="$(git fetch origin main 2>&1)"; then
        echo "GREEN-PUSH-FETCH-FAILED $sha: $fetch_err" >&2
      elif [ "$sha" = "$(git rev-parse origin/main 2>/dev/null)" ]; then
        if ! push_err="$(git push origin "$sha:refs/heads/green" 2>&1)"; then
          # A non-fast-forward rejection (green already points somewhere that isn't an
          # ancestor of $sha) and a platform policy block (e.g. GH007) are both the remote
          # declining the ref update on its own terms, not a script bug: watch-main-ci's
          # Routine 2 reports both as GREEN-PUSH-REFUSED and recovers the same way. Git
          # reports the same non-fast-forward rejection as "(fetch first)" rather than
          # "(non-fast-forward)" when this checkout has never fetched the commit green
          # currently points to, which is the common case here (this script only ever
          # fetches main), so both phrasings are matched.
          if [[ "$push_err" == *"GH007"* || "$push_err" == *"private email address"* \
             || "$push_err" == *"non-fast-forward"* || "$push_err" == *"fetch first"* ]]; then
            echo "GREEN-PUSH-REFUSED $sha" >&2
          else
            echo "GREEN-PUSH-FAILED $sha: $push_err" >&2
          fi
        fi
      else
        echo "GREEN-PUSH-SKIPPED-STALE $sha" >&2
      fi
    fi
  else
    post_evidence fail
    post_status local-full-suite failure "a step failed"
  fi
fi
exit "$failed"
