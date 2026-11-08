#!/usr/bin/env python3
"""Guards `.forge/coordinator-core.md` and its project-instruction snippet.

`shape` checks the core file is no longer than MAX_CHARS, opens with its
truncation-guard instruction, ends with its codeword marker, and carries one
mid-file check word line in its middle third, each word appearing nowhere else
(so a reader's proof needs the file's last line and its middle, which neither a
tail read nor a relayed last line supplies). `drift` checks the live project-instructions text, saved
to a file, still carries the repo's snippet verbatim (whitespace-normalised).
`rotated` checks both words actually changed whenever the file's body did,
by diffing the working-tree text against the same file at a prior git ref.
`lock` checks each core section's `Condenses:` provenance line against
`coordinator-core.lock.json`: the hash of every cited source section (read
from the `template/` source text, whitespace-normalised) and the codeword
must match, so a source rule cannot change without the core being re-read and
the lock refreshed (`lock --refresh`, which refuses unless the codeword
rolled).

`notes` checks an update of the harness's project instructions carries the
owner's coordinator-notes zone through unchanged (SDLC-118) and fits the
host's size limit; it fails closed when the live text has no recognisable
zone, unless `--first-write` says it has never had one.

TheForge's coordinator-core ADR records the problem this file solves and the
constraints that must survive every edit to it.

Usage:
    check_coordinator_core.py shape [CORE_FILE]
    check_coordinator_core.py drift LIVE_FILE [--snippet SNIPPET_FILE]
    check_coordinator_core.py rotated [CORE_FILE] [--against REF]
    check_coordinator_core.py notes [--first-write] LIVE_FILE NEW_FILE
    check_coordinator_core.py lock [--refresh] [CORE_FILE] [--lock LOCK_FILE] [--source-root DIR]
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _git_subprocess import run_git  # noqa: E402

# Owner-set ceiling, so the whole file still fits one read by a harness with a small file-read limit.
MAX_CHARS = 64_000
GUARD_HEADING = "TRUNCATION GUARD"
GUARD_WINDOW_LINES = 10
MARKER_RE = re.compile(r"^END OF COORDINATOR CORE — codeword: ([A-Z]{6,})$")
MID_RE = re.compile(r"^Mid-file check word: ([A-Z]{6,})$")
SNIPPET_START = "<!-- coordinator-core-snippet:start -->"
SNIPPET_END = "<!-- coordinator-core-snippet:end -->"
DEFAULT_CORE = Path(".forge/coordinator-core.md")
DEFAULT_SNIPPET = Path("docs/agents/coordinator-core-snippet.md")
DEFAULT_LOCK = Path("coordinator-core.lock.json")
DEFAULT_SOURCE_ROOT = Path("template")
PROVENANCE_PREFIX = "Condenses: "
NO_SOURCE = "none (authoritative)"
GIT_TIMEOUT = 30
CHAR_LIMIT = 16_000  # bytes, UTF-8 encoded: what `wc -c` and the harness's project-instructions field both count
# The canonical heading a created notes zone gets; a live heading is recognised by NOTES_HEADING_RE instead.
# If you change this, also change the zone name in coordinator/SKILL.md's "Preserving coordinator notes"
# and coordinator-core.md's "Project instructions".
NOTES_HEADING = "## Coordinator notes (owner-requested, preserved on update)"
# SDLC-118: a live heading reworded after the fact must still be found; an exact match fails open.
NOTES_HEADING_RE = re.compile(r"^## coordinator notes\b", re.IGNORECASE)
# Live project instructions written while the composer existed carry this line directly above the
# generated content; a notes zone that sits right above it has no heading to end at, so
# extract_notes_zone stops here too.
MARKER = "<!-- generated below: compose_project_instructions.py (SDLC-113); edit the source skills, never this text -->"


class NotesError(ValueError):
    """The text itself is ambiguous (not drift between two copies)."""


def _last_marker_match(text: str) -> re.Match[str] | None:
    non_empty = [line for line in text.splitlines() if line.strip()]
    return MARKER_RE.match(non_empty[-1].strip()) if non_empty else None


def _body_without_marker(text: str) -> str:
    """Everything before the final non-empty line (the codeword marker),
    normalised the way `_normalise` does for `drift_problems`."""
    lines = text.splitlines()
    non_empty_idxs = [i for i, line in enumerate(lines) if line.strip()]
    if not non_empty_idxs:
        return ""
    return _normalise("\n".join(lines[: non_empty_idxs[-1]]))


def _mid_matches(text: str) -> list[tuple[int, re.Match[str]]]:
    """Each mid-file check word line, with its index among the file's non-empty lines."""
    non_empty = [line.strip() for line in text.splitlines() if line.strip()]
    return [(i, m) for i, line in enumerate(non_empty) if (m := MID_RE.match(line))]


def _mid_word(text: str) -> str | None:
    matches = _mid_matches(text)
    return matches[0][1].group(1) if len(matches) == 1 else None


def _strip_mid_line(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not MID_RE.match(line.strip()))


def shape_problems(text: str) -> list[str]:
    errors: list[str] = []
    if len(text) > MAX_CHARS:
        errors.append(f"is {len(text)} characters, over the {MAX_CHARS} limit")
    lines = text.splitlines()
    if not any(GUARD_HEADING in line for line in lines[:GUARD_WINDOW_LINES]):
        errors.append(f"has no '{GUARD_HEADING}' instruction in its first {GUARD_WINDOW_LINES} lines")
    match = _last_marker_match(text)
    if match is None:
        errors.append("does not end with an 'END OF COORDINATOR CORE — codeword: <WORD>' line")
    else:
        codeword = match.group(1)
        if text.count(codeword) != 1:
            errors.append(f"names its codeword {codeword!r} more than once; it must appear only on the last line")
    mids = _mid_matches(text)
    if len(mids) != 1:
        errors.append(f"has {len(mids)} 'Mid-file check word: <WORD>' lines; it must have exactly one")
    else:
        index, mid = mids[0]
        word = mid.group(1)
        total = sum(1 for line in lines if line.strip())
        # A tail read must not reach it, and a head read must not either.
        if not total // 3 <= index < total - total // 3:
            errors.append(f"has its mid-file check word on non-empty line {index + 1} of {total}; it must sit in the middle third")
        if text.count(word) != 1:
            errors.append(f"names its mid-file check word {word!r} more than once; it must appear only on its own line")
        if match is not None and match.group(1) == word:
            errors.append("uses the same word for the codeword and the mid-file check word")
    return errors


def rotated_problems(old_text: str | None, new_text: str) -> list[str]:
    """`old_text` is None for a brand-new file -- nothing to rotate against.
    Otherwise, a body change (everything but the marker line) with the same
    codeword as before is the gap this guards: the codeword's only job is to
    tell a fresh copy from a stale one, so it must move whenever the body
    does. A malformed or missing marker on either side is `shape`'s problem,
    not this one's."""
    if old_text is None:
        return []
    old_match = _last_marker_match(old_text)
    new_match = _last_marker_match(new_text)
    if old_match is None or new_match is None:
        return []
    if _body_without_marker(old_text) == _body_without_marker(new_text):
        return []
    problems = []
    codeword = new_match.group(1)
    if old_match.group(1) == codeword:
        problems.append(f"coordinator-core.md's body changed but its codeword is still {codeword!r}; roll the codeword on the END OF COORDINATOR CORE line")
    old_mid, new_mid = _mid_word(old_text), _mid_word(new_text)
    body_changed = _body_without_marker(_strip_mid_line(old_text)) != _body_without_marker(_strip_mid_line(new_text))
    if body_changed and old_mid == new_mid:
        problems.append(f"coordinator-core.md's body changed but its mid-file check word is still {new_mid!r}; roll it too")
    return problems


def snippet_text(snippet_file_text: str) -> str | None:
    start = snippet_file_text.find(SNIPPET_START)
    end = snippet_file_text.find(SNIPPET_END)
    if start == -1 or end == -1 or end < start:
        return None
    return snippet_file_text[start + len(SNIPPET_START) : end]


def _normalise(text: str) -> str:
    return " ".join(text.split())


def drift_problems(live: str, snippet_file_text: str) -> list[str]:
    snippet = snippet_text(snippet_file_text)
    if snippet is None or not snippet.strip():
        return [f"snippet file has no text between {SNIPPET_START} and {SNIPPET_END}"]
    if _normalise(snippet) in _normalise(live):
        return []
    missing = [line.strip() for line in snippet.splitlines() if line.strip() and _normalise(line) not in _normalise(live)]
    detail = f"; first line not found: {missing[0]!r}" if missing else "; every line is present but not in the snippet's order"
    return ["the live project instructions do not carry the coordinator-core snippet verbatim" + detail]


class SectionNotFound(ValueError):
    """A cited heading is missing, or appears more than once, in its source file."""


def extract_markdown_section(text: str, heading: str, file_label: str) -> str:
    """Returns the body of the section opened by an exact `heading` line
    (stripped of surrounding whitespace), up to the next heading at the same
    or a shallower `#`-depth, exclusive of both heading lines."""
    lines = text.split("\n")
    depth = len(heading) - len(heading.lstrip("#"))
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        raise SectionNotFound(f"{file_label}: heading {heading!r} not found")
    end = len(lines)
    for i in range(start, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("#") and len(stripped) - len(stripped.lstrip("#")) <= depth:
            end = i
            break
    return "\n".join(lines[start:end]).strip("\n")


def _heading_line(text: str, heading_text: str, label: str) -> str:
    matches = [ln.strip() for ln in text.split("\n") if re.fullmatch(r"#{1,6} " + re.escape(heading_text), ln.strip())]
    if len(matches) != 1:
        raise SectionNotFound(f"{label}: heading {heading_text!r} found {len(matches)} times, expected exactly once")
    return matches[0]


def _source_text(source_root: Path, rel: str) -> str | None:
    for candidate in (source_root / rel, source_root / (rel + ".jinja")):
        text = _read(candidate)
        if text is not None:
            return text
    return None


def _section_hash(source_root: Path, path: str, heading_text: str) -> str:
    text = _source_text(source_root, path)
    if text is None:
        raise SectionNotFound(f"cited source {path} not found under {source_root}/")
    body = extract_markdown_section(text, _heading_line(text, heading_text, path), path)
    return hashlib.sha256(_normalise(body).encode("utf-8")).hexdigest()


def core_codeword(core_text: str) -> str | None:
    lines = [ln for ln in core_text.splitlines() if ln.strip()]
    match = MARKER_RE.match(lines[-1]) if lines else None
    return match.group(1) if match else None


def _core_sections(core_text: str) -> list[tuple[str, str | None]]:
    """Each `## ` section's heading text and the first non-blank line under it."""
    lines = core_text.split("\n")
    sections = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            following = next((ln.strip() for ln in lines[i + 1 :] if ln.strip()), None)
            sections.append((line[3:].strip(), following))
    return sections


def build_lock(core_text: str, source_root: Path) -> tuple[dict, list[str]]:
    """The lock the core's provenance lines imply right now, plus any problem reading them."""
    problems: list[str] = []
    codeword = core_codeword(core_text)
    if codeword is None:
        problems.append("the core has no END OF COORDINATOR CORE codeword line")
    sections: dict[str, list[dict]] = {}
    for heading, first_line in _core_sections(core_text):
        if first_line is None or not first_line.startswith(PROVENANCE_PREFIX):
            problems.append(f'core section "{heading}" has no "{PROVENANCE_PREFIX.strip()}" provenance line directly under its heading')
            continue
        cited = first_line[len(PROVENANCE_PREFIX) :].strip()
        entries: list[dict] = []
        if cited != NO_SOURCE:
            for item in cited.split("; "):
                match = re.fullmatch(r'(\S+) "(.+)"', item.strip())
                if match is None:
                    problems.append(f'core section "{heading}": cannot read provenance item {item!r}; expected <path> "<heading>"')
                    continue
                path, source_heading = match.groups()
                try:
                    entries.append({"path": path, "heading": source_heading, "sha256": _section_hash(source_root, path, source_heading)})
                except SectionNotFound as exc:
                    problems.append(f'core section "{heading}": {exc}')
        sections[heading] = entries
    return {"version": 1, "codeword": codeword, "sections": sections}, problems


def lock_problems(core_text: str, lock: dict | None, source_root: Path) -> list[str]:
    built, problems = build_lock(core_text, source_root)
    if problems:
        return problems
    if lock is None:
        return ["the lock file is missing or unreadable; create it with `lock --refresh`"]
    if not isinstance(lock, dict) or not isinstance(lock.get("sections"), dict):
        return ["the lock file is malformed (expected an object with a \"sections\" object); recreate it with `lock --refresh`"]
    if lock.get("codeword") != built["codeword"]:
        problems.append(f"the lock's codeword {lock.get('codeword')!r} differs from the core's {built['codeword']!r}; re-read the core and run `lock --refresh`")
    locked = lock.get("sections", {})
    for heading in sorted(set(locked) - set(built["sections"])):
        problems.append(f'the lock has a section "{heading}" the core no longer has')
    for heading, entries in built["sections"].items():
        old = locked.get(heading)
        if old is None:
            problems.append(f'core section "{heading}" is not in the lock')
            continue
        if [(e["path"], e["heading"]) for e in entries] != [(e.get("path"), e.get("heading")) for e in old]:
            problems.append(f'core section "{heading}" cites different sources than the lock records')
            continue
        for new, prior in zip(entries, old):
            if new["sha256"] != prior.get("sha256"):
                problems.append(
                    f'core section "{heading}": source {new["path"]} "{new["heading"]}" changed since the lock was refreshed; '
                    "re-read this core section against it, roll the codeword, then run `lock --refresh`"
                )
    return problems


def refresh_lock(core_text: str, lock: dict | None, source_root: Path) -> tuple[dict | None, list[str]]:
    """The lock to write, or None plus the reasons it must not be written yet."""
    built, problems = build_lock(core_text, source_root)
    if problems:
        return None, problems
    if lock is not None and not isinstance(lock, dict):
        lock = None
    if lock is not None and lock != built and lock.get("codeword") == built["codeword"]:
        return None, ["a refresh means the core was re-read: roll the codeword on the END OF COORDINATOR CORE line first"]
    return built, []


def is_notes_heading(line: str) -> bool:
    return NOTES_HEADING_RE.match(line.strip()) is not None


def extract_notes_zone(text: str, label: str) -> str | None:
    """Returns the zone under a '## Coordinator notes' heading, heading line included, up to the
    next `#`/`##` heading or MARKER, or None.

    Raises NotesError when more than one such heading appears (no copy is then unambiguous)."""
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if is_notes_heading(line)]
    if not starts:
        return None
    if len(starts) > 1:
        raise NotesError(f"{label}: a '## Coordinator notes' heading appears {len(starts)} times")
    end = len(lines)
    for i in range(starts[0] + 1, len(lines)):
        if lines[i].startswith(("# ", "## ")) or lines[i].strip() == MARKER:
            end = i
            break
    return "\n".join(line.rstrip() for line in lines[starts[0] : end]).strip("\n")


def notes_problems(live_text: str, new_text: str, *, first_write: bool = False) -> list[str]:
    """SDLC-118: the problems that stop an update of the project instructions
    because it would change the coordinator-notes zone. An empty list means
    the zone is carried through unchanged (or, with first_write, is new) and
    the new text fits the host limit. Any difference is reported,
    owner-directed or not: the caller proceeds only when the printed diff is
    exactly the change the owner asked for. A live text with no recognisable
    zone is an error unless first_write says it has never had one."""
    problems = []
    # The host refuses an over-limit text outright; the fix is the owner's call, never a trimmed note.
    byte_length = len(new_text.encode("utf-8"))
    if byte_length > CHAR_LIMIT:
        problems.append(
            f"the new text is {byte_length} bytes, over the {CHAR_LIMIT}-byte harness limit; "
            "ask the owner what to shorten"
        )
    live = extract_notes_zone(live_text, "live")
    new = extract_notes_zone(new_text, "new")
    if live is None:
        if first_write:
            return problems
        return problems + [
            "the live text has no '## Coordinator notes' heading; pass --first-write only if it "
            "has never had a notes zone, otherwise ask the owner which section holds the notes"
        ]
    if live == new:
        return problems
    if new is None:
        return problems + ["the new text has no '## Coordinator notes' zone; the live one would be lost"]
    diff = difflib.unified_diff(
        live.split("\n"), new.split("\n"), "live notes", "new notes", lineterm=""
    )
    return problems + ["the coordinator-notes zone differs from the live one:\n" + "\n".join(diff)]


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _read_at_ref(path: Path, ref: str) -> str | None:
    """`path`'s text at `ref`, or None when it didn't exist there (a
    brand-new file, or `ref` itself missing, e.g. the repo's first commit)."""
    result = run_git(["git", "show", "--end-of-options", f"{ref}:{path}"], GIT_TIMEOUT)
    return result.stdout if result.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    shape = sub.add_parser("shape")
    shape.add_argument("core", nargs="?", type=Path, default=DEFAULT_CORE)
    drift = sub.add_parser("drift")
    drift.add_argument("live", type=Path)
    drift.add_argument("--snippet", type=Path, default=DEFAULT_SNIPPET)
    rotated = sub.add_parser("rotated")
    rotated.add_argument("core", nargs="?", type=Path, default=DEFAULT_CORE)
    rotated.add_argument("--against", default="HEAD")
    lock = sub.add_parser("lock")
    lock.add_argument("core", nargs="?", type=Path, default=DEFAULT_CORE)
    lock.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    lock.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    lock.add_argument("--refresh", action="store_true")
    notes = sub.add_parser("notes")
    notes.add_argument("--first-write", action="store_true")
    notes.add_argument("live", type=Path)
    notes.add_argument("new", type=Path)
    args = parser.parse_args(argv)

    if args.command == "shape":
        text = _read(args.core)
        if text is None:
            print(f"check_coordinator_core: {args.core} is missing or unreadable", file=sys.stderr)
            return 1
        errors = [f"{args.core} {problem}" for problem in shape_problems(text)]
    elif args.command == "drift":
        live = _read(args.live)
        snippet_file = _read(args.snippet)
        if live is None or snippet_file is None:
            missing = args.live if live is None else args.snippet
            print(f"check_coordinator_core: {missing} is missing or unreadable", file=sys.stderr)
            return 1
        errors = drift_problems(live, snippet_file)
    elif args.command == "lock":
        core_text = _read(args.core)
        if core_text is None:
            print(f"check_coordinator_core: {args.core} is missing or unreadable", file=sys.stderr)
            return 1
        lock_text = _read(args.lock)
        try:
            lock_obj = json.loads(lock_text) if lock_text is not None else None
        except json.JSONDecodeError as exc:
            print(f"check_coordinator_core: {args.lock} is not valid JSON: {exc}", file=sys.stderr)
            return 1
        if args.refresh:
            new_lock, errors = refresh_lock(core_text, lock_obj, args.source_root)
            if new_lock is not None:
                try:
                    args.lock.write_text(json.dumps(new_lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                except OSError as exc:
                    print(f"check_coordinator_core: cannot write {args.lock}: {exc}", file=sys.stderr)
                    return 1
                print(f"wrote {args.lock}")
        else:
            errors = lock_problems(core_text, lock_obj, args.source_root)
            if not errors:
                print("coordinator-core lock is current")
    elif args.command == "notes":
        live_text, new_text = _read(args.live), _read(args.new)
        if live_text is None or new_text is None:
            missing = args.live if live_text is None else args.new
            print(f"check_coordinator_core: {missing} is missing or unreadable", file=sys.stderr)
            return 1
        try:
            errors = notes_problems(live_text, new_text, first_write=args.first_write)
        except NotesError as exc:
            errors = [str(exc)]
        if not errors:
            print("coordinator-notes zone carried through unchanged")
    else:
        new_text = _read(args.core)
        if new_text is None:
            print(f"check_coordinator_core: {args.core} is missing or unreadable", file=sys.stderr)
            return 1
        old_text = _read_at_ref(args.core, args.against)
        errors = rotated_problems(old_text, new_text)

    for error in errors:
        print(f"check_coordinator_core: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
