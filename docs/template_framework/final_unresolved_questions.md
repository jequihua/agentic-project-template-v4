# Final Unresolved Questions

The v2 scaffold build passes (1–7) are complete. These are forward-looking
choices for a future version or the template release decision — not blockers for
adoption.

## Open (deferred)

- **frutlups runner:** whether to build the thin automated driver specified in
  `frutlups_driver_boundary.md` (currently spec-only, no runner).
- **generated indexes / front matter:** whether a future version adds generated
  prompt/review indexes or artifact front matter (currently markdown-first, no
  tooling).
- **mode-value sets:** whether to parse allowed mode values from the modes docs
  instead of hardcoding them in `test_mode_values_are_controlled` (deferred per
  the Pass 6 review; revisit only if mode values start changing often).
- **pruned project copies:** whether a tool should support physically pruned
  per-project copies (currently keep-and-mark-inactive is the default; the v1
  destructive prune scripts are not part of the v2 model).

## Resolved during the build (recorded for the release decision)

- keep-and-mark-inactive over destructive pruning (Pass 3);
- optional lanes default off, opt-in only (Pass 4–5);
- one ceremony axis and controlled mode values (Pass 2, 6);
- single-sourced contracts: self-report schema, `PROJECT_STATE` fields, and the
  frutlups driver spec.
