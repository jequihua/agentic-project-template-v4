# Method

Progress is an artifact becoming more explicit, reviewable, or correct. Agent
activity is not evidence by itself.

## Authorities

- `roadmap.yaml`: milestones, slices, acceptance, verification, risk, and write
  boundaries.
- `05_governance/ledger.jsonl`: append-only loop events and derived state.
- `00_brief/decisions.md`: accepted project decisions.
- `questions/`: durable blockers and their answers.

`docs/roadmap.md`, status/index output, prompts, coder notes, and review prose
are views or evidence. They do not replace their authority source.

## Roles

The human owner controls destination, priorities, waivers, external effects,
and stop/go decisions. The architect translates that authority into brief and
roadmap entries, runs the loop scripts, saves manual outputs, records reviews,
accepts slices, and makes authorized acceptance commits. The coder changes only
the prompt's product boundary and reports facts. Review is product-read-only;
manual reviewers may write only their named report, while autonomous reviewers
return it for frutlups to save. frutlups may perform the architect's mechanical
handoffs but receives no broader authority.

## One slice

1. The architect renders a coding prompt. Its successful write and hash are
   followed by a `prompt` event.
2. The coder implements within the effective prefixes, runs focused checks, and
   returns factual notes. Git—not those notes—produces the changed-file list.
3. The architect records `coded`. An out-of-bound change refuses the event and
   leaves the tree for a human; nothing is reverted automatically.
4. `verify.py` runs the declared full argv and writes a receipt. It appends
   `verified` whether the check passes or fails.
5. On success, a review prompt carries the receipt, cumulative changed-path
   manifest, current-round bounded diff, and optional notes to a read-only
   reviewer. A neutral `artifact` event records its immutable identity without
   changing lifecycle state.
6. `ledger.py record` validates the report and appends `reviewed`.
7. A pass becomes `accept_pending`. The architect accepts it, optionally making
   the exact acceptance commit. Needs-work or failed verification produces a
   new corrective round; blocked stops for the named owner. A human or architect
   may append `unblocked` with a reason to start the next corrective round while
   preserving the blocked findings.

Manual and autonomous operation use these same files and transitions. Switching
is safe between steps because the ledger is read fresh; no conversion exists.

## Acceptance envelope

Review against the slice objective, acceptance list, non-goals, read/write
boundary, and verification contract plus repository safety rules. A reviewer
does not enlarge the envelope. A newly desired property becomes a proposed
roadmap change, not an in-place blocking demand.

Findings have stable ids, severity, disposition, and summary:

- P0: imminent safety, credential, destructive-authority, or data-loss risk.
- P1: incorrect behavior, broken required contract, or material architecture
  error; must be fixed before pass.
- P2: material bounded defect in evidence, compatibility, or maintainability;
  must be fixed before pass unless a human waives the exact finding.
- P3: clarity or deferred hardening that cannot falsely authorize acceptance;
  it may be carried to `backlog.md` with a pass.

The reviewer opens and closes findings. A coder may remediate or challenge but
never self-close. Only the human owner records `waived_by_human`. A report with
open P0-P2 cannot pass. Uncertain materiality remains P2 until reviewed.

## Objective and verdict

The closure decision independently records whether the stated objective is
`achieved`, `not_achieved`, or `indeterminate`, with one evidence sentence. The
verdict judges the implementation against its envelope: `pass`, `needs_work`,
or `blocked`. A truthful stopped experiment can pass its implementation contract
while its objective remains not achieved; that does not claim research success.

The report contains one final section and one line:

```text
## Verdict
Verdict: pass|needs_work|blocked - next: <one move>
```

Human records may additionally use `override`; autonomous reviewers may not.

## Rounds and reopening

Rounds start at 1. Failed verification, a needs-work review, or an authorized
unblock advances the next coding prompt to the following round and carries the
relevant command tails, open findings, and unblock reason. The prompt
automatically baselines exact ledger-known same-slice state; `--allow-dirty` is
reserved for inspected unknown architect state. Transport failure
may retry the same agent job without a new prompt event and does not consume a
corrective round. Review later rounds only against open findings, the delta,
and evidence invalidated by that delta.

An accepted slice may be reopened only by a human or architect record with a
reason. Append `reopened` at the next round; never edit the earlier pass or
acceptance.

## Milestones

A milestone's slices are accepted only through the ledger. If
`holistic_review: false`, all accepted slices make it done without a
`milestone_done` event. If true, a holistic review must pass before that event
is recorded. A holistic P0-P2 finding id starts with the affected slice id. All
open findings for one slice produce one reopen reason containing every id; then
continue that slice's round sequence. Holistic prompt/report artifact events
preserve provenance across that reopen. Empty work or an empty next frontier is
not completion.

## Commits

Coders never commit unless the owner explicitly changes that rule. The normal
commit boundary is an accepted slice. `ledger.py accept --commit` appends the
accepted event, stages only the accepted slice and its loop evidence, and makes
`Accept M001-S01 round 2`; it never pushes. The event omits its own commit hash
to avoid circular identity and the command prints the resulting hash. A known
external/manual acceptance commit may be recorded in the optional field.

Before committing, require passing verification and review, inspect status,
exclude secrets/local state, and inspect the exact staged paths. Pull requests,
front-repository publication, tags, and pushes require separate human authority.

## Planning uncertainty

`not_yet_specified` holds plausibly in-scope concerns not sharp enough to be a
slice or precise question. `ruled_out` holds accepted project exclusions. They
never enter the ready frontier. Sharp externally blocked work belongs in
`questions/open/`; do not hide it as uncertainty. Changing the project
destination or resurrecting a ruled-out item needs human approval.
