# Package Workspace

Status: ships empty — this workspace belongs to YOUR project's package code.

When the package toggle is activated (`docs/template_framework/project_profiles.md`):

- package source code goes under `08_pkg/src/` in your package's directory;
- package tests go under `08_pkg/tests/` (see its README for the discovery
  command shape);
- add project-owned contract docs here as they are earned — for example
  `architecture_contract.md`, `public_api_contract.md`, `testing_strategy.md`,
  `package_status.md`. None are required up front.

The template's own OKF/profile package documentation formerly lived here; it
is framework-owned and now lives in `docs/template_framework/okf_pkg/`.

## Template-owned tooling that remains in this folder

Two OKF-lane tooling artifacts stay at their pinned paths (the generator and
scaffold tests hard-code them): `08_pkg/okf_navigation_manifest.json` and the
optional, generated, disposable `08_pkg/generated/okf_navigation.md`
(regenerate or verify with `python scripts/generate_okf_navigation.py` /
`--check`). They are not authoritative, never copy live state, and are not
part of your project's package. Leave them alone unless working on the OKF
lane itself.
