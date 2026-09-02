# Front-facing repository projection

The development repository holds the brief, roadmap, ledger, prompts, reviews,
and product. A public/front-facing repository is a separate outside Git
repository containing a curated projection. Never nest either repository in
the other.

`front_repo.toml` maps explicit files and mirrored directories from development
paths to front paths. Directory mappings may carry `exclude` globs relative to
their own source. Global ignore rules cover names, suffixes, and basenames. The
tool rejects missing sources, traversal, symlinks, source/destination overlap,
and writes outside the resolved destination.
At least one `[[files]]` or `[[directories]]` mapping must be active; an empty
manifest is refused with the exact configuration to add.

## Commands

```powershell
python scripts/front_repo.py bootstrap --output-dir <new-empty-dir>
python scripts/front_repo.py check --target-repo <front-repo>
python scripts/front_repo.py status --target-repo <front-repo>
python scripts/front_repo.py apply --target-repo <front-repo>
```

`bootstrap` creates a first-copy tree but never runs `git init`. The human
inspects it, validates it, initializes Git, commits, and publishes. `check` and
`status` are read-only. `apply` performs the one-way update but never commits,
pushes, opens a pull request, or uses a network.

The source must be clean for `bootstrap`, `check`, and `apply` by default.
`apply` also requires a clean target; read-only `check` and `status` report its
projection without changing it. Explicit per-run overrides are
`--allow-dirty-source` and `--allow-dirty-target`. These do not relax
containment, symlink, divergence, or sensitive-source checks.

## Divergence and provenance

After bootstrap/apply, `.front_repo_sync.json` records the source commit,
whether the source was dirty under an override, the manifest SHA-256, and the
SHA-256 of every projected target file. Commit this state in the front
repository as provenance.

Before apply, the tool compares the target to the previous state. A modified,
deleted, replaced, or symlinked managed file is diverged. An unmanaged file that
would be overwritten or deleted is also diverged. Apply refuses and lists every
path unless the human supplies `--overwrite-diverged`. The state file changes
only after all projection writes succeed, so a failed apply never claims a new
source state.

Stale deletion occurs only inside explicitly managed target directories. Files
beside those directories are never deleted.

## Sensitive sources

The tool refuses `.env*`, `*.pem`, `*.key`, `credentials*`, `secrets*`,
`frutlups.local.toml`, `.git/`, and `local_state/` sources unless the human uses
`--allow-sensitive` for that run. Review the check output before such an
override. A clean tree or manifest entry does not make a secret safe to publish.

The Git executable comes from ignored `frutlups.local.toml` when its absolute
`git` field exists, otherwise from `PATH`. No credential is read. When
`FRUTLUPS_SEAT` is set, `bootstrap` and `apply` refuse; agent seats never
publish.

## Subtree alternative

`git subtree split --prefix <dir>` can fit a product that already occupies one
directory with exactly the desired public layout and commit messages. It cannot
rename paths, curate mappings, or omit tracked members, so the manifest
projection remains the default.
