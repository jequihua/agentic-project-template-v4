# Reviewer Operating Card

Routine surface for running one review. `PROJECT_STATE.md` is the only
live-state source — this card copies none of it.

## Normal review

1. Read `PROJECT_STATE.md`, the coding prompt under review, the coder
   self-report, and the changed files — nothing else by default.
2. When the bundle cites repository paths or `test_*` identifiers, run
   `python scripts/artifact_integrity_preflight.py` on the exact artifacts
   before semantic review.
3. In human-ledger projects, check the round in the `Round` column of
   `05_governance/reviews/INDEX.md`. On round 2 or later, review only the
   previously blocking findings, the delta, and invalidated evidence.
4. Judge substance against the acceptance envelope: the prompt's Task,
   Non-Goals, Verification, and Definition Of Done, plus baseline safety
   rails. You may not widen the envelope — record a newly desired property
   as `envelope expansion` change control for the architect.
5. Classify every finding P0-P3 with a plane word (product / harness /
   evidence / authority / environment); a blocking finding names its
   violated invariant (table: `05_governance/current/review_protocol.md`).
6. Check recurrence: has this invariant failed before in this slice's
   lifecycle? Name the prior report and apply the escalation ladder
   (`docs/template_framework/closure_convergence.md`).
7. Write findings-first output: confirmed issues by severity; scope
   discipline; verification performed; documentation and governance
   honesty; closure decision as a `## Closure Decision` section carrying
   `Objective status:` and `Objective evidence:` (objective achievement is
   judged separately from the implementation verdict); exactly one
   recommended next move.
8. End with a `## Verdict` section whose ATX heading text is exactly
   `Verdict`. Its first non-empty line must be exactly
   `Verdict: <value> - next: <one move>`, where `<value>` is exactly one of
   `pass`, `needs_work`, `blocked`, or `override`. Use one chosen value, never
   the list of choices. Use ASCII space-hyphen-space followed by lowercase
   `next:` and one space; an em dash or en dash is rejected. Put nothing
   between the value and separator, and make the one move non-empty.
   One verdict section per file; later rounds use their own
   round-qualified file.
9. Human reviewers/architects only: update
   `05_governance/reviews/INDEX.md` when the report and verdict exist.
   Autonomous seats never write the INDEX; in a declared `no-ledger`
   project it stays empty by design.

## Hard rules

- Unresolved P0-P2 never coexists with `pass`; a P3 may accompany `pass` as
  a named follow-up. Uncertain severity stays P2.
- One verdict, one next move — never a menu.
- Candidate mode only: name the exact candidate identity reviewed, and
  recording the verdict must change no candidate bytes
  (`docs/template_framework/candidate_review_acceptance.md`).
- A universal term (`all`, `every`, `no path`, `exact`, `independent`) in
  blocking evidence needs a bounded domain and an independent falsifier;
  if the domain cannot be bounded, narrow the claim.
- External repositories block only through their declared causal role;
  preservation-only drift is reported, never a gate
  (`docs/template_framework/external_repository_roles.md`).
- You answer the materiality questions before P1/P2 — never the implementer;
  a blocking fault-injection finding names the real seam outcome it models.
- Finding dispositions are role-owned: the coder remediates or challenges;
  you withdraw or close; the owner accepts risk.

## Escalate instead of improvising

- the third same-invariant recurrence, or corrections that keep enlarging
  the assurance harness;
- a powerful harness (deletes, installs, signals, or mutates environment)
  inside the evidence;
- a candidate identity mismatch;
- anything on the architect card's escalation list (contracts, credentials,
  live cost, execution semantics).

## Deeper sources

- Convergence contract: `docs/template_framework/closure_convergence.md`.
- Disposition table and output shape:
  `05_governance/current/review_protocol.md`.
- Strictness levels: `docs/template_framework/review_strictness_levels.md`.
- Candidate lifecycle:
  `docs/template_framework/candidate_review_acceptance.md`.
- Live state: `PROJECT_STATE.md`.
