# Architect / Reviewer Initialization - Optional frutlups Loop Tooling

Use this prompt only when the human owner wants frutlups to help run the
artifact-first loop.

frutlups is optional. The template must work manually without it.

## What frutlups Is

frutlups is a lightweight Python package for orchestrating artifact-first coding
loops between coding agents, review agents, and a human owner.

It can read project artifacts and help with:

- loop status;
- next frontier;
- coding prompt creation;
- review prompt creation;
- self-report and review-report validation;
- verdict recording;
- resumability.

Record the project-specific install/source reference in
`05_governance/current/frutlups_posture.md`. Example local editable source:

```text
<path-to-frutlups-repo>
```

Key guide:

```text
<path-to-frutlups-repo>\08_pkg\ARTIFACT_TEMPLATE_GUIDE.md
```

## Posture

Use frutlups in one of three modes:

- manual: not used;
- semi-manual: agents run `status`, `next`, or prompt-generation commands;
- automated driver: a local runner consumes `status --json` and stops at gates.

Record the mode in `PROJECT_STATE.md`.

## Manual / Semi-Manual Commands

Examples from a package workspace:

```powershell
.\.venv\Scripts\python.exe -m frutlups status ..
.\.venv\Scripts\python.exe -m frutlups next ..
.\.venv\Scripts\python.exe -m frutlups make-coding-prompt .. --dry-run
.\.venv\Scripts\python.exe -m frutlups make-review-prompt .. --dry-run
```

Do not hand-edit loop state to force progress. Recorded verdicts move the
frontier.

## Loop Ownership

- the architect/reviewer creates coding prompts;
- the coder creates the matching review prompt only after the self-report exists;
- recorded verdicts (`pass` / `needs_work` / `blocked` / `override`) move the
  frontier — never manual roadmap edits.

## Slice Prompt Contract Projects

When the project opts into the slice prompt contract
(`docs/template_framework/slice_prompt_contract.md`): every slice is a typed
sidecar entry beside the roadmap; a live entry carries a complete execution
envelope, and every environment binding it names must have its value declared
in the runner's policy or admission refuses; sidecar entries are authored by
the architect/reviewer or the human owner, never by a coder seat or a runner;
a corrective entry becomes dispatchable only through the operating tool's
governed validation. Run the pre-launch size check before the launch word.

## Thin Driver Direction

Any runner is external: this scaffold ships none and defines only the
specification boundary a conforming runner must honor. See
`docs/template_framework/frutlups_driver_boundary.md`.
