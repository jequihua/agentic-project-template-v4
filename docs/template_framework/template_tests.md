# Template Tests

Scaffold tests guard the template's rails. They are intentionally small,
structural, and fast. They are not a validation framework and must not pretend
the template is finished.

Run them with the command in `PROJECT_STATE.md`:

    python -m unittest discover -s tests

## What Belongs In A Scaffold Test

Test structural invariants and contracts, not prose:

- required files / docs exist;
- a contract and the file it governs do not drift (for example the
  `PROJECT_STATE` field contract vs `PROJECT_STATE.md`, or the self-report schema
  vs its onboarding copy);
- a single source of truth is actually referenced, not re-stated;
- controlled field values stay within their allowed set;
- workspace activation is explicit (active or inactive, never ambiguous);
- optional tools (llloom, frutlups) are never imported by the test suite.

## What Stays Documentation-Only

- philosophy, rationale, and guidance prose;
- anything that requires human judgment to evaluate;
- long narrative that would turn a test into a paragraph snapshot.

## Avoiding Brittle Tests

- check structure or classification, not exact wording, so harmless rewording
  does not break the suite;
- when a phrase is checked, it must protect a load-bearing guarantee (for example
  `append-only`, or `no runner is implemented`);
- match real import statements (line-anchored), not arbitrary mentions, so a
  guard does not flag its own assertion text;
- never assert a value a legitimate project would change (for example do not
  hard-assert `Memory mode: none`); assert membership in the allowed set instead,
  so the test stays downstream-safe.

## Clone-Only Tests And Template-Source Purity

One check protects the template as shipped, not a project built from it: the
shipped `Memory mode: none` default. It is scoped by the scaffold's own
`Status` line - it runs while `PROJECT_STATE.md` still says
`Status: initialized template scaffold` and reports as skipped, never as a
failure, once framework initialization replaces it.

The template-source purity checks (no machine-local paths, binary-safe LF)
run in every project. They walk only the template-owned surfaces declared
under `template_owned_surfaces` in `frutlups.layout.yaml` and skip the
governed local surfaces (`.frutlups_drive/`, `local_state/`), so a run store
or an imported corpus never trips them while the same defect in distributable
source still fails; a guard test proves both directions. Project invariants
over reviewed artifacts are the artifact preflight's job and stay
unconditional.

## Losslessness Is Equality, Not Parsing

A rendered contract-v1 prompt carries its sidecar entry verbatim in a fenced
YAML block (`Typed Entry`). The reference checker proves losslessness by
strict-loading that block and comparing it to the attempt-resolved entry by
equality; the test suite mutates every leaf of the block (delete, alter,
duplicate into a second block) and asserts refusal. No test parses Markdown
prose for field values, and no test or script parses CommonMark fences: the
closure record and the workflow status are read by total, line-based rules.
Two prose rails stay authority-bearing and are checked exactly rather than
by presence: the status line (plain spelling, agreement, declared by both
carriers) and the Write Manifest rows with the Self-Report path (exact
cardinality); section order follows the layout's `rendered_section_order`.
The suite falsifies each: quoted, tagged, block-scalar, and flow status
spellings in both directions, extra and duplicate rows, and every canonical
rendering with its last section moved first.

## Fixture Corpora And The Artifact Preflight

Fixture corpora under `tests/fixtures/` are exempt from the artifact-integrity
preflight by policy: adversarial fixtures intentionally carry unresolved
sentinels, fictional repository paths, and deleted-section residue, and a
preflight run over them reports exactly those intended defects. The
preflight's acceptance domain for a change is the changed non-fixture
Markdown; fixture corpora are scanned by their own tests (UTF-8, LF, no
machine-local paths, digest parity) instead.

## Optional Tools Must Not Be Imported

The suite must run without llloom or frutlups installed. A shared helper checks
that no `test_*.py` imports either tool. This keeps the template usable by
projects that never enable an optional lane.

## Adversarial Checks Belong In Reviews

Existence tests prove a guard is present; reviews prove it has teeth. A review
should temporarily break an invariant (drop a required field, add a forbidden
import) and confirm the matching test fails, then restore. This "verify, do not
trust" step lives in the review prompt, not in the committed suite.

## Reporting Test Changes

In a self-report, state the old and new test count (for example "16 -> 18") and
what each new or changed test protects. If a test was made stricter or a helper
was extracted, say so and why.
