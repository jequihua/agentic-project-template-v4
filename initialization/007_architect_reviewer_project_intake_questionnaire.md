# Architect / Reviewer Project Intake Questionnaire

Use this prompt after the architect/reviewer has already initialized on the
artifact-first framework with `001_architect_reviewer_framework_initialization.md`.

This is a light intake, not a hostile interrogation. Ask the human owner the
static questions below, make only necessary follow-up asks, then use the answers
to populate the template and create the first development roadmap.

## Read For Intake

Intake population needs only these, beyond the role initialization:

- `docs/template_framework/project_profiles.md`
- `docs/template_framework/project_state_contract.md`
- `docs/template_framework/review_strictness_levels.md`
- `prompts/templates/coding_prompt.md`
- `docs/template_framework/prompt_style_guide.md`
- `ENVIRONMENT.md`
- `MILESTONES.md` (its Rules section)
- `docs/template_framework/method.md` (the roadmap register semantics)

The full framework corpus is not intake reading; open deeper sources only on
escalation.

## Purpose

The goal is to turn the human owner's project idea into durable project
artifacts:

- a backed-up answer transcript;
- clear problem, scope, constraints, and success criteria;
- a project glossary for overloaded or fuzzy terms;
- the right active workspace/profile selection;
- an honest `PROJECT_STATE.md`;
- a first roadmap and first coding prompt.

Do not start implementation during intake. The output of intake is a project
ready to begin the artifact-first coding loop.

## Tone

Be precise, calm, and economical.

- Ask the whole questionnaire or one compact section at a time, depending on the
  human owner's preference.
- Ask follow-up questions only when an answer is ambiguous, contradictory, or
  blocks template population.
- When the human uses fuzzy or overloaded terms, propose a clear canonical term
  for `00_brief/glossary.md`.
- If the project is an existing repo and the answer can be found in files, inspect
  the files instead of asking the human to restate it.
- Do not pressure the human to over-specify speculative details. Mark unknowns as
  questions or assumptions.

## Answer Backup

Before editing the template from the answers, create:

```text
00_brief/project_intake_answers.md
```

Use this structure:

```markdown
# Project Intake Answers

Date:
Human owner:
Architect/reviewer:

## Raw Answers

Copy or summarize the human answers here, preserving uncertainty and wording that
may matter later.

## Follow-Up Clarifications

Record any follow-up questions and answers.

## Architect Interpretation

Summarize the inferred project type, active profile/toggles, likely risks,
unknowns, and first roadmap shape.

## Terms To Add To Glossary

List canonical terms, aliases, and rejected/ambiguous terms.
```

The backup is historical evidence. Do not rewrite it to make later decisions look
cleaner; append clarifications if needed.

## Questionnaire

### 1. Project Identity

1. What is the project's working name?
2. In one sentence, what is the project trying to achieve?
3. What kind of project is this?
   - Examples: machine-learning biomass estimation, text classification,
     exploratory analysis, mathematical optimization algorithm, reusable package,
     app/dashboard/API, legacy code migration, research prototype, production
     hardening.
4. Who is the primary human owner or decision-maker?
5. Who is the intended user or audience?

Follow up if unclear:
- Is this mainly research, production software, analysis, or migration?
- Is the output meant for humans, another system, a paper/report, or an internal
  workflow?

### 2. Desired Outcome

1. What concrete artifact should exist when the first milestone is done?
   - Examples: validated notebook, trained model, package API, command-line tool,
     dashboard, migration report, benchmark, paper figure, deployment plan.
2. What would make you say "this worked"?
3. What is explicitly out of scope for the first milestone?
4. Are there deadlines, external commitments, or review dates?

Follow up if unclear:
- What is the smallest useful version?
- Which result matters more: correctness, interpretability, speed, reproducible
  evidence, user experience, or deployment readiness?

### 3. Inputs, Data, And Existing Assets

1. What inputs does the project use?
   - Data files, databases, APIs, documents, images, code repositories, manual
     annotations, simulations, human labels, logs, or no data yet.
2. Where do those inputs live?
3. Are there privacy, licensing, IRB, embargo, credential, or sharing
   restrictions?
4. Is there an existing codebase or prior project history?
5. What artifacts already exist and should be trusted?
6. What artifacts exist but may be stale, experimental, or unreliable?

Follow up if unclear:
- Is there a ground truth or reference answer?
- Are labels/measurements noisy or uncertain?
- Should `90_legacy_review/` be activated before coding?

### 4. Method And Technical Direction

1. What approach do you expect?
   - ML model, rules/heuristics, statistical analysis, optimization, simulation,
     package refactor, web app, ETL/data pipeline, report generation, migration.
2. Are there methods, libraries, models, languages, or platforms that must be
   used?
3. Are there methods, libraries, models, languages, or platforms that must not be
   used?
4. What needs to be reproducible?
5. What needs to be explainable or auditable?
6. What level of testing or validation is expected?

Follow up if unclear:
- Is the method already decided, or should the first milestone compare options?
- Are there compute limits, live-cost limits, or hardware constraints?

### 5. Success Metrics And Evidence

1. What metrics or evidence will define success?
   - Accuracy, F1, RMSE, biomass error, runtime, memory use, cost, coverage,
     usability, migration completeness, test pass rate, expert review.
2. What baseline or current state should we compare against?
3. What failure modes would make the result unusable?
4. What evidence should be produced for review?

Follow up if unclear:
- Is "good enough" a numeric threshold, a qualitative judgment, or both?
- Who accepts the evidence?

### 6. Constraints, Risks, And Non-Goals

1. What constraints are hard?
   - Time, compute, budget, dependencies, platform, data access, licenses,
     security, privacy, model choices, interface requirements.
2. What are the biggest risks or unknowns?
3. What should agents avoid doing without explicit approval?
4. What should definitely not be built in the first milestone?

Follow up if unclear:
- Could any action create live cost, credential exposure, data leakage, or
  irreversible history changes?

### 7. Glossary And Project Language

1. Which terms are central to the project?
2. Which terms are overloaded, fuzzy, or domain-specific?
3. Are there synonyms that should be collapsed into one canonical term?
4. Are there terms that must be kept distinct?

Examples:
- "biomass" vs "above-ground biomass" vs "yield";
- "sample" vs "plot" vs "observation";
- "model" as statistical model vs software model;
- "user" vs "customer" vs "operator";
- "migration" as code migration vs data migration.

Follow up if unclear:
- "When you say `<term>`, do you mean X or Y?"
- "Should `<alias>` be recorded as an alias of `<canonical term>`?"

### 8. Workflow Preferences

1. How much review ceremony should the first milestone use?
   - Tiny corrective loop, normal pass, high-risk architecture/migration pass.
2. Should optional memory be used?
   - `Memory mode`: `none`, `lightweight`, or `llloom`.
3. Should optional frutlups loop tooling be used?
   - `Frutlups mode`: `manual`, `semi-manual`, or `automated driver`.
4. Are there preferred commit/checkpoint habits?
5. Should the coder propose review prompts, or should the architect/reviewer
   always own review prompts?

Follow up if unclear:
- If the project is risky, should the first coding prompt be a discovery/review
  slice rather than implementation?

## Populate The Template From Answers

After the questionnaire is complete, use the answer backup as the evidence source
for template population. Make the smallest useful set of edits.

### Choose Profile And Workspaces

From the project type (section 1) and the answers, choose the base profile plus
the optional toggles the project needs, following
`docs/template_framework/project_profiles.md`. Activate only the workspaces the
project requires; leave the rest inactive as scope markers. Record the choice in
`PROJECT_STATE.md` (`Project profile`, `Active workspaces`, `Optional inactive
workspaces`) and flip each activated workspace's `CONTEXT.md` status line.

### Required Edits

Update or create:

- `00_brief/project_intake_answers.md` with raw answers and interpretation.
- `00_brief/problem_statement.md` with the project objective and project type.
- `00_brief/success_metrics.md` with success criteria and evidence expectations.
- `00_brief/constraints.md` with hard constraints, non-goals, and approval
  gates.
- `00_brief/glossary.md` with canonical terms, aliases, definitions, and open
  terminology questions.
- `PROJECT_STATE.md` with honest current state, selected profile/toggles, active
  workspaces, current objective, modes, validation command, latest accepted
  review if any, and next expected action.
- `03_experiments/` with a first roadmap or milestone plan.
- `prompts/for_coding_agent/` with the first coding prompt, if enough
  information exists.

### Conditional Edits

Activate and populate only when justified by the answers:

- `01_data/` for data sources, schemas, quality, splits, leakage, labels, or
  provenance.
- `02_analysis/` for exploratory analysis summaries or hypotheses.
- `04_delivery/` for reports, model cards, stakeholder deliverables, or paper
  outputs.
- `06_infra/` for environment, compute, cloud/HPC, credentials, live validation,
  or blocker-resolution work.
- `07_app/` for dashboards, APIs, web apps, or user-facing tools.
- `08_pkg/` for reusable package code, APIs, or library design.
- `09_ops/` for recurring jobs, monitoring, runbooks, or long-running processes.
- `90_legacy_review/` for existing codebases or migration projects.
- `memory/` and `05_governance/current/memory_posture.md` only when memory mode is
  `lightweight` or `llloom`.

When activating a workspace, update both `PROJECT_STATE.md` and that workspace's
`CONTEXT.md` status line.

## Glossary Format

Populate `00_brief/glossary.md` with this structure:

```markdown
# Glossary

Canonical terms for this project. Keep definitions short and operational.

## Terms

### Term

Definition:

Aliases:

Do not confuse with:

Source / rationale:

Status: accepted | tentative | needs human clarification

## Open Terminology Questions

- Question:
  - Why it matters:
  - Current guess:
```

Do not use the glossary as a specification or scratchpad. Use it to remove
language ambiguity that would otherwise derail prompts, reviews, tests, or
acceptance criteria.

## First Roadmap Shape

Create a first roadmap that is milestone-oriented and modest. Prefer 3-7 slices.
Under the slice prompt contract (`docs/template_framework/slice_prompt_contract.md`),
each slice is additionally a typed entry in the roadmap's sidecar; the prose
fields below remain the human narrative.

For each slice, include:

- objective;
- expected artifacts;
- active workspaces;
- non-goals;
- verification/evidence;
- review strictness level;
- likely first coding prompt path.

If the project is uncertain, make Slice 1 a discovery or legacy-review slice
rather than an implementation slice.

## Definition Of Done

The intake is complete when:

- the answer backup exists;
- the glossary has canonical terms and open terminology questions;
- `PROJECT_STATE.md` tells a coder what is active, next, and out of scope;
- active workspace statuses match `PROJECT_STATE.md`;
- the first roadmap exists;
- a first coding prompt exists or a clearly recorded blocker explains why not;
- optional llloom/frutlups modes remain off unless explicitly chosen;
- the human owner can read the artifacts and recognize the project.
