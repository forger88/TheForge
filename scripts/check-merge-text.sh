#!/usr/bin/env bash
# Scans the text a merge writes on the hosting platform, which no pre-commit hook
# sees: a PR's title, body, commit messages, the commit authors' and committers'
# names and emails, and the message that will actually be merged
# (CLAUDE.md, "TheForge stays project-neutral", check 3; ADR-0003). Also scans
# the PR's own changed file contents at its head commit -- the pre-commit
# denylist hook exists to catch exactly this, but skips silently in the usual
# case (an agent session with no denylist configured), so a merge is the one
# point that can require it instead of merely hoping it ran (issue "No
# merge-time denylist scan of a PR's file contents"). The file-contents scan
# gets .theforge-denylist-allow's self-reference exceptions, the same as the
# ordinary pre-commit hook, read at the PR's base commit with the hook's
# exclude pattern so a PR cannot widen its own allowance; the
# title/body/commits/identities scan gets none (see the comment where $dir
# is created, below).
#
# Usage: scripts/check-merge-text.sh <pr-number> [--message-file FILE]
#        scripts/check-merge-text.sh <pr-number> --verify-merged [--message-file FILE] [--head-sha SHA]
#
# --verify-merged runs after the merge: it reads the squash commit actually
# written to the base branch and fails unless its message equals the one the
# scan printed (CRLF, trailing whitespace and a platform-added no-reply
# Co-authored-by trailer run excepted), and its author, committer and any such
# trailer are no-reply identities. Read-only; a mismatch is fixed forward
# (CLAUDE.md, "Agent commit identity"). --head-sha, from the scan's output,
# additionally fails when the PR's head is not the commit the scan covered.
#
# Every GitHub call below goes through api_get/api_get_paginated/
# api_get_raw_file, which hit the REST API with GH_TOKEN/GITHUB_TOKEN
# before falling back to `gh api` -- the reverse of `gh api` first, since
# some sandboxes have a working token that `gh auth status` nonetheless
# reports invalid, and `gh api` refuses to run at all in that state
# (issue "scripts/check-merge-text.sh can't run in some cloud sandboxes
# (gh auth invalid)"). Both failing aborts the whole script under `set
# -e`: there is no manual-scan fallback to fall back to.
#
# With no --message-file, the merged message is guessed as the title plus the
# body, which is only right when nobody hand-writes a different one: GitHub's own
# default for a multi-commit PR is the list of commit messages instead, and a
# maintainer or agent merging with a hand-written message bypasses this guess
# entirely. Pass --message-file with the exact text about to be merged (the
# message a hand-edit, a squash-merge dialog, or `gh pr merge --body-file` is
# about to write) to scan that text itself rather than this script's guess at it.
# A hand-edited message is re-scanned this way before merging with it (CLAUDE.md,
# "TheForge stays project-neutral", check 3).
#
# Fails on any denylist hit, and when no denylist is available at all (see
# denylist-path.sh; this repository's own committed .theforge-denylist is the
# usual case now): a merge is a maintainer act, and a maintainer always has one.
# Issue/PR-style references only
# warn, because PR text may cite this repository's own issues; the merger checks
# that each listed number is one of ours. Also runs check-commit-identities.sh
# against every head commit's author/committer and any Co-authored-by trailer,
# failing on a non-no-reply address (CLAUDE.md, "Agent commit identity"): this
# is the one step every merge goes through, and the only place that can see
# commit identities before they land on main. On success it prints the message
# it checked, which is the message to merge with -- the merger merges through
# the API with that exact commit_title/commit_message, or otherwise strips any
# Co-authored-by trailer the platform would add from a head commit's author:
# that trailer carries the merging account's own no-reply alias, which the
# identity check already allows, but it is still not part of this script's
# scanned message. The squash commit's own author (the merger's no-reply
# alias, set by the platform at merge time) remains the one identity this
# script cannot see before merging -- see CLAUDE.md for why that is accepted.
#
# It also runs the PR-time review guards (check_review_gate.py, and
# check_sdlc_wording_hold.py / check_forge_sync_trust_record.py when their
# trigger files change); see the comment where they run, below.
set -euo pipefail

# A git call below (the repo_dir `git init`, or check-denylist.sh's own
# `git rev-parse --show-toplevel`) can inherit a leaked GIT_DIR/
# GIT_INDEX_FILE/etc. from this process's own environment -- e.g. if this
# script is ever run from inside another git hook's environment -- and get
# silently redirected at a real repository instead of the throwaway one
# below (the same hazard scripts/_git_env.py's clean_git_env documents for
# this repository's own test fixtures). Strip them first.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_PREFIX \
      GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT || true
for git_config_env_var in "${!GIT_CONFIG_KEY_@}" "${!GIT_CONFIG_VALUE_@}"; do
  unset "$git_config_env_var"
done

pr="${1:?usage: check-merge-text.sh <pr-number> [--message-file FILE] [--verify-merged [--head-sha SHA]]}"
case "$pr" in
  ''|*[!0-9]*) echo "check-merge-text: '$pr' is not a PR number." >&2; exit 2 ;;
esac
shift
message_file=""
verify_merged_mode=0
expect_head_sha=""
while [ $# -gt 0 ]; do
  case "$1" in
    --message-file)
      message_file="${2:?usage: check-merge-text.sh <pr-number> [--message-file FILE]}"
      shift 2
      ;;
    --verify-merged)
      verify_merged_mode=1
      shift
      ;;
    --head-sha)
      expect_head_sha="${2:?usage: check-merge-text.sh <pr-number> --verify-merged --head-sha SHA}"
      shift 2
      ;;
    *)
      echo "check-merge-text: unrecognised argument '$1'." >&2
      exit 2
      ;;
  esac
done
if [ -n "$expect_head_sha" ] && [ "$verify_merged_mode" -ne 1 ]; then
  echo "check-merge-text: --head-sha only applies with --verify-merged." >&2
  exit 2
fi
if [ -n "$message_file" ] && [ ! -f "$message_file" ]; then
  echo "check-merge-text: no such message file '$message_file'." >&2
  exit 2
fi
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=denylist-path.sh
. "$here/denylist-path.sh"
denylist="$(resolve_denylist_path)"
if [ ! -f "$denylist" ]; then
  echo "check-merge-text: no denylist at '$denylist'; a merge needs one (set THEFORGE_DENYLIST_FILE)." >&2
  exit 1
fi
# A present-but-empty denylist must fail here too: without this, every
# piece below would scan against zero patterns, check-denylist.sh would exit 0
# for each one once it goes clean, and this script would report the merge
# text as scanned when nothing was actually checked.
if ! grep -vE '^[[:space:]]*(#|$)' "$denylist" | grep -q .; then
  echo "check-merge-text: denylist at '$denylist' exists but has no terms; a merge needs real terms, not an empty file." >&2
  exit 1
fi
# The scans below run from a temporary directory, so pass them an absolute path.
THEFORGE_DENYLIST_FILE="$(cd "$(dirname "$denylist")" && pwd)/$(basename "$denylist")"
export THEFORGE_DENYLIST_FILE

# One target repository for both transports: every REST call and every `gh
# api` fallback names owner_repo explicitly, so they cannot scan different
# repositories in a fork checkout (where gh's own default is the upstream).
# Only when owner_repo can't be resolved does a fallback use gh's "{owner}/
# {repo}" placeholder; the base.repo check below then cannot apply.
gh_repo_placeholder='{owner}/{repo}'
# Strips any "scheme://[user@]host/" or scp-style "[user@]host:" prefix,
# not just the literal "git@github.com:"/"https://github.com/" forms --
# a remote on another host (a proxy mirror, an ssh:// form) still names
# "owner/repo" as its last two path segments, and parsing only the
# github.com-literal forms silently cancelled the REST-first fix in
# exactly the non-github.com-remote environments it was meant to help
# (issue "check-merge-text.sh: additional fail-open / scope gaps",
# finding 7). The scp-style prefix's "user@" is optional: git's own scp-
# like syntax doesn't require one.
owner_repo="$(git remote get-url origin 2>/dev/null \
  | sed -E 's#\.git$##; s#/$##; s#^[A-Za-z][A-Za-z0-9+.-]*://([^/@]+@)?[^/]+/##; s#^([^/@]+@)?[^/:]+:##')" || owner_repo=""
gh_token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
# rest_curl writes the token into a double-quoted curl config line, so a
# character that could break out of it (quote, backslash, newline) means no
# REST: fall back to `gh api` rather than send a mangled header.
token_is_curl_safe() {
  case "$1" in
    *[!A-Za-z0-9_.~+/=-]*) return 1 ;;
  esac
}
if ! token_is_curl_safe "$gh_token"; then
  echo "check-merge-text: token has characters unsafe for the curl config; using 'gh api' only." >&2
  gh_token=""
fi
# Shared by api_get and api_get_paginated so their header sets can't drift
# apart; api_get_raw_file needs a different Accept header and builds its own.
json_rest_headers=(-H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")

# rest_curl ARGS... -- curl with the bearer token supplied as a curl config on
# stdin: an argv `-H` would show the token to other local accounts in the
# process list. printf is a builtin, so the token never enters any argv.
rest_curl() {
  printf 'header = "Authorization: Bearer %s"\n' "$gh_token" | curl -K - "$@"
}

# api_get PATH -- a single resource's raw JSON body. REST with gh_token
# first (never gated on `gh auth status`); `gh api` when that's not
# possible or fails.
api_get() {
  local path="$1"
  if [ -n "$owner_repo" ] && [ -n "$gh_token" ]; then
    if rest_curl -fsS "${json_rest_headers[@]}" "https://api.github.com/repos/$owner_repo/$path"; then
      return 0
    fi
    echo "check-merge-text: REST GET '$path' failed; falling back to 'gh api'." >&2
  fi
  gh api "repos/${owner_repo:-$gh_repo_placeholder}/$path"
}

# api_get_raw_file PATH -- like api_get, but for the contents API's raw-
# file Accept header. Silent on failure: the caller decides what a missing
# file means ("absent" for the optional .theforge-denylist-allow; a hard
# refusal for fetch_pr_version's guard inputs).
api_get_raw_file() {
  local path="$1"
  if [ -n "$owner_repo" ] && [ -n "$gh_token" ]; then
    if rest_curl -fsS \
         -H "Accept: application/vnd.github.raw" \
         "https://api.github.com/repos/$owner_repo/$path"; then
      return 0
    fi
  fi
  gh api -H "Accept: application/vnd.github.raw" "repos/${owner_repo:-$gh_repo_placeholder}/$path"
}

# api_get_paginated PATH -- every page's raw JSON body, concatenated (fed
# to `jq -s`, which parses back-to-back JSON values regardless of
# whitespace). Same fallback rule as api_get.
#
# Builds each page's own "$base_url&page=N" rather than following the
# response's own Link `rel="next"` URL: that URL names the repository by
# its numeric id, and some proxy-sandbox network policies 403 exactly
# that shape while allowing the owner/repo-path URL this function builds
# itself (issue "check-merge-text.sh: additional fail-open / scope
# gaps", finding 6). Whether to keep paging is still read off the Link
# header, but only for *presence* of `rel="next"`, checked with a plain
# `grep -qi` -- no `-P`, so a sandbox whose grep lacks PCRE support can't
# silently stop pagination one page early the way the old `grep -oP`
# extraction did on such a grep (same issue, finding 3).
api_get_paginated() {
  local path="$1" base_url hdrs body page pages="" has_next
  if [ -n "$owner_repo" ] && [ -n "$gh_token" ]; then
    base_url="https://api.github.com/repos/$owner_repo/$path"
    case "$base_url" in
      *\?*) base_url="${base_url}&per_page=100" ;;
      *) base_url="${base_url}?per_page=100" ;;
    esac
    page=1
    # Buffered in $pages, not printed per page: a mid-pagination failure
    # falls back to a fresh `gh api --paginate` that re-fetches every
    # page, so printing page 1 as it arrived would duplicate it.
    while :; do
      hdrs="$(mktemp)"
      if ! body="$(rest_curl -fsS -D "$hdrs" "${json_rest_headers[@]}" "${base_url}&page=${page}")"; then
        rm -f "$hdrs"
        echo "check-merge-text: REST GET (paginated) '$path' failed; falling back to 'gh api --paginate'." >&2
        gh api "repos/${owner_repo:-$gh_repo_placeholder}/$path" --paginate
        return $?
      fi
      pages="$pages$body"
      if grep -i '^link:' "$hdrs" | grep -qi 'rel="next"'; then
        has_next=1
      else
        has_next=0
      fi
      rm -f "$hdrs"
      [ "$has_next" -eq 1 ] || break
      page=$((page + 1))
    done
    printf '%s' "$pages"
    return 0
  fi
  gh api "repos/${owner_repo:-$gh_repo_placeholder}/$path" --paginate
}

dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
# Scanning from here, outside any git working tree, is deliberate, not an
# oversight: check-denylist.sh's allow-list resolves via `git rev-parse
# --show-toplevel`, which fails from here, so .theforge-denylist-allow's
# per-file exceptions (this repository's own name, allowed in CLAUDE.md and
# similar standing docs) never apply to merge text. A PR's title, body,
# commit messages and author/committer identities get the strict,
# zero-allowance scan with no self-reference exception -- the owner's
# decision when the real denylist was seeded, since merge text isn't one of
# the standing self-reference files the allow-list was scoped to.
#
# One fetch of the PR resource, not three: title, body and head_sha are all
# projections of the same JSON, so deriving them locally via jq avoids three
# separate round trips for one resource.
pr_json="$(api_get "pulls/$pr")"
# The remote's repository must be the one the PR belongs to; a fork checkout
# whose origin is the fork would otherwise scan whichever PR shares the number.
if [ -n "$owner_repo" ]; then
  pr_base_repo="$(printf '%s' "$pr_json" | jq -r '.base.repo.full_name // empty')"
  if [ "$(printf '%s' "$pr_base_repo" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$owner_repo" | tr '[:upper:]' '[:lower:]')" ]; then
    echo "check-merge-text: PR $pr's base repository is '${pr_base_repo:-unknown}' but origin names '$owner_repo'; refusing rather than scan a different repository." >&2
    exit 1
  fi
fi
printf '%s' "$pr_json" | jq -r .title > "$dir/title"
printf '%s' "$pr_json" | jq -r '.body // ""' > "$dir/body"
head_sha="$(printf '%s' "$pr_json" | jq -r .head.sha)"
base_sha="$(printf '%s' "$pr_json" | jq -r '.base.sha // empty')"

# build_squash_message -- the message to merge with: $message_file's text, or
# the title plus the body. Shared by the scan and --verify-merged so the text
# scanned and the text verified cannot be built two ways.
build_squash_message() {
  if [ -n "$message_file" ]; then
    # The caller has the exact text about to be merged; scan that, not a guess at it.
    cp "$message_file" "$dir/squash"
    cp "$message_file" "$dir/squash-scanned"
  else
    { printf '%s (#%s)\n\n' "$(cat "$dir/title")" "$pr"; cat "$dir/body"; } > "$dir/squash"
    # The platform's own " (#<this PR>)" suffix is not a leak; scan the squash text without it.
    sed "1s/ (#$pr)\$//" "$dir/squash" > "$dir/squash-scanned"
  fi
}

# normalise_message FILE -- CRLF to LF, trailing whitespace stripped per line,
# trailing blank lines dropped. The only tolerance --verify-merged allows.
normalise_message() {
  sed -E 's/\r$//; s/[[:space:]]+$//' "$1" \
    | awk '{ l[NR] = $0 } END { n = NR; while (n > 0 && l[n] == "") n--; for (i = 1; i <= n; i++) print l[i] }'
}

# verify_merged -- after a merge, the squash commit's message must equal the
# scanned one and its identities must be no-reply. Fails closed: a transport
# failure aborts under set -e without printing the success line.
verify_merged() {
  local merged merge_sha commit_json last actual_head
  merged="$(printf '%s' "$pr_json" | jq -r '.merged // false')"
  merge_sha="$(printf '%s' "$pr_json" | jq -r '.merge_commit_sha // empty')"
  if [ "$merged" != "true" ] || [ -z "$merge_sha" ]; then
    echo "check-merge-text: PR $pr is not merged; --verify-merged runs after the merge." >&2
    exit 1
  fi
  if [ -n "$expect_head_sha" ] && [ "$head_sha" != "$expect_head_sha" ]; then
    echo "check-merge-text: PR $pr's head is $head_sha but the scan covered $expect_head_sha; the merge was not pinned to the scanned head. Fix forward and tell the owner." >&2
    exit 1
  fi
  commit_json="$(api_get "git/commits/$merge_sha")"
  printf '%s' "$commit_json" | jq -r '.message' > "$dir/actual-raw"
  printf '%s' "$commit_json" | jq -r '(.author.name + " <" + .author.email + ">\n" + .committer.name + " <" + .committer.email + ">\n")' > "$dir/identities"
  build_squash_message
  normalise_message "$dir/squash" > "$dir/expected-norm"
  normalise_message "$dir/actual-raw" > "$dir/actual-norm"
  # Peel the platform's trailing Co-authored-by run off the actual message, but
  # only lines the expected text does not itself carry; identity-check them below.
  mapfile -t actual_lines < "$dir/actual-norm"
  : > "$dir/trailers"
  while [ "${#actual_lines[@]}" -gt 0 ]; do
    last="${actual_lines[${#actual_lines[@]}-1]}"
    if printf '%s' "$last" | grep -qiE '^co-authored-by:' && ! grep -qxF -- "$last" "$dir/expected-norm"; then
      printf '%s\n' "$last" >> "$dir/trailers"
      unset "actual_lines[${#actual_lines[@]}-1]"
    else
      break
    fi
  done
  if [ "${#actual_lines[@]}" -gt 0 ]; then
    printf '%s\n' "${actual_lines[@]}" | awk '{ l[NR] = $0 } END { n = NR; while (n > 0 && l[n] == "") n--; for (i = 1; i <= n; i++) print l[i] }' > "$dir/actual-final"
  else
    : > "$dir/actual-final"
  fi
  if ! (cd "$dir" && "$here/check-commit-identities.sh" identities trailers); then
    echo "check-merge-text: PR $pr's squash commit $merge_sha carries a non-no-reply identity; fix it forward and tell the owner." >&2
    exit 1
  fi
  if ! cmp -s "$dir/expected-norm" "$dir/actual-final"; then
    echo "check-merge-text: squash commit $merge_sha's message does not match the scanned message; fix forward, never rewrite main." >&2
    # The diff would repeat the landed text, so print it only when that text is clean.
    if (cd "$dir" && "$here/check-denylist.sh" actual-final >&2); then
      diff -u "$dir/expected-norm" "$dir/actual-final" >&2 || true
    else
      echo "check-merge-text: the landed message holds denylisted terms; its text is not echoed. Rewrite it." >&2
    fi
    exit 1
  fi
  echo "check-merge-text: PR $pr's squash commit $merge_sha carries exactly the scanned message."
}
if [ "$verify_merged_mode" -eq 1 ]; then
  verify_merged
  exit 0
fi

# fetch_pr_version REF PATH OUT -- PATH's content at REF into OUT; any fetch
# failure aborts the merge scan rather than reading as "file absent".
fetch_pr_version() {
  if [ -z "$1" ]; then
    echo "check-merge-text: PR $pr names no commit to fetch '$2' at; refusing rather than skip a guard." >&2
    exit 1
  fi
  if ! api_get_raw_file "contents/$2?ref=$1" > "$3"; then
    echo "check-merge-text: could not fetch '$2' at $1 for PR $pr; refusing rather than skip a guard. (Fallback: restore review-gate-check.yml for these guards.)" >&2
    exit 1
  fi
}

# One fetch of the commits resource, not two: commit messages and author/
# committer identities are both projections of the same paginated listing.
# A squash merge copies each head commit's author into a Co-authored-by
# trailer, so a personal address or project name there reaches main even
# when every commit message, the title and the body are clean.
# refuse_if_fetch_truncated JSON_FILE PR_JSON_FIELD NOUN CAP_DESCRIPTION --
# some of GitHub's PR sub-resource listings (/commits, /files) silently cap
# out with no further pagination past that point; pr_json's own count field
# is the authoritative total, so a mismatch against what was actually
# fetched means a silent partial list (issue "check-merge-text.sh:
# additional fail-open / scope gaps", findings 1 and 2) -- refuse rather
# than scan it.
refuse_if_fetch_truncated() {
  local json_file="$1" field="$2" noun="$3" cap_description="$4" expected fetched
  expected="$(printf '%s' "$pr_json" | jq -r ".$field")"
  fetched="$(jq -s '[.[][]] | length' < "$json_file")"
  if [ "$fetched" -ne "$expected" ]; then
    echo "check-merge-text: fetched $fetched $noun for PR $pr but the PR reports $expected; $cap_description -- refusing rather than scan a partial list." >&2
    exit 1
  fi
}

api_get_paginated "pulls/$pr/commits" > "$dir/commits.json"
refuse_if_fetch_truncated "$dir/commits.json" commits "commit(s)" \
  "GitHub's /commits listing silently caps at 250"
jq -s -r '[.[][] | .commit.message + "\n"] | join("")' < "$dir/commits.json" > "$dir/commits"
jq -s -r '[.[][] | .commit | (.author.name + " <" + .author.email + ">\n" + .committer.name + " <" + .committer.email + ">\n")] | join("")' \
  < "$dir/commits.json" > "$dir/identities"

# The PR's own changed file contents, as they stand at its head commit --
# what actually lands on main if this PR is merged now. This scan itself
# (what it covers, the allow-list it honors) is a separate, already-shipped
# piece of work; only *how* it fetches its data changed above, via the
# same api_get/api_get_paginated helpers. A "removed" file's
# content never lands, so it's excluded; a renamed-only file's content does
# land (at its new path) and stays included. Fetched by blob sha (from the
# same /files listing), not by path through the contents API, so no path
# percent-encoding is needed and there's no contents-API size cap on a large
# file. GitHub's /files endpoint caps out at 3000 changed files with no
# further pagination past that; the check below against pr_json.changed_files
# turns that into a refusal rather than a silent partial scan (issue
# "check-merge-text.sh: additional fail-open / scope gaps", finding 2) -- the
# title, body, commit-message and identity scans above are unaffected either way.
#
# Unlike the title/body/commits/identities scan above, this one *does* get
# the allow-list: these are real files at their real repository-relative
# paths, exactly what .theforge-denylist-allow's self-reference exceptions
# (this script's sibling check-denylist.sh, CLAUDE.md, and similar standing
# files that legitimately name this repository by its own identity) are
# scoped to -- the ordinary pre-commit hook
# already grants them this at commit time, and a merge-time re-scan with no
# allow-list at all would make every future PR that touches one of those
# files permanently unmergeable. repo_dir is given its own throwaway `git
# init` so check-denylist.sh's `git rev-parse --show-toplevel` finds an
# allow-list there. Read at the PR's base, not its head: a PR must not widen
# its own allowance, so a legitimate widening merges in an earlier PR.
repo_dir="$dir/repo"
mkdir -p "$repo_dir"
git init -q "$repo_dir"
# Outside repo_dir, passed by path: the PR's own copy is written into repo_dir
# below as content to scan and must not replace the base list.
base_allow_file="$dir/base-denylist-allow"
api_get_raw_file "contents/.theforge-denylist-allow?ref=$base_sha" \
  > "$base_allow_file" 2>/dev/null || : > "$base_allow_file"
export THEFORGE_DENYLIST_ALLOW_FILE="$base_allow_file"

# The ordinary pre-commit `denylist` hook never runs on a path this exclude
# regex matches at all (vendored third-party prose, .theforge-denylist
# itself, and other rendered/standing paths carrying real tracker numbers
# or the owner's account that are deliberately out of scope -- see
# .pre-commit-config.yaml's own comments on the denylist hook). Pulled from
# that file's own "- id: denylist" block rather than duplicated here, so a
# later edit to the real exclusion is what this scan honors; a PR touching
# one of those paths would otherwise fail a check the normal commit-time
# hook never even runs on it. Base commit, for the same reason as the
# allow-list above.
fetch_pr_version "$base_sha" .pre-commit-config.yaml "$dir/base-pre-commit-config.yaml"
denylist_hook_exclude="$(awk '
  /^[[:space:]]*- id: denylist$/ { infile=1; next }
  infile && /^[[:space:]]*- id:/ { exit }
  infile && /^[[:space:]]*exclude:/ {
    sub(/^[[:space:]]*exclude:[[:space:]]*/, "")
    print
    exit
  }
' "$dir/base-pre-commit-config.yaml")"

# NUL-delimited, not tab/newline-delimited: a git tree entry name can
# legally contain a tab or a newline (rare, but real), which would corrupt
# a tab-separated "$filename\t$sha" record; a NUL byte, by contrast, can
# never appear in one, so pairing fields this way is always unambiguous.
# Collecting the whole filter into one joined string (rather than a plain
# `.[] | select(...) | (...)`) matters here too: jq prints a trailing
# newline after every top-level result, which would otherwise land
# *between* every record (and between pages) and corrupt the NUL framing.
api_get_paginated "pulls/$pr/files" > "$dir/pr-files.json"
refuse_if_fetch_truncated "$dir/pr-files.json" changed_files "changed file entry(ies)" \
  "GitHub's /files listing silently caps at 3000"
jq -s -r '[.[][] | select(.status != "removed") | (.filename + "\u0000" + .sha + "\u0000")] | join("")' \
  < "$dir/pr-files.json" > "$dir/pr-files-list"
pr_file_args=()
while IFS= read -r -d '' pr_file_path && IFS= read -r -d '' pr_file_blob_sha; do
  [ -n "$pr_file_path" ] || continue
  if [ -n "$denylist_hook_exclude" ] && printf '%s' "$pr_file_path" | grep -qP "$denylist_hook_exclude"; then
    continue
  fi
  # A git tree entry can't actually hold a ".." segment or an absolute path,
  # so GitHub's own API shouldn't ever hand us one here -- but pr_file_path
  # is still attacker-influenced (any PR author controls their own file
  # list), and "$repo_dir/$pr_file_path" below is a filesystem write: refuse
  # outright rather than trust that upstream invariant to keep the write
  # inside $repo_dir.
  case "$pr_file_path" in
    /*) pr_file_path_unsafe=1 ;;
    *) pr_file_path_unsafe=0 ;;
  esac
  case "/$pr_file_path/" in
    */../*) pr_file_path_unsafe=1 ;;
  esac
  if [ "$pr_file_path_unsafe" -eq 1 ]; then
    echo "check-merge-text: PR $pr's changed-file list names a path outside the repository ('$pr_file_path'); refusing." >&2
    exit 1
  fi
  pr_file_dest="$repo_dir/$pr_file_path"
  mkdir -p "$(dirname "$pr_file_dest")"
  api_get "git/blobs/$pr_file_blob_sha" | jq -r .content | base64 -d > "$pr_file_dest"
  pr_file_args+=("$pr_file_path")
done < "$dir/pr-files-list"

build_squash_message

# CLAUDE.md, "Agent commit identity" already accepts a GitHub no-reply
# identity whose Name repeats the login its own email encodes; mask only
# that exact, narrow case (never on email shape alone, which check-
# commit-identities.sh below doesn't validate the Name against either --
# keep the two scripts' accepted-shape logic in step if either changes).
identity_name() { # $1 = "Name <email>"; prints Name (no trailing space), or nothing if unparseable
  printf '%s' "$1" | sed -nE 's/^([^<]*)<[^<>]*>$/\1/p' | sed -E 's/[[:space:]]+$//'
}
identity_email() { # $1 = "Name <email>"; prints email, or nothing if unparseable
  printf '%s' "$1" | sed -nE 's/^[^<]*<([^<>]*)>$/\1/p'
}
github_noreply_login() { # $1 = email; prints the login a
                          # "<digits>+login@users.noreply.github.com" address
                          # encodes, or nothing if it isn't that shape
  printf '%s' "$1" | sed -nE 's/^([0-9]+\+)?([^@]+)@users\.noreply\.github\.com$/\2/p'
}
is_self_referential() { # $1 = "Name <email>"; true only when Name is
                         # exactly the login its own no-reply email encodes
  local email login
  email="$(identity_email "$1")"
  [ -n "$email" ] || return 1
  login="$(github_noreply_login "$email")"
  [ -n "$login" ] || return 1
  [ "$(identity_name "$1")" = "$login" ]
}
mask_noreply() { # $1=mode ("whole"=a self-referential identity line,
                  # "trailer"=only a self-referential Co-authored-by one),
                  # $2=src file, $3=dst file
  : > "$3"
  while IFS= read -r line || [ -n "$line" ]; do
    masked=0
    if [ "$1" = "whole" ] && is_self_referential "$line"; then
      masked=1
    elif [ "$1" = "trailer" ] && printf '%s' "$line" | grep -qiE '^co-authored-by:'; then
      trailer="$(printf '%s' "$line" | sed -E 's/^[Cc]o-[Aa]uthored-[Bb]y:[[:space:]]*//')"
      is_self_referential "$trailer" && masked=1
    fi
    if [ "$masked" -eq 1 ]; then
      echo "<no-reply commit identity, accepted by CLAUDE.md>" >> "$3"
    else
      printf '%s\n' "$line" >> "$3"
    fi
  done < "$2"
}
mask_noreply whole "$dir/identities" "$dir/identities-scanned"
mask_noreply trailer "$dir/commits" "$dir/commits-scanned"
# check-commit-identities.sh below needs the *un*masked squash-scanned, so
# mask into a separate file for the denylist pass only.
mask_noreply trailer "$dir/squash-scanned" "$dir/squash-denylist-scanned"

status=0
for piece in title body commits-scanned identities-scanned squash-denylist-scanned; do
  if ! (cd "$dir" && "$here/check-denylist.sh" "$piece"); then
    status=1
  fi
done
# A separate invocation, not folded into the loop above: that scan
# deliberately runs from $dir, outside any git tree, so the allow-list never
# applies to merge text (see the comment above where $dir is created); this
# one runs from $repo_dir, a real (if throwaway) git toplevel whose allow-list
# is the base commit's (THEFORGE_DENYLIST_ALLOW_FILE), so a file like
# check-denylist.sh or CLAUDE.md gets the same self-reference exception
# here that the ordinary pre-commit hook already grants it at commit time.
if [ "${#pr_file_args[@]}" -gt 0 ]; then
  if ! (cd "$repo_dir" && "$here/check-denylist.sh" "${pr_file_args[@]}"); then
    status=1
  fi
fi
if [ "$status" -ne 0 ]; then
  echo "check-merge-text: denylisted terms in PR $pr's merge text or changed file contents; rewrite them before merging." >&2
  exit 1
fi

if ! (cd "$dir" && "$here/check-commit-identities.sh" identities commits squash-scanned); then
  echo "check-merge-text: a non-no-reply commit identity is in PR $pr's head commits or trailers; fix it forward before merging." >&2
  exit 1
fi

# PR-time review guards. Every fetch aborts the scan on trouble (set -e;
# refuse_if_fetch_truncated), so no guard is skipped for lack of data.
# Hazard: $here's copies of the guard scripts are what run, so run this from
# a base-branch checkout; from a PR branch the PR checks itself with its own,
# possibly edited, guard (unenforced; docs/security/threat-model.md, B10).
jq -s -r '[.[][] | .filename + "\n"] | join("")' < "$dir/pr-files.json" > "$dir/pr-files-names"

guard_failed() { # $1 = guard name
  echo "check-merge-text: the $1 guard failed for PR $pr; fix the PR before merging." >&2
  exit 1
}

# pr_file_status PATH -- the PR's own status for PATH ("added", "modified",
# ...), or nothing when the PR doesn't touch it.
pr_file_status() {
  jq -s -r --arg p "$1" '[.[][] | select(.filename == $p) | .status] | first // empty' < "$dir/pr-files.json"
}

python3 "$here/check_review_gate.py" "$dir/body" "$dir/pr-files-names" || guard_failed "review-gate"

sdlc_status="$(pr_file_status docs/software-development-lifecycle.md)"
if [ -n "$sdlc_status" ]; then
  if [ "$sdlc_status" = "added" ]; then
    : > "$dir/sdlc_old.md"
  else
    fetch_pr_version "$base_sha" docs/software-development-lifecycle.md "$dir/sdlc_old.md"
  fi
  fetch_pr_version "$head_sha" docs/software-development-lifecycle.md "$dir/sdlc_new.md"
  python3 "$here/check_sdlc_wording_hold.py" "$dir/body" "$dir/sdlc_old.md" "$dir/sdlc_new.md" \
    || guard_failed "SDLC wording hold"
fi

answers_status="$(pr_file_status .copier-answers.yml)"
if [ -n "$answers_status" ]; then
  if [ "$answers_status" = "added" ]; then
    : > "$dir/answers_old.yml"
  else
    fetch_pr_version "$base_sha" .copier-answers.yml "$dir/answers_old.yml"
  fi
  fetch_pr_version "$head_sha" .copier-answers.yml "$dir/answers_new.yml"
  python3 "$here/check_forge_sync_trust_record.py" "$dir/body" "$dir/answers_old.yml" "$dir/answers_new.yml" \
    || guard_failed "forge-sync trust record"
fi

(cd "$dir" && "$here/check-no-issue-refs.sh" --warn title body commits identities squash-scanned)

# A force-push between the initial fetch (where $head_sha was captured) and
# the commits/files fetches above could leave $head_sha naming a commit
# whose content was never actually scanned (e.g. A -> B -> A, with B's
# content scanned under A's unchanged commit/file counts) -- re-check right
# before reporting success, not just once at the top.
recheck_sha="$(printf '%s' "$(api_get "pulls/$pr")" | jq -r .head.sha)"
if [ "$recheck_sha" != "$head_sha" ]; then
  echo "check-merge-text: PR $pr's head moved from $head_sha to $recheck_sha while this scan ran; re-run the scan against the new head before merging." >&2
  exit 1
fi

echo "check-merge-text: PR $pr's merge text and commit identities are clean."
# Everything above was fetched and scanned at head commit $head_sha; a push
# to the PR between this scan and the merge changes what actually lands,
# with nothing here to catch that drift (issue "check-merge-text.sh:
# additional fail-open / scope gaps", finding 5). Pin the merge to this sha
# (e.g. `gh pr merge --match-head-commit`) rather than merging "whatever the
# PR's head is by the time the merge call runs" -- or re-run this script
# first if the head commit has moved.
echo "Scanned at head commit $head_sha -- pin the merge to it (e.g. 'gh pr merge $pr --match-head-commit $head_sha ...'), or re-run this script first if the PR's head has moved since."
echo "After merging, verify the landed message: scripts/check-merge-text.sh $pr --verify-merged${message_file:+ --message-file '$message_file'} --head-sha $head_sha"
if [ -n "$message_file" ]; then
  echo "This is the exact message from '$message_file', already scanned above -- merge with it unchanged:"
else
  echo "This script guessed the merge message as the title plus the body; merge through the API with" \
       "commit_title/commit_message set to exactly this, or, if you hand-write a different message or" \
       "accept the platform's own default (commit-list) message instead, re-run with --message-file" \
       "before merging with it. Either way, strip any Co-authored-by trailer the platform adds from a" \
       "head commit's author -- this script's message never carries it:"
fi
echo
cat "$dir/squash"
