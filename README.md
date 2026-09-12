# Agentic Project Template v4

A compact, artifact-first harness for manual software-development loops. This
`/2` protocol candidate prepares shared contracts for a future compatible runner.
Manual operation needs only Python 3.11+, PyYAML and Git. No frutlups installation
is needed. frutlups 0.3.2 does not support `/2`; autonomous compatibility and the
paired live canary remain pending. See `docs/upgrading.md` before upgrading an
existing project or enabling a runner.

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
python scripts/ledger.py coded M001-S01
python scripts/verify.py M001-S01
python scripts/prompt.py M001-S01 --review
python scripts/ledger.py record <review-report>
python scripts/ledger.py accept M001-S01
```

The architect hands the generated coding/review prompts to the chosen agents.
Optional `coded --notes <path>` binds saved notes. Add `--commit` to the original
accept command when a commit is authorized; acceptance otherwise changes only
the ledger. If that commit is interrupted, `ledger.py recover` diagnoses the
pending intent and `recover --execute` performs only its missing Git work.
`prompt.py M001-S01 --preview` renders the actual prompt without writes.
Explicit blockers and recorded resolutions are exceptional boundaries, not extra
steps for every edit. See `docs/operating.md` for their commands and holistic review.

## Sources of truth

- plan and boundaries: `roadmap.yaml`
- decisions: `00_brief/decisions.md`
- loop history: `05_governance/ledger.jsonl`
- blockers: `questions/open/`

`python scripts/ledger.py status` prints the current state and next step;
`index` renders the historical table. Do not maintain duplicate state files.

Local venvs, caches, credentials, run output, `project.local.toml` and
`frutlups.local.toml` are ignored. Keep machine paths and secrets out of tracked
evidence. `docs/project_checks.md` covers runtime selection, required test
discovery, fresh-process user paths and optional raw-evidence/research guidance.
