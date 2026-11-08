# Third-party sources and licences

TheForge is MIT licensed, copyright forger88 (see [`LICENSE`](LICENSE)).
Much of what it ships is adapted from two upstream projects, credited here with their licence texts alongside under [`licenses/`](licenses/):

- [`licenses/MIT-mattpocock-skills.txt`](licenses/MIT-mattpocock-skills.txt): the MIT licence covering every skill adapted from `mattpocock/skills`.
- [`licenses/APACHE-2.0-impeccable.txt`](licenses/APACHE-2.0-impeccable.txt): the Apache License 2.0 covering `impeccable`.
- [`licenses/NOTICE-impeccable.md`](licenses/NOTICE-impeccable.md): `impeccable`'s own upstream NOTICE file, carried forward unmodified as Apache 2.0 section 4(d) requires.
  It records a nested attribution (`ehmo/platform-design-skills`, MIT) inside the Apache-licensed project.

The same credits, scoped to individual skills, live in `template/.agents/skills/THIRD_PARTY.md`, and every generated project receives that file and the licence texts under `.agents/skills/licenses/`, plus a short `NOTICE.md` at its root.

## `mattpocock/skills` (MIT)

Author: Matt Pocock.
Source: <https://github.com/mattpocock/skills>.
Licence: MIT.

TheForge's agent skills build on Matt Pocock's skills: the grilling interview, domain modelling, deep-module design vocabulary, writing for agents, test-driven development, bug diagnosis, two-axis code review, ticket slicing and triage.
Each adapted skill under `template/.agents/skills/` carries a one-line source note under its frontmatter naming the upstream path and commit, and says whether it was modified.
The per-skill table is in `template/.agents/skills/THIRD_PARTY.md`; the pinned upstream paths are recorded in `template/skills-lock.json`.

## `impeccable` (Apache License 2.0)

Author: Paul Bakaus.
Source: <https://github.com/pbakaus/impeccable>.
Licence: Apache License 2.0, plus the upstream NOTICE file.

The feature pipeline's user-interface checks (stages 3, 5 and 8) are run against the `impeccable` design skill.
A generated project installs it unmodified at the pinned upstream ref recorded in `template/skills-lock.json` (tag `skill-v4.7.0`); TheForge's own text only refers to it.
Any redistribution of `impeccable` must carry its NOTICE file forward, which is why `licenses/NOTICE-impeccable.md` ships with every generated project.

## Everything else

Everything else in this repository was written for TheForge and is covered by its MIT licence.
When a new third-party file is taken in (a skill, a vendored script, a font, a data file), it is credited here and in `template/.agents/skills/THIRD_PARTY.md`, with its licence text alongside, in the same change that adds it.
