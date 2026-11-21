# Rule strengths: Never and Default

Every rule in this project's agent instructions, forge rule files and skills is either Never or Default, and a new rule says which.

## Never

A Never rule is a hard line that no brief or thread overrides on its own judgement.
Only the repo owner changes or waives one, and a waiver is recorded where the rule would otherwise apply.

## Default

A Default rule is the normal case, which a specific brief or the owner can depart from when the work genuinely needs it.
A thread departing from a Default says so explicitly, in the PR body or wherever it would normally record the rule it follows, and never departs silently.
A silent departure is a review finding, even when the departure was reasonable.

## Unmarked rules

An unmarked rule is a Default, not a weaker one, unless its own wording is absolute ("never", "only the owner changes it", and similar).

## Where the owner's decisions sit above these rules

The numbered `SDLC-` statements in `docs/software-development-lifecycle.md` sit above every rule here.
Where a rule appears to disagree with one, the statement wins until the owner decides, and the agent that notices flags it rather than resolving it (`.forge/process-and-evidence.md`).
