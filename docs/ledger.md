# Ledger and receipt contracts

`05_governance/ledger.jsonl` is append-only UTF-8. Each event has `schema`, UTC
`t`, `ev`, and `by` (`human`, `architect`, or `frutlups`). Unknown fields and
malformed lines are refused. The writer uses `frutlups.ledger/2` under a
`frutlups.roadmap/2` roadmap. Readers also accept legacy `/1` history followed by
`/2`; they never rewrite old evidence or allow `/1` after `/2`. Exact new fields,
actor rules and examples live in [the protocol contract](contracts.md).

## Ordinary events and evidence

| Event | Recorded evidence |
| --- | --- |
| `prompt` | Slice/round, prompt path/hash, frozen envelope reference; optional exact dirty baseline. |
| `coded` | Current changed paths, cumulative manifest, implemented or blocked result; optional bound notes/outcome. |
| `verified` | Receipt path/hash and execution result. |
| `reviewed` | Report path/hash, verdict and open finding IDs. |
| `accepted` | Slice approval; optional requested commit intent. |
| `artifact` | Hash-bound review prompt, holistic report or supporting evidence; no lifecycle transition. |
| `reopened` | Authorized new corrective round with a reason. |
| `resolved` | Human/architect resolution with bound authority/environment references. |
| `milestone_done` | Milestone closure; optional requested commit intent. |

Changed kinds remain `added`, `modified`, `deleted`, and `renamed`. Framework
SHA-256 normalizes CRLF to LF when no NUL exists; lone CR and binary bytes remain
unchanged. Raw product manifests need project-owned Git storage checks.

A `/2` manifest contains cumulative `path,sha,kind,round` rows. Notes require both `notes_path` and `notes_sha`.
Prompt/receipt/report/manifest/outcome and supporting artifacts are immutable.
`ledger.py check` checks their references. Active verification/review/acceptance
also rejects product drift after the coded handoff. Historical completed Git
witnesses validate their committed blobs rather than today's mutable worktree.

Corrective prompts baseline known evidence. Unknown dirty state needs explicit
architect attribution; no event authorizes cleanup. Stored paths remain contained
repository-relative POSIX paths. See [operating](operating.md) for CLI details.

## Derived state

| Last relevant event | Slice step |
| --- | --- |
| None | `unstarted`, round 1 |
| `prompt(r)` | `coding` |
| Implemented `coded(r)` | `verifying` |
| Blocked `coded(r)` or blocked review | `blocked` |
| Failed verification or needs-work review | `fix`, next round |
| Successful verification | `reviewing` |
| Passing review | `accept_pending` |
| Acceptance | `accepted` |
| Authorized reopen or blocker resolution | `fix`, next round |

Approval and requested Git completion are distinct. Ledger-only acceptance is
sufficient when no commit was requested. Pending commit intent freezes other
writes until exact recovery or authorized cancellation. Read-only `recover`
diagnoses; `recover --execute` recognizes the existing witness or finishes only
the missing Git work. Completion needs no append that dirties the ledger again.
See [the recovery commands](upgrading.md) for unknown ownership and cancellation.

A `/2` holistic report persists `holistic_reviewed`. Needs-work reopens its
explicitly affected slices; blocked requires resolution; pass leaves
`close_pending` until `close`. Re-recording the same decision does not rerun
review or duplicate reopen events. Legacy `/1` histories retain their prior
holistic and `unblocked` grammar.

Wrong rounds, unknown IDs and illegal transitions refuse before append. Next
suggests an open reopened slice first, otherwise a nonaccepted slice in an active
milestone. Manual architects may deliberately select another active slice before
earlier holistic closure; an autonomous runner must enforce its own admitted
run boundary. Status/index are generated views, never authority.

## Verification receipts

`frutlups.receipt/2` references the canonical manifest instead of repeating the
changed-path list. Legacy `/1` inline `changed_files` receipts remain readable.
The frozen full argv runs without a shell using the selected project runtime.
`ok` requires successful commands, no timeout and equal content/type/index/HEAD
snapshots. A dirty-but-unchanged baseline may pass; mutation of an already-dirty
file may not. Ignored scratch and the wider host remain outside that witness.

Sanitized output tails are bounded; portable runtime and observation metadata
state what the maintained command witnesses. `fresh_process` or `clean_checkout`
is a project declaration that the actual command must substantiate, not an
inferred claim. [Project checks](project_checks.md) cover discovery, dependencies,
raw storage and the documented prepare/exit/serve path. Holistic accepted-range
evidence uses the first accepted receipt's immutable `base_commit`.

## Review and finding grammar

A report has a findings table (`id,severity,disposition,summary`), one closure
decision and exactly one `Verdict: pass|needs_work|blocked|override - next: ...`.
Pass/override refuse open P0-P2. Only human may record an override or waiver.
Rows split on unescaped pipes; `\|` means a literal pipe in the summary.
Holistic P0-P2 IDs begin with the affected slice ID.

An optional `/2` Finding updates table identifies the original report path/hash
and exact finding ID. Explicit dispositions drive the generated backlog region;
an unrelated pass never closes an old finding. `reconcile` rebuilds that region
without changing historical reports or architect prose. The complete table
contract is in [contracts](contracts.md).

Prompts contain the complete frozen envelope and concise evidence references.
Source/config/test changes precede bulk artifacts. Ordinary diffs are HEAD diffs
filtered to current-round paths, not true prior-round deltas. Manifests remain
cumulative. Bounded diff pages can be read with file tools; no shell is required.
Coding/review caps are 16/48 KiB UTF-8, including custom framing. Mandatory
instructions are never truncated. `prompt.py --preview` makes the actual text
reviewable without reserving a name or writing evidence.
