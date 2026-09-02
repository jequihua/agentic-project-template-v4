# Ledger and receipt contracts

## Ledger

`05_governance/ledger.jsonl` is UTF-8, LF, and append-only. Each non-empty line
is one compact JSON object with `schema: "frutlups.ledger/1"`, UTC ISO-8601 `t`,
`ev`, and `by` (`human`, `architect`, or `frutlups`). A malformed line invalidates
the ledger and reports its line number. Unknown event fields are refused.

| Event | Required event data |
| --- | --- |
| `prompt` | `slice`, `round`, prompt `path`, `sha` |
| `coded` | `slice`, `round`, `changed` objects (`path`, `sha`, `kind`), optional `notes_path`, seat/time/usage |
| `verified` | `slice`, `round`, receipt `receipt`, `sha`, `ok` |
| `reviewed` | `slice`, `round`, `report`, `sha`, `verdict`, open P0-P2 ids, optional seat/time/usage |
| `accepted` | `slice`, `round`, optional already-known `commit` |
| `reopened` | `slice`, new `round`, non-empty `reason` |
| `milestone_done` | `milestone`, optional `holistic_report` |
| `note` | non-empty `text`, optional `slice` |
| `stop` | `reason`, `detail`; frutlups only |

Changed kinds are `added`, `modified`, `deleted`, and `renamed`. Present files
use the SHA-256 of current bytes. A deletion hashes the pre-change Git blob. A
rename records the destination path and bytes. Git porcelain is parsed with NUL
delimiters; filenames are not workflow state.

Prompt, receipt, and report paths are immutable evidence and are always
re-hashed by `ledger.py check`; optional notes paths must remain present (their
event has no hash field). Product paths are mutable: check the most recent
`coded` reference for each path, and require deleted paths to remain absent.
This detects current drift without invalidating history when a later slice
legitimately changes the same file.

## Fold

Events are applied in file order for each roadmap slice:

| Last relevant event | Derived step |
| --- | --- |
| none | `unstarted`, round 1 |
| `prompt(r)` | `coding` |
| `coded(r)` | `verifying` |
| `verified(r, ok=false)` | `fix`; next prompt is r+1 |
| `verified(r, ok=true)` | `reviewing` |
| `reviewed(r, needs_work)` | `fix`; next prompt is r+1 |
| `reviewed(r, blocked)` | `blocked` |
| `reviewed(r, pass)` | `accept_pending` |
| `accepted(r)` | `accepted` |
| `reopened(new r)` | `fix` at new r |

Skipped or decreasing rounds, events in the wrong state, acceptance without a
pass/authorized override, reopening without acceptance, and unknown roadmap ids
are errors. The project next slice is the first reopened slice, otherwise the
first non-accepted slice in the first active milestone. A milestone is done when
all slices are accepted and, when holistic review is configured, a
`milestone_done` event exists.

Corrective rounds count prompt events above round 1 after failed verification or
needs-work. A same-round transport retry has no new prompt event.

## Verification receipt

Receipts are deterministic JSON objects:

```json
{"schema":"frutlups.receipt/1","slice":"M001-S01","round":1,"t":"...","base_commit":"abc123","tree_dirty_before":true,"commands":[{"label":"full","argv":["python","-m","pytest"],"exit":0,"secs":1.2,"stdout_tail":"","stderr_tail":"","timed_out":false}],"changed_files":[{"path":"07_app/x.py","sha":"...","kind":"modified"}],"tree_clean_after":false,"ok":true}
```

The authoritative command is the slice `verification` override or
`verification.full`. It is an argv list and runs with no shell from repository
root. `ok` requires exit 0, no timeout, and an identical Git-status snapshot
before and after command execution. The literal dirty/clean booleans describe
the whole worktree; an already-dirty but unchanged tree can produce `ok: true`.
Receipt writing and ledger append happen after the second snapshot.

Output tails are at most 4 KB each. Paths are repository-relative; outside paths
become `<outside-repo>`. Environment values and secrets are never serialized.

## Review grammar

A review has exactly one findings table, closure decision, and verdict section.
The four table columns are `id`, `severity`, `disposition`, and `summary`.
Finding ids are unique. Exactly one `Objective status:` and one non-empty
`Objective evidence:` line follow the closure heading. The first non-empty line
under the final verdict heading is:

`Verdict: pass|needs_work|blocked|override - next: <one move>`

`pass` and `override` are refused with open P0-P2. `override` may be recorded
only with `by=human`.

## Stable status view

`ledger.py status` prints one line per roadmap slice as
`M001-S01 r1 <step>` followed by `next: <slice-or-none>`. frutlups 0.3 must emit
the same text for the same roadmap and ledger. `ledger.py index` is a generated
Markdown table; neither output is another state store.
