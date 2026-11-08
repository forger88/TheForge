#!/usr/bin/env python3
"""Check a PR's `Review:` field against the review gate its changed files require.

(`.forge/review-gate.md`, "Full gate and light gate".)

The self-review step this check backs up is the builder's own judgement call
about which gate applies and whether an exemption exists. That judgement is
exactly where real self-merges have gone wrong: one cited an invented
exemption to skip Standards/Spec review and self-review entirely, another
self-declared the light gate on a plain config-file change -- a non-doc file
the light gate (prose-only docs only) never covers. Both were drafting-time
misjudgments against rules that were already clear, which is why this check
has no allowlist of "valid" exemption phrases to keep in sync with the rules:
it recognizes exactly the full-gate and light-gate paths below, and a
`Review:` line citing anything else still has to independently satisfy one
of them.

Usage:
    check_review_gate.py BODY_FILE FILES_FILE

BODY_FILE holds the PR's body text. FILES_FILE lists every path the PR
changes, one per line. Exits 1 with a message naming exactly what's missing
when the `Review:` field doesn't clear the gate its changed files require;
exits 0 otherwise.

A consuming project adopting this guard through `forge-sync` may need its
own "Process changes follow the lifecycle doc" check first: enabling a new
required PR check can itself be an engineering-management-effect policy
change under that project's own rules, separate from whether the rule this
guard enforces is already in force there. Check that project's own rule
before wiring the workflow live, not just before merging the sync.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# A changed path disqualifies the light gate unless it ends in `.md` and
# matches none of these. This is the one place that decides which docs carry
# rules the light gate must not be allowed to skip past -- extend it at
# stage 0, or when a project adds another rule-bearing doc, in the same PR
# that adds the doc.
DISQUALIFYING_DOC_PATTERNS = [
    re.compile(r"(?:^|/)CLAUDE\.md$"),
    re.compile(r"(?:^|/)AGENTS\.md$"),
    re.compile(r"(?:^|/)CONTEXT\.md$"),
    re.compile(r"^docs/principles\.md$"),
    re.compile(r"^docs/decisions-log\.md$"),
    re.compile(r"^docs/software-development-lifecycle\.md$"),
    re.compile(r"^docs/requirements/requirements-specification\.md$"),
    re.compile(r"(?:^|/)\.agents/skills/"),
    re.compile(r"(?:^|/)\.forge/"),
    re.compile(r"^docs/agents/"),
    re.compile(r"^docs/security/threat-model\.md$"),
    re.compile(r"^docs/forge-overrides\.md$"),
    re.compile(r"(?:^|/)pull_request_template\.md$"),
]

# An unfilled template placeholder, e.g. `<performer, tier[, model]>`. Excludes
# a bracketed URL/autolink (`<https://...>`), which is real, filled-in content
# a field is allowed to cite (e.g. a self-review entry linking the PR thread
# it checked), not an unfilled placeholder.
#
# This stays deliberately strict rather than trying to allow every other
# legitimate non-URL bracket mention (a literal tag name, say): this check
# fails closed, and the cost of that -- a real entry has to avoid or quote
# a bare non-URL `<...>` span -- is far cheaper than the cost of the other
# direction, letting a half-filled field (the template's own placeholder
# left in place, with a few genuine words added around it) read as real.
# A word-count-after-stripping heuristic was tried and rejected for exactly
# that failure mode: `<tier>, build-tier` strips to "build-tier" alone,
# clearing a low word threshold while the actual placeholder never got
# filled in.
PLACEHOLDER_RE = re.compile(r"<(?!\w+://)[^<>]*>")
# The one sanctioned way to skip Standards/Spec: `n/a (light gate: <reason>)`.
# Self-review has no equivalent -- it is never exempt. DOTALL: the reason can
# wrap onto a second line, since the paragraph it's drawn from (REVIEW_FIELD_RE)
# is itself matched with DOTALL. The reason is captured, not just matched, so
# field_is_light_gate_na can reject it if it's itself an unfilled `<reason>`
# placeholder.
LIGHT_GATE_RE = re.compile(
    r"^\s*n/?a\s*\(\s*light\s+gate\s*:\s*(?P<reason>.+?)\)\s*$", re.IGNORECASE | re.DOTALL
)
NA_RE = re.compile(r"^\s*n/?a\b", re.IGNORECASE)
# .forge/review-gate.md: an axis the builder reviewed itself never clears the full gate.
BUILDERS_OWN_RE = re.compile(r"builder['\u2019]s own|no sub-agent tool", re.IGNORECASE)

# The template puts `Review:` at the start of its own line/paragraph, so a PR
# body that quotes the field's format elsewhere (to explain a departure, say)
# does so mid-sentence or indented, not as its own line-starting occurrence.
REVIEW_LINE_START_RE = re.compile(r"^Review:\s*Standards:", re.IGNORECASE | re.MULTILINE)
# Self-review's capture stops only at a blank line or end of string; a
# trailing trailer block is stripped afterwards by
# _strip_trailing_trailer_block, which a single-line lookahead here can't
# tell apart from a self-review entry's own hyphenated label line.
REVIEW_FIELD_RE = re.compile(
    r"Review:\s*Standards:\s*(?P<standards>.*?)\.\s*Spec:\s*(?P<spec>.*?)\.\s*Self-review:\s*(?P<selfreview>.*?)\s*\.?\s*(?=\n\s*\n|\Z)",
    re.IGNORECASE | re.DOTALL,
)
# Known commit-trailer keys only, not any hyphenated `Key:` shape: a
# self-review entry's own label (`Fast-path:`, `Reuse:`) never collides with
# one of these, including when such a label is the self-review's last line
# with nothing after it -- the ambiguity a generic hyphenated-word pattern
# would still have. `-by`/`-By` covers the common git-trailer family
# (Signed-off-by, Reviewed-by, Acked-by, Tested-by, Reported-by,
# Suggested-by, Co-authored-by) without naming each one.
_TRAILER_LINE_RE = re.compile(
    r"^(?:[\w-]*-by|Claude-Session|Change-Id|Fixes|Cc|Bug):\s", re.IGNORECASE
)


def _strip_trailing_trailer_block(text: str) -> str:
    """Strip a trailing, contiguous block of commit-trailer lines from the
    end of `text` (routinely appended after the template's last field with
    no separating blank line), leaving everything before the first
    non-trailer, non-blank line (scanning backward) untouched."""
    lines = text.split("\n")
    cut = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if line.strip() == "":
            continue
        if _TRAILER_LINE_RE.match(line):
            cut = i
            continue
        break
    return "\n".join(lines[:cut]).rstrip()


def is_light_gate_eligible(paths: list[str]) -> tuple[bool, str | None]:
    """Every changed path must be a `.md` file outside the disqualifying list.

    Returns (True, None) when the whole change qualifies, or (False, path)
    naming the first disqualifying path found. Fails closed on an empty
    list: a PR always changes at least one file, so an empty list means the
    caller's own data is broken, not that there's nothing to disqualify it.
    """
    if not paths:
        return False, "<no changed files>"
    for path in paths:
        if not path.endswith(".md"):
            return False, path
        if any(pattern.search(path) for pattern in DISQUALIFYING_DOC_PATTERNS):
            return False, path
    return True, None


def field_is_real(text: str) -> bool:
    """A Standards/Spec/Self-review entry that actually says something.

    Rejects an empty field, an unfilled `<...>` placeholder, and anything
    starting with `n/a` (that path is field_is_light_gate_na's, not this
    one's -- an `n/a` that isn't the sanctioned light-gate phrase is neither
    real content nor a recognized exemption, so it fails both checks).
    """
    stripped = text.strip()
    if not stripped:
        return False
    if PLACEHOLDER_RE.search(stripped):
        return False
    return not NA_RE.match(stripped)


def field_is_light_gate_na(text: str) -> bool:
    match = LIGHT_GATE_RE.match(text.strip())
    if not match:
        return False
    reason = match["reason"].strip()
    return bool(reason) and not PLACEHOLDER_RE.search(reason)


def check(body: str, paths: list[str]) -> list[str]:
    """Every failure the Review: field has against the gate its files require.

    Uses the LAST line-starting `Review: Standards:` occurrence in the body,
    and bounds its capture to that paragraph (up to the next blank line or
    end of string). A PR body often has more text after the template's
    `Review:` line (a required attribution footer, for instance) and may
    quote the field's own format earlier for explanation -- matching the
    first occurrence greedily to end-of-string would swallow trailing
    content into Self-review, or lock onto a quoted example instead of the
    real field further down.
    """
    starts = list(REVIEW_LINE_START_RE.finditer(body))
    if not starts:
        return [
            "Review: field missing, or missing one of its Standards:/Spec:/Self-review: "
            "entries (the PR template's `Review:` line has all three)."
        ]
    segment = body[starts[-1].start() :]
    match = REVIEW_FIELD_RE.search(segment)
    if not match:
        return [
            "Review: field missing, or missing one of its Standards:/Spec:/Self-review: "
            "entries (the PR template's `Review:` line has all three)."
        ]

    standards, spec = match["standards"], match["spec"]
    selfreview = _strip_trailing_trailer_block(match["selfreview"])
    eligible, blocker = is_light_gate_eligible(paths)
    failures: list[str] = []

    if not field_is_real(selfreview):
        failures.append("Review: Self-review entry is missing or a placeholder (self-review is never exempt).")

    for label, text in (("Standards", standards), ("Spec", spec)):
        if BUILDERS_OWN_RE.search(text):
            failures.append(
                f"Review: {label} was the builder's own review; the full gate needs a "
                f"clean-context sub-agent for it (.forge/review-gate.md, \"A clean-context "
                f"review needs a sub-agent that really ran\")."
            )
            continue
        if field_is_real(text):
            continue
        if field_is_light_gate_na(text):
            if not eligible:
                failures.append(
                    f"Review: {label} claims the light gate (`n/a (light gate: ...)`), but "
                    f"`{blocker}` is not a prose-only doc eligible for it -- full gate required."
                )
            continue
        failures.append(
            f"Review: {label} entry is missing, a placeholder, or cites an exemption this check "
            f"doesn't recognize. Only a real entry, or `n/a (light gate: <reason>)` when every "
            f"changed file qualifies for the light gate, is accepted -- no other exemption skips "
            f"this axis."
        )

    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_review_gate.py BODY_FILE FILES_FILE", file=sys.stderr)
        return 2
    body = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
    paths = [line.strip() for line in Path(argv[1]).read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]

    failures = check(body, paths)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
