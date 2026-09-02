# Memory Posture

Memory mode is set in `PROJECT_STATE.md`; mode definitions are in
`docs/template_framework/memory_modes.md`. This file records the *current posture*
for whichever mode is active. It is not a second copy of live state.

This file's own path is the layout-configured
`optional_lanes.llloom.posture_file` in `frutlups.layout.yaml`. It mirrors
operational posture and status; it never selects the mode, and no consumer
parses this prose to decide whether memory is enabled.

Current mode: none

## When mode is `lightweight`

- facts/claims file:
- what it covers:

A plain-markdown file. No llloom install, root, or commands.

## When mode is `llloom`

Record:

- memory root (must equal `optional_lanes.llloom.memory_root` in
  `frutlups.layout.yaml`):
- install source:
- read-first pages:
- allowed read commands (read-only): `doctor`, `status`, `query`, `claim-card`,
  `list-claims`, `list-sources`, `list-pages`, `verify`, `lint`
- last `doctor` / `verify` status:

Operating manual:

## Rules (both modes)

- coder default is read-only;
- memory mutation requires an explicitly assigned memory-update slice or
  direct human-owner authority;
- never hand-edit llloom authority files (claim YAML, source registry, journals,
  locks, rendered claim blocks);
- report stale, contradictory, or failing memory instead of patching it by hand.
