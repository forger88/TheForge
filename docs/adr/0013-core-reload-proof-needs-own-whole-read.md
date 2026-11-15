# ADR-0013: The coordinator-core reload proof needs the coordinator's own whole read

**Status:** accepted; supersedes ADR-0012's constraint 4; itself superseded by ADR-0014

## Context

ADR-0012's constraint 4 detects a truncated coordinator core with a codeword that appears only on the file's last line, which the coordinator quotes back to the owner as proof that it read the file.
That proof can be posted without the read it is meant to prove.
A helper that copies the file may report its last line, or the coordinator may read only the tail; either way the single end-of-file word is to hand without a whole read.
The file holds the rules the coordinator must personally follow, so a read by anyone else, or of only part of it, does not load them.

## Decision

Constraint 4 now reads:

4. Trim detection and proof of a whole read: an instruction at the top, a codeword marker that appears only on the last line, and a mid-file check word that appears only on its own line in the file's middle third.
   Any edit to the file's body rolls both words.
   The coordinator reads the whole file itself, with its own file-read tool, in the session that posts the proof; a helper may make the copy, told to copy only and report nothing but success or failure, but never reads it on the coordinator's behalf.
   The coordinator then reports "Coordinator core instructions re-loaded.
   Proof: codeword <word>, mid-file check <word>", and stops and says so when either word's line is missing.
   A word another thread reported, a word recalled from an earlier load, or a word seen in a partial or tail read is not proof and is never posted as proof.
   A coordinator that finds it posted, or was about to post, the proof without that read reads the file in full at once and tells the owner plainly that the earlier proof was not valid.

ADR-0012's other constraints stand unchanged.

### Options considered

- **Only tell the copy helper not to read or report the file.**
  Kept, as part of the decision: it removes the easiest route to a relayed codeword.
  Not enough alone: a helper can still volunteer content, the coordinator can still read only the tail, and a word recalled from an earlier load in the same session is still to hand.
- **Only strengthen the wording.**
  Kept, as the primary control: the rule has to say that the read is the coordinator's own and whole.
  Not enough alone: the single end-of-file word is exactly what a tail read or a helper's "last line" report supplies, so the wording had nothing checkable behind it.
- **A mid-file check word that rolls with the codeword.**
  Kept: a tail read, a head read and a helper's report of the last line all miss it, so quoting it is evidence that the middle of the file was read.
  It does not prove the coordinator read every line, and a helper told to report the whole file could still supply it; the wording forbids that.
- **A per-reload random value, written into the copy by the helper.**
  Rejected: the helper would know the value, which reopens the relay; and the committed file could no longer be checked mechanically.

## The guard for this constraint

| Constraint | Guard |
|---|---|
| 4 | `shape` (exactly one mid-file check word line, in the middle third, its word used nowhere else and differing from the codeword), `rotated` (both words roll when the body changes); `ShapeTests` and `RotatedProblemsTests`; `ConstraintGuards.test_proof_needs_the_coordinators_own_whole_read` for the own-whole-read wording in the snippet and the core |

## Consequences

- Every consuming project re-pastes the coordinator-core snippet into its project instructions, because the proof line and the reading rule changed.
- A coordinator's proof line now carries two words, which costs a few bytes of the project-instruction field.
- The proof is still self-reported: the mid-file word raises the cost of cheating but the rule, not the mechanism, is what forbids it.
- The mid-file word's own line carries a fixed label (`Mid-file check word:`), and the core file's top-of-file instruction announces that the label exists, so a bare `grep` for that label supplies the word with no read at all, more cheaply than the tail-read or relayed-report bypasses this ADR names. Since any label the shape guard can check mechanically can be grepped the same way, no mechanical change closes this gap; accepted as a residual risk (owner decision, 2026-11-02) rather than redesigning the proof around a non-fixed label.
