"""Slice prompt contract v1: fixtures, reference checker, scaffolds, the single
canonical vocabulary declaration, the dispatch preflight rules, the old-consumer
fence composition, and the pre-launch audit's drive-grammar reader.

Losslessness is equality, not parsing: a rendered prompt carries its sidecar
entry verbatim in a fenced YAML block, and the checker compares that block with
the attempt-resolved entry. The tests mutate every leaf of the block and assert
refusal. No test parses Markdown prose for field values or CommonMark fences.

Stdlib-only structure tests always run. Tests that evaluate fixtures through
the reference checker need PyYAML (the declared dependency) and are skipped
when it is absent, exactly like the OKF profile-checker tests. Two tests use
external evidence when available: `FRUTLUPS_0_1_8_PYTHON` (released legacy
consumer) and `FRUTLUPS_DRIVE_SRC` (the drive's own manifest loader).
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX_ROOT = ROOT / "tests" / "fixtures" / "slice_contract"
MANIFEST = FIX_ROOT / "manifest.json"
LAYOUT = ROOT / "frutlups.layout.yaml"
CONTRACT_DOC = ROOT / "docs" / "template_framework" / "slice_prompt_contract.md"
LEGACY_SCAFFOLD = ROOT / "prompts" / "templates" / "coding_prompt.md"
V1_SCAFFOLD = ROOT / "prompts" / "templates" / "coding_prompt_contract_v1.md"
CHECKER = ROOT / "scripts" / "slice_contract_check.py"
OPTIN = FIX_ROOT / "optin_project_for_old_consumer"

try:  # the declared dependency; only the checker-driven tests need it
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:  # pragma: no cover
    HAVE_YAML = False

MACHINE_FRAGMENTS = ("C:" + "\\Users\\dev", "repos" + "_dev", "/Users/", "/home/")
SLOT_RE = re.compile(r"TBD:[a-z_]+")
EXPECTED_V1_SECTION_ORDER = [
    "Current State", "Active Workspaces", "Read First", "Memory Posture", "Task",
    "Implementation Discipline", "OKF Authoring", "Write Manifest", "Opening Gates",
    "External Repositories", "Correction Scope Map", "Candidate Identity",
    "Execution Envelope", "Objective And Closure Proof", "Non-Goals", "Verification",
    "Seat Conduct", "Self-Report", "Definition Of Done", "Typed Entry",
]
LEGACY_REQUIRED = [
    "Current State", "Active Workspaces", "Read First", "Memory Posture", "Task",
    "Non-Goals", "Verification", "Self-Report", "Definition Of Done",
]
VOCABULARY_KEYS = (
    "entry_status_values", "authored_by_values", "artifact_types", "role_owners",
    "retry_policies", "gate_kinds", "cleanup_values", "result_handling_values",
    "objective_status_values", "sentinels",
)


def _scripts_module(name: str):
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module(name)


def _headings(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def _layout_block_text() -> str:
    text = LAYOUT.read_text(encoding="utf-8")
    start = text.index("\nslice_prompt_contract:\n")
    end = text.index("\ntemplate_owned_surfaces:\n")
    return text[start:end]


def _doc_table(doc: str, first_header: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    lines = doc.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"| {first_header} |"):
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                key = re.findall(r"`([^`]+)`", cells[0])
                if key:
                    rows[key[0]] = re.findall(r"`([^`]+)`", cells[1])
            break
    return rows


def _section(doc: str, heading: str) -> str:
    start = doc.index(heading)
    nxt = doc.find("\n## ", start + 1)
    return doc[start:nxt if nxt != -1 else None]


def _typed_block(rendered: str) -> tuple[str, str, str]:
    """(head, block_text, tail) around the single ```yaml block of the Typed Entry section."""
    i = rendered.index("## Typed Entry")
    head, section = rendered[:i], rendered[i:]
    lines = section.split("\n")
    o = lines.index("```yaml")
    c = lines.index("```", o + 1)
    return head + "\n".join(lines[:o + 1]) + "\n", "\n".join(lines[o + 1:c]), "\n" + "\n".join(lines[c:])


class SliceContractFixtureManifestTests(unittest.TestCase):
    """Stdlib-only: the fixture corpus is inventoried, digest-pinned, and clean."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.fixtures = cls.manifest["fixtures"]

    def test_manifest_schema(self) -> None:
        self.assertEqual(self.manifest["manifest_schema"], "slice_contract_fixture_manifest")
        self.assertEqual(self.manifest["contract_version"], 1)
        self.assertEqual(self.manifest["layout"], "frutlups.layout.yaml")
        self.assertEqual(self.manifest["checker"], "scripts/slice_contract_check.py")
        self.assertEqual(set(self.manifest["modes"]), {"sidecar", "align", "render", "review", "document", "external"})

    def test_ids_unique_sorted_and_shapes_valid(self) -> None:
        ids = [f["id"] for f in self.fixtures]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 100)
        for f in self.fixtures:
            with self.subTest(fixture=f["id"]):
                self.assertIn(f["mode"], self.manifest["modes"])
                self.assertIn(f["expected"]["result"], ("pass", "fail", "legacy", "old_consumer_refusal"))
                self.assertEqual(f["expected"]["codes"], sorted(set(f["expected"]["codes"])))
                self.assertEqual(bool(f["expected"]["codes"]), f["expected"]["result"] == "fail")

    def test_inventory_complete_both_directions_and_digests_match(self) -> None:
        listed = {(ROOT / f["path"]).resolve() for f in self.fixtures}
        on_disk = {p.resolve() for p in FIX_ROOT.rglob("*") if p.is_file() and p.name != "manifest.json" and "__pycache__" not in p.parts}
        self.assertEqual(on_disk - listed, set(), "fixtures on disk absent from manifest")
        self.assertEqual(listed - on_disk, set(), "manifest paths absent on disk")
        for f in self.fixtures:
            with self.subTest(fixture=f["id"]):
                digest = hashlib.sha256((ROOT / f["path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, f["sha256"], "fixture bytes drifted from the pinned digest")

    def test_fixtures_are_utf8_lf_single_trailing_newline_and_free_of_machine_paths(self) -> None:
        for f in self.fixtures:
            with self.subTest(fixture=f["id"]):
                raw = (ROOT / f["path"]).read_bytes()
                text = raw.decode("utf-8")
                self.assertNotIn(b"\r\n", raw)
                if not f["path"].endswith(".py"):
                    self.assertTrue(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "exactly one trailing newline")
                for fragment in MACHINE_FRAGMENTS:
                    self.assertNotIn(fragment, text)

    def test_every_content_reason_code_has_a_fixture(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        reason = re.search(r"REASON_CODES = \((.*?)\n\)", source, re.DOTALL).group(1)
        codes = set(re.findall(r'"([a-z_]+)"', reason))
        covered = {c for f in self.fixtures for c in f["expected"]["codes"]}
        self.assertEqual(codes - covered, set(), "content reason codes without a fixture")
        self.assertEqual(covered - codes, set(), "fixtures expecting a code the inventory does not declare")

    def test_every_emitted_code_is_inventoried(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        reason = set(re.findall(r'"([a-z_]+)"', re.search(r"REASON_CODES = \((.*?)\n\)", source, re.DOTALL).group(1)))
        env = set(re.findall(r'"([a-z_]+)"', re.search(r"ENVIRONMENT_CODES = \((.*?)\n\)", source, re.DOTALL).group(1)))
        emitted = set(re.findall(r'(?:Diagnostic|err)\(\s*"([a-z_]+)"', source))
        self.assertEqual(emitted - (reason | env), set(), "emitted codes outside the inventory")
        self.assertEqual(reason & env, set())

    def test_contract_doc_lists_exactly_the_inventoried_codes(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        reason = set(re.findall(r'"([a-z_]+)"', re.search(r"REASON_CODES = \((.*?)\n\)", source, re.DOTALL).group(1)))
        env = set(re.findall(r'"([a-z_]+)"', re.search(r"ENVIRONMENT_CODES = \((.*?)\n\)", source, re.DOTALL).group(1)))
        doc = _section(CONTRACT_DOC.read_text(encoding="utf-8"), "## 10. Validity Rules")
        listed = set(re.findall(r"`([a-z_]+)`", doc.split("Sentinels (layout")[0]))
        self.assertEqual(listed, reason | env)

    def test_no_markdown_grammar_or_fence_parsing_remains(self) -> None:
        """The reassessed method: no prose field extraction, no CommonMark fence reader."""
        checker = CHECKER.read_text(encoding="utf-8")
        preflight = (ROOT / "scripts" / "artifact_integrity_preflight.py").read_text(encoding="utf-8")
        for forbidden in ("extract_rendered", "fenced_lines", "FENCE_RE", "_bullets(", "_table_rows(", "Extracted("):
            self.assertNotIn(forbidden, checker, forbidden)
        self.assertNotIn("WORKFLOW_FENCE_RE", preflight)


class SliceContractScaffoldTests(unittest.TestCase):
    """Stdlib-only: two scaffolds, legacy byte-identical, v1 fully slotted."""

    def test_legacy_scaffold_digest_is_pinned_in_the_contract_doc(self) -> None:
        doc = CONTRACT_DOC.read_text(encoding="utf-8")
        match = re.search(r"Legacy scaffold digest: `([0-9a-f]{64})`", doc)
        self.assertIsNotNone(match)
        actual = hashlib.sha256(LEGACY_SCAFFOLD.read_bytes()).hexdigest()
        self.assertEqual(actual, match.group(1), "legacy scaffold bytes changed; update the pin deliberately")

    def test_layout_still_configures_the_legacy_scaffold(self) -> None:
        text = LAYOUT.read_text(encoding="utf-8")
        self.assertIn('coding_template: "prompts/templates/coding_prompt.md"', text)
        self.assertIn('scaffold: "prompts/templates/coding_prompt_contract_v1.md"', text)
        self.assertIn('legacy_scaffold: "prompts/templates/coding_prompt.md"', text)
        self.assertEqual(text.count("sidecar_suffix"), 1, "one suffix authority only")
        self.assertNotIn("oracle_content_bound_bytes", text)
        self.assertIn('    - "Typed Entry"\n', text)
        self.assertIn("  rendered_section_order:\n", text)

    def test_v1_scaffold_section_order_and_slots(self) -> None:
        text = V1_SCAFFOLD.read_text(encoding="utf-8")
        self.assertEqual(_headings(text), EXPECTED_V1_SECTION_ORDER)
        legacy_positions = [EXPECTED_V1_SECTION_ORDER.index(h) for h in LEGACY_REQUIRED]
        self.assertEqual(legacy_positions, sorted(legacy_positions))
        slots = set(SLOT_RE.findall(text))
        for slot in (
            "TBD:milestone", "TBD:slice", "TBD:title", "TBD:authored_by", "TBD:mode",
            "TBD:strictness", "TBD:live", "TBD:corrective", "TBD:attempt", "TBD:status",
            "TBD:dispatch_authority", "TBD:task", "TBD:active_workspaces", "TBD:read_first",
            "TBD:write_manifest_rows", "TBD:opening_gates", "TBD:external_input_rows",
            "TBD:correction_rows", "TBD:controlling_ruling", "TBD:candidate_strategy",
            "TBD:hard_wall_seconds", "TBD:local_output_root", "TBD:objective_success_criteria",
            "TBD:non_goals", "TBD:verification", "TBD:self_report_path", "TBD:definition_of_done",
            "TBD:typed_entry",
        ):
            self.assertIn(slot, slots)
        section = text[text.index("## Typed Entry"):]
        self.assertEqual(section.count("```yaml\nTBD:typed_entry\n```"), 1)
        for phrase in ("fills or deletes", "delete this section"):
            self.assertNotIn(phrase, text.lower())

    def test_canonical_renderings_carry_no_slot_or_residue(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        names = [f["path"] for f in manifest["fixtures"] if f["mode"] == "render" and f["expected"]["result"] == "pass" and "prose-not-authority" not in f["tags"]]
        self.assertGreaterEqual(len(names), 4)
        for path in names:
            with self.subTest(fixture=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertNotIn("TBD", text)
                self.assertNotIn("{attempt}", text)
                self.assertNotIn("Conditional:", text)
                self.assertEqual(len(_headings(text)), len(set(_headings(text))))


@unittest.skipUnless(HAVE_YAML, "PyYAML is required to evaluate fixtures through the checker")
class SliceContractCheckerTests(unittest.TestCase):
    """The reference checker reproduces every fixture and refuses every mutation."""

    @classmethod
    def setUpClass(cls) -> None:
        import yaml
        cls.yaml = yaml
        cls.check = _scripts_module("slice_contract_check")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.layout, diags = cls.check.load_layout_contract(LAYOUT)
        assert cls.layout is not None, diags
        cls.positive = yaml.safe_load((FIX_ROOT / "all_fields.slices.yaml").read_text(encoding="utf-8"))

    def _argv(self, fixture: dict) -> list[str] | None:
        mode, args = fixture["mode"], fixture["args"]
        base = ["--root", str(ROOT), "--json"]
        if mode == "sidecar":
            return base + ["--sidecar", str(ROOT / fixture["path"])]
        if mode == "align":
            argv = list(base)
            for s in args["sidecars"]:
                argv += ["--sidecar", str(FIX_ROOT / s)]
            return argv
        if mode == "render":
            argv = base + ["--sidecar", str(FIX_ROOT / args["sidecar"]), "--slice", args["slice"], "--rendered", str(ROOT / fixture["path"])]
            if "attempt" in args:
                argv += ["--attempt", str(args["attempt"])]
            return argv
        if mode == "review":
            return base + ["--review-report", str(ROOT / fixture["path"])]
        return None

    def _run(self, argv: list[str]) -> tuple[int, dict]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.check.main(argv)
        return code, json.loads(out.getvalue())

    def test_every_fixture_reproduces_its_expected_result_and_codes(self) -> None:
        for fixture in self.manifest["fixtures"]:
            argv = self._argv(fixture)
            if argv is None:
                continue
            with self.subTest(fixture=fixture["id"]):
                code, result = self._run(argv)
                self.assertEqual(result["schema"], "template.slice_contract_check.v1")
                self.assertEqual(result["result"], fixture["expected"]["result"])
                self.assertEqual(code, 0 if fixture["expected"]["result"] == "pass" else 1)
                codes = sorted({d["code"] for d in result["diagnostics"]})
                self.assertEqual(codes, fixture["expected"]["codes"])

    @staticmethod
    def _key_paths(value, path=()):
        if isinstance(value, dict):
            for k, v in value.items():
                yield path + (k,)
                yield from SliceContractCheckerTests._key_paths(v, path + (k,))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from SliceContractCheckerTests._key_paths(v, path + (i,))

    @staticmethod
    def _delete(doc, path):
        target = doc
        for step in path[:-1]:
            target = target[step]
        if isinstance(target, list):
            target.pop(path[-1])
        else:
            del target[path[-1]]

    @staticmethod
    def _alter(doc, path):
        target = doc
        for step in path[:-1]:
            target = target[step]
        value = target[path[-1]]
        if isinstance(value, bool):
            target[path[-1]] = not value
        elif isinstance(value, (int, float)):
            target[path[-1]] = value + 1
        elif isinstance(value, str):
            target[path[-1]] = value + "X"
        else:
            return False
        return True

    def test_deleting_every_key_path_refuses(self) -> None:
        for index in (0, 1):
            entry = self.positive["slices"][index]
            for path in list(self._key_paths(entry)):
                with self.subTest(slice=entry["slice"], path=".".join(map(str, path))):
                    mutated = copy.deepcopy(self.positive)
                    self._delete(mutated["slices"][index], path)
                    diags = self.check.validate_sidecar(mutated, "x", self.layout, sidecar_path=FIX_ROOT / "all_fields.slices.yaml")
                    self.assertTrue(diags, f"deleting {path} was accepted")

    def _canonical_renderings(self):
        for f in self.manifest["fixtures"]:
            if f["mode"] == "render" and f["expected"]["result"] == "pass" and "prose-not-authority" not in f["tags"]:
                doc = self.yaml.safe_load((FIX_ROOT / f["args"]["sidecar"]).read_text(encoding="utf-8"))
                yield f["id"], doc, f["args"]["slice"], (ROOT / f["path"]).read_text(encoding="utf-8")

    def test_typed_entry_mutations_refuse_for_every_leaf_of_every_canonical_rendering(self) -> None:
        count = 0
        for fid, doc, slice_id, rendered in self._canonical_renderings():
            count += 1
            self.assertEqual(self.check.check_rendered(doc, slice_id, None, rendered, fid, self.layout), [])
            head, block, tail = _typed_block(rendered)
            typed = self.yaml.safe_load(block)
            entry = next(s for s in doc["slices"] if s["slice"] == slice_id)
            self.assertEqual(typed, self.check.resolve_entry(entry, self.layout["attempt_token"], entry.get("attempt")))
            for path in list(self._key_paths(typed)):
                for mutation in ("delete", "alter"):
                    mutated = copy.deepcopy(typed)
                    if mutation == "delete":
                        self._delete(mutated, path)
                    elif not self._alter(mutated, path):
                        continue
                    text = head + self.yaml.safe_dump(mutated, sort_keys=False, allow_unicode=True).rstrip("\n") + tail
                    with self.subTest(fixture=fid, path=".".join(map(str, path)), mutation=mutation):
                        codes = {d.code for d in self.check.check_rendered(doc, slice_id, None, text, fid, self.layout)}
                        self.assertIn("typed_entry_mismatch", codes)
            with self.subTest(fixture=fid, mutation="second block"):
                text = rendered.rstrip("\n") + "\n\n```yaml\n" + block + "\n```\n"
                codes = {d.code for d in self.check.check_rendered(doc, slice_id, None, text, fid, self.layout)}
                self.assertIn("typed_entry_ambiguous", codes)
            with self.subTest(fixture=fid, mutation="undeclared key"):
                text = head + block + "\nundeclared_key: value" + tail
                codes = {d.code for d in self.check.check_rendered(doc, slice_id, None, text, fid, self.layout)}
                self.assertIn("typed_entry_mismatch", codes)
        self.assertGreaterEqual(count, 4, "the manifest enumerates at least four canonical renderings")

    def test_layout_section_order_equals_the_scaffold_and_covers_every_section(self) -> None:
        order = list(self.layout["rendered_section_order"])
        self.assertEqual(order, _headings(V1_SCAFFOLD.read_text(encoding="utf-8")))
        self.assertEqual(set(order), set(self.layout["rendered_sections_required"]) | set(self.layout["rendered_sections_conditional"]))
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(order[-1], "Typed Entry")

    def _preflight_codes(self, text: str) -> set[str]:
        preflight = _scripts_module("artifact_integrity_preflight")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "prompt.md").write_text(text, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                preflight.main(["--root", str(root), "prompt.md"])
        return set(re.findall(r"^ERROR (\S+)", out.getvalue(), re.MULTILINE))

    def test_status_spellings_cannot_conceal_disagreement_in_either_direction(self) -> None:
        """Round-4 R4-F1: every YAML spelling of the carrier's status that still
        loads equal must refuse when the workflow metadata disagrees, in the
        checker (specific codes, no typed_entry_mismatch) and in the preflight."""
        frozen_doc = self.yaml.safe_load((FIX_ROOT / "frozen_entry_valid.slices.yaml").read_text(encoding="utf-8"))
        frozen = (FIX_ROOT / "frozen_entry_rendered_m001_s01.md").read_text(encoding="utf-8")
        routine = (FIX_ROOT / "all_fields_rendered_m001_s01.md").read_text(encoding="utf-8")
        cases = (("frozen->ready", frozen_doc, frozen, "frozen", "ready"), ("ready->frozen", self.positive, routine, "ready", "frozen"))
        for label, doc, rendered, real, fake in cases:
            head, block, tail = _typed_block(rendered)
            self.assertEqual(self.check.check_rendered(doc, "M001-S01", None, rendered, label, self.layout), [])
            metadata_swapped = head.replace(f"status: {real}\n", f"status: {fake}\n", 1)
            typed = self.yaml.safe_load(block)
            spellings = {
                "single-quoted": block.replace(f"status: {real}\n", f"status: '{real}'\n"),
                "double-quoted": block.replace(f"status: {real}\n", f'status: "{real}"\n'),
                "tagged": block.replace(f"status: {real}\n", f"status: !!str {real}\n"),
                "block scalar": block.replace(f"status: {real}\n", f"status: |-\n  {real}\n"),
                "flow mapping": self.yaml.safe_dump(typed, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10 ** 6).rstrip("\n"),
                "plain (metadata only)": block,
            }
            for name, mutated in spellings.items():
                with self.subTest(direction=label, spelling=name):
                    self.assertEqual(self.yaml.safe_load(mutated), typed, "the spelling must still load equal: that is the concealment shape")
                    text = metadata_swapped + mutated + tail
                    codes = {d.code for d in self.check.check_rendered(doc, "M001-S01", None, text, label, self.layout)}
                    self.assertIn("rendered_status_disagreement", codes)
                    self.assertNotIn("typed_entry_mismatch", codes)
                    if name != "plain (metadata only)":
                        self.assertIn("typed_entry_status_line", codes)
                    self.assertIn("status_ambiguous", self._preflight_codes(text))
            with self.subTest(direction=label, spelling="agreeing, plain"):
                self.assertNotIn("status_ambiguous", self._preflight_codes(rendered))

    def test_write_manifest_and_self_report_are_exact_by_cardinality(self) -> None:
        rendered = (FIX_ROOT / "all_fields_rendered_m001_s01.md").read_text(encoding="utf-8")
        declared = "| 08_pkg/tests/test_route_cost.py | test | coder | create_once |\n"
        self_report = "`05_governance/reviews/m001/m001_s01_route_cost_ledger_self_report.md`\n"
        probes = {
            "extra row (reviewer's probe)": (rendered.replace(declared, declared + "| 03_experiments/active_roadmap.md | analysis | coder | append_only |\n", 1), {"rendered_manifest_row_undeclared"}, {"rendered_manifest_row_missing"}),
            "duplicate row": (rendered.replace(declared, declared + declared, 1), {"rendered_manifest_row_undeclared"}, {"rendered_manifest_row_missing"}),
            "removed row": (rendered.replace(declared, "", 1), {"rendered_manifest_row_missing"}, {"rendered_manifest_row_undeclared"}),
            "replaced cell": (rendered.replace(declared, declared.replace("create_once", "modify"), 1), {"rendered_manifest_row_missing", "rendered_manifest_row_undeclared"}, set()),
            "second self-report line": (rendered.replace(self_report, self_report + "\n`05_governance/reviews/m001/other.md`\n", 1), {"rendered_self_report_path_undeclared"}, {"rendered_self_report_path_missing"}),
            "duplicated self-report line (R5-F1)": (rendered.replace(self_report, self_report + "\n" + self_report, 1), {"rendered_self_report_path_undeclared"}, {"rendered_self_report_path_missing"}),
            "self-report line removed": (rendered.replace(self_report, "", 1), {"rendered_self_report_path_missing"}, {"rendered_self_report_path_undeclared"}),
        }
        for label, (text, expected, absent) in probes.items():
            with self.subTest(probe=label):
                codes = {d.code for d in self.check.check_rendered(self.positive, "M001-S01", None, text, label, self.layout)}
                self.assertTrue(expected <= codes, f"{expected} not in {codes}")
                self.assertFalse(absent & codes, f"{absent & codes} emitted unexpectedly")

    def test_section_order_is_enforced_for_every_canonical_rendering(self) -> None:
        count = 0
        for fid, doc, slice_id, rendered in self._canonical_renderings():
            count += 1
            headings = _headings(rendered)
            lines = rendered.split("\n")
            last = lines.index(f"## {headings[-1]}")
            first = lines.index(f"## {headings[0]}")
            moved = "\n".join(lines[:first] + lines[last:] + [""] + lines[first:last]).rstrip("\n") + "\n"
            with self.subTest(fixture=fid, mutation="last section first"):
                codes = {d.code for d in self.check.check_rendered(doc, slice_id, None, moved, fid, self.layout)}
                self.assertEqual(codes, {"rendered_section_order"})
        self.assertGreaterEqual(count, 4)

    def test_pipe_and_newline_bearing_scalars_round_trip_through_the_carrier(self) -> None:
        doc = copy.deepcopy(self.positive)
        entry = doc["slices"][1]
        entry["external_inputs"][0]["repository"] = "repo|name with `ticks`"
        entry["task"] = "line one | pipe\nline two\n"
        rendered = (FIX_ROOT / "all_fields_rendered_m002_s02_attempt_002.md").read_text(encoding="utf-8")
        head, _block, tail = _typed_block(rendered)
        resolved = self.check.resolve_entry(entry, self.layout["attempt_token"], entry["attempt"])
        text = head + self.yaml.safe_dump(resolved, sort_keys=False, allow_unicode=True).rstrip("\n") + tail
        codes = {d.code for d in self.check.check_rendered(doc, "M002-S02", None, text, "x", self.layout)}
        self.assertNotIn("typed_entry_mismatch", codes)

    def test_confirming_a_different_attempt_is_refused(self) -> None:
        rendered = (FIX_ROOT / "all_fields_rendered_m002_s02_attempt_002.md").read_text(encoding="utf-8")
        codes = {d.code for d in self.check.check_rendered(self.positive, "M002-S02", "001", rendered, "x", self.layout)}
        self.assertIn("attempt_mismatch", codes)
        self.assertEqual(self.check.check_rendered(self.positive, "M002-S02", "002", rendered, "x", self.layout), [])

    def test_reviewer_sidecar_probes_refuse(self) -> None:
        base = FIX_ROOT / "all_fields.slices.yaml"
        for label, mutate, code in (
            ("roadmap unresolved", lambda d: d.update(roadmap="absent_roadmap.md"), "roadmap_link_unresolved"),
            ("attempt 000", lambda d: d["slices"][1].update(attempt="000"), "attempt_format"),
            ("external input without path", lambda d: d["slices"][1]["external_inputs"][0].pop("path"), "external_input_invalid"),
            ("output root escapes", lambda d: d["slices"][1]["execution_envelope"].update(local_output_root="local_state/../06_infra/attempt_{attempt}/"), "local_output_root_outside_local_state"),
            ("absolute dispatch authority", lambda d: d["slices"][0].update(dispatch_authority="C:/outside/authority.md"), "authority_path_invalid"),
        ):
            with self.subTest(probe=label):
                mutated = copy.deepcopy(self.positive)
                mutate(mutated)
                codes = {d.code for d in self.check.validate_sidecar(mutated, "x", self.layout, sidecar_path=base)}
                self.assertIn(code, codes)

    def test_review_report_rules_are_section_local_and_line_based(self) -> None:
        report = (FIX_ROOT / "review_report_closure_valid.md").read_text(encoding="utf-8")
        probe = report.replace("## Closure Decision", "```a`b\nObjective status: achieved\nObjective evidence: not authority\n```text\nexample\n```\n\n## Closure Decision")
        self.assertEqual(self.check.check_review_report(probe, "x", self.layout), [])
        quoted = report.replace("## Findings\n", "## Findings\n\n```markdown\n## Verdict\n```\n")
        self.assertIn("verdict_section_duplicate", {d.code for d in self.check.check_review_report(quoted, "x", self.layout)})

    def test_checker_output_is_deterministic_and_ordered(self) -> None:
        argv = ["--root", str(ROOT), "--json", "--sidecar", str(FIX_ROOT / "governance_record_label_on_reserved_path.slices.yaml")]
        outputs = [self._run(argv)[1] for _ in range(2)]
        self.assertEqual(outputs[0], outputs[1])
        keys = [(d["path"], d["location"], d["code"], d["message"]) for d in outputs[0]["diagnostics"]]
        self.assertEqual(keys, sorted(keys))

    def test_contract_doc_tables_equal_the_layout_in_both_directions(self) -> None:
        doc = CONTRACT_DOC.read_text(encoding="utf-8")
        vocab = _doc_table(doc, "Vocabulary")
        self.assertEqual(set(vocab), set(VOCABULARY_KEYS))
        for key in VOCABULARY_KEYS:
            with self.subTest(vocabulary=key):
                self.assertEqual(vocab[key], list(self.layout[key]))
        matrix = _doc_table(doc, "Role")
        self.assertEqual(set(matrix), set(self.layout["role_type_matrix"]))
        for role, types in self.layout["role_type_matrix"].items():
            with self.subTest(role=role):
                self.assertEqual(matrix[role], list(types))
                self.assertTrue(set(types) <= set(self.layout["artifact_types"]))
        self.assertEqual(set(self.layout["role_type_matrix"]), set(self.layout["role_owners"]))
        for reserved in ("review_report", "verdict_record", "acceptance_record", "routing_state", "review_prompt"):
            self.assertNotIn(reserved, self.layout["role_type_matrix"]["coder"])
        self.assertIn("review_prompt", self.layout["role_type_matrix"]["reviewer"])

    def test_layout_block_lists_only_one_declaration_of_each_vocabulary(self) -> None:
        block = _layout_block_text()
        for key in VOCABULARY_KEYS:
            self.assertEqual(block.count(f"{key}:"), 1, key)

    def test_environment_codes_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_layout = Path(tmp) / "frutlups.layout.yaml"
            bad_layout.write_text("x: 1\n", encoding="utf-8")
            layout, diags = self.check.load_layout_contract(bad_layout)
            self.assertIsNone(layout)
            self.assertEqual([d.code for d in diags], ["layout_contract_block_missing"])
            code, result = self._run(["--root", str(ROOT), "--json", "--sidecar", str(Path(tmp) / "missing.slices.yaml")])
            self.assertEqual(code, 1)
            self.assertEqual({d["code"] for d in result["diagnostics"]}, {"sidecar_unreadable"})
        codes = {d.code for d in self.check.check_rendered(self.positive, "M009-S09", None, "", "x", self.layout)}
        self.assertEqual(codes, {"slice_not_found"})

    def test_roadmap_link_must_be_an_ordinary_adjacent_file(self) -> None:
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "elsewhere").mkdir()
            outside = root / "elsewhere" / "roadmap.md"
            outside.write_text("# elsewhere\n", encoding="utf-8")
            beside = root / "active_roadmap.md"
            shutil.copyfile(FIX_ROOT / "all_fields.slices.yaml", root / "all_fields.slices.yaml")
            try:
                os.symlink(outside, beside)
            except (OSError, NotImplementedError):
                self.skipTest("external evidence: file symlink creation is not permitted on this seat")
            codes = {d.code for d in self.check.validate_sidecar(self.positive, "x", self.layout, sidecar_path=root / "all_fields.slices.yaml")}
            self.assertIn("roadmap_link_unresolved", codes)

    def test_roadmap_directory_junction_is_refused(self) -> None:
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target_dir").mkdir()
            link = root / "active_roadmap.md"
            proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(root / "target_dir")], capture_output=True, text=True)
            if proc.returncode != 0 or not link.exists():
                self.skipTest("external evidence: junction creation unavailable on this seat")
            shutil.copyfile(FIX_ROOT / "all_fields.slices.yaml", root / "all_fields.slices.yaml")
            codes = {d.code for d in self.check.validate_sidecar(self.positive, "x", self.layout, sidecar_path=root / "all_fields.slices.yaml")}
            self.assertIn("roadmap_link_unresolved", codes)


class ReadyPromptPreflightTests(unittest.TestCase):
    """The artifact preflight enforces the dispatch placeholder policy with a
    total, line-based status rule: every `status:` line must agree."""

    def _run(self, body: str) -> tuple[int, str]:
        preflight = _scripts_module("artifact_integrity_preflight")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "prompt.md").write_text(body, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = preflight.main(["--root", str(root), "prompt.md"])
        return code, out.getvalue()

    @staticmethod
    def _prompt(status: str, body: str) -> str:
        return f"# P\n\n```yaml\nmilestone: M001\nslice: M001-S01\nstatus: {status}\n```\n\n## Task\n\n{body}\n"

    def test_ready_prompt_with_sentinel_is_an_error(self) -> None:
        for sentinel in ("TBD", "<value>", "<path>", "<one move>"):
            with self.subTest(sentinel=sentinel):
                code, out = self._run(self._prompt("ready", f"Do the thing {sentinel}."))
                self.assertEqual(code, 1)
                self.assertIn("ready_tbd", out)

    def test_ready_prompt_with_deleted_section_residue_is_an_error(self) -> None:
        code, out = self._run(self._prompt("ready", "Do the thing.\n\n## Opening Gates\n\n*Conditional: rendered only when the entry declares gates.*"))
        self.assertEqual(code, 1)
        self.assertIn("ready_optional_section_residue", out)

    def test_frozen_and_draft_prompts_may_carry_placeholders(self) -> None:
        for status in ("frozen", "draft"):
            with self.subTest(status=status):
                _, out = self._run(self._prompt(status, "TBD"))
                self.assertNotIn("ready_tbd", out)
                self.assertNotIn("ready_optional_section_residue", out)

    def test_agreeing_status_lines_are_one_status(self) -> None:
        code, out = self._run(self._prompt("ready", "Implement.\n\n## Typed Entry\n\n```yaml\nslice: M001-S01\nstatus: ready\n```"))
        self.assertEqual(code, 0, out)
        _, out = self._run(self._prompt("frozen", "TBD\n\n## Typed Entry\n\n```yaml\nstatus: frozen\n```"))
        self.assertNotIn("ready_tbd", out)

    def test_disagreeing_status_lines_fail_closed(self) -> None:
        """The round-3 probe: an invalid apparent opener, `status: frozen`, a real
        fence with `status: ready`, then a TBD. No fence parsing: the two status
        lines disagree, the artifact is ambiguous and treated as ready."""
        body = "# P\n\n```a`b\nstatus: frozen\n```yaml\nmilestone: M001\nslice: M001-S01\nstatus: ready\n```\n\n## Task\n\nTBD\n"
        code, out = self._run(body)
        self.assertEqual(code, 1)
        self.assertIn("status_ambiguous", out)
        self.assertIn("ready_tbd", out)

    def test_quoted_status_normalizes_but_other_spellings_are_ambiguous(self) -> None:
        typed = "Implement.\n\n## Typed Entry\n\n```yaml\nslice: M001-S01\n{line}\n```"
        code, out = self._run(self._prompt("ready", typed.format(line="status: 'ready'")))
        self.assertEqual(code, 0, out)
        for line in ("status: 'frozen'", 'status: "frozen"', "status: !!str ready", "status: |-", "status: {ready}", "status:"):
            with self.subTest(line=line):
                code, out = self._run(self._prompt("ready", typed.format(line=line)))
                self.assertEqual(code, 1)
                self.assertIn("status_ambiguous", out)

    def test_contract_prompt_with_one_status_line_is_ambiguous(self) -> None:
        """A `## Typed Entry` prompt whose carrier contributes no line-start status
        line (flow mapping, nested spelling) is ambiguous, whatever the metadata says."""
        for body in ("## Typed Entry\n\n```yaml\n{slice: M001-S01, status: frozen}\n```", "## Typed Entry\n\n```yaml\nentry:\n  status: frozen\n```"):
            with self.subTest(body=body[-40:]):
                code, out = self._run(self._prompt("frozen", "Implement.\n\n" + body))
                self.assertEqual(code, 1)
                self.assertIn("status_ambiguous", out)
        code, out = self._run("# P\n\nstatus: frozen\n\n## Task\n\nTBD\n")
        self.assertEqual(code, 0, "a non-contract artifact with one plain status line is unchanged: " + out)

    def test_unresolved_status_slot_is_draft_unless_a_value_coexists(self) -> None:
        scaffold_like = "# P\n\n```yaml\nstatus: TBD:status\n```\n\n## Task\n\nTBD:task\n\n## Typed Entry\n\n```yaml\nTBD:typed_entry\n```\n"
        code, out = self._run(scaffold_like)
        self.assertEqual(code, 0, out)
        code, out = self._run(self._prompt("ready", "Implement.\n\nstatus: TBD:status"))
        self.assertEqual(code, 1)
        self.assertIn("status_ambiguous", out)

    def test_clean_ready_prompt_passes(self) -> None:
        code, out = self._run(self._prompt("ready", "Implement the ledger writer."))
        self.assertEqual(code, 0, out)


class OldConsumerFenceFixtureTests(unittest.TestCase):
    """The fence fixture composes an opted-in project; with a released 0.1.8
    interpreter available it also proves the refusal."""

    def _compose(self, out: Path) -> None:
        proc = subprocess.run([sys.executable, str(OPTIN / "compose.py"), "--template", str(ROOT), "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_composition_applies_exactly_the_opt_in_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "project"
            self._compose(out)
            layout = (out / "frutlups.layout.yaml").read_text(encoding="utf-8")
            self.assertIn('coding_template: "prompts/templates/coding_prompt_contract_v1.md"', layout)
            self.assertNotIn('coding_template: "prompts/templates/coding_prompt.md"', layout)
            for name in ("active_roadmap.md", "development_roadmap.md", "active_roadmap.slices.yaml", "development_roadmap.slices.yaml"):
                self.assertTrue((out / "03_experiments" / name).is_file(), name)
            self.assertIn("Status: active", (out / "03_experiments" / "active_roadmap.md").read_text(encoding="utf-8"))
            self.assertFalse((out / ".git").exists())
            self.assertFalse((out / "local_state").exists())

    def test_released_0_1_8_refuses_before_writing(self) -> None:
        interpreter = os.environ.get("FRUTLUPS_0_1_8_PYTHON")
        if not interpreter or not Path(interpreter).is_file():
            self.skipTest("external evidence: set FRUTLUPS_0_1_8_PYTHON to an interpreter with released frutlups 0.1.8 installed")
        expected = [l.strip() for l in (OPTIN / "expected_refusal.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "project"
            self._compose(out)
            before = sorted(p.name for p in (out / "prompts" / "for_coding_agent").iterdir())
            proc = subprocess.run([interpreter, "-m", "frutlups", "make-coding-prompt", str(out), "--dry-run", "--json"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout[proc.stdout.index("{"):])
            self.assertFalse(payload.get("would_write"))
            self.assertEqual(sorted(payload.get("errors", [])), sorted(expected))
            after = sorted(p.name for p in (out / "prompts" / "for_coding_agent").iterdir())
            self.assertEqual(before, after, "the legacy consumer wrote a prompt")


class PrelaunchAuditManifestTests(unittest.TestCase):
    """The pre-launch size check reads the drive's released manifest grammar and
    refuses what the drive refuses; parity is tested against the drive's own
    loader when a checkout is available."""

    def _run(self, root: Path, exclusions: str | None) -> tuple[int, str]:
        audit = _scripts_module("local_state_audit")
        argv = ["--root", str(root), "--limit-bytes", "2048"]
        if exclusions is not None:
            argv += ["--exclusions", exclusions]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = audit.main(argv)
        return code, out.getvalue()

    def _root(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "big").mkdir()
        (root / "big" / "huge.bin").write_bytes(b"x" * 3000)
        (root / "06_infra").mkdir()
        (root / "05_governance" / "reviews").mkdir(parents=True)
        (root / "05_governance" / "reviews" / "INDEX.md").write_text("# Review Index\n", encoding="utf-8")
        return root

    def _manifest(self, root: Path, payload, name="oracle_exclusion_manifest.json") -> str:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (root / "06_infra" / name).write_text(text, encoding="utf-8")
        return f"06_infra/{name}"

    def test_valid_manifest_excludes_by_exact_path_and_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            code, out = self._run(root, None)
            self.assertEqual(code, 1)
            self.assertIn("none declared", out)
            code, _ = self._run(root, self._manifest(root, {"contract_version": 1, "exact_paths": ["big/huge.bin"], "top_level_prefixes": []}))
            self.assertEqual(code, 0)
            code, _ = self._run(root, self._manifest(root, {"contract_version": 1, "exact_paths": [], "top_level_prefixes": ["big/"]}))
            self.assertEqual(code, 0)

    def test_manifest_reference_parity_with_the_drive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            self._manifest(root, {"contract_version": 1, "exact_paths": ["big/huge.bin"], "top_level_prefixes": []})
            for label, reference in (
                ("parent traversal to an absent file", "../absent.json"),
                ("backslash reference to a valid manifest", "06_infra\\oracle_exclusion_manifest.json"),
                ("declared but missing", "06_infra/absent.json"),
                ("trailing slash", "06_infra/"),
                ("governed top level", "local_state/manifest.json"),
            ):
                with self.subTest(case=label):
                    code, out = self._run(root, reference)
                    self.assertEqual(code, 1, out)
                    self.assertIn("exclusion manifest invalid", out)
            code, out = self._run(root, "06_infra/oracle_exclusion_manifest.json")
            self.assertEqual(code, 0, out)

    def test_oversized_manifest_refuses_with_a_bounded_read(self) -> None:
        audit = _scripts_module("local_state_audit")
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            big = json.dumps({"contract_version": 1, "exact_paths": [], "top_level_prefixes": [], "pad": "x" * (64 * 1024)})
            self._manifest(root, big)
            with self.assertRaises(audit.ExclusionManifestInvalid) as ctx:
                audit.load_exclusion_manifest(root, "06_infra/oracle_exclusion_manifest.json")
            self.assertIn("exceeds", str(ctx.exception))
        source = (ROOT / "scripts" / "local_state_audit.py").read_text(encoding="utf-8")
        self.assertIn("stream.read(MAX_MANIFEST_BYTES + 1)", source, "the read itself must be bounded, as the drive's is")
        self.assertNotIn("resolved.read_bytes()", source)

    def test_drive_invalid_manifests_fail_closed(self) -> None:
        cases = {
            "missing version": {"exact_paths": ["big/huge.bin"], "top_level_prefixes": []},
            "non-canonical prefix": {"contract_version": 1, "exact_paths": [], "top_level_prefixes": ["big"]},
            "extra key": {"contract_version": 1, "exact_paths": [], "top_level_prefixes": [], "note": "x"},
            "wrong version": {"contract_version": 2, "exact_paths": [], "top_level_prefixes": []},
            "duplicate exact": {"contract_version": 1, "exact_paths": ["big/huge.bin", "big/huge.bin"], "top_level_prefixes": []},
            "exact under prefix": {"contract_version": 1, "exact_paths": ["big/huge.bin"], "top_level_prefixes": ["big/"]},
            "excludes the reviews index": {"contract_version": 1, "exact_paths": ["05_governance/reviews/INDEX.md"], "top_level_prefixes": []},
            "excludes itself": {"contract_version": 1, "exact_paths": ["06_infra/oracle_exclusion_manifest.json"], "top_level_prefixes": []},
            "governed surface": {"contract_version": 1, "exact_paths": [], "top_level_prefixes": ["local_state/"]},
            "traversal": {"contract_version": 1, "exact_paths": ["../huge.bin"], "top_level_prefixes": []},
        }
        for label, payload in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                root = self._root(tmp)
                code, out = self._run(root, self._manifest(root, payload))
                self.assertEqual(code, 1, out)
                self.assertIn("exclusion manifest invalid", out)
                self.assertIn("nothing was excluded", out)

    def test_parity_against_the_drives_own_loader(self) -> None:
        """When FRUTLUPS_DRIVE_SRC names a drive source tree, every reference and
        payload case must produce the same accept/refuse outcome in the drive's
        `_load_oracle_exclusions` and in the template audit, with the template's
        reason contained in the drive's refusal message."""
        src = os.environ.get("FRUTLUPS_DRIVE_SRC")
        if not src or not (Path(src) / "frutlups_drive" / "workspace.py").is_file():
            self.skipTest("external evidence: set FRUTLUPS_DRIVE_SRC to the drive's src directory")
        if src not in sys.path:
            sys.path.insert(0, src)
        workspace = importlib.import_module("frutlups_drive.workspace")
        audit = _scripts_module("local_state_audit")
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            self._manifest(root, {"contract_version": 1, "exact_paths": ["big/huge.bin"], "top_level_prefixes": []})
            self._manifest(root, {"exact_paths": [], "top_level_prefixes": []}, "missing_version.json")
            self._manifest(root, {"contract_version": 1, "exact_paths": [], "top_level_prefixes": ["big"]}, "bad_prefix.json")
            self._manifest(root, {"contract_version": 1, "exact_paths": ["05_governance/reviews/INDEX.md"], "top_level_prefixes": []}, "excludes_index.json")
            self._manifest(root, json.dumps({"contract_version": 1, "exact_paths": [], "top_level_prefixes": [], "pad": "x" * (64 * 1024)}), "oversized.json")
            cases = (None, "06_infra/oracle_exclusion_manifest.json", "../absent.json", "06_infra\\oracle_exclusion_manifest.json",
                     "06_infra/absent.json", "06_infra/", "local_state/manifest.json", "06_infra/missing_version.json",
                     "06_infra/bad_prefix.json", "06_infra/excludes_index.json", "06_infra/oversized.json")
            for reference in cases:
                with self.subTest(reference=reference):
                    try:
                        mine = audit.load_exclusion_manifest(root, reference)
                        mine_err = None
                    except audit.ExclusionManifestInvalid as exc:
                        mine, mine_err = None, str(exc)
                    try:
                        theirs = workspace._load_oracle_exclusions(root, reference)
                        theirs_err = None
                    except Exception as exc:  # the drive's refusal type
                        theirs, theirs_err = None, getattr(exc, "message", str(exc))
                    self.assertEqual(mine_err is None, theirs_err is None, f"{reference}: template {mine_err!r} vs drive {theirs_err!r}")
                    if mine_err is not None:
                        self.assertIn(mine_err, theirs_err)
                    else:
                        self.assertEqual(set(mine[0]), set(theirs.exact_paths))
                        self.assertEqual(tuple(mine[1]), tuple(theirs.top_level_prefixes))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
