# A bug fix starts from a red loop

A bug ticket, a Main Health finding or a reported failure is fixed the way `.agents/skills/diagnosing-bugs/SKILL.md` says.
First comes one command, run locally, that goes red on the reported symptom.
Then come hypotheses, then the fix, then the same command going green.
No red-capable command, no hypothesis.

The fix PR's `Evidence:` line is that command, shown red before the fix and green after, plus the other members of the bug's class the fix checked, by name, with the source that list came from (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line").
A bug brief names this rule.
A brief that cannot name a seam for the loop says so, and that gap is itself a finding to record.

## The repro becomes the regression test

The repro that drove the red loop becomes the fix's regression test, never a deleted scratch file.
When a brief hands over a standalone repro script, do not discard it once the fix is green.
Move it into the matching permanent test file, adapted to that suite's conventions, as the regression test, and do not commit the standalone repro file itself.
A fix whose only proof was a repro file deleted when the ticket closed leaves no regression test behind at all.

## Fix the class, not the line

A bug is usually an instance of a pattern.
Before calling the fix done, grep the whole relevant tree, test files included, for the same shape, and fix every instance (`.forge/review-gate.md`, "Fix the class of bug, not just the flagged line").
