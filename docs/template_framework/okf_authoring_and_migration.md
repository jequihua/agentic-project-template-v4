---
type: framework_doc
framework_profile: "0.1-rc.1"
---

# OKF Authoring And Migration

The single practical guide for applying the accepted framework profile
(`docs/template_framework/okf_pkg/okf_profile_v0_1.md`, pinned candidate `framework_profile: "0.1-rc.1"`) to
new artifacts and for adopting it gradually in a mixed repository. This guide does not
restate the profile's full field, YAML, namespace, or reason-code specification — it
tells you the minimum to author correctly and how to adopt or roll back safely.

Validate any opted-in artifact read-only with:

```text
python scripts/artifact_integrity_preflight.py --profile <path> [<path> ...]
```

## Opt-In Rules

- **Legacy is the default.** Markdown without frontmatter remains valid and is the
  default for every artifact unless an active coding prompt, or a human-approved
  adoption decision, opts in an exact **new artifact path**.
- **Opt-in is per artifact.** It is never a repository-wide mode and is never inferred
  from a directory, a neighbouring file, an active tool, or an installed dependency.
- **Minimum block.** The only required fields are `type` and the pinned
  `framework_profile: "0.1-rc.1"`. `framework_id`, `title`, `description`, `tags`,
  timestamps, tool namespaces, and every other field are never made mandatory here.
- **`framework_id` is recommended, not required** — add it only for a concept that is
  cross-referenced or may move (profile §4.3); ordinary navigation uses links.
- **Placement.** The block starts on the very first line, is delimited by `---`, and
  precedes the Markdown title. It follows the producer envelope (profile §6). A fenced
  YAML example later in a document is body content, not frontmatter.
- **No authority.** Profile validity conveys no truth, approval, freshness, safety,
  current-state, or execution authority. `PROJECT_STATE.md` remains the only live-state
  source; a checker `pass` never grants execution eligibility.
- **Read-only checking.** The profile check reads and never rewrites. This slice adds
  no read-then-rewrite path, so no unknown-field preservation is claimed.

## The Minimum Block

Every profiled artifact uses the same two-field block; only the `type` value changes:

```yaml
---
type: <registry-type>
framework_profile: "0.1-rc.1"
---
```

Substitution rule: replace `<registry-type>` with the artifact's type from the table
below. The rest of the block is identical for every type. Write the version
double-quoted, `"0.1-rc.1"` — that is the profile's published, copy-ready spelling and
it keeps the pinned value visibly explicit. (A bare `0.1-rc.1` also resolves as a
string under the declared PyYAML engine and currently profile-passes; the double-quoted
form is the canonical emitted spelling, not a fix for a rejection.)

## Artifact-Type Mapping

Every template-owned type in the accepted registry (profile §5.2):

| `type` | Artifact class / when to use |
| --- | --- |
| `brief` | objective, scope, constraints, or success-criteria briefs (`00_brief/`) |
| `constraint` | a recorded constraint on the work |
| `decision` | a governance/architecture decision record |
| `analysis` | analysis summaries, findings, or hypotheses (`02_analysis/`) |
| `coding_prompt` | a coder prompt (`prompts/for_coding_agent/`) |
| `review_prompt` | a reviewer prompt (`prompts/for_review_agent/`) |
| `self_report` | a coder self-report |
| `review_report` | a reviewer's report |
| `verdict_record` | a recorded accept/needs-work verdict |
| `delivery_plan` | a delivery report or plan (`04_delivery/`) |
| `framework_doc` | a framework/methodology document (this guide is one) |

Types outside this registry are OKF-valid but profile-`fail`
(`PROFILE_TYPE_UNSUPPORTED`); `source`/`claim`/`entity`/`page` (llloom) and
`milestone`/`slice` (frutlups) are reserved to those packages.

## Copy-Ready Examples

Implementation-loop artifacts (drop the block in as the first lines, then your title
and body):

```yaml
---
type: coding_prompt
framework_profile: "0.1-rc.1"
---
```

```yaml
---
type: review_prompt
framework_profile: "0.1-rc.1"
---
```

```yaml
---
type: self_report
framework_profile: "0.1-rc.1"
---
```

```yaml
---
type: review_report
framework_profile: "0.1-rc.1"
---
```

```yaml
---
type: verdict_record
framework_profile: "0.1-rc.1"
---
```

A framework document (like this guide):

```yaml
---
type: framework_doc
framework_profile: "0.1-rc.1"
---
```

For `brief`, `constraint`, `decision`, `analysis`, and `delivery_plan`, apply the
substitution rule to the minimum block above — for example a brief begins:

```yaml
---
type: brief
framework_profile: "0.1-rc.1"
---
```

## Coexistence With Body Shapes

Frontmatter is additive; it never changes the canonical body:

- **Prompt documents** keep their workflow routing metadata as ordinary **fenced
  Markdown content** (a ```` ```yaml ```` block in the body), clearly not the
  top-of-file frontmatter. The two are different things: the top block is OKF/profile
  frontmatter; the fenced block is workflow content read by the project loop.
- **Self-reports** keep the canonical headings from `prompts/templates/self_report.md`
  exactly, unchanged, after the frontmatter.
- **Review reports and verdict records** gain no authority from metadata; a verdict's
  weight comes from the review, not from a `type` value.
- **Ordinary framework/project documents** retain their existing Markdown bodies with
  only the two-field block added.

## Adoption Sequence (additive and reversible)

1. Inventory or select candidate **new** artifacts with `rg --files`; do not modify
   them while selecting.
2. If an existing project is adopting the profile, record explicit human approval as a
   decision (for example in `05_governance/` or `migration_decision_log.md`).
3. Opt in the exact output paths in a coding prompt (list every path and its registry
   `type`).
4. Add only the two minimum fields, unless a documented use needs more.
5. Run the read-only profile check on those exact paths, plus ordinary project
   validation (`python -m unittest discover -s tests`).
6. Inspect the diff and accept, or roll back.

## Rollback

Rollback means removing the **entire** newly added frontmatter block from the
explicitly opted-in artifact in a reviewed diff, leaving its Markdown body unchanged,
then re-running legacy and project validation. Before rolling back, check whether a
downstream consumer has begun relying on that metadata. For historical artifacts the
default is **no edit at all** — never present bulk removal or history rewriting as
rollback.

## Profile-Version Changes Are Change-Controlled

Do not silently replace `0.1-rc.1`, do not declare stable `0.1`, and do not
mass-update artifacts until a new contract, its compatibility behaviour, a
migration/rollback plan, and fixtures have been accepted (profile §8). A profile
change is a reviewed slice, not an in-place edit.
