# A bug fix starts from a red loop

A bug ticket, a Main Health finding or a reported failure is fixed as `.agents/skills/diagnosing-bugs/SKILL.md` says: first one local command that goes red on the reported symptom, then hypotheses, then the fix, then the same command green.
No red-capable command, no hypothesis.

The fix PR's `Evidence:` line is that command, red before and green after, plus the other members of the bug's class the fix checked, by name, with the source of that list (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line").
A bug brief names this rule, and a brief that cannot name a seam for the loop says so, which is itself a finding to record.

## The repro becomes the regression test

The repro that drove the red loop becomes the fix's regression test, never a deleted scratch file.
A standalone repro script handed over in a brief is moved into the matching permanent test file, adapted to that suite's conventions; the standalone file itself is not committed.
A fix whose only proof was a deleted repro file leaves no regression test at all.

## Fix the class, not the line

A bug is usually an instance of a pattern: before calling the fix done, grep the whole relevant tree, tests included, for the same shape and fix every instance (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line").
