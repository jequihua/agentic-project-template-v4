# Local State Not Committed

Use this file to record local-only paths and secret boundaries.

Do not commit:

- `.venv/` or other virtual environments
- caches and temporary test output
- credentials, tokens, service account files, API keys
- raw private data
- bulky generated run outputs
- local llloom memory roots unless the human owner explicitly approves

If llloom is enabled, record:

- memory root:
- whether it is local-only:
- allowed commands:
- last verified status:

`.gitignore` enforces these exclusions. Before a milestone commit, follow the
Milestone Commit Closure checklist in `docs/template_framework/method.md`.

## Known Local Roots

Record substantial local-only roots a new agent or human should know about
(virtual environments, memory roots, run-output folders, copied reference trees,
large data caches). Keep it short; it is a pointer, not live state.

| Path | Purpose | Rebuildable | Retain Until | Cleanup Note |
| --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD |

## Snapshot Exclusions (driven projects)

When an autonomous runner freezes pass boundaries, large or generated local
outputs must either live under `local_state/` or be declared in the runner's
exclusion manifest. That manifest is the runner's own strict JSON file
(`contract_version`, `exact_paths`, `top_level_prefixes`), declared in the
runner policy and recommended at the path named by `local_state.oracle_exclusion_manifest`
in `frutlups.layout.yaml`. Do not duplicate its entries here: record the
manifest path once, and one sentence per entry on why it is excluded. The
pre-launch check that reads the same file is the layout's
`local_state.prelaunch_size_check` command; pass its `--exclusions` flag only
when a manifest is declared (see
`docs/template_framework/security_and_local_state.md`).

- exclusion manifest path:
- entries and reasons:

## Seeing And Cleaning Local Footprint

Rebuildable residue (caches, coverage, build output) can be surfaced and removed
without touching meaningful artifacts:

```powershell
python scripts/local_state_audit.py --root .   # read-only footprint report
python scripts/local_cleanup.py --check --root .   # dry-run: list rebuildable residue
python scripts/local_cleanup.py --apply --root .   # delete only rebuildable residue
```

Cleanup never deletes `.git`, virtual environments, `local_state/`, memory roots,
the evidence/governance workspaces, archives, or nested repositories. See
`docs/template_framework/security_and_local_state.md`.

If cloud or credentialed work is enabled, use `06_infra/live_validation_gate.md`.

