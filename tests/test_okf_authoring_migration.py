"""Compatibility tests for the opt-in OKF authoring/migration surface.

These reuse the read-only profile checker (they do not add a second parser).
Registry/profile tests are skipped when PyYAML is not installed; an acceptance run
installs the declared dependency first and they run with zero skips there.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
DOCS = ROOT / "docs" / "template_framework"
GUIDE = DOCS / "okf_authoring_and_migration.md"
CARD = DOCS / "architect_operating_card.md"
TEMPLATES = ROOT / "prompts" / "templates"
GUIDE_REL = "docs/template_framework/okf_authoring_and_migration.md"

# Types reserved to downstream packages (profile §5.2). The template-owned coverage set
# is derived by subtracting these from the accepted registry, so a later accepted
# template-owned addition cannot silently escape the guide/example coverage.
RESERVED_DOWNSTREAM = {"source", "claim", "entity", "page", "milestone", "slice"}

try:
    import yaml  # noqa: F401
    _PYYAML = True
except ImportError:
    _PYYAML = False


def _preflight():
    return importlib.import_module("artifact_integrity_preflight")


def _registry() -> set:
    import okf_yaml_profile
    return set(okf_yaml_profile.PROFILE_TYPE_REGISTRY)


def _template_owned_types() -> set:
    return _registry() - RESERVED_DOWNSTREAM


def _profile_records(root, rel_paths):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _preflight().main(["--root", str(root), "--profile", "--json", *rel_paths])
    data = json.loads(buf.getvalue())
    return {a["path"]: a for a in data["artifacts"]}, rc


def _minimum_block(type_value: str) -> str:
    return f'---\ntype: {type_value}\nframework_profile: "0.1-rc.1"\n---\n'


def _yaml_body_blocks(text: str) -> list[str]:
    """Fenced ```yaml blocks in the Markdown body (not the top-of-file frontmatter)."""
    blocks, cur, in_fence = [], [], False
    for line in text.splitlines():
        if not in_fence and line.strip() == "```yaml":
            in_fence, cur = True, []
        elif in_fence and line.strip() == "```":
            blocks.append("\n".join(cur))
            in_fence = False
        elif in_fence:
            cur.append(line)
    return blocks


def _guide_table_types(text: str) -> list[str]:
    """The backticked `type` values in the guide's Artifact-Type Mapping table."""
    types, in_section = [], False
    for line in text.splitlines():
        if line.strip().startswith("## Artifact-Type Mapping"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.lstrip().startswith("|"):
            first = line.strip().strip("|").split("|")[0].strip()
            if first.startswith("`") and first.endswith("`"):
                token = first.strip("`")
                if token != "type":  # skip the header row
                    types.append(token)
    return types


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


class AuthoringPolicyTests(unittest.TestCase):
    """Structural policy invariants that do not require PyYAML."""

    def test_guide_has_profile_frontmatter(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        self.assertTrue(text.startswith('---\ntype: framework_doc\n'))
        self.assertIn('framework_profile: "0.1-rc.1"', text.split("---", 2)[1])

    def test_legacy_templates_have_no_default_frontmatter(self) -> None:
        for name in ("coding_prompt.md", "review_prompt.md", "self_report.md"):
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            self.assertFalse(text.startswith("---\n"), f"{name} gained default frontmatter")

    def test_coding_template_routing_policy(self) -> None:
        coding = _norm((TEMPLATES / "coding_prompt.md").read_text(encoding="utf-8"))
        self.assertIn("okf authoring", coding)
        self.assertIn("legacy/no-frontmatter", coding)
        self.assertIn("exact new artifact path", coding)
        self.assertIn("registry `type`", coding)
        # Prohibits implicit directory/neighbour/file-class and historical conversion —
        # each specific prohibition is asserted so removing one cannot pass silently.
        self.assertIn("historical", coding)
        self.assertIn("directory", coding)
        self.assertIn("neighbouring file", coding)
        self.assertIn("file class", coding)
        self.assertIn("implicitly", coding)
        self.assertIn(GUIDE_REL, coding)

    def test_review_template_routing_policy(self) -> None:
        review = _norm((TEMPLATES / "review_prompt.md").read_text(encoding="utf-8"))
        # Applies only on opt-in, requires the two-field minimum, allows justified
        # conformant optional fields, and never turns the minimum into a maximum.
        self.assertIn("only when the coding prompt opted", review)
        self.assertIn("minimum", review)
        self.assertIn("additional profile-permitted fields", review)
        # Optional fields must be justified and conformant — not arbitrary metadata.
        self.assertIn("documented need", review)
        self.assertIn("conform to the accepted profile", review)
        self.assertIn("do not reject a profile-valid enriched artifact", review)
        self.assertIn("recommended-only", review)
        self.assertNotIn("only `type` and `framework_profile`", review)
        # Still checks path/type, profile evidence, body/legacy, no authority/conversion.
        for phrase in ("exact path/type", "read-only profile-check evidence",
                       "unchanged markdown body", "preserved legacy compatibility",
                       "authority inflation", "unrequested/implicit conversion"):
            self.assertIn(phrase, review)
        self.assertIn(GUIDE_REL, review)

    def test_self_report_template_routing_policy(self) -> None:
        report = (TEMPLATES / "self_report.md").read_text(encoding="utf-8")
        norm = _norm(report)
        self.assertIn("record each opted-in", norm)
        self.assertIn("registry `type`", norm)
        self.assertIn("read-only profile-check result", norm)
        self.assertIn("under the existing headings", norm)
        self.assertIn("only when its own exact path was", norm)
        self.assertIn(GUIDE_REL, norm)

    def test_workflow_metadata_labelled_on_both_prompt_templates(self) -> None:
        for name in ("coding_prompt.md", "review_prompt.md"):
            head = _norm((TEMPLATES / name).read_text(encoding="utf-8").split("```yaml", 1)[0])
            self.assertIn("not", head, f"{name} workflow-metadata block not labelled")
            self.assertIn("frontmatter", head, f"{name} workflow-metadata block not labelled")

    def test_self_report_headings_and_onboarding_invariant(self) -> None:
        report = (TEMPLATES / "self_report.md").read_text(encoding="utf-8")
        fields = [l.strip()[:-1].strip() for l in report.splitlines()
                  if l.strip().endswith(":") and not l.strip().startswith("#")]
        for heading in ("Intent", "Files Changed", "Verification Run",
                        "Definition Of Done Audit", "Recommended Next Move"):
            self.assertIn(heading, fields)
        # 12 = the 11 fields shipped with the OKF slice plus 'Deviations From
        # Prompt', added 2026-08-03 by an owner-approved convergence slice.
        self.assertEqual(len(fields), 12)
        init = (ROOT / "initialization" / "002_coder_framework_initialization.md").read_text(encoding="utf-8")
        for field in fields:
            self.assertIn(f"{field}:", init)

    def test_migration_entry_and_readme_link_to_guide(self) -> None:
        migration = (DOCS / "migration_and_adoption.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(GUIDE_REL, migration)
        self.assertIn(GUIDE_REL, readme)
        self.assertNotIn("## Adoption Sequence", migration)  # links, does not duplicate


@unittest.skipUnless(_PYYAML, "PyYAML not installed")
class ProfileCompatibilityTests(unittest.TestCase):
    def _check_doc(self, content: str):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text(content, encoding="utf-8")
            recs, rc = _profile_records(tmp, ["a.md"])
            return recs["a.md"], rc

    def test_reserved_exclusions_are_registry_members(self) -> None:
        # A typo in the excluded set cannot silently invent a template-owned type.
        self.assertTrue(RESERVED_DOWNSTREAM.issubset(_registry()))

    def test_guide_table_matches_derived_template_types(self) -> None:
        derived = _template_owned_types()
        table = _guide_table_types(GUIDE.read_text(encoding="utf-8"))
        self.assertEqual(len(table), len(set(table)))  # no duplicate rows
        self.assertEqual(set(table), derived)

    def test_minimum_block_valid_for_every_template_type(self) -> None:
        for t in sorted(_template_owned_types()):
            with self.subTest(type=t):
                rec, rc = self._check_doc(_minimum_block(t) + "\n# Title\n\nBody.\n")
                self.assertEqual(rec["okf_concept"]["result"], "pass")
                self.assertEqual(rec["framework_profile"]["result"], "pass")
                self.assertEqual(rec["execution_eligibility"], "not_evaluated")
                self.assertEqual(rc, 0)

    def test_guide_copy_ready_examples_are_valid(self) -> None:
        examples = [b for b in _yaml_body_blocks(GUIDE.read_text(encoding="utf-8"))
                    if b.lstrip().startswith("---") and "<" not in b]
        self.assertGreaterEqual(len(examples), 6)
        for block in examples:
            with self.subTest(block=block.splitlines()[1] if block.splitlines() else block):
                rec, rc = self._check_doc(block.rstrip("\n") + "\n\n# Title\n\nBody.\n")
                self.assertEqual(rec["okf_concept"]["result"], "pass", block)
                self.assertEqual(rec["framework_profile"]["result"], "pass", block)
                self.assertEqual(rc, 0, block)

    def test_shipped_profiled_artifacts_pass_profile(self) -> None:
        # The shipped profiled documents (the authoring guide and the architect
        # operating card, both profiled `framework_doc`) must profile-pass with a
        # clean checker exit — proving the shipped surface, not development history.
        recs, rc = _profile_records(
            ROOT, [GUIDE.relative_to(ROOT).as_posix(),
                   CARD.relative_to(ROOT).as_posix()])
        self.assertEqual(rc, 0)  # checker exit success, not only the per-layer fields
        for rel, rec in recs.items():
            self.assertEqual(rec["okf_concept"]["result"], "pass", rel)
            self.assertEqual(rec["framework_profile"]["result"], "pass", rel)
            self.assertEqual(rec["execution_eligibility"], "not_evaluated", rel)

    def test_enriched_optional_fields_are_accepted(self) -> None:
        # The accepted enriched shape (framework_id/title/description/tags/timestamp)
        # must pass; a corrected reviewer must not reject justified optional fields.
        fixture = ROOT / "tests" / "fixtures" / "okf_profile" / "accepted_full.md"
        recs, rc = _profile_records(ROOT, [fixture.relative_to(ROOT).as_posix()])
        rec = next(iter(recs.values()))
        self.assertEqual(rec["okf_concept"]["result"], "pass")
        self.assertEqual(rec["framework_profile"]["result"], "pass")
        self.assertEqual(rec["execution_eligibility"], "not_evaluated")
        self.assertEqual(rc, 0)  # checker exit success, not only the per-layer fields

    def test_bare_version_spelling_resolves_as_string_and_passes(self) -> None:
        # The guide must not claim bare 0.1-rc.1 is a non-string / out of subset.
        text = _norm(GUIDE.read_text(encoding="utf-8"))
        self.assertNotIn("resolve as a non-string", text)
        self.assertNotIn("non-string and is out of subset", text)
        self.assertIn("resolves as a string", text)
        # Backed by the declared engine and the accepted checker.
        self.assertIsInstance(yaml.safe_load("x: 0.1-rc.1")["x"], str)
        rec, rc = self._check_doc(
            "---\ntype: framework_doc\nframework_profile: 0.1-rc.1\n---\n# T\n\nBody.\n")
        self.assertEqual(rec["okf_concept"]["result"], "pass")
        self.assertEqual(rec["framework_profile"]["result"], "pass")
        self.assertEqual(rc, 0)

    def test_mixed_legacy_and_profile_coexist_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            files = {
                "legacy.md": "# Legacy Doc\n\nPlain Markdown, no frontmatter.\n",
                "prompt.md": _minimum_block("coding_prompt") + "\n# A Prompt\n\nBody.\n",
                "report.md": _minimum_block("self_report") + "\n# A Report\n\nBody.\n",
            }
            for name, content in files.items():
                (tmp / name).write_text(content, encoding="utf-8")
            before = {n: hashlib.sha256((tmp / n).read_bytes()).hexdigest() for n in files}
            recs, rc = _profile_records(tmp, list(files))
            after = {n: hashlib.sha256((tmp / n).read_bytes()).hexdigest() for n in files}
            self.assertEqual(rc, 0)  # legacy + profiled set is a clean checker run
            self.assertEqual(before, after)  # no input was mutated
            self.assertEqual(recs["legacy.md"]["okf_concept"]["result"], "not_evaluated")
            self.assertEqual(recs["legacy.md"]["framework_profile"]["result"], "not_applicable")
            for name in ("prompt.md", "report.md"):
                self.assertEqual(recs[name]["okf_concept"]["result"], "pass")
                self.assertEqual(recs[name]["framework_profile"]["result"], "pass")
            for rec in recs.values():
                self.assertEqual(rec["execution_eligibility"], "not_evaluated")

    def test_profile_success_grants_no_execution_eligibility(self) -> None:
        rec, rc = self._check_doc(_minimum_block("framework_doc") + "\n# T\n\nBody.\n")
        self.assertEqual(rec["framework_profile"]["result"], "pass")
        self.assertEqual(rec["execution_eligibility"], "not_evaluated")
        self.assertEqual(rc, 0)  # checker exit success


if __name__ == "__main__":
    unittest.main()
