# Architect initialization

Read `AGENTS.md`, then populate `00_brief/` from the owner's material. Replace
the example roadmap with modest milestones and narrow slices, set workspace
statuses, and record durable decisions in the D-register.

Before issuing work:

1. Set a real `verification.full` argv.
2. Make every slice's acceptance observable and non-goals explicit.
3. Keep `read_first` small enough that the total seat read fits its budget.
4. Set write prefixes narrowly and run `python scripts/roadmap.py check`.
5. Render the human view and confirm the owner recognizes the project.

Run the manual loop in `docs/operating.md`. You own prompt issuance, evidence
recording, review routing, acceptance, and authorized commits. Never rewrite
accepted ledger or review history.
