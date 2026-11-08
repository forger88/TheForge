# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues on `forger88/TheForgeStaging`.
Use the `gh` CLI for all operations (or the hosting platform's MCP tools where `gh` has no working token).

Some agent harnesses refuse GitHub's GraphQL endpoint, which the `gh issue` and `gh pr` subcommands below use, so there those subcommands fail; use `gh api` REST routes or the MCP tools instead.
For example, `gh api repos/forger88/TheForgeStaging/issues/<number>` reads an issue, `.../issues/<number>/comments` its comments, `gh api --method POST repos/forger88/TheForgeStaging/issues -f title=... -F body=@<file>` creates one, `gh api --method POST repos/forger88/TheForgeStaging/issues/<number>/comments -F body=@<file>` comments on one, `gh api --method PATCH repos/forger88/TheForgeStaging/issues/<number> -f state=closed -f state_reason=completed` closes one, and `gh api "repos/forger88/TheForgeStaging/pulls?state=all"` lists PRs.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`.
  Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments with `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply or remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`, always with a reason (`--reason completed` or `--reason "not planned"`).
  Closing as not planned for a real finding or proposal also adds a `docs/decisions-log.md` entry in the same change (`.forge/decisions-log.md`).

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Standing trackers

These issues are created once by `scripts/bootstrap.py` and are never closed, whatever their sub-issue or comment count reads (`.forge/tickets-and-branches.md`):

| Tracker | Issue | Holds |
|---|---|---|
| Post-merge review tracker | #60 | Pending notes (a comment per merged PR not yet reviewed), the watermark and run log (`.agents/skills/post-merge-review/SKILL.md`) |
| Deferred-ideas epic | #341 | `future` ideas the owner raised and deferred |
| Hanging epic | #342 | `hanging` items: accepted risks and deliberately deferred gaps |
| Architecture-findings epic | #343 | `deferred-arch-finding` items from review passes |
| Local full-suite evidence tracker | #344 | One comment per full local-suite run, each naming the commit it covered and the result of each check (`.agents/skills/watch-main-ci/SKILL.md`, Routine 2) |

## Sub-issues and blocking edges

- **Sub-issue**: link a child to its parent with the sub-issues endpoint (`gh api --method POST repos/forger88/TheForgeStaging/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>`), where `<child-db-id>` is the child's numeric **database id** (`gh api repos/forger88/TheForgeStaging/issues/<n> --jq .id`), not its number.
- **Blocking**: use the platform's native issue dependencies (`gh api --method POST repos/forger88/TheForgeStaging/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`).
  `issue_dependencies_summary.blocked_by` reports open blockers only, which is the live gate.
  Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body.
  A ticket is unblocked when every blocker is closed.

## Pull requests as a triage surface

**PRs as a request surface: no.**
_(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments`, and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`, then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` or `NONE` (drop `OWNER`, `MEMBER` and `COLLABORATOR`).
- **Comment, label or close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#<n>` may be either: resolve with `gh pr view <n>` and fall back to `gh issue view <n>`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
