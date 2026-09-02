# PROJECT_STATE Contract

`PROJECT_STATE.md` is the single canonical surface for live project state. It is
short, current, and read first. Other artifacts link to it instead of restating
live state.

## Required Fields

`PROJECT_STATE.md` must contain these fields (label followed by a value):

- `Status`
- `Template version`
- `Project profile`
- `Active workspaces`
- `Optional inactive workspaces`
- `Current objective`
- `Current loop mode`
- `Current ceremony level`
- `Memory mode`
- `Frutlups mode`
- `Latest accepted review`
- `Next expected action`
- `Validation command`
- `Local-state warning`

A scaffold test checks that every required field here also appears in
`PROJECT_STATE.md`, so the contract and the file cannot silently drift.

## Controlled Field Values

Two fields take controlled values, enforced by a scaffold test (membership, not a
fixed value, so a project may legitimately enable a lane):

- `Memory mode`: `none` (default) / `lightweight` / `llloom` — defined in
  `docs/template_framework/memory_modes.md`. This field is the only memory
  activation authority. The lane's machine-readable paths (memory root,
  posture file) come from `optional_lanes.llloom` in `frutlups.layout.yaml`;
  `PROJECT_STATE.md` deliberately has no memory-root field, so mode and path
  authority never split across two prose surfaces.
- `Frutlups mode`: `manual` (default/off) / `semi-manual` / `automated driver` —
  defined in `docs/template_framework/frutlups_modes.md`.

## Template Version Carries The Pin

`Template version` records both the template generation and the exact template
commit the project was projected from, in the form `v3 @ <commit>` (full or
short SHA; a release tag is acceptable when the template publishes one).
Framework initialization writes it; only a template refresh (see
`docs/template_framework/migration_and_adoption.md`, "Refreshing A Project To A
Newer Template Pin") changes it. The shipped scaffold carries the bare `v3`
because a template cannot know its own future commit; the pin is written at
projection time. No tool parses this value. It exists so a human or agent can
tell which template commit the checked-in framework docs are a snapshot of, and
so a refresh has an exact baseline to diff against.

## Which Fields Are Current Truth

These fields are live truth and override stale mentions elsewhere:

- `Active workspaces` / `Optional inactive workspaces`
- `Current objective`, `Current loop mode`, `Current ceremony level`
- `Memory mode`, `Frutlups mode`
- `Latest accepted review`
- `Next expected action`

If another artifact disagrees with these, `PROJECT_STATE.md` wins (see the
source-of-truth hierarchy in `CLAUDE.md`).

## Update Cadence

Update `PROJECT_STATE.md` when:

- a slice or pass is accepted (update `Latest accepted review` and
  `Next expected action`);
- the active/inactive workspace set changes;
- memory mode or frutlups mode changes;
- the current objective, loop mode, or ceremony level changes.

Keeping it current is part of closure, not an optional courtesy. Do not let it
become a stale dashboard.

## What Must Not Be Duplicated

Do not copy live state into multiple files:

- test counts, milestone numbers, and "current" claims live in one place and are
  derived or linked, not hand-copied across many docs;
- if a fact belongs in `PROJECT_STATE.md`, other files reference it rather than
  restating it.

Treat active prompt/review numbers, prompt-index counts, current worktree
contents, current workspace lists, latest-review labels, and next actions as
volatile. Durable artifacts should link to `PROJECT_STATE.md` or the relevant
index. When a historical artifact must preserve an observed value, label it as a
dated snapshot rather than continuing truth.

## Relationship To Other Artifacts

- `CONTEXT.md`: lightweight workspace orientation (what belongs here, what does
  not, what to read first, active/inactive status). It does not store live state.
- Reviews: the latest accepted review feeds `Latest accepted review`. Reviews are
  historical evidence; `PROJECT_STATE.md` summarizes the resulting live state.
- Prompts: reference `PROJECT_STATE.md` for current state; they do not restate it.
- Workspace status docs (for example a project-authored package-status doc
  in `08_pkg/`): scoped to that
  workspace, not a second global state surface.
