# Frutlups Modes

frutlups is optional loop tooling for artifact-first development. The active mode
is set by `Frutlups mode` in `PROJECT_STATE.md`. The template must work fully
without frutlups — manual operation is first-class.

Current posture (install reference, guide, commands) lives in
`05_governance/current/frutlups_posture.md`. This is an optional lane and follows
the shared shape in `docs/template_framework/optional_lanes.md`.

## Modes

### manual (default posture)

No frutlups. Humans and agents move artifacts by hand: the architect/reviewer
writes coding prompts, the coder implements and writes self-reports, the coder
writes the matching review prompt after the self-report exists, and the reviewer
writes review reports and verdicts. Plain files are the loop.

### semi-manual

frutlups is used as a read-only compass and a prompt/verdict helper when the
human owner chooses it. Distinguish the two kinds of command:

- read-only (never writes): `status`, `next` (and `--json` on any command);
- write actions (each writes one artifact; preview with `--dry-run`):
  `make-coding-prompt`, `make-review-prompt`, `record-verdict`.

The human still decides. Recorded verdicts (`pass` / `needs_work` / `blocked` /
`override`) move the frontier; do not hand-edit roadmap or loop state to claim
progress.

### automated driver

A conforming external runner may coordinate the loop. The template ships none
and defines only the specification boundary — see
`docs/template_framework/frutlups_driver_boundary.md`. frutlups owns durable
state, validation, gates, deterministic prompts, and resumability; the runner
stays thin.

## Switching Mode

Changing `Frutlups mode` in `PROJECT_STATE.md` is the switch. When it changes:

- to `manual`: ignore frutlups entirely; run the loop with plain files.
- to `semi-manual`: enable frutlups per the init prompts, record posture in
  `frutlups_posture.md`, use read-only commands for orientation and write
  commands (with `--dry-run`) for prompts and verdicts.
- to `automated driver`: only with a conforming external runner installed and
  its operator manual as the runner authority; without one, treat it as
  `semi-manual` plus the boundary spec.

## Rules (all modes)

- manual operation must always remain possible;
- `status` / `next` only read repository state; they never invent it;
- recorded verdicts, not manual roadmap edits, move the frontier;
- manual and automated loops share one commit boundary — an accepted milestone
  verdict (see `docs/template_framework/method.md` Commit Discipline). In manual
  operation the architect/reviewer commits accepted milestones by default; a
  runner commits only when explicitly authorized and must run the same closure
  checklist;
- a runner may report pull-request-ready but must not open PRs by default; the
  human owner may request a PR link at any point;
- frutlups, provider credentials, CI, and llloom are never required for the
  scaffold or its tests.
