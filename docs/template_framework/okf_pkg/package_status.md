# Package Status

Status: ships a reusable OKF/profile framework for candidate profile `0.1-rc.1`.
Current project routing lives only in `PROJECT_STATE.md`; this file describes
shipped framework capabilities, not project routing or a next action.

Shipped capabilities:

- the inherited artifact-first scaffold behavior;
- the three prerequisite process safeguards — stable-reference guidance across the
  canonical contracts and default prompt/report surfaces, the read-only
  artifact-integrity preflight `scripts/artifact_integrity_preflight.py` (its
  default checks are standard-library only), and proportional append-only Level 1
  fast-close — covered by focused scaffold tests;
- the canonical framework-profile candidate contract at
  `docs/template_framework/okf_pkg/okf_profile_v0_1.md` (`framework_profile: "0.1-rc.1"`);
- the manifest-driven golden-fixture corpus under `tests/fixtures/okf_profile/`,
  with separate per-parser and per-layer outcomes and deterministic integrity
  tests;
- an optional `--profile` mode of `scripts/artifact_integrity_preflight.py`,
  backed by the mandatory pure-Python PyYAML `SafeLoader` adapter
  `scripts/okf_yaml_profile.py`; it follows the manifest `full_parser` oracle,
  emits schema `template.okf_profile_check.v2`, reads each artifact once under a
  bounded total-input snapshot, rejects semantic duplicate keys, and separates the
  `okf_concept`, `framework_profile`, and `execution_eligibility` results. It is
  installed via the editable project metadata (`pip install -e .`), which declares
  PyYAML. There is no custom-parser fallback;
- a deterministic, disposable OKF-backbone navigation read model —
  `scripts/generate_okf_navigation.py` (standard library only) rendering
  `08_pkg/generated/okf_navigation.md` from `08_pkg/okf_navigation_manifest.json`,
  with a `--check` staleness mode. It is byte-reproducible, path-contained,
  non-authoritative, never copies live state, and is disposable (deleting it loses
  no canonical information). It strictly rejects unsafe manifest text, identifiers,
  and source paths before any write, and translates output-filesystem failures into
  a concise exit 2 with no residue;
- an opt-in OKF authoring and migration documentation surface — the canonical guide
  `docs/template_framework/okf_authoring_and_migration.md` (a profiled
  `framework_doc`) plus concise routing in the `coding_prompt`, `review_prompt`, and
  `self_report` templates, with mixed legacy/profile compatibility tests
  (`tests/test_okf_authoring_migration.py`). Opt-in is per exact new artifact path
  with the two-field minimum block; legacy no-frontmatter remains the default. It
  adds no YAML writer, converter, inventory CLI, or dependency;
- the compact, registry-validated architect operating card
  (`docs/template_framework/architect_operating_card.md`) and its reusable
  operating-card/entry-point tests.

The profile is a pinned candidate (`0.1-rc.1`), not stable `0.1`. PyYAML is the
sole declared runtime dependency and is used only by the `--profile` checker; all
other scripts remain standard-library only. No OKF frontmatter rollout, YAML
writer, converter, bulk migration, or repository-inventory CLI is implemented.
Stable `0.1` is promoted only after the template-only, pairwise, and three-way
compatibility gates pass.
