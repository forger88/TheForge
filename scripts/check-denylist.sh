#!/usr/bin/env bash
# Greps the files pre-commit hands us, case-insensitively, against a denylist of
# project-specific terms (CLAUDE.md, "TheForge stays project-neutral"; ADR-0003).
# This private staging repository commits its own real denylist at
# .theforge-denylist (issue "Commit a real denylist into staging..."); that file
# must never ship under template/ or in a copier-generated project (see
# scripts/test_denylist_not_shipped.py).
#
# Denylist location: $THEFORGE_DENYLIST_FILE, else ~/.theforge-denylist, else
# this repository's own committed .theforge-denylist (scripts/denylist-path.sh).
# Whichever of the first two is in effect, the committed denylist is unioned
# in too when it exists (ADR-0005): an override adds its own terms, it does
# not drop the owner's standing ones.
# Format: one term per line; blank lines and lines starting with "#" are ignored.
# Exits 0 with a note only when no denylist is available AND this isn't
# forger88/TheForgeStaging (e.g. a contributor working on the public
# TheForge template, which carries no committed denylist of its own) --
# see the two fail-closed cases below for what no longer gets that pass.
#
# Allowed hits: .theforge-denylist-allow (committed) lists "path:term" pairs for
# the few public terms that must appear in a named file, such as the copyright
# holder in LICENSE. Only add a pair for a term that is already public.
# The allow-list is resolved relative to `git rev-parse --show-toplevel`, so it
# only applies when this script runs inside a working tree of this repository.
# check-merge-text.sh runs it from a scratch directory outside any repository
# on purpose, so merge text never gets an allow-list exception (see that
# script's own comment at its scan directory).
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"

# Case folding must not depend on the caller's ambient locale: under LC_ALL=C,
# grep -i folds ASCII only, so "ÉxampleTerm" would stop matching "éxampleterm".
# Pick the first installed UTF-8 locale that really folds; with none, fail
# closed rather than scan with weaker matching.
fold_locale=""
for candidate in C.UTF-8 C.utf8 en_US.UTF-8 en_US.utf8; do
  if [ "$(printf 'é\n' | LC_ALL=$candidate grep -ciF 'É' 2>/dev/null || true)" = 1 ] \
     && [ "$(printf 'é\n' | LC_ALL=$candidate grep -ci 'É' 2>/dev/null || true)" = 1 ]; then
    fold_locale="$candidate"; break
  fi
done
if [ -z "$fold_locale" ]; then
  echo "check-denylist: no installed UTF-8 locale folds non-ASCII case; refusing (install C.UTF-8 or en_US.UTF-8)." >&2
  exit 1
fi
command -v iconv >/dev/null 2>&1 || {
  echo "check-denylist: iconv is required to scan UTF-16/UTF-32 content; refusing." >&2
  exit 1
}
export LC_ALL="$fold_locale" LANG="$fold_locale"
# shellcheck source=denylist-path.sh
. "$here/denylist-path.sh"
denylist="$(resolve_denylist_path)"
if [ ! -f "$denylist" ]; then
  # An explicit override pointing at nothing is always a misconfiguration
  # (a typo'd path, a stale env var), never "no denylist available": fail
  # loudly rather than silently scanning against zero patterns.
  if [ -n "${THEFORGE_DENYLIST_FILE:-}" ]; then
    echo "check-denylist: THEFORGE_DENYLIST_FILE='$THEFORGE_DENYLIST_FILE' does not exist; refusing (point it at a real file, or unset it)." >&2
    exit 1
  fi
  # forger88/TheForgeStaging commits its own real denylist, so a missing
  # committed file here means it was deleted or renamed, not that this
  # checkout genuinely has none -- fail instead of the silent rc=0 that let
  # a renamed .theforge-denylist turn this hook off with no visible sign.
  # Deliberately narrower than check-not-raw-clone.sh's sibling regex
  # (`forger88/TheForge(Staging)?`, which treats either repo as a legitimate
  # non-raw clone): only Staging commits a real denylist, so only Staging's
  # absence is suspicious -- a plain TheForge checkout never had one to lose.
  if git -C "$here" remote -v 2>/dev/null | grep -qiE '(^|[/:])forger88/TheForgeStaging(\.git)?([[:space:]]|$)'; then
    echo "check-denylist: forger88/TheForgeStaging commits its own .theforge-denylist, but none was found at '$denylist'. Restore it, or set THEFORGE_DENYLIST_FILE if you mean to scan against something else." >&2
    exit 1
  fi
  echo "check-denylist: no denylist at '$denylist'; skipping (set THEFORGE_DENYLIST_FILE to scan)."
  exit 0
fi

# No `|| pwd` fallback: outside a real git working tree (check-merge-text.sh's
# scratch scan directory), there is no allow-list, full stop -- falling back to
# the current directory would let an allow-list file placed there by accident
# (or by a future change to that scratch directory's contents) silently start
# granting the self-reference exception to merge text, which the owner's
# decision says it must never have.
if toplevel="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  # THEFORGE_DENYLIST_ALLOW_FILE lets check-merge-text.sh point at the PR's
  # base-commit allow-list while the PR's own copy of that file is scanned
  # like any other file.
  allow_file="${THEFORGE_DENYLIST_ALLOW_FILE:-$toplevel/.theforge-denylist-allow}"
else
  allow_file=""
fi

# Strip comments and blanks into a temporary pattern file.
patterns="$(mktemp)"
decoded="$(mktemp)"
hits="$(mktemp)"
trap 'rm -f "$patterns" "$decoded" "$hits"' EXIT
# grep exits 1 for "no lines left" (handled by the empty check below) and 2 for a read error.
grep_rc=0
grep -vE '^[[:space:]]*(#|$)' "$denylist" > "$patterns" || grep_rc=$?
if [ "$grep_rc" -gt 1 ]; then
  echo "check-denylist: could not read the denylist at '$denylist'; refusing." >&2
  exit 1
fi
[ -s "$patterns" ] || {
  # A present-but-empty denylist must not look like "clean" to a caller that
  # treats exit 0 as "scanned and found nothing" -- only the distinct
  # "no denylist file at all" case above gets that exit.
  echo "check-denylist: denylist at '$denylist' exists but has no terms; refusing (point THEFORGE_DENYLIST_FILE at a populated file to scan against something else)." >&2
  exit 1
}

# Union in this repository's own committed denylist whenever $denylist is an
# override (tier 1/2): a back-port session, or a stale ~/.theforge-denylist
# left over from one, must not silently turn off the owner's own standing
# protections (a post-merge review finding).
union_file="$(resolve_union_denylist_path "$denylist")"
if [ -n "$union_file" ]; then
  grep_rc=0
  grep -vE '^[[:space:]]*(#|$)' "$union_file" >> "$patterns" || grep_rc=$?
  if [ "$grep_rc" -gt 1 ]; then
    echo "check-denylist: could not read the denylist at '$union_file'; refusing." >&2
    exit 1
  fi
fi

is_allowed() { # $1=file $2=matched line
  [ -f "$allow_file" ] || return 1
  local entry path term
  while IFS= read -r entry; do
    case "$entry" in ''|'#'*) continue ;; esac
    path="${entry%%:*}"; term="${entry#*:}"
    [ "$path" = "$1" ] || continue
    # Allowed only if the line still matches nothing once the allowed term is removed.
    if ! printf '%s\n' "$2" | sed "s/$term//Ig" | grep -qiF -f "$patterns"; then
      return 0
    fi
  done < "$allow_file"
  return 1
}

status=0
for f in "$@"; do
  [ -f "$f" ] || continue

  # The path string itself, not just its contents: CLAUDE.md's
  # project-neutrality rule names "file names, directory names" too, and a
  # path's directory segments are checked here along with its filename.
  grep_rc=0
  printf '%s\n' "$f" | grep -qiF -f "$patterns" || grep_rc=$?
  if [ "$grep_rc" -eq 0 ]; then
    if ! is_allowed "$f" "$f"; then
      echo "denylisted term in the path '$f'" >&2
      status=1
    fi
  elif [ "$grep_rc" -gt 1 ]; then
    echo "could not check the path '$f' (grep error); treating it as not clean" >&2
    status=1
  fi

  # -a: scan as text. Under a UTF-8 locale, --binary-files=without-match skips
  # a file merely containing bytes invalid as UTF-8, and a denylisted term can
  # sit beside them. The locale is pinned above, not forced to C, because C
  # would drop -i's non-ASCII case folding.
  #
  # Each file is scanned as it is and decoded as UTF-16/UTF-32 (either byte
  # order): those encodings interleave NULs, so the raw bytes never contain a
  # term.
  # A grep read error is not "clean": it fails the file (it exits 2, not 1).
  for enc in raw UTF-16LE UTF-16BE UTF-32LE UTF-32BE; do
    if [ "$enc" = raw ]; then
      src="$f"
    else
      src="$decoded"
      # iconv -c exits 1 when it drops a sequence (a stray odd byte) yet still
      # writes the rest: scan that. Any other failure is not clean.
      iconv_rc=0
      iconv -c -f "$enc" -t UTF-8 -- "$f" > "$src" 2>/dev/null || iconv_rc=$?
      if [ "$iconv_rc" -gt 1 ]; then
        echo "could not decode $f as $enc; treating it as not clean" >&2
        status=1
        continue
      fi
    fi
    grep_rc=0
    grep -niaF -f "$patterns" -- "$src" > "$hits" || grep_rc=$?
    if [ "$grep_rc" -gt 1 ]; then
      echo "could not scan $f (read error); treating it as not clean" >&2
      status=1
      continue
    fi
    while IFS= read -r hit; do
      [ -n "$hit" ] || continue
      lineno="${hit%%:*}"
      line="${hit#*:}"
      if is_allowed "$f" "$line"; then continue; fi
      # Only the line number is printed, never $hit, which carries the term.
      echo "denylisted term in $f:$lineno" >&2
      status=1
    done < "$hits"
  done
done

if [ "$status" -ne 0 ]; then
  echo >&2
  echo "Rewrite these lines generically. Matched terms are not printed separately so" >&2
  echo "that this hook's output does not itself repeat the denylist." >&2
fi
exit "$status"
