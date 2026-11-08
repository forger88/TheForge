# Why the review architecture is shaped this way

This project reviews every change in layers, each catching a class of problem the others structurally cannot:

1. **Standards and Spec at merge**: two clean-context sub-agents compare the diff with the repo's documented conventions and with the ticket and requirements.
2. **Self-review at merge**: the builder searches the rest of the codebase for everything the diff could break.
3. **The post-merge review**: review-tier agents re-review every merged PR since a watermark, across PRs, including a security axis.
4. **The architecture pass**: a design-tier agent judges a whole feature's seams once all its slices have merged.

The question of whether some of these could be combined to save a pass comes up periodically.
The answer is no, for a different reason per pairing.

## Standards and Spec are split to prevent masking

A change can pass one axis and fail the other: it can follow every convention while implementing the wrong thing, or do exactly what the ticket asked while breaking the project's conventions.
Running the axes as separate parallel sub-agents stops one axis's clean result from masking the other's finding.
A single reviewer doing both reintroduces exactly the reranking the split exists to prevent.

## Self-review asks a different question

Standards and Spec compare a bounded diff against a fixed document.
Self-review's checks (other callers, other builders of a changed data shape, reuse versus recreation, both sides of a new cap, a fix covering its whole class, a gate still running on what it enforces) are codebase-wide searches triggered by what the diff touches.
They need search breadth tied to intent: knowing exactly what the diff touched, well enough to know where to grep.
The implementing thread already has that, and a fresh sub-agent would first have to rediscover it, so self-review is run by the builder, and its lack of independence is deliberate.

## The post-merge review exists because a per-PR review cannot see everything

Some bugs only exist once several changes are present together: two routes that each compute the same value their own way and disagree, a migration that is safe alone and unsafe after another, a resource that leaks only under real concurrent load.
No per-PR review sees them, however thorough, because the other half of the bug is not in its diff.
Batching the second review after merge also lets one pass cover many PRs, and lets merges flow without waiting on a second reviewer.

## What the trade costs

Merging on the builder's own review plus focused tests means `main` can run red between a merge and the next full pass.
The price is the gap until detection plus the time the fix takes, and it is accepted knowingly in exchange for throughput and fewer long-lived branches.
The `green` branch (`.forge/main-health-patterns.md`) is the mitigation for anyone who needs a verified commit.

## Net

Do not collapse any of these layers.
The saving from combining them is small, and the risk is shipping again the bugs each layer was added to catch.
