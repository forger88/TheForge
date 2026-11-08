#!/usr/bin/env bash
# Fails when a file check-merge-text.sh hands us contains a non-no-reply
# commit identity: an "author/committer <email>"-shaped line, or a
# "Co-authored-by:" trailer, whose address is not a no-reply address
# (CLAUDE.md, "Agent commit identity").
#
# An agent's own commits already use a no-reply bot identity; a squash merge is
# authored by the platform under the merging account's no-reply alias and
# committed by the platform's own no-reply identity. Both are allowed. A real
# personal address anywhere in these positions is never acceptable, because it
# would carry a name or address CLAUDE.md requires kept off this repository's
# history.
#
# Allowed email shapes, kept generic (no vendor or account name hardcoded so
# this stays usable by any harness or hosting account):
#   - local part exactly "noreply" at any domain (user@noreply.example.com)
#   - any address at the "users.noreply.github.com" domain, with or without a
#     leading "<digits>+" prefix
#
# check-merge-text.sh's mask_noreply re-derives the github.com shape to decide
# what the denylist pass may hide; change that shape there too if it changes here.
#
# A file named exactly "identities" is treated strictly: check-merge-text.sh
# generates it mechanically as one "Name <email>" line per commit author and
# committer, so every non-blank line in it must be that shape and must be
# no-reply-shaped -- a line that fails to even look like "Name <email>" is
# itself a finding, not silently skipped, since there is no other content
# that file can legitimately hold. Every other file (free-form commit
# messages, PR text) is scanned only for "Co-authored-by:" trailers; prose
# lines that merely happen to contain "<...>" are not identities and are
# left alone.
#
# Matched addresses are never printed, only "file:line" -- the same discipline
# scripts/check-denylist.sh keeps, so this hook's own output never repeats what
# must not appear.
#
# Usage: check-commit-identities.sh FILE...
set -euo pipefail

identity_line_re='^[^<]*<([^<>]*)>$'

email_of() { # $1 = "Name <email>"; prints the email, or nothing if unparseable
  printf '%s' "$1" | sed -n -E "s/$identity_line_re/\1/p"
}

is_noreply_shaped() { # $1 = email (non-empty)
  case "$1" in
    noreply@*) return 0 ;;
    *@users.noreply.github.com) return 0 ;;
    *) return 1 ;;
  esac
}

status=0
for f in "$@"; do
  [ -f "$f" ] || continue
  strict=0
  case "$(basename "$f")" in
    identities) strict=1 ;;
  esac
  lineno=0
  while IFS= read -r line || [ -n "$line" ]; do
    lineno=$((lineno + 1))
    [ -n "$line" ] || continue
    candidate=""
    if [ "$strict" -eq 1 ]; then
      candidate="$line"
    elif printf '%s' "$line" | grep -qiE '^co-authored-by:'; then
      candidate="$(printf '%s' "$line" | sed -E 's/^[Cc]o-[Aa]uthored-[Bb]y:[[:space:]]*//')"
    else
      continue
    fi
    email="$(email_of "$candidate")"
    if [ -z "$email" ] || ! is_noreply_shaped "$email"; then
      echo "non-no-reply commit identity in $f:$lineno" >&2
      status=1
    fi
  done < "$f"
done

if [ "$status" -ne 0 ]; then
  echo >&2
  echo "Fix the identity forward (a new commit, or an amended trailer on the branch" >&2
  echo "still open for review) -- never by rewriting history already on main" >&2
  echo "(CLAUDE.md, \"Agent commit identity\")." >&2
fi
exit "$status"
