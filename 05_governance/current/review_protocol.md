# Review Protocol

## Review Strictness Levels

Strictness levels are defined canonically in
`docs/template_framework/review_strictness_levels.md`. That file is the single
source for what each level requires. Do not restate the level definitions here.

In short: the strictness level (1-4) is the one ceremony axis. It decides prompt
size, review depth, artifact expectations, and closure burden. Workflow mode (see
`docs/template_framework/workflow_modes.md`) describes the kind of work, not its
weight. There is only one tiering axis.

## Fast-Close Guardrails

Fast-close (Level 1) is append-only. Never silently rewrite or delete historical
artifacts.

Fast-close is forbidden for:

- behavior or generated-output changes;
- public contract or API changes;
- schema changes;
- new dependencies;
- credentials or secrets;
- live-cost or cloud operations;
- security, privacy, or data-handling changes;
- substantive reinterpretation;
- any case where eligibility is uncertain.

Anything above requires a normal Level 2+ slice and review.

Fast-close is eligible only when all of these are true:

- the defect is confined to documentation or metadata wording;
- the intended replacement is objective and unambiguous;
- no behavior, generated output, public contract, schema, dependency,
  credential, cost, security, or data-handling behavior changes;
- a focused diff and deterministic check can prove closure;
- the current reference can be corrected without obscuring historical evidence.

When eligible, correct the current reference, append one compact correction
record linked to the finding, run the relevant deterministic check, and record
closure. The correction record lives beside the review evidence it relates to
(the milestone folder under `05_governance/reviews/`); any role may execute an
eligible fast-close when acting on an explicit reviewer finding or a recorded
human-owner instruction (an owner-reported defect is transcribed to a durable
note first and linked as the finding). Do not create a new full coding prompt,
self-report, and review prompt only to repair the tiny defect.
If eligibility is uncertain, use Level 2.

A fast-close correction block must record:

- actor;
- date;
- reason;
- linked evidence or finding;
- whether behavior changed (must be "no" for fast-close).

Preserve the original text unless it contains secrets or harmful content. Use the
template at `prompts/templates/fast_close_correction.md`.

"Preserve the original text" applies to historical evidence. It does not require
an operative current-reference artifact to retain a known-wrong identifier; the
review/correction record preserves that history.

## Convergence And Disposition

Rounds, recurrence, the escalation ladder, the acceptance envelope, and
corrective-pass re-review scope are defined canonically in
`docs/template_framework/closure_convergence.md`. In short: reviews are
numbered rounds recorded in `05_governance/reviews/INDEX.md`; blocking
findings name their violated invariant; the third same-invariant recurrence
stops the correction loop and routes to architect reassessment with human
awareness; and a reviewer may not widen the acceptance envelope — a newly
desired property is an `envelope expansion` finding routed to the architect
as change control, never an in-place `needs_work` demand.

Every finding carries a disposition and a plane word (product / harness /
evidence / authority / environment):

| Disposition | Meaning | Default routing |
| --- | --- | --- |
| P0 | imminent safety, security, data-loss, credential, or destructive-authority risk | stop immediately; human awareness |
| P1 | incorrect behavior, broken public/frozen/release-critical contract, invalid candidate identity, or material architectural error | `needs_work` |
| P2 | material bounded defect in authority, evidence, compatibility, or maintainability | `needs_work` while unresolved |
| P3 | clarity, style, pre-effect local cleanup or diagnostic incompleteness, synthetic-only robustness, or follow-up that cannot misroute execution or falsify acceptance | may accompany `pass` as named follow-up |

An internal assurance sentence worded too broadly is narrowed under the claim
budget (`docs/template_framework/closure_convergence.md`); its product
consequence is assessed separately, not inherited from the sentence.

Before recording P1 or P2, the reviewer — never the implementer — answers:

1. Can the outcome execute or authorize an unintended external effect?
2. Can it corrupt, destroy, expose, or falsely accept project data or
   evidence?
3. Can it misroute recovery, spend, credentials, or trust boundaries?
4. Can it persist beyond the failing process or cause unbounded resource
   use?
5. Is it a real supported seam outcome rather than synthetic-only behavior?
6. Is the failed property explicitly required for this release rather than
   an overbroad assurance sentence?

All answers no routes the finding to P3. Answers may be batched per finding
class when several findings share a mechanism. Materiality disagreements go
to the envelope arbiter (the human owner), recorded durably.

An unresolved P0-P2 finding never coexists with `pass`. There is no
"non-blocking P2": if independent review cannot show a defect is unable to
affect behavior, authority, safety, evidence truth, or routing, it stays P2.
`needs_work` routes to the implementer of the reviewed slice; use `blocked`
when closure depends on an actor other than that implementer (another role,
external evidence, or authority) — the verdict line's next move then names
the owning actor.
A human owner may record an explicit external waiver naming the exact finding
and the reviewed identity; a waiver is a separate decision record and never
rewrites the review or its verdict. Waiver and override entries are
identity-bound and are re-acknowledged by the owner at milestone closure and
at any release-objective upgrade — materiality is release-objective-relative.

## Finding Disposition Lifecycle

This lifecycle activates only when a correction inherits findings or a
finding changes state; ordinary passing reviews carry none of it.

| State | Meaning | Who may record it |
| --- | --- | --- |
| `open` | independently reported and unresolved | reviewer |
| `remediated_pending_review` | coder claims the underlying defect was corrected — a claim only | coder |
| `disputed_pending_review` | coder supplies counter-evidence — a challenge only | coder |
| `withdrawn_by_reviewer` | the finding was materially wrong or inapplicable | reviewer, or architect acting in reviewer role |
| `closed_by_review` | independent review confirms remediation | reviewer |
| `accepted_risk_by_owner` | unresolved finding knowingly accepted | human owner; architect may record the decision |

A coder owns remediation evidence, not review disposition. Counter-evidence
routes a finding to reviewer reconsideration; it does not withdraw it. Only
the reviewer — or the architect acting in reviewer role — may withdraw or
close a review finding, and only the human owner accepts unresolved risk. A withdrawal record states why the
review was wrong or no longer applicable, and correction evidence never
silently changes a finding's disposition.

## Review Output Shape

Use findings-first review:

1. Confirmed issues by severity.
2. Scope discipline.
3. Verification performed.
4. Documentation and governance honesty.
5. Closure decision, as a `## Closure Decision` section (the closure record
   below).
6. Recommended next move: pick exactly one.

Each finding carries its P0-P3 disposition and plane word; blocking findings
name the violated invariant. On round 2 or later, review only the previously
blocking findings, the delta, and invalidated evidence.

On round 2 or later, open the report with a compact closure receipt of at
most fifteen lines: the candidate or reviewed identity, finding IDs opened
and closed with their dispositions, the claim-map reference, standing waiver
or accepted-limitation references, the current-run verification summary, and
the verdict line; when the slice adopts a failure-model ledger, the receipt
names its frozen version. Append-only history remains the audit trail; the
closure receipt is the active decision surface, and a live waiver never
stays off it.

## Closure Record

Every review report carries, immediately before `## Verdict`, exactly one
`## Closure Decision` section with exactly two lines:

```markdown
## Closure Decision

Objective status: <achieved|not_achieved|not_applicable|indeterminate>
Objective evidence: <one line citing the slice closure-proof artifacts, or the exact not-applicable justification>
```

`achieved`: the cited closure evidence establishes every applicable objective
success criterion. `not_achieved`: the evidence establishes that at least one
applicable criterion was not met. `not_applicable`: the review has no
applicable objective dimension, with an explicit reason. `indeterminate`:
relevant evidence exists or was sought but is absent, incomplete, conflicting,
or otherwise insufficient to decide.

Implementation completion and objective achievement are assessed separately.
A truthful pre-execution or fail-closed stop may earn `pass` with
`Objective status: not_achieved` or `indeterminate`; those are legal receipts
that never imply milestone completion, and the one next move says so.
`pass` with `not_applicable` completes only with an explicit compatible routing
status from the operating tool; being the last slice is never sufficient. The
objective status owns no route: routing is the operating tool's dimension. No
objective line appears inside `## Verdict`.

Machine reading of the record is section-local and line-based: a report
contains exactly one line starting with `## Closure Decision` and exactly one
starting with `## Verdict` anywhere in the file (so never quote those heading
lines in an example, fenced or not); the closure section is the two lines
between them, and the verdict footer is the first non-empty line after the
verdict heading. Lines elsewhere are not authority and are not counted.

The reviewer also confirms the coder wrote only paths the coding prompt's write
manifest assigns to the coder; a coder-written review report, verdict record,
acceptance state, or routing state is a P1 authority finding
(`docs/template_framework/slice_prompt_contract.md`).

End every review report with a `## Verdict` section whose ATX heading text is
exactly `Verdict`. Its first non-empty line must be exactly
`Verdict: <value> - next: <one move>`, where `<value>` is exactly one of
`pass`, `needs_work`, `blocked`, or `override`. Use one chosen value, never the
list of choices. Use ASCII space-hyphen-space followed by lowercase `next:`
and one space; an em dash or en dash is rejected. Put nothing between the
value and separator, and make the one move non-empty.

A review report file carries exactly one `## Verdict` section. A later
round's review goes to its own round-qualified file
(`..._roundN_review_report.md` or the prompt-declared path); never
append a second verdict section to an existing report.
