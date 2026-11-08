# The decisions log

`docs/decisions-log.md` records decisions that produce no shipped code and would otherwise exist only as a closed issue.
It holds two kinds of entry: a finding or proposal considered and declined (closed `wontfix` or as not planned), and an idea named but not yet designed.
Its job is to stop a settled question from being reopened by someone who cannot see the closed issue.

Shipped-feature design lands in `docs/adr/` and `docs/design/` instead.
The log is not a mirror of the issue tracker: it does not cover shipped work, the post-merge review's run archive, or ordinary bug fixes.

## When to add an entry

Closing an issue `wontfix` or as not planned, when it carries a real finding or proposal, adds a few lines to `docs/decisions-log.md` in the same PR or commit that closes it.
A duplicate, an invalid report, or routine housekeeping needs no entry.
The entry says what was considered, why it was not done, and the issue number.
Sibling findings closed together share one entry.
Writing the entry is part of closing the issue, not a follow-up.

## Shape of an entry

Each entry is a short dated section, newest first, with a heading naming the decision, two to five lines on what was considered and why it was declined, and the issue number.
The log is a record, so unlike the project's other docs it narrates what was decided and why.
