# Human User Manual For Artifact-First Template v3

This manual is for the human owner of a project created from this template. It
explains the philosophy, the folder and file layout, how to start a project, how
to run the agent loop manually or with optional tooling, how commit and pull
request permissions work, and how to publish a clean front-facing repository.

Paths in this manual are written as if the template is the root of your project
repository.

## 1. What This Template Is

This is an artifact-first project template for agentic software development. It
is designed for work where a human owner supervises a loop between:

- an architect/reviewer agent;
- a coding agent;
- optional tooling such as llloom memory or frutlups loop orchestration.

The template is not just a folder skeleton. It is a set of rails. The rails make
sure agents know what matters, what is out of scope, what must be reviewed, what
state is current, and what has already been accepted.

The central idea is:

> Progress is an artifact becoming more explicit, reviewable, or correct.

An "artifact" can be a problem statement, glossary, roadmap, coding prompt,
self-report, review, test, source file, app, package, data schema, report, or
front-facing publication repo. Chat can help produce artifacts, but chat is not
the durable source of truth.

## 2. The Philosophy

### Visible Work Beats Hidden Chat

Agents forget, chats get long, and assumptions drift. The template pushes
important decisions into files so the next agent can read a small, stable set of
artifacts and continue without reconstructing the whole conversation.

### Narrow Slices Beat Broad Autonomy

The loop works best when each coding prompt asks for one coherent slice. A slice
should have:

- a purpose;
- active workspaces;
- a short read-first list;
- explicit non-goals;
- verification;
- a self-report path;
- a definition of done.

### Review Is Findings-First

The reviewer does not simply say "looks good". Reviews lead with issues by
severity, then scope discipline, verification, documentation honesty, closure
decision, and one recommended next move.

### Current State Has One Home

`PROJECT_STATE.md` is the live dashboard. Other files may contain history,
policy, or evidence, but current state should not be duplicated in many places.

### Optional Tooling Is Optional

The template must work manually. llloom and frutlups are optional lanes, not
requirements. A project can ignore them unless the human owner explicitly turns
them on.

### Human Ownership Is Final

Agents can propose, implement, review, and prepare commits. The human owner keeps
final authority over scope, external commitments, irreversible cleanup, live
cost, credentials, pull requests, and publication.

## 3. Roles

### Human Owner

The human owner decides priorities, approves optional lanes, answers project
intake questions, resolves ambiguous requirements, authorizes risky actions, and
may request pull request links or publication steps at any time.

The architect's routine surface is the one-screen operating card
`docs/template_framework/architect_operating_card.md`: it carries the normal loop, the
four OKF rules, the legacy-or-profile decision, the type-selection aid, and escalation
triggers, and links to deeper contracts. Normal project operation does **not** require
reading the full OKF profile or understanding parser internals — routine authors copy a
minimum block and run the checker, and only escalate for migration, profile/version, or
downstream-execution work.

### Architect / Reviewer Agent

The architect/reviewer keeps the project on rails. This role:

- initializes the framework;
- interviews the human owner;
- populates the template;
- selects active workspaces;
- creates the roadmap;
- writes coding prompts;
- reviews implementation and artifacts;
- records verdicts;
- updates `PROJECT_STATE.md`;
- runs Milestone Commit Closure after accepted milestones;
- creates milestone commits by default, unless the human owner changes that
  permission.

### Coding Agent

The coding agent implements the active prompt. This role:

- reads only the current state, active prompt, active workspace context, and
  named files;
- makes narrow changes;
- verifies them;
- writes a self-report;
- does not commit by default;
- does not mutate memory or loop state unless explicitly assigned.

### Optional Tooling

frutlups may help read loop state, generate prompts, validate reports, record
verdicts, and resume work. A conforming external runner may automate handoffs;
the template ships none. llloom may provide durable source-grounded memory.
Neither is required by default.

## 4. Source Of Truth Order

When artifacts disagree, use this order:

1. Latest explicit human instruction.
2. `PROJECT_STATE.md`.
3. Latest accepted review or verdict.
4. `CLAUDE.md`.
5. Active prompt.
6. Active workspace `CONTEXT.md`.
7. Relevant contract artifacts.
8. Named llloom claims, only when memory mode is `llloom`.
9. Older prompts, reviews, and historical roadmaps.

This order matters. For example, if an old roadmap says `08_pkg` is inactive but
`PROJECT_STATE.md` now says it is active, `PROJECT_STATE.md` wins.

## 5. Root Files And Directories

This section describes the template parts exhaustively at the level a human owner
needs to navigate them.

### `README.md`

The lightweight starting page. It tells agents and humans to read:

1. `CLAUDE.md`;
2. `PROJECT_STATE.md`;
3. the relevant initialization prompt.

It also points to adoption guidance and explains that optional lanes are off by
default.

### `CLAUDE.md`

The repository operating instructions for agents. It contains:

- purpose;
- read order;
- source-of-truth order;
- workspace map;
- operating rules;
- role definitions.

Agents should read this before doing normal project work.

### `PROJECT_STATE.md`

The current project dashboard. It should stay short and current. It records:

- status;
- template version;
- profile;
- active workspaces;
- inactive workspaces;
- current objective;
- loop mode;
- ceremony level;
- memory mode;
- frutlups mode;
- latest accepted review;
- next expected action;
- validation command;
- local-state warning.

Use it to answer: "What should happen next?"

### `MILESTONES.md` and `milestones/`

Milestone-level planning and bundles. The template starts with a `m000` adoption
milestone. Use milestones when work needs a named boundary larger than one slice.

### `ENVIRONMENT.md`

Environment notes for the project. Use this for stable environment expectations,
not secrets or local-only paths.

### `LOCAL_STATE_NOT_COMMITTED.md`

Local state and secret-boundary policy. It reminds agents not to commit:

- virtual environments;
- caches;
- credentials;
- tokens;
- raw private data;
- bulky generated outputs;
- local llloom memory roots unless explicitly approved.

When llloom is enabled, record the local memory root and last verified status
here.

### `pyproject.toml`

Template-level Python/test metadata. The scaffold tests are designed to run
without optional tools installed.

### `frutlups.layout.yaml`

A proposed layout configuration that describes the template to frutlups. It
records workspace names, state fields, prompt directories, report suffixes,
optional lanes, validation command, git policy, and pull request policy.

It is documentation-as-data. A project can use it manually as a reference, and
frutlups can use it when supported. Paths are relative to the project root.

### `.gitignore`

The git ignore rules for local state, caches, generated outputs, virtual
environments, and optional memory roots. Before a milestone commit, the
architect/reviewer checks whether `.gitignore` needs updates.

## 6. Workspace Folders

Each workspace has a `CONTEXT.md` file. `CONTEXT.md` is orientation, not live
state. It says what belongs in the folder, what does not, and whether the
workspace is active.

Active/inactive truth lives in `PROJECT_STATE.md`.

### `00_brief/`

Core active workspace. It defines what the project is.

Files:

- `CONTEXT.md`: workspace orientation.
- `problem_statement.md`: the project objective and problem framing.
- `success_metrics.md`: what counts as success and what evidence is required.
- `constraints.md`: hard constraints, non-goals, approval gates, and limits.
- `assumptions.md`: assumptions that are not yet fully proven.
- `glossary.md`: canonical terms, aliases, distinctions, and open terminology
  questions.
- `project_intake_answers.md`: created during the questionnaire; backs up the
  human owner's answers and the architect's interpretation.

Use this folder to make the project understandable before implementation starts.

### `01_data/`

Optional workspace. Activate it for projects with data sources, labels, schemas,
data quality questions, leakage risk, provenance, splits, or privacy/licensing
constraints.

Files:

- `CONTEXT.md`: workspace orientation.
- `data_sources.md`: where data comes from and what can be trusted.
- `schema.md`: fields, units, types, joins, identifiers, and shape.
- `data_quality.md`: missingness, noise, leakage, bias, validation, and known
  issues.

Do not store raw private data here unless the human owner explicitly approves.

### `02_analysis/`

Optional workspace. Activate it for exploratory analysis, hypotheses, durable
interpretations, and findings.

Files:

- `CONTEXT.md`: workspace orientation.
- `findings.md`: reviewed findings and evidence.
- `hypotheses.md`: candidate explanations or analysis directions.

Do not use this as a scratchpad for unreviewed run output.

### `03_experiments/`

Core active workspace. It holds roadmaps, experiment plans, run summaries,
validation evidence, and milestone notes.

Files:

- `CONTEXT.md`: workspace orientation.
- `experiment_plan.md`: planned experiments or validation work.
- `run_summary.md`: curated run results and evidence summaries.
- roadmap files created during intake, for example a first development roadmap.

This is often where the first roadmap lives.

### `04_delivery/`

Optional workspace. Activate it when the project must produce stakeholder-ready
or system-ready outputs.

Files:

- `CONTEXT.md`: workspace orientation.
- `final_summary.md`: final or milestone-level summary.
- `report.md`: structured report, model card, paper-support artifact, or
  deliverable draft.

### `05_governance/`

Core active workspace. It holds decision records, risks, assumptions, costs,
reviews, verdicts, human notes, and current protocols.

Files and folders:

- `CONTEXT.md`: workspace orientation.
- `decision_log.md`: accepted decisions and rationale.
- `assumptions_log.md`: assumptions that affect work.
- `risks.md`: known risks and mitigations.
- `cost_log.md`: cost-sensitive or live-resource notes.
- `review_log.md`: pointer-only compatibility artifact; do not duplicate
  routine review rows here.
- `reviews/INDEX.md`: canonical index of review artifacts and verdicts
  (machine-read by autonomous runners; keep citations as repo-relative
  backtick paths).
- `reviews/m000/README.md`: milestone-specific review bundle placeholder.
- `human_owner_notes/README.md`: place for human-owner notes if needed.
- `current/review_protocol.md`: findings-first review protocol.
- `current/question_policy.md`: how agents should ask or record questions.
- `current/known_divergences.md`: known mismatches between artifacts.
- `current/memory_posture.md`: current posture for optional memory mode.
- `current/frutlups_posture.md`: current posture for optional frutlups mode.

Do not put current project state here if it belongs in `PROJECT_STATE.md`.

### `06_infra/`

Optional workspace. Activate it for environment, cloud, HPC, credentials,
live-cost validation, CI, deployment, or blocker-resolution work.

Files:

- `CONTEXT.md`: workspace orientation.
- `live_validation_gate.md`: rules before live, costly, credentialed, or external
  operations.
- `blocker_resolution_plan.md`: plan for environment or dependency blockers.

### `07_app/`

Optional workspace. Activate it for a user-facing app, dashboard, API, or human
review interface.

Files:

- `CONTEXT.md`: workspace orientation.
- `app_description.md`: app purpose, users, workflows, screens, API surface, or
  UI expectations.

### `08_pkg/`

Optional workspace. Activate it when the project includes reusable package code
or a library/API.

Ships empty apart from orientation files and the pinned OKF navigation
tooling (see `08_pkg/README.md`):

- `CONTEXT.md`: workspace orientation.
- `README.md`: package overview and what belongs here.
- `src/`: your package source tree.
- `tests/README.md`: package test orientation.

Contract docs the project adds as they are earned (none ship):
`architecture_contract.md`, `public_api_contract.md`, `testing_strategy.md`,
`package_status.md`. The template's own OKF package documentation lives in
`docs/template_framework/okf_pkg/`, not here.

Important: this is inside the development repository. It is not a nested git
repo. If the package later needs a public repository, use the front-facing repo
sync lane described later.

### `09_ops/`

Optional workspace. Activate it for recurring operations, scheduled jobs,
monitoring, runbooks, and long-running process habits.

Files:

- `CONTEXT.md`: workspace orientation.
- `long_running_jobs.md`: job inventory and supervision notes.
- `monitoring.md`: monitoring signals and expectations.
- `runbooks.md`: operational procedures.

### `90_legacy_review/`

Optional workspace. Activate it before major changes to an existing codebase or
migration project.

Files:

- `CONTEXT.md`: workspace orientation.
- `repo_map.md`: map of the existing repository.
- `reuse_candidate_log.md`: what can be reused.
- `migration_decision_log.md`: append-only migration decisions.
- `feature_scope.md`: existing/new feature boundaries.
- `legacy_risks.md`: risks in legacy code or migration.

Do not make major legacy-code changes before enough evidence is recorded here.

### `memory/`

Optional workspace. Activate it when `Memory mode` is `lightweight` or `llloom`.

Files:

- `README.md`: memory lane orientation.

For `llloom`, the actual memory root may be local-only and must be recorded in
`LOCAL_STATE_NOT_COMMITTED.md` and `05_governance/current/memory_posture.md`.

## 7. Framework Docs

Framework docs live in `docs/template_framework/`. In a project they are a
snapshot of the template commit recorded in `Template version`; see
`migration_and_adoption.md` for refreshing them to a newer pin.

Important files:

- `method.md`: artifact-first method, default loop, commit discipline, pull
  request policy.
- `project_state_contract.md`: required fields and update cadence for
  `PROJECT_STATE.md`.
- `project_profiles.md`: base profile and optional workspace toggles.
- `workflow_modes.md`: kinds of work.
- `review_strictness_levels.md`: ceremony levels from small fixes to high-risk
  reviews.
- `review_protocol.md` is under `05_governance/current/`, but docs point to it.
- `prompt_style_guide.md`: how prompts should be shaped.
- `template_tests.md`: what scaffold tests prove.
- `optional_lanes.md`: how memory and frutlups stay optional.
- `memory_modes.md`: `none`, `lightweight`, and `llloom`.
- `frutlups_modes.md`: `manual`, `semi-manual`, and `automated driver`.
- `frutlups_driver_boundary.md`: what a conforming thin runner may and must not
  do; the template ships no runner.
- `slice_prompt_contract.md`: the versioned, opt-in typed per-slice prompt
  contract (sidecar YAML, exact write manifest, execution envelope, closure
  record) that autonomous prompt generation renders from.
- `migration_and_adoption.md`: how to adopt v3 in new or existing projects.
- `security_and_local_state.md`: secret and local-state policy.
- `front_repo_sync.md`: development repo to front-facing repo publication
  pattern.
- `final_unresolved_questions.md`: unresolved template-design questions.
- `human_user_manual.md`: this manual.

## 8. Prompts

Prompts live in `prompts/`.

Folders:

- `prompts/for_coding_agent/`: prompts given to the coding agent.
- `prompts/for_review_agent/`: prompts or checklists for review.
- `prompts/templates/`: reusable prompt and report shapes.
- `prompts/handoff/`: handoff notes when needed.
- `prompts/INDEX.md`: prompt index and conventions.

Important templates:

- `prompts/templates/coding_prompt.md`: coding prompt shape.
- `prompts/templates/review_prompt.md`: review prompt shape.
- `prompts/templates/self_report.md`: required coder self-report headings.
- `prompts/templates/fast_close_correction.md`: append-only correction shape for
  tiny documentation fixes.

Prompt numbering should be sequential and narrow. Current state belongs in
`PROJECT_STATE.md`, not in long prompt history.

## 9. Initialization Prompts

Initialization prompts live in `initialization/`. "Run a prompt" means give that
Markdown file to the relevant agent as its instructions for the session.

### `001_architect_reviewer_framework_initialization.md`

Use this first for the architect/reviewer. It teaches the agent:

- the artifact-first method;
- the source-of-truth order;
- role responsibilities;
- commit discipline;
- how to keep `PROJECT_STATE.md` current;
- how to create coding prompts and review implementation.

First action: inspect the project profile and update `PROJECT_STATE.md` so the
coder knows what is active, next, out of scope, and how to validate.

### `002_coder_framework_initialization.md`

Use this first for the coding agent. It teaches the agent:

- implement only narrow slices;
- read the current prompt and active workspace contexts;
- obey non-goals;
- verify changes;
- write the canonical self-report;
- do not commit by default.

First action: read the active coding prompt. If none exists, report that the
architect/reviewer should create one.

### `003_architect_reviewer_llloom_initialization.md`

Use this only if the human owner chooses `Memory mode: llloom`.

It teaches the architect/reviewer what llloom is, how to install it, how to
initialize a memory root, what to populate, and how to update memory safely.

Install source:

```text
<path-to-llloom-repo>
```

Manual:

```text
<path-to-llloom-repo>\manual\agent_usage_manual.md
```

Typical install from a project virtual environment:

```powershell
$python = ".\.venv\Scripts\python.exe"
$llloomRepo = "<path-to-llloom-repo>"
& $python -m pip install -e $llloomRepo
```

The architect/reviewer should treat memory population as a high-ceremony
architecture slice, not a bulk import.

### `004_coder_llloom_initialization.md`

Use this only when `PROJECT_STATE.md` says `Memory mode: llloom`.

It teaches the coder to use llloom read-only by default. The coder may run
commands such as:

- `doctor`;
- `status`;
- `query`;
- `claim-card`;
- `list-claims`;
- `list-sources`;
- `list-pages`;
- `verify`;
- `lint`.

The coder must not hand-edit llloom claim YAML, source registry, journals, locks,
or rendered claim blocks unless explicitly assigned a memory-update slice.

### `005_architect_reviewer_frutlups_initialization.md`

Use this only if the human owner wants frutlups to help run the loop.

It explains that frutlups can help with:

- loop status;
- next frontier;
- coding prompt creation;
- review prompt creation;
- self-report and review-report validation;
- verdict recording;
- resumability.

Reference source:

```text
<path-to-frutlups-repo>
```

Reference guide:

```text
<path-to-frutlups-repo>\08_pkg\ARTIFACT_TEMPLATE_GUIDE.md
```

The architect/reviewer records mode in `PROJECT_STATE.md`:

- `manual`;
- `semi-manual`;
- `automated driver`.

### `006_coder_frutlups_initialization.md`

Use this only when `PROJECT_STATE.md` enables frutlups.

It teaches the coder that frutlups is a compass and gate helper, not a
replacement for judgment or self-reporting. The coder may use read-only
orientation commands when enabled, but should not record verdicts unless
explicitly assigned.

### `007_architect_reviewer_project_intake_questionnaire.md`

Use this after the architect/reviewer has initialized on the framework. This is
the human-owner questionnaire.

It asks about:

- project identity;
- desired outcome;
- inputs, data, and existing assets;
- method and technical direction;
- success metrics and evidence;
- constraints, risks, and non-goals;
- glossary and project language;
- workflow preferences.

Then it instructs the architect/reviewer to:

- create `00_brief/project_intake_answers.md`;
- populate `00_brief/problem_statement.md`;
- populate `00_brief/success_metrics.md`;
- populate `00_brief/constraints.md`;
- populate `00_brief/glossary.md`;
- choose profile and active workspaces;
- update `PROJECT_STATE.md`;
- create a first roadmap in `03_experiments/`;
- create the first coding prompt if enough information exists.

## 10. First Steps For A New Project

Use this sequence when starting a new project from the template.

### Step 1: Create The Development Repository

Create a new repository from the template. This repository is the development
repository. It contains the artifact-first loop and the software under
development.

Do not initialize a nested repo inside `08_pkg/` or any other workspace.

### Step 2: Run The Architect / Reviewer Framework Initialization

Give the architect/reviewer:

```text
initialization/001_architect_reviewer_framework_initialization.md
```

Expected outcome:

- architect/reviewer understands the template;
- `PROJECT_STATE.md` is checked and corrected if necessary;
- the human owner is ready for intake.

### Step 3: Decide Optional Lanes

The defaults are:

```text
Memory mode: none
Frutlups mode: manual
```

Keep those defaults unless you have a reason to enable optional tooling.

Choose `llloom` when source-grounded memory is worth the overhead.

Choose `frutlups` semi-manual mode when you want tool-assisted loop state,
prompt generation, report validation, and verdict recording.

Do not enable either just because it exists.

### Step 4: Run The Project Intake Questionnaire

Give the architect/reviewer:

```text
initialization/007_architect_reviewer_project_intake_questionnaire.md
```

The architect/reviewer interviews the human owner, makes only necessary
follow-up asks, and creates the durable intake artifacts.

Expected output:

- `00_brief/project_intake_answers.md`;
- populated brief files;
- populated glossary;
- chosen active workspaces;
- updated `PROJECT_STATE.md`;
- first roadmap;
- first coding prompt or a clear blocker.

### Step 5: Run The Coder Framework Initialization

Give the coding agent:

```text
initialization/002_coder_framework_initialization.md
```

Then give it the first coding prompt created by the architect/reviewer.

Expected output:

- implementation or artifact edits for the slice;
- verification;
- a self-report with required headings.

### Step 6: Review The Slice

The architect/reviewer reviews:

- changed files;
- tests and verification;
- self-report claims;
- non-goals;
- project state updates;
- documentation honesty.

The review is written using the findings-first shape from
`05_governance/current/review_protocol.md`.

### Step 7: Decide And Continue

The review verdict determines the next move:

- accepted: update `PROJECT_STATE.md`, maybe commit at milestone boundary;
- needs work: create a corrective coding prompt;
- blocked: ask the human owner or resolve external dependency;
- override: human decision required.

## 11. The Questionnaire And Template Population

The questionnaire is intentionally lighter than a full interrogation. Its goal is
not to ask everything. Its goal is to ask enough that agents can work safely.

The architect/reviewer should:

1. Ask the static questions.
2. Ask follow-ups only for ambiguity, contradiction, or missing required facts.
3. Inspect existing files instead of asking the human to restate discoverable
   facts.
4. Mark unknowns as assumptions or questions.
5. Write the answer backup before editing the template.
6. Populate the smallest useful set of artifacts.

The human owner should expect questions such as:

- What is the project trying to achieve?
- What kind of project is it?
- What artifact should exist after the first milestone?
- What inputs or existing code exist?
- What methods or tools must be used or avoided?
- What metrics or evidence define success?
- What constraints, risks, and non-goals matter?
- Which terms need precise definitions?
- Should memory or frutlups be enabled?

The glossary is important. It prevents agents from mixing up terms such as:

- "model" as statistical model vs software model;
- "sample" vs "observation";
- "migration" as code migration vs data migration;
- "user" vs "operator";
- project-specific scientific or business terms.

## 12. Running The Development Roadmap Manually

Manual operation is the default and must always remain valid.

The manual loop:

1. Architect/reviewer reads `PROJECT_STATE.md` and the roadmap.
2. Architect/reviewer writes a narrow coding prompt in
   `prompts/for_coding_agent/`.
3. Coder runs the prompt.
4. Coder writes a self-report.
5. Architect/reviewer writes or runs a review prompt/checklist.
6. Architect/reviewer writes a review and verdict.
7. `PROJECT_STATE.md` is updated.
8. The next prompt is created, or the milestone closes.

Manual mode is best when:

- the project is small;
- the human owner wants close supervision;
- frutlups is not installed;
- the loop needs flexible discussion.

### Optional Roadmap Uncertainty And Project Exclusions

Two optional roadmap headings keep long-lived planning honest. Both are
manual-first and neither is required.

Give each concern exactly one destination:

- the next reviewable transition is already clear -> write a normal slice;
- a precise dependency is owned outside the slice (an external answer, an
  authority, a credential, a cost decision) -> keep it as a question or block,
  and it stays sharp;
- the concern is plausibly in scope but cannot yet be framed honestly as a
  slice -> add an optional `## Not Yet Specified` bullet;
- the work is deliberately outside the project destination -> add an optional
  `## Ruled Out` bullet with its reason, date, and evidence or authority.

Entries are ordinary Markdown bullets. Neither list feeds execution
automatically, and neither is a slice.

Reconsider both lists at an accepted slice boundary or during a deliberate
planning pass, not on every action. At that point a `Not Yet Specified` entry
may stay, sharpen into a slice, split, merge, or disappear with a brief reviewed
explanation.

Human approval is required when a new exclusion would narrow the project
destination, and when ruled-out work is resurrected. An architect may record an
exclusion the brief or an accepted owner decision already established, and the
reviewer checks that citation.

Full definitions, the admission decision, and an example live in
`docs/template_framework/method.md`.

### Optional Fresh Contexts At Durable Handoffs

Refreshing an agent context is an optional, controller/human-owned orchestration
choice. Persistent contexts remain fully valid. Supported choices:

- keep a persistent context;
- start a fresh context after an accepted milestone closure; or
- start a fresh context after a complete artifact handoff.

A durable handoff means the active prompt, implementation evidence/self-report,
verdict, unresolved questions, and the next action relevant to that boundary are
recorded in repository artifacts. Never refresh midway through implementation or
review, or while material information exists only in chat.

Reinitialize a fresh session from the role initialization prompt, `CLAUDE.md`,
`PROJECT_STATE.md`, the architect operating card when relevant, and the active
slice artifacts. The purpose is to reduce accumulated transcript cost and stale
assumptions, not to weaken evidence, hide history, or require a new workflow
mode.

## 13. Running The Roadmap With Frutlups

frutlups is optional loop tooling. It is not a replacement for the template. It
reads and writes the same artifacts.

### Manual Mode

`Frutlups mode: manual`

No frutlups. Use files and prompts by hand.

### Semi-Manual Mode

`Frutlups mode: semi-manual`

Use frutlups as a compass and artifact helper. Read-only commands may include:

```powershell
.\.venv\Scripts\python.exe -m frutlups status .
.\.venv\Scripts\python.exe -m frutlups next .
.\.venv\Scripts\python.exe -m frutlups status . --json
```

Write commands should be previewed first:

```powershell
.\.venv\Scripts\python.exe -m frutlups make-coding-prompt . --dry-run
.\.venv\Scripts\python.exe -m frutlups make-review-prompt . --dry-run
.\.venv\Scripts\python.exe -m frutlups record-verdict . --dry-run
```

Recorded verdicts move the frontier. Do not hand-edit loop state to pretend a
review happened.

### Automated Driver Mode

`Frutlups mode: automated driver`

The interface between the template and any runner remains
specification-only and runner-neutral in this template.
No runner ships with this template. A conforming external runner now
exists — frutlups-drive, published as its own repository — which implements
the typed outcomes below and has driven complete projects autonomously; this
template does not depend on it, and
any runner honoring the normative boundary may sit in its place.
A thin runner may:

- consume `frutlups status --json`;
- route prompt files to configured agents;
- wait for self-reports and reviews;
- validate reports;
- record verdicts;
- stop on gates;
- report commit-ready or pull-request-ready.

A conforming runner acts on typed planning outcomes:

- `ready`: continue the declared loop;
- `needs_specification`: run one bounded architect planning turn, then recompute
  durable state;
- `blocked`: stop and report the cited block and its owner;
- `complete`: succeed only when explicit accepted completion evidence exists;
- `invalid` or an unknown outcome: stop fail-closed with diagnostics.

Also true of any conforming runner:

- an empty frontier and retry exhaustion never imply completion;
- it consumes versioned frutlups state instead of parsing roadmap prose;
- it must not graduate `Not Yet Specified` entries, choose `Ruled Out` entries,
  or decide project scope;
- human approval gates remain intact; and
- it must not commit or open pull requests by default.

The runner must also stop on a blocked verdict, a required override, an invalid
self-report, an invalid review report, a memory gate failure, or an environment
gate failure.

Initializing a project for fully autonomous work (proven by the first
published runner's live campaigns; runner commands live in the runner's own
operator manual, not here):

- initialize from the current template pin and record it in
  `Template version` (`v3 @ <commit>`), so a later session can tell which
  template the checked-in docs are a snapshot of;
- declare `Frutlups mode: automated driver`, and — for a project where no
  human keeps ledgers — declare the no-ledger index mode in the runner's
  committed policy: the reviews INDEX then legitimately stays at its shipped
  header-only state, and any data row that appears is treated as an anomaly,
  never as bookkeeping;
- declare seat models, budgets, and corrective efforts (one rung above each
  seat's default, drawn from a fail-closed catalog fixed at initialization)
  identically in the committed policy and the human-approved live gate; the
  run starts only on the human owner's explicit launch word;
- keep machine-local bindings (provider CLIs, the planning tool, the optional
  memory tool) in ignored local state, written without a byte-order mark,
  each tool in its own isolated environment the runner reaches only through
  declared subprocess boundaries;
- review reports carry exactly one verdict section per file, and later rounds
  use their own round-qualified files — the released planning tool refuses an
  ambiguous multi-verdict file rather than silently resolving it;
- opt into the slice prompt contract
  (`docs/template_framework/slice_prompt_contract.md`): typed sidecar entries
  with exact write manifests, a complete execution envelope on every live
  slice, bindings declared by name here and by value in the runner policy,
  and the pre-launch size check run before the launch word;
- expect governed self-recovery and governed stops, not silent failure: a
  seat that completes without delivering its declared artifacts is waited
  out and re-dispatched once at the corrective effort, and unresolvable
  situations stop fail-closed with a typed reason and an escalation document
  for the human.

The normative boundary is
`docs/template_framework/frutlups_driver_boundary.md`.

## 14. llloom Memory

llloom is optional durable, source-grounded memory.

Use llloom when the project needs a stable memory of claims and evidence across
many agent sessions, especially when provenance matters.

Do not use llloom when the repository artifacts are enough.

### Memory Modes

`Memory mode: none`

Default. Repository artifacts are the only memory.

`Memory mode: lightweight`

A plain Markdown facts/claims file is used. No llloom package.

`Memory mode: llloom`

llloom is used for source-grounded claims, pages, registries, journals, and
verification.

### llloom Responsibilities

Architect/reviewer:

- initializes memory;
- populates source-grounded claims;
- updates memory only in explicitly assigned memory-update slices or under
  direct human-owner authority;
- records posture in `05_governance/current/memory_posture.md`.

Coder:

- reads memory only when relevant;
- cites claims/pages used in self-report;
- reports stale or contradictory memory;
- does not mutate memory unless explicitly assigned a memory-update slice or
  acting under direct human-owner authority.

### Populated Roots In The Autonomous Loop

When an autonomous runner drives a project with `Memory mode: llloom` over a
populated root (proven live by the first published runner's campaigns):

- the root is authored before launch through llloom's own released verbs from
  a seed manifest of locator-anchored claims; pages need their commentary
  pairs, and an interrupted apply is recovered with llloom's own dead-owner
  unlock, never by hand-editing the root;
- the runner injects bounded, read-only memory context per dispatch under
  declaration authority; health checks fail closed; memory never gains
  control flow;
- at run boundaries the runner may submit a governed update proposal to the
  llloom review queue; nothing is ever applied to the root by a machine —
  applying updates remains a human or architect decision.

### Installation Reminder

Install source:

```text
<path-to-llloom-repo>
```

Manual:

```text
<path-to-llloom-repo>\manual\agent_usage_manual.md
```

Example:

```powershell
$python = ".\.venv\Scripts\python.exe"
$llloomRepo = "<path-to-llloom-repo>"
& $python -m pip install -e $llloomRepo
```

The memory root is the layout-configured
`optional_lanes.llloom.memory_root` in `frutlups.layout.yaml`. Record it in:

- `05_governance/current/memory_posture.md`;
- `LOCAL_STATE_NOT_COMMITTED.md`.

`PROJECT_STATE.md` selects the mode only; it has no memory-root field.

## 15. Commit Permissions And Milestone Closure

The default policy is:

- architect/reviewer commits accepted milestones;
- coder does not commit by default;
- automation does not commit by default;
- automation may commit only when explicitly configured and authorized;
- pull request opening is separate and human-controlled.

After a positive milestone verdict, the architect/reviewer normally runs the
Milestone Commit Closure checklist:

1. Run validation, or record why it cannot run.
2. Inspect `git status --short`.
3. Update `.gitignore` if generated junk or local state appears.
4. Confirm no credentials, private raw data, caches, test output, local state, or
   unrelated files are being committed.
5. Stage only accepted milestone files.
6. Inspect `git diff --cached --stat`.
7. Inspect `git diff --cached --name-only` when useful.
8. Commit with a clear milestone message.

The human owner may change the policy. For example:

- allow the architect/reviewer to commit every accepted slice;
- allow frutlups automation to commit after accepted milestones;
- require the human to perform commits manually;
- pause commits until a roadmap is complete.

Whatever policy is chosen should be recorded in:

- `docs/template_framework/method.md` if it is a template-wide policy;
- `frutlups.layout.yaml` if frutlups/runner behavior needs to know it;
- `PROJECT_STATE.md` or governance notes if it is project-specific.

## 16. Pull Request Permissions And Links

Commits and pull requests are different.

Default PR policy:

- the human owner controls PR timing;
- agents/runners may report `pull-request-ready`;
- agents/runners must not open PRs by default;
- the human owner may request a PR link at any time.

Good PR boundaries:

- completed roadmap;
- release candidate;
- human-defined work package;
- a branch with stacked accepted milestone commits.

The human owner can ask the architect/reviewer:

```text
Please prepare a pull request link for the current branch.
```

Depending on repository setup, the agent can:

- verify status and branch;
- ensure accepted commits are present;
- push the branch if explicitly authorized;
- return a GitHub compare URL;
- or, if explicitly authorized, create the pull request.

If only a link is requested and the branch is pushed, a compare URL usually has
this shape:

```text
https://github.com/<owner>/<repo>/compare/<base>...<branch>?expand=1
```

Do not open a PR automatically unless the human owner explicitly asks for that or
an authorized workflow allows it.

## 17. Development Repo Versus Front-Facing Repo

A project made from this template is a development repository. It contains:

- brief;
- roadmap;
- prompts;
- reviews;
- governance;
- tests;
- code;
- optional memory/tooling posture;
- artifacts that help agents work safely.

That is not always what you want to publish to the world.

If the developed software needs a clean public repo, use a separate
front-facing repository. The front-facing repo is populated as a curated
projection of files from the development repo.

Do not create a nested git repo inside `08_pkg/`.

## 18. First Publication To A Front-Facing Repo

The front repo tools live in:

```text
scripts/front_repo_sync/
```

Files:

- `bootstrap_front_repo.py`: first-copy export to a clean non-repo directory.
- `sync_front_repo.py`: ongoing one-way sync to an existing front-facing git
  repo.
- `front_repo_sync_manifest.example.toml`: curated projection manifest.
- `front_repo_gitignore`: starting `.gitignore` for the front-facing repo.
- `README.md`: local tool instructions.

### First Copy When The Front Repo Does Not Exist Yet

1. Adapt `scripts/front_repo_sync/front_repo_sync_manifest.example.toml`.
2. Run check mode:

```powershell
python scripts/front_repo_sync/bootstrap_front_repo.py --check --output-dir <DIR>
```

3. If the plan is right, run apply:

```powershell
python scripts/front_repo_sync/bootstrap_front_repo.py --apply --output-dir <DIR>
```

4. Inspect `<DIR>`.
5. Run validation in `<DIR>` if needed.
6. Human owner initializes git in `<DIR>`:

```powershell
git init
git add .
git commit -m "Initial publication"
git remote add origin <remote-url>
git push -u origin main
```

The bootstrap tool never runs `git init`, never commits, never pushes, and never
opens PRs.

### Ongoing Sync After The Front Repo Exists

Run check:

```powershell
python scripts/front_repo_sync/sync_front_repo.py --check --target-repo <FRONT_REPO_DIR>
```

Run apply:

```powershell
python scripts/front_repo_sync/sync_front_repo.py --apply --target-repo <FRONT_REPO_DIR>
```

The sync tool:

- is one-way from development repo to front-facing repo;
- requires the target to contain `.git`;
- requires a clean target tree before apply unless explicitly overridden;
- keeps writes/deletes inside the target;
- refuses nested dev/target roots;
- refuses source paths outside the dev repo;
- rejects symlinked files or subdirectories in mirrored sources;
- never commits, pushes, opens PRs, initializes git, or calls frutlups.

The human/project workflow owns commits and PRs in the front-facing repo.

## 19. Tests And Validation

The scaffold tests protect rails. Run:

```powershell
python -m unittest discover -s tests
```

The tests check structural invariants such as:

- required files exist;
- `PROJECT_STATE.md` follows its contract;
- active/inactive workspace statuses are explicit;
- optional tools are not imported by scaffold tests;
- prompt self-report schema stays aligned;
- frutlups layout config remains portable;
- commit and PR policies are encoded;
- front-repo sync safety rails exist and behave;
- the shipped memory-default check runs only while `Status` is still the
  scaffold default; the machine-local-path and LF checks walk the
  template-owned surfaces in every project, skipping the governed local
  surfaces (`.frutlups_drive/`, `local_state/`).

Tests do not replace human review. Reviews should still perform adversarial
checks when a safety rail matters.

## 20. Common Operating Patterns

### Small Documentation Fix

Use a Level 1 or Level 2 pass. Keep changes narrow. Fast-close must be
append-only and must not change behavior.

### Normal Feature Slice

Use a Level 3 prompt. Require code/artifact changes, verification, self-report,
and review.

### High-Risk Slice

Use Level 4 for:

- architecture changes;
- credentials;
- live cost;
- cloud/HPC;
- legacy migration;
- llloom memory population;
- security-sensitive work.

### Existing Codebase

Activate `90_legacy_review/` first. Map the repo, identify reuse candidates, and
record migration decisions before major changes.

### Data Science Or ML Project

Likely activate:

- `01_data/`;
- `02_analysis/`;
- `03_experiments/`;
- `04_delivery/`;
- maybe `08_pkg/` if code becomes reusable;
- maybe `06_infra/` if compute or environment is complex.

### Package Project

Likely activate:

- `08_pkg/`;
- maybe `06_infra/` for CI/environment;
- maybe front-facing repo sync for publication.

### App Or Dashboard

Likely activate:

- `07_app/`;
- `08_pkg/` if shared code is needed;
- `06_infra/` for runtime/deployment;
- `09_ops/` if it will be operated.

## 21. What To Ask Agents For

Useful requests to the architect/reviewer:

```text
Initialize on the template framework.
Run the project intake questionnaire.
Populate the template from my answers.
Create the first roadmap.
Create the next coding prompt.
Review the coder self-report.
Run milestone commit closure.
Prepare a pull request link for the current branch.
Help sync the front-facing repo.
```

Useful requests to the coder:

```text
Run this coding prompt.
Verify the implementation.
Write the self-report at the specified path.
Do not commit.
```

Useful requests when optional lanes are enabled:

```text
Initialize llloom for this project.
Use llloom read-only for this slice and cite claims used.
Run frutlups status and next.
Use frutlups to draft the next prompt with --dry-run.
Record this verdict with frutlups after review.
```

## 22. Human Control Checklist

Before starting:

- Do I know the project objective?
- Did the architect/reviewer run the framework initialization?
- Did we run the intake questionnaire?
- Is `PROJECT_STATE.md` honest?
- Are optional lanes off unless explicitly chosen?

Before coding:

- Is there a narrow coding prompt?
- Are active workspaces correct?
- Are non-goals explicit?
- Is validation defined?

Before accepting a slice:

- Did the coder write a self-report?
- Did tests or validation run?
- Did review check claims, scope, and artifacts?
- Is `PROJECT_STATE.md` updated?

Before committing:

- Was the milestone accepted?
- Did `.gitignore` get checked?
- Are only accepted files staged?
- Are secrets/local state excluded?
- Did validation pass or is failure documented?

Before opening or requesting a PR:

- Is the branch pushed or ready to push?
- Is the PR boundary intentional?
- Did the human owner request the link or PR?

Before publishing to a front-facing repo:

- Is the manifest curated?
- Did `--check` look right?
- Did bootstrap/sync write only expected files?
- Is the front repo separate, not nested?
- Did the human owner inspect before first commit/push?

## 23. The Short Version

1. Create the development repo from the template.
2. Run architect/reviewer initialization.
3. Run the project intake questionnaire.
4. Populate the brief, glossary, state, roadmap, and first prompt.
5. Run coder initialization and the first coding prompt.
6. Review findings-first.
7. Iterate until a milestone is accepted.
8. Run Milestone Commit Closure.
9. Request PR links when the human owner wants them.
10. Use front-repo bootstrap/sync only when you want a clean public repo separate
    from the development repo.
