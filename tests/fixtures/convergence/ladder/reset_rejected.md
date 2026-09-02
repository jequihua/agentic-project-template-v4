# Ladder Scenario: Renumbering Is Not A Reset Reason

A claimed reset justified only by renumbering is not honored; the count
continues, the occurrence is the third, and another corrective prompt is
illegal.

| invariant | prompt | response | guard_or_reason | human_aware | human_authorized | reset_reason | expected_round | expected_legal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| copied-live-prompt-number | p090 | narrow-correction | no | no | no | none | 1 | yes |
| copied-live-prompt-number | p091 | correction-with-guard | yes | no | no | none | 2 | yes |
| copied-live-prompt-number | p092 | corrective-prompt | no | no | no | renumbering | 3 | no |
