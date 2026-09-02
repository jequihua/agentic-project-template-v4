# Fast-Close Correction

Fast-close is for low-risk corrections only. It is append-only: add a correction
block, never silently rewrite or delete prior text. Preserve the original text
unless it contains secrets or harmful content.

Correct operative text in a current-reference artifact in place. Preserve the
old value and rationale in this correction record; do not leave a known-wrong
identifier active merely to make the reference artifact append-only.

Use fast-close only when the replacement is objective, behavior does not change,
and a focused diff plus deterministic check can prove closure. Otherwise use
Level 2 or higher. An eligible fast-close does not need a new numbered coding and
review prompt pair.

The full rule lives in `05_governance/current/review_protocol.md`.

## Never Use Fast-Close For

- behavior or generated-output changes;
- public contract or API changes;
- schema changes;
- new dependencies;
- credentials or secrets;
- live-cost or cloud operations;
- security, privacy, or data-handling changes;
- substantive reinterpretation;
- any case where eligibility is uncertain.

Any of the above requires a normal Level 2+ slice and review.

## Attribution-Only Corrections

A finding-attribution defect (the record misstates who dispositioned or
corrected a finding) is fast-close eligible when all five hold: the
substantive measurements already reproduce; no score, severity, verdict,
behavior, contract, or authority input changes; the correct actor and
disposition are objective from an existing review, amendment, or owner
record; the correction preserves historical text via append-only
supersession; and a focused diff plus a direct citation check prove closure.

The disposition fields below apply only when findings are involved; for an
ordinary correction with no inherited finding, write n/a.

## Correction

Actor:

Date:

Reason:

Linked evidence or finding:

Prior disposition:

New disposition:

Disposition authority:

Affected finding IDs:

Affected current-reference file and location:

Original issue:

Correction:

Behavior changed: no

Verification command and result:

Closure actor and decision:

Recommended next move:
