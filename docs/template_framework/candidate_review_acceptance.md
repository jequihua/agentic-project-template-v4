# Candidate, Review, And Acceptance

Opt-in lifecycle contract for identity-bound deliveries: frozen handoffs,
release candidates, and migrations. Ordinary slices keep the normal
reviewed-diff practice and never use this contract. Using it adds no
manifest requirement, no registry, no new `PROJECT_STATE.md` field, and no
tool; a coding prompt opts in by carrying a Candidate Identity section.

## Definitions

- **Candidate**: the immutable bytes submitted for review — one file, a
  directory bound by a manifest, or a git tree.
- **Candidate identity**: the stable value a review binds to. The coding
  prompt declares exactly one strategy:

| Strategy | Best for | Identity |
| --- | --- | --- |
| file | one-document deliverable | SHA-256 of the canonical bytes |
| manifest | multi-file handoff or package | SHA-256 of an immutable manifest listing member paths and digests |
| git | a repository tree | tree or commit ID |

- **Review report**: immutable evidence produced outside the candidate. It
  names the exact identity reviewed, the checks performed, findings, and the
  verdict.
- **Acceptance record**: an owner-controlled decision, outside the candidate,
  naming an exact candidate identity and the passing review report it relies
  on.

## The Core Guarantee

A candidate never contains its own current, reviewed, or accepted status —
and recording a review verdict or an acceptance never changes candidate
bytes.

- `needs_work` followed by changed candidate bytes produces a new candidate
  identity; the next review binds the new identity.
- Recording a verdict or acceptance produces no new identity, ever. If
  writing a status record would change the candidate's bytes, the status
  record is in the wrong place.
- An acceptance record that names a different identity than the passing
  review it cites is invalid.
- Current routing stays where it always lives: `PROJECT_STATE.md` and the
  existing indexes link to the accepted candidate; the candidate does not
  announce itself.

## Non-Circular Identity

Never record the hash of the commit that contains the record making the
claim. Use one of:

1. accept a pre-existing candidate commit or tree, committing the acceptance
   record separately afterwards;
2. accept a file or manifest digest, letting the acceptance-record commit be
   separate; or
3. point a human-controlled tag or release at the already reviewed candidate
   commit.

## Corrections

A `needs_work` verdict on a frozen candidate follows the ordinary corrective
loop, including rounds and the escalation ladder
(`docs/template_framework/closure_convergence.md`). Only a change to
candidate bytes creates a new identity; status bookkeeping never does. If a
correction sequence keeps editing status or evidence statements inside the
candidate, that is the Case-1 loop this contract exists to prevent — move
the statements outside the candidate instead of re-freezing it.

## Rollback

Stop using the lifecycle: the candidate files remain ordinary artifacts, the
review and acceptance records remain historical evidence, and nothing needs
migration.
