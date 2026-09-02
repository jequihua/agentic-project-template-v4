# Architect initialization

Read `AGENTS.md`, then populate `00_brief/` from the owner's material. Replace
the example roadmap with modest milestones and narrow slices, set workspace
statuses, and record durable decisions in the D-register.

Before issuing work:

1. Separate the project horizon, admitted milestones, and current run boundary.
2. Admit one disposable slice using the exact intended toolchain.
3. Configure hermetic verification before accepting a baseline.
4. Put a real user-path smoke test at the integration milestone.
5. Express time, token, cost, retry, and artifact budgets in operational units.
6. Make acceptance observable, non-goals explicit, and `read_first` bounded.
7. Set write prefixes narrowly and run `python scripts/roadmap.py check`.
8. Render the human view and confirm the owner recognizes the project.

Run the manual loop in `docs/operating.md`. You own prompt issuance, evidence
recording, review routing, acceptance, and authorized commits. Never rewrite
accepted ledger or review history.
