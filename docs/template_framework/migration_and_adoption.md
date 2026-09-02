# Migration And Adoption

How to adopt this v3 template in a new repo or an existing v1-style project.

Principle: **adoption is additive and reversible.** Do not destroy, move, or
reinterpret history without explicit human approval and a recorded decision.

## New Project

1. Copy the scaffold (or use it as a GitHub template).
2. Fill `PROJECT_STATE.md` honestly: status, the template pin in
   `Template version` (`v3 @ <commit>`), profile, active workspaces, modes
   (default `Memory mode: none`, `Frutlups mode: manual`), objective, next action,
   validation command.
3. Choose the base profile and activate only the optional workspaces you need
   (see `project_profiles.md`). Leave the rest inactive as scope markers.
4. Run the scaffold tests to confirm the rails are intact.
5. Start the loop: the architect/reviewer writes the first coding prompt.

## Existing (v1-style) Project — Additive First

Do the additive steps before any cleanup:

1. Add the v3 control surfaces without deleting anything:
   - `PROJECT_STATE.md` (the single current-state surface);
   - `CLAUDE.md` source-of-truth order and workspace map;
   - `05_governance/current/` protocols (review, fast-close, and memory/frutlups
     posture only if those lanes are used).
2. Point existing docs at `PROJECT_STATE.md` instead of restating live state.
3. Keep existing prompts, reviews, verdicts, and notes exactly where they are —
   they remain historical evidence.
4. If the repo already has memory or loop tooling, set the matching controlled
   mode value; do not enable a lane you are not using.
5. For an existing codebase, fill `90_legacy_review/` before major changes, and
   record any interpretation of old history in `migration_decision_log.md`
   (append-only).
6. Only after the v3 surfaces are in place and trusted, consider optional
   cleanup — and only with explicit human approval (see below).

## History Preservation (defaults)

- Do not move or delete historical v1 prompt/review artifacts by default.
- Do not run destructive prune scripts as a default migration step.
- Do not rewrite old artifacts just to fit v3 naming.
- Interpret old history with append-only notes or the migration decision log,
  never by editing the original record.
- Physically pruning optional workspaces is an explicit human/project decision,
  recorded in `migration_decision_log.md` — never the default.

## Refreshing A Project To A Newer Template Pin

A project carries a snapshot of the template's framework surfaces, frozen at
the commit recorded in `Template version`. When the template moves, that
snapshot ages: a fresh agent reads the project's copy and may find it
contradicting the tools actually installed. Refresh deliberately, as one
documented commit.

Three kinds of surface:

- **Template-owned, overwritten from the new pin:** exactly the surfaces
  declared under `template_owned_surfaces` in `frutlups.layout.yaml`: the
  framework docs, the initialization prompts, the prompt templates, the
  scripts lane, the fixture folders, the layout itself, the two current
  protocols, and the scaffold test modules by name. A scaffold test keeps
  that list equal to the shipped modules. Any other file under the tests
  folder is the project's own and is never touched.
- **Project-owned, never overwritten:** `PROJECT_STATE.md`, `MILESTONES.md`,
  the content of the numbered workspaces, the coding and review prompt
  folders, `05_governance/reviews/`, `05_governance/human_owner_notes/`,
  `questions/`, the decision and risk logs, and every project-authored test.
- **Merged by hand:** `CLAUDE.md` and `README.md`. Intake customizes them, so
  carry template rule changes across manually.

Steps:

1. Confirm the project's template-owned surfaces still match the recorded pin
   (diff against that template commit). Local edits there are drift; resolve
   them first, never overwrite them silently.
2. Copy the new pin's versions of the template-owned surfaces; merge the
   merge-by-hand surfaces.
3. Set `Template version` to the new pin.
4. Run the project's validation command; the clone-only checks report as
   skipped, not failed, in an initialized project.
5. Commit as one documented refresh and record it in
   `05_governance/decision_log.md`.

When not refreshing: record the disagreement in
`05_governance/current/known_divergences.md` and continue on the
source-of-truth order in `CLAUDE.md`. The checked-in snapshot is evidence of
what the template said at the pin, not authority over the tools installed now.

## Opting Into The Slice Prompt Contract

Opt-in is one reviewed migration step with exactly two effects: add a sidecar
(`<roadmap-stem>.slices.yaml`) beside each selected prose roadmap, and set the
layout's `prompts.coding_template` to the contract-v1 scaffold
`prompts/templates/coding_prompt_contract_v1.md`. Rollback reverses both in one
step. Absent sidecar plus the legacy template path is legacy v3 behavior
byte-for-byte. Validate with the reference checker before dispatching:

```text
python scripts/slice_contract_check.py --sidecar 03_experiments/active_roadmap.slices.yaml
```

Full contract: `docs/template_framework/slice_prompt_contract.md`.

## Front Matter (OKF Profile)

Front matter is optional and applies to **new artifacts only**; legacy
no-frontmatter documents remain the default and are never retrofitted by default.
Opt-in is per exact artifact path, and the minimum block is just `type` and
`framework_profile: "0.1-rc.1"`. For the copy-ready per-type examples, the adoption
and rollback sequence, and profile-version change control, see the canonical guide
`docs/template_framework/okf_authoring_and_migration.md`.

## Commit Cadence / Checkpoints

- Commit after each accepted slice or adoption step so `git log` reflects the
  loop.
- `PROJECT_STATE.md` should say whether there are accepted-but-uncommitted
  artifacts.

## Human Stop/Go Points

Get explicit human approval, and record the decision, before: deleting or moving
history, running any prune/cleanup, enabling an optional lane (memory or
frutlups), or any other irreversible step.
