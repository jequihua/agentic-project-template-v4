# Ladder Scenario: Fourth Round With Human Authorization And A Changed Method

After reassessment, the human owner explicitly authorizes continuing with a
revised method. Legal at round 4.

| invariant | prompt | response | guard_or_reason | human_aware | human_authorized | reset_reason | expected_round | expected_legal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| incomplete-inventory-count | p050 | narrow-correction | no | no | no | none | 1 | yes |
| incomplete-inventory-count | p051 | correction-with-guard | yes | no | no | none | 2 | yes |
| incomplete-inventory-count | p052 | architect-reassessment | no | yes | no | none | 3 | yes |
| incomplete-inventory-count | p053 | revised-method-correction | yes | yes | yes | none | 4 | yes |
