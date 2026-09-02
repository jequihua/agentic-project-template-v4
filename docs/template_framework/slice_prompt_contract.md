# Slice Prompt Contract

Contract version: 1
Legacy scaffold digest: `be60e7c354df33fe13477eef56b6fb33e4e2a4d11eb07ed5b62eb4916143ae7e`

The typed, versioned, per-slice specification from which a safe coding prompt
is rendered without architectural invention at generation time. It exists
because a roadmap that reads as detailed to a human carries no field a tool is
obliged to honor: the first fully autonomous campaign lost its largest stop
class to prompts that named a task ("publish the closure decision") with no
exact write path. This contract makes the slice definition data.

Ownership: the template owns the schema, the canonical rendered form, the
validity rules, and the fixtures. Consumers (frutlups' renderer and prompt
health; any conforming runner) implement their own parsers and must reproduce
the fixtures in `tests/fixtures/slice_contract/manifest.json`. The closed
vocabularies are declared ONCE, in the `slice_prompt_contract` block of
`frutlups.layout.yaml`; the tables in section 4 are proven equal to it in both
directions by `tests/test_slice_contract.py`, and the reference checker
`scripts/slice_contract_check.py` reads them from there.

## 1. Declaration, Opt-In, Rollback, Fence

- The typed source is a **sidecar YAML beside each selected prose roadmap**,
  named `<roadmap-stem>` + the layout's `sidecar_suffix` (`.slices.yaml`).
  The prose roadmap stays the human narrative and is untouched; the sidecar's
  `roadmap` key names it and must resolve to an ordinary regular file beside
  the sidecar — not a symlink or junction, and its strictly resolved parent is
  the sidecar's own directory.
- **Absent sidecar = legacy v3 semantics byte-for-byte.** Nothing about a
  project without a sidecar changes.
- **Opt-in is one reviewed migration step** with exactly two effects: add the
  sidecar(s), and set the layout's `prompts.coding_template` to the v1
  scaffold `prompts/templates/coding_prompt_contract_v1.md`. Rollback reverses
  both in one step. The legacy scaffold `prompts/templates/coding_prompt.md`
  is byte-identical to its pre-contract form (digest above).
- **Old-consumer fence.** A legacy consumer pointed at an opted-in project must
  refuse before writing any prompt and may not emit a legacy-shaped prompt.
  Observed mechanism against released frutlups 0.1.8 (tag object
  `f370e0743acf6f73ad08eaa13b755c87d41c5628`, peeled commit
  `2d4f1c1ff76b057c79a106d6b586d4949110ed31`): the v1 scaffold's slots
  (`TBD:<field>` tokens, the Write Manifest form) do not match the legacy
  slot forms its renderer consumes, so it exits 1 with `would_write: false`
  and nine "slot missing" diagnostics — not an unconsumed-`TBD` diagnostic.
  The executable proof input is
  `tests/fixtures/slice_contract/optin_project_for_old_consumer/` (compose
  script, both roadmap projections, both sidecars, the expected refusal).
- **Unknown contract version fails closed.** A request for autonomous prompt
  generation in a project with no sidecar refuses with a migration
  diagnostic; it never silently opts the project in.
- **Cross-projection alignment.** A project with an active and a detailed
  roadmap projection carries one sidecar per projection: both declare the
  same version, each `roadmap` link resolves to its prose file, an
  overlapping slice id is semantically identical in both, and a missing
  counterpart, version mismatch, or any field mismatch fails closed before
  rendering. No consumer silently prefers one conflicting sidecar.

Why a sidecar and not blocks inside the roadmap: the released legacy roadmap
parser treats any `Label:` line inside a milestone section as a field and
absorbs continuation lines until the next boundary, so typed YAML placed in
the roadmap would be folded into rendered prompt text without a diagnostic.

## 2. Sidecar Grammar

Top level:

```yaml
slice_prompt_contract_version: 1
roadmap: active_roadmap.md      # the prose roadmap beside this file
slices:
  - slice: M001-S01
    # ... one entry per slice, fields in section 3
```

The positive all-fields fixture (`tests/fixtures/slice_contract/all_fields.slices.yaml`)
is the normative example: one routine `ready` slice and one live, corrective,
attempt-`002` slice exercising every field. Its attempt-`001` twin
(`tests/fixtures/slice_contract/all_fields_attempt_001.slices.yaml`) differs
only in the attempt identity.

## 3. Per-Slice Fields

All fields are required unless marked; `none` is a contract-defined explicit
value and is distinct from a missing key. "Record path" below means an exact
repository-relative file path: no directory, glob, absolute form, or parent
traversal.

| Group | Field | Rule |
| --- | --- | --- |
| identity | `slice` | `Mnnn-Snn`, unique per sidecar, belongs to `milestone` |
| identity | `title`, `milestone` | non-empty; `milestone` is `Mnnn` |
| identity | `authored_by` | `architect_reviewer` or `human_owner` — never a coder seat or a runner |
| dispatch | `status` | `frozen` (default; valid planning material, not current work) or `ready` |
| dispatch | `dispatch_authority` | required when `ready`: record path of the owner note or controller record granting dispatch; `ready` also presumes every opening gate is satisfied |
| dispatch | `attempt` | three zero-padded digits as a string, `"001"` through `"999"`; required for corrective entries and whenever a write uses `create_fresh_per_attempt`; **one attempt identity per entry** — a different attempt is a different entry (sidecar) |
| class | `strictness` | `Level 1` … `Level 4` |
| class | `mode` | a workflow mode (`docs/template_framework/workflow_modes.md`) |
| class | `live`, `corrective` | booleans; they switch the envelope and correction requirements |
| task | `task` | multi-line specification; a task equal to the title is invalid |
| task | `active_workspaces`, `read_first` | non-empty lists; `read_first` entries are exact repository-relative paths |
| writes | `writes` | non-empty list of write-manifest entries (section 4) |
| scope | `non_goals`, `verification`, `definition_of_done` | non-empty lists; verification entries are exact commands or checks |
| gates | `opening_gates` | `none` or a non-empty list of `{kind, reference[, sha256 \| repository, tag, commit]}`; for path-kind gates the reference is a record path |
| inputs | `external_inputs` | `none` or a non-empty list of `{repository, path, role, identity}`; `path` is a record path; `role` per `docs/template_framework/external_repository_roles.md` |
| inputs | `candidate_identity` | `none` or `{strategy, paths, identity_value}`; `paths` are record paths |
| correction | `correction` | required iff `corrective: true`, else `none` (section 6) |
| live | `execution_envelope` | required iff `live: true`, else `none` (section 7) |
| objective | `objective.success_criteria`, `objective.closure_proof` | non-empty lists; closure proof names the evidence the review looks for, distinct from the implementation's definition of done |

## 4. Vocabularies, Write Manifest, Role/Type Matrix

### Vocabularies

Each row is exactly the layout's list of the same name (proven by test).

| Vocabulary | Values |
| --- | --- |
| `entry_status_values` | `frozen`, `ready` |
| `authored_by_values` | `architect_reviewer`, `human_owner` |
| `artifact_types` | `implementation`, `test`, `evidence`, `analysis`, `documentation`, `fixture`, `generated_output`, `config`, `self_report`, `coding_prompt`, `review_prompt`, `review_report`, `verdict_record`, `acceptance_record`, `routing_state`, `framework_doc`, `governance_record` |
| `role_owners` | `coder`, `reviewer`, `architect_reviewer`, `human_owner`, `runner` |
| `retry_policies` | `create_once`, `create_fresh_per_attempt`, `modify`, `append_only` |
| `gate_kinds` | `accepted_review`, `owner_note`, `artifact_exists`, `artifact_identity`, `pinned_external_release`, `human_launch_word`, `external_answer` |
| `cleanup_values` | `retain_until_closure`, `delete_after_evidence`, `quarantine` |
| `result_handling_values` | `preserve_and_stop`, `preserve_and_continue` |
| `objective_status_values` | `achieved`, `not_achieved`, `not_applicable`, `indeterminate` |
| `sentinels` | `TBD`, `<value>`, `<path>`, `<one move>` |

### Write manifest

Each `writes` entry: `path`, `artifact_type`, `role_owner`, `retry_policy`.

- `path` is an exact repository-relative **file** path. Directory paths,
  globs, absolute paths, parent traversal, and implicit neighbouring-file
  authority are invalid. A task noun with no declared path grants nothing.
- `retry_policy`: `create_once` (never overwrites an existing artifact),
  `create_fresh_per_attempt` (requires exactly one attempt token in the
  path), `modify` (only the exact authorized working artifact; never across an
  accepted-history fence), `append_only` (never alters prior bytes).

### Role/type matrix

Each row is exactly the layout's `role_type_matrix` entry of the same role
(proven by test). A row outside it is invalid.

| Role | May own |
| --- | --- |
| `coder` | `implementation`, `test`, `evidence`, `analysis`, `documentation`, `fixture`, `generated_output`, `config`, `self_report` |
| `reviewer` | `review_prompt`, `review_report`, `evidence`, `analysis`, `documentation` |
| `architect_reviewer` | `implementation`, `test`, `evidence`, `analysis`, `documentation`, `fixture`, `generated_output`, `config`, `coding_prompt`, `review_prompt`, `review_report`, `verdict_record`, `acceptance_record`, `framework_doc`, `governance_record` |
| `human_owner` | `documentation`, `coding_prompt`, `review_prompt`, `verdict_record`, `acceptance_record`, `governance_record`, `framework_doc`, `config` |
| `runner` | `coding_prompt`, `review_prompt`, `verdict_record`, `routing_state`, `generated_output`, `evidence` |

Exactly one coder-owned `self_report` is required; it is a claim artifact,
never review or acceptance authority. Reserved paths classify the artifact
regardless of label: a path ending in `_self_report.md`, `_review_report.md`,
or `_verdict_record.md`, or under the review-prompt or coding-prompt folders,
IS that artifact type; labelling it `governance_record` does not bypass the
matrix. Under contract v1 the `review_prompt` is not coder-owned (a deliberate
tightening; the legacy `coder_may_create_review_prompt` convention is
unchanged for legacy projects); it may be owned by `reviewer`,
`architect_reviewer`, `runner`, or `human_owner` according to project policy.
A coder-owned `review_report`, `verdict_record`, `acceptance_record`, or
`routing_state` is always invalid.

### Attempt grammar

Every corrective or fresh-per-attempt operation carries an attempt identity.
A write path may contain at most one attempt token (layout `attempt_token`,
`{attempt}`); an attempt-bearing entry's `local_output_root` carries exactly
one token, an entry without an attempt carries none. The token is source
syntax only. The rendered prompt carries the resolved exact values
(`..._attempt_002_...`), never the token or any sentinel. A rendered prompt
whose write target or output root resolves to another attempt's value reuses
history and is invalid, and confirming a different attempt than the entry
declares is refused (`attempt_mismatch`). Deterministic allocation and
historical collision checks are the operating tool's job; this contract fixes
the grammar and the fixtures.

## 5. Dispatch Status Is Not Validity

A valid entry is not automatically dispatchable. Pre-created entries for
later roadmap slices stay `status: frozen`: they validate, they are never
current work, and no consumer promotes them silently. `ready` requires every
opening gate satisfied and a recorded `dispatch_authority`. The renderer
copies the entry's `status`, `authored_by`, and `dispatch_authority` into the
prompt's workflow metadata; a prompt is dispatchable only at workflow
`status: ready`, and a ready prompt contains no unresolved sentinel and no
deleted-section residue (`scripts/artifact_integrity_preflight.py` errors on
both). Dispatch status is read line-based: every line-start `status:` line
in a prompt is exactly `status: <value>` with the entry's value, plain and
unquoted, and a contract prompt carries at least two (the workflow metadata
and the typed entry of section 8); the checker refuses any other spelling
(`typed_entry_status_line`, `rendered_status_disagreement`). The preflight
reads the same lines by a total line rule with no fence or YAML parsing: it
normalizes only matching surrounding quotes, and a disagreement, any other
spelling (tag, flow mapping, block scalar), or a contract prompt with fewer
than two status lines is `status_ambiguous` — the prompt is treated as
ready and fails closed. `artifact_exists` alone never gates a consumption of bytes that
matter; use `artifact_identity` (reference + `sha256`) or
`pinned_external_release` (`repository`, `tag`, `commit`).

## 6. Corrective Entries And The Governed Transaction

A corrective entry (`corrective: true`) carries a `correction` block with
every field typed so the rendered Correction Scope Map needs no invention:

- `findings`: list of `{id, violated_invariant, prior_disposition,
  authority_action, coder_obligation, closure_proof}`;
- `prior_evidence`: list of `{path, sha256}` (record paths);
- `controlling_ruling`: the record path of the owner note, or
  `{disputed: <owner-note record path>}` when authority is disputed;
- `closure_proof`: list (the block-level required closure proof);
- `claims_withdrawn`, `evidence_invalidated`: `none` or a non-empty list;
- `minimum_rerun_set`: non-empty list.

"Allowed files and claims" is derived — exactly the write manifest — and has
no separate field.

Authority and atomicity:

- sidecar entries are authored by `architect_reviewer` or `human_owner` —
  never by a coder seat and never by a runner's writer;
- a corrective proposal is not dispatchable until a released governed
  operation of the operating tool validates and records its sidecar entry;
  that transaction may create the entry and render the prompt atomically and
  publishes neither unless the whole transaction is valid;
- a runner's guarded writer applies exactly one artifact — the rendered
  prompt at its declared path — and never writes the sidecar;
- retries never overwrite an accepted sidecar entry or a historical prompt.

## 7. Execution Envelope (live entries)

Required fields: `timing_probe` (`command`, `expected_seconds`),
`agent_budget_seconds`, `subprocess_budget_seconds` (model/agent wall and
scientific subprocess wall are separate), `expected_wall_seconds`,
`hard_wall_seconds` (all positive numbers), `frozen_override` (`none` or
`{authority: <owner-note record path>}`), `environment_bindings` (`none` or a
non-empty list of `{name, value_sha256}` — names and hashes only; a `value`
key is invalid), `identities` (`none` or a non-empty list; arm / group /
order / attempt), `retained_bytes_max`, `local_output_root` (must resolve, after
normalization, under the declared local-state root `local_state/`; carries the
attempt token per section 4), `cleanup` (`retain_until_closure`,
`delete_after_evidence`, `quarantine`), `negative_result_handling` and
`stopped_result_handling` (`preserve_and_stop`, `preserve_and_continue`).
`delete_after_evidence` is a declared lifecycle policy, never deletion
authority by itself.

Enforcement (stated honestly; the drive's version-5 answer is the source):

| Field | Enforced by |
| --- | --- |
| budgets, walls, `frozen_override` | the runner validates them against its own policy and gate at admission; an envelope exceeding the policy/gate ceilings is refused, never silently overridden; an override still needs the policy to admit it |
| `environment_bindings` | the runner injects the value declared in its policy/gate and refuses at admission when the policy value's hash differs from the slice's `value_sha256`; a project declaring a binding here must declare its value runner-side |
| `timing_probe`, `retained_bytes_max`, `local_output_root`, `cleanup`, result handling | template/operator-enforced (the pre-launch audit command and the human gate); useful contract data a later runner version may consume |

Every runner-consumed field reaches the runner only through the operating
tool's versioned machine payload; no runner parses the sidecar. The human
gate `06_infra/live_validation_gate.md` records approval and the launch word
against the envelope; a live entry without a complete envelope is not
dispatchable.

## 8. Canonical Rendered Form

One scaffold per regime. The legacy scaffold is unchanged. The v1 scaffold
`prompts/templates/coding_prompt_contract_v1.md` carries typed slots and ends
with a `## Typed Entry` section whose single fenced `yaml` block is the
**machine carrier**: the sidecar entry for the slice, every `{attempt}` token
resolved in every string leaf, emitted from the renderer's typed model.
Losslessness is equality, not parsing. The reference checker strict-loads
that block (duplicate keys refused, size bounded) and compares the loaded
mapping with the attempt-resolved entry; a missing, altered, or undeclared
leaf is `typed_entry_mismatch`, an absent block `typed_entry_missing`, a
second block in the section `typed_entry_ambiguous`, an unloadable block
`typed_entry_unparseable`. Any YAML serialization that loads to the same
mapping conforms (key order and quoting are free) with one normative
exception: the top-level `status` key is the plain line-start line
`status: <value>` (`typed_entry_status_line`), because dispatch status is
read by line-based tools (section 5). The suite deletes and
alters every leaf of every canonical rendering's block, appends an undeclared
key, and duplicates the block, and proves refusal each time; it also proves
that pipe- and newline-bearing scalars round-trip.

The prose sections are the human rendering of the same entry. The checker
never extracts a field value from prose; the prose is checked only for what
a line-based rule states exactly:

- section presence, uniqueness, and applicability per the layout
  (`rendered_sections_required`, `rendered_sections_conditional`) and, once
  those hold, section order per the layout's `rendered_section_order`
  (`rendered_section_order`), headings counted at line start; a
  not-applicable group has no section and no `*Conditional:*` residue;
- no slot token, sentinel, or unresolved `{attempt}` token survives;
- the Write Manifest table carries exactly the declared rows
  `| path | artifact_type | role_owner | retry_policy |` (resolved paths),
  one per manifest entry, in any order, and nothing else: a missing row is
  `rendered_manifest_row_missing`, an extra or duplicate row
  `rendered_manifest_row_undeclared` — the table is write authority read by
  the coder, so it is exact by cardinality, not by presence;
- the Self-Report section carries the manifest's self-report path exactly
  once, as its only backticked path line — a multiset equal to the
  singleton (`rendered_self_report_path_missing` when absent,
  `rendered_self_report_path_undeclared` for a different path or a second
  occurrence);
- every line-start `status:` line in the prompt equals `status: <value>`
  with the entry's value, and at least two exist (the workflow metadata and
  the typed entry): `rendered_status_disagreement`;
- an attempt-bearing entry's resolved paths do not appear with another
  attempt number (history reuse);
- `--attempt`, when given, equals the entry's own attempt.

Two prose surfaces remain authority-bearing rails because the coding agent
reads them directly: the workflow status line and the Write Manifest table
with its Self-Report path. They are checked exactly, as above. Elsewhere —
task, lists, candidate identity, envelope narrative — a prose value that
disagrees with an exact typed entry is a renderer-quality defect, not a
contract violation: such fixtures are tagged `prose-not-authority` and
render `pass`. A consumer that needs a field reads the typed entry; no
machine consumer takes the descriptive prose as authority.

| Typed field | Human rendering (not authority) |
| --- | --- |
| `milestone`, `slice`, `title`, `authored_by`, `mode`, `strictness`, `live`, `corrective`, `attempt`, `status`, `dispatch_authority` | workflow metadata block (the `attempt` and `dispatch_authority` lines are removed when the entry has none) |
| `task`, `active_workspaces`, `read_first` | Task, Active Workspaces, Read First |
| `writes` | Write Manifest table (resolved paths; exact rows are checked) and the Self-Report path (checked) |
| `opening_gates` | Opening Gates (conditional) |
| `external_inputs` | External Repositories (conditional) |
| `correction` | Correction Scope Map (conditional) |
| `candidate_identity` | Candidate Identity (conditional) |
| `execution_envelope` | Execution Envelope (conditional; resolved output root) |
| `objective` | Objective And Closure Proof |
| `non_goals`, `verification`, `definition_of_done` | Non-Goals, Verification, Definition Of Done |
| seat conduct | Seat Conduct (static pointer to `CLAUDE.md`) |
| the whole entry, attempt-resolved | Typed Entry (the carrier; equality is the proof) |

Section order and the required/conditional split are declared in the layout
(`rendered_section_order` — equal to the scaffold's heading sequence, proven
by test — with `rendered_sections_required` and
`rendered_sections_conditional`; `Typed Entry` is required and last). The
canonical renderings are
`all_fields_rendered_m001_s01.md` (routine), `frozen_entry_rendered_m001_s01.md`
(frozen: no dispatch-authority line), `all_fields_rendered_m002_s02_attempt_002.md`
(live corrective, from `all_fields.slices.yaml`) and
`all_fields_rendered_m002_s02_attempt_001.md` (from its attempt-001 twin).
Downstream conformance means: the typed entry block equals the entry, and the
prose satisfies the line-based rules above.

## 9. Review Side: The Closure Record

Every review report carries exactly one `## Closure Decision` section as the
section immediately before `## Verdict`:

```markdown
## Closure Decision

Objective status: <achieved|not_achieved|not_applicable|indeterminate>
Objective evidence: <one line citing the slice closure-proof artifacts, or the exact not-applicable justification>

## Verdict

Verdict: <pass|needs_work|blocked|override> - next: <one move>
```

Exact shape, read by section-local, line-based rules with no fence parsing:
the report holds exactly one line starting with `## Closure Decision` and
exactly one starting with `## Verdict`, counted wherever they stand (fenced
or not), so an example never quotes either heading line
(`closure_section_duplicate`, `verdict_section_duplicate`); the closure
section is the two non-empty lines between the two headings, the status line
first and the evidence line immediately after; `Objective status:` and
`Objective evidence:` lines anywhere else are not authority and are not
counted; no objective line appears inside `## Verdict`; the verdict footer
is unchanged as the first non-empty line under `## Verdict`; no section
stands between the two. Values: `achieved` (cited closure evidence
establishes every applicable criterion), `not_achieved` (evidence
establishes at least one criterion was not met), `not_applicable` (no
applicable objective dimension, with an explicit reason), `indeterminate`
(relevant evidence is absent, incomplete, conflicting, or otherwise
insufficient to decide).

Rule: implementation `pass` and objective achievement are independent.
`pass` + `not_achieved` and `pass` + `indeterminate` are legal receipts that
never imply milestone completion; `pass` + `not_applicable` completes only
with an explicit compatible routing status from the operating tool; last-slice
position is never sufficient. This contract defines no route for any status:
routing is the operating tool's dimension. Full doctrine:
`05_governance/current/review_protocol.md` and
`docs/template_framework/closure_convergence.md`.

## 10. Validity Rules (reason codes)

Content codes (each has at least one fixture; the checker's `REASON_CODES`
tuple equals this list, proven by test):

`sidecar_not_mapping`, `version_missing`, `unknown_contract_version`,
`roadmap_missing`, `roadmap_link_unresolved`, `slices_missing`,
`slice_not_mapping`, `missing_field`, `invalid_type`, `duplicate_slice`,
`slice_id_format`, `slice_milestone_mismatch`, `authored_by_invalid`,
`status_invalid`, `dispatch_authority_missing`, `authority_path_invalid`,
`attempt_missing`, `attempt_format`, `strictness_invalid`,
`task_is_title_only`, `empty_list`, `read_first_path_invalid`,
`write_path_empty`, `write_path_directory`, `write_path_glob`,
`write_path_absolute`, `write_path_escape`, `write_path_not_file`,
`artifact_type_invalid`, `role_owner_invalid`, `retry_policy_invalid`,
`role_type_incompatible`, `reserved_artifact_mislabeled`, `self_report_count`,
`attempt_token_missing`, `attempt_token_unexpected`, `attempt_token_multiple`,
`write_read_conflict`, `sentinel_residue`, `gate_kind_invalid`,
`gate_reference_missing`, `gate_reference_invalid`, `gate_identity_missing`,
`external_input_invalid`, `candidate_identity_invalid`, `correction_missing`,
`correction_field_missing`, `correction_findings_missing`,
`correction_prior_evidence_invalid`, `correction_ruling_missing`,
`correction_closure_proof_missing`, `correction_list_invalid`,
`correction_unexpected`, `envelope_missing`, `envelope_unexpected`,
`envelope_field_missing`, `envelope_field_invalid`, `envelope_probe_invalid`,
`envelope_binding_value_present`, `envelope_binding_hash_format`,
`envelope_cleanup_invalid`, `envelope_handling_invalid`,
`local_output_root_outside_local_state`, `local_output_root_attempt_token`,
`objective_missing`, `projection_version_mismatch`,
`projection_counterpart_missing`, `projection_entry_mismatch`,
`attempt_mismatch`, `rendered_section_missing`, `rendered_section_duplicate`,
`rendered_section_unexpected`, `rendered_sentinel_residue`,
`rendered_section_residue`, `rendered_token_unresolved`,
`rendered_manifest_row_missing`, `rendered_self_report_path_missing`,
`rendered_attempt_path_reuse`, `typed_entry_missing`, `typed_entry_ambiguous`,
`typed_entry_unparseable`, `typed_entry_mismatch`, `typed_entry_status_line`,
`rendered_status_disagreement`, `rendered_manifest_row_undeclared`,
`rendered_self_report_path_undeclared`, `rendered_section_order`,
`closure_section_missing`, `closure_section_duplicate`,
`closure_after_verdict`, `closure_not_adjacent`, `closure_line_count`,
`objective_status_line_missing`, `objective_status_invalid`,
`objective_evidence_line_missing`, `verdict_section_missing`,
`verdict_section_duplicate`, `verdict_footer_invalid`,
`objective_status_in_verdict`.

Environment codes (I/O and usage; unit-tested, not fixture-driven; the
checker's `ENVIRONMENT_CODES`): `layout_unreadable`, `layout_contract_block_missing`,
`layout_contract_block_incomplete`, `sidecar_unreadable`,
`rendered_unreadable`, `review_report_unreadable`, `slice_not_found`, `usage`.

Sentinels (layout `sentinels`): `TBD`, `<value>`, `<path>`, `<one move>`; a
scalar that is only `...` counts as unresolved.

## 11. Reference Checker And Fixtures

`scripts/slice_contract_check.py` is the reference implementation: read-only,
exact-path driven, deterministic, network-free, stable reason codes in stable
order, `--json` output (`template.slice_contract_check.v1`). It is never
dispatch authority. Modes: validate one sidecar (including the roadmap link);
validate two and prove alignment; prove a rendered prompt against its entry
(`--slice`, optional `--attempt` confirming the entry's own attempt); check a
review report's closure record. It parses YAML and reads Markdown only by
line-start rules: it holds no Markdown grammar and no fence reader. It
needs the declared PyYAML dependency (`ENVIRONMENT.md`).

The fixture corpus `tests/fixtures/slice_contract/` is inventoried and
digest-pinned by `manifest.json` (every fixture carries its SHA-256; the
suite fails when bytes drift). Every content reason code has at least one
fixture expecting it; fixtures tagged `prose-not-authority` are positive
renderings whose prose disagrees with an exact typed entry and pin the
boundary of the contract. Downstream parsers are tested against these fixtures,
not against private reimplementations; the release receipt carries their
digests. Fixture corpora are exempt from the artifact-integrity preflight by
policy (they intentionally carry sentinels, fictional paths, and residue) and
are scanned by their own tests instead (`docs/template_framework/template_tests.md`).

## 12. Companion Rails

- Seat conduct: `CLAUDE.md` Autonomous-Loop Seat Posture (bounded probes; no
  recursive enumeration; no external snapshots; no secret values; the runner
  fence is the evidence) — rendered as the Seat Conduct section.
- Template-source purity and local-output topology: the layout's
  `template_owned_surfaces` and `local_state` blocks; the drive's JSON
  exclusion manifest at the layout's recommended path
  (`local_state.oracle_exclusion_manifest`) is the single machine-read
  exclusion source, and the template's pre-launch check reads it with the
  drive's own grammar — the declared reference is validated unmodified before
  any filesystem access, a declared-but-missing or linked file refuses, and
  only an omitted `--exclusions` flag means none declared. It applies the
  drive's published rules (bounded read of the limit plus one byte, strict
  JSON, canonical paths, governed surfaces) and the suite proves parity case
  by case against the drive's own loader when `FRUTLUPS_DRIVE_SRC` names a
  drive checkout; admission itself remains the drive's decision. The
  command is the layout's
  `local_state.prelaunch_size_check`
  (`docs/template_framework/security_and_local_state.md`):

  ```text
  python scripts/local_state_audit.py --limit-bytes 16777216 --exclusions 06_infra/oracle_exclusion_manifest.json
  python scripts/local_state_audit.py --limit-bytes 16777216   # no manifest declared
  ```

- Placeholders and dispatch: `docs/template_framework/prompt_style_guide.md`.

## 13. Migration And Release Identity

- Migration rule: absent sidecar = legacy. Opt in per section 1. A project
  refreshes the template-owned surfaces per
  `docs/template_framework/migration_and_adoption.md` and records the
  template pin in `PROJECT_STATE.md`.
- Release identity: contract v1 ships with a template release tag; the release
  receipt names the contract version, the tag, the full commit, the fixture
  manifest path and per-fixture digests, the legacy scaffold digest above, and
  this migration rule. Consumers declare compatibility against the tag,
  never against a branch. A later revision of the schema is contract version
  2 with its own fixtures; version 1 artifacts stay readable under version 1.
