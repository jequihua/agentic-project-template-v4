# Operating the project

## Initialize

Start from an archive of the template so framework tests are omitted. Read
`AGENTS.md` and `initialization/architect.md`. Populate `00_brief/`, choose
workspace statuses, replace the example roadmap, and set a real project-owned
full verification argv. Validate and render:

```powershell
python scripts/roadmap.py check
python scripts/roadmap.py render
python scripts/ledger.py status
```

Never start coding while the roadmap check fails.

## Manual slice walkthrough

1. `python scripts/prompt.py M001-S01` requires a clean product tree, writes the
   next coding prompt, and appends its `prompt` event. Give that file to a coder.
   For a deliberate dirty handoff, use `--allow-dirty`; the event records exact
   path/hash/kind baseline entries so unchanged architect work is not attributed
   to the coder.
2. Save the coder's final text as the named optional coder-notes file when it is
   worth retaining. Run
   `python scripts/ledger.py coded M001-S01 --notes <path>`. The script reads Git
   and refuses an out-of-bound change.
3. Run `python scripts/verify.py M001-S01`. It writes a receipt and records the
   result. A failure routes to the next corrective round.
4. On success run `python scripts/prompt.py M001-S01 --review`. Give the prompt
   to a read-only reviewer. The reviewer writes the named report or returns the
   complete text for you to save there.
5. Run `python scripts/ledger.py record <report>`. On needs-work, render the next
   coding prompt. On pass, run `python scripts/ledger.py accept M001-S01`; add
   `--commit` only when local commit authority is intended.

At any time, `ledger.py status` shows the fold and next slice; `ledger.py index`
prints history. Do not create hand-maintained state or index files.

## Steering and closure

Edit the roadmap only between stable loop steps, then check and render it. Add
or narrow slices rather than rewriting accepted history. When all milestone
slices are accepted, run `python scripts/prompt.py --holistic M001` when the
milestone requires holistic review. Record the report with
`ledger.py record <report> --milestone M001`; reopen named slices for blocking
findings or record milestone completion after pass.

Owner reopening uses
`python scripts/ledger.py reopen M001-S01 --reason "<reason>" --by human`.
When a blocked review's external decision is resolved, a human or architect
uses `python scripts/ledger.py unblock M001-S01 --reason "<resolution>"`. This
preserves its findings and starts the next corrective round. frutlups stops on
`blocked`; it cannot authorize this transition.

Corrective manual rounds usually have uncommitted reports, receipts, and prior
product changes. Commit or stash them before the next prompt, or deliberately
use `prompt.py <slice> --allow-dirty` to capture their exact baseline.

## Recovery

Scripts append events only after their artifact writes succeed. After an
interruption, inspect Git and the ledger before choosing one move:

- Prompt exists, no `prompt` event: validate it, then use
  `ledger.py prompt <SLICE> <path>`, or remove the unissued prompt.
- Coder exited, no `coded`: leave the tree intact, save any notes, and run
  `ledger.py coded`; never guess or auto-revert the delta.
- Receipt exists, no `verified`: it was not made authoritative. Preserve it if
  diagnostically useful, then rerun `verify.py`; the successful atomic write and
  event append replace the incomplete attempt.
- Report exists, no `reviewed`: run `ledger.py record`.
- Accepted event exists but an intended commit does not: inspect and commit the
  exact accepted paths manually. Never append a second acceptance.
- Malformed/truncated ledger line: stop. Preserve bytes and obtain human
  authority for repair; normal commands never rewrite the ledger.
- Out-of-prefix or crash-dirty tree: the tool leaves it unchanged for human
  attribution. Do not reset, clean, or stash automatically.

`ledger.py check` detects evidence drift. Resolve the cause; do not update hashes
to silence it.

CLI file arguments may use `/` or `\`; ledger content always stores canonical
repository-relative POSIX paths. Absolute paths, traversal, and repository
escapes remain invalid.

## Hermetic verification

`scripts/hermetic_verification.py` is the default project-owned entry point. It
fails with exit 2 until `COMMANDS` contains real argv lists. Each command runs
without a shell in a temporary directory outside the repository with `TEMP`,
`TMP`, `PYTHONDONTWRITEBYTECODE`, and runtime `PROJECT_ROOT` set. It stops at the
first failure. Replace the placeholder before establishing the project baseline
and keep the command representative of the declared toolchain.

## Autonomous operation

frutlups 0.3 reads the same roadmap, templates, and ledger; creates the same
prompts, reports, receipts, and events; and folds to the same status text. It
does not provide manual-mode verbs. It saves reviewer final text because
reviewer seats have no write tools. It can be stopped and manual operation can
resume at the ledger's current step.

Machine executables and PATH entries live in ignored `frutlups.local.toml`.
Committed `frutlups.toml` has behavior and seat names only. frutlups sets
`FRUTLUPS_SEAT`, so front-repository mutation is refused. It never invokes
llloom itself; when memory is active, it exposes the executable to the seat and
the prompt names allowed verbs.

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
