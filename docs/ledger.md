# Ledger and receipt contracts

`05_governance/ledger.jsonl` is append-only UTF-8. Events have `schema`, UTC
`t`, `ev`, and `by` (`human`, `architect`, or `frutlups`). Unknown fields and
malformed lines refuse. A `frutlups.roadmap/2` roadmap uses the `frutlups.ledger/2`
writer. Readers accept legacy `/1` followed by `/2`, without rewriting evidence
or allowing `/1` after `/2`. [Contracts](contracts.md) defines fields, actor rules
and examples.

## Events and evidence

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

Change kinds: `added`, `modified`, `deleted`, and `renamed`. Framework
SHA-256 normalizes CRLF to LF when no NUL exists; lone CR and binary bytes remain
unchanged. Raw manifests need project-owned Git storage checks.

A `/2` manifest contains cumulative `path,sha,kind,round` rows. Notes bind `notes_path` and `notes_sha`.
Prompt/receipt/report/manifest/outcome and supporting artifacts are immutable;
`ledger.py check` validates their references. Active verification/review/acceptance
also rejects product drift after coding. Historical completed Git witnesses
validate committed blobs rather than today's worktree.

Corrective prompts baseline known evidence. Unknown dirty state needs explicit
architect attribution; no event authorizes cleanup. Paths are contained,
repository-relative POSIX paths. See [CLI details](operating.md).

Even ledger-only manual HEAD fallback batches the full committed tree, subject
to the existing 8 MiB metadata limit and safe UTF-8 paths. Unrelated invalid
entries or overflow refuse. Absent paths, directories and confirmed unborn
branches have no exact HEAD blob. A directory-to-file replacement needs explicit
`--allow-dirty` attribution. Broken refs or unavailable objects refuse. Hashes
remain normalized; fallback does not prove executable mode or raw storage.

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

Approval and Git completion are distinct. Ledger-only acceptance suffices when
no commit was requested. Pending intent freezes other writes until exact recovery
or authorized cancellation. Read-only `recover` diagnoses; `recover --execute`
recognizes an existing witness or finishes the missing Git work, without another
ledger append. See [recovery](upgrading.md) for unknown ownership and cancellation.

A `/2` holistic report persists `holistic_reviewed`. Needs-work reopens explicitly
affected slices; blocked requires resolution; pass leaves `close_pending` until
`close`. Re-recording a decision neither reruns review nor duplicates reopen
events. Legacy `/1` retains its holistic and `unblocked` grammar.

Wrong rounds, unknown IDs and illegal transitions refuse before append. Next
prefers an open reopened slice, then a nonaccepted slice in an active milestone.
Manual architects may select another active slice before earlier holistic
closure; autonomous runners must enforce their admitted run boundary. Status/index
are generated views, never authority.

## Verification receipts

`frutlups.receipt/2` references the canonical manifest; legacy `/1` inline
`changed_files` receipts remain readable. The frozen full argv runs without a
shell in the selected project runtime. `ok` requires successful commands, no
timeout and equal content/type/index/HEAD snapshots. An unchanged dirty baseline
may pass; an already-dirty file's mutation may not. Ignored scratch and the wider
host are outside that witness.

Output tails are sanitized and bounded. Portable runtime and observation metadata
state the command's witness; the command must substantiate declared
`fresh_process` or `clean_checkout` observations. [Project checks](project_checks.md)
cover discovery, dependencies, raw storage and the documented prepare/exit/serve
path. Holistic ranges use the first accepted receipt's immutable `base_commit`.

## Review and finding grammar

A report has a findings table (`id,severity,disposition,summary`), one closure
decision and exactly one `Verdict: pass|needs_work|blocked|override - next: ...`.
Pass/override refuse open P0-P2. Only human may record an override or waiver.
Rows split on unescaped pipes; `\|` means a literal pipe in the summary.
Holistic P0-P2 IDs begin with the affected slice ID.

The optional `/2` Finding updates table binds the original report path/hash and
exact finding ID. Explicit dispositions drive the generated backlog; unrelated
passes never close old findings. `reconcile` rebuilds that region without changing
historical reports or architect prose. See [contracts](contracts.md).

Prompts contain the complete frozen envelope and concise evidence references.
Source/config/tests precede bulk artifacts. Ordinary diffs filter HEAD changes
to current-round paths, not prior-round deltas; manifests remain cumulative.
Bounded diff pages need only file tools. Coding/review caps are 16/48 KiB UTF-8,
including custom framing; mandatory instructions are never truncated.
`prompt.py --preview` shows actual text without reserving names or writing evidence.

Optional [run admission](autonomy.md) adds `ledger.py run admit|extend` and balances
to status. Ordinary manual work requires no autonomous profile or run records.
