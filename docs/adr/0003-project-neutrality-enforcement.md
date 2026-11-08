# ADR-0003: Project neutrality is enforced in three checks

**Status:** accepted (the denylist check amended for the private staging repository only by ADR-0005: it now commits its own denylist; the public TheForge repository's practice is unchanged)

## Context

TheForge is public, and its content is distilled from real projects that use this process.
That distillation is the main way project-specific material leaks in: a product name left in a skill, an issue number cited as the reason for a rule, a configuration key used as an example, a worked example that still has the shape of the incident it came from even after its names were changed.

Each of these leaks has a different shape, and no single check catches all of them.

## Decision

Project neutrality is enforced by three checks (`CLAUDE.md`, "TheForge stays project-neutral"), and every change passes all three.

1. **A mechanical scan**, run as pre-commit hooks, with no context needed to apply it:
   - `scripts/check-no-issue-refs.sh`: an `#NNN` pattern (a hash and two to six digits) fails the commit.
     `THIRD_PARTY.md` credit files are the single exemption.
   - `scripts/check-denylist.sh`: a case-insensitive grep against a denylist read from a path outside the repository.
     It catches known project-specific terms, but it cannot know them on its own, so the maintainer back-porting from a project supplies that project's terms.
     The denylist is never committed to the public TheForge repository, because a public list of what to hide is itself a leak (amended for this private staging repository only, by ADR-0005, which commits its own real denylist here).
2. **A read-through by a fresh, context-free reviewing agent**, given the diff with no history of the source project, that treats any oddly specific term or example as a finding.
   This is what catches everything a pattern cannot: an example still shaped like its original incident, an oddly specific term nobody thought to denylist, a person's name.
3. **A merge-text scan** (`scripts/check-merge-text.sh`), run before merging: the squash message, the PR's title, body and commit messages, and every head commit's author/committer name and email, since a squash merge writes text no pre-commit hook sees and copies commit authors into `Co-authored-by:` trailers the script's own squash message never carries.
   The same script also requires every head-commit identity and `Co-authored-by:` trailer to be no-reply-shaped (`scripts/check-commit-identities.sh`; `CLAUDE.md`, "Agent commit identity"), the mechanical guard for that rule.

## Alternatives rejected

- **The regex alone.** Catches only references, not names, vocabulary or examples.
- **A committed denylist.** Would publish the very terms it exists to keep out.
- **A human or agent read-through alone.** Reliable for judgement, unreliable for volume: a reviewer skimming a large back-port misses a stray number a regex never would.

## Consequences

- No single check is sufficient alone, and none is skipped because another passed.
- A contributor with no denylist is not blocked: the denylist hook skips with a note.
  A maintainer back-porting from a real project always supplies one.
- The few public terms that must appear (the template's copyright holder in its licence and its own source location) are allowed by `path:term` pairs in `.theforge-denylist-allow`, never by weakening the scan.
  The merge-text scan deliberately does not consult that allow-list at all, including for a head commit's or the squash commit's own identity: it runs from outside any working tree, so no self-reference exception applies to merge text.
