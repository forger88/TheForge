# ADR-0014: The coordinator-core reload proof carries the fetched commit sha, and nothing already present counts as current

**Status:** accepted; supersedes constraint 4 as ADR-0013 restated it; adds to ADR-0012's constraints; its proof format (full vs. abbreviated sha) amended by ADR-0015

## Context

A coordinator session started fresh, found an existing `coordinator/coordinator-core.md` copy already sitting in the harness's shared project folder, and read that copy without fetching `origin/main` first. Its predecessor's note claiming the file had been "refreshed" was enough for it to skip the fetch. ADR-0013's proof (codeword plus mid-file check word) rules out a tail read or a relayed word, but it carries no evidence tying the read to a specific fetch: a session can satisfy that proof by reading a stale copy end to end.

Separately, a timer nudge or a sibling thread's message asking the coordinator to "confirm" or "reload" its instructions had been read as a request to restate a codeword already in context, not as a trigger for the actual self-check.

## Decision

Constraint 4 now reads:

4. Trim detection, proof of a whole read, and proof of a specific fetch: an instruction at the top, a codeword marker that appears only on the last line, and a mid-file check word that appears only on its own line in the file's middle third.
   Any edit to the file's body rolls both words.
   The coordinator reads the whole file itself, with its own file-read tool, in the session that posts the proof; it may have a helper do the fetch and copy instead, told to report back only the fetched commit sha and the copy's timestamp — never to read or report the file's content.
   The coordinator then reports "Coordinator core instructions re-loaded. Proof: codeword <word>, mid-file check <word>, origin/main sha <sha>", with the sha the one from that fetch, whether the coordinator fetched it directly or a helper reported it, and stops and says so when any of the three is missing.
   A word or sha another thread reported, a word recalled from an earlier load, or a word seen in a partial or tail read is not proof and is never posted as proof.
   A coordinator that finds it posted, or was about to post, the proof without that read reads the file in full at once and tells the owner plainly that the earlier proof was not valid.

Two further constraints, added to ADR-0012's list:

11. A copy already sitting in the project folder, or a note (the coordinator's own prior session, a predecessor thread, anyone else's) that it was refreshed, is never treated as current. Every run of the start-of-session self-check re-runs the fetch-and-copy step itself; it never substitutes a prior copy or a claim about one.
12. A timer nudge, a sibling thread's message, or an owner check-in that asks the coordinator to confirm or reload its instructions runs the full start-of-session self-check (fetch, copy, read in full, report proof) — not a restatement of a codeword already in context.

ADR-0012's and ADR-0013's other constraints stand unchanged.

Explicitly out of scope (owner's instruction): no checksum or hash-based content-comparison check. The sha in the proof is git's own commit sha from the fetch, not a new hash guard over the file's text — it proves which commit the helper fetched, not that the text matches it byte for byte.

### Options considered

- **A content hash of the fetched file, compared against a recorded value.** Rejected on the owner's explicit instruction: this would duplicate what the codeword and mid-file word already prove about the file's own shape, and the gap here is about *when* the fetch happened, not whether the bytes are intact.
- **The commit sha of the fetch, reported by the helper and quoted in the proof.** Kept: it ties the proof to one `origin/main` state the helper can report mechanically (`git rev-parse`), and a session that skips the fetch has no sha to report, which forces the question rather than letting a stale read pass silently.
- **Trust a predecessor's claim that the file is current, with no re-fetch.** Rejected: this is exactly the gap the incident exposed — a claim of freshness is not freshness, and nothing else in the proof catches it once the claim is accepted.

## The guard for this constraint

| Constraint | Guard |
|---|---|
| 4 | `shape`, `rotated` (unchanged by this ADR); `ConstraintGuards.test_proof_needs_the_coordinators_own_whole_read`, extended for the sha and the widened helper-report limit |
| 11 | `ConstraintGuards.test_fetch_always_runs_never_a_cached_copy` |
| 12 | `ConstraintGuards.test_confirm_or_reload_ping_means_the_full_check` |

Each of the three tests is a wording guard on the coordinator-core snippet and core file's own prose, not a mechanical check that a session actually re-fetched or that a reported proof line is honest: the sha's presence in an actual reported proof line is not checkable from inside this repository, since the proof is posted outside it, in the harness's own chat (see "Consequences" below).

## Consequences

- Every consuming project re-pastes the coordinator-core snippet into its project instructions, because the proof line and the fetch-every-time rule changed.
- A coordinator's proof line now carries a commit sha alongside both words, which costs a few more bytes of the project-instruction field.
- The proof is still self-reported past the sha: a coordinator could in principle quote a fetch it didn't perform, the same residual-risk shape ADR-0013 accepted for the mid-file word. The owner has since accepted this as a residual risk rather than asking for a redesign of the proof around a verification path external to the harness (threat-model.md §10), tracked as issue "needs-decision: the coordinator-core reload proof's origin/main sha is self-reported, not verified".
