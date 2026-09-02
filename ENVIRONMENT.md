# Environment

This file is the durable place for environment expectations.

## Default

- Shell examples should work in PowerShell on Windows.
- The repository stays manually readable and operable without services,
  credentials, or network access. Its Python **validation tooling** requires the
  dependencies declared in `pyproject.toml` (currently PyYAML), installable online
  or from a controlled offline wheelhouse. Other scripts remain standard-library
  only.
- Prefer a virtual environment; it may live in the repo (`.venv`, git-ignored) or
  in an external venvs directory. The commands below assume it is **activated**, so
  they use a plain `python` and cite no repository-local executable.
- Use `rg` / `rg --files` for search.

## Python Environment And Dependencies

The OKF/profile checker (`scripts/artifact_integrity_preflight.py --profile`,
backed by `scripts/okf_yaml_profile.py`) requires PyYAML. This repository is
metadata/tooling-only (no importable package); the editable install exists only to
declare the dependency. Create and activate a clean virtual environment, then
install the project (which resolves PyYAML from `pyproject.toml`):

```powershell
python -m venv <env-dir>
<env-dir>\Scripts\Activate.ps1      # POSIX: source <env-dir>/bin/activate
python -m pip install -e .
```

After installation, all validation runs locally and offline; no network, service,
or credential is used at runtime.

Controlled-offline install (activated env, external wheelhouse holding the reviewed
PyYAML wheel plus the build backend and `wheel`):

```powershell
python -m pip install --no-index --find-links <wheelhouse> setuptools wheel
python -m pip install --no-index --find-links <wheelhouse> --no-build-isolation -e .
```

Do not commit virtual environments, wheels, wheelhouses, download caches,
`*.egg-info`, or machine-specific constraints (all are git-ignored).

## Scaffold Checks

With the environment activated and the project installed (above):

```powershell
python -m unittest discover -s tests
```

Tests that require PyYAML are skipped when it is not installed; the acceptance run
must have the project installed (which pulls PyYAML), so those tests run.

## Tooling

llloom:
- Optional memory package.
- Install source when enabled: record the project-specific source or package
  reference here.

frutlups:
- Optional loop tooling package.
- Install/source reference when enabled: record the project-specific source or
  package reference here.

## Record Here When Activated

- Python version: 3.10+ baseline.
- Virtual environment: an activated venv (in-repo `.venv` or external), git-ignored;
  not committed.
- Required package installs: the editable project (`pip install -e .`), which
  declares `PyYAML>=6.0.3,<7` (pure-Python `yaml.SafeLoader`). Both online and
  controlled-offline wheelhouse installs are documented above.
- Test command: `python -m unittest discover -s tests` (env activated).
- Platform caveats: PowerShell activation shown; on POSIX use
  `source <env-dir>/bin/activate`.
- Long-running job expectations: none; checks are fast, local, and offline.
- Known blockers: none.
