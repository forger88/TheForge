# Sourced by check-denylist.sh and check-merge-text.sh to resolve which
# denylist file(s) to scan against. Not executable on its own.
#
# Priority: an explicitly set $THEFORGE_DENYLIST_FILE always wins, even when it
# points at nothing (the caller gets a clear "missing" message instead of a
# silent fallback). Otherwise ~/.theforge-denylist, for a maintainer's own
# broader list. Otherwise this repository's own committed .theforge-denylist
# (issue "Commit a real denylist into staging..."), so a scan run inside this
# checkout has something to check against by default. Otherwise back to
# ~/.theforge-denylist, so the caller's existing "no denylist" message and exit
# behaviour are unchanged when none of the three exist.
#
# Tier 3 is resolved from this file's own location, not the caller's current
# directory: a back-port session is often run from a different repository's
# checkout, which has its own git root and no reason to carry this
# repository's denylist (${BASH_SOURCE[0]} is this file's own path even when
# sourced, unlike $0, which is the caller's).
resolve_denylist_path() {
  if [ -n "${THEFORGE_DENYLIST_FILE:-}" ]; then
    printf '%s\n' "$THEFORGE_DENYLIST_FILE"
    return
  fi
  if [ -f "$HOME/.theforge-denylist" ]; then
    printf '%s\n' "$HOME/.theforge-denylist"
    return
  fi
  local committed
  committed="$(committed_denylist_path)"
  if [ -f "$committed" ]; then
    printf '%s\n' "$committed"
    return
  fi
  printf '%s\n' "$HOME/.theforge-denylist"
}

# This repository's own committed denylist path (tier 3 above), resolved the
# same cwd-independent way, exposed separately so it can also be unioned in
# below when an override is active.
committed_denylist_path() {
  local repo_root
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  printf '%s\n' "$repo_root/.theforge-denylist"
}

# The owner's own standing terms must stay checked even during a
# back-port session, or on an ordinary commit left under a stale leftover
# ~/.theforge-denylist from one -- not dropped the way a plain override
# (tier 1/2) replacing the committed default used to drop them (a post-merge
# review finding; ADR-0005 amended from "replaces" to "unions"). Prints the committed
# denylist's path when $1 (the resolved primary) is an override that differs
# from it and the committed file actually exists; prints nothing when $1
# already *is* the committed file (tier 3/4, nothing to add) or the
# committed file doesn't exist (nothing to union with, e.g. a back-port run
# outside this repository).
resolve_union_denylist_path() {
  local primary committed
  primary="$1"
  committed="$(committed_denylist_path)"
  [ "$primary" = "$committed" ] && return 0
  [ -f "$committed" ] || return 0
  printf '%s\n' "$committed"
}
