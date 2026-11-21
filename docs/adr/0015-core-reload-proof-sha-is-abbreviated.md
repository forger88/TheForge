# ADR-0015: The coordinator-core reload proof's sha is git's abbreviated form, not the full 40-character hash

**Status:** accepted; amends constraint 4's proof format as ADR-0014 stated it (ADR-0012's and ADR-0013's other constraints, and ADR-0014's other content, stand unchanged)

## Context

ADR-0014 fixed the proof line's shape as `"Coordinator core instructions re-loaded. Proof: codeword <word>, mid-file check <word>, origin/main sha <sha>"`, with `<sha>` being the fetch's full 40-character commit sha. The owner asked for the shorter, abbreviated form instead (git's own `--short` output, typically 7-10 characters): the full hash adds length to the proof line for no benefit the abbreviated form doesn't already give, since both still identify one `origin/main` state the helper fetched.

## Decision

Constraint 4's proof format now asks for and reports the **short** commit sha — git's abbreviated form (e.g. `git rev-parse --short`) — in place of the full hash, everywhere the proof line's wording names it: `.forge/coordinator-core.md` and `docs/agents/coordinator-core-snippet.md` (and their `template/` copies). The quoted proof string itself (`"...origin/main sha Z"`) is unchanged; only what `Z` resolves to changes.

This changes nothing else ADR-0014 decided: the sha still proves which commit the fetch used, not that the file's bytes are intact (that's still the codeword and mid-file word's job), and it is still self-reported, the residual risk ADR-0014 already recorded.

### Options considered

- **Keep the full 40-character sha.** Rejected on the owner's explicit instruction: no benefit over the abbreviated form for this proof's purpose.
- **Drop the sha from the proof entirely.** Not what was asked; ADR-0014's freshness guarantee still needs a sha tied to the fetch.

## Consequences

- Every consuming project re-pastes the coordinator-core snippet, because the proof line's underlying instruction (what `Z` means) changed, the same consequence ADR-0014 recorded for its own change.
- `git rev-parse --short` is not guaranteed a fixed length (git lengthens it to stay unambiguous), so a coordinator reporting it should use git's own output as given, not pad or truncate it itself.
