# Prompt Style Guide

Prompts should make the next action safer without becoming a mini manual.

## Rules

- Point to stable artifacts instead of repeating long history.
- Use a short read-first list. Normal prompts should aim for five or fewer files.
- State active workspaces.
- State non-goals.
- State verification.
- State output paths as an exact write manifest: every artifact the slice
  writes with its exact repository-relative file path, artifact type, role
  owner, and retry policy; a task noun such as "publish the decision" with
  no declared path is not a prompt
  (`docs/template_framework/slice_prompt_contract.md`).
- State definition of done.
- Use `rg` / `rg --files` for search instructions.
- Keep llloom and frutlups optional unless `PROJECT_STATE.md` enables them.
- Do not copy volatile live state into durable prompts or reports. Active prompt
  numbers, index row counts, worktree contents, workspace lists, and next actions
  should be linked or derived from `PROJECT_STATE.md` and indexes. If an observed
  value is evidence, label it as a dated snapshot.
- When the slice cites repository paths or test identifiers, require the
  read-only `scripts/artifact_integrity_preflight.py` check before semantic
  review.

## Placeholders And Dispatch

- Every line-start `status:` line in a prompt is exactly `status: <value>`,
  plain and unquoted, with one value (the workflow metadata and the
  contract's typed entry both carry it); a disagreement, any other spelling,
  or a contract prompt with a single status line is ambiguous and the
  preflight treats the prompt as ready and fails closed.
- A prompt is dispatchable only at workflow `status: ready`. A ready prompt
  contains no unresolved sentinel (`TBD`, `<value>`, `<path>`, `<one move>`)
  and no deleted-section residue; optional sections are removed, never shipped
  as placeholders. `python scripts/artifact_integrity_preflight.py` errors on
  both.
- Pre-created prompts for later roadmap slices stay `status: frozen`: valid
  planning material, never current work, never promoted silently. Under the
  slice prompt contract, `ready` requires satisfied opening gates and a
  recorded dispatch authority.
- The coder never writes the review report, verdict record, acceptance
  state, or routing state; a prompt that assigns them to the coder is invalid.

## Claims And Amendments

- Universal words (`all`, `every`, `complete`, `no path`, `exact`, `total`)
  are budgeted at authoring time: enumerate the domain in a claim record or
  narrow the sentence before the prompt ships — the ratchet's source is the
  prompt, not the report (`docs/template_framework/closure_convergence.md`).
- When an amendment changes a finding's disposition, place one compact
  controlling delta table before the active task and explicitly supersede
  contradictory operative wording; the historical amendment record keeps the
  old text. Operative prompts carry one clear controlling instruction.

## Size Budgets

Budgets are guidance, not gates, but respect them:

- a coding prompt aims for one page; if it cannot fit, the slice is too big;
- a review report leads with at most ten findings — more is a finding against
  the prompt's scope, not a reason for more review text;
- a self-report aims for one page plus verification evidence.

Active review input is bounded by the evidence window in
`docs/template_framework/closure_convergence.md`; link history instead of
re-reading it.

## Recommended Coding Prompt Shape

1. Role and workflow mode.
2. Current state link.
3. Active workspaces.
4. Read first.
5. Task.
6. Non-goals.
7. Verification.
8. Self-report requirements.
9. Definition of done.

