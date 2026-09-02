# Artifact-First Project Template v3

This repository is a clean starting point for an artifact-first agentic software
project.

The core idea: progress is an artifact becoming more explicit, reviewable, or
correct. The scaffold starts with one current-state file, clear active
workspaces, proportional ceremony, and optional memory/tooling lanes.

## Start Here

1. Read `CLAUDE.md`.
2. Read `PROJECT_STATE.md`.
3. Read the role-specific prompt in `initialization/`.
4. Use only active workspaces listed in `PROJECT_STATE.md` unless a prompt
   activates more.
5. Keep changes narrow, documented, and reviewable.

Adopting this template in a new or existing repo? See
`docs/template_framework/migration_and_adoption.md`.

Human owner starting from scratch? See
`docs/template_framework/human_user_manual.md`.

## Optional Lanes

- `llloom` memory is optional. Default memory mode is `none`.
- `frutlups` loop tooling is optional. The template must work manually without
  it.
- The optional OKF/profile lane ships a versioned document-profile candidate
  (`0.1-rc.1`), a read-only `--profile` checker, a disposable navigation-view
  generator, and an opt-in authoring guide. It is off by default: legacy
  no-frontmatter Markdown stays the norm, and a project opts in per new artifact
  only if it wants profiled metadata. See
  `docs/template_framework/okf_authoring_and_migration.md`, with
  `docs/template_framework/architect_operating_card.md` as the routine architect
  quick start.
- Inactive workspaces are placeholders, not obligations.
- Workspace activation and profiles: see
  `docs/template_framework/project_profiles.md`. The default is the `base`
  profile; optional workspaces are activated explicitly, not automatically.

## Optional Roadmap Registers

Two optional roadmap headings help long-lived planning. Neither is required,
executable, or part of the ready frontier, and a project that uses neither works
exactly as before.

- `## Not Yet Specified` — a plausibly in-scope concern that is not yet sharp
  enough to become a reviewable slice. It is not a promise, a slice, or a
  blocker.
- `## Ruled Out` — an accepted project-level exclusion, recorded with its reason,
  date, and evidence. This is not a slice-local `Non-Goals` entry; those expire
  with their prompt.

A precise question or dependency owned outside the slice stays sharp in the
existing question/block lane — do not park it in `Not Yet Specified`. A new
exclusion that would narrow the project destination, and any resurrection of
ruled-out work, needs human approval.

Canonical contract: `docs/template_framework/method.md`.

Running autonomously? An empty frontier is never proof of completion: no ready
slice, with or without `Not Yet Specified` entries, does not mean the project is
done. Only explicit accepted completion evidence does. The future runtime
boundary is `docs/template_framework/frutlups_driver_boundary.md`.
No runner ships with this template.

## Initial Status

The repository starts as a blank project scaffold. Run the framework
initialization and project intake prompts before assigning implementation work.
