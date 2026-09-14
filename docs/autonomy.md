# Optional autonomous run contract

Manual use needs no run records or frutlups installation. This optional contract
defines persistent runner allowance; paired qualification remains pending.

## Declaration and compatibility

Opt in only after matching runner qualification by adding to a `/2` roadmap:

```yaml
autonomy:
  schema: frutlups.autonomy/1
```

Old strict readers refuse this exact declaration before work. Ledger/roadmap
remain `/2`. Without the declaration, run events and verification attempts
refuse. Removing it cannot erase history. Config and run stores grant nothing.

Enable only with no pre-admission attempts. `/1` and ordinary `/2` lifecycle
prefixes remain valid. Earlier `/2` attempts require a separately approved
migration; never delete or silently reattribute them.

## Exact grant grammar

Keep existing `schema,t,ev,by` fields and validation. Unknown keys refuse.
`Ref` is `{path,sha}` under the existing safe-path/normalized-SHA256 rules.
`Head` is exactly `{run,revision}`, where revision is a nonnegative integer.

| Event | Required additional fields |
| --- | --- |
| `run_admitted` | `run,milestone,slices,stop,allowance,max_corrective_rounds,grantors,previous,reason,authority` |
| `run_extended` | `run,milestone,revision,allowance,reason,authority` |

- `run`: existing identifier grammar, globally unique on admission.
- `milestone`: an existing active milestone ID. `slices`: nonempty distinct IDs from
  that milestone, in roadmap order. `stop`: final selected slice ID, or milestone
  ID if holistic review is enabled. These name respectively the exact `accepted`
  or `milestone_done` event that permanently retires the run. Already-satisfied
  stops refuse; later manual reopening cannot revive it.
- `allowance`: exactly `jobs,transport_retries,format_retries,seconds`, all
  nonnegative integers (never booleans). Initial jobs/seconds must be positive.
  Extensions add increments, at least one positive, without changing consumption.
- `max_corrective_rounds`: nonnegative per-slice lifetime ceiling, checked against
  the existing folded count before coder dispatch. Extensions cannot change it;
  even an explicitly new run does not reset that count.
  Coder reservations require the issued `coding` state and exact round, so they
  cannot skip the prompt that charges the corrective round.
- `grantors`: distinct list containing `human`, optionally `architect` under
  owner delegation. Grant `by` must be human/architect; extension actor must be
  in the root list. Automated seats have no grant authority.
- `previous`: null only for the first admission; otherwise the exact current
  Head. Root revision is zero; extension revision must be current plus one.
- `reason`: nonempty text. `authority`: nonempty distinct immutable Ref list documenting
  the specific approval. Reusing a prior grant's reference set refuses. Bind a
  permanent approval snapshot, not an appendable decision register.

One run is current globally. Successor admission links and supersedes it; no
unfinished invocation may be bypassed. Extensions require the current nonterminal
run and matching milestone. Repeated/stale grants refuse. Both events carry
milestone so accepted commits retain their authority.

Selection is pinned; issued envelopes still freeze work authority. Scope changes
need architect decisions. Grants cannot resolve blockers, waive findings, clear
pending Git work or authorize domain experiments/canaries.

New admission requires roadmap status `active`; a grant never activates planned
work. Historical replay permits a later `done` label only when the complete ledger
proves all milestone slices accepted, required holistic closure and no unfinished
invocation in that milestone. `done` alone is insufficient. Reactivate the milestone
before reopening completed run history for further work; new admission still needs
new explicit authority.

## Attempts and accounting

Attempt fields stay unchanged: no `run` key or replacement `contract` hash.
Membership is the latest admission in ledger order. Every profile attempt needs
a current run and in-bound scope. Config/restarts cannot replenish allowance.

| Invocation | Jobs | Retry unit | Seconds |
| --- | ---: | --- | --- |
| Model/provider probe or initial seat | 1 | none | reserve deadline |
| Transport retry | 1 | transport | reserve deadline |
| Read-only format repair | 1 | format | reserve deadline |
| Independent runner verification | 0 | none | reserve deadline |

Every start spends its job/retry even if the process crashes before launch.
Follow parents to the initial invocation: at most one transport and one format
repair over that whole chain. Parents must be finished and in the same run.
Repeated initial model `(scope,round,role,contract)` in a run refuses. Existing
read-only repair roles and exact checkpoint/contract binding still apply; an
extension alone does not invalidate a completed matching checkpoint.

A crash after an initial model reservation, even before launch, does not permit
another initial attempt for that context. Establish safe child disposition and
record completion/resolution; redispatch uses the chain's transport retry and
another job/time reservation. Size the run-wide transport allowance for these
interruptions. With one transport unit, one such retry exhausts that run counter.
An explicit extension can fund another chain's retry, but cannot reset a used
chain retry. If the transport retry itself crashes, that chain cannot retry again
under the same run, even after extension: use manual recovery/work or a newly
authorized run. Format repair is read-only and cannot repeat the interrupted work.

`reviewer` requires the current `reviewing` slice and exact round. `holistic`
requires the admitted milestone and holistic round, every milestone slice
accepted (including unselected slices), holistic enabled, and no blocked,
close-pending or done decision. These checks apply to transport and format
retries too. Resolving a holistic blocker or reaccepting reopened work can make
review eligible again. Preflight `probe` attempts remain lifecycle-neutral.

`verification` requires the currently verifying slice/round, `retry: initial`,
no parent. It shares ordinary completion and the global unfinished-attempt gate.
The runner reserves, executes its independent verifier with the clipped deadline,
saves the receipt, records completion, then appends `verified`. Completion may
bind the receipt in `evidence`. Standalone verification cannot run while an
unfinished attempt holds the gate; ordinary manual verification is unchanged.

Remaining is initial allowance plus valid increments minus charges. Reserve a
positive integer deadline no greater than remaining seconds before dispatch;
frutlups must clip its actual timeout too. For a durable `completed` operation
with measured full-lifetime `usage.secs`, charge `ceil(secs)`. Overall usage may
be partial because provider tokens/cost are missing. Missing duration or a
`failed/resolved` finish keeps at least the full reservation. Any measured
duration above reservation increases the charge and retires the run for new
dispatch; preserve negative balances and truthful completion evidence. A new
authorized admission is required after overrun. Ordinary exhaustion can be
extended; no prior charge or retry history is cleared.

In this profile `secs` means complete local operation lifetime, not a partial
provider measurement; omit it if unknown. Active seconds include probes, seats
and independent verification, counting model-internal commands once. They exclude
owner waits, offline gaps and local bookkeeping. This is not whole-session wall
time or a hard dollar cap. Keep missing token/cost metrics unknown.

## Commands and handoff

Save an immutable approval file; commands bind its hash, not the truthfulness of
its prose. Run commands refuse `FRUTLUPS_SEAT`. For example:

```text
python scripts/ledger.py run admit M001 --run-id R001 --slice M001-S01 --stop M001-S01 --jobs 4 --transport-retries 1 --format-retries 1 --seconds 100 --max-corrective-rounds 2 --authority 05_governance/approval-R001.md --reason "Owner approved this slice"
python scripts/ledger.py run extend R001 --revision 1 --jobs 2 --seconds 30 --authority 05_governance/approval-R001-extension1.md --reason "Owner approved this increment"
python scripts/ledger.py status
```

Use `--by architect` only with owner authority. Delegation requires admission
`--grantor human --grantor architect`. Extension retries default to zero.
`status` reports folded balances. The default manual roadmap needs none of this.
Before issuing prompts, commit profile/grant/approval changes or explicitly
attribute the inspected baseline with existing `--allow-dirty`. Admission itself
does not waive the clean-product gate.

Hold the shared writer lock through the run. Fsync reservations before launch
and completion before refund/redispatch. Broken appends or bound evidence refuse;
preserve them. Optional logs/caches do not determine charges.

Profile status and each append revalidate all bound historical references.
Cost grows with retained history and evidence bytes; a prior successful check
does not authorize later bytes. Keep this cost in historical-validation
measurements when sizing long autonomous runs; no persistent verdict cache exists.

A clean tree, absent PID or reacquired lock does not prove a prior child ended.
Unfinished work blocks both another runner and ordinary manual mutations. A
human/architect can record `attempt_finished` with `status: resolved`, reason,
bound evidence of safe child disposition and honest usage through the existing
`ledger.py attempt <event.json>` command. Bind new recovery evidence directly
in that finish; an intervening artifact append is correctly blocked. Unknown
charges remain reserved after resolution; no output/checkpoint is fabricated.

Then release the runner lock and continue manually. Returning to frutlups folds
the same balances; manual acceptance of the named stop retires the run. Separately
launched manual model sessions are not automatically metered. No extra budget
events are required for ordinary manual work.

Hashes/actors do not authenticate a malicious writer or prove orphan deadlines.
Adapters, process ownership and cross-mode behavior need paired qualification.
Distribute `tests/fixtures/autonomy_v1.json` and the unchanged base corpus from
the same full commit as the template export.
