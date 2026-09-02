# Ladder Scenario: Renamed Prompt Does Not Reset The Count

The same invariant reappears under a new prompt number. The count follows the
invariant, so the second occurrence still requires a guard; another bare
narrow correction is illegal.

| invariant | prompt | response | guard_or_reason | human_aware | human_authorized | reset_reason | expected_round | expected_legal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| self-certifying-provenance | p070 | narrow-correction | no | no | no | none | 1 | yes |
| self-certifying-provenance | p099 | narrow-correction | no | no | no | none | 2 | no |
