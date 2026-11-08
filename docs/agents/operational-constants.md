# Operational constants

An inventory of the project's limits, intervals and tuning values (byte caps, rate limits, timeouts, retry counts, page sizes, budgets), split into what is deploy-time configuration and what is a deliberately hardcoded invariant.
A PR that adds or changes such a value updates this file in the same PR (`.forge/ci-and-checks.md`, "Operational constants").

## Why this file exists

A limit scattered as a literal across the code is invisible to the operator who has to tune it and to the reviewer who has to check both sides of it (`self-review` part 4).
One inventory makes every value findable, says which ones an operator may change, and records the invariants that tie values together so an override can't silently break them.

## Configurable

Every value here has a typed configuration field, one committed default in the project's default configuration file, and (where the project supports them) an environment-variable override.
The default lives in exactly one place; code never carries a second fallback default of its own.

| Config path | Environment override | Default | What it bounds, and any invariant tying it to another value |
|---|---|---|---|
| `<section>.<key>` (example: `exports.max_rows`) | `<ENV_NAME>` (example: `EXPORTS_MAX_ROWS`) | `<value>` (example: `50000`) | One sentence on what it bounds and where it is enforced (example: rows per export file; the export writer stops and reports truncation above it). |

Where two values must hold a relation (one at most another, one fitting inside a transport limit set elsewhere), the configuration loader refuses to start when an override breaks it, and the row above says so.
Where a value must be mirrored somewhere the loader can't reach (a client-side copy, a container start command, a reverse proxy's body limit), the row names the mirror, and the drift risk is listed under "Known gaps" below.

## Hardcoded

Values that are protocol or domain invariants rather than tuning knobs, with the reason each stays out of configuration.

| Constant | Where | Value | Why it is not configurable |
|---|---|---|---|
| `<NAME>` (example: `INVOICE_NUMBER_WIDTH`) | `<module>` | `<value>` (example: `10`) | One sentence (example: fixed by the external format partners parse). |

## Known gaps

Each mirrored value an override can drift from, and each limit not yet enforced where it should be, with a tracking issue.

None yet.
