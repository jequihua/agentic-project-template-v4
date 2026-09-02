# Coder Self-Report

This file is the canonical self-report schema for the template. Keep these
headings exactly. Other surfaces reference this file rather than defining their
own schema. The coding prompt template points here. The coder initialization
prompt (`002`) carries an onboarding copy of the skeleton that must remain
identical to this file; the `test_self_report_schema_single_source` scaffold test
enforces that agreement.

When a slice opted any output artifact into the OKF profile (see
`docs/template_framework/okf_authoring_and_migration.md`), record each opted-in
path, its assigned registry `type`, and the read-only profile-check result under the
existing headings below (for example within Files Changed and Verification Run). Add
`type: self_report` frontmatter to this report only when its own exact path was
opted in.

Intent:

Files Changed:

Behavior Implemented:

Tests Added Or Updated:

Verification Run:

Record commands and results as dated/run-specific evidence. Distinguish files
owned by this slice from complete shared-worktree state; do not present a
worktree snapshot, active prompt number, or next action as continuing truth.
Report observed external-repository drift honestly with its declared role
(`docs/template_framework/external_repository_roles.md`); preservation-only
drift is reported, not upgraded into a stop.

Definition Of Done Audit:

When the coding prompt carries an Objective And Closure Proof section, state
which closure-proof items this slice produced and which it did not, with the
artifact paths. This is a claim; the objective status itself is recorded by
the reviewer, never here.

When this slice works from review findings, reproduce the controlling
disposition table here and distinguish findings this slice remediated,
findings it only challenged, findings already withdrawn by reviewer
authority, and findings still open. Keep the reproduction compact — the
table's rows plus at most one evidence line each, in the same fifteen-line
spirit as the review-side closure receipt. Never claim closure of a finding
another authority dispositioned. Cite owner or architect instructions by
exact artifact and section, never as invented quotations.

Non-Goals Confirmed:

Deviations From Prompt:

State anything done differently from the prompt, and any prompt item not
done, with the reason. Write "none" when the implementation matches the
prompt exactly.

Memory Used:

Memory Update Requested:

Known Limits / Follow-Up:

When touched code shows material out-of-scope complexity accretion, name one
evidence-backed simplification candidate and treat it explicitly as unapproved
follow-up, not authorized work.

On a corrective pass, also name here the claims withdrawn or narrowed and the
validation evidence invalidated and recollected, matching the corrective
prompt's Correction Scope Map.

Recommended Next Move:

Reference `PROJECT_STATE.md` or the prompt/review index. Avoid copying a current
prompt number when the identity may change during corrective review.

