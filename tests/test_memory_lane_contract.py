"""Memory-lane contract checks (Plan 006/007 template-side alignment).

One authority model: `PROJECT_STATE.md` selects the memory mode; the typed
layout fields in `frutlups.layout.yaml` supply the governed paths; filesystem
presence is availability only; posture prose is never parsed for activation.
These tests pin that contract with text-based checks so the shipped template
cannot publish a contradictory or unsafe default. They must run without llloom
or frutlups installed.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Clone-only integrity checks: they protect the template as shipped and are
# scoped by the scaffold's own Status line, so a populated project reports them
# as skipped, never as failures.
SCAFFOLD_STATUS = "initialized template scaffold"


def _is_fresh_scaffold(state_path: Path = ROOT / "PROJECT_STATE.md") -> bool:
    """True only while PROJECT_STATE.md still carries the shipped Status."""
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Status:"):
            return line.split(":", 1)[1].strip() == SCAFFOLD_STATUS
    return False


_CLONE_ONLY = unittest.skipUnless(
    _is_fresh_scaffold(),
    "clone-only integrity check: PROJECT_STATE.md Status is no longer the shipped scaffold",
)

LAYOUT = ROOT / "frutlups.layout.yaml"
STATE = ROOT / "PROJECT_STATE.md"
CODING_TEMPLATE = ROOT / "prompts" / "templates" / "coding_prompt.md"
REVIEW_TEMPLATE = ROOT / "prompts" / "templates" / "review_prompt.md"
MEMORY_MODES = ROOT / "docs" / "template_framework" / "memory_modes.md"
POSTURE = ROOT / "05_governance" / "current" / "memory_posture.md"
INIT_ARCHITECT = ROOT / "initialization" / "003_architect_reviewer_llloom_initialization.md"
INIT_CODER = ROOT / "initialization" / "004_coder_llloom_initialization.md"
MANUAL = ROOT / "docs" / "template_framework" / "human_user_manual.md"

# Frozen by the accepted Frutlups M011-S01 contract; do not change one side alone.
FROZEN_MEMORY_ROOT = "llloom_memory"
FROZEN_POSTURE_FILE = "05_governance/current/memory_posture.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _llloom_lane_block(layout_text: str) -> str:
    """The `optional_lanes.llloom` block, ended by the next 2-space-indented key."""
    match = re.search(r"^optional_lanes:\n(.*?)(?=^\S)", layout_text, re.S | re.M)
    assert match, "layout has no optional_lanes block"
    lanes = match.group(1)
    lane = re.search(r"^  llloom:\n((?:    .*\n|\n)*)", lanes, re.M)
    assert lane, "optional_lanes has no llloom lane"
    return lane.group(1)


def _layout_list(layout_text: str, key: str) -> list[str]:
    match = re.search(rf"^  {key}:\n((?:    - .*\n)+)", layout_text, re.M)
    assert match, f"layout has no {key} list"
    return [line.strip()[len("- ") :].strip('"') for line in match.group(1).splitlines()]


def _headings(text: str) -> list[str]:
    return [line[len("## ") :].strip() for line in text.splitlines() if line.startswith("## ")]


def _section_body(text: str, heading: str) -> str:
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == f"## {heading}"]
    assert len(starts) == 1, f"expected exactly one '## {heading}' section, found {len(starts)}"
    body: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def _normalized(text: str) -> str:
    """Collapse all whitespace runs so phrase checks survive line wrapping."""
    return " ".join(text.split())


_BACKSLASH = chr(92)  # split so the machine-path scans never match this file


def _is_safe_repo_relative(value: str) -> bool:
    if not value or value != value.strip():
        return False
    if value.startswith(("/", _BACKSLASH, "~")) or _BACKSLASH in value:
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    return ".." not in value.split("/")


class MemoryLaneLayoutContractTests(unittest.TestCase):
    def test_layout_declares_frozen_llloom_keys(self) -> None:
        """The exact typed keys and shipped defaults exist under optional_lanes.llloom."""
        lane = _llloom_lane_block(_read(LAYOUT))
        self.assertIn('default_mode: "none"', lane)
        self.assertIn(f'memory_root: "{FROZEN_MEMORY_ROOT}"', lane)
        self.assertIn(f'posture_file: "{FROZEN_POSTURE_FILE}"', lane)

    def test_layout_paths_are_safe_repository_relative(self) -> None:
        lane = _llloom_lane_block(_read(LAYOUT))
        for key in ("memory_root", "posture_file"):
            match = re.search(rf'^    {key}: "([^"]*)"', lane, re.M)
            self.assertIsNotNone(match, f"llloom lane has no quoted {key}")
            value = match.group(1)
            self.assertTrue(
                _is_safe_repo_relative(value),
                f"{key} value {value!r} is not a safe repository-relative path",
            )

    def test_posture_file_key_matches_governance_section(self) -> None:
        """The lane's posture_file and the governance section name the same file."""
        text = _read(LAYOUT)
        self.assertIn(f'memory_posture: "{FROZEN_POSTURE_FILE}"', text)
        self.assertTrue((ROOT / FROZEN_POSTURE_FILE).is_file())

    @_CLONE_ONLY
    def test_project_state_default_memory_mode_is_none(self) -> None:
        lines = [line.strip() for line in _read(STATE).splitlines()]
        index = lines.index("Memory mode:")
        values = [line for line in lines[index + 1 :] if line]
        self.assertEqual(values[0], "- none", "shipped default must stay Memory mode: none")

    def test_project_state_has_no_memory_root_field(self) -> None:
        """Mode and path authority must not split: the state file never carries the root."""
        for line in _read(STATE).splitlines():
            self.assertNotRegex(line.strip(), r"(?i)^memory root\b")


class MemoryLaneGovernedPathTests(unittest.TestCase):
    def test_governed_paths_named_consistently(self) -> None:
        """Initialization, posture, modes doc, and local-state rails agree on the root."""
        for path, fragment in (
            (INIT_ARCHITECT, "optional_lanes.llloom.memory_root"),
            (INIT_ARCHITECT, FROZEN_MEMORY_ROOT),
            (INIT_CODER, "optional_lanes.llloom.memory_root"),
            (POSTURE, "optional_lanes.llloom.memory_root"),
            (POSTURE, "optional_lanes.llloom.posture_file"),
            (MEMORY_MODES, "optional_lanes.llloom.memory_root"),
            (MEMORY_MODES, "optional_lanes.llloom.posture_file"),
            (ROOT / ".gitignore", f"{FROZEN_MEMORY_ROOT}/"),
            (ROOT / "scripts" / "_local_state_common.py", f'"{FROZEN_MEMORY_ROOT}"'),
        ):
            self.assertIn(fragment, _read(path), f"{path.name} omits '{fragment}'")

    def test_initialization_splits_authority(self) -> None:
        """Owner-authorized initialization; observation never activates; no root in state."""
        architect = _read(INIT_ARCHITECT)
        self.assertIn("Never initialize the lane", architect)
        self.assertIn("availability", architect)
        self.assertIn("has no memory-root field", architect)
        self.assertNotIn("Record the path in:\n\n- `PROJECT_STATE.md`", architect)
        coder = _read(INIT_CODER)
        self.assertIn("read-only validation", coder)
        self.assertIn("Never initialize, repair", coder)

    def test_posture_mirrors_and_never_selects(self) -> None:
        posture = _read(POSTURE)
        self.assertIn("optional_lanes.llloom.posture_file", posture)
        self.assertIn("never selects the mode", posture)


class MemoryPostureScaffoldTests(unittest.TestCase):
    def test_scaffolds_have_one_memory_posture_section_in_order(self) -> None:
        coding = _headings(_read(CODING_TEMPLATE))
        self.assertEqual(coding.count("Memory Posture"), 1)
        self.assertLess(coding.index("Read First"), coding.index("Memory Posture"))
        self.assertLess(coding.index("Memory Posture"), coding.index("Task"))
        review = _headings(_read(REVIEW_TEMPLATE))
        self.assertEqual(review.count("Memory Posture"), 1)
        self.assertLess(review.index("Read First"), review.index("Memory Posture"))
        self.assertLess(review.index("Memory Posture"), review.index("Review Checks"))

    def test_memory_posture_sections_are_static(self) -> None:
        """No dynamic slot, no fence, no backend invocation, no duplicated posture path."""
        for template in (CODING_TEMPLATE, REVIEW_TEMPLATE):
            body = _section_body(_read(template), "Memory Posture")
            for line in body.splitlines():
                self.assertNotIn(
                    line.strip(), ("TBD", "- TBD", "`TBD`"),
                    f"{template.name} Memory Posture carries a slot-form line",
                )
            self.assertNotIn("```", body, "the section must stay fence-free")
            for invocation in ("llloom.exe", "--root", "." + _BACKSLASH + ".venv"):
                self.assertNotIn(invocation, body)
            self.assertNotIn(
                FROZEN_POSTURE_FILE, body,
                "posture path is routed via Read First, never duplicated in the section",
            )

    def test_required_section_lists_include_memory_posture_in_emitted_order(self) -> None:
        """Every required heading exists exactly once, in the configured order.

        Mirrors the frutlups scanner (`_required_section_errors`): exact
        spelling, exactly once, configured order — a missing required section
        must fail here, never pass by omission.
        """
        layout = _read(LAYOUT)
        for key, template in (
            ("required_coding_prompt_sections", CODING_TEMPLATE),
            ("required_review_prompt_sections", REVIEW_TEMPLATE),
        ):
            required = _layout_list(layout, key)
            self.assertIn("Memory Posture", required)
            self.assertEqual(
                required.index("Memory Posture"), required.index("Read First") + 1,
                f"{key} must place Memory Posture directly after Read First",
            )
            headings = _headings(_read(template))
            for name in required:
                self.assertEqual(
                    headings.count(name), 1,
                    f"{template.name} must carry required heading '{name}' exactly once",
                )
            emitted = [name for name in headings if name in required]
            self.assertEqual(
                emitted, required,
                f"{key} order/completeness drifts from {template.name}",
            )
            if key == "required_review_prompt_sections":
                # The review scaffold is fully owned by the configured list:
                # any extra heading is drift the renderer would carry silently.
                self.assertEqual(
                    headings, required,
                    f"{template.name} must carry exactly the configured "
                    "headings, no extras",
                )


# The exact owned-section slot map of the accepted frutlups renderer
# (`_coding_scaffold_slots` / `_review_scaffold_slots`): each owned section
# carries exactly one slot line of the given kind, and no slot-form line may
# appear anywhere else in the scaffold.
_CODING_SLOTS = {
    "Active Workspaces": "list",
    "Read First": "list",
    "Task": "prose",
    "Non-Goals": "list",
    "Verification": "list",
    "Self-Report": "path",
    "Definition Of Done": "list",
}
_REVIEW_SLOTS = {
    "Review Objective": "prose",
    "Read First": "list",
    "Verification": "list",
    "Non-Goals": "list",
    "Definition Of Done": "list",
}


def _slot_form(line: str) -> str:
    stripped = line.strip()
    if stripped == "- TBD":
        return "list"
    if stripped == "TBD":
        return "prose"
    if stripped == "`" + "TBD" + "`":
        return "path"
    return ""


def _section_map(text: str) -> dict[str, str]:
    """Map of `## ` heading -> body text, plus the pre-heading preamble at ""."""
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[len("## ") :].strip()
            assert current not in sections, f"duplicate heading {current!r}"
            sections[current] = []
        else:
            sections[current].append(line)
    return {name: "\n".join(body) for name, body in sections.items()}


class ConfiguredScaffoldSlotTests(unittest.TestCase):
    """Pin the slot forms the accepted frutlups renderer consumes."""

    def _assert_slots(self, template, owned: dict) -> None:
        sections = _section_map(_read(template))
        for name, body in sections.items():
            forms = [form for form in map(_slot_form, body.splitlines()) if form]
            if name in owned:
                self.assertEqual(
                    forms, [owned[name]],
                    f"{template.name} section {name!r} must carry exactly one "
                    f"{owned[name]} slot, found {forms}",
                )
            else:
                self.assertEqual(
                    forms, [],
                    f"{template.name} section {name!r} carries a stray slot form",
                )

    def test_coding_scaffold_slot_forms(self) -> None:
        self._assert_slots(CODING_TEMPLATE, _CODING_SLOTS)

    def test_review_scaffold_slot_forms(self) -> None:
        self._assert_slots(REVIEW_TEMPLATE, _REVIEW_SLOTS)

    def test_exactly_one_workflow_routing_region(self) -> None:
        """One fenced yaml block per scaffold, carrying the milestone/slice slots."""
        for template in (CODING_TEMPLATE, REVIEW_TEMPLATE):
            text = _read(template)
            blocks = re.findall(r"^```yaml\n(.*?)^```$", text, re.S | re.M)
            self.assertEqual(
                len(blocks), 1, f"{template.name} must have exactly one yaml block"
            )
            self.assertEqual(text.count("```"), 2, f"{template.name} has extra fences")
            for field in ("milestone: TBD", "slice: TBD"):
                self.assertEqual(
                    blocks[0].count(field), 1,
                    f"{template.name} workflow block needs exactly one '{field}'",
                )


class MemoryAuthorityDoctrineTests(unittest.TestCase):
    def test_identifier_authority_doctrine_present(self) -> None:
        modes = _read(MEMORY_MODES)
        self.assertIn("routing identifiers only", modes)
        self.assertIn("memory-update slice", modes)
        self.assertIn(
            "milestone and slice identifiers never grant",
            _section_body(_read(CODING_TEMPLATE), "Memory Posture"),
        )
        self.assertIn(
            "milestone and slice identifiers",
            _section_body(_read(REVIEW_TEMPLATE), "Memory Posture"),
        )

        # Every governed lane surface must name BOTH mutation authorities: an
        # explicitly assigned memory-update slice AND direct human-owner
        # authority. A slice-only rule would wrongly reject owner-directed
        # mutation (review finding, note 018 P0/P1).
        surfaces = {
            MEMORY_MODES.name: _read(MEMORY_MODES),
            POSTURE.name: _read(POSTURE),
            "coding Memory Posture": _section_body(
                _read(CODING_TEMPLATE), "Memory Posture"
            ),
            "review Memory Posture": _section_body(
                _read(REVIEW_TEMPLATE), "Memory Posture"
            ),
            INIT_ARCHITECT.name: _read(INIT_ARCHITECT),
            INIT_CODER.name: _read(INIT_CODER),
            MANUAL.name: _read(MANUAL),
        }
        for name, text in surfaces.items():
            normalized = _normalized(text)
            for phrase in ("memory-update slice", "direct human-owner authority"):
                self.assertIn(
                    phrase, normalized,
                    f"{name} must name the mutation authority {phrase!r}",
                )

    def test_no_identifier_derived_memory_convention(self) -> None:
        """`M010` stays an ordinary identifier: it may appear only in the doctrine
        sentence that denies it special meaning."""
        for directory in ("docs", "initialization", "prompts", "05_governance"):
            for path in (ROOT / directory).rglob("*.md"):
                if "M010" in _read(path) and path != MEMORY_MODES:
                    self.fail(f"{path} names M010 outside the doctrine denial")


if __name__ == "__main__":
    unittest.main()
