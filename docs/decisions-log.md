# Decisions log

Decisions that produced **no shipped code** and would otherwise exist only as a closed issue: a finding considered and declined, or an idea named but not yet designed.
Shipped-feature design lands in `docs/adr/` and `docs/design/` instead (`.forge/decisions-log.md`).

Closing an issue as `wontfix` or not planned, when it carries a real finding or proposal (not a duplicate, an invalid report or routine housekeeping), adds an entry here in the same PR or commit that closes it (SDLC-088).
Group sibling findings closed together into one entry.
This is a record, so entries narrate what was considered and why it was not done; newest entries go at the bottom.

## Entry shape

```md
### <Short title> (issue "<tracking issue title>")

**Considered:** <what was proposed or found, in a sentence or two>

**Declined because:** <the reason, citing an ADR or principle where one applies>

**Date:** <YYYY-MM-DD>
```

## Entries

### Script and guard-test the entrypoint migration (issue "Open design question: should the entrypoint migration be scripted and guard-tested, not hand-performed prose?")

**Considered:** the forge sync hardening feature's stage 8 architecture pass found that `forge-sync`'s "Entrypoint migration" is safety-critical yet hand-performed prose, checked only afterwards by `check_forge_entrypoint.py` on its result, and asked whether to replace it with a scripted, guard-tested migration function run inside the reviewed sync PR.

**Declined because:** the migration applies only to projects generated before `.forge/entrypoint.md` existed, a small set of pilot projects; every later project is expected to get the entrypoint line at generation (the owner was "almost certain"), so a migration script would be permanent, potentially fragile code for a one-off step that careful review of each pilot's sync PR already covers. The owner: "We don't need to carry potentially fragile scripting for the migration. The pilot repos can just get careful review. This is therefore won't fix."
This decision predates `.forge/code-shape-rules.md`'s "A safety-critical process step needs a tested mechanism, not just reviewed prose", which the same architecture pass prompted; the migration has not been re-decided under it.

**Date:** 2026-10-30

### Keep the entrypoint migration as a recorded departure from the tested-mechanism principle (issue "Does the \"won't fix\" on scripting the entrypoint migration stand under the new tested-mechanism principle?")

**Considered:** whether the won't-fix above still stands now that `.forge/code-shape-rules.md`'s "A safety-critical process step needs a tested mechanism, not just reviewed prose" (Default) has landed, since the entrypoint migration — a step that could delete the wrong lines — is exactly what that principle targets. Two options were put to the owner: confirm the won't-fix as a recorded departure from the Default, or reopen the migration question and script it with guard tests.

**Declined because:** the migration only ever runs against a small set of pilot projects generated before `.forge/entrypoint.md` existed, so careful review of each one's sync PR stays proportionate to the risk; scripting it would add permanent, fragile code for a step that runs only a handful of times. The owner confirmed this as the intended departure: "Option 1 is correct."

**Date:** 2026-11-01

### Leave the merge pin and the merge-time self-scan unfixed (issue "Merge-time scan residual gaps: unenforced head pin, self-scan from the PR's own branch, token in argv, encoding blind spots")

**Considered:** two residual gaps in `check-merge-text.sh`: nothing enforces the head-sha pin it tells the merger to use (a push after the final head re-check lands unscanned content, detected only afterwards by `--verify-merged --head-sha`), and the scan and every guard it runs execute from the merger's own checkout, so a merge run from the PR's own branch scans it with its own possibly weakened scripts. The other two gaps in the issue (token in `curl` argv, denylist encodings, locale folding and swallowed `grep` errors) were fixed.

**Declined because:** the owner decided against fixing them: "Gaps 1 and 2 are won't fix." They are recorded as accepted risks in `docs/security/threat-model.md` §10.

**Date:** 2026-11-01
