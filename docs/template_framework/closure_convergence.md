# Closure Convergence

Canonical contract for how the review loop terminates: rounds, recurrence,
escalation, the acceptance envelope, corrective passes, the active evidence
window, and assurance claims. The finding-disposition table (P0-P3) lives in
`05_governance/current/review_protocol.md`; this document owns everything
else. The verdict vocabulary is unchanged: `pass` / `needs_work` / `blocked` /
`override`.

## Rounds

A slice's reviews are numbered rounds. Round 1 is the first review of the
slice; each corrective pass increments the round. The round is recorded in
the review report metadata (`round:`) and in the `Round` column of
`05_governance/reviews/INDEX.md`. A fresh context reads the round there; it
never infers it from memory or prompt numbers.

## Escalation Ladder

| Round | Required response | Prohibited response |
| ---: | --- | --- |
| 1 | narrow correction proportional to risk | unrelated redesign |
| 2 | correction plus a durable deterministic guard, or an explicit recorded reason a guard is impossible; for assurance-plane findings, also record whether the harness is now more complex than the behavior it proves | another prose-only patch using the same failed method |
| 3 | stop the correction loop; the only legal next move is architect reassessment with human awareness — simplify the proof, narrow the claim, delete machinery, or redesign | issuing another same-shape corrective coding prompt |
| 4+ | continue only after explicit human authorization and a changed method | treating persistence as progress |

Round 3 is a routing stop, not a failure verdict. The reassessment may
conclude the findings have different roots and work continues — but that
conclusion is made deliberately, with the human owner aware, in one bounded
planning turn.

Circuit breaker (fires before the round count): if every confirmed finding
of a round falsifies only claims or states introduced by the previous
round's correction — none standing against the envelope as it existed before
that correction — the next step is architect reassessment or owner
disposition, never another same-shape corrective prompt. This is computable
from artifacts that already exist: each round's claim map plus the findings'
violated-invariant statements. The breaker is vacuously inapplicable at
round 2 — round 1 is not a correction, so it introduces nothing.

## Recurrence

A recurrence is the same violated invariant, or materially the same refuted
claim, within one artifact lifecycle. Judge it by the named invariant — never
by wording, function names, file names, or prompt numbers. In particular:

- different bypass strings, cleanup paths, process phases, or repository
  entries count as one recurrence when they refute the same material claim
  or show the same proof mechanism is not closed over its stated domain;
- repeated fast-close corrections on the same invariant count as recurrence;
  fast-close is not an escalation bypass;
- two findings are not the same class merely because both are documentation
  defects; the reviewer names the invariant, not the symptom.

Blocking findings therefore name their violated invariant, so the next
reviewer can count without archaeology.

The count resets only when:

- an accepted architectural change removes the failed representation;
- an accepted durable guard covers the invariant and the next independent
  review confirms it; or
- the human owner explicitly decides the new finding has a different root.

Renaming, renumbering, refactoring, or a larger test table never resets the
count.

## Acceptance Envelope

The envelope of a slice is what its coding prompt stated — Task, Non-Goals,
Verification, Definition Of Done — plus the baseline rails that always apply
(correctness, security, trust-boundary validation, data-loss prevention).

A reviewer may block only inside the envelope. A newly desired property —
however reasonable — is recorded as an `envelope expansion` finding and
routed to the architect as change control: the architect revises the
contract, states why the property is necessary, and states which prior
evidence it invalidates. It never enters as an in-place `needs_work` demand
on the current round.

When the parties disagree about what the envelope's own words mean — for
example whether a stated guarantee is scoped or unscoped — the human owner
arbitrates (source-of-truth rank 1), and the ruling is recorded durably (a
decision-log row or owner note), not left in chat.

Conformance is not release disposition. A finding can be true — the
implementation really does fail the stated falsifier — and still be accepted
debt when it is immaterial inside the supported release model (the
materiality gate in `05_governance/current/review_protocol.md` decides). The
verdict vocabulary is unchanged; the owner waiver/`override` path is the
routine, early route for true-but-immaterial residue, not a late escape
hatch discovered after many rounds.

## Corrective Passes

A corrective pass keeps the slice identity and increments the round.

- Re-review scope: the previously blocking findings, the delta, and any
  evidence the change invalidated — not a fresh full review. Settled scope
  stays settled.
- A corrective coding prompt (Level 2 and up) carries a Correction Scope
  Map: findings addressed; allowed files and claims; claims withdrawn or
  narrowed; evidence invalidated; minimum rerun set.
- Rerun rule (structural, not ritual): a change to a shared constructor,
  gate, or primitive reruns every dependent lane; a leaf data change reruns
  the affected lane; a prose-only change reruns the integrity checks that
  consume the prose. "Rerun everything" and "spot-check" both require a
  stated reason.

Owner-initiated reopening: the human owner may reopen an accepted `pass`
(source-of-truth rank 1) — for example when a defect against the accepted
envelope surfaces after the verdict. Represent it as the next round of the
same slice: the prior verdict row and report stay immutable history, the
reviews index gains a new row for the new round, the ruling is recorded
durably (decision log or owner note), and the corrective pass proceeds under
this protocol. Reopening does not rewrite the earlier review and does not by
itself count as a recurrence of the reviewed invariant.

## Objective Status Is Not A Verdict

A slice has two independent result dimensions. The implementation verdict
(`pass` / `needs_work` / `blocked` / `override`) judges the delivered change
against its acceptance envelope. The objective status (`achieved` /
`not_achieved` / `not_applicable` / `indeterminate`, recorded in the review
report's `## Closure Decision` section per
`05_governance/current/review_protocol.md`) judges whether the slice's
declared objective success criteria were met by the cited closure proof.
The coding prompt supplies both inputs (Definition Of Done for the first,
Objective And Closure Proof for the second); the reviewer assesses them
separately. `pass` with `not_achieved` or `indeterminate` is an honest,
legal receipt — a truthful pre-execution stop is one — and never implies
milestone completion; a third dimension, routing, belongs to the operating
tool and is never inferred from a verdict plus slice position. The verdict
vocabulary is unchanged.

## Active Evidence Window

Retention and active review input are different things. Git and governance
history retain everything; the active window contains only what is needed to
judge the current transition. Removing an artifact from the window neither
deletes nor discredits it.

Default window by strictness level:

- Level 1: current reference, exact finding, focused diff or check.
- Level 2: current prompt, self-report, immediately preceding findings,
  changed artifacts, directly controlling contract.
- Level 3: Level 2 plus relevant tests and the current roadmap/slice entry.
- Level 4: explicitly enumerated broader sources justified by the risk —
  still no automatic all-history rule.

History enters the window only when causally relevant, needed to verify
append-only preservation, or named by a controlling contract.

## Assurance Claims And Powerful Harnesses

Findings and claims carry a plane word: product, harness, evidence,
authority, or environment. An assurance-plane failure blocks like any other
finding of its disposition, but it is never reported as a product
regression.

Proof-bearing terms: `all`, `every`, `complete`, `no path`, `exact`,
`total`, `independent`, `mechanism-complete` — or equivalent phrasing
(`never`, `always`, `any`, `guarantees`); the list is a lint, not a grammar,
and synonyms do not escape the rule. A blocking finding or acceptance claim
using one must give a compact **finding claim map**:

- claim — the bounded property asserted;
- domain — the finite set or bounded grammar it holds over;
- independent falsifier — a check not generated from the implementation's
  own tables or constants;
- causal witness — when the claim names a branch or mechanism, how that
  branch is known to have actually run.

If the domain cannot be bounded, narrow the claim. A finite adversarial list
never proves an unbounded universal.

The claim budget applies at authoring time: proof-bearing terms in a coding
prompt's Task, Verification, or Definition Of Done require a **prompt claim
record** adjacent in the prompt — the finding claim map's four fields plus
exclusions and material consequence (claim, enumerated domain, exclusions,
material consequence, independent falsifier, causal witness). The four-field
map governs blocking findings; the six-field record governs prompt
authoring; where both apply, the record contains the map. A coder is never
obligated to deliver a universal the prompt's own claim record does not
bound; prefer "for states A-D" over "every". The ratchet's source is the
prompt, not the report.

Probe classes: a conformance probe drives only real supported seam outcomes
and may block; a host-limitation probe records an unavailable real
integration honestly; a synthetic-robustness probe deliberately exceeds the
seam and routes to P3/hardening unless a baseline safety rail is crossed. A
blocking fault-injection finding names the real seam outcome it models.
Reviewers may probe anything — classes bound what a probe may block, never
what it may investigate.

For a seam that already meets the powerful-harness definition below, a slice
MAY adopt a failure-model ledger
(`prompts/templates/failure_model_ledger.md`), versioned and frozen with the
round's candidate identity; a reviewer who believes the frozen ledger is
wrong files an `envelope expansion` finding rather than blocking in place.
The ledger is optional; no slice requires it.

A harness is powerful when it can delete or replace filesystem entries,
create or alter repositories outside a disposable root, build or install
packages, mutate process-wide environment or import authority, handle
signals, or decide provenance or preservation. A powerful harness must: use
the least-powerful primitive that works; declare an exact owned root before
any destructive cleanup; fail closed when ownership or parent identity
changes; open its cleanup boundary (`finally`) before the first protected
operation; carry causal negative tests for early failure and refusal paths;
and keep diagnostics bounded, with no silent recovery that changes the
claimed result.

When a lane consumes an external repository as `authority_input`, or writes
inside a declared `mutation_target` envelope
(`docs/template_framework/external_repository_roles.md`), prove the interval
with the same closed-world snapshot before and after: repository identity,
HEAD, the complete status entry set, and content identity for every
pre-existing changed or untracked entry in the declared set. Any unaccounted
change fails the lane; attribution by filename or by path-set difference is
not proof. Drift in a `preservation_only` repository is reported and
dispositioned by role; it never fails an unrelated lane, and an undeclared
neighbor is never a gate at all.

Convergence check: a correction must reduce unresolved acceptance
obligations. A correction that introduces as many new proof mechanisms or
universal claims as it closes is not converging; route it to architect
reassessment (round 3 semantics) regardless of the current count.
