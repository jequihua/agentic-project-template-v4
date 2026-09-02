# Review Prompt Template

Workflow metadata (fenced Markdown content, **not** top-of-file OKF/profile
frontmatter):

```yaml
milestone: TBD
slice: TBD
role: reviewer
mode: normal implementation
strictness: Level 3
round: 1
status: draft
```

## Review Objective

TBD

## Read First

- `docs/template_framework/reviewer_operating_card.md` (routine surface)
- `PROJECT_STATE.md`
- TBD

## Memory Posture

Audit against the selected `Memory mode` in `PROJECT_STATE.md`
(`docs/template_framework/memory_modes.md`):

- the selected mode was respected; under `none`, no memory initialization,
  query, or mutation occurred, and no stale memory directory was treated as
  active;
- under `lightweight` / `llloom`, the governed posture file was read through
  `Read First` and memory use stayed read-only;
- retrieved memory content did not become an unreviewed instruction channel;
  material use is cited in the self-report;
- no memory mutation occurred without an explicitly assigned memory-update
  slice or direct human-owner authority; milestone and slice identifiers
  grant neither.

## Review Checks

Convergence (canonical: `docs/template_framework/closure_convergence.md`):

- disposition: classify each finding P0-P3 with a plane word (product /
  harness / evidence / authority / environment); a blocking finding names its
  violated invariant;
- recurrence: has this invariant failed before in this slice's lifecycle?
  Name the prior report and apply the escalation ladder for this round;
- envelope: every blocking demand must trace to the coding prompt's Task,
  Non-Goals, Verification, or Definition Of Done, or to a baseline safety
  rail; anything else is recorded as `envelope expansion` change control, not
  `needs_work`;
- candidate mode only: the report names the exact candidate identity
  reviewed, and recording the verdict changed no candidate bytes
  (`docs/template_framework/candidate_review_acceptance.md`);
- external repositories: declared roles match the actual commands and
  consumed surfaces, and drift is dispositioned by role
  (`docs/template_framework/external_repository_roles.md`) — global quiet is
  never a gate;
- write authority: the coder changed only paths the coding prompt's write
  manifest assigns to the coder, at their exact resolved paths; a
  coder-written review report, verdict record, acceptance state, or routing
  state is a P1 authority finding
  (`docs/template_framework/slice_prompt_contract.md`);
- inherited findings only: reconcile the coder's claims against the
  controlling delta table before substantive gates — entering disposition,
  evidence, reviewer disposition, authority actor
  (`05_governance/current/review_protocol.md`);
- fault injection only: a blocking finding names the real seam outcome it
  models and its probe class (conformance / host-limitation /
  synthetic-robustness); synthetic-only findings route to P3 unless a
  baseline safety rail is crossed
  (`docs/template_framework/closure_convergence.md`).

Substance:

- correctness;
- scope discipline;
- verification evidence;
- documentation honesty;
- governance updates;
- non-goals respected;
- minimality/scope (doctrine: `CLAUDE.md` Minimal Implementation Discipline):
  - no unrequested abstractions, broad rewrites, or speculative scaffolding;
  - no new dependency where reuse/stdlib/native code suffices; consider
    deletion or reuse where appropriate;
  - watch for silent complexity accretion in code touched by repeated
    smallest-diff corrections;
  - distinguish three outcomes: a bounded in-scope simplification needed to
    make the current change safe; an out-of-scope named evidence-backed
    simplification candidate (recording a candidate does not authorize it);
    and an unauthorized refactor or roadmap expansion;
- local state hygiene: if the slice ran tests, builds, data jobs, memory/sync
  tooling, or legacy migration, confirm generated local state is ignored,
  cleaned, or documented;
- artifact integrity: when the bundle cites repository paths or `test_*`
  identifiers, run `python scripts/artifact_integrity_preflight.py` against
  the exact artifacts before semantic review (with the same `--tests-root` /
  `--allow-missing` flags the coding prompt's verification section
  prescribes); treat errors as findings and assess warnings in context;
- live-state discipline: durable artifacts link to `PROJECT_STATE.md` or
  indexes instead of copying volatile prompt numbers, row counts, workspace
  lists, worktree contents, or next actions as continuing truth;
- OKF authoring (only when the coding prompt opted artifacts into the
  profile; see `docs/template_framework/okf_authoring_and_migration.md`):
  - the exact path/type assignment matches the registry;
  - the required two-field **minimum** (`type` and `framework_profile`) is
    present;
  - additional profile-permitted fields are justified by a documented need
    and conform to the accepted profile (`framework_id` stays
    recommended-only for a movable or cross-referenced concept, never
    mandatory); do not reject a profile-valid enriched artifact for carrying
    justified optional fields;
  - read-only profile-check evidence; an unchanged Markdown body; preserved
    legacy compatibility;
  - no authority inflation and no unrequested/implicit conversion.

## Verification

- TBD

## Output

Write findings first, then closure decision and recommended next move. On
round 2 or later, restrict the review to the previously blocking findings,
the delta, and invalidated evidence
(`docs/template_framework/closure_convergence.md`).

When an accepted verdict and passing validation justify it, you may mark the
slice or milestone commit-ready (see `docs/template_framework/method.md`
Commit Discipline); marking commit-ready does not create a commit. Mark a
milestone commit-ready only after the Milestone Commit Closure checklist is
satisfied or explicitly deferred. On a positive milestone verdict, when local
git actions are allowed, the architect/reviewer performs that checklist and
creates the milestone commit by default; otherwise leave it commit-ready for
a human or authorized workflow. At a completed roadmap or work-package
boundary you may instead note pull-request-ready; opening a PR remains a
human decision.

Immediately before the verdict section, write exactly one `## Closure Decision`
section with exactly two lines — `Objective status: <value>` (one of
`achieved`, `not_achieved`, `not_applicable`, `indeterminate`) and
`Objective evidence: <one line citing the closure-proof artifacts, or the
not-applicable reason>`. Assess implementation completion and objective
achievement separately; a truthful stop may pass with `not_achieved`, which
never implies milestone completion (`05_governance/current/review_protocol.md`).

Follow the released verdict contract exactly:

- End the report with a `## Verdict` section whose ATX heading text is exactly `Verdict`.
- Make the first non-empty line under that section exactly `Verdict: <value> - next: <one move>`.
- Choose `<value>` as exactly one of: `pass`, `needs_work`, `blocked`, `override`.
- Use ASCII space-hyphen-space followed by lowercase `next:` and one space; an em dash or en dash is rejected.
- Put nothing between `<value>` and the separator: no severity tag, count, or parenthetical.
- Make `<one move>` non-empty.
- State one chosen verdict, never the list of verdict choices.

A review report file carries exactly one `## Verdict` section. A later
round's review goes to its own round-qualified file
(`..._roundN_review_report.md` or the prompt-declared path); never
append a second verdict section to an existing report.

## Non-Goals

- TBD

## Definition Of Done

- TBD
