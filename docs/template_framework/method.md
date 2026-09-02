# Artifact-First Method

The template is a repository-native operating method for agentic software work.

Core principle:

> Progress is an artifact becoming more explicit, reviewable, or correct.

The method prefers:

- visible files over hidden chat state;
- narrow slices over broad autonomy;
- explicit non-goals over impressive scope creep;
- the smallest correct useful change (YAGNI) over speculative architecture or a
  mechanically smallest diff, keeping structure earned by present evidence;
- findings-first review over generic approval;
- human stop/go over fully delegated ownership.

## Default Loop

1. Architect/reviewer prepares a narrow coding prompt.
2. Coder implements, verifies, and writes a self-report.
3. A review prompt or review checklist is prepared.
4. Reviewer checks code, artifacts, claims, and scope.
5. Verdict is recorded.
6. `PROJECT_STATE.md` and relevant indexes are updated.
7. Human owner decides whether to proceed, pause, or redirect.

Reviews are numbered rounds with an escalation ladder; findings carry P0-P3
dispositions; and a reviewer may not widen a slice's acceptance envelope. The
canonical convergence contract is
`docs/template_framework/closure_convergence.md`: the third same-invariant
recurrence routes to architect reassessment with human awareness, not another
corrective prompt. Identity-bound deliveries (frozen handoffs, release
candidates, migrations) additionally follow
`docs/template_framework/candidate_review_acceptance.md`.

### The Loop On One Page

Who writes what, where it lands, and which routing row it touches:

| Step | Actor | Artifact | Lands in | Routing row |
| --- | --- | --- | --- | --- |
| 1 | architect/reviewer | coding prompt | `prompts/for_coding_agent/` | `prompts/INDEX.md` |
| 2 | coder | implementation and tests | paths named by the prompt | none |
| 3 | coder | self-report (schema: `prompts/templates/self_report.md`) | the milestone folder under `05_governance/reviews/` | `05_governance/reviews/INDEX.md` |
| 4 | architect/reviewer | review prompt (with `round:`) | `prompts/for_review_agent/` | `prompts/INDEX.md` |
| 5 | reviewer | review report ending in one verdict line | the milestone folder under `05_governance/reviews/` | `05_governance/reviews/INDEX.md` (Round, Verdict) |
| 6 | architect/reviewer | `PROJECT_STATE.md` and reached-cadence indexes | repo root | cadence table below |
| 7 | human owner | stop / go / redirect | — | — |

Default conventions (a project may override them once, in a recorded
decision; until then, these hold):

- one flat number sequence across all prompts in `prompts/INDEX.md`; a
  self-report or review report reuses its governing prompt's number plus the
  slice and round in its filename;
- `prompts/INDEX.md` status values: `draft`, `ready`, `delivered`,
  `superseded`; whoever records a verdict also flips the reviewed prompt's
  row to `delivered`;
- review reports and fast-close correction records live in the milestone
  folder under `05_governance/reviews/`; the verdict is the report's final
  line plus the reviews-index cell — no separate verdict file unless a
  project opts into one;
- a human-owner message that carries authority (a ruling, a reported defect)
  is transcribed to a numbered, dated note under
  `05_governance/human_owner_notes/` before work relies on it.

A `pass` verdict closes the implementation transition; whether the slice's
objective was achieved is the review's separate closure record, and a
milestone completes only on explicit accepted completion evidence, never on a
pass at the last slice (`docs/template_framework/closure_convergence.md`).

### Closure Routing Ownership And Cadence

Step 6 updates only the surfaces whose cadence has been reached; do not mirror
one accepted change into every routing file.

| Surface | Default ownership and update cadence |
| --- | --- |
| `PROJECT_STATE.md` | update when accepted current truth changes |
| `prompts/INDEX.md` | update when a prompt is created or reaches terminal status |
| `05_governance/reviews/INDEX.md` | append/update when review evidence and a verdict exist |
| `MILESTONES.md` | update when a milestone is created or closes, not for every slice transition |
| `05_governance/review_log.md` | no routine duplicate row; pointer-only compatibility surface |

`05_governance/reviews/INDEX.md` is the canonical review routing surface. It
is also a machine-readable convention: autonomous runners may reconcile its
rows against project evidence mechanically. Keep one row per review round in
the documented column shape, and cite every artifact as a repo-relative,
backtick-quoted path — a citation that is not a backtick-quoted repo-relative
path is invisible to mechanical reconciliation and weakens the project's
autonomous reviewability. Manual-first projects that never run an autonomous
runner are unaffected; nothing else about the INDEX changes.

The INDEX additionally operates in a declared mode, in the same spirit as
Memory mode and Frutlups mode. `human-ledger` (the default): a person
maintains the rows and everything above applies as written. `no-ledger`: the
project is operated by an autonomous runner, nobody maintains rows, the file
legitimately remains at its shipped header-only state, and mechanical
reconciliation treats any row that appears as an anomaly rather than
bookkeeping. The declaration lives in the operating tool's project-local
configuration (for frutlups-drive, `index_mode` in the committed drive
policy); manual-first projects declare nothing and are unaffected. The
scaffold ships the INDEX header-only; the first data row is always project
history, never template content.

`05_governance/review_log.md` remains only as a pointer-only compatibility
artifact and takes no routine review rows.

## Roadmap Uncertainty And Project Exclusions

Long-lived planning needs two words the loop above does not supply. Two optional
level-2 roadmap headings supply them: `## Not Yet Specified` for work inside the
destination that is not yet sharp, and `## Ruled Out` for work deliberately kept
outside it. Both registers are optional and manual-first — a project that uses
neither is fully valid — and neither adds a workspace, artifact type, dependency,
required `PROJECT_STATE.md` field, or tool.

Admit each concern exactly once:

- sharp and actionable: write a narrow slice;
- sharp but blocked on external evidence, ownership, or authority: record a
  question or block (`05_governance/current/question_policy.md`) — the work
  stays sharp, and a known blocker is never hidden as fog;
- in scope but not yet sharp enough to state a reviewable question or artifact
  transition: record a `Not Yet Specified` entry;
- outside the accepted destination: record a `Ruled Out` entry, subject to the
  authority rule below.

`Ruled Out` is a project-level terminal register. A prompt's `Non-Goals` are
slice-local fences that expire with their slice and may become valid work later;
they are never promoted into `Ruled Out` automatically.

Entries in both registers are ordinary top-level Markdown bullets. Neither
register is an executable slice, and neither enters the frontier.

Reconsider entries at an accepted slice or pass boundary, or during an explicit
architect planning pass — not on every loop action. At such a boundary a
`Not Yet Specified` entry may be left unchanged, sharpened into a proposed slice,
split, merged, or removed with a brief reviewed explanation.

The architect may record an exclusion that the accepted brief or an accepted
owner decision already establishes, and the reviewer checks that citation. A
proposed entry that would narrow or redraw the destination needs human approval
before it becomes an accepted exclusion. Removing or resurrecting an accepted
`Ruled Out` entry is always a Level 4, human-aware scope change.

An empty frontier is not completion evidence. Zero ready slices — with zero
`Not Yet Specified` entries beside them — never establish completion; only
explicit accepted closure evidence does.

Use either section only when it carries information:

```markdown
## Not Yet Specified

- Packaging hardening after the first consumer run — revisit when the run report
  shows which install and upgrade paths actually fail.

## Ruled Out

- Hosted multi-tenant control plane — excluded because the accepted brief
  requires a local-only tool; 2026-08-01; evidence:
  `00_brief/problem_statement.md`.
```

## Lightweight Context

`CONTEXT.md` files orient agents to folders. They are not the live project state.
The live state belongs in `PROJECT_STATE.md`.

## Commit Discipline

Git records coherent accepted states, not every conversational step. This is the
canonical commit rule; other surfaces reference it.

- Ordinary prompt passes do not imply a commit.
- After a positive review/verdict closes a milestone, the architect/reviewer agent
  normally performs Milestone Commit Closure (below) and creates the milestone
  commit. The architect/reviewer is the default committer at milestone closure.
- Coders do not commit during implementation unless explicitly assigned.
- Automation does not commit unless explicitly configured and authorized.
- Small post-milestone refinements may be batched, unless they change important
  rails (contracts, public API, state model) — those commit with their milestone.
- The human owner may pause, redirect, or override commit timing.
- Before risky experimentation, commit the last known-good state first.
- Pull request policy is separate and human-controlled (below).

### Milestone Commit Closure

When a milestone commit is being made (normally by the architect/reviewer at an
accepted closure, or by an explicitly authorized workflow), run this checklist
before staging:

1. Run validation, or record why it cannot be run.
2. Re-acknowledge open accepted-limitation and waiver entries with the human
   owner; a release-objective upgrade re-opens their materiality
   (`05_governance/current/review_protocol.md`).
3. Inspect `git status --short`.
4. Update `.gitignore` if generated junk or local state appears.
5. Optional local footprint glance: when tests, runs, data, memory, legacy
   review, or package builds may have produced local state, run
   `git status --short --ignored` or `python scripts/local_state_audit.py
   --root .`. Delete only clearly rebuildable caches/build output (for example
   `python scripts/local_cleanup.py --apply`), or record retained local roots in
   `LOCAL_STATE_NOT_COMMITTED.md`. This glance is optional and never a blocker.
6. Confirm no credentials, raw private data, caches, test output, local state, or
   unrelated files are being committed.
7. Stage only the accepted milestone files.
8. Inspect `git diff --cached --stat` (and `git diff --cached --name-only` when
   useful).
9. Commit with a clear milestone message.

### Pull Requests

`commit-ready` and `pull-request-ready` are different signals.

- Milestone commits may stack on a branch until a roadmap, release candidate, or
  human-defined work package closes.
- The suggested PR boundary is a completed roadmap, release candidate, or
  human-defined work package.
- The human owner may request a PR link at any point, regardless of that boundary.
- Agents and runners may report pull-request-ready, but must not open PRs by
  default.
- Opening a PR requires explicit human request or an explicitly authorized
  workflow.

## Adopting The Method

To adopt this method in a new or existing repository, follow
`docs/template_framework/migration_and_adoption.md`. Adoption is additive and
history-preserving by default.
