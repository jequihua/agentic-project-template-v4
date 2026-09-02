# Envelope Fixture: Slice Coding Prompt (Excerpt)

The acceptance envelope for the fixture findings in `findings.md`: Task,
Non-Goals, Verification, Definition Of Done, plus the baseline safety rails
defined in `docs/template_framework/closure_convergence.md`.

## Task

Implement `fit` and `predict` for simple linear regression.

## Non-Goals

- polynomial regression;
- plotting.

## Verification

- unit tests for fit/predict;
- ValueError on mismatched input lengths.

## Definition Of Done

- fit/predict correct on the fixture dataset;
- mismatched-length inputs raise ValueError;
- tests added and passing.
