# Environment

The scaffold supports Windows PowerShell first and POSIX shells. Runtime
requirements are Python 3.11+, PyYAML, and Git. Manual scripts are local and
offline after installation; they use no service or credential.

## Setup

Create and activate a virtual environment, then install the dependency metadata:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

POSIX activation is `source .venv/bin/activate`. A controlled-offline install
may use a reviewed wheelhouse:

```powershell
python -m pip install --no-index --find-links <wheelhouse> setuptools wheel PyYAML
python -m pip install --no-index --find-links <wheelhouse> --no-build-isolation -e .
```

Do not commit venvs, wheels, caches, machine constraints, or executable paths.

## Commands

```powershell
python scripts/roadmap.py check
python scripts/roadmap.py render
python scripts/ledger.py check
python -m unittest discover -s tests
```

The last command qualifies the template repository. Exported projects do not
contain framework tests; their authoritative full command is
`verification.full` in `roadmap.yaml` and runs through
`python scripts/verify.py <SLICE>`. The default calls
`scripts/hermetic_verification.py`, which fails closed until the project fills
its `COMMANDS` argv lists. Bare lists run from repository root; mappings such as
`{"argv": ["npm", "test"], "cwd": "07_app/web"}` run from a safe project
subdirectory. `TEMP`, `TMP`, and `VERIFICATION_SCRATCH` identify external
scratch space so tools can keep caches and build residue outside the project.

frutlups is optional. Its committed example is `frutlups.toml`. Machine-local
executables live only in ignored `frutlups.local.toml`, whose schema is
`frutlups.local/1` and whose supported keys are `pi`, `claude`, `git`, `llloom`,
`path_dirs`, and `env_passthrough`.
