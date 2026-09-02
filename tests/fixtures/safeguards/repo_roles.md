# Fixture: External Repository Roles — Drift Outcomes

Scenario table for the causal-role contract
(`docs/template_framework/external_repository_roles.md`). Each row is one
drift event observed during an evidence run; the expected column is the
contract's outcome. An undeclared repository has no role row in a prompt and
is out of scope by omission.

| repo | role | event | expected |
| --- | --- | --- | --- |
| checker-repo | authority_input | consumed-surface-drift | blocks-dependent-lane |
| checker-repo | authority_input | unconsumed-file-drift | no-block |
| target-repo | mutation_target | outside-envelope-overlap | blocks-closure |
| target-repo | mutation_target | inside-envelope-authorized-write | no-block |
| neighbor-repo | preservation_only | consumed-surface-drift | report-only |
| neighbor-repo | preservation_only | unconsumed-file-drift | report-only |
| unrelated-repo | undeclared | consumed-surface-drift | out-of-scope |
