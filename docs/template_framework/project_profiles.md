# Project Profiles And Workspace Activation

The template uses **one base profile plus explicit toggles**, not a fixed set of
named products. This keeps the default surface small while letting a project turn
on exactly the workspaces it needs.

The goal is that a coding agent always knows which folders matter for the current
project by reading `PROJECT_STATE.md`, without scanning workspaces that the
project never uses.

## Default Profile: `base`

A new project starts in the `base` profile. Active workspaces:

- `00_brief`
- `03_experiments`
- `05_governance`
- `prompts`
- `questions`

Everything else is present but inactive. The canonical folder map (core vs
optional) lives in `CLAUDE.md`; this doc owns the activation rules, not a second
copy of the map.

## Toggles (orthogonal — combine freely with the base)

Toggles are independent. A project can enable any combination.

- **package**: activate `08_pkg` (add `architecture_contract.md`,
  `public_api_contract.md`, `testing_strategy.md` as needed).
- **data / analysis / delivery**: activate `01_data`, `02_analysis`,
  `04_delivery` for data-science or experiment-heavy work.
- **infra**: activate `06_infra` for environment, live-validation, or
  blocker-resolution work.
- **app**: activate `07_app` for an app, dashboard, or API surface.
- **ops**: activate `09_ops` for recurring operations or long-running jobs.
- **legacy / existing-repo**: activate `90_legacy_review` before major changes
  to an existing codebase.
- **memory**: set memory mode to `lightweight` or `llloom` (activates `memory/`
  and the memory posture). Optional and read-only by default.

Common shapes are just named combinations, not rigid categories — for example a
"software package" project is `base + package`, a "data-science" project is
`base + data/analysis/delivery`, a "full system" project is
`base + package + infra + app + ops`. Name the shape informally in
`PROJECT_STATE.md`; do not treat these names as a fixed enum.

## How To Activate An Optional Workspace

Activation is explicit and manual. To activate a workspace:

1. Move it from `Optional inactive workspaces` to `Active workspaces` in
   `PROJECT_STATE.md`.
2. Flip its `CONTEXT.md` `Status:` line from `inactive ...` to `active ...`.
3. Record the change at slice/pass closure, per the update cadence in
   `project_state_contract.md`.

To deactivate, reverse the steps.

## Inactive Workspace `CONTEXT.md` Files

Keep inactive workspaces and keep their `CONTEXT.md` files. Each inactive
`CONTEXT.md` must mark `Status: inactive ...`. They are useful as **scope
markers**: an inactive `07_app/CONTEXT.md` reminds an agent not to invent an app,
and an inactive `09_ops` is ready the day long-running jobs appear.

A project may delete an optional workspace it is certain it will never use, but
deletion is a deliberate human decision, not a default and not automated.

## What Must Not Happen Automatically

- No automatic activation of optional workspaces.
- No script or generator that creates, deletes, or rewrites workspaces by profile
  (the v1 destructive prune scripts are not part of this model).
- No silent edits to `PROJECT_STATE.md` workspace lists without recording the
  change at closure.

If a project later wants profile tooling, that is a separate, explicitly approved
decision — the markdown model above must work without it.
