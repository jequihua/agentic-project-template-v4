# Project State

Status: initialized template scaffold

Template version: v3

Field contract: `docs/template_framework/project_state_contract.md`

Project profile:
- base profile (see `docs/template_framework/project_profiles.md`)

Active workspaces:
- `00_brief`
- `03_experiments`
- `05_governance`
- `prompts`
- `questions`

Optional inactive workspaces:
- `01_data`
- `02_analysis`
- `04_delivery`
- `06_infra`
- `07_app`
- `08_pkg`
- `09_ops`
- `90_legacy_review`
- `memory`

Current objective:
- Run framework initialization and project intake to define this project.

Current loop mode:
- project initialization

Current ceremony level:
- Level 2 - lightweight initialization

Memory mode:
- none

Frutlups mode:
- manual

Latest accepted review:
- none

Optional OKF/profile lane:
- The reusable OKF document profile candidate `0.1-rc.1`, its read-only
  `--profile` checker, the disposable navigation generator, and the opt-in
  authoring guide ship with this template but are inactive by default. Legacy
  no-frontmatter Markdown remains the default. Opt in per new artifact only when a
  project chooses to. See `docs/template_framework/okf_authoring_and_migration.md`.

Next expected action:
- Human owner runs `initialization/001_architect_reviewer_framework_initialization.md`
  and then `initialization/007_architect_reviewer_project_intake_questionnaire.md`.

Validation command:
- `python -m unittest discover -s tests`

Local-state warning:
- Local venvs, caches, raw data, credentials, and llloom memory roots are not
  committed unless explicitly approved.
