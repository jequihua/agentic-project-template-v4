# Operating the project

## Initialize

Start from an archive of the template so framework tests are omitted. Read
`AGENTS.md` and `initialization/architect.md`. Populate `00_brief/`, choose
workspace statuses, replace the example roadmap, and set a real project-owned
full verification argv. From the extracted project directory, validate,
initialize Git and make a baseline (configure your Git name/email if needed):

```powershell
python scripts/roadmap.py check
git init
git add --all
git commit -m "Initialize project"
python scripts/roadmap.py render
python scripts/ledger.py status
```

Never start coding while the roadmap check fails. The shipped `/2` roadmap is a
manual candidate. For existing projects, use [the selective upgrade procedure](upgrading.md);
keep incompatible runners disabled.

## Manual slice walkthrough

1. `python scripts/prompt.py M001-S01` writes the next coding prompt and appends
   its `prompt` event with a frozen acceptance envelope. `--preview` renders the
   same text without writes; `--check` reports diagnostics and section bytes.
   Notes are advisory; mandatory gates belong in acceptance. Corrective state is
   baselined automatically. Unknown dirty paths stop issuance; inspect and commit/stash
   them, or use `--allow-dirty` only to admit that exact architect-owned state.
2. Save the coder's final text as the named optional coder-notes file when it is
   worth retaining. Run
   `python scripts/ledger.py coded M001-S01 --notes <path>`. The script reads Git
   and refuses an out-of-bound change. Omit `--notes` for a simple handoff.
   An explicit authority/environment blocker uses `ledger.py blocked` or a saved
   structured outcome; [the exceptional commands](upgrading.md) preserve its edits.
3. Run `python scripts/verify.py M001-S01`. It writes a receipt and records the
   result. A failure routes to the next corrective round.
4. On success run `python scripts/prompt.py M001-S01 --review`. Its neutral
   artifact event makes the prompt immutable without advancing the fold. Give
   it to a read-only reviewer, who writes the named report or returns the text.
5. Run `python scripts/ledger.py record <report>`. On needs-work, render the next
   coding prompt. On pass, run `python scripts/ledger.py accept M001-S01`; add
   `--commit` only when local commit authority is intended.

At any time, `ledger.py status` shows the fold and next slice; `ledger.py index`
prints history. Do not create hand-maintained state or index files.

With ledger-only acceptance, inspect and commit the accepted product and loop
evidence before starting the next slice. This housekeeping is intentional: new
slices require a clean tree unless an architect explicitly admits dirty state.
`ledger.py prompt <slice> <saved-prompt>` records a prepared legacy `/1` prompt
only. `/2` requires `prompt.py`, including for customized templates, so saved
text cannot bypass the complete frozen-envelope and prompt-size checks.

## Steering and closure

Edit the roadmap only between stable loop steps, then check and render it. Add
or narrow slices rather than rewriting accepted history. When all milestone
slices are accepted, run `python scripts/prompt.py --holistic M001` when the
milestone requires holistic review. Record the report with
`ledger.py record <report> --milestone M001`. In `/2`, needs-work reopens affected
slices, blocked requires resolution, and pass persists `close_pending`. Then
`ledger.py close M001` completes closure; add `--commit` only when authorized.

Holistic report names use `<MID>_holistic_review.md`, then
`<MID>_holistic_2_review.md`, `_3_`, and so on. The first free name excludes
existing filesystem entries and paths already named in recorded holistic
prompts or reports, so issuing another prompt cannot reuse an earlier report.
Slice and holistic recording project explicit finding dispositions into the marked
region of `05_governance/backlog.md`. `ledger.py reconcile` rebuilds it after an
interruption. Passing another review never implicitly closes an older finding.

Owner reopening uses
`python scripts/ledger.py reopen M001-S01 --reason "<reason>" --by human`.
After a blocker, a human or architect uses
`ledger.py resolve M001-S01 --reason "<new fact>" --authority <decision-or-evidence>`.
This preserves the original envelope and blocker; it grants no undeclared budget.
The resumed blocked round keeps the original acceptance scope. If the resolution
changes that scope, the architect plans a new slice; editing roadmap acceptance
does not override the frozen blocker. Ordinary needs-work rounds read the current
admitted roadmap when issued.
Legacy `/1` reviewer blocks retain `ledger.py unblock <slice> --reason ...`.

Corrective prompts recognize ledger-known prompts, receipts, reports, notes,
and unchanged same-slice products automatically. A changed known path remains
new work; a foreign artifact or injected prompt remains unknown and refuses.
After acceptance, committed owner hotfixes may match HEAD during holistic review
and close. They are visible in current holistic evidence; the earlier review
still approves only its original candidate. Uncommitted drift still refuses.

## Recovery

Scripts append events only after their artifact writes succeed. After an
interruption, inspect Git and the ledger before choosing one move:

- Prompt exists, no `prompt` event: inspect its frozen envelope and validate it
  before manual attribution. An unrecorded file alone never authorizes work.
- Coder exited, no `coded`: leave the tree intact, save any notes, and run
  `ledger.py coded`; never guess or auto-revert the delta.
- Receipt exists, no `verified`: it was not made authoritative. Preserve it if
  diagnostically useful, then rerun `verify.py`; the successful atomic write and
  event append replace the incomplete attempt.
- Report exists, no `reviewed`: run `ledger.py record`.
- A command refused before any ledger append: newly created unchanged immutable
  JSON artifacts are removed. Existing artifacts and uncertain/crashed appends
  are preserved. Inspect only the named unrecorded path, verify it is absent from
  ledger references, and obtain architect attribution before moving it aside.
- Approval has a pending commit intent: use `ledger.py recover` to inspect, then
  `recover --execute` to complete only missing exact Git work. Never repeat approval.
  Unfinishable intent needs authorized cancellation; see [recovery](upgrading.md).
- Malformed/truncated ledger line: stop. Preserve bytes and obtain human
  authority for repair; normal commands never rewrite the ledger.
- Out-of-prefix or crash-dirty tree: the tool leaves it unchanged for human
  attribution. Do not reset, clean, or stash automatically.

`ledger.py check` detects evidence drift. Resolve the cause; do not update hashes
to silence it.

An unfinished external invocation freezes new work even when its local output
was lost. `ledger.py attempt <event.json>` records a reservation, completion or
review checkpoint. For a known completed `review-1`, save this exact shape as
ignored `local_state/attempt.json`, using the actual invocation and known metrics:

```json
{"ev":"attempt_finished","by":"architect","invocation":"review-1",
 "status":"completed","usage":{"completeness":"unknown"}}
```

Run `python scripts/ledger.py attempt local_state/attempt.json`. Missing metrics
remain unknown. For unknown completion, first establish the external process is
finished, record the observed evidence in `00_brief/decisions.md`, then save:

```json
{"ev":"attempt_finished","by":"human","invocation":"review-1",
 "status":"resolved","usage":{"completeness":"unknown"},
 "reason":"Process ended; output and usage could not be recovered",
 "evidence":[{"path":"00_brief/decisions.md","sha":"<normalized SHA-256>"}]}
```

Replace the hash with the actual evidence identity. From the project directory:
`python -B -c "import sys; sys.path.insert(0,'scripts'); import _common as c; print(c.sha(c.Path('00_brief/decisions.md')))"`.
Run the same `attempt` command. This attributes unknown work without inventing
success, usage or new budget. JSON input is bounded to 2 MiB before parsing.

CLI file arguments may use `/`, `\`, or one leading `./`/`.\`; ledger content
always stores canonical repository-relative POSIX paths. Absolute paths,
traversal, repeated dot prefixes, and repository escapes remain invalid.

## Hermetic verification

The project-owned `scripts/hermetic_verification.py` fails with exit 2 until
`COMMANDS` contains real argv lists or argv/cwd mappings:

```python
COMMANDS = [
    ["python", "-m", "pytest"],
    {"argv": ["npm", "test"], "cwd": "07_app/web"},
]
```

Commands run without a shell from repository root by default; a mapping's cwd
must resolve to a directory inside the repository. `TEMP`, `TMP`, and
`VERIFICATION_SCRATCH` point to external scratch, while `PROJECT_ROOT` names the
project and bytecode writes are disabled. The first failure reports command
number, argv, cwd, and exit code. Tools should direct caches/build output to the
scratch variable where their CLI supports it.

For example, a Python runner can pass
`Path(os.environ["VERIFICATION_SCRATCH"]) / "pytest"` to pytest's
`--basetemp`; a JavaScript config can set its cache directory from
`process.env.VERIFICATION_SCRATCH`. Static argv invokes the project-owned runner
or config, which reads the runtime environment.

Authoritative verification witnesses file contents, types, index and HEAD before
and after execution, including already-dirty files. It does not claim host-wide
isolation. The project owns acceptance-to-test discovery, product dependencies,
and fresh-process user paths; see [project checks](project_checks.md). A runtime
selection belongs in the optional project convention, not a conflicting runner setting.

## Autonomous operation

frutlups remains optional. Version 0.3.2 cannot operate `/2` projects: schema
admission refuses before model probes or writes. Do not downgrade the roadmap to
bypass that refusal. A future exact template/runner pair must pass shared contract
and interruption qualification before autonomous use; [the compatibility table](upgrading.md)
records that pending boundary.

The future compatible runner must consume the same frozen envelope, runtime,
receipt and recovery contracts. Reviewer seats retain read-only tools; complete
manifests and bounded diff pages are readable files. `--backend autonomous`
previews the structured coder outcome form without installing or invoking a runner.

## Questions and external actions

Put precise blockers in `questions/open/`. Human answers move to `answered/`
and update the decision register or roadmap when authoritative. Publishing,
pushes, service/host changes, credentials, cost, destructive cleanup, and
front-repository apply remain human-controlled and are outside the slice loop.

## Instantiate without framework tests

`.gitattributes` marks `/tests` as `export-ignore`. From a committed template
revision:

```powershell
git archive --format=zip --output ..\project.zip HEAD
Expand-Archive ..\project.zip ..\project
```

Inspect the archive before initializing the project repository. The exported
project keeps runtime scripts and `pyproject.toml` but carries no framework
tests or fixtures.
