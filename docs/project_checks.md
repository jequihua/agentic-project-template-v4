# Project-owned checks

An ordinary project needs one prepared interpreter and one maintained full
verification command. Configure `scripts/hermetic_verification.py` before the
baseline; its empty `COMMANDS` deliberately fails. Use argv lists, optionally with
a repository-relative `cwd`. Literal `python` uses the selected project runtime.
The architect owns command selection and test discovery; the project owns its
product dependencies. Installing the template's PyYAML dependency does not prove
that a product package can be built, installed or used.

## Runtime and coverage

For a project that pins Python, declare `runtime: {python: '3.14'}` in a `/2`
roadmap. The ignored `project.local.toml` may contain `schema = 'template.local/1'`
and `python = '<absolute executable on this machine>'`. Omit the file to use the
interpreter invoking the manual scripts. Keep that local path out of tracked
notes, receipts and prompts. A selected version mismatch stops verification before
the product command. The same resolver is available to the future compatible
runner; a second conflicting runner setting is not runtime authority.

For each new acceptance gate, identify the maintained command and the test or
inspection that witnesses it. Adding a test file alone is insufficient: exercise
the full command to prove discovery. When a small required suite is an acceptance
gate, let its project-owned launcher reject zero tests, missing required test IDs
and skipped required tests. Do not demand every test run in a separate process.
For a changed CLI/schema, check its named callers, examples and help output within
the admitted read window. Required flags belong in the maintained commands.

Receipts record execution evidence, not automatic coverage approval. Set
`verification.observation` to `in_process`, `fresh_process`, `clean_checkout` or
`inspection` only when the command actually performs that check; the default
`process` says only that a command ran. The runtime identity contains portable
Python version, implementation, selection source and a declaration/identity hash;
it is not an inventory of installed product packages.

## A prepare, exit, then serve gate

If the documented user path runs separate commands, acceptance must exercise
separate operating-system processes. A useful small fixture performs:

```text
python viewer.py prepare --output current.json
python viewer.py serve --output current.json --once
```

`prepare` persists the required result and identities of its code and inputs.
After it exits, `serve` reads that result and rejects changed code or inputs.
An in-memory cache shared only by a unit test does not satisfy this sequence.
Change code deliberately and observe a clear stale-output refusal, then exercise
the documented refresh operation in an owned scratch project. A real browser or
server acceptance owns its child processes and endpoints, and cleans up only
those resources. The template's one-shot viewer fixture exercises process
persistence and freshness; it does not claim browser or network coverage.

The maintenance regression `tests/test_project_checks.py` runs the faulty cache-only
sequence, the corrected sequence, changed-code rejection, required flags, scratch
refresh, discovery/skip guards and an unavailable product dependency. Framework
tests are excluded from project exports; these are examples to adapt to the
project's actual command, not a new mandatory test harness.

## Raw evidence and current output

Choose byte policy before first hashing retained raw evidence. Use scoped `-text`
attributes for exact-byte directories or choose deterministic serialization before
creating manifests. Keep framework prose's existing normalized evidence identity.
An optional `/2` `verification.git_boundary` command checks the exact candidate
tree named by `TEMPLATE_CANDIDATE_TREE`; it must not modify worktree, index, HEAD,
attributes or manifests. Declare `verification.timeout_seconds` for its allowance.
The commit operation binds a successful check to the candidate before completion.

At an artifact milestone, compare selected Git blobs to the raw manifest and run
the documented user path from a clean materialized candidate. A copied dirty
worktree cannot witness Git serialization. Include LF, CRLF and binary examples
where relevant; do not globally disable text normalization.

Retained historical evidence stays tied to its historical implementation. Current
derived output instead needs a check-only comparison against regeneration in
owned scratch, using declared code/input identities. Exercise the refresh branch
there as well as the check branch. Updating current output never licenses rewriting
old manifests to hide damaged bytes. Verification witnesses tracked and untracked
nonignored files, raw contents, modes/types, index entries and HEAD. Ignored stores,
submodule internals and the wider host are outside that witness.

## Optional research admission

Use this section only when the project runs experiments. Keep authority in the
roadmap and decisions; the project executor owns scientific outcome meanings.

| Admission fact | Small concrete example |
| --- | --- |
| Boundary and technical canary | A changed ingestion/domain/time boundary gets one representative canary, including fractional/adversarial round-trip inputs; batch launch requires its declared pass. |
| Separate attempt units | Admit one technical canary and three scientific attempts. A model corrective round supplies neither another canary nor a replacement experiment. |
| Typed outcome | Keep infrastructure failure, invalid scientific state, incomplete output, valid extinction and valid negative/nonconvergence distinct. Missing snapshots are unknown, not successful empty data. |
| Stop and replacement authority | First common infrastructure failure stops unstarted jobs. Retain started failed attempt A1 and explicitly mark A2/A3 unstarted. An authorized replacement A4 keeps A1 and makes four total reserved/started identities visible. |
| Interpretation | Separate self-checks from informative contrasts. State the conditions of a zero-effect result and distinguish observed regimes from general claims. |
| Evaluation provenance | Freeze evaluation before outcomes. Label any post-outcome addition with its decision and timing; it cannot silently become a predeclared success gate. |

For example, an infrastructure failure in A1 leaves A2 and A3 unstarted and records
an explicit authority/environment blocker with the retained evidence. A human or
architect must record the new fact and authority before resumption. A valid
extinction or negative result follows the project's predeclared scientific policy
without an invented infrastructure retry. Software verification proves only the
software claims it exercised; domain interpretation still needs its own evidence.
These are project admission rules, not a template experiment scheduler.
