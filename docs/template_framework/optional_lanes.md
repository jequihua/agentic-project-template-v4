# Optional Lanes

Optional capabilities (memory, frutlups) are added as *lanes* with a consistent
shape so they stay opt-in and never become ambient ceremony.

A lane has:

- a modes doc in `docs/template_framework/` defining the allowed modes and the
  default-off state;
- a posture file in `05_governance/current/` recording the current fill-in
  posture when enabled (not a second live-state file);
- an initialization prompt pair in `initialization/` (architect/reviewer + coder);
- a controlled, default-off value in `PROJECT_STATE.md`;
- a scaffold test guaranteeing the test suite never imports the optional tool.

Rules for every lane:

- the default is off; a project that has not chosen the lane can ignore it;
- enabling a lane is explicit (a controlled `PROJECT_STATE.md` value), never
  automatic;
- scaffold tests must not require the optional tool installed;
- the modes doc is canonical for behavior; the posture file is a current fill-in
  surface, not a second copy of live state.

Current lanes: memory (`memory_modes.md`) and frutlups (`frutlups_modes.md`). A
future lane should follow this same shape.
