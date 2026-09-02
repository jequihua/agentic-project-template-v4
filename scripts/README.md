# Scripts

The v2 scaffold is markdown-first. Scripts are optional and the core loop does not
depend on them. Most scripts are standard-library only; the OKF/profile checker
(`artifact_integrity_preflight.py --profile`) additionally requires the declared
PyYAML dependency (see below and `ENVIRONMENT.md`).

## front_repo_sync/

A safe, stdlib-only lane to publish the developed software to a **separate,
outside** front-facing repository — never a nested repo inside this development
repo. `bootstrap_front_repo.py` does the first-copy export (no git init);
`sync_front_repo.py` does ongoing one-way sync into an existing front repo. See
`scripts/front_repo_sync/README.md` and
`docs/template_framework/front_repo_sync.md`.

## local_state_audit.py and local_cleanup.py

Optional local-state hygiene support (stdlib-only).

- `local_state_audit.py --root .` is **read-only**: it reports file/dir counts,
  approximate bytes, the largest top-level directories, and flags nested `.git`
  repos, virtual environments, caches, and large files. It never modifies
  anything.
- `local_cleanup.py` is **dry-run by default** (`--check`); `--apply` deletes only
  rebuildable residue (Python/test caches, coverage, `build`/`dist`, `*.egg-info`,
  temp test folders). It never touches `.git`, virtual environments,
  `local_state/`, memory roots, the evidence/governance workspaces, archives, or
  nested repositories, and never escapes `--root` or follows symlinks.

See `docs/template_framework/security_and_local_state.md` for the policy and the
Windows deletion note.

## slice_contract_check.py

The reference checker for the slice prompt contract v1
(`docs/template_framework/slice_prompt_contract.md`). Read-only, exact-path
driven, deterministic, network-free; stable reason codes in stable order;
`--json` output. It validates a sidecar, proves two projections align, proves a
rendered prompt carries every retained field of a slice entry at a resolved
attempt, and checks a review report's closure record. It reads the closed
vocabularies from the `slice_prompt_contract` block of `frutlups.layout.yaml`
and needs the declared PyYAML dependency (imported lazily; `--help` works
without it). It is never dispatch authority; downstream tools keep their own
parsers and must pass the same fixtures (`tests/fixtures/slice_contract/`).

```text
python scripts/slice_contract_check.py --sidecar <roadmap-stem>.slices.yaml
python scripts/slice_contract_check.py --sidecar <a> --sidecar <b>
python scripts/slice_contract_check.py --sidecar <s> --slice M001-S02 --attempt 2 --rendered <prompt.md>
python scripts/slice_contract_check.py --review-report <review_report.md>
```

`local_state_audit.py --limit-bytes N --exclusions <manifest.json>` is the
read-only pre-launch size check: it lists every undeclared file at or above
`N` bytes outside the governed local surfaces and exits 1 while any exists,
reading the same JSON exclusion manifest the runner reads.

## artifact_integrity_preflight.py

A read-only preflight for the exact Markdown artifacts named on the command line.
Its default checks are standard-library only (the opt-in `--profile` mode below
requires PyYAML). It checks local Markdown links, backticked repository paths,
backticked `test_*` identifiers, machine-local paths, required frontmatter when
requested, unresolved `TBD` values in `status: ready` documents, and a narrow set
of volatile current-state phrases. Hard integrity defects return exit code 1;
historical/volatile language is advisory.

```text
python scripts/artifact_integrity_preflight.py <artifact.md> [<artifact.md> ...]
```

Every cited local path is normalized (either separator) and validated for
repository containment before existence is checked: a citation that escapes the
repository root (via parent traversal or a resolved symlink) and a
machine-absolute path (Windows drive-letter, UNC host/share, or a POSIX home
root) are hard errors.
A path-shaped citation is one with a separator whose final component has a file
extension, or whose top-level component already exists; slash-separated prose
whose components are ordinary words is ignored. A missing path-shaped citation is
a hard error even when its top-level directory is absent.

Use `--json`, `--require-frontmatter`, or `--check-volatile` as needed. A roadmap
may repeat `--allow-missing <repo-relative-path>` for explicit planned outputs;
these remain visible as warnings but do not fail the run. An `--allow-missing`
value is itself normalized and containment-checked, so it can only downgrade a
safe repository-relative future path — never an escape or machine-absolute path.
The tool never repairs files and never scans other files unless they are
explicitly named. Use repeatable `--tests-root <repo-relative-directory>` when an
artifact cites test identifiers from a test tree other than this project's own
`tests/` directory.

### Illustrative example paths

Use `example://...` (for example `example://temp/report.html`) as the canonical
notation for an illustrative, non-repository path inside tracked Markdown. The
citation normalizer already ignores URL-like tokens containing `://`, so
illustrative notation is never treated as a repository citation and needs no
allowance. Keep the three cases distinct:

1. `example://temp/report.html` is illustrative notation, not a repository
   citation; it is never checked and never an error.
2. A real planned repository-relative path is cited normally and repeated via
   `--allow-missing <repo-relative-path>`; it remains visible as a warning.
3. A broken repository citation or a raw machine-local absolute path remains a
   hard error.

Do not use illustrative notation to disguise a real repository citation.

### Optional `--profile` framework-profile check

`--profile` adds an opt-in, read-only check of the pinned framework profile
`0.1-rc.1` (defined in `docs/template_framework/okf_pkg/okf_profile_v0_1.md`). It is backed by a mandatory,
bounded PyYAML `SafeLoader` adapter (`okf_yaml_profile.py`) — the declared PyYAML
dependency must be installed (see `ENVIRONMENT.md`); absent it, `--profile` fails
clearly (exit 2) with no custom-parser fallback. It reports three **separate**
results per artifact — `okf_concept`
(`pass`/`fail`/`unverified`/`not_evaluated`), `framework_profile`
(`pass`/`fail`/`not_applicable`), and `execution_eligibility` (always
`not_evaluated`) — each with an `OKF_*`/`PROFILE_*` reason code or `null`. PyYAML
owns YAML syntax; project code owns Markdown framing, resource limits,
duplicate-key rejection, and the producer profile. Invalid YAML is
`OKF_YAML_INVALID`; a bounded resource refusal is `unverified`
`OKF_PARSE_LIMIT_EXCEEDED`; valid YAML outside the producer subset is OKF `pass`
with profile `fail` (`PROFILE_YAML_OUT_OF_SUBSET`). It never decides execution
eligibility. Without `--profile`, behavior, output, and exit status are unchanged.

```text
python scripts/artifact_integrity_preflight.py --profile <artifact.md> [...]
python scripts/artifact_integrity_preflight.py --profile --json <artifact.md> [...]
```

Profile mode reads each artifact once as bytes under a total-input bound
(`MAX_ARTIFACT_BYTES = 1 MiB`) before UTF-8 decode, and enforces a separate,
smaller frontmatter-block bound (`MAX_FRONTMATTER_BYTES = 64 KiB`, 500 lines, 8,192
chars/line) plus token/node/depth/scalar/collection/alias limits before and during
PyYAML. Oversized input and pathological nesting are bounded refusals
(`OKF_PARSE_LIMIT_EXCEEDED`) with no traceback; malformed UTF-8 is a pre-L1 read
error (OKF `not_evaluated`). The default (non-`--profile`) preflight keeps its
standard-library behavior and imposes no total-input limit. Install the project first
(`pip install -e .`, see `ENVIRONMENT.md`).

With `--profile --json` the output adds `schema_version:
"template.okf_profile_check.v2"`, per-layer summary counts, and an `artifacts`
list in input order; it is deterministic and never mutates inputs. The exit status
is nonzero on an integrity error, an L1/L2 `fail`, or an OKF `unverified` resource
refusal (so refusal is not mistaken for success). The pinned outcomes are frozen by
`tests/fixtures/okf_profile/manifest.json`.

## generate_okf_navigation.py

A standard-library-only generator that
renders one deterministic, **disposable** navigation read model,
`08_pkg/generated/okf_navigation.md`, from one explicit human-authored manifest,
`08_pkg/okf_navigation_manifest.json`. The view only lowers the cost of locating
canonical sources; it is **not authoritative**, never copies live state, and loses
no information when deleted. PyYAML is not used here (the manifest is JSON).

```text
python scripts/generate_okf_navigation.py            # render; write only if changed
python scripts/generate_okf_navigation.py --check     # read-only staleness check
```

The CLI exposes no arbitrary root, manifest, source, or output path — the manifest
and output paths are fixed. It resolves the repository root independently of the
working directory, validates every manifest source as a unique, contained, existing
regular file (rejecting absolute/backslash/parent-traversal/drive-letter paths,
output-as-input, and symlink-based escapes), enforces finite manifest/group/source/
path/label bounds, keeps the output beneath `08_pkg/generated/`, emits UTF-8 with LF
endings and one trailing newline (no timestamp, hostname, absolute path, or
run-specific data), does not rewrite an already byte-identical output, and writes a
changed output atomically. Exit contract: the default command returns `0` on success
(written or already current) and `2` on an invalid/unsafe manifest, source, or output
state. `--check` is strictly read-only and returns `0` (current), `1` (missing or
stale), or `2` (invalid arguments or an invalid/unsafe manifest/source/output).
Expected failures print a concise diagnostic without a traceback and leave any existing
output byte-identical. Deleting the generated file loses no canonical information;
manual navigation via `08_pkg/README.md` and the linked contracts still works without
the generator.

Correction 017 closes the manifest-to-Markdown gap. That safety boundary uses strict
**rejection** (not escaping), so the current benign output stays byte-identical: the
rendered title, group titles, and source labels must be trimmed, single-line, entirely
printable, and free of the delimiters `` \ ` [ ] < > ``; `view_id`/`group_id` must be
diagnostic-safe ASCII (`[A-Za-z0-9][A-Za-z0-9_-]*`); and each source-path segment must
be portable ASCII (letter/digit start; letters, digits, dots, underscores, hyphens; no
trailing dot). Unsafe values are rejected with a concise field-specific message before
any write. Correction 018 completes the output-filesystem contract: every expected
output existence/read/resolution/stat/mkdir/temp-create/open/write/replace failure in
both the default command and `--check` becomes the concise exit 2 (relative path and
sanitized OS-error text only, no traceback, no machine-local path), including the two
`os.path.realpath` calls and the fixed-path stat inspection in `_safe_output_path`;
and the raw `tempfile.mkstemp` descriptor is owned by the writer until `os.fdopen`
returns, so an `os.fdopen` failure closes the descriptor before unlinking the temp
path — a pre-existing output is left byte-for-byte and no `.okfnav-*.tmp` residue
remains.

Candidate future scripts:

- state consistency check;
- prompt / review index generator;
- self-report skeleton writer;
- environment check.

