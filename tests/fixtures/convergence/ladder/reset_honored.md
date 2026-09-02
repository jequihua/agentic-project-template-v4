# Ladder Scenario: Accepted Guard Plus Confirming Review Resets The Count

An accepted durable guard covering the invariant, confirmed by the next
independent review, resets the lifecycle: the later occurrence is a fresh
round 1.

| invariant | prompt | response | guard_or_reason | human_aware | human_authorized | reset_reason | expected_round | expected_legal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stale-status-selector | p080 | narrow-correction | no | no | no | none | 1 | yes |
| stale-status-selector | p081 | correction-with-guard | yes | no | no | none | 2 | yes |
| stale-status-selector | p082 | narrow-correction | no | no | no | accepted-guard-confirmed | 1 | yes |
