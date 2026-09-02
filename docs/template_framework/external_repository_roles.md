# External Repository Roles

A repository outside the task can constrain a result only through a declared
causal role. Physical proximity, visibility, and read access create no
authority: a repository matters when the task consumes a fact from it, is
authorized to mutate it, or explicitly observes it as a courtesy. For a
repository that is none of these, omission is the clearest statement that it
is out of scope — do not snapshot it, and do not make its quiet a gate.

## The Three Roles

| Role | Why the repository is present | What can block closure |
| --- | --- | --- |
| `authority_input` | named bytes, commits, manifests, tests, or facts from it determine the result | drift in the exact consumed authority during its evidence interval |
| `mutation_target` | the task is authorized to modify an explicitly bounded write envelope | change outside the declared envelope, or unresolved concurrent overlap inside it |
| `preservation_only` | a concrete courtesy observation, nothing consumed or targeted | only the task's own unauthorized consumption or mutation |

Role rules:

- `authority_input` names the exact surface and its identity basis (commit,
  tree, digest — and content identity for consumed dirty bytes; `HEAD` alone
  is insufficient when dirty bytes are consumed). Drift there blocks only the
  dependent evidence: resume from a fresh stable snapshot or rerun the
  affected lane; unrelated lanes stand.
- `mutation_target` compares opening state with completed state to separate
  authorized work from concurrent or accidental change. Unexpected overlap
  blocks closure, because the agent cannot safely attribute, stage, revert,
  or overwrite it.
- `preservation_only` drift is reported honestly and never blocks an
  unrelated result. The reviewer checks the task's declared commands, input
  surfaces, and changed paths for evidence the task itself did not consume or
  target the repository; global quiescence is never demanded.

## Promotion Is Prospective

A task that discovers mid-run it needs a repository it omitted or classified
`preservation_only` must stop before consuming the new authority: reclassify
it as `authority_input`, name and snapshot the exact surface, then continue.
Consumption first with retroactive justification is prohibited.

## What Never Establishes Causation

- Attribution never by filename, directory proximity, repository name, or a
  hard-coded project list — two tasks can legitimately touch similarly named
  files, and a changed file proves nothing about consumption.
- Universal exclusion proofs ("no possible indirect read occurred") are not
  required and not accepted as gates; declare the actual inputs and targets,
  then test the causal seams that could affect the result.

## Relationship To The Convergence Contract

The closed-world interval mechanics (what a before/after snapshot must
contain) live in `docs/template_framework/closure_convergence.md`. This
document decides which repositories that machinery may bind: `authority_input`
surfaces and `mutation_target` envelopes — never a `preservation_only`
neighbor, and never an undeclared one.
