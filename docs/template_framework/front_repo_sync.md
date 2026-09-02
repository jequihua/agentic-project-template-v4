# Front-Facing Repository Pattern

A project made from this template is a **development repository**: it holds the
artifact-first loop (brief, governance, prompts, reviews, package, tests). The
software being developed is **not** initialized as a nested git repository inside
it — nested repos create a hidden second source of truth and confuse tooling.

When the software needs a public/front-facing home, that home is a **separate,
outside** repository, populated as a *curated projection* of this development
repo. The projection is defined by a manifest, not by copying everything.

## Tooling

The lane lives in `scripts/front_repo_sync/` (stdlib-only):

- `bootstrap_front_repo.py` — first-copy export into a new non-repo directory,
  before the front repo exists. It never initializes git.
- `sync_front_repo.py` — ongoing one-way sync (development repo → front repo)
  into an existing front-facing git repo.
- `front_repo_sync_manifest.example.toml` — the curated projection to adapt.
- `front_repo_gitignore` — a starting `.gitignore` for the front repo.

## First publication flow

1. `bootstrap_front_repo.py --check --output-dir <DIR>` (prints the plan).
2. `bootstrap_front_repo.py --apply --output-dir <DIR>` (writes the clean tree).
3. The human owner inspects `<DIR>` and runs any desired validation.
4. The human owner runs `git init`, makes the first commit, adds a remote, pushes.
5. Future updates use `sync_front_repo.py --check` then `--apply`.

Always run `--check` before `--apply`.

## Safety rails

- No nested repos: the destination must not be inside the development repo, the
  development repo must not be inside the destination, and they must not be the
  same path.
- Bootstrap targets a non-repo directory (refuses an existing `.git`; refuses a
  non-empty directory unless `--allow-non-empty-output`).
- Sync requires an existing target with `.git`, clean before `--apply` unless
  `--allow-dirty-target`.
- Manifest source paths must resolve inside the development repo (no `../` escape,
  no outside-repo absolute paths); the projection cannot read parent folders,
  secrets, or arbitrary machine paths.
- Directory mirrors do not follow symlinks: a symlinked file or subdirectory in a
  mirrored source is rejected (not followed), so the walk cannot read outside the
  development repo through a symlink.
- All writes/deletes stay inside the resolved destination; missing sources fail.
- The tool never commits, pushes, opens PRs, runs `git init`, or calls frutlups.

## Ownership

Commits in the front-facing repo are governed by the human/project workflow, not
this tool — the sync only projects files. Pull requests remain human-requested by
default (see `method.md` Commit Discipline → Pull Requests).
