"""Qualification of complete, bounded prompts and nonmutating preview."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from test_scaffold import PASS_REPORT, git_init, project_copy, quiet_call, run_git, set_full

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _common as c  # noqa: E402
import _evidence as evidence  # noqa: E402
import _findings as findings  # noqa: E402
import ledger  # noqa: E402
import prompt  # noqa: E402
import roadmap  # noqa: E402
import verify  # noqa: E402


def fixture(root, *, notes="", schema="frutlups.roadmap/2"):
    project_copy(root)
    # The fixture mirrors the actual standalone command surface.
    for path in (ROOT / "scripts").glob("*.py"):
        (root / "scripts" / path.name).write_bytes(path.read_bytes())
    data = yaml.safe_load((root / "roadmap.yaml").read_text(encoding="utf-8"))
    data["schema"] = schema
    data["milestones"][0]["slices"][0]["notes"] = notes
    (root / "roadmap.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    set_full(root, "pass")
    git_init(root)
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "fixture")


class PromptV2Tests(unittest.TestCase):
    def test_reopen_invalidates_passing_holistic_decision(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)

            def accept_round(round_no):
                prompt.coding(root, "M001-S01")
                (root / "07_app/source.py").write_text(f"round_no = {round_no}\n", encoding="utf-8")
                self.assertEqual(
                    quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 0
                )
                self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
                report = f"05_governance/reviews/m001/round{round_no}.md"
                (root / report).write_text(
                    PASS_REPORT.replace("round 1", f"round {round_no}"), encoding="utf-8"
                )
                self.assertEqual(
                    quiet_call(ledger.main, ["--root", str(root), "record", report]), 0
                )
                self.assertEqual(
                    quiet_call(ledger.main, ["--root", str(root), "accept", "M001-S01"]), 0
                )

            accept_round(1)
            report = "05_governance/reviews/m001/holistic.md"
            (root / report).write_text(
                PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic"), encoding="utf-8"
            )
            self.assertEqual(
                quiet_call(
                    ledger.main, ["--root", str(root), "record", report, "--milestone", "M001"]
                ),
                0,
            )
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "reopen",
                        "M001-S01",
                        "--reason",
                        "new accepted behavior",
                    ],
                ),
                0,
            )
            accept_round(2)
            self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "close", "M001"]), 2)
            text = prompt.holistic(root, "M001", preview=True)
            self.assertIn("Previous holistic decision: pass", text)

    def test_omitted_old_finding_keeps_its_original_slice_ownership(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            events = []
            for number in (1, 2):
                rel = f"r{number}.md"
                text = (
                    PASS_REPORT.replace("round 1", f"round {number}")
                    .replace(
                        "| --- | --- | --- | --- |",
                        f"| --- | --- | --- | --- |\n| F{number} | P1 | open | still broken |",
                    )
                    .replace("Verdict: pass", "Verdict: needs_work")
                )
                (root / rel).write_text(text, encoding="utf-8")
                events.append(
                    {
                        "ev": "reviewed",
                        "schema": "frutlups.ledger/2",
                        "by": "architect",
                        "report": rel,
                        "sha": c.sha(root / rel),
                    }
                )
            updates = (
                "## Finding updates\n| source | sha | id | disposition | related |\n"
                "| --- | --- | --- | --- | --- |\n"
                f"| r2.md | {events[1]['sha']} | F2 | closed_by_review | - |\n\n"
            )
            text = PASS_REPORT.replace("round 1", "round 3").replace(
                "## Closure Decision", updates + "## Closure Decision"
            )
            (root / "r3.md").write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source-bound closure: F1"):
                findings.validate_record(
                    root, events, "r3.md", c.sha(root / "r3.md"), "architect", {"open": ["F2"]}
                )

    def test_high_priority_carry_cannot_replace_a_human_waiver(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for severity in ("P0", "P1", "P2"):
                with self.subTest(severity=severity):
                    report = PASS_REPORT.replace(
                        "| --- | --- | --- | --- |",
                        f"| --- | --- | --- | --- |\n| F1 | {severity} | carried | unresolved |",
                    )
                    (root / "report.md").write_text(report, encoding="utf-8")
                    digest = c.sha(root / "report.md")
                    with self.assertRaisesRegex(ValueError, "only P3"):
                        findings.validate_record(root, [], "report.md", digest, "architect")
                    # Existing legacy dispositions remain readable without relabeling.
                    findings.project(
                        root,
                        [
                            {
                                "ev": "reviewed",
                                "schema": "frutlups.ledger/1",
                                "by": "architect",
                                "report": "report.md",
                                "sha": digest,
                            }
                        ],
                    )
                    prior = report.replace("carried", "open").replace(
                        "Verdict: pass", "Verdict: needs_work"
                    )
                    (root / "prior.md").write_text(prior, encoding="utf-8")
                    event = {
                        "ev": "reviewed",
                        "schema": "frutlups.ledger/2",
                        "by": "architect",
                        "report": "prior.md",
                        "sha": c.sha(root / "prior.md"),
                    }
                    updates = (
                        "## Finding updates\n| source | sha | id | disposition | related |\n"
                        "| --- | --- | --- | --- | --- |\n"
                        f"| prior.md | {event['sha']} | F1 | carried | - |\n\n"
                    )
                    text = PASS_REPORT.replace(
                        "## Closure Decision", updates + "## Closure Decision"
                    )
                    (root / "update.md").write_text(text, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "only P3"):
                        findings.validate_record(
                            root, [event], "update.md", c.sha(root / "update.md"), "architect"
                        )

    def test_blocker_resolution_preserves_envelope_changes_notes_and_authority(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            prompt.coding(root, "M001-S01")
            (root / "07_app/source.py").write_text("retained = True\n", encoding="utf-8")
            notes = "05_governance/reviews/m001/coder_notes.md"
            (root / notes).write_text("Retained partial implementation.\n" * 200, encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "blocked",
                        "M001-S01",
                        "--notes",
                        notes,
                        "--requirement",
                        "Owner-approved input",
                        "--reason",
                        "Input authority missing",
                        "--actor",
                        "human",
                        "--action",
                        "Approve the input",
                        "--remaining",
                        "Read input",
                    ],
                ),
                0,
            )
            decision = root / "00_brief/decisions.md"
            decision.write_text("D-1: The named input is approved.\n", encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "resolve",
                        "M001-S01",
                        "--reason",
                        "D-1 permits input",
                        "--authority",
                        "00_brief/decisions.md",
                    ],
                ),
                0,
            )
            text = prompt.coding(root, "M001-S01", preview=True)
            for phrase in (
                "Input authority missing",
                "D-1 permits input",
                "Retained changes",
                "Previous notes",
                "Retained partial implementation.",
                "Resolution authority",
            ):
                self.assertIn(phrase, text)
            self.assertIn(c.sha(decision), text)
            self.assertEqual(
                text, (root / prompt.coding(root, "M001-S01")).read_text(encoding="utf-8")
            )

    def test_preview_matches_issuance_without_allocating_or_writing(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root, notes="The refresh branch must use fresh input.")
            before = c.status_bytes(root), (root / "05_governance/ledger.jsonl").read_bytes()
            with mock.patch.object(prompt, "_next", side_effect=AssertionError("allocated")):
                preview = prompt.coding(root, "M001-S01", preview=True)
            self.assertEqual(
                before, (c.status_bytes(root), (root / "05_governance/ledger.jsonl").read_bytes())
            )
            self.assertIn("Advisory context; mandatory gates belong in acceptance", preview)
            self.assertIn("refresh branch must use fresh input", preview)
            self.assertEqual(
                preview, (root / prompt.coding(root, "M001-S01")).read_text(encoding="utf-8")
            )
            event = ledger.read(root / "05_governance/ledger.jsonl")[-1]
            self.assertEqual(c.sha(root / event["envelope"]["path"]), event["envelope"]["sha"])
            envelope = json.loads((root / event["envelope"]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(envelope["runtime"], {})
            self.assertEqual(envelope["timeout_seconds"], 600)
            self.assertEqual(envelope["observation"], "process")

    def test_unicode_mandatory_cap_precedes_git_and_preserves_state(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root, notes="界" * 6000)
            with mock.patch.object(evidence, "prompt_baseline") as baseline:
                with self.assertRaisesRegex(ValueError, "cap is 16384.*Section bytes"):
                    prompt.coding(root, "M001-S01", preview=True)
            baseline.assert_not_called()
            self.assertEqual((root / "05_governance/ledger.jsonl").read_bytes(), b"")

    def test_missing_reads_and_advisory_scope_are_diagnosed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            data = roadmap.load(root)
            item = data["milestones"][0]["slices"][0]
            item["read_first"] = ["07_app/future.py"]
            item["acceptance"] = ["Implement integration in `tests/user_path.py`."]
            envelope = prompt._envelope(
                root, data, item, ledger.fold([], data)["slices"]["M001-S01"]
            )
            diagnostics = prompt._diagnostics(root, envelope)
            self.assertTrue(
                any("missing required read: 07_app/future.py" in x for x in diagnostics)
            )
            self.assertTrue(any("outside writes: tests/user_path.py" in x for x in diagnostics))
            (root / "roadmap.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required reads"):
                prompt.coding(root, "M001-S01", True, preview=True)

    def test_review_uses_frozen_envelope_after_roadmap_edit(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root, notes="Original advisory explanation.")
            prompt.coding(root, "M001-S01")
            (root / "07_app/source.py").write_text("answer = 41\n", encoding="utf-8")
            self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 0)
            self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
            data = roadmap.load(root)
            data["milestones"][0]["slices"][0]["objective"] = "A newly changed objective."
            data["milestones"][0]["slices"][0]["notes"] = "New advisory explanation."
            (root / "roadmap.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
            preview = prompt.review(root, "M001-S01", preview=True)
            self.assertIn("Original advisory explanation.", preview)
            self.assertNotIn("A newly changed objective.", preview)
            self.assertNotIn("New advisory explanation.", preview)
            for heading in (
                "## Non-goals",
                "## Read first",
                "## Implementation boundary",
                "## Declared verification",
            ):
                self.assertIn(heading, preview)
            issued = prompt.review(root, "M001-S01")
            self.assertEqual(preview, (root / issued).read_text(encoding="utf-8"))
            events = ledger.read(root / "05_governance/ledger.jsonl")
            refs = [e for e in events if e["ev"] == "artifact" and e["role"] == "evidence"]
            self.assertTrue(refs)
            for ref in refs:
                self.assertEqual(c.sha(root / ref["path"]), ref["sha"])
            unseen = root / "07_app/unrecorded.py"
            unseen.write_text("unseen = True\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unrecorded product changes"):
                prompt.review(root, "M001-S01", preview=True)
            unseen.unlink()
            source = root / "07_app/source.py"
            original = source.read_bytes()
            changed_bytes = (
                original.replace(b"\r\n", b"\n")
                if b"\r\n" in original
                else original.replace(b"\n", b"\r\n")
            )
            source.write_bytes(changed_bytes)
            with self.assertRaisesRegex(ValueError, "raw product content or mode changed"):
                prompt.review(root, "M001-S01", preview=True)
            source.write_bytes(original)
            (root / "07_app/source.py").write_text("answer = 42\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "active product drift"):
                prompt.review(root, "M001-S01", preview=True)

    def test_large_evidence_prioritizes_small_source_and_bounds_reads(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            prompt.coding(root, "M001-S01")
            (root / "07_app/z_source.py").write_text("def answer(): return 41\n", encoding="utf-8")
            folder = root / "07_app/artifacts"
            folder.mkdir()
            for number in range(700):
                (folder / f"bulk_{number:04d}.csv").write_text("bulk,1\n" * 3000, encoding="utf-8")
            self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 0)
            self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
            original = Path.read_text

            def bounded_only(path, *args, **kwargs):
                if path.suffix == ".csv":
                    raise AssertionError("bulk file read whole")
                return original(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", bounded_only):
                text = prompt.review(root, "M001-S01", preview=True)
            self.assertLessEqual(len(text.encode("utf-8")), prompt.REVIEW_LIMIT)
            self.assertIn("701 cumulative paths", text)
            self.assertIn("def answer(): return 41", text)
            self.assertIn("not a prior-round delta", text)
            self.assertIn("read as a file, starting at line 1", text)
            events = ledger.read(root / "05_governance/ledger.jsonl")
            state = ledger.fold(events, roadmap.load(root))["slices"]["M001-S01"]
            manifest = json.loads((root / state["manifest"]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["changed"]), 701)

    def test_custom_template_is_preserved_and_missing_authority_appended(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root, notes="Project advisory text.")
            template = root / "prompts/templates/coding_prompt.md"
            custom = "# Project custom voice\n\n{{objective}}\n"
            template.write_text(custom, encoding="utf-8")
            text = prompt.coding(root, "M001-S01", True, preview=True)
            self.assertTrue(text.startswith("# Project custom voice"))
            self.assertIn("## Acceptance", text)
            self.assertIn("## Forbidden writes", text)
            self.assertEqual(template.read_text(encoding="utf-8"), custom)
            autonomous = prompt.coding(root, "M001-S01", True, preview=True, backend="autonomous")
            self.assertIn('"schema": "frutlups.outcome/2"', autonomous)
            self.assertIn("blocked_authority", autonomous)

    def test_legacy_custom_template_does_not_gain_version_two_protocol(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root, schema="frutlups.roadmap/1")
            template = root / "prompts/templates/coding_prompt.md"
            template.write_text("# Custom\n{{objective}}\n", encoding="utf-8")
            text = prompt.coding(root, "M001-S01", True, preview=True)
            self.assertNotIn("frutlups.outcome/2", text)
            self.assertNotIn("## Forbidden writes", text)
            with self.assertRaisesRegex(ValueError, "require the /2"):
                prompt.coding(root, "M001-S01", True, preview=True, backend="autonomous")

    def test_check_renders_sections_and_changes_no_files(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = prompt.main(["--root", str(root), "M001-S01", "--check"])
            self.assertEqual(result, 0)
            self.assertIn("UTF-8 bytes", output.getvalue())
            self.assertIn("## Acceptance:", output.getvalue())
            self.assertEqual(c.status_bytes(root), b"")


if __name__ == "__main__":
    unittest.main()
