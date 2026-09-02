# Frutlups Driver Boundary

Status: specification boundary only. No runner is implemented in this template;
conforming external runners exist (frutlups-drive is the first published one)
and any runner honoring this boundary may sit in its place.

A conforming thin runner MAY:

- consume `frutlups status --json`;
- route generated prompt files to configured sinks;
- wait for expected artifacts to appear;
- record verdicts only from a valid review report;
- report `commit-ready` after an accepted verdict / milestone closure;
- report `pull-request-ready` at a suggested PR boundary (completed roadmap,
  release candidate, or human-defined work package);
- resume from durable repository state.

The runner MUST NOT commit or open pull requests by default. Auto-commit and PR
creation require explicit configuration and human authorization, and a stop
condition must never be bypassed to create a commit or open a PR (boundaries:
`docs/template_framework/method.md` Commit Discipline). The human owner may
request a PR link at any point.

In manual agent operation the architect/reviewer is the default committer at
milestone closure; this boundary governs only a runner. A runner authorized to
commit MUST perform the same Milestone Commit Closure checks (`.gitignore`
hygiene, `git status`/staged-diff review, staging only accepted milestone
changes) and stop if junk, secrets, local state, invalid reports, or unrelated
changes are detected.

The runner MUST stop cleanly on:

- `blocked` verdict;
- `override` required;
- invalid self-report;
- invalid review report;
- an `invalid` or unknown planning-frontier state (below);
- memory gate failure;
- environment gate failure.

## Planning-Frontier Outcomes

This template implements no parser, schema, state machine, or runner for what
follows; it records only the boundary a future frutlups contract and a future
runner must honor. The runner consumes versioned frutlups planning state and
refuses any contract version it does not implement.

Each typed outcome binds to exactly one runner behavior:

- `ready`: continue the normal declared loop;
- `needs_specification`: dispatch one bounded architect planning turn, then
  recompute durable state;
- `blocked`: stop and report the cited block and its owner;
- `complete`: stop successfully only with explicit accepted completion evidence;
- `invalid` or unknown: stop fail-closed with diagnostics.

The runner MUST also observe:

- the absence of a ready slice never proves completion; neither zero slices, nor
  zero slices together with zero `Not Yet Specified` entries, is completion
  evidence;
- it does not parse roadmap prose, graduate `Not Yet Specified` entries, edit
  roadmaps, choose exclusions, or decide completion;
- it may dispatch an architect only when the typed state names that actor;
- retry exhaustion or a turn with no durable progress is a stopped run, never
  completion;
- all existing human gates, commit/PR restrictions, durable resumption, and
  thin-runner boundaries remain intact.

The runner stays thin on purpose: frutlups owns durable state, validation, gates,
deterministic prompts, and resumability. The runner only coordinates sinks and
waits. It must never hand-edit loop state, invent verdicts, or bypass a gate.
