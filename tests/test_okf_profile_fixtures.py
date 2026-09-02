"""Deterministic integrity checks for the OKF profile golden-fixture corpus.

These tests validate the fixture *contract and inventory* only. They do NOT parse
fixture YAML and do NOT judge the semantic truth of any document; that is a future
checker's job. Everything here is standard-library only.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIX_ROOT = ROOT / "tests" / "fixtures" / "okf_profile"
MANIFEST = FIX_ROOT / "manifest.json"

OKF_RESULTS = {"pass", "fail", "unverified", "not_evaluated"}
PROFILE_RESULTS = {"pass", "fail", "not_applicable"}
OKF_REASONS = {
    "OKF_FRONTMATTER_MISSING", "OKF_TYPE_MISSING", "OKF_YAML_UNSUPPORTED",
    "OKF_YAML_INVALID", "OKF_PARSE_LIMIT_EXCEEDED",
}
PROFILE_REASONS = {"PROFILE_YAML_OUT_OF_SUBSET", "PROFILE_VERSION_UNSUPPORTED", "PROFILE_TYPE_UNSUPPORTED"}

REQUIRED_TAGS = {
    "accepted", "legacy", "out_of_subset", "okf_fail", "profile_fail",
    "semantic_equivalence", "moved_path", "mixed_version", "scalar_typing",
    "duplicate_key", "flow_collection", "unknown_extension", "quoted_numeric",
    "tool_namespace", "frontmatter_boundary", "type", "version",
    "anchors_aliases", "merge_keys", "unprofiled",
}

# Built by concatenation so this test file itself never contains the literal
# machine-local fragments it scans fixtures for.
FORBIDDEN_FRAGMENTS = (
    "C:" + "\\Users\\dev",
    "repos" + "_dev",
    "agentic-project-template" + "-v2" + "-dev",
    "/Users/" + "dev",
)

# The shipped profile records the normative OKF source as an external, revision-pinned
# reference (not vendored). This is the exact release provenance contract; the shipped
# guard below validates it entirely offline (local files only, no network).
PROFILE = ROOT / "docs" / "template_framework" / "okf_pkg" / "okf_profile_v0_1.md"
PROV_SOURCE_ID = "OKF"
PROV_VERSION = "0.1-draft"
PROV_UPSTREAM_PATH = "okf/SPEC.md"
PROV_REVISION = "ee67a5ca27044ebe7c38385f5b6cffc2305a9c1a"
PROV_LOCATOR = (
    "https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/"
    "ee67a5ca27044ebe7c38385f5b6cffc2305a9c1a/okf/SPEC.md"
)
PROV_DIGEST = "b9655e607346dbbdc6de21190e9a953313eda6a7eba68d4d272a65975940ad6e"

# The record is one bounded subsection with six uniquely labeled rows. The guard
# validates the row *for each label* rather than searching the whole profile, so a
# field-only change is caught even when the old value survives in prose or the URL.
PROV_HEADING = "### Normative source (external pinned record)"
PROV_ROWS = {
    "Source identifier": PROV_SOURCE_ID,
    "Version": PROV_VERSION,
    "Upstream specification path": PROV_UPSTREAM_PATH,
    "Immutable locator": PROV_LOCATOR,
    "Upstream revision": PROV_REVISION,
    "Raw-byte SHA-256": PROV_DIGEST,
}


def provenance_block(text: str) -> str | None:
    """Body of the single external-pinned-record subsection, bounded at the next
    same-or-higher-level heading. Returns None unless exactly one such heading exists."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.strip() == PROV_HEADING]
    if len(starts) != 1:
        return None
    body = []
    for l in lines[starts[0] + 1:]:
        s = l.strip()
        if s.startswith("## ") or s.startswith("### "):
            break
        body.append(l)
    return "\n".join(body)


def record_rows(block: str) -> list[tuple[str, str]]:
    """(label, value) for every '- Label: value' row in the block, value stripped of a
    single backtick or angle-bracket display wrapper. Order and duplicates preserved."""
    rows = []
    for l in block.splitlines():
        s = l.strip()
        if not s.startswith("- ") or ": " not in s:
            continue
        label, value = s[2:].split(": ", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
            value = value[1:-1]
        elif len(value) >= 2 and value[0] == "<" and value[-1] == ">":
            value = value[1:-1]
        rows.append((label.strip(), value))
    return rows


class OkfProfileFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.fixtures = cls.manifest["fixtures"]

    # ----- manifest shape -----

    def test_manifest_schema_and_version(self) -> None:
        self.assertEqual(self.manifest["manifest_schema"], "okf_profile_fixture_manifest")
        self.assertTrue(str(self.manifest["manifest_version"]).strip())
        self.assertEqual(self.manifest["profile_candidate"], "0.1-rc.1")
        self.assertEqual(
            self.manifest["layers"],
            ["okf_concept", "framework_profile", "execution_eligibility"],
        )

    def test_manifest_vocabulary_matches_accepted_sets(self) -> None:
        vocab = self.manifest["vocabulary"]
        self.assertEqual(set(vocab["okf_concept_result"]), OKF_RESULTS)
        self.assertEqual(set(vocab["framework_profile_result"]), PROFILE_RESULTS)
        self.assertEqual(vocab["execution_eligibility"], ["not_evaluated"])
        self.assertEqual(set(vocab["okf_reason_codes"]), OKF_REASONS)
        self.assertEqual(set(vocab["profile_reason_codes"]), PROFILE_REASONS)

    # ----- ids / paths / ordering -----

    def test_ids_and_paths_unique_and_deterministically_ordered(self) -> None:
        ids = [f["id"] for f in self.fixtures]
        paths = [f["path"] for f in self.fixtures]
        self.assertEqual(len(ids), len(set(ids)), "duplicate fixture id")
        self.assertEqual(len(paths), len(set(paths)), "duplicate fixture path")
        self.assertEqual(ids, sorted(ids), "fixtures are not ordered by id")
        self.assertGreaterEqual(len(ids), 20, "fixture corpus looks too small")

    def test_paths_are_safe_bounded_and_exist(self) -> None:
        root_resolved = FIX_ROOT.resolve()
        prefix = "tests/fixtures/okf_profile/"
        for f in self.fixtures:
            path = f["path"]
            self.assertTrue(path.startswith(prefix), f"{path} not under fixture root")
            self.assertNotIn("..", path.split("/"), f"{path} contains a parent traversal")
            resolved = (ROOT / path).resolve()
            self.assertTrue(
                resolved == root_resolved or root_resolved in resolved.parents,
                f"{path} escapes the fixture root",
            )
            self.assertTrue(resolved.is_file(), f"{path} is not a regular file")

    def test_inventory_complete_both_directions(self) -> None:
        manifest_paths = {(ROOT / f["path"]).resolve() for f in self.fixtures}
        on_disk = {p.resolve() for p in FIX_ROOT.rglob("*.md")}
        missing_from_manifest = on_disk - manifest_paths
        missing_on_disk = manifest_paths - on_disk
        self.assertEqual(missing_from_manifest, set(), "fixtures on disk absent from manifest")
        self.assertEqual(missing_on_disk, set(), "manifest paths absent on disk")

    # ----- expected outcomes use the accepted vocabulary -----

    def test_expected_outcomes_use_accepted_vocabulary(self) -> None:
        for f in self.fixtures:
            expected = f["expected"]
            self.assertEqual(
                expected["execution_eligibility"], "not_evaluated",
                f"{f['id']}: execution eligibility must be not_evaluated in this layer",
            )
            for parser in ("subset_parser", "full_parser"):
                block = expected[parser]
                okf = block["okf_concept"]
                prof = block["framework_profile"]
                self.assertIn(okf["result"], OKF_RESULTS, f"{f['id']}/{parser} okf result")
                self.assertIn(prof["result"], PROFILE_RESULTS, f"{f['id']}/{parser} profile result")
                self.assertTrue(
                    okf["reason"] is None or okf["reason"] in OKF_REASONS,
                    f"{f['id']}/{parser} okf reason '{okf['reason']}' not in accepted set",
                )
                self.assertTrue(
                    prof["reason"] is None or prof["reason"] in PROFILE_REASONS,
                    f"{f['id']}/{parser} profile reason '{prof['reason']}' not in accepted set",
                )
                # A pass/not_applicable/not_evaluated result carries no reason code.
                if okf["result"] in {"pass", "not_evaluated"}:
                    self.assertIsNone(okf["reason"], f"{f['id']}/{parser} okf pass carries a reason")
                if prof["result"] in {"pass", "not_applicable"}:
                    self.assertIsNone(prof["reason"], f"{f['id']}/{parser} profile ok carries a reason")

    # ----- coverage tags and groups -----

    def test_required_scenario_tags_present(self) -> None:
        seen = set()
        for f in self.fixtures:
            seen.update(f["tags"])
        missing = REQUIRED_TAGS - seen
        self.assertEqual(missing, set(), f"missing required scenario tags: {sorted(missing)}")

    def test_groups_reference_real_fixtures_and_declare_comparison(self) -> None:
        ids = {f["id"] for f in self.fixtures}
        groups = self.manifest["groups"]
        for name in ("semantic_equivalence", "moved_path", "mixed_version"):
            self.assertIn(name, groups, f"missing group {name}")
            for pair in groups[name]["members"]:
                for member in pair:
                    self.assertIn(member, ids, f"group {name} references unknown fixture {member}")
                self.assertEqual(len(pair), len(set(pair)), f"group {name} pair has a duplicate")
        # The equivalence group compares semantic mappings and makes no byte-parse claim.
        eq = groups["semantic_equivalence"]
        self.assertEqual(eq["comparison"], "semantic_mapping_equality")
        self.assertFalse(eq["byte_identical_parse_claim"])
        # The moved-path pair shares a stable identity but distinct concept-id paths.
        a, b = groups["moved_path"]["members"][0]
        pa = next(f["path"] for f in self.fixtures if f["id"] == a)
        pb = next(f["path"] for f in self.fixtures if f["id"] == b)
        self.assertNotEqual(pa, pb, "moved-path pair must have distinct paths")

    # ----- portability / safety of fixture text -----

    def test_fixtures_are_utf8_and_free_of_machine_paths(self) -> None:
        for md in FIX_ROOT.rglob("*.md"):
            text = md.read_text(encoding="utf-8")  # raises on non-UTF-8
            for fragment in FORBIDDEN_FRAGMENTS:
                self.assertNotIn(fragment, text, f"{md} contains machine-local fragment")
            self.assertNotIn("BEGIN " + "PRIVATE KEY", text, f"{md} contains a private key block")


class ProfileProvenanceTests(unittest.TestCase):
    """Narrow release contract: the profile cites an external, revision-pinned OKF
    source in one bounded, uniquely labeled record a template-only consumer can locate
    and authenticate offline. Each labeled row is validated for its exact value, so a
    field-only change fails even when the old value survives elsewhere."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PROFILE.read_text(encoding="utf-8")
        cls.block = provenance_block(cls.text)
        cls.rows = record_rows(cls.block) if cls.block is not None else []
        cls.values = dict(cls.rows)

    def test_exactly_one_external_pinned_record_block(self) -> None:
        self.assertIsNotNone(self.block, "expected exactly one external pinned-record subsection")

    def test_six_labeled_rows_are_exact_unique_and_bounded(self) -> None:
        labels = [label for label, _ in self.rows]
        # Exactly the six expected labels, each once: rejects a missing label, a
        # duplicate/conflicting row, or an extra labeled row inside the record.
        self.assertEqual(sorted(labels), sorted(PROV_ROWS),
                         "record labels missing, duplicated, or extra")
        self.assertEqual(len(self.rows), len(PROV_ROWS))
        for label, expected in PROV_ROWS.items():
            self.assertEqual(self.values[label], expected,
                             f"labeled provenance row '{label}' value drifted")

    def test_locator_row_is_public_https_and_revision_pinned(self) -> None:
        loc = self.values.get("Immutable locator", "")
        rev = self.values.get("Upstream revision", "")
        self.assertTrue(loc.startswith("https://"), "locator is not public HTTPS")
        self.assertIn("raw.githubusercontent.com", loc)
        self.assertRegex(rev, r"^[0-9a-f]{40}$")  # immutable commit, not a moving name
        self.assertIn("/" + rev + "/", loc)
        self.assertIn("/" + PROV_UPSTREAM_PATH, loc)  # external path lives in the URL too
        for moving in ("/main/", "/master/", "/HEAD/", "/refs/"):
            self.assertNotIn(moving, loc, "locator uses a moving ref, not a revision")
        self.assertNotIn(":\\", loc)  # no machine-local path form
        self.assertFalse(loc.lower().startswith("file:"))

    def test_digest_row_is_lowercase_sha256(self) -> None:
        self.assertRegex(self.values.get("Raw-byte SHA-256", ""), r"^[0-9a-f]{64}$")

    def test_source_is_external_not_vendored(self) -> None:
        # No upstream specification is redistributed anywhere in the shipped tree.
        self.assertEqual(list(ROOT.rglob("SPEC.md")), [], "a vendored SPEC.md ships")
        # Any 'vendored' mention must be an explicit negation, never a false claim.
        low = self.text.lower()
        idx = 0
        while True:
            i = low.find("vendored", idx)
            if i == -1:
                break
            self.assertIn("not", low[max(0, i - 12):i],
                          "profile makes a positive 'vendored' claim but ships no spec")
            idx = i + len("vendored")


if __name__ == "__main__":
    unittest.main()
