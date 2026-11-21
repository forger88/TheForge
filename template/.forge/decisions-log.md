# The decisions log

`docs/decisions-log.md` records decisions that produce no shipped code and would otherwise exist only as a closed issue: a finding or proposal declined (closed `wontfix` or not planned), or an idea named but not yet designed.
It stops a settled question being reopened by someone who cannot see the closed issue.

Shipped-feature design goes in `docs/adr/` and `docs/design/` instead.
The log does not mirror the tracker: no shipped work, post-merge review run archive or ordinary bug fixes.

## When to add an entry

Closing an issue `wontfix` or not planned, when it carries a real finding or proposal, adds an entry in the same PR or commit that closes it, not as a follow-up.
A duplicate, an invalid report or routine housekeeping needs none.
The entry says what was considered, why it was not done, and the issue number; sibling findings closed together share one entry.

## Shape of an entry

Each entry is a short dated section, newest first: a heading naming the decision, two to five lines on what was considered and why it was declined, and the issue number.
As a record, the log narrates what was decided and why, unlike the project's other docs.
