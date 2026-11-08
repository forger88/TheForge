# Rule strengths: Never and Default

Every rule in this project's agent instructions, its forge rule files and the skills they point into has one of two strengths.
A new rule says which strength it has.

## Never

A Never rule is a hard line.
No brief and no thread overrides it on its own judgement.
Only the repo owner can change or waive a Never rule, and the owner's waiver is recorded where the rule would otherwise apply.

## Default

A Default rule is the normal case.
A specific brief or the repo owner can call for something different when the work genuinely needs it.
A thread departing from a Default says so explicitly, in the PR body or wherever it would normally record the rule it is following, and never departs silently.
A silent departure is a review finding, even when the departure itself was reasonable.

## Unmarked rules

A rule with no strength marked is a Default, unless its own wording is absolute ("never", "only the owner changes it", and similar).
An unmarked rule is not meant to read as weaker than a marked one.

## Where the owner's decisions sit above these rules

The numbered `SDLC-` statements in `docs/software-development-lifecycle.md` sit above every rule here.
Where a rule appears to disagree with a statement, the statement wins until the owner decides otherwise, and the agent that notices flags it rather than resolving it (see `.forge/process-and-evidence.md`).
