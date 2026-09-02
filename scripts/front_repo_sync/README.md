# Front-Facing Repo Bootstrap And Sync

A project made from this template is a **development repository** — where the
artifact-first loop lives. The software being developed is **not** initialized as
a nested git repo inside it. If you need a public/front-facing software repo, it
is a **separate, outside** repository populated from this one.

This lane gives you a safe, stdlib-only way to do that:

- `bootstrap_front_repo.py` — first-copy export into a new non-repo directory
  (never initializes git);
- `sync_front_repo.py` — ongoing one-way sync into an existing front-facing git
  repo;
- `front_repo_sync_manifest.example.toml` — the curated projection (adapt it);
- `front_repo_gitignore` — a starting `.gitignore` for the front repo;
- `_front_repo_common.py` — shared core.

## First publication flow

1. `python scripts/front_repo_sync/bootstrap_front_repo.py --check --output-dir <DIR>`
2. `python scripts/front_repo_sync/bootstrap_front_repo.py --apply --output-dir <DIR>`
3. The human owner inspects `<DIR>` and runs any desired validation.
4. The human owner initializes it: `git init`, first commit, add remote, push.
5. Future updates: `python scripts/front_repo_sync/sync_front_repo.py --check --target-repo <DIR>`
   then `--apply`.

Always run `--check` before `--apply`.

## What it refuses to do

- It refuses an output/target that is **nested inside** the development repo, or a
  development repo nested inside the destination, or an identical path (no nested
  repos, no recursive copy).
- Bootstrap refuses a directory that already contains `.git`, and a non-empty
  directory unless you pass `--allow-non-empty-output`.
- Sync requires the target to exist and contain `.git`, and to be clean before
  `--apply` unless you pass `--allow-dirty-target`.
- Missing source files fail with a non-zero exit.
- Manifest **source** paths must resolve inside the development repo (no `../`
  escape, no outside-repo absolute paths) — sources are a curated projection from
  inside the repo only, never parent folders, secrets, or machine paths.
- Directory mirrors do **not** follow symlinks: a symlinked file or subdirectory
  encountered during a source walk is rejected, so the projection cannot read
  outside the development repo through a symlink.
- All writes/deletes stay inside the resolved destination root.
- It never runs `git init`, `git add`, `git commit`, `git push`, `gh`, or
  frutlups.

## Adapting the manifest

Source paths are relative to the development repo root; target paths are relative
to the front-facing repo root. The example maps a package profile
(`08_pkg/...` → `src`, `tests`, `README.md`, `pyproject.toml`). Change these to
match what your project should publish. Do not hardcode machine-local default
paths; pass `--output-dir` / `--target-repo` or set project-local defaults.

Commits and PRs in the front-facing repo remain governed by the human/project
workflow — this tool only projects files. PRs remain human-requested by default.
