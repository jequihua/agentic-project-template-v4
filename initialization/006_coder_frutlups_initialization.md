# Coder Initialization - Optional frutlups Loop Tooling

Use this prompt only when `PROJECT_STATE.md` enables frutlups.

## What frutlups Is

frutlups is optional loop tooling. It reads repository artifacts to tell you
where the artifact-first loop stands and what should happen next.

It should not replace your self-report or your judgment. It helps enforce gates.

Reference guide:

```text
<path-recorded-in-frutlups_posture.md>
```

## Read-Only Orientation

From the expected package workspace, run:

```powershell
.\.venv\Scripts\python.exe -m frutlups status ..
.\.venv\Scripts\python.exe -m frutlups next ..
```

If frutlups is not installed, do not install it unless the prompt or architect
asks you to. Report that frutlups is unavailable and continue manually if the
prompt allows.

## Coder Responsibilities

- Implement only the active coding prompt.
- Write the self-report with exact required headings.
- If the project convention allows it, create a draft review checklist or
  matching review prompt after the self-report exists.
- Do not record verdicts unless explicitly assigned.
- Do not edit roadmap or verdict state to claim progress.

## Automation Stop Conditions

If using an automated or semi-automated driver, stop and report when:

- self-report is invalid;
- review report is invalid;
- verdict is `blocked`;
- override is required;
- no frontier exists;
- memory verification fails;
- environment gate fails.
