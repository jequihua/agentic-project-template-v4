# Ladder Scenario: Fourth Round Without Human Authorization

After reassessment, a fourth same-invariant correction continues without
explicit human authorization. Illegal at round 4.

| invariant | prompt | response | guard_or_reason | human_aware | human_authorized | reset_reason | expected_round | expected_legal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| incomplete-inventory-count | p040 | narrow-correction | no | no | no | none | 1 | yes |
| incomplete-inventory-count | p041 | correction-with-guard | yes | no | no | none | 2 | yes |
| incomplete-inventory-count | p042 | architect-reassessment | no | yes | no | none | 3 | yes |
| incomplete-inventory-count | p043 | corrective-prompt | no | no | no | none | 4 | no |
