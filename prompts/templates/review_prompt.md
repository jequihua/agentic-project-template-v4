# Review prompt: {{slice_id}} — {{title}} (round {{round}})

Read `AGENTS.md` first. Do not change product files. Use the receipt as execution
evidence; do not rerun verification unless this prompt explicitly says so.

## Objective and acceptance

{{objective}}

{{acceptance}}

## Changed files

{{diff_manifest}}

## Code diff

{{diff_evidence}}

## Coder notes

{{coder_notes}}

## Verification receipt

{{receipt}}

## Prior findings

{{prior_findings}}

## Output

Autonomous seats return the complete report for the runner to save. In manual
mode, write only `{{report_path}}` when that tool is granted, or return it for
the architect to save.

Use this exact contract:

```markdown
# Review: {{slice_id}} round {{round}}

## Findings
| id | severity | disposition | summary |
| --- | --- | --- | --- |

## Closure Decision
Objective status: achieved | not_achieved | indeterminate
Objective evidence: one sentence tied to acceptance and the receipt

## Verdict
Verdict: pass|needs_work|blocked - next: one move
```

Use one allowed value on each choice line. A pass requires zero open P0-P2.
{{finding_id_rule}}
