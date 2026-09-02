# Ladder Scenario: Unrelated Findings Do Not Share A Count

A second finding with a different violated invariant starts its own lifecycle
at round 1, even though it is the second report in the slice.

| invariant | prompt | response | guard_or_reason | human_aware | human_authorized | reset_reason | expected_round | expected_legal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stale-status-selector | p060 | narrow-correction | no | no | no | none | 1 | yes |
| unsafe-fixed-home-cleanup | p061 | narrow-correction | no | no | no | none | 1 | yes |
