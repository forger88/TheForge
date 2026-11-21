# Why the review architecture is shaped this way

Every change is reviewed in layers, each catching a class of problem the others structurally cannot:

1. **Standards and Spec at merge**: two clean-context sub-agents compare the diff with the repo's documented conventions and with the ticket and requirements.
2. **Self-review at merge**: the builder searches the rest of the codebase for everything the diff could break.
3. **The post-merge review**: review-tier agents re-review every merged PR since a watermark, across PRs, including a security axis.
4. **The architecture pass**: a design-tier agent judges a whole feature's seams once all its slices have merged.

Combining any of these to save a pass is periodically proposed, and the answer is no, for a different reason per pairing.

## Standards and Spec are split to prevent masking

A change can follow every convention while implementing the wrong thing, or do exactly what the ticket asked while breaking conventions.
Separate parallel sub-agents stop one axis's clean result masking the other's finding; one reviewer doing both reintroduces that reranking.

## Self-review asks a different question

Standards and Spec compare a bounded diff against a fixed document.
Self-review's checks (other callers, other builders of a changed data shape, reuse versus recreation, both sides of a new cap, a fix covering its whole class, a gate still running on what it enforces) are codebase-wide searches that need to know exactly what the diff touched in order to know where to grep.
The builder already knows that and a fresh sub-agent would have to rediscover it, so the builder runs self-review, and its lack of independence is deliberate.

## The post-merge review exists because a per-PR review cannot see everything

Some bugs exist only when several changes are present together: two routes computing the same value differently, a migration safe alone but unsafe after another, a resource that leaks only under real concurrent load.
No per-PR review sees them, because the other half is not in its diff.
Batching the second review after merge also lets one pass cover many PRs, and lets merges flow without waiting on a second reviewer.

## What the trade costs

Merging on the builder's own review plus focused tests means `main` can run red between a merge and the next full pass, for the time until detection plus the fix.
That is accepted knowingly for throughput and fewer long-lived branches, and the `green` branch (`.forge/main-health-patterns.md`) is the mitigation for anyone who needs a verified commit.

## Net

Do not collapse any of these layers: the saving is small, and the risk is shipping again the bugs each layer was added to catch.
