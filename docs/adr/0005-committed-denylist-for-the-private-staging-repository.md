# ADR-0005: The private staging repository commits its own denylist

**Status:** accepted (amended 2026-10-29: an active override unions with the committed denylist rather than replacing it -- see "Amendment" below)

## Context

ADR-0003 rejected a committed denylist outright: "would publish the very terms it exists to keep out." That held when there was one repository, and anything committed to it was, by definition, headed for the public template.

That is no longer the shape of this project. The public TheForge repository is now a downstream product of this private staging repository, published from it rather than identical to it (issue "Commit a real denylist into staging, wire the merge-text scan to it by default, and hard-exclude it from the public snapshot"). The owner, 2026-10-27:

> Now that the public The Forge is going to be a product of the private The Forge Staging, i think we can afford to put more hard edged sanitisation checks into The Forge Staging, with explicit denylists that include my name, email addresses, names of other projects, etc.
>
> Yes raise a ticket to fix the denylist problem. Commit it to the forge staging. I'll keep that as a private repo. Queue it now.

In the meantime, `scripts/check-merge-text.sh` and `scripts/check-denylist.sh` had been running in practice with no denylist present in most working environments at all (none of `$THEFORGE_DENYLIST_FILE` or `~/.theforge-denylist` is normally set in an agent session), which is closer to "no denylist, no scan" than to the layered defense ADR-0003 describes.

## Decision

This private staging repository (only) commits a real denylist, `.theforge-denylist`, naming the owner's standing terms: his name, email addresses, and the names of other projects distilled into TheForge. `scripts/denylist-path.sh` makes it the default `check-denylist.sh`/`check-merge-text.sh` resolve to when neither `$THEFORGE_DENYLIST_FILE` nor `~/.theforge-denylist` is set, so a scan in this repository has something real to check against without a maintainer provisioning it each session.

ADR-0003's own two reasons against a committed denylist are addressed, not removed:

- "Would publish the very terms it exists to keep out" -- true only if the committed file reaches a generated project or the public snapshot. It must not reach a generated project, and does not structurally: it lives at the repository root, outside `template/`, which Copier's `_subdirectory: template` setting never copies from. `scripts/check-denylist-not-shipped.sh` (an always-run pre-commit hook) and `scripts/test_denylist_not_shipped.py` (which renders the template end-to-end) both go red if that ever changes. Reaching the eventual public snapshot is a separate, not-yet-structural guarantee: the public repository is expected to be a snapshot of this repository's own root, not a Copier render, so nothing yet stops a root-level file from being published that way. Closing that gap is the publish method's job (issue "Commit a real denylist into staging, wire the merge-text scan to it by default, and hard-exclude it from the public snapshot"; issue "Publish TheForge as a fresh repository with no history"), not this ADR's.
- The maintainer-back-port use case ADR-0003 built the external-file mechanism for -- naming a *different* source project's terms for one scan, without keeping them anywhere permanent -- still works: `$THEFORGE_DENYLIST_FILE` (or `~/.theforge-denylist`) adds its own terms to the committed default rather than replacing it (amended below).

ADR-0003 itself is otherwise unchanged and still governs the public TheForge repository's own practice in full: a committed denylist there remains rejected, for the original reason, because nothing stops that repository's own content from being public.

## Alternatives rejected

- **Keep relying on a maintainer-supplied external file for this repository too.** This is the status quo ADR-0003 chose, and the one this ADR amends: in practice it left most sessions scanning against nothing.
- **Commit the denylist to the public TheForge repository as well.** Rejected outright; that repository's content is exactly what must never carry it, which is why this decision is scoped to the private staging repository by name, not to "TheForge" generally.

## Amendment, 2026-10-29: the override unions rather than replaces

The three-tier resolution below originally had an override (`$THEFORGE_DENYLIST_FILE` or `~/.theforge-denylist`) *replace* the committed default for that one scan, matching ADR-0003's original external-file mechanism and the actor row in `docs/security/threat-model.md`. A post-merge review run flagged the consequence: a back-port session, or a stale `~/.theforge-denylist` left over from one, ran with none of the owner's own standing terms checked -- exactly the highest-risk work, with the owner's own protections off.

The owner, deciding between a decision card's options on 2026-10-29: "Fix the bug so the additional terms (not 'override' -- you've named that poorly) works as union not replace."

`scripts/denylist-path.sh` now unions an active override's terms with the committed denylist's terms (when the committed file exists and differs from the override), rather than one replacing the other. `check-denylist.sh` builds its pattern set from both files' terms combined. A maintainer back-porting from a real project still points `$THEFORGE_DENYLIST_FILE` at that project's own terms only -- nothing changes about what the maintainer supplies -- but the scan also keeps checking the committed terms alongside it. The three-tier resolution for which file is the *primary* one (used for the existing missing/empty-file fail-closed checks) is unchanged; only what gets unioned in afterwards is new.

## Consequences

- `scripts/denylist-path.sh` is the one place the resolution lives; both `check-denylist.sh` and `check-merge-text.sh` source it rather than duplicating the lookup. The three-tier priority (`$THEFORGE_DENYLIST_FILE`, then `~/.theforge-denylist`, then this repository's own `.theforge-denylist`) still decides the *primary* file; the amendment above adds the committed file back in as a union whenever the primary is an override.
- `.theforge-denylist`'s own integrity becomes an asset in `docs/security/threat-model.md` alongside the guards' integrity generally: a change that shrinks or empties it, or moves it under `template/`, is a full-gate review item, the same as a change to any other guard.
- A contributor with none of the three denylist locations present (now a rare case, since this repository's own commit is normally there) still is not blocked at commit, per ADR-0003's existing accepted consequence; the merge-text scan remains the backstop that does fail without one.

**Source:** issue "Commit a real denylist into staging, wire the merge-text scan to it by default, and hard-exclude it from the public snapshot"; the owner's words quoted above.
**Implemented in:** `.theforge-denylist`, `scripts/denylist-path.sh`, `scripts/check-denylist.sh`, `scripts/check-merge-text.sh`, `scripts/check-denylist-not-shipped.sh`, `scripts/test_denylist_not_shipped.py`, `.pre-commit-config.yaml`.
