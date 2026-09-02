# Template v3 Architecture Contract

Status: active design contract for the reusable OKF/profile framework shipped with
this template.

## System Purpose

Provide a reusable artifact-first project template with optional OKF
interoperability while remaining manually operable, offline, lightweight, and
independent of optional agent packages.

## Preserved Authorities

- Human-owner decisions and accepted reviews retain their existing authority.
- `CLAUDE.md` retains the source-of-truth hierarchy.
- `PROJECT_STATE.md` remains the single canonical live-state surface.
- Project-profile activation remains explicit and manual.
- OKF metadata or generated views never establish truth, approval, freshness,
  safety, or execution authority.

## Layer Boundary

1. Human-readable Markdown content.
2. OKF concept conformance under normative OKF rules.
3. The versioned framework producer/interoperability profile.
4. Package-native workflow, authority, schema, gate, and lifecycle semantics.
5. Optional generated or read-model views derived from canonical artifacts.

Each layer reports its own result. A lower-layer pass never implies a
higher-layer pass.

## Dependency Boundary

The baseline is Python 3.10+. The OKF/profile checker requires a single declared,
mature runtime dependency — **PyYAML** (`PyYAML>=6.0.3,<7`, pure-Python
`SafeLoader`) — as its YAML syntax engine. PyYAML is installed once and runs
locally and offline; other scripts remain standard-library only. The template must
not require Drift, llloom, frutlups, models, network access at runtime, services,
credentials, or cloud resources. Any further dependency requires a separate reviewed
decision.

## Compatibility Boundary

Legacy Markdown without frontmatter remains supported. Profile adoption is
additive and opt-in. Unknown OKF keys/types are tolerated at consumption
boundaries, while package-native execution remains strictly gated.

## Generation Boundary

Generated views are deterministic, reproducible, stale-detectable, disposable,
and clearly identify their canonical inputs and regeneration owner. They are
never canonical and never copy live state.

## Version Boundary

The pinned framework candidate is `0.1-rc.1`, defined canonically in
`docs/template_framework/okf_pkg/okf_profile_v0_1.md`. Stable `0.1` is deferred until template, pairwise,
and three-way hardening gates pass. Stable versions are not silently mutated; an
incompatible stable evolution requires a new major version and migration decision.
`okf_version` remains independent.

## Shipped Implementation Boundary

The shipped framework surface is the three prerequisite process safeguards
(stable-reference guidance, the deterministic artifact-integrity preflight, and
proportional fast-close), the framework-profile candidate contract and its
golden-fixture/manifest contract, the optional read-only PyYAML-backed OKF/profile
checker (`--profile`, via `scripts/okf_yaml_profile.py`, installed through the
editable project metadata), the deterministic disposable navigation read model
(`scripts/generate_okf_navigation.py` rendering `08_pkg/generated/okf_navigation.md`
from `08_pkg/okf_navigation_manifest.json`), the opt-in authoring/migration
documentation surface, and the compact architect operating card. The navigation
view is deterministic, disposable, standard-library only, never canonical, and does
not copy live state; it strictly rejects unsafe manifest text/identifiers/paths
before any write and translates output-filesystem failures into a concise exit 2
with no residue. No OKF frontmatter rollout, YAML writer, or migration logic is
implemented.

## Forbidden Couplings

- No generated authority competing with repository-native state.
- No mandatory dependency on another workhorse package (llloom, frutlups, Drift)
  or on a model, service, network, or credential. A single declared library
  dependency (PyYAML) for the YAML syntax engine is permitted.
- No whole-file synchronization from an external source repository into the
  reusable template.
- No profile validity used as a proxy for trust or execution eligibility.

## Deferred Areas

Profile fields are specified in the candidate contract
`docs/template_framework/okf_pkg/okf_profile_v0_1.md`; fixture vocabulary and outcomes are pinned by
`tests/fixtures/okf_profile/manifest.json`; the YAML syntax engine is PyYAML
(§6.6 of the profile). Drift evaluation and llloom/frutlups runtime integration are
decided only in their reviewed roadmap slices.
