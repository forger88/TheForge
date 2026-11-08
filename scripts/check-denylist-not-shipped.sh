#!/usr/bin/env bash
# Refuses a commit that would ship this repository's own denylist
# (.theforge-denylist, and anything matching that name) under template/, which
# Copier copies into every generated project, or that references it from
# copier.yml (issue "Commit a real denylist into staging, wire the merge-text
# scan to it by default, and hard-exclude it from the public snapshot").
# Repo-structure check, not file-content: always runs, regardless of which
# files are staged. See scripts/test_denylist_not_shipped.py for the matching
# end-to-end check against an actual Copier render.
#
# Three layers, because a file-name check alone is bypassable (issue "the
# denylist-not-shipped guards can be bypassed -- the full denylist can ship
# in a generated project"): a Jinja `{% include ".theforge-denylist" %}` in
# any template/ file renders the real denylist's content into the generated
# project without a file named like it ever existing under template/; a
# symlink under template/ whose target resolves outside template/ (e.g. to
# ../.theforge-denylist) copies that target's content the same way. Neither
# leaves a filename match, so both need their own check below.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"

hits="$(find "$root/template" -iname '.theforge-denylist*' 2>/dev/null || true)"
if [ -n "$hits" ]; then
  echo "check-denylist-not-shipped: this repository's own denylist must never ship under template/:" >&2
  echo "$hits" >&2
  exit 1
fi

if grep -qiE '\.theforge-denylist' "$root/copier.yml"; then
  echo "check-denylist-not-shipped: copier.yml must not reference .theforge-denylist (it would ship it)." >&2
  exit 1
fi

# A Jinja include/import/extends can pull the denylist's content into a
# rendered file without any file under template/ being named like it.
refs="$(grep -rliE 'theforge-denylist' "$root/template" 2>/dev/null || true)"
if [ -n "$refs" ]; then
  echo "check-denylist-not-shipped: a file under template/ references .theforge-denylist by name --" >&2
  echo "a Jinja include/import/extends of it would ship its content without ever being named like it:" >&2
  echo "$refs" >&2
  exit 1
fi

# A symlink under template/ whose target resolves outside template/ ships
# that target's content the same way Copier ships any other file.
while IFS= read -r -d '' link; do
  target="$(readlink -f "$link" 2>/dev/null || true)"
  case "$target" in
    "$root/template"/*) ;;
    *)
      echo "check-denylist-not-shipped: symlink under template/ resolves outside template/:" >&2
      echo "  $link -> $target" >&2
      exit 1
      ;;
  esac
done < <(find "$root/template" -type l -print0 2>/dev/null)

echo "check-denylist-not-shipped: .theforge-denylist is absent from template/, unreferenced by copier.yml or any template/ file, and no template/ symlink escapes template/."
