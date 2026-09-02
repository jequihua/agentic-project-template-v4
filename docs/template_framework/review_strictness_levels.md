# Review Strictness Levels

Use one ceremony axis to decide prompt size, artifacts, review depth, and commit
expectations.

## Level 1 - Tiny Correction

Use for low-risk docs or count corrections.

Requires:
- compact note or checklist;
- no behavior, dependency, public contract, credential, or live-cost change;
- append-only correction if historical artifact is amended.

Use Level 1 only when the correction has one objectively verifiable value and a
focused diff can prove closure. Correct the operative text of a current
reference artifact in place; preserve the audit trail in an append-only
correction/review record. Do not create a new coding/review prompt family solely
for an eligible Level 1 correction.

## Level 2 - Corrective Repair

Use for one or two reviewed findings.

Requires:
- focused prompt;
- focused self-report;
- focused review;
- update only affected artifacts;
- on corrective round 2 or later, a Correction Scope Map in the prompt
  (`docs/template_framework/closure_convergence.md`).

## Level 3 - Normal Pass

Use for normal implementation, scaffold, or template pass.

Requires:
- coding prompt;
- self-report;
- review prompt or accepted review checklist;
- review report;
- verdict or closure decision.

## Level 4 - High-Risk / Directional

Use for architecture pivots, public contracts, credentials, live-cost work,
memory population, or legacy migration.

Requires:
- explicit human awareness;
- broader evidence;
- stronger review;
- clear rollback or stop conditions.

