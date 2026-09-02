# Architect / Reviewer Initialization - Optional llloom Memory

Use this prompt only when the human owner chooses llloom memory for the project.

llloom is optional. Do not enable it by default.

## What llloom Is

llloom is durable, source-grounded memory. It stores source evidence, verified
claims, rendered pages, operation journals, and rebuildable sidecars.

Authority order:

1. raw source bytes and registry hash;
2. claim YAML with locators and excerpt hashes;
3. operation journals and update reports;
4. rendered pages;
5. rebuildable sidecars.

## Install Source

Choose and record the project-specific install source or package reference in
`05_governance/current/memory_posture.md`. Example local editable source:

```text
<path-to-llloom-repo>
```

Example PowerShell, from the project root:

```powershell
$python = ".\.venv\Scripts\python.exe"
$llloomRepo = "<path-to-llloom-repo>"
& $python -m pip install -e $llloomRepo
```

Optional extras are not default. Install them only when needed:

```powershell
& $python -m pip install -e "$llloomRepo[structured]"
& $python -m pip install -e "$llloomRepo[docling]"
```

## Initialize

Initialization is authorized only by the human owner setting
`Memory mode: llloom` in `PROJECT_STATE.md`. Never initialize the lane because
a memory directory happens to exist: directory presence is availability
evidence only, never activation.

Use the memory root configured in `frutlups.layout.yaml` under
`optional_lanes.llloom.memory_root`. The shipped value is:

```text
llloom_memory
```

Choosing a different root is a contract change, not a local preference: the
new value must remain a safe repository-relative path, and the layout field,
`05_governance/current/memory_posture.md`, the documentation, and the tests
must change together in one reviewed update.

Record the root in:

- `05_governance/current/memory_posture.md`
- `LOCAL_STATE_NOT_COMMITTED.md`

`PROJECT_STATE.md` selects the mode only; it has no memory-root field, and the
root is never recorded there.

Run:

```powershell
.\.venv\Scripts\llloom.exe --root .\llloom_memory init
.\.venv\Scripts\llloom.exe --root .\llloom_memory doctor
.\.venv\Scripts\llloom.exe --root .\llloom_memory verify
```

## Populate Memory

Treat population as a Level 4 architecture slice, not a bulk import.

Use the llloom manual at:

```text
<path-to-llloom-repo>\manual\agent_usage_manual.md
```

Seed only durable facts useful to future agents:

- architecture decisions;
- module boundaries;
- public contracts;
- reviewed findings;
- resolved questions;
- external source constraints.

Do not seed speculation, temporary debugging notes, or ungrounded claims.

## Update Protocol

Memory mutation requires an explicitly assigned memory-update slice or direct
human-owner authority.

Preferred update path:

1. add or update source under memory `raw/sources/`;
2. write a deterministic seed manifest;
3. run `seed apply --dry-run`;
4. run real `seed apply`;
5. run `doctor --last-op`;
6. run `verify` or `lint` when claims/pages are affected;
7. write a memory update report;
8. review before treating new memory as authoritative.

## Coder Posture

Coder default is read-only:

- `doctor`
- `status`
- `query`
- `claim-card`
- `list-sources`
- `list-pages`
- `verify`
- `lint`

No hand edits to claim YAML, source registry, journals, locks, or rendered claim
blocks.
