# Environment setup by ticket scope

The canonical recipe for setting up a build thread's environment, kept in the repo so it survives losing any working folder.
Every build thread's brief points here (`.agents/skills/build-thread-brief/SKILL.md`), and the Main Health thread's shared setup builds on it (`.agents/skills/watch-main-ci/SKILL.md`).
Don't keep a second copy anywhere else.
Fill in each scope at stage 0, once the stack is settled, and keep it checked against a passing full-suite run.

Run everything from a fresh `git worktree` cut from `origin/main` (`implement-with-merge` step 1).

## Every ticket

- Create the ticket's worktree with `python3 scripts/worktree_setup.py <branch-name>` (`implement-with-merge` step 1), which fetches `origin/main`, creates the worktree, and symlinks the installed, git-ignored dependency directories `scripts/worktree_shared_paths.txt` names, so the ticket starts without reinstalling them. Stage 0 fills that file in with this project's own shared-dependency paths. A ticket that changes a dependency pin passes `--no-shared-paths` and installs fresh in its own worktree instead of reusing the primary checkout's copy.
- The pre-commit hook is the one piece of setup every ticket needs, because it enforces the lint gate on whatever the commit touches: `pre-commit install --install-hooks`, after installing the pinned `pre-commit` from the project's dev requirements.
  Check it is installed with `test -f .git/hooks/pre-commit`; never commit with `--no-verify`. (`worktree_setup.py` reports, but never installs, a missing hook.)
- Beyond the hook, **set up only what the ticket's own scope needs**.
  A plain prose-only doc edit (no script to run, no regenerated file, no test) needs nothing beyond the standing pre-commit hook.
- The project's one-command setup is `pip install pre-commit==4.3.0 && pre-commit install --install-hooks`.
  Make it idempotent, quiet (short status lines, with full output written to a git-ignored log directory), and split by scope, so a build thread can install only what it needs.

## Scope (a): one component, no services

- What to install: (set at stage 0).
- Run only the test files near the change, with coverage limited to the touched modules, for example `pytest tests/test_<area>.py --cov=<package>.<module> --cov-report=term-missing`.
- Skip the full suite (`python3 -m unittest discover -s scripts -p 'test_*.py' && python3 -m unittest discover -s template/scripts -p 'test_*.py'`), integration suites and end-to-end tests unless the ticket says otherwise.

## Scope (b): needs local services (a database, a broker)

- What to start, and how: (set at stage 0).
- Shared services may be started, never stopped, and never mutated by hand (`.agents/skills/post-merge-review/SKILL.md`, "Operational safety rules").
- A destructive check (a schema mutation to prove a guard goes red) runs only against a private, throwaway instance (`.agents/skills/tdd/SKILL.md`, "Guard-removal verification").
- If a system package the service needs is missing from the container, install it, and say so in the PR rather than skipping the tests silently.

## Scope (c): end-to-end

- How to bring the stack up and down: (set at stage 0).
- Run only the spec files the change touches, and repeat one file several times to check for flakes rather than running the whole suite.
- Nothing in an end-to-end run may call a paid external service without the owner's explicit, per-run approval.

## Scope (d): generated docs

- What regenerates which built document, and the pinned tools it needs: (set at stage 0, if the project builds any documents).
