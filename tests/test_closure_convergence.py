"""Contract and fixture tests for the closure-convergence doctrine.

Structural tests guard that the canonical convergence contract exists, is
linked from the surfaces that must route through it, and keeps its
load-bearing guarantees (ladder rows, disposition set, round tracking,
envelope rule). Fixture tests pin the executable semantics of the ladder,
the recurrence/reset counting, the envelope classification, and the
disposition/verdict routing as small table-driven scenarios.

The tiny rule functions in this module are the pinned reference semantics of
the prose in `docs/template_framework/closure_convergence.md` and the
disposition table in `05_governance/current/review_protocol.md`. They grant
no authority and are not a runner; if the doctrine changes, change both the
prose and these rules in the same reviewed slice.

Standard library only. No optional package (llloom/frutlups) is imported.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "template_framework" / "closure_convergence.md"
DOC_REL = "docs/template_framework/closure_convergence.md"
PROTOCOL = ROOT / "05_governance" / "current" / "review_protocol.md"
FIX_ROOT = ROOT / "tests" / "fixtures" / "convergence"

VERDICTS = ("pass", "needs_work", "blocked", "override")
DISPOSITIONS = {"P0", "P1", "P2", "P3"}
PLANES = {"product", "harness", "evidence", "authority", "environment"}

# Reset reasons the doctrine honors (closure_convergence.md, Recurrence).
ALLOWED_RESET_REASONS = {
    "accepted-architectural-change",
    "accepted-guard-confirmed",
    "human-different-root",
}


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
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


# --- pinned reference semantics -------------------------------------------

def effective_rounds(rows: list[dict[str, str]]) -> list[int]:
    """Round per report, counted per named invariant, honoring only the
    doctrine's reset reasons. Prompt identifiers never affect the count."""
    counts: dict[str, int] = {}
    result = []
    for row in rows:
        invariant = row["invariant"]
        if row.get("reset_reason", "none") in ALLOWED_RESET_REASONS:
            counts[invariant] = 0
        counts[invariant] = counts.get(invariant, 0) + 1
        result.append(counts[invariant])
    return result


def response_legal(round_n: int, row: dict[str, str]) -> bool:
    """Escalation-ladder legality of a response at a given round."""
    resp = row["response"]
    guard = row.get("guard_or_reason") == "yes"
    aware = row.get("human_aware") == "yes"
    authorized = row.get("human_authorized") == "yes"
    if round_n == 1:
        return resp in {
            "narrow-correction", "correction-with-guard",
            "architect-reassessment",
        }
    if round_n == 2:
        return (resp == "correction-with-guard" and guard) or (
            resp == "architect-reassessment"
        )
    if round_n == 3:
        return resp == "architect-reassessment" and aware
    return resp == "revised-method-correction" and authorized


def classify_finding(disposition: str, traces_to_prompt: bool,
                     safety_rail: bool) -> str:
    """Acceptance-envelope classification of a review finding."""
    if disposition == "P3":
        return "advisory"
    if traces_to_prompt or safety_rail:
        return "blocking"
    return "envelope_expansion"


def verdict_legal(findings: list[tuple[str, bool]], verdict: str) -> bool:
    """Disposition routing: `findings` is (disposition, resolved) pairs."""
    unresolved_blocking = [
        d for d, resolved in findings
        if d in {"P0", "P1", "P2"} and not resolved
    ]
    if verdict == "pass":
        return not unresolved_blocking
    if verdict == "needs_work":
        return bool(unresolved_blocking)
    return True  # blocked/override legality depends on external facts


# --- structural contract tests ---------------------------------------------

class ConvergenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.protocol = PROTOCOL.read_text(encoding="utf-8")

    def test_doc_exists_and_is_linked_from_routing_surfaces(self):
        self.assertTrue(DOC.is_file())
        for rel in (
            "05_governance/current/review_protocol.md",
            "prompts/templates/review_prompt.md",
            "docs/template_framework/architect_operating_card.md",
            "docs/template_framework/method.md",
            "CLAUDE.md",
            "docs/template_framework/review_strictness_levels.md",
            "docs/template_framework/prompt_style_guide.md",
            "prompts/templates/coding_prompt.md",
        ):
            with self.subTest(surface=rel):
                self.assertIn(DOC_REL, _read(rel))

    def test_disposition_set_is_exactly_p0_to_p3(self):
        rows = _table_rows(_section(self.protocol, "## Convergence And Disposition"))
        self.assertEqual({r["Disposition"] for r in rows}, DISPOSITIONS)
        # No fifth verdict state may creep in on either canonical surface.
        for name, text in (("protocol", self.protocol), ("doc", self.doc)):
            with self.subTest(surface=name):
                self.assertNotIn("pass_with_conditions", text)

    def test_verdict_line_is_pinned_with_unchanged_vocabulary(self):
        line = "`Verdict: <value> - next: <one move>`"
        for surface in (self.protocol, _read("prompts/templates/review_prompt.md")):
            self.assertIn(line, surface)
            for value in VERDICTS:
                self.assertIn(f"`{value}`", surface)

    def test_plane_vocabulary_membership(self):
        section = _section(self.protocol, "## Convergence And Disposition")
        for plane in PLANES:
            self.assertIn(plane, section)

    def test_ladder_table_shape_and_load_bearing_rows(self):
        rows = _table_rows(_section(self.doc, "## Escalation Ladder"))
        by_round = {r["Round"]: r for r in rows}
        self.assertEqual(set(by_round), {"1", "2", "3", "4+"})
        self.assertIn("guard", by_round["2"]["Required response"])
        self.assertIn("architect reassessment", by_round["3"]["Required response"])
        self.assertIn("human awareness", by_round["3"]["Required response"])
        self.assertIn("corrective coding prompt", by_round["3"]["Prohibited response"])
        self.assertIn("human authorization", by_round["4+"]["Required response"])

    def test_recurrence_counts_invariants_not_prompt_numbers(self):
        section = _section(self.doc, "## Recurrence")
        self.assertIn("prompt numbers", section)
        self.assertIn("fast-close", section)
        self.assertIn("renumbering", section)

    def test_envelope_expansion_rule_present_on_routing_surfaces(self):
        for rel in (
            DOC_REL,
            "05_governance/current/review_protocol.md",
            "prompts/templates/review_prompt.md",
        ):
            with self.subTest(surface=rel):
                self.assertIn("envelope expansion", _read(rel))

    def test_round_tracking_surfaces(self):
        self.assertIn("round: 1", _read("prompts/templates/review_prompt.md"))
        index = _read("05_governance/reviews/INDEX.md")
        self.assertIn("| Round |", index.splitlines()[2])

    def test_correction_scope_map_fields(self):
        text = _read("prompts/templates/coding_prompt.md")
        self.assertIn("## Correction Scope Map", text)
        section = text.split("## Correction Scope Map", 1)[1].split("## ", 1)[0]
        self.assertIn("delete this section", section.lower())
        for field in (
            "Findings addressed:",
            "Allowed files and claims:",
            "Claims withdrawn or narrowed:",
            "Evidence invalidated:",
            "Minimum rerun set:",
        ):
            with self.subTest(field=field):
                self.assertIn(field, section)

    def test_claim_map_and_evidence_window(self):
        assurance = _section(
            self.doc, "## Assurance Claims And Powerful Harnesses"
        )
        for part in ("claim", "domain", "independent falsifier",
                     "causal witness"):
            with self.subTest(claim_map=part):
                self.assertIn(part, assurance)
        self.assertIn("narrow the claim", assurance)
        self.assertIn("reduce unresolved acceptance", assurance)
        window = _section(self.doc, "## Active Evidence Window")
        for level in ("Level 1", "Level 2", "Level 3", "Level 4"):
            with self.subTest(window=level):
                self.assertIn(level, window)

    def test_self_report_carries_deviations_heading(self):
        # The schema-sync test guards the init-002 copy; this guards the
        # heading itself and its placement in the canonical schema.
        report = _read("prompts/templates/self_report.md")
        self.assertIn("Deviations From Prompt:", report)
        self.assertLess(
            report.index("Non-Goals Confirmed:"),
            report.index("Deviations From Prompt:"),
        )
        self.assertLess(
            report.index("Deviations From Prompt:"),
            report.index("Memory Used:"),
        )

    def test_reviewer_operating_card_exists_and_linked(self):
        card = ROOT / "docs" / "template_framework" / "reviewer_operating_card.md"
        self.assertTrue(card.is_file())
        text = card.read_text(encoding="utf-8")
        # Budget: the card stays a one-page routine surface.
        nonblank = [l for l in text.splitlines() if l.strip()]
        self.assertLessEqual(len(nonblank), 80)
        self.assertLessEqual(len(text.split()), 650)
        # Load-bearing content: envelope prohibition, verdict line, round scope.
        self.assertIn("may not widen the envelope", text)
        self.assertIn(
            "`Verdict: <value> - next: <one move>`",
            text,
        )
        self.assertIn("previously blocking findings", text)
        self.assertIn(DOC_REL, text)
        # Linked from the reviewer's entry points.
        card_rel = "docs/template_framework/reviewer_operating_card.md"
        for rel in (
            "initialization/001_architect_reviewer_framework_initialization.md",
            "prompts/templates/review_prompt.md",
        ):
            with self.subTest(entry=rel):
                self.assertIn(card_rel, _read(rel))

    def test_question_template_matches_policy_statuses(self):
        template = ROOT / "questions" / "template_question.md"
        self.assertTrue(template.is_file())
        text = template.read_text(encoding="utf-8")
        policy = _read("05_governance/current/question_policy.md")
        for status in ("open", "answered", "superseded", "withdrawn"):
            with self.subTest(status=status):
                self.assertIn(status, policy)
                self.assertIn(status, text)
        self.assertIn("template_question.md", _read("questions/README.md"))

    def test_loop_on_one_page_table(self):
        method = _read("docs/template_framework/method.md")
        self.assertIn("### The Loop On One Page", method)
        section = method.split("### The Loop On One Page", 1)[1].split("### ", 1)[0]
        rows = _table_rows(section)
        self.assertEqual(len(rows), 7, "the loop table keeps its seven steps")
        actors = " ".join(r["Actor"] for r in rows)
        for actor in ("architect/reviewer", "coder", "reviewer", "human owner"):
            self.assertIn(actor, actors)
        self.assertIn("The Loop On One Page", _read("CLAUDE.md"))

    def test_no_new_required_project_state_field(self):
        """Convergence tracking lives in review artifacts and the review
        index, never as a live-state field. Prose that mentions a round, and
        citations of report filenames like `..._round1.md`, are legitimate
        (simulation finding F1, 2026-08-03); what must never appear is a
        field label that would turn PROJECT_STATE into a convergence
        dashboard."""
        label = re.compile(
            r"^\s*(?:current\s+|latest\s+)?"
            r"(round|recurrence|disposition|envelope)s?\b[^:\n]{0,40}:",
            re.IGNORECASE,
        )
        for line in _read("PROJECT_STATE.md").splitlines():
            self.assertIsNone(
                label.match(line),
                f"PROJECT_STATE.md grew a convergence field: {line!r}",
            )


# --- fixture-driven scenario tests ------------------------------------------

class ConvergenceFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (FIX_ROOT / "manifest.json").read_text(encoding="utf-8")
        )

    def test_fixture_inventory_matches_manifest(self):
        for group, names in self.manifest.items():
            if not isinstance(names, list):
                continue  # e.g. candidate_identities: a digest map, not a group
            found = sorted(
                p.name for p in (FIX_ROOT / group).glob("*.md")
            )
            with self.subTest(group=group):
                self.assertEqual(found, sorted(names))

    def test_ladder_scenarios(self):
        for name in self.manifest["ladder"]:
            rows = _table_rows(
                (FIX_ROOT / "ladder" / name).read_text(encoding="utf-8")
            )
            self.assertTrue(rows, f"{name} has no scenario table")
            rounds = effective_rounds(rows)
            for i, (row, round_n) in enumerate(zip(rows, rounds)):
                with self.subTest(scenario=name, report=i + 1):
                    self.assertEqual(
                        round_n, int(row["expected_round"]),
                        f"{name}: effective round mismatch at report {i + 1}",
                    )
                    self.assertEqual(
                        response_legal(round_n, row),
                        row["expected_legal"] == "yes",
                        f"{name}: legality mismatch at report {i + 1}",
                    )

    def test_envelope_classification(self):
        rows = _table_rows(
            (FIX_ROOT / "envelope" / "findings.md").read_text(encoding="utf-8")
        )
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(finding=row["finding"]):
                self.assertEqual(
                    classify_finding(
                        row["disposition"],
                        row["traces_to_prompt"] == "yes",
                        row["safety_rail"] == "yes",
                    ),
                    row["expected_classification"],
                )

    def test_disposition_verdict_matrix(self):
        cases = (
            ([("P0", False)], "pass", False),
            ([("P1", False)], "pass", False),
            ([("P2", False)], "pass", False),
            ([("P2", True)], "pass", True),
            ([("P3", False)], "pass", True),
            ([("P3", False), ("P2", False)], "pass", False),
            ([("P2", False)], "needs_work", True),
            ([], "needs_work", False),
        )
        for findings, verdict, expected in cases:
            with self.subTest(findings=findings, verdict=verdict):
                self.assertEqual(verdict_legal(findings, verdict), expected)


class CandidateLifecycleTests(unittest.TestCase):
    """Behavioral checks of the candidate/review/acceptance separation.

    The digests below are real: reviews and acceptance records bind the exact
    SHA-256 of the frozen candidate fixtures, and the tests recompute those
    digests from bytes. This proves concretely that creating review and
    acceptance records changes no candidate bytes, and that changed bytes
    after `needs_work` produce a new identity.
    """

    CDIR = FIX_ROOT / "candidate"
    FIELD_NAMES = {
        "candidate_file", "candidate_sha256", "verdict",
        "relies_on_review", "expected",
    }

    @classmethod
    def setUpClass(cls):
        import hashlib
        cls.manifest = json.loads(
            (FIX_ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        cls.digests = {
            name: hashlib.sha256((cls.CDIR / name).read_bytes()).hexdigest()
            for name in ("candidate_a.md", "candidate_b.md")
        }

    def _fields(self, name: str) -> dict[str, str]:
        fields = {}
        for line in (self.CDIR / name).read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() in self.FIELD_NAMES:
                fields[key.strip()] = value.strip()
        return fields

    def test_contract_doc_states_status_neutrality_and_is_linked(self):
        doc = _read("docs/template_framework/candidate_review_acceptance.md")
        self.assertIn(
            "never contains its own current, reviewed, or accepted status", doc
        )
        self.assertIn("no new identity, ever", doc)
        rel = "docs/template_framework/candidate_review_acceptance.md"
        for surface in (
            "docs/template_framework/method.md",
            "prompts/templates/coding_prompt.md",
            "prompts/templates/review_prompt.md",
            "docs/template_framework/architect_operating_card.md",
        ):
            with self.subTest(surface=surface):
                self.assertIn(rel, _read(surface))

    def test_candidate_mode_is_optional_in_coding_template(self):
        text = _read("prompts/templates/coding_prompt.md")
        self.assertIn("## Candidate Identity", text)
        section = text.split("## Candidate Identity", 1)[1]
        self.assertIn("delete this section", section.lower())

    def test_candidate_digests_are_stable_and_distinct(self):
        recorded = self.manifest["candidate_identities"]
        for name, digest in self.digests.items():
            with self.subTest(candidate=name):
                self.assertEqual(digest, recorded[name])
        self.assertNotEqual(
            self.digests["candidate_a.md"], self.digests["candidate_b.md"],
            "needs_work plus changed bytes must produce a new identity",
        )

    def test_candidates_carry_no_status_fields(self):
        import re
        pattern = re.compile(
            r"^(status|verdict|reviewed|accepted|current)\s*:", re.IGNORECASE
        )
        for name in ("candidate_a.md", "candidate_b.md"):
            text = (self.CDIR / name).read_text(encoding="utf-8")
            with self.subTest(candidate=name):
                for line in text.splitlines():
                    self.assertIsNone(
                        pattern.match(line.strip()),
                        f"{name} carries a status field: {line!r}",
                    )

    def test_reviews_bind_the_exact_frozen_identity(self):
        for review in ("review_a.md", "review_b.md"):
            fields = self._fields(review)
            with self.subTest(review=review):
                self.assertEqual(
                    fields["candidate_sha256"],
                    self.digests[fields["candidate_file"]],
                    f"{review} does not bind its candidate's real digest",
                )

    def test_acceptance_binding_rule(self):
        for name in (
            "acceptance_b.md",
            "acceptance_wrong_identity.md",
            "acceptance_nonpassing.md",
        ):
            acceptance = self._fields(name)
            review = self._fields(acceptance["relies_on_review"])
            valid = (
                acceptance["candidate_sha256"] == review["candidate_sha256"]
                and acceptance["candidate_file"] == review["candidate_file"]
                and review["verdict"] == "pass"
            )
            with self.subTest(acceptance=name):
                self.assertEqual(valid, acceptance["expected"] == "valid")


if __name__ == "__main__":
    unittest.main()
