# Security And Local State

The template must keep secrets and local state out of committed artifacts.

Never commit:

- credentials;
- tokens;
- service account files;
- raw private data;
- local memory roots unless explicitly approved;
- generated logs containing secrets.

For live work, use `06_infra/live_validation_gate.md`.

For local state policy, use `LOCAL_STATE_NOT_COMMITTED.md`.

## Governed Local Surfaces And The Pre-Launch Size Check

Two surfaces are governed local state and never distributable: the runner's
run store `.frutlups_drive/` and the local-state root `local_state/`
(`frutlups.layout.yaml`, `local_state.governed_ignored_surfaces`). The
template-source purity checks skip them and walk only the template-owned
surfaces (`template_owned_surfaces`), so a populated project keeps the same
checks green while a defect in distributable source still fails.

Live and generated outputs go under `local_state/` by default. Anything
larger than the runner's oracle content bound (16 MiB) that must stay outside
it is declared in the runner's JSON exclusion manifest - the single
machine-read exclusion source; the Markdown roots table only references it.
Before the launch word, run the read-only pre-launch check, which reads that
same JSON file with the runner's own grammar - it refuses exactly what the
runner refuses (a non-canonical reference, a declared file that is missing,
a link, malformed fields) - and exits 1 while any undeclared file sits at or
above the bound. Pass `--exclusions` only when the runner policy declares a
manifest; a project without one runs the check without the flag:

```powershell
python scripts/local_state_audit.py --limit-bytes 16777216 --exclusions 06_infra/oracle_exclusion_manifest.json
python scripts/local_state_audit.py --limit-bytes 16777216   # no manifest declared
```

## Rebuildable Local State

A repository can be commit-clean and still be large, slow, or hard to delete
because of rebuildable runtime residue: Python/test caches, coverage output,
build/dist output, packaging metadata, and temporary test folders. These are the
same categories `.gitignore` already excludes — they are local artifacts, not
source.

Two stdlib-only support tools make this visible and cleanable. They are optional;
the core loop does not depend on them.

```powershell
python scripts/local_state_audit.py --root .   # read-only footprint report
python scripts/local_cleanup.py --check --root .   # dry-run: list rebuildable residue
python scripts/local_cleanup.py --apply --root .   # delete only rebuildable residue
```

Policy:

- the audit is strictly read-only and never fails merely because a project is
  large;
- cleanup is dry-run by default; only `--apply` deletes, and only the rebuildable
  allowlist (`__pycache__`, pytest/mypy/ruff caches, `.coverage`, `coverage.xml`,
  `htmlcov`, `test-results`, `build`, `dist`, `*.egg-info`, temp test folders);
- cleanup never deletes `.git`, virtual environments (`.venv`/`venv`/`env`),
  `local_state/`, local memory roots, the evidence/governance workspaces
  (`01_data`, `03_experiments`, `05_governance`, `90_legacy_review`, `memory`),
  archives, copied source trees, or any nested repository; it never escapes the
  `--root` and never follows symlinks;
- deleting virtual environments, archives, or memory roots is a separate, explicit
  decision — the audit may flag them, but cleanup will not remove them.

## Windows Deletion Hygiene

Deletion friction on Windows usually comes from open handles and Git object
files, not from the template. When removing a local clone or a heavy local root:

- close editors, terminals, notebooks, servers, and Explorer windows inside the
  target folder;
- run the deletion from a terminal **outside** the target folder;
- stop file watchers or language servers if a handle stays open;
- clear read-only attributes only when intentionally deleting a whole local clone.

