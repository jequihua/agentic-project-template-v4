# Coder Initialization - Optional llloom Memory

Use this prompt only when `PROJECT_STATE.md` says memory mode is `llloom`.

## Role

You use llloom as read-only source-grounded project memory during normal coding.
You do not mutate memory unless assigned a memory-update slice or acting under
direct human-owner authority.

## Read First

1. `PROJECT_STATE.md`
2. `05_governance/current/memory_posture.md`
3. the active coding prompt
4. the llloom pages or claims named by the prompt

The llloom manual is here:

```text
<path-recorded-in-memory_posture.md>
```

## Startup

Use the memory root configured in `frutlups.layout.yaml` under
`optional_lanes.llloom.memory_root` and mirrored in `memory_posture.md`.
(`PROJECT_STATE.md` selects the mode; it does not carry the root.)

These startup checks are read-only validation: they observe and report lane
health. Never initialize, repair, or otherwise mutate the lane from here.

Run proportional checks:

```powershell
.\.venv\Scripts\llloom.exe --root <memory_root> doctor
.\.venv\Scripts\llloom.exe --root <memory_root> verify
```

Run one relevant query only when memory matters to the slice:

```powershell
.\.venv\Scripts\llloom.exe --root <memory_root> query "<subsystem or question>"
```

If `doctor` reports serious errors, `verify` fails, or memory contradicts the
task prompt, stop and report the mismatch. Report stale or contradicted claims;
do not hand-patch them — that is a separate, assigned memory-update slice.

## Read-Only Commands

Allowed by default:

- `doctor`
- `status`
- `query`
- `claim-card`
- `list-claims`
- `list-sources`
- `list-pages`
- `list-render-targets`
- `verify`
- `lint`

Do not hand-edit (all inside the configured memory root):

- claim YAML under `claims/entities/`
- rendered claim blocks under `pages/`
- the source registry and journals under `state/`
- locks or tombstones
- raw sources unless assigned a memory-update slice or under direct
  human-owner authority

## Self-Report Additions

In your self-report, include:

- memory commands run;
- pages or claims used;
- stale or contradicted claims found;
- whether a memory update is requested.

Use claim, page, or source ids when available.
