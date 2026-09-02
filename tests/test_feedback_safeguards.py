"""Contract and fixture tests for the usage-feedback safeguards.

Covers three classification layers added on top of the closure-convergence
machinery: external-repository causal roles (which repositories may block),
the finding-disposition lifecycle (who may change a finding's state), and
risk-calibrated convergence (which findings may block, via the materiality
gate, probe classes, claim budget, and circuit breaker).

The small oracle functions are the pinned reference semantics of the prose
contracts, in the same style as tests/test_closure_convergence.py (the
`_section` / `_table_rows` helpers are copied from there). They grant no
authority; if doctrine changes, change prose and oracle in one reviewed
slice. Standard library only; no optional package is imported.
"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLES_DOC = ROOT / "docs" / "template_framework" / "external_repository_roles.md"
ROLES_REL = "docs/template_framework/external_repository_roles.md"
PROTOCOL = ROOT / "05_governance" / "current" / "review_protocol.md"
CONVERGENCE = ROOT / "docs" / "template_framework" / "closure_convergence.md"
FIX_ROOT = ROOT / "tests" / "fixtures" / "safeguards"

ROLE_NAMES = {"authority_input", "mutation_target", "preservation_only"}
LIFECYCLE_STATES = {
    "open",
    "remediated_pending_review",
    "disputed_pending_review",
    "withdrawn_by_reviewer",
    "closed_by_review",
    "accepted_risk_by_owner",
}
PROBE_CLASSES = ("conformance", "host-limitation", "synthetic-robustness")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Body of the `## heading` section up to the next `## `."""
    out, capturing = [], False
    for line in text.splitlines():
        if line.strip() == heading:
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            out.append(line)
    return "\n".join(out)


def _table_rows(text: str) -> list[dict[str, str]]:
    """Parse the first Markdown table in `text` into header-keyed row dicts."""
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("|")]
    if len(lines) < 3:
        return []
    header = [c.strip().strip("`") for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


# --- pinned reference semantics -------------------------------------------

def role_drift_outcome(role: str, event: str) -> str:
    """Causal-role contract: what a drift event may do to closure."""
    if role == "authority_input":
        return (
            "blocks-dependent-lane"
            if event == "consumed-surface-drift"
            else "no-block"
        )
    if role == "mutation_target":
        return (
            "blocks-closure"
            if event == "outside-envelope-overlap"
            else "no-block"
        )
    if role == "preservation_only":
        return "report-only"
    return "out-of-scope"


def may_record(state: str) -> set[str]:
    """Finding-lifecycle authority: which actors may record a disposition."""
    return {
        "open": {"reviewer"},
        "remediated_pending_review": {"coder"},   # a claim, not a closure
        "disputed_pending_review": {"coder"},     # a challenge, not a withdrawal
        "withdrawn_by_reviewer": {"reviewer", "architect"},
        "closed_by_review": {"reviewer"},
        "accepted_risk_by_owner": {"owner", "architect"},
    }[state]


def materiality_allows(answers: tuple[bool, ...]) -> set[str]:
    """Six materiality answers -> severities the reviewer may assign.

    Questions (any yes keeps P1/P2 available): unintended external effect;
    data/evidence corruption or false acceptance; misrouted recovery, spend,
    credentials, or trust; persistence beyond the failing process or
    unbounded resources; real supported seam outcome; explicitly required
    for this release.
    """
    assert len(answers) == 6
    return {"P0", "P1", "P2", "P3"} if any(answers) else {"P3"}


# --- FIX-1: external repository roles ---------------------------------------

class ExternalRepositoryRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = ROLES_DOC.read_text(encoding="utf-8")
        cls.convergence = CONVERGENCE.read_text(encoding="utf-8")

    def test_doc_exists_and_is_linked(self):
        self.assertTrue(ROLES_DOC.is_file())
        for rel in (
            "docs/template_framework/closure_convergence.md",
            "prompts/templates/coding_prompt.md",
            "prompts/templates/review_prompt.md",
            "prompts/templates/self_report.md",
            "CLAUDE.md",
            "docs/template_framework/architect_operating_card.md",
            "docs/template_framework/reviewer_operating_card.md",
        ):
            with self.subTest(surface=rel):
                self.assertIn(ROLES_REL, _read(rel))

    def test_role_table_membership_and_guarantees(self):
        rows = _table_rows(_section(self.doc, "## The Three Roles"))
        self.assertEqual({r["Role"] for r in rows}, ROLE_NAMES)
        self.assertIn("never blocks", self.doc)          # preservation drift
        self.assertIn("before consuming", self.doc)      # prospective promotion
        self.assertIn("never by filename", self.doc)     # no name attribution
        self.assertIn("omission is the clearest statement", self.doc)

    def test_closed_world_interval_is_role_gated(self):
        assurance = _section(
            self.convergence, "## Assurance Claims And Powerful Harnesses"
        )
        self.assertIn("`authority_input`", assurance)
        self.assertIn("`mutation_target`", assurance)
        self.assertIn("`preservation_only`", assurance)
        self.assertIn("never fails an unrelated lane", assurance)
        # The original interval mechanics and attribution rule survive.
        self.assertIn("closed-world snapshot", assurance)
        self.assertIn("not proof", assurance)

    def test_coding_template_declaration_is_optional(self):
        text = _read("prompts/templates/coding_prompt.md")
        self.assertIn("## External Repositories", text)
        section = text.split("## External Repositories", 1)[1].split("## ", 1)[0]
        flat = " ".join(section.lower().split())
        self.assertIn("delete this section otherwise", flat)
        self.assertIn("do not snapshot them", flat)

    def test_drift_fixture_matches_oracle(self):
        rows = _table_rows(
            (FIX_ROOT / "repo_roles.md").read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(rows), 7)
        self.assertEqual(
            {r["role"] for r in rows} - {"undeclared"}, ROLE_NAMES
        )
        for row in rows:
            with self.subTest(repo=row["repo"], event=row["event"]):
                self.assertEqual(
                    role_drift_outcome(row["role"], row["event"]),
                    row["expected"],
                )


class FindingLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = PROTOCOL.read_text(encoding="utf-8")
        cls.section = _section(cls.protocol, "## Finding Disposition Lifecycle")

    def test_lifecycle_states_membership(self):
        rows = _table_rows(self.section)
        self.assertEqual({r["State"] for r in rows}, LIFECYCLE_STATES)

    def test_role_authority_rule_present(self):
        self.assertIn(
            "A coder owns remediation evidence, not review disposition",
            self.section,
        )
        self.assertIn("activates only when", self.section)

    def test_delta_table_in_coding_template(self):
        text = _read("prompts/templates/coding_prompt.md")
        section = text.split("## Correction Scope Map", 1)[1].split("## ", 1)[0]
        for column in (
            "Finding", "Prior disposition", "Controlling authority action",
            "Coder obligation", "Required closure proof",
        ):
            with self.subTest(column=column):
                self.assertIn(column, section)

    def test_fast_close_carries_disposition_fields(self):
        text = _read("prompts/templates/fast_close_correction.md")
        for field in (
            "Prior disposition:", "New disposition:",
            "Disposition authority:", "Affected finding IDs:",
        ):
            with self.subTest(field=field):
                self.assertIn(field, text)
        self.assertIn("## Attribution-Only Corrections", text)

    def test_role_one_liners_present(self):
        self.assertIn(
            "never withdraw",
            _read("initialization/002_coder_framework_initialization.md"),
        )
        self.assertIn(
            "withdrawal, and closure",
            _read(
                "initialization/"
                "001_architect_reviewer_framework_initialization.md"
            ),
        )
        self.assertIn(
            "dispositions are role-owned",
            _read("docs/template_framework/reviewer_operating_card.md"),
        )

    def test_lifecycle_cases_match_oracle(self):
        text = (FIX_ROOT / "lifecycle_cases.md").read_text(encoding="utf-8")
        authority_part, routing_part = text.split("| case | substantive_change", 1)
        rows = _table_rows(authority_part)
        self.assertGreaterEqual(len(rows), 10)
        for row in rows:
            with self.subTest(case=row["case"]):
                legal = row["actor"] in may_record(row["target_state"])
                self.assertEqual(
                    legal, row["expected"] == "legal",
                    f"authority mismatch: {row['case']}",
                )
        routing_rows = _table_rows("| case | substantive_change" + routing_part)
        for row in routing_rows:
            with self.subTest(case=row["case"]):
                eligible = (
                    row["substantive_change"] == "no"
                    and row["actor_objective_from_record"] == "yes"
                )
                self.assertEqual(
                    "fast-close" if eligible else "level-2-review",
                    row["expected_route"],
                )

    def test_ordinary_slices_carry_no_lifecycle_ceremony(self):
        # 003 case 7 as a direct structural check: every lifecycle surface is
        # gated behind a conditional, so an ordinary passing slice meets none
        # of it.
        coding = _read("prompts/templates/coding_prompt.md")
        scope = coding.split("## Correction Scope Map", 1)[1].split("## ", 1)[0]
        self.assertIn("delete this section otherwise",
                      " ".join(scope.lower().split()))
        report = _read("prompts/templates/self_report.md")
        self.assertIn("When this slice works from review findings", report)
        self.assertIn("activates only when", self.section)
        fast_close = _read("prompts/templates/fast_close_correction.md")
        self.assertIn("write n/a", fast_close)

    def test_reconciliation_is_capped(self):
        flat = " ".join(_read("prompts/templates/self_report.md").split())
        self.assertIn("Keep the reproduction compact", flat)
        self.assertIn("fifteen-line spirit", flat)

    def test_amendment_dominance_rule_in_style_guide(self):
        guide = _read("docs/template_framework/prompt_style_guide.md")
        self.assertIn("controlling delta table", guide)
        self.assertIn("supersede", guide)


class RiskCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = PROTOCOL.read_text(encoding="utf-8")
        cls.convergence = CONVERGENCE.read_text(encoding="utf-8")
        cls.disposition = _section(cls.protocol, "## Convergence And Disposition")

    def test_materiality_gate_shape_and_owner(self):
        self.assertIn("never the implementer", self.disposition)
        numbered = [
            l for l in self.disposition.splitlines()
            if l.strip()[:2] in {"1.", "2.", "3.", "4.", "5.", "6."}
        ]
        self.assertGreaterEqual(len(numbered), 6)
        self.assertIn("All answers no routes the finding to P3", self.disposition)
        self.assertIn(
            "batched per finding class", " ".join(self.disposition.split())
        )
        self.assertIn("envelope arbiter", self.disposition)

    def test_severity_cells_are_calibrated(self):
        rows = _table_rows(self.disposition)
        by_disp = {r["Disposition"]: r for r in rows}
        self.assertIn("release-critical", by_disp["P1"]["Meaning"])
        self.assertIn("synthetic-only", by_disp["P3"]["Meaning"])

    def test_conformance_is_not_release_disposition(self):
        self.assertIn("Conformance is not release disposition", self.convergence)
        self.assertIn("true-but-immaterial", self.convergence)

    def test_claim_budget_at_authoring_time(self):
        assurance = _section(
            self.convergence, "## Assurance Claims And Powerful Harnesses"
        )
        self.assertIn("`total`", assurance)
        self.assertIn(
            "never obligated to deliver a universal",
            " ".join(assurance.split()),
        )
        self.assertIn(
            "budgeted at authoring time",
            _read("docs/template_framework/prompt_style_guide.md"),
        )
        self.assertIn(
            "proof-bearing term", _read("prompts/templates/coding_prompt.md")
        )

    def test_circuit_breaker_present_and_mechanical(self):
        ladder = _section(self.convergence, "## Escalation Ladder")
        self.assertIn("Circuit breaker", ladder)
        self.assertIn("introduced by the previous", ladder)
        self.assertIn("never another same-shape corrective prompt", ladder)
        self.assertIn("inapplicable at round 2", " ".join(ladder.split()))

    def test_probe_classes(self):
        assurance = _section(
            self.convergence, "## Assurance Claims And Powerful Harnesses"
        )
        for cls_name in PROBE_CLASSES:
            with self.subTest(probe=cls_name):
                self.assertIn(cls_name, assurance)
        self.assertIn(
            "names the real seam outcome it models", assurance
        )
        flat = " ".join(assurance.split())
        self.assertIn("never what it may investigate", flat)
        # The per-slice review checklist carries the probe-class check too.
        review = _read("prompts/templates/review_prompt.md")
        self.assertIn("probe class", review)
        self.assertIn("fault injection", review)

    def test_proof_bearing_list_is_a_lint_not_a_grammar(self):
        assurance = _section(
            self.convergence, "## Assurance Claims And Powerful Harnesses"
        )
        flat = " ".join(assurance.replace("**", "").split())
        self.assertIn("equivalent phrasing", flat)
        self.assertIn("a lint, not a grammar", flat)
        # The two claim shapes are named distinctly and reconciled.
        self.assertIn("finding claim map", flat)
        self.assertIn("prompt claim record", flat)
        self.assertIn("the record contains the map", flat)

    def test_closure_receipt_in_output_shape(self):
        output = _section(self.protocol, "## Review Output Shape")
        self.assertIn("closure receipt", output)
        for element in (
            "identity", "finding IDs", "claim-map", "waiver",
            "verification summary", "verdict line", "frozen version",
        ):
            with self.subTest(element=element):
                self.assertIn(element, output)
        flat = " ".join(output.split())
        # The element itself, not merely the closing sentence, must be in the
        # receipt enumeration.
        self.assertIn("standing waiver or accepted-limitation references", flat)
        self.assertIn("a live waiver never stays off it", flat)

    def test_failure_model_ledger_template(self):
        ledger = ROOT / "prompts" / "templates" / "failure_model_ledger.md"
        self.assertTrue(ledger.is_file())
        text = ledger.read_text(encoding="utf-8")
        self.assertIn("Optional", text)
        self.assertIn("powerful-harness", text)
        self.assertIn("frozen", text)
        rows = _table_rows(text)
        self.assertTrue(rows)
        header = set(rows[0].keys())
        self.assertEqual(
            header,
            {"ID", "Seam", "Real outcome", "Support class",
             "Authorized effect", "Required response", "Release severity",
             "Causal test"},
        )
        self.assertIn("failure_model_ledger.md", self.convergence)

    def test_waiver_entries_are_gated_at_closure(self):
        self.assertIn("re-acknowledged by the owner", self.disposition)
        self.assertIn(
            "Re-acknowledge open accepted-limitation",
            _read("docs/template_framework/method.md"),
        )

    def test_intake_read_list_is_bounded(self):
        text = _read(
            "initialization/"
            "007_architect_reviewer_project_intake_questionnaire.md"
        )
        self.assertIn("## Read For Intake", text)
        section = text.split("## Read For Intake", 1)[1].split("## ", 1)[0]
        bullets = [
            l for l in section.splitlines() if l.strip().startswith("- ")
        ]
        self.assertLessEqual(len(bullets), 8)
        self.assertIn("not intake reading", section)
        # Intake authors the first roadmap; the register semantics come along.
        self.assertIn("method.md", section)

    def test_materiality_oracle_truth_table(self):
        no6 = (False,) * 6
        self.assertEqual(materiality_allows(no6), {"P3"})
        for i in range(6):
            answers = tuple(j == i for j in range(6))
            with self.subTest(single_yes=i):
                self.assertIn("P2", materiality_allows(answers))
        self.assertIn("P1", materiality_allows((True,) * 6))


if __name__ == "__main__":
    unittest.main()
