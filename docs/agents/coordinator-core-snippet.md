# Coordinator-core project-instruction snippet

The text between the two marker lines below is the source for the section of the harness's project instructions that makes the coordinator load `.forge/coordinator-core.md`.
Paste it into the project instructions verbatim, after the owner's own scope section and the coordinator-notes zone of standing owner decisions, which stay exactly as they are.
It carries the coordinator's rules by pointing at `.forge/coordinator-core.md`; nothing else in the project instructions is generated from this repository.
`python3 scripts/check_coordinator_core.py drift <file holding the live project instructions>` fails when the live field no longer contains this text; edit this file and re-paste, never the field alone.
TheForge's coordinator-core ADR records the problem this snippet and the coordinator core solve, and the constraints that must survive every edit to either.

<!-- coordinator-core-snippet:start -->
## Coordinator core (the coordinator loads it; no other thread does)

Only the coordinator session acts on this section.
Every other thread (build, design, review, Main Health, grilling, sweep, research) ignores it and keeps reading its instructions through the repository's `CLAUDE.md` and its `@.forge/entrypoint.md` import, exactly as before.

At the start of every coordinator session, again after a context compaction, and again whenever a timer, a sibling thread's message, or an owner check-in asks you to confirm or reload your instructions (that ask always means this whole check, never a restatement of a codeword already in context), before any other action:

1. Start the fetch-and-copy every time, whatever is already there: a copy already sitting in `coordinator/coordinator-core.md`, or a predecessor's note that it refreshed the file, never counts as current on its own. Fetch `origin/main` of the source repo (the one a standing owner decision names as the coordinator core source; otherwise the one on the owner's `Lead repo:` line, or the only repo) and copy its `.forge/coordinator-core.md` to `coordinator/coordinator-core.md` in the harness's shared project folder, replacing any older copy, noting the commit sha of that fetch; a helper may do this instead, told to report nothing but the fetched commit sha and the copy's timestamp.
2. Read that copy in full yourself, first line to last, with your own file-read tool, in this session, and run its "Start-of-session self-check"; the reading is never delegated.
3. If that repo has no such file, the file can't be copied, doesn't end with its `END OF COORDINATOR CORE` codeword line, or has no `Mid-file check word:` line, stop and tell the owner "Coordinator core instructions lost: <what failed>"; never work from a partial copy.
4. Otherwise tell the owner "Coordinator core instructions re-loaded. Proof: codeword XXXX, mid-file check YYYY, origin/main sha Z", with XXXX replaced by the codeword on that file's last line and YYYY by the word on its `Mid-file check word:` line, both as you read them yourself in step 2, and Z by the commit sha of step 1's fetch, whether you fetched it yourself or a helper reported it to you.

The proof is valid only from your own whole read in this session, of a copy fetched in this same check: a word or sha another thread reported, a word recalled from an earlier load, or a word seen in a partial or tail read is not proof, so never post it as proof. If you find you posted, or were about to post, the proof without that read, read the file in full at once and tell the owner plainly that the earlier proof was not valid.

If you are the coordinator and can't say what the current codeword is, reload the coordinator core now, before doing anything else.

The owner's scope section and the standing owner decisions in these project instructions override the coordinator core file where they differ, and no update removes or rewrites them.
<!-- coordinator-core-snippet:end -->
