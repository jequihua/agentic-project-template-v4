# Agentic Project Template v4

A compact, artifact-first harness for manual or autonomous software-development
loops. The same roadmap, ledger, prompts, receipts, and review grammar are used
in both modes. Manual operation needs only Python 3.11+, PyYAML, and Git;
frutlups is optional.

## Start a project

Create a project archive from the template repository so template qualification
tests are excluded:

```powershell
git archive --format=zip --output ..\my-project.zip HEAD
Expand-Archive ..\my-project.zip ..\my-project
```

Then edit `00_brief/`, replace the example `roadmap.yaml`, choose active
workspace statuses, record decisions, and set a real project-owned
`verification.full` command. The provided hermetic entry point fails closed
until its `COMMANDS` list is customized with argv lists or safe per-directory
argv/cwd mappings. Commands run from the project while temporary output is
directed through the external `VERIFICATION_SCRATCH`. Run:

```powershell
python scripts/roadmap.py check
python scripts/roadmap.py render
```

## Manual slice loop

```powershell
python scripts/prompt.py M001-S01
python scripts/ledger.py coded M001-S01 --notes <optional-coder-notes>
python scripts/verify.py M001-S01
python scripts/prompt.py M001-S01 --review
python scripts/ledger.py record <review-report>
python scripts/ledger.py accept M001-S01 --commit
```

The architect hands the generated coding/review prompts to the chosen agents.
Without `--commit`, acceptance changes only the ledger. See
`docs/operating.md` for rounds, recovery, holistic review, and autonomous use.
If a review is blocked, a human or architect can resume the next round with
`ledger.py unblock <slice> --reason <resolution>`.

## Sources of truth

- plan and boundaries: `roadmap.yaml`
- decisions: `00_brief/decisions.md`
- loop history: `05_governance/ledger.jsonl`
- blockers: `questions/open/`

`python scripts/ledger.py status` prints the current state and next step;
`index` renders the historical table. Do not maintain duplicate state files.

Local venvs, caches, credentials, run output, and `frutlups.local.toml` are
ignored. Record no secrets in prompts, receipts, notes, or the ledger.
