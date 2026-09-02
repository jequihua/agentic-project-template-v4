# Template v3 Testing Strategy

Status: risk-based strategy for the shipped reusable OKF/profile framework.

## Test Layers

### Inherited Scaffold Regression

Run `python -m unittest discover -s tests` before and after every slice. Require
zero failures without deleting, skipping, or weakening inherited assertions.
Record counts only as dated observations.

### Safeguard Unit And Contract Tests

Focused positive, negative, determinism, non-mutation, portability, dependency, and
policy tests cover the three prerequisite safeguards — stable references, the
explicit-scope artifact-integrity preflight, and proportional fast-close — in
`tests/test_template_scaffold.py`.

### Profile Fixture Tests

The `tests/fixtures/okf_profile/manifest.json` corpus records separate OKF-concept,
framework-profile, and execution-eligibility expectations per parser. Focused
integrity tests cover malformed, valid-out-of-profile YAML, unknown keys/types,
unknown versions, legacy documents, inventory, and safety. The runtime checker is
PyYAML-backed and is driven against the manifest's `full_parser` oracle; the
`subset_parser` column remains durable cross-parser evidence and is never executed at
runtime. Checker tests additionally cover hostile YAML (malformed quotes/escapes,
colon-space, tabs, multiple documents, duplicate keys, YAML-1.1 scalar spellings,
floats/exponents, flow/tags/anchors/aliases/merge keys), resource-limit refusals and
alias cycles, CRLF/Unicode handling, deterministic v2 JSON, non-mutation, containment,
the pure-Python `SafeLoader` (no unsafe/C loader), package-metadata declaration of
PyYAML, and a clean no-fallback error when the dependency is absent.

### Dependency Bootstrap

The suite requires the declared PyYAML dependency for the profile-checker tests.
Install it (see `ENVIRONMENT.md`: `python -m pip install -e .` in `.venv`) before
`python -m unittest discover -s tests` is treated as a valid acceptance run.
Profile-checker tests skip when PyYAML is not importable; the default
(non-`--profile`) preflight and the rest of the suite remain standard-library only.

### Deterministic Regeneration Tests

Generated views must support delete/regenerate and check-only evidence with
byte-identical output for identical inputs, and inputs must remain unchanged. The
navigation view is covered by `tests/test_okf_navigation_view.py` (standard library
only): committed-view equals fresh render, two-run and delete/regenerate byte
identity, non-rewrite when current, `--check` current/stale/missing read-only exit
codes, manifest-order preservation, marker/authority-notice/source-path/command
presence, no copied source body or live state, safe failure on malformed JSON / wrong
schema / unknown keys / duplicate groups or sources / type errors / exceeded limits /
missing or non-regular sources / unsafe path forms / containment escapes /
output-as-input, temp-residue-free failure preserving existing bytes, source
non-mutation, and outside-CWD CLI targeting. Directory-at-output and mocked output
read/temp-create/temp-write/atomic-replace failures are translated to a concise exit 2
through the public `main()` boundary (preserving any prior output and leaving no temp
residue), and a manifest-value matrix (whitespace-only/padded, CR/LF/tab/NUL/
format-character, each forbidden Markdown delimiter, unsafe identifiers, injection
reproducers, and link-breaking source paths) proves rejection before any write with the
benign manifest and view still byte-identical. A real-file-handle wrapper proves zero
production `os.close` calls after ownership transfers (no double close), and
pre-transfer non-`OSError` failures propagate unchanged after the captured descriptor is
closed and the temp path removed, with no user-facing diagnostic. Symlink
source/output/parent-escape rejection is asserted where the platform permits symlink
creation, with a narrowly documented platform/privilege skip otherwise; a
`realpath`-mocked test covers the containment-escape branch portably.

### Mixed Legacy/Profile Authoring Tests

`tests/test_okf_authoring_migration.py` reuses the read-only `--profile` checker — it
adds no second parser. It **derives** the template-owned coverage set from the
`PROFILE_TYPE_REGISTRY` by subtracting one explicit set of downstream package-reserved
types (`source`, `claim`, `entity`, `page`, `milestone`, `slice`) — asserting each
excluded type is actually a registry member so a typo cannot invent a template-owned
type — and compares that derived set exactly with the `type` values parsed from the
guide's Artifact-Type Mapping table, so a later template-owned addition cannot silently
escape the guide/examples. It proves the shipped profiled artifacts (the authoring guide
and the architect operating card) profile-`pass` with checker exit 0 (not only the
per-layer record fields); that the minimum two-field block passes for every derived
template-owned type; that every copy-ready guide example is conformant; that the enriched
`accepted_full.md` shape (with justified optional fields) still passes; that bare
`0.1-rc.1` resolves to `str` under the declared engine and profile-passes; that a
temporary mixed set of a plain legacy Markdown file, a profiled prompt, and a profiled
self-report yields the separate legacy (`not_evaluated`/`not_applicable`) and profile
(`pass`) outcomes with every input byte unchanged and execution eligibility always
`not_evaluated`; that the legacy prompt/self-report templates carry no default
frontmatter while the coding, review, and self-report routing policies are each asserted
structurally; that the workflow-metadata warning is present on both prompt templates;
that the canonical self-report headings and the onboarding-copy invariant are intact; and
that the migration entry point and root README link to the one guide rather than
duplicating it.

### Architect Operating-Card Tests

The shipped `test_architect_operating_card.py` suite protects the operator surface
independently: the card is a profiled `framework_doc`; it stays within its line/word
budget; it contains the normal loop, four OKF rules, decision tree, authority warning,
and escalation triggers; it carries no volatile route values, reason-code tables, or
schema identifiers; and its type-selection aid equals the registry-derived
template-owned partition exactly and lists each type **exactly once** — the aid is parsed
into an ordered list and asserted to have no duplicate entries and a cardinality equal to
the derived partition, so both a removal and a duplicate fail — while naming the
downstream-reserved types as package-owned. It also asserts the architect routine read
list is four artifacts or fewer and the coder list five or fewer and task-local, and that
the entry points link the card without copying its body.

### Standalone Checkout Contract

The template's own `.gitattributes` enforces a binary-safe blanket LF rule
(`* text=auto eol=lf`, plus the explicit generated-navigation and OKF-profile boundary
rules) so that when this template becomes the root of its own Git repository the complete
tree checks out LF on every platform, regardless of the checkout machine's `core.autocrlf`.
`text=auto` (not an unconditional `text`) keeps a future binary asset from being corrupted.
`tests/test_template_scaffold.py` asserts this blanket rule is present, is binary-safe, and
that no shipped distributable text file currently carries CRLF, so the release bytes stay
deterministic.

### Compatibility Gates

Before stable `0.1`, run template-only, template-to-llloom, template-to-frutlups,
llloom-to-frutlups, cross-parser, and three-way scenarios, including degraded,
migration, rollback, failure, dirty-worktree, and performance cases.

## Result Discipline

Negative tests are required. Stable reason-code families and result layers stay
separate; a format/profile result cannot substitute for package execution
validation. Do not invent test function names before code exists—roadmaps use
scenario identifiers until implementation names are reviewed.

## Baseline Evidence

Capture target-specific command, repository identity, date, and result before
each migration stage. Source-repository results are comparison evidence, not
target acceptance evidence.

## Known Gaps

The PyYAML-backed OKF/profile checker (`--profile`), the deterministic navigation-view
generator, and the opt-in authoring surface are shipped for candidate profile
`0.1-rc.1`. No pairwise or three-way compatibility harness exists yet; that remaining
gap is intentional roadmap work, not implemented behavior.
