# Fixture: Finding-Disposition Lifecycle Cases

Table-driven cases for the role-authority rule in
`05_governance/current/review_protocol.md` (Finding Disposition Lifecycle).
Each row is one attempted disposition recording; `expected` says whether the
actor holds that authority. The final two rows exercise the fast-close
routing decision for a pure attribution defect versus a substantive change.

| case | actor | action | target_state | expected |
| --- | --- | --- | --- | --- |
| coder claims a withdrawn finding as remediated closure | coder | record | withdrawn_by_reviewer | violation |
| coder supplies counter-evidence | coder | record | disputed_pending_review | legal |
| coder claims remediation as a claim only | coder | record | remediated_pending_review | legal |
| coder attempts to close own finding | coder | record | closed_by_review | violation |
| reviewer confirms remediation | reviewer | record | closed_by_review | legal |
| reviewer withdraws a materially wrong finding | reviewer | record | withdrawn_by_reviewer | legal |
| architect records withdrawal in reviewer role | architect | record | withdrawn_by_reviewer | legal |
| owner accepts unresolved risk | owner | record | accepted_risk_by_owner | legal |
| architect records the owner's acceptance decision | architect | record | accepted_risk_by_owner | legal |
| coder accepts risk on the owner's behalf | coder | record | accepted_risk_by_owner | violation |

| case | substantive_change | actor_objective_from_record | expected_route |
| --- | --- | --- | --- |
| attribution-only correction, five gates hold | no | yes | fast-close |
| correction changes a measured value | yes | yes | level-2-review |
| correct actor not derivable from any record | no | no | level-2-review |
