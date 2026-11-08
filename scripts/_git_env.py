"""Root-only counterpart of template/scripts/_git_subprocess.py's
`clean_git_env`, for this repository's own (non-shipped) test fixtures.

Kept as a separate file rather than imported from `template/`: that tree is
shipped (and partly Jinja-templated) to consumers, while `scripts/` is
TheForge's own tooling with a different lifecycle. Same hazard, same fix,
duplicated on purpose rather than coupling the two.

When this hook runs as a `git commit` pre-commit hook, git sets
GIT_DIR/GIT_INDEX_FILE (and, under a core.hooksPath override, the
GIT_CONFIG_* family) in the hook's own environment, and they propagate to
every subprocess the hook spawns -- including `git init` in a throwaway
test-fixture repo, or `copier copy`'s own internal git calls when rendering
a fresh project. Left unstripped, a nested call inherits the leaked
variables and operates on this real repository instead of its own
throwaway one, corrupting its index (found live: a `test_denylist_not_shipped.py`
run via `git commit`'s pre-commit hook unstaged an unrelated, already-staged
commit's changes by doing exactly this to this repository's real index).
"""

from __future__ import annotations

import os

_DANGEROUS_GIT_ENV_NAMES = frozenset(
    (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
    )
)
_DANGEROUS_GIT_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")


def clean_git_env() -> dict[str, str]:
    """A copy of this process's environment with every repository-identity-
    redirecting GIT_* variable removed, so a nested git call (or a tool like
    `copier` that shells out to git) is never silently redirected at this
    real repository by a leaked pre-commit-hook environment."""
    return {
        name: value
        for name, value in os.environ.items()
        if name not in _DANGEROUS_GIT_ENV_NAMES and not name.startswith(_DANGEROUS_GIT_ENV_PREFIXES)
    }
