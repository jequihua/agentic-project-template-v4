# Architect initialization

Read `AGENTS.md`, then populate `00_brief/` from the owner's material. Replace
the example roadmap with modest milestones and narrow slices, set workspace
statuses, and record durable decisions in the D-register.

Before issuing work:

1. Separate the project horizon, admitted milestones, and current run boundary.
2. Admit one disposable slice using the exact intended toolchain.
3. Configure the project runtime and full verifier before accepting a baseline;
   prove the maintained command discovers required tests and product dependencies.
4. Put a real user-path smoke test at integration; use fresh processes when the
   documented path prepares, exits, then serves.
5. Express time, token, cost, retry, and artifact budgets in operational units.
6. Make acceptance observable, non-goals explicit, and required reads available.
   Keep notes advisory; distinguish future output paths from missing reads.
7. Own the required integration/docs/test writes or name their architect owner.
   Check the roadmap and use `prompt.py <slice> --preview` to inspect actual scope.
8. Render the human view and confirm the owner recognizes the project.

Run the manual loop in `docs/operating.md`. You own prompt issuance, evidence
recording, review routing, acceptance, and authorized commits. Never rewrite
accepted ledger or review history.

The `/2` template is manual-ready only after its recorded local qualification;
autonomous use still needs the paired runner gates in `docs/upgrading.md`.
Consult `docs/project_checks.md` for optional storage/freshness and research
admission. Research projects separately authorize model, canary and scientific
attempts; a blocker resolution cannot silently replenish those allowances.
