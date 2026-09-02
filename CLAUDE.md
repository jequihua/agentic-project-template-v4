# Project Instructions

## Purpose

This repository follows an artifact-first agentic development workflow.

The unit of progress is not "an agent completed a task." The unit of progress is
"an artifact advanced from one reviewable state to another."

## Read Order

For normal work, read only:

1. `PROJECT_STATE.md`
2. the active prompt or initialization prompt
3. the relevant workspace `CONTEXT.md`
4. the exact files named by the prompt

Do not re-read the whole repository unless the prompt asks for a broader review.

## Source Of Truth

When artifacts disagree, use this order:

1. latest explicit human instruction
2. `PROJECT_STATE.md`
3. latest accepted review or verdict
4. this `CLAUDE.md`
5. active prompt
6. active workspace `CONTEXT.md`
7. relevant contract artifacts
8. named `llloom` claims, only when memory mode is `llloom`
9. older prompts, reviews, and historical roadmaps

## Workspace Map

Core:
- `00_brief/` - objective, scope, constraints, success criteria
- `03_experiments/` - plans, runs, evidence, milestone notes
- `05_governance/` - decisions, risks, reviews, verdicts, current protocols
- `prompts/` - coding and review prompts
- `questions/` - durable questions when ownership or evidence is outside scope

Optional:
- `01_data/` - data sources, schema, quality, leakage, splits
- `02_analysis/` - analysis summaries, findings, hypotheses
- `04_delivery/` - reports, model cards, final deliverables
- `06_infra/` - environment, local/cloud/HPC execution, live validation gates
- `07_app/` - apps, dashboards, APIs
- `08_pkg/` - reusable package code
- `09_ops/` - runbooks, monitoring, long-running job patterns
- `90_legacy_review/` - existing-repo review before major changes
- `memory/` - optional memory posture notes, only active when enabled

Activation model: optional workspaces are activated explicitly, never
automatically. See `docs/template_framework/project_profiles.md`.

## Operating Rules

- Keep prompts narrow.
- State non-goals explicitly.
- Use `rg` or `rg --files` for search.
- Prefer updating existing artifacts over creating ad hoc notes.
- Keep `PROJECT_STATE.md` short and current.
- Keep `CONTEXT.md` files as lightweight orientation, not live state stores.
- Treat active prompt numbers, next actions, workspace lists, worktree contents,
  and other changing values as volatile state. Link to `PROJECT_STATE.md` or an
  index instead of copying them into durable analysis and reference artifacts.
- Before semantic review, run the artifact-integrity preflight on the exact
  artifacts in the slice when they cite repository paths or test identifiers.
- Review findings carry a P0-P3 disposition; only unresolved P0-P2 block a
  pass. The third same-invariant recurrence in a slice stops the corrective
  loop and routes to architect reassessment
  (`docs/template_framework/closure_convergence.md`).
- External repositories constrain a result only through a declared causal
  role; preservation-only drift never blocks
  (`docs/template_framework/external_repository_roles.md`).
- Do not treat llloom or frutlups as required unless `PROJECT_STATE.md` enables
  them.
- Do not commit secrets, credentials, raw private data, local venvs, caches, or
  local memory workspaces.

### Autonomous-Loop Seat Posture

When an autonomous driver operates this project, every dispatched seat
(coder, reviewer, architect) reads this file first. Three rules prevent
false environmental verdicts, host damage, and runaway enumeration:

- Interpreter posture: Python commands, including the project
  verification command, use the canonical interpreter named by the
  project's execution-environment record (`ENVIRONMENT.md`). When the
  host provides no bare `python` alias, that absence is deliberate
  explicit-interpreter discipline, not an environmental defect, and
  does not ground a `blocked` verdict.
- Stay-in-workspace covers actions, not only files: seats do not kill,
  restart, or reconfigure host processes, services, or system or global
  state. A seat that believes such an action is required reports it and
  stops instead of performing it.
- Bounded probes: use exact-path reads and `rg` on named files; never
  recursively enumerate local state, dependency caches, run stores, or
  virtual environments; write no snapshot or temp file outside the
  repository's declared local-state root; never persist a secret value or a
  resolved machine-local path. The governing runner's before/after fence is
  the workspace evidence; a seat does not build its own.

## Minimal Implementation Discipline

Default to the smallest correct useful change (YAGNI), not mechanically the
smallest diff. YAGNI rejects unsupported future machinery; it does not reject
structure earned by current evidence.

Before adding or generalizing:

- Check whether the work is needed now, already exists in the repository, or is
  covered by stdlib/native features or an already installed dependency.
- Prefer reuse, deletion, and small local changes over addition; a one-liner is
  fine when it fully solves the task.
- Avoid speculative abstractions, new dependencies, factories, interfaces,
  extension points, configuration, and scaffolding "for later."
- When alternatives meet the same requirements and safeguards, prefer fewer
  branches, states, concepts, and indirections, provided clarity and
  operability are not worse.

As code evolves:

- Duplication is cheaper than the wrong abstraction. Extraction earned by
  repeated concrete duplication—usually by the third occurrence—or by a shared
  invariant that must change together is not speculative. Prefer the smallest
  shared helper only when it reduces total complexity and preserves local
  clarity.
- Small corrections must not silently accrete complexity. If touched code has
  become materially harder to reason about or change safely, make a bounded
  in-scope simplification when necessary; otherwise record one named,
  evidence-backed simplification candidate without expanding the slice. A
  candidate is not authorized work.
- When tests share setup and assertion shape, prefer table-driven cases or
  `subTest`; keep separate tests when behavior, setup, or the failure story
  differs, and assert exact contract values individually.

Never trade away:

- correctness, security, trust-boundary validation, data-loss prevention,
  accessibility, explicit human requirements, or needed tests.

## Roles

The full loop — who writes what, where it lands, which index row it touches —
is one table: `docs/template_framework/method.md`, The Loop On One Page.

- Human owner: final stop/go, priorities, external authority.
- Architect/reviewer: roadmap, coding prompts, review prompts or final review
  criteria, verdicts, memory population, scope discipline.
- Coder: implementation, tests, self-report, optional draft review checklist.
- Tooling: optional state reading, prompt generation, validation, and indexes.

Roles are logical, not tied to a provider.

