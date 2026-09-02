# Framework Profile Candidate — `framework_profile: "0.1-rc.1"`

Status: candidate contract. This document is the single canonical definition of
the framework producer/interoperability profile layered on OKF. It pins the first
candidate identifier `framework_profile: "0.1-rc.1"`. It is **not** stable `0.1`,
and it is not silently mutable (see Lifecycle below). Live routing remains in
`PROJECT_STATE.md`; this file is a durable contract, not a state surface.

This is a specification only. It defines no parser, checker, writer, fixture set,
or metadata rollout; those belong to later reviewed slices.

Normative OKF claims cite the external normative OKF `SPEC.md` (version `0.1-draft`)
by section; that specification is an external source referenced by the pinned record
in the Sources section below and is not redistributed here. "OKF" below means OKF v0.1
as specified there. The keywords MUST, SHOULD, MAY, MUST NOT, and SHOULD NOT are used
in their normative sense.

## 1. Purpose And Non-Authority

The framework profile is an **additive producer envelope** on top of OKF. It
constrains how *this template stack* produces and cross-reads frontmatter so that
the template, and later llloom and frutlups, emit and read the same documents
predictably. It adds interoperability guarantees; it removes none of OKF's
permissive consumption model (SPEC §9).

The profile has no workflow, trust, or execution authority:

- `PROJECT_STATE.md` remains the sole canonical live-state authority. Profile
  frontmatter MUST NOT restate volatile live state (active prompt/review numbers,
  next action, workspace lists, worktree contents); durable documents link to
  `PROJECT_STATE.md` or an index instead.
- Profile conformance MUST NOT be read as truth, approval, freshness, safety, or
  execution eligibility. "Profile-valid" is not "trusted", "current", or
  "executable".
- Baseline template operation stays manually readable and offline. The OKF/profile
  checker requires the declared PyYAML dependency (§6.6); it is installed once and
  runs locally and offline, with no service, model, credential, or network use.
  Manual Markdown authoring needs no dependency, and other scripts remain
  standard-library only.

## 2. Layer Model And Separated Results

A document is evaluated at independent layers; a lower-layer pass never implies a
higher-layer pass. This mirrors `docs/template_framework/okf_pkg/architecture_contract.md` (Layer
Boundary).

| Layer | Scope | Owner |
| --- | --- | --- |
| L1 OKF concept | Parseable YAML frontmatter + non-empty `type` (SPEC §4.1, §9); markdown body; links; reserved `index.md`/`log.md` | OKF |
| L2 Framework profile | This document: producer YAML envelope, `framework_profile` version, `framework_*` fields, shared `type` registry, namespaces, identity/authority rules | template |
| L3 Template semantics | Project structure, `PROJECT_STATE.md` authority, workspaces, prompts | template |
| L4 llloom semantics | Sources/hashes, claims, verification, lifecycle | llloom |
| L5 frutlups semantics | Milestone/slice discovery, schemas, verdicts, gates | frutlups |

This profile defines only L1↔L2 producer/consumer behavior. It records three
**independent validation results** — never conflate them, and never infer a later
one from an earlier one:

1. **OKF concept conformance** — real YAML parsing plus OKF rules (SPEC §9).
   Result: `pass` / `fail` / `unverified`. The template runtime parses YAML with a
   mandatory PyYAML `SafeLoader` adapter (see §6.6), so it can conclusively
   distinguish invalid YAML from valid-but-out-of-profile YAML; valid YAML outside
   the producer subset is OKF-evaluated from the parsed concept and is **not**
   invalid OKF (OKF itself uses flow sequences such as `tags: [sales, orders]`,
   SPEC §4.1 and Appendix A). Reason-code family: `OKF_FRONTMATTER_MISSING`,
   `OKF_TYPE_MISSING`, `OKF_YAML_INVALID` (a conclusive YAML syntax, multi-document,
   or duplicate-key failure), and `OKF_PARSE_LIMIT_EXCEEDED` (a bounded resource
   refusal — `unverified`, not invalid). `OKF_YAML_UNSUPPORTED` is **retained only
   to explain the historical house-subset `subset_parser` oracle data**; the PyYAML
   runtime does not emit it.
2. **Framework-profile conformance** — this document's envelope, version, types,
   namespaces, and identity rules. Result: `pass` / `fail` / `not_applicable`. A
   valid YAML flow collection MAY be OKF-`pass` yet profile-`fail`. Reason-code
   family: `PROFILE_YAML_OUT_OF_SUBSET`, `PROFILE_VERSION_UNSUPPORTED`,
   `PROFILE_TYPE_UNSUPPORTED`.
3. **Tool-execution eligibility** — package-native schema/authority/gate/lifecycle
   checks, decided by L4/L5 packages and **never** inferred from L1/L2. Reason-code
   family: `EXECUTION_*`.

Reason-code ownership and completeness:

- The `PROFILE_*` codes above are the **canonical framework-profile reason codes**
  defined by this contract. This candidate defines exactly these three; the family
  is extensible only through change control (§8).
- The `OKF_*` codes name the **OKF-concept reason family**; a checker MAY add
  members as OKF-layer diagnostics without a profile change.
- `EXECUTION_*` is a **downstream-owned family** (L4/L5). This contract does not
  enumerate or own its members.

Consumers MUST ignore unknown reason codes rather than reject them. This list is
not claimed to be exhaustive of every diagnostic a checker may emit; it fixes only
the profile-layer codes needed to classify the cases in §10.

## 3. `okf_version` Versus `framework_profile`

These two version identifiers are **independent** and MUST NOT be conflated
(decision X-G1 in the accepted cross-stack integration plan, §A.2; adopted here as
a candidate default):

- `okf_version` identifies the OKF **spec** revision. Per SPEC §11 it MAY appear
  **only** in a bundle-root `index.md` frontmatter block. It is not a per-concept
  field and is out of scope for concept documents.
- `framework_profile` identifies this **L2 profile** revision and is declared
  per concept (see §4). Its pinned candidate value is the string `0.1-rc.1`.

A breaking OKF spec change and a breaking profile change are versioned
separately. A breaking profile change is a new profile **major** (for example
`1.0`), never `0.2` (§8).

## 4. Frontmatter Fields

A framework-profile concept is an OKF concept document (SPEC §4) whose frontmatter
additionally satisfies this section. Fields fall into required, derived,
recommended, and optional classes.

### 4.1 Required

- `type` — inherited OKF requirement (SPEC §4.1 "Required", §9 item 2): a short,
  non-empty string. For profile conformance it MUST be a value in the shared
  registry (§5) or an entry added through change control; otherwise the profile
  result is `fail` (`PROFILE_TYPE_UNSUPPORTED`) while the OKF result is unaffected.
- `framework_profile` — the pinned profile version string. For this candidate its
  value MUST be `0.1-rc.1`. An unrecognized value yields profile
  `PROFILE_VERSION_UNSUPPORTED` (§8), not an OKF failure.

### 4.2 Derived (never authored as live state)

- **Concept ID** — the concept's path within the bundle with the `.md` suffix
  removed (SPEC §2). It is the portable *address*, not a durable identity, and
  MUST NOT be hand-copied into frontmatter as a stored field; it is computed from
  the path.

### 4.3 Recommended

- `framework_id` — a durable, path-independent identifier (SHOULD be present for
  any concept that is cross-referenced or may move). Moving a file changes its
  concept ID but MUST NOT change its `framework_id`. Cross-references that must
  survive moves SHOULD use `framework_id`; ordinary navigation uses links.
- `title`, `description` — OKF recommended fields (SPEC §4.1 "Recommended"),
  reused unchanged.

### 4.4 Optional and extensions

- `resource`, `tags`, `timestamp` — these appear in the SPEC §4.1 **Recommended**
  list (in priority order: `title`, `description`, `resource`, `tags`,
  `timestamp`), not the required set; OKF requires none of them. **As an L2 profile
  decision**, this profile also does not require them (MAY): a document is
  profile-conformant without them. This optional posture is a profile choice
  consistent with OKF, not an OKF downgrade. When present, they are reused
  unchanged, subject to the producer envelope in §6 (for example `tags` is emitted
  as a block sequence of scalars, not flow style; a `timestamp` is a double-quoted
  ISO 8601 string per §6.3).
- Producer extensions — any additional key is permitted (SPEC §4.1 "Extensions").
  Every consumer MUST tolerate unknown keys and namespaces on read and MUST NOT
  reject a document for unrecognized fields (SPEC §4.1, §9). Unknown-field
  **preservation** across a rewrite is an obligation only of a named
  read-then-rewrite path; read-only and new-document paths make no round-trip
  claim (integration plan §B.0). No path in this candidate rewrites existing
  frontmatter.

## 5. Namespaces And Artifact-Type Vocabulary

### 5.1 Namespaces

- `framework_*` — flat, scalar-valued keys in the template-owned L2 namespace
  (for example `framework_profile`, `framework_id`).
- `<tool>:` mappings — single-level mappings reserved to a package: `llloom:` is
  llloom-owned, `frutlups:` is frutlups-owned. The `<tool>:` mapping convention is
  collision-resistant and keeps package-specific meaning inside the package's own
  namespace.
- A consumer MUST tolerate unknown namespaces on read. A package MUST NOT redefine
  another package's namespace.

### 5.2 Shared `type` registry

The shared artifact-type registry is template-owned. For this candidate the
recognized profile types are:

`brief`, `constraint`, `decision`, `analysis`, `coding_prompt`, `review_prompt`,
`self_report`, `review_report`, `verdict_record`, `delivery_plan`,
`framework_doc`.

The following types are reserved to their owning packages and recognized as valid
registry members when produced by those packages: `source`, `claim`, `entity`,
`page` (llloom); `milestone`, `slice` (frutlups).

A `type` outside this registry is OKF-valid (SPEC §4.1 tolerates unknown types)
but profile-`fail` with `PROFILE_TYPE_UNSUPPORTED`. New shared types or
`framework_*` keys are added only through the change-control process (§8;
integration plan §B.3), never by opportunistic local invention.

## 6. House YAML Producer Envelope

The profile constrains the YAML that *producers* emit and that a house-subset
*consumer* is required to interpret. It is a producer profile; it does **not**
redefine YAML and does **not** narrow OKF's own permissive consumption model.

### 6.1 Allowed constructs (the producer subset)

A profile-conformant frontmatter block MUST use only:

- the `---`-delimited block at the top of the file (SPEC §4.1);
- **mapping keys that are YAML string scalars.** A key whose resolved YAML tag is
  not the string tag (for example a bare integer, boolean, or null key) is outside
  the producer subset even when unique; a non-scalar/complex key is likewise
  outside it. (This records the existing rule; it adds no name allowlist — key
  *names* remain unconstrained as long as they resolve as strings.)
- scalar values (strings, integers, booleans `true`/`false`, `null`);
- double-quoted strings where quoting is needed;
- single-level block mappings for a `<tool>:` namespace;
- block sequences of scalars (for example `tags`);
- `#` comments (full-line or trailing).

### 6.2 Forbidden in the producer subset

A profile-conformant frontmatter block MUST NOT rely on: flow collections
(`{a: 1}`, `[1, 2]`), anchors/aliases, merge keys (`<<`), tags (`!!...`),
multi-document streams (`---` separators mid-file), or newline-significant
literal/folded block scalars (`|`, `>`).

A frontmatter block MUST NOT contain **duplicate mapping keys** at the same level.
A duplicate key is out of subset for every parser (see §6.5).

### 6.3 Scalar lexical and quoting rules

To guarantee that the house-subset parser and a full-YAML parser resolve the same
**semantic scalar type**, producers MUST follow these rules; a checker evaluates
profile conformance against them:

- **Booleans** MUST be written as the bare lowercase tokens `true` or `false`
  only. The YAML 1.1 spellings `yes`/`no`/`on`/`off` (and capitalized `True`/
  `False`) MUST NOT be used to mean a boolean; if such a word is intended as text
  it MUST be double-quoted (this avoids the "Norway problem", where a full parser
  reads `no` as boolean while a subset parser reads it as a string).
- **Null** MUST be written as the bare token `null` (an empty value and `~` also
  denote null but SHOULD NOT be used; producers SHOULD prefer `null`).
- **Integers** MUST be written in canonical decimal form: the bare token `0`, or
  an optionally signed nonzero decimal with no leading zero — matching
  `0|-?[1-9][0-9]*`. Bare leading-zero forms (`007`, `010`, `-010`), `00`, and `-0`
  are **not** canonical integers (canonical zero is the single token `0`); each is
  out of subset (§6.5). A numeric-looking value intended as text — including any
  leading-zero form — MUST be double-quoted (for example `"007"`), which makes it a
  string scalar and profile-conformant.
- **Strings that resemble another scalar type** — a bare value that would parse as
  a boolean, null, integer, float, date, or timestamp but is intended as text —
  MUST be double-quoted (for example a version value is written `"0.1-rc.1"`).
- **Timestamps** MUST be double-quoted ISO 8601 strings (for example
  `"2026-05-28T14:30:00Z"`), so both parsers yield an identical string scalar
  rather than one parser producing a native date/datetime.
- **Unsupported scalar classes** — block scalars (`|`, `>`), tagged scalars
  (`!!str`, etc.), and flow scalars — are out of subset (§6.2, §6.5).

Under these rules, producer-subset input yields the same semantic scalar type in
the house-subset parser and in a full-YAML parser.

### 6.4 Ordering and comparison semantics

- **Sequence order is significant** and MUST be preserved by any producer,
  consumer, or serializer.
- **Mapping-key order is not semantic**: two mappings with the same keys and values
  in a different key order are **semantically equal**.
- **Cross-parser agreement is semantic-mapping equality** — equal keys, equal
  values, equal scalar types, and equal sequence order — **not** byte-identical
  parses. Different YAML implementations MAY tokenize identical input differently.
- **Byte identity** applies only to **deterministic serialization/regeneration**
  (a writer or a generated view emitting a document), never to a parse.
- A **read-only** check (preflight or profile checker) proves **input
  non-mutation** (input bytes unchanged); it makes no round-trip or byte-emission
  claim.

### 6.5 Classifying constructs outside the subset

A construct that is valid YAML but outside §6.1 (including flow collections,
anchors/aliases, merge keys, tags, block scalars, **duplicate keys**, and a scalar
that violates the canonical scalar rules in §6.3 — such as a bare leading-zero
numeric) is **out of subset**, not automatically invalid:

- The framework-profile result is `fail` with `PROFILE_YAML_OUT_OF_SUBSET`, on
  **every** parser (house-subset or full).
- The OKF-concept result is determined by conclusive parseability:
  - a full-YAML parser reports OKF `pass` if the block parses and `type` is
    present; for a **duplicate key** (which YAML forbids) a conclusive parser
    reports OKF `fail`;
  - a house-subset parser that cannot conclusively interpret the construct reports
    OKF `unverified` with `OKF_YAML_UNSUPPORTED` — it MUST NOT report OKF `fail`
    for a construct whose validity it cannot determine.

"Fail loud" for an out-of-subset construct therefore means a `PROFILE_*`
diagnostic, and an OKF result named per the parser used — not a blanket OKF
failure. This keeps the producer subset strict while leaving generic OKF
consumption tolerant.

### 6.6 YAML syntax engine (PyYAML)

The template runtime uses a mandatory, declared PyYAML dependency
(`PyYAML>=6.0.3,<7`) through a single bounded adapter
(`scripts/okf_yaml_profile.py`) as the YAML **syntax and representation** engine.
Ownership is divided:

- PyYAML (pure-Python `yaml.SafeLoader` only) owns YAML tokenizing, quoting,
  escaping, scalar resolution, indentation, and collection parsing.
- Project code owns the exact Markdown `---` framing (outside YAML), finite
  resource limits, duplicate-key rejection, canonical scalar/style policy from
  token/node evidence, and the OKF/profile results.

PyYAML resolves *what YAML means*; the profile decides *what producers may write*.
A valid YAML 1.1 scalar (for example `no`, `1e3`, `1_000`) may be OKF-parseable and
still fail the producer profile unless written in the canonical form of §6.3. The
adapter never uses an unsafe loader, never constructs arbitrary Python objects,
never decides execution eligibility, and never mutates its input. There is no
custom-parser fallback: if the dependency is absent, the checker fails clearly
rather than switching semantics.

## 7. Document Identity, Authority, And Precedence

- **Live-state authority.** `PROJECT_STATE.md` is the only canonical live-state
  surface. No profile field, generated view, or index is a competing live-state
  authority.
- **Source-of-truth order.** Governance precedence follows `CLAUDE.md` (latest
  human instruction, then `PROJECT_STATE.md`, then accepted reviews, and so on).
  The profile does not alter it.
- **Addressing versus identity.** Concept ID (SPEC §2) addresses a concept by
  path; `framework_id` (§4.3) is its durable identity across moves.
- **Generated views.** Any generated `index.md`/`log.md` or derived view MUST
  disclose its canonical source, remain reproducible and disposable, and MUST NOT
  copy live state or claim authority (architecture_contract Generation Boundary;
  SPEC §6, §7).
- **Links.** Cross-links are ordinary markdown links, untyped for generic
  consumers; absolute bundle-relative links (leading `/`) are recommended (SPEC
  §5.1, §5.3). Consumers MUST tolerate broken links (SPEC §5.3).

## 8. Candidate Lifecycle, Compatibility, And Promotion Gates

- **Candidate identity.** The pinned value is `0.1-rc.1`. It is a candidate, not
  stable `0.1`, and MUST NOT be presented as stable.
- **Compatible clarification.** A backward-compatible change (a new optional
  field, a new registry `type`, a new reason code) increments the rc revision
  (`0.1-rc.2`, …) with accompanying fixture and consumer evidence. Consumers on an
  earlier compatible rc adopt at leisure.
- **Incompatible change.** A change to required fields, the YAML subset, or
  existing semantics requires a new candidate line plus a recorded migration
  decision, explicit human approval, and a hardening slice; downstream pins the
  prior profile until it migrates.
- **Minor versus major.** After stabilization, an additive change is a profile
  **minor**; a breaking change is a profile **major** (for example `1.0`). `0.2`
  would be a *minor*, not a breaking release.
- **Promotion gate.** Stable `framework_profile: "0.1"` is promoted **only** after
  the template, pairwise, and three-way hardening gates pass (integration plan
  §C.1, §H). Stable releases are not retroactively mutated.
- **Unknown declared version.** A consumer that reads an unknown `framework_profile`
  value MUST record a framework-profile result of `fail` with
  `PROFILE_VERSION_UNSUPPORTED` and disable profile behavior, while still
  attempting generic OKF best-effort consumption (SPEC §11 SHOULD) — so the
  OKF-concept result is evaluated independently. Profile-derived classification and
  execution eligibility are then unavailable. An unknown version MUST NOT be
  reclassified as legacy no-frontmatter input, and MUST NOT trigger filename
  inference.

## 9. Legacy No-Frontmatter Behavior

A Markdown document with **no opening `---` frontmatter delimiter** on its first
line is classified, **before the L1 OKF-concept evaluation**, as **legacy non-OKF
input with a supported fallback** (governing scenario PW-YAML-02d), regardless of
whether it has a body. It is not routed through OKF conformance and is not asserted
as an OKF `fail`; it is simply not an OKF concept because it carries no frontmatter
(SPEC §9 items 1–2 describe what conformance *would* require). This is distinct
from a **malformed** document that *opens* a frontmatter block but never closes it,
which is a conclusive OKF `fail` `OKF_FRONTMATTER_MISSING` (§10), not a legacy
document. Such a legacy document:

- remains valid, first-class template content (baseline manual/offline operation
  is unaffected);
- has **no OKF-concept result and no profile `fail` asserted** — the OKF-concept
  layer is *not evaluated* and the framework-profile layer is `not_applicable`;
- MAY be handled by a package's own filename/heading inference fallback, which is
  distinct from the unknown-declared-version path in §8 (an unknown version is a
  profile `fail`, not a legacy document).

Profile adoption is additive and opt-in. A repository MAY mix legacy and
profiled documents; consumers read both under OKF's permissive model (SPEC §9).

## 10. Conformance Summary (decision table)

Execution eligibility is always a separate L4/L5 determination; this contract does
**not** evaluate it, so its column reads "not evaluated (L4/L5)" in every row. Each
OKF-concept and framework-profile cell gives one exact result (with reason code
where applicable) or states that the layer is not evaluated.

These are the **authoritative PyYAML-runtime (`full_parser`) outcomes** (§6.6).
The retired house-subset `subset_parser` column in the fixture manifest is durable
historical/cross-parser evidence only. The runtime applies this explicit
precedence (not row order): (1) framing/UTF-8; (2) resource refusal; (3) YAML
syntax, document-count, and duplicate-key failures; (4) missing/empty `type`;
(5) producer-subset, registry, and version evaluation. A conclusive OKF failure
therefore outranks an out-of-profile result at L1, while L2 is evaluated
independently.

| Input | OKF-concept result | Framework-profile result | Execution eligibility |
| --- | --- | --- | --- |
| Fully subset-conformant concept: registry `type`, `framework_profile: "0.1-rc.1"`, only §6-canonical constructs and scalars (a double-quoted numeric-looking string such as `"007"` is a canonical string), and any number of tolerated unknown extension keys/namespaces | `pass` | `pass` | not evaluated (L4/L5) |
| Valid YAML outside the producer subset: flow collection (`tags: [a, b]`), anchor/alias, merge key, explicit tag, block scalar, single-quoted string, or a non-canonical scalar spelling (`no`, `1e3`, `1_000`, `1:20`, native timestamp, leading-zero numeric) | `pass` | `fail` `PROFILE_YAML_OUT_OF_SUBSET` | not evaluated (L4/L5) |
| Malformed YAML, invalid tabs/quoting, multiple documents, or a duplicate mapping key (at any inspected level) | `fail` `OKF_YAML_INVALID` | `fail` `PROFILE_YAML_OUT_OF_SUBSET` | not evaluated (L4/L5) |
| A finite parse/resource limit is exceeded (bytes, lines, tokens, nodes, depth, scalar/collection size, aliases, or an alias cycle) | `unverified` `OKF_PARSE_LIMIT_EXCEEDED` | `fail` `PROFILE_YAML_OUT_OF_SUBSET` | not evaluated (L4/L5) |
| Well-formed frontmatter, `type` missing or empty | `fail` `OKF_TYPE_MISSING` | `not_applicable` (no valid `type` to profile) | not evaluated (L4/L5) |
| Opening `---` line but no closing `---` (unterminated frontmatter) | `fail` `OKF_FRONTMATTER_MISSING` | `not_applicable` | not evaluated (L4/L5) |
| Subset-conformant frontmatter, `type` outside the registry | `pass` (unknown types tolerated, SPEC §4.1) | `fail` `PROFILE_TYPE_UNSUPPORTED` | not evaluated (L4/L5) |
| Subset-conformant frontmatter, registry `type`, **no `framework_profile` field** (not opted into the profile) | `pass` | `not_applicable` | not evaluated (L4/L5) |
| Otherwise OKF-valid, `framework_profile` value other than `0.1-rc.1` | `pass` (evaluated independently, best-effort SPEC §11) | `fail` `PROFILE_VERSION_UNSUPPORTED`, behavior disabled | not evaluated (L4/L5) |
| No opening `---` delimiter on the first line (plain Markdown, with or without a body) | not evaluated — legacy non-OKF fallback before L1; no `fail` asserted (§9, PW-YAML-02d) | `not_applicable` | not evaluated (L4/L5) |

A checker MUST name the layer and result for each finding and MUST NOT collapse
these columns into a single verdict. The first-line delimiter and the presence of a
closing delimiter discriminate the legacy (no opening `---`), unterminated (opening
`---`, no closing `---`), and framed (opening and closing `---`) cases. When a
framed document exhibits more than one condition, the precedence above selects the
OKF-concept result and the framework profile is `fail` for any producer-subset
violation.

## 11. Out Of Scope For This Contract

This contract does not define a YAML serializer, writer, or comment-preserving
editor; generated indexes or navigation views; frontmatter rollout, legacy
conversion, or migration tooling; any stable `0.1` declaration; or any
llloom, frutlups, Drift, model, service, network, credential, or live-cost
integration. The read-only OKF/profile checker and its PyYAML adapter are shipped
separately; they never write, migrate, or decide execution eligibility.

## 12. Deferred And Adopted Decisions

- X-G1 (`okf_version` vs `framework_profile`): **adopted default — independent**
  (§3), consistent with the accepted integration plan; revisable only through
  change control.
- X-G2 (shared YAML frontmatter subset): **pinned here** as §6, to be stabilized
  at cross-stack hardening.
- **Unprofiled OKF concept:** a well-formed, subset-readable OKF concept that
  carries a registry `type` but **no `framework_profile` field** is OKF-concept
  `pass`, framework-profile `not_applicable`, and execution `not_evaluated` (§10).
  This is a compatible clarification for a document outside profile opt-in: it
  changes no declared `0.1-rc.1` document, adds no reason code, and therefore does
  **not** change the candidate identifier `0.1-rc.1`.
- **PyYAML syntax engine + diagnostic vocabulary:** the template runtime
  standardizes YAML syntax on a mandatory PyYAML `SafeLoader` adapter (§6.6) and the
  runtime oracle is the manifest's `full_parser` expectation. Two OKF diagnostics are
  part of the extensible OKF reason family (§2): `OKF_YAML_INVALID` (conclusive
  syntax/multi-document/duplicate-key failure) and `OKF_PARSE_LIMIT_EXCEEDED` (a
  bounded resource refusal, `unverified`). Per §2 the OKF reason family is
  checker-extensible, and the producer subset (§6), registry, version policy,
  three-layer separation, and existing accepted outcomes are unchanged; this
  therefore does **not** change the candidate identifier `0.1-rc.1`.
- Any future conflict between an accepted planning decision and this contract MUST
  be recorded under change control rather than resolved silently in this file.

## Sources

### Normative source (external pinned record)

The normative OKF specification is an external source; it is **not** vendored into
this template, and no upstream specification bytes or license file are redistributed
here. The exact cited bytes are pinned so a consumer holding only this template can
independently retrieve and authenticate them:

- Source identifier: `OKF`
- Version: `0.1-draft`
- Upstream specification path: okf/SPEC.md
- Immutable locator: <https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/ee67a5ca27044ebe7c38385f5b6cffc2305a9c1a/okf/SPEC.md>
- Upstream revision: `ee67a5ca27044ebe7c38385f5b6cffc2305a9c1a`
- Raw-byte SHA-256: `b9655e607346dbbdc6de21190e9a953313eda6a7eba68d4d272a65975940ad6e`

The immutable locator is a revision-pinned public HTTPS URL that resolves to the exact
raw specification bytes whose SHA-256 is recorded above; the inline section citations
(§2, §3.1, §4.1, §5.1, §5.3, §6, §7, §9, §11) refer to that specification, read
read-only. The digest authenticates those external bytes only; it confers no profile,
execution, approval, or freshness authority. This template performs no network access;
a consumer verifies the cited bytes against this pinned record.

### Framework decisions

The layer/version boundaries in `docs/template_framework/okf_pkg/architecture_contract.md` and the shipped
governance records under `05_governance/`. Planning notes explain the framework layer
but do not redefine OKF.
