# Frutlups Posture

Frutlups mode is set in `PROJECT_STATE.md`; mode definitions are in
`docs/template_framework/frutlups_modes.md`. This file records the *current
posture* when frutlups is enabled. It is not a second copy of live state.

Current mode: optional, not required (manual operation is first-class)

## When frutlups is enabled (semi-manual or automated driver)

Record:

- install/source reference:
- guide:
- read-only compass commands: `status`, `next` (add `--json` for machine state)
- write actions (preview with `--dry-run`): `make-coding-prompt`,
  `make-review-prompt`, `record-verdict`
- last `status` summary:

## Rules

- manual operation stays valid; frutlups is never required;
- do not hand-edit loop state to force progress; recorded verdicts move the
  frontier;
- roles (`architect`, `reviewer`, `coder`, `human`) are logical and
  provider-neutral;
- do not install frutlups unless assigned.
