# Ledger and receipt contracts

## Ledger

`05_governance/ledger.jsonl` is append-only UTF-8/LF. Each line has schema
`frutlups.ledger/1`, UTC `t`, `ev`, and `by` (`human`, `architect`, or
`frutlups`). Malformed lines and unknown fields are refused.

| Event | Required event data |
| --- | --- |
| `prompt` | `slice`, `round`, prompt `path`, `sha`; optional dirty `baseline` changed objects |
| `artifact` | slice/milestone `scope`, positive round or `holistic`, `role`, `path`, `sha` |
| `coded` | `slice`, `round`, `changed` (`path`, `sha`, `kind`), optional notes/usage |
| `verified` | `slice`, `round`, receipt `receipt`, `sha`, `ok` |
| `reviewed` | `slice`, `round`, `report`, `sha`, `verdict`, open ids, optional usage |
| `accepted` | `slice`, `round`, optional already-known `commit` |
| `reopened` | `slice`, new `round`, non-empty `reason` |
| `unblocked` | blocked `slice`, next `round`, non-empty `reason`; human or architect only |
| `milestone_done` | `milestone`, optional `holistic_report` |
| `note` | non-empty `text`, optional `slice` |
| `stop` | `reason`, `detail`; frutlups only |

Changed kinds are `added`, `modified`, `deleted`, and `renamed`. Evidence SHA-256
uses bytes with every CRLF pair normalized to LF when no NUL byte is present;
NUL-containing data hashes byte-for-byte and lone CR bytes are unchanged. The
same rule applies to files and Git blobs. It does not rewrite files. Front-repo
projection hashes remain raw because they detect exact publication divergence.
A deletion hashes the pre-change Git blob; a rename records its destination.

Prompt, receipt, report, and `artifact` paths are immutable and re-hashed by
`ledger.py check`; optional notes must remain present. Product paths are mutable:
their latest `coded` identity must match unless the path has returned exactly to
its current HEAD blob or to absence when HEAD lacks it.

`artifact` is non-transitioning. A `review_prompt` belongs to a reviewing slice
at that round. `holistic_prompt` and `holistic_report` belong to a milestone that
is ready for holistic review; their round is `holistic`. Architects/frutlups
record prompts, and a human may record a holistic report. Folding validates
scope and timing without changing lifecycle state.

A prompt `baseline` uses the same path/SHA/kind objects as `changed`. Corrective
prompts automatically record exact same-slice artifacts and matching product
history plus the harness ledger/backlog. Unknown paths still refuse unless the
architect inspects and admits them with `--allow-dirty`. `coded` excludes an
entry only while all three values remain identical. CLI paths may normalize
backslashes and one leading `./`; stored paths stay strict repository-relative
POSIX paths.

## Fold

Events are applied in file order for each roadmap slice:

| Last relevant event | Derived step |
| --- | --- |
| none | `unstarted`, round 1 |
| `prompt(r)` | `coding` |
| `artifact` | no state change; validate review readiness |
| `coded(r)` | `verifying` |
| `verified(r, ok=false)` | `fix`; next prompt is r+1 |
| `verified(r, ok=true)` | `reviewing` |
| `reviewed(r, needs_work)` | `fix`; next prompt is r+1 |
| `reviewed(r, blocked)` | `blocked` |
| `unblocked(r+1)` | `fix` at r+1, preserving findings and the unblock reason |
| `reviewed(r, pass)` | `accept_pending` |
| `accepted(r)` | `accepted` |
| `reopened(new r)` | `fix` at new r |

Wrong/decreasing rounds, illegal transitions, and unknown ids are errors. Next
is the first open reopened slice, then the first non-accepted slice in the first
active milestone. A holistic milestone also requires `milestone_done`.

Corrective rounds count prompt events above round 1; transport retries do not.
Every candidate is validated and folded before append, so refusal changes no
ledger bytes.

## Verification receipt

Receipts are deterministic JSON objects shaped like:

```json
{"schema":"frutlups.receipt/1","slice":"M001-S01","round":1,"base_commit":"...","commands":[{"argv":["python","-m","pytest"],"exit":0}],"changed_files":[],"ok":true}
```

The slice override or `verification.full` argv runs without a shell from root.
`ok` requires exit 0, no timeout, and identical before/after Git status; a tree
may stay dirty and still pass. Tails are at most 4 KB, outside paths become
`<outside-repo>`, and secrets/environment values are not serialized. Writing and
append occur after the final snapshot.
Holistic range evidence takes `base_commit` from the first accepted slice's
successful receipt, so that receipt and its normalized identity must remain
portable and immutable.

## Review grammar

A review has one findings table (`id`, `severity`, `disposition`, `summary`),
closure decision, and verdict section. Ids are unique; closure has one objective
status and one evidence line. The final verdict is:

`Verdict: pass|needs_work|blocked|override - next: <one move>`

`pass`/`override` refuse open P0-P2; only a human records `override`.

In a holistic report, every P0-P2 finding id begins with its affected slice id,
for example `M001-S02-H1-F1`. Open findings are grouped by slice and cause one
`reopened` event per slice, whose reason retains all grouped ids.

Slice review manifests are cumulative across coded rounds and mark current
versus earlier paths; their code diff remains current-round-only. Holistic
manifests are cumulative. Per-slice diffs appear only when the stat is at most
4 KB, there are at most 64 unique paths, and combined evidence stays within
32 KB; otherwise the prompt gives a local-inspection pointer.

## Stable status view

`ledger.py status` prints `M001-S01 r1 <step>` per slice and then `next`. frutlups
0.3 must match status, normalized hashing, artifacts, baselines, and lifecycle
folding. `ledger.py index` is generated; neither output is another state store.
