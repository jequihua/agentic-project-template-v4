# Manual protocol 2 candidate

This is the template-owned contract for a manual candidate. frutlups 0.3.2 does
not support it. Paired runner conformance and the final live canary are pending;
no newer runner version is implied by a package number. Manual use requires only
Python 3.11+, PyYAML and Git. The roadmap schema itself is the static writer gate:
`frutlups.roadmap/2`. Old tools reject it before issuing work. `/1` projects retain
their old grammar. New readers accept a `/1` ledger prefix followed by `/2` events,
never a `/1` event after `/2`, and never `/2` under a `/1` roadmap. Upgrade by a
reviewed selective copy; do not rewrite historical bytes.

## References, versions and exclusion

All references are `{path, sha}`: a strict repository-relative POSIX regular file
and its 64-character lowercase SHA-256. Framework evidence hashes normalize CRLF
to LF only when no NUL exists; lone CR and binary bytes are unchanged. CLI inputs
may normalize backslashes and one leading `./`. Unknown keys are errors. Events
remain bounded JSON objects, one per line, with `schema`, UTC `t`, `ev`, `by`.
The version-2 schema is `frutlups.ledger/2`; legacy fields retain their meanings.

Each mutation owns byte 0 of `<git-common-dir>/frutlups-writer.lock`: Windows
`msvcrt.locking(LK_NBLCK, 1)` or POSIX `flock(LOCK_EX|LOCK_NB)`, held through all
artifact/ledger/Git effects. The file contains one arbitrary byte; its existence
is not authority. A process may reenter its own lock. Compatible runners hold the
same lock for the whole run. Status takes no lock and may observe a stable prefix
while a writer is working. Do not kill another owner.

## Immutable envelopes and evidence

A `/2 prompt` adds `envelope: {path,sha}`. The envelope artifact has schema
`frutlups.envelope/2` and freezes the slice/round, objective, acceptance, non-goals,
read-first, effective allowed/forbidden paths, focused/full argv, advisory notes,
prior findings and resolution. Review uses that recorded envelope. Roadmap edits
cannot silently change the acceptance envelope of issued work.

A `/2 coded` retains `changed` for the current round and adds `result`
(`implemented|blocked_authority|blocked_environment`) and `manifest: {path,sha}`.
The manifest is `frutlups.manifest/2`, with `slice`, `round`, and cumulative
`changed` rows containing `path,sha,kind,round`. Optional `notes_path` requires
`notes_sha`. Optional `outcome` is a reference. Supporting `artifact` events may
use role `evidence`; they change no lifecycle state. Every bound reference is
immutable and belongs to the accepted commit payload.

A reopened slice re-observes previously owned paths when an intervening slice
changed them, including changes already committed to HEAD. Record that current
identity in the new round; it does not rewrite or reattribute historical events.
At milestone closure, latest globally recorded identities supersede earlier
accepted-slice file identities while old committed witnesses retain their own
historical meaning.

`frutlups.receipt/2` replaces repeated `changed_files` with the same `manifest`
reference. `witness` has exact fields `before,after,stable,head,index,product`:
before/after are canonical complete snapshot hashes; head is the observed commit,
index hashes staged entries/modes/flags, and product hashes raw file/type/mode
identities excluding exact ledger/backlog, roadmap and bound evidence paths.
Recorded artifact writes can follow verification without hiding product drift.
The receipt also records portable runtime identity and observation mode. The rest of the `/1` receipt fields retain their
meaning. `ok` requires successful execution and equal snapshots, including files
already dirty before verification. Git-owned tracked and untracked nonignored
files are witnessed; ignored scratch is outside that claim.

Coding/review prompts are at most 16/48 KiB UTF-8 including framing. Complete
manifests and bounded readable diff pages are referenced, not repeated. Source,
configuration and tests precede bulk evidence in inline selection. A HEAD diff
filtered to this round's paths is labeled exactly that, not a prior-round diff.
Oversized mandatory scope refuses issuance; it is never truncated. Preview uses
the same renderer without reserving names, writing files or appending events.

## Outcomes and resolution

Autonomous coding returns an outcome object, schema `frutlups.outcome/2`, bounded
to 16 KiB. Exact keys are `schema,slice,round,invocation,outcome,requirement,reason,
actor,action,remaining,evidence,authority`. `remaining` is a string list, `evidence`
is a reference list, `authority` contains relative decision/budget paths. The
three outcomes match `coded.result`. `requirement` and `reason` are nonempty;
blocked outcomes also require actor/action. Implemented work may use empty
actor/action. No outcome is inferred from enthusiastic prose.

Manual `coded` remains the ordinary implemented handoff; notes are optional.
`blocked` explicitly supplies the blocker fields or a saved outcome. Both paths
validate edits against the same fence. A blocked result enters `blocked` without
automatic verification. `resolved` has `scope,reason,authority` (bound references)
and is human/architect only; it moves a blocked slice to the next corrective
round, preserving the original blocker and resolution. It grants only the recorded
authority, not a new model/domain budget. Zero changed files can be implemented.
Autonomous format repair may read the original output once; it may never repeat
the writable coder or scientific commands just to repair formatting.

## Commit intent and witness

`accepted` or `milestone_done` may add `commit_intent`, in the same approval
append: `{id,parent,manifest,message}`. No intent means ledger-only approval.
The operation id is 32 lowercase hexadecimal characters; parent is a full Git object id;
manifest is a bound `frutlups.commit-manifest/1` artifact. It pins `id,scope,parent,
index_tree,entries,ledger,git_boundary`; entries contain `path,state,sha,storage,mode`, state
`file|deleted`, storage `normalized|raw`. Rename origin is a deletion row. The
manifest and ledger are implicit eligible paths, avoiding a self-hash. Ledger
metadata pins its previous normalized prefix. Current working ledger bytes are
preserved; Git must store exactly that prefix plus the ordered approval event
under the existing normalized-text rule.

Completion is a Git commit with `Template-Operation: <id>`, exact parent, actual
approved delta, matching blobs/modes and ledger prefix through approval. Unchanged
eligible files need not appear in the delta. The trailer only locates a candidate.
Validate historical witnesses from committed blobs, not today's worktree/index.
Subsequent legitimate descendants do not invalidate earlier completion. Lookup is
bounded and refuses missing history, duplicate witnesses and unexplained movement.

Pending intent freezes other ledger writes. Recovery first recognizes an existing
witness, otherwise stages and commits only the pinned payload. No new approval,
review, coder call or completion append occurs. Unrelated staged entries and
content/index drift refuse without cleanup. An unresolved local Git dispatch
marker requires explicit process attribution; a stale filename/PID proves no
process has ended. `--git-resolved --reason ...` is human/architect attribution,
not permission to kill a process.

`commit_cancelled` has `operation,reason,retain_acceptance`, human/architect only,
after no witness and any in-flight Git action is resolved. Only human may retain
ledger-only acceptance. Otherwise the scope is reopened for new verification and
review. Cancellation preserves approval, evidence and index; it authorizes no
reset, cleanup, changed-payload approval or fabricated completion.

Optional `/2 verification.git_boundary` is a nonmutating argv hook receiving
`TEMPLATE_CANDIDATE_TREE`. It validates project-owned raw manifests against that
tree; snapshots before/after must match. The commit manifest freezes `git_boundary`
as `null` or `{argv,timeout_seconds,runtime}`, with a portable `runtime` declaration
(`{}` or `{python: "3.x[.y]"}`). Recovery refuses a changed hook, timeout or runtime
policy, including adding/removing the hook; use cancellation and a new review.
Completed historical witnesses retain their original policy. Choose scoped `-text` before hashing
raw data. Generic projects need no hook. Historical raw evidence remains frozen;
current derived output uses a project-owned scratch regeneration check instead.

## Reviews, findings and checkpoints

The existing findings/closure/verdict grammar remains. A `/2` report may include
`## Finding updates` before Closure Decision, with columns
`source | sha | id | disposition | related`. Source is the original report path,
sha its normalized identity, id the original finding, disposition an existing
value, and related a comma-separated list of linked finding IDs (or `-`). Explicit
updates never implicitly close another linked finding. Unknown sources/IDs,
contradictory updates and ID collisions refuse; a passing unrelated report closes
nothing. Human-waiver checks apply to both rows and updates on every record path.
Only P3 findings may be carried. Unresolved findings retain their original report
scope even when an older ID lacks a slice prefix or a later report omits it.

The backlog's `<!-- findings:begin -->` / `<!-- findings:end -->` region is a
deterministic projection of recorded reports. Preserve all prose outside it. Old
free-text lines remain legacy notes. `reconcile` rebuilds a failed projection
without rerunning reviews or modifying historical evidence.

`holistic_reviewed` stores `milestone,report,sha,verdict,open`. Needs-work atomically
reopens grouped affected slices in the fold; blocked stops the milestone for an
explicit resolution; pass leaves `close_pending` until `milestone_done`. A replay
of an already-recorded report completes only its pending mechanical close. No
re-review or repeated reopen. Manual next-slice suggestion retains active-slice
flexibility; an autonomous run must separately pin and enforce its boundary.

`review_checkpoint` stores `invocation,scope,round,contract,report,sha,seat`.
`contract` hashes the complete envelope/product/baseline/prompt/route/seat/model/
effort/tools/parser binding. Reuse requires exact equality; changed bindings require
new review. Checkpoints preserve each routed report; a merge cannot erase them.

`attempt_started` stores `invocation,scope,round,role,contract,allowance_seconds,
retry` and optional `parent`; roles are coder/reviewer/holistic/probe, retries are
initial/transport/format. `attempt_finished` stores `invocation,status,usage` and
optional `reason,evidence`; status is completed/failed/resolved. Usage has only
known `secs,tokens_in,tokens_out,cost_usd` plus `completeness` (complete/partial/
unknown). Missing metrics are unknown, never zero. Invocation IDs are unique;
retry links must reference their prior invocation. An unfinished reservation
blocks new work even with a clean tree or lost local logs. Only human/architect
may resolve an unknown attempt, with reason and evidence. A format retry is
read-only; no writable coder is relaunched for formatting. Compatible runner
format repair keeps reviewer/holistic roles, or uses `probe` for a coder outcome;
it cannot turn that coder outcome into a review checkpoint. Compatible runner
admission/reservation limits remain runner-owned; ordinary manual use needs none
of these events.

## Qualification boundary

The template's synthetic corpus and tests specify locally executable semantics.
Old frutlups rejection is testable now. Matching new runner, per-seat adapter
capture, cross-mode interruption, persistent autonomous budgets and the exact-pair
live canary remain F20/F40/F41 gates. A manual candidate is not an autonomous
release. Never replace a project's verifier, decisions, custom templates or
accepted ledger with scaffold examples during upgrade.
