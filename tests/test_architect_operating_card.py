"""Reusable contract tests for the architect operating card and role entry points.

Standard library plus the already-installed PyYAML boundary only where the accepted
registry must be read. No optional package (llloom/frutlups/Drift) is imported. These
protect the shipped operating-card budget, its exact registry-derived type-aid
partition, and the progressive-disclosure role read lists, independently of any
development-only handoff bundle.
"""

from __future__ import annotations

import importlib
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

CARD = ROOT / "docs" / "template_framework" / "architect_operating_card.md"
CARD_REL = "docs/template_framework/architect_operating_card.md"

# Types reserved to downstream packages (profile §5.2); excluded from the
# template-owned partition the card's type-selection aid must list.
RESERVED_DOWNSTREAM = {"source", "claim", "entity", "page", "milestone", "slice"}

try:
    import yaml  # noqa: F401
    _PYYAML = True
except ImportError:
    _PYYAML = False


def _ticks(line: str) -> list[str]:
    return re.findall(r"`([^`]+)`", line)


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


def _numbered_items(section_body: str) -> list[str]:
    return [re.sub(r"^\d+\.\s*", "", l.strip())
            for l in section_body.splitlines() if re.match(r"^\d+\.\s", l.strip())]


class OperatingCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CARD.read_text(encoding="utf-8")
        cls.body = cls.text.split("---", 2)[2]

    def test_is_profiled_framework_doc(self):
        self.assertTrue(self.text.startswith('---\ntype: framework_doc\n'))
        self.assertIn('framework_profile: "0.1-rc.1"', self.text.split("---", 2)[1])

    def test_line_and_word_limits(self):
        nonblank = [l for l in self.body.splitlines() if l.strip()]
        self.assertLessEqual(len(nonblank), 80)
        self.assertLessEqual(len(self.body.split()), 650)

    def test_contains_loop_rules_tree_authority_escalation(self):
        low = self.text.lower()
        self.assertIn("## normal loop", low)
        self.assertIn("## four okf rules", low)
        self.assertIn("legacy or profile?", low)          # decision tree
        self.assertIn("conformance is not authority", low)  # authority warning
        self.assertIn("escalate", low)
        for trigger in ("migration", "profile version", "dependency", "credentials",
                        "execution semantics"):
            self.assertIn(trigger, low)

    def test_normal_loop_names_exclusion_check_and_fog_reconsideration(self):
        """M013: the routine loop tells the architect to check accepted
        project-level exclusions before slicing and to reconsider only the
        `Not Yet Specified` concerns new evidence has clarified, at accepted
        boundaries. The card links the method instead of restating its contract;
        its budget stays guarded by test_line_and_word_limits."""
        loop = _section(self.text, "## Normal loop")
        self.assertTrue(loop.strip(), "card has no normal-loop section")
        for label, anchor in (
            ("exclusion register", "`Ruled Out`"),
            ("checked before slicing", "before slicing"),
            ("fog register", "`Not Yet Specified`"),
            ("accepted boundaries", "at accepted boundaries"),
            ("evidence-clarified only", "new evidence has clarified"),
            ("links the method", "docs/template_framework/method.md"),
        ):
            with self.subTest(loop=label):
                self.assertIn(anchor, loop, f"normal loop omits: {label}")
        # Progressive disclosure: the detailed doctrine stays in the method.
        low = self.text.lower()
        for copied in ("admission", "level 4", "resurrect", "needs_specification",
                       "empty frontier", "terminal register"):
            self.assertNotIn(
                copied, low, f"the card must not restate the method contract: {copied}"
            )

    def test_no_volatile_state_or_copied_profile_tables(self):
        low = self.text.lower()
        for reason in ("okf_yaml_invalid", "profile_yaml_out_of_subset",
                       "okf_parse_limit_exceeded", "profile_type_unsupported",
                       "profile_version_unsupported"):
            self.assertNotIn(reason, low)
        self.assertNotIn("schema_version", low)
        self.assertNotIn("coding prompt 0", low)   # no active prompt number
        self.assertNotIn("milestone m00", low)

    @unittest.skipUnless(_PYYAML, "PyYAML not installed")
    def test_type_aid_equals_registry_partition_and_excludes_reserved(self):
        registry = set(importlib.import_module("okf_yaml_profile").PROFILE_TYPE_REGISTRY)
        derived = registry - RESERVED_DOWNSTREAM
        self.assertTrue(RESERVED_DOWNSTREAM.issubset(registry))
        section = _section(self.text, "## Choose a template-owned type")
        aid_list = []
        for line in section.splitlines():
            s = line.strip()
            if (s.startswith("- Project knowledge:") or s.startswith("- Implementation loop:")
                    or s.startswith("- Delivery / framework:")):
                aid_list.extend(_ticks(line))
        aid = set(aid_list)
        # Exactly once: no duplicate entry, and cardinality equals the derived partition
        # (a removal shrinks the list, a duplicate makes list length exceed set length).
        self.assertEqual(len(aid_list), len(aid), "type aid must list each type exactly once")
        self.assertEqual(len(aid_list), len(derived))
        # Exact partition: a newly accepted template-owned type absent here would fail.
        self.assertEqual(aid, derived)
        self.assertFalse(aid & RESERVED_DOWNSTREAM)
        # Reserved types are named as package-owned, excluded from ordinary selection.
        section_ticks = set(_ticks(section))
        self.assertTrue(RESERVED_DOWNSTREAM.issubset(section_ticks))


class RoleEntryPointTests(unittest.TestCase):
    def test_architect_read_list_at_most_four_and_no_full_profile(self):
        text = (ROOT / "initialization" / "001_architect_reviewer_framework_initialization.md"
                ).read_text(encoding="utf-8")
        items = _numbered_items(_section(text, "## Read First"))
        self.assertLessEqual(len(items), 4)
        joined = " ".join(items)
        self.assertIn("PROJECT_STATE.md", joined)
        self.assertIn("architect_operating_card.md", joined)
        self.assertNotIn("okf_profile_v0_1.md", joined)  # full profile is not routine

    def test_coder_read_list_at_most_five_and_task_local(self):
        text = (ROOT / "initialization" / "002_coder_framework_initialization.md"
                ).read_text(encoding="utf-8")
        items = _numbered_items(_section(text, "## Read First"))
        self.assertLessEqual(len(items), 5)
        self.assertTrue(any("named by the prompt" in i for i in items))
        self.assertNotIn("okf_profile_v0_1.md", " ".join(items))

    def test_entry_points_link_card_without_copying(self):
        for rel in ("README.md", "docs/template_framework/human_user_manual.md",
                    "initialization/001_architect_reviewer_framework_initialization.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(entry=rel):
                self.assertIn(CARD_REL, text)              # links to the card
                self.assertNotIn("## Four OKF rules", text)  # does not copy the card body
                self.assertNotIn("Legacy or profile?", text)


if __name__ == "__main__":
    unittest.main()
