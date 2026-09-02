# Ladder Scenario: Healthy Convergence

One invariant, corrected narrowly, then guarded, then reassessed. Every
response is legal under the escalation ladder.

| invariant | prompt | response | guard_or_reason | human_aware | human_authorized | reset_reason | expected_round | expected_legal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stale-status-selector | p010 | narrow-correction | no | no | no | none | 1 | yes |
| stale-status-selector | p011 | correction-with-guard | yes | no | no | none | 2 | yes |
| stale-status-selector | p012 | architect-reassessment | no | yes | no | none | 3 | yes |
