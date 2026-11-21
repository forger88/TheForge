#!/usr/bin/env python3
"""Vendored-skill guard (skills-lock.json / THIRD_PARTY.md, "Vendored skills").

Checks `skills-lock.json` at the repo root against the files actually under
`.agents/skills/`, with no network access: it compares against the content
hash recorded at vendoring time, never against upstream, so a stale lock is
caught the same way whether upstream has moved on or not. It fails when:

- a lock entry names a skill directory that doesn't exist;
- a lock entry has no recorded `computedHash`;
- a skill's current content no longer matches its lock entry's
  `computedHash`, computed over every file in the skill's whole directory
  (not just its `SKILL.md`), hashed together by sorted relative path, so a
  vendored skill's supporting scripts and reference files are tamper-checked
  the same as `SKILL.md` itself;
- a skill directory whose `SKILL.md` (or `SKILL.md.jinja`) carries an
  upstream `<!-- Source: ... -->` note has no lock entry at all;
- under `--template` (this repository's own copy; see
  `check_forge_entrypoint.py`'s `--root`/`--template` for the same two-hook
  convention), `skills-lock.json` itself is missing, or a lock entry has
  `"templated": true` but its primary file isn't a `SKILL.md.jinja` (a
  plain `SKILL.md` marked templated would otherwise be excluded from the
  hash entirely and never checked at all). Without `--template` (a
  generated project, which may legitimately vendor no skills, or whose
  `.jinja` files Copier has already rendered away) neither case is an
  error.

A skill marked "Modified" in its own source note is still checked the same
way as one marked "Unmodified": the lock's hash tracks this repository's
current content, not the pristine upstream content, so a deliberate local
edit updates the lock entry in the same change, exactly like any other
pinned dependency (.forge/code-shape-rules.md, "Pinned dependencies").

A lock entry carrying `"templated": true` (a vendored skill shipped as
`SKILL.md.jinja`, so Copier renders it per project) ships identically into
every generated project, so its one recorded `computedHash` has to pass in
both places: here, where the primary file is `SKILL.md.jinja`, and in a
rendered project, where it's a plain, per-project-substituted `SKILL.md`.
Since that one file's bytes necessarily differ between the two, the
`computedHash` for a templated entry is the directory hash with the primary
file excluded on both sides, so every *other* file in the skill's directory
(scripts, reference docs, and the like) still goes through the same
tamper-check as any other skill's. The primary file's own content, which
only this repository can check (there's no single hash a per-project render
could match), is covered separately by the entry's `templateHash`: the
`.jinja` source's own bytes, checked only here, never against a rendered
project's plain `SKILL.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = ROOT / "skills-lock.json"
SKILLS_DIR = ROOT / ".agents" / "skills"
SOURCE_NOTE = re.compile(r"<!--\s*Source:")


def hash_target(path: Path, exclude: Path | None = None) -> str:
    """Sha256 of a single file's bytes, or of a whole directory's files by sorted relative path.

    `exclude`, when given, is a file under a directory `path` to leave out of
    the hash (the one file Copier rendering diverges on; see module docstring).
    """
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    files = (p for p in path.rglob("*") if p.is_file() and p != exclude)
    # Sort on the relative path's str parts, not the Path: WindowsPath orders
    # case-insensitively (`agents/` before `SKILL.md`), which changes the hash.
    for file in sorted(files, key=lambda p: p.relative_to(path).parts):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def skill_file(skill_dir: Path) -> Path | None:
    """The one SKILL.md (or SKILL.md.jinja) file a single-file skill is hashed from."""
    candidates = [p for p in (skill_dir / "SKILL.md", skill_dir / "SKILL.md.jinja") if p.is_file()]
    return candidates[0] if len(candidates) == 1 else None


def check_lock_entries(lock: dict, template: bool) -> list[str]:
    errors: list[str] = []
    for name, entry in lock.get("skills", {}).items():
        skill_dir = SKILLS_DIR / name
        if not skill_dir.is_dir():
            errors.append(f"{name}: skills-lock.json names this skill, but {skill_dir} does not exist")
            continue
        skill_path = entry.get("skillPath", ".")
        exclude = None
        primary = None
        if skill_path != ".":
            primary = skill_file(skill_dir)
            if primary is None or not primary.exists():
                errors.append(f"{name}: no single SKILL.md or SKILL.md.jinja under {skill_dir}")
                continue
            if entry.get("templated"):
                if template and primary.suffix != ".jinja":
                    # In a generated project the primary is legitimately a
                    # plain, already-rendered SKILL.md; only this repo's own
                    # source tree is required to carry the .jinja itself.
                    errors.append(
                        f"{name}: skills-lock.json marks this skill \"templated\", but {primary} is "
                        "not a SKILL.md.jinja; this repository's own source tree must carry the "
                        ".jinja, or the flag should be removed"
                    )
                    continue
                # Its bytes differ between this repo's .jinja and a render's
                # plain SKILL.md; excluded here, checked via templateHash below.
                exclude = primary
        recorded = entry.get("computedHash")
        if not recorded:
            errors.append(f"{name}: skills-lock.json has no computedHash; add one (sha256 of the skill directory)")
            continue
        actual = hash_target(skill_dir, exclude=exclude)
        if actual != recorded:
            errors.append(
                f"{name}: content no longer matches skills-lock.json's computedHash "
                f"(recorded {recorded}, now {actual}); update the lock entry if this change was "
                "deliberate and reviewed, or restore the file if it was not"
            )
        if primary is not None and entry.get("templated") and primary.suffix == ".jinja":
            recorded_template = entry.get("templateHash")
            if not recorded_template:
                errors.append(f"{name}: skills-lock.json has no templateHash; add one (sha256 of {primary.name})")
                continue
            actual_template = hash_target(primary)
            if actual_template != recorded_template:
                errors.append(
                    f"{name}: {primary.name} content no longer matches skills-lock.json's templateHash "
                    f"(recorded {recorded_template}, now {actual_template}); update the lock entry if this "
                    "change was deliberate and reviewed, or restore the file if it was not"
                )
    return errors


def check_unlocked_vendored_skills(lock: dict) -> list[str]:
    errors: list[str] = []
    if not SKILLS_DIR.is_dir():
        return errors
    locked = set(lock.get("skills", {}))
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        if skill_dir.name in locked:
            continue
        candidates = [p for p in (skill_dir / "SKILL.md", skill_dir / "SKILL.md.jinja") if p.is_file()]
        for skill_md in candidates:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            if SOURCE_NOTE.search(text):
                errors.append(
                    f"{skill_dir.name}: {skill_md.name} carries an upstream Source note "
                    "but skills-lock.json has no entry for it"
                )
                break
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        action="store_true",
        help="Run as this repository's own template/ copy, where skills-lock.json and every "
        "templated entry's .jinja source must always be present.",
    )
    args = parser.parse_args(argv)

    if not LOCK_PATH.exists():
        if args.template:
            print(
                f"check_skills_lock: FAIL: {LOCK_PATH} is missing; this repository always vendors "
                "skills and must always carry a lock.",
                file=sys.stderr,
            )
            return 1
        print("check_skills_lock: NOT RUNNING: no skills-lock.json at the repo root.")
        return 0
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    errors = check_lock_entries(lock, template=args.template) + check_unlocked_vendored_skills(lock)
    for line in errors:
        print(line, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
