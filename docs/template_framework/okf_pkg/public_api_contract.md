# Template v3 Public API Contract

Status: the profile and fixture contracts, the PyYAML-backed OKF/profile checker,
the disposable navigation view, the opt-in authoring/migration surface, and the
architect operating card ship for candidate profile `0.1-rc.1`.

## Framework-Profile Contract

The versioned framework-profile document contract is defined canonically in
`docs/template_framework/okf_pkg/okf_profile_v0_1.md`, which pins the candidate
`framework_profile: "0.1-rc.1"`. That file is the single source for profile
fields, namespaces, artifact types, the YAML producer envelope, and the separated
OKF/profile/execution result vocabulary; this contract does not restate it. The
candidate and its fixture meanings are pinned; it is not stable `0.1`.

## Optional Profile Checker Surface (PyYAML)

`scripts/artifact_integrity_preflight.py` exposes an opt-in `--profile` mode: a
read-only OKF/profile checker over explicitly named Markdown artifacts, backed by a
mandatory pure-Python PyYAML `SafeLoader` adapter (`scripts/okf_yaml_profile.py`).
It emits three separated layer results (`okf_concept`, `framework_profile`,
`execution_eligibility`) with `OKF_*`/`PROFILE_*` reason codes or `null`, and a
deterministic `--profile --json` shape identified by
`schema_version: "template.okf_profile_check.v2"`. It follows the manifest's
`full_parser` oracle, distinguishes invalid YAML (`OKF_YAML_INVALID`) from a bounded
resource refusal (`OKF_PARSE_LIMIT_EXCEEDED`) from valid-out-of-profile YAML
(`PROFILE_YAML_OUT_OF_SUBSET`), never decides execution eligibility, never mutates
inputs, and never changes default (non-`--profile`) behavior. There is no
custom-parser fallback: absent PyYAML, `--profile` fails clearly (exit 2). It is
installed through the editable project metadata (`pip install -e .`), which declares
PyYAML. Profile mode reads each artifact once under a 1 MiB total-input bound before
decode. The pinned outcomes are frozen by `tests/fixtures/okf_profile/manifest.json`
(test/oracle data, not a runtime API).

## Optional Navigation-View Surface

`scripts/generate_okf_navigation.py` is a standard-library-only generator that
renders one deterministic, disposable navigation read model,
`08_pkg/generated/okf_navigation.md`, from one explicit human-authored manifest,
`08_pkg/okf_navigation_manifest.json`. It exposes exactly two fixed commands — the
default render (writes only when the output differs; exit `0` on success, `2` on an
invalid/unsafe manifest, source, or output state) and `--check` (read-only; exit `0`
current, `1` missing/stale, `2` invalid/unsafe). It exposes no arbitrary root,
manifest, source, or output path; validates every source as a unique, contained,
existing regular file (rejecting absolute/backslash/traversal/drive-letter paths,
output-as-input, and symlink escapes) under finite manifest/group/source/path/label
bounds; keeps the output beneath `08_pkg/generated/`; and emits byte-reproducible
UTF-8/LF output with no run-specific data. Unsafe rendered text (untrimmed,
multi-line, non-printable, or containing `` \ ` [ ] < > ``), non-ASCII identifiers,
and non-portable source-path segments are strictly rejected before any write rather
than escaped, keeping the benign output byte-identical. Every expected output
existence/read/resolution/stat/mkdir/temp-create/open/write/replace failure in both
generate and `--check` becomes the documented concise exit 2 (relative path and
sanitized OS-error text only, no traceback, no machine-local path), and the raw
`tempfile.mkstemp` descriptor is closed if `os.fdopen` fails before ownership
transfers so no descriptor or `.okfnav-*.tmp` residue is left and a pre-existing
output is preserved byte-for-byte. The view is **not authoritative**, never copies
live state, and loses no canonical information when deleted (manual navigation via
`08_pkg/README.md` remains). This surface adds no dependency (PyYAML is not used
here).

## Opt-In Authoring And Migration Surface

A documentation and template-routing surface makes the profile usable for new
authoring and gradual adoption without changing the profile or converting legacy
documents. It comprises the canonical guide
`docs/template_framework/okf_authoring_and_migration.md` (a profiled `framework_doc`),
the minimum-block/type mapping and adoption/rollback/version-change rules it defines,
and concise routing added to the `coding_prompt`, `review_prompt`, and `self_report`
templates. Opt-in is per exact new artifact path, the minimum block is `type` plus
`framework_profile: "0.1-rc.1"`, legacy no-frontmatter remains the default, and
authors validate opted-in paths read-only with the existing `--profile` checker. This
surface adds **no** YAML writer, serializer, converter, bulk-migration tool, inventory
CLI, or repository scanner, and no new dependency; it makes no round-trip/unknown-field
preservation claim and infers no authority from profile conformance. Profile
`0.1-rc.1` remains a candidate rather than stable `0.1`.

## Architect Operating Card Surface

`docs/template_framework/architect_operating_card.md` is a profiled `framework_doc`
with a bounded line/word budget and a registry-validated type-selection aid: the
normal loop, the four OKF rules, the artifact-type selection aid, the authority
warning, and the escalation triggers. It is a routine operator quick start, not an
authority, and copies no canonical contract. Its reusable limits, exact type-aid
partition, read-budget, authority, and escalation protections are covered by
`tests/test_architect_operating_card.py`.

## Current Public Surface

The shipped surface is the inherited repository structure, documents, scripts, and
validation command, strengthened by the three prerequisite safeguards
(stable-reference guidance, the read-only `scripts/artifact_integrity_preflight.py`,
and proportional fast-close), plus the profile and fixture contracts, the optional
PyYAML-backed `--profile` checker, the navigation generator
(`scripts/generate_okf_navigation.py`) with its tracked disposable view
(`08_pkg/generated/okf_navigation.md`), the opt-in authoring/migration documentation
surface, and the architect operating card. No OKF writer, converter, or inventory CLI
is implemented, and no llloom implementation exists. Per-slice review status and
routing live in `PROJECT_STATE.md`.

## Naming And Path Decisions

Exact module paths, callable names, CLI flags, schemas, reason codes, and output
locations are decided by the corresponding reviewed slices. Intake does not
freeze speculative names.

## Error Behavior

Checks separate hard errors, advisory warnings, unsupported/unverified inputs,
profile failures, and execution refusals. They must not call unsupported valid YAML
invalid OKF or infer execution eligibility from format conformance.

## Compatibility Rules

- Baseline manual/offline use and legacy no-frontmatter documents remain valid.
- No new baseline runtime dependency is allowed without approval.
- Candidate profile changes are explicit and fixture-backed.
- Stable incompatible changes require a new major version and migration path.
