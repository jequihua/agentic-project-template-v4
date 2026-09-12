"""Legacy finding meaning, strict new closures, and bounded history work."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _common as c
import _evidence
import _findings as findings
import _integrity
import ledger
import prompt
import roadmap
import verify
from test_integrity_v2 import verified
from test_scaffold import PASS_REPORT, quiet_call, run_git
from test_verification_v2 import awaiting

ROOT = Path(__file__).resolve().parents[1]


def report_row(identity, severity="P2", disposition="open", *, scope="M001-S01", round_no=1):
    value = PASS_REPORT.replace("M001-S01", scope).replace("round 1", f"round {round_no}")
    value = value.replace(
        "| --- | --- | --- | --- |",
        "| --- | --- | --- | --- |\n"
        f"| {identity} | {severity} | {disposition} | Recorded finding |",
    )
    if disposition == "open" and severity != "P3":
        value = value.replace("achieved", "not_achieved").replace(
            "Verdict: pass", "Verdict: needs_work"
        )
    return value


def save_report(root, name, text, *, legacy=False, actor="architect", checkpoint=False):
    rel = "05_governance/reviews/" + name + ".md"
    c.atomic_text(root / rel, text)
    parsed = _evidence.parse_review(text)
    event = {
        "schema": f"frutlups.ledger/{1 if legacy else 2}",
        "t": c.now(),
        "ev": "reviewed",
        "by": actor,
        "slice": parsed["identity"],
        "round": parsed["round"],
        "report": rel,
        "sha": c.sha(root / rel),
        "verdict": parsed["verdict"],
        "open": parsed["open"],
    }
    if checkpoint:
        event = {key: event[key] for key in ("schema", "t", "by", "round", "report", "sha")}
        event.update(
            ev="review_checkpoint",
            scope=parsed["identity"],
            invocation="review-seat",
            contract="0" * 64,
            seat="reviewer",
        )
    return event


class FindingCompatibilityTests(unittest.TestCase):
    def test_pinned_legacy_projection_corpus(self):
        data = json.loads((ROOT / "tests/fixtures/protocol_v2.json").read_text(encoding="utf-8"))
        for case in data["legacy_findings"]:
            with self.subTest(case=case["name"]), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                for ref in case["reports"]:
                    c.atomic_text(root / ref["path"], ref["text"])
                    self.assertEqual(c.sha(root / ref["path"]), ref["sha"])
                for event in case["events"]:
                    ledger._validate(event)
                projected, diagnostics = findings.project(root, case["events"])
                actual = [
                    {
                        "source": item["source"],
                        "id": item["id"],
                        "owner": item["owner"],
                        "disposition": item["disposition"],
                        "last_report": item["last_report"],
                    }
                    for item in projected.values()
                ]
                self.assertEqual(actual, case["expected"])
                self.assertTrue(any(case["diagnostic"] in message for message in diagnostics))

    def test_real_legacy_rounds_upgrade_without_rewriting_or_reopening_closed_findings(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            awaiting(root, "pass")

            def cli(*args):
                self.assertEqual(quiet_call(ledger.main, ["--root", str(root), *args]), 0, args)

            verify.run(root, "M001-S01", 10)
            first = save_report(root, "legacy_r1", report_row("F1"), legacy=True)
            cli("record", first["report"])
            prompt.coding(root, "M001-S01")
            (root / "07_app/product.txt").write_text("fixed\n", encoding="utf-8")
            cli("coded", "M001-S01")
            verify.run(root, "M001-S01", 10)
            second = save_report(
                root,
                "legacy_r2",
                report_row("F1", disposition="closed_by_review", round_no=2),
                legacy=True,
            )
            cli("record", second["report"])
            cli("accept", "M001-S01")
            rm = roadmap.load(root)
            # This artifact is the persisted /1 shape produced by the old unguarded
            # holistic waiver path. New records must use the current actor checks.
            text = report_row(
                "M001-S01-W1", disposition="waived_by_human", scope="M001", round_no="holistic"
            )
            waiver = save_report(root, "legacy_waiver", text, legacy=True)
            ledger_path = root / "05_governance/ledger.jsonl"
            ledger.append(
                ledger_path,
                {
                    "ev": "artifact",
                    "by": "architect",
                    "scope": "M001",
                    "round": "holistic",
                    "role": "holistic_report",
                    "path": waiver["report"],
                    "sha": waiver["sha"],
                },
                rm,
            )
            prefix = ledger_path.read_bytes()
            old_bytes = {
                event["report"]: (root / event["report"]).read_bytes()
                for event in (first, second, waiver)
            }
            rm["schema"] = "frutlups.roadmap/2"
            (root / "roadmap.yaml").write_text(
                yaml.safe_dump(rm, sort_keys=False), encoding="utf-8"
            )
            ledger.append(ledger_path, {"ev": "note", "by": "architect", "text": "Upgrade"}, rm)
            self.assertTrue(ledger_path.read_bytes().startswith(prefix))
            cli("check")
            cli("reconcile")
            run_git(root, "add", ".")
            run_git(root, "commit", "-qm", "legacy history and explicit upgrade")
            cli("reopen", "M001-S01", "--reason", "new work after stable upgrade")
            prompt.coding(root, "M001-S01")
            (root / "07_app/product.txt").write_text("upgraded\n", encoding="utf-8")
            cli("coded", "M001-S01")
            verify.run(root, "M001-S01", 10)
            third = save_report(root, "upgraded_r3", PASS_REPORT.replace("round 1", "round 3"))
            cli("record", third["report"])
            cli("accept", "M001-S01")
            cli("check")
            for rel, expected in old_bytes.items():
                self.assertEqual((root / rel).read_bytes(), expected)
            projected, diagnostics = findings.project(root, ledger.read(ledger_path))
            self.assertEqual(
                projected[(first["report"], first["sha"], "F1")]["disposition"], "closed_by_review"
            )
            self.assertEqual(len(projected), 2)
            self.assertTrue(any("Legacy waiver actor" in value for value in diagnostics))

    def test_new_waiver_guard_and_exact_unresolved_identity(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            original = save_report(root, "original", report_row("F1"), legacy=True)
            empty = save_report(root, "new", PASS_REPORT)
            with self.assertRaises(ValueError) as raised:
                findings.validate_record(
                    root, [original], empty["report"], empty["sha"], "architect"
                )
            for value in (original["report"], original["sha"], "F1"):
                self.assertIn(value, str(raised.exception))
            waived = save_report(root, "waived", report_row("W1", disposition="waived_by_human"))
            for actor in ("architect", "frutlups"):
                with (
                    self.subTest(actor=actor),
                    self.assertRaisesRegex(ValueError, "waiver requires"),
                ):
                    findings.project(root, [{**waived, "by": actor}])
            findings.project(root, [{**waived, "by": "human"}])

    def test_checkpoint_does_not_suppress_later_decision_same_report(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            decision = save_report(root, "checkpoint", report_row("F1"))
            checkpoint = save_report(root, "checkpoint", report_row("F1"), checkpoint=True)
            self.assertEqual(findings.project(root, [checkpoint])[0], {})
            rows, _ = findings.project(root, [checkpoint, decision])
            self.assertEqual(list(rows), [(decision["report"], decision["sha"], "F1")])

    def test_update_separator_and_generated_marker_damage_refuse_without_write(self):
        good = "## Finding updates\n| source | sha | id | disposition | related |\n"
        tail = f"\n| review.md | {'a' * 64} | F1 | closed_by_review | - |\n"
        for separator in (
            "| x | x | x | x | x |",
            "| --- | --- |",
            "| --- | --- | --- | --- | -- |",
        ):
            with self.subTest(separator=separator), self.assertRaisesRegex(ValueError, "table"):
                findings.updates(
                    PASS_REPORT.replace(
                        "## Closure Decision", good + separator + tail + "## Closure Decision"
                    )
                )
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            backlog = root / "05_governance/backlog.md"
            for marker in (
                "<!-- findings:begn -->",
                findings.BEGIN,
                findings.END + "\n" + findings.BEGIN,
                "prefix " + findings.BEGIN + "\n" + findings.END,
                findings.BEGIN + findings.END,
            ):
                with self.subTest(marker=marker):
                    c.atomic_text(backlog, "# Preserve prose\n" + marker + "\n")
                    before = backlog.read_bytes()
                    with self.assertRaisesRegex(ValueError, "markers"):
                        findings.reconcile(root, [])
                    self.assertEqual(backlog.read_bytes(), before)


class AdmissionAndScalingTests(unittest.TestCase):
    def test_same_length_overwrite_with_unchanged_metadata_never_reuses_hash_proof(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for reader in (findings.read_report, _integrity._reference):
                with self.subTest(reader=reader.__name__):
                    event = save_report(root, "immutable", report_row("F1"))
                    ref = {"path": event["report"], "sha": event["sha"]}
                    path = root / ref["path"]
                    original = path.read_bytes()
                    changed = original.replace(b"Recorded finding", b"Modified finding")
                    self.assertNotEqual(original, changed)
                    self.assertEqual(len(original), len(changed))
                    stamp = path.stat()
                    with (
                        c.command_scope(),
                        mock.patch.object(c, "file_key", return_value=("same",)),
                    ):
                        reader(root, ref)
                        path.write_bytes(changed)
                        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                        with self.assertRaisesRegex(ValueError, "immutable evidence drift"):
                            reader(root, ref)

    def test_derived_roadmap_can_render_after_verification_but_product_cannot_change(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            events, _, current = verified(root)
            self.assertIn("docs/roadmap.md", _integrity.evidence_paths(root, events))
            self.assertEqual(quiet_call(roadmap.main, ["--root", str(root), "render"]), 0)
            _integrity.require_active(root, current, events)
            changed = copy.deepcopy(current)
            product = root / "07_app/product.txt"
            product.write_text("owner edit\n", encoding="utf-8")
            for step in ("coding", "reviewing", "accept_pending"):
                changed["step"] = step
                with self.subTest(step=step), self.assertRaisesRegex(ValueError, "product differs"):
                    _integrity.require_active(root, changed, events)

    def test_accepted_head_matching_owner_hotfix_agrees_with_check_and_holistic_record(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            verified(root)

            def cli(*args):
                self.assertEqual(quiet_call(ledger.main, ["--root", str(root), *args]), 0, args)

            report = save_report(root, "pass", PASS_REPORT)
            cli("record", report["report"])
            cli("accept", "M001-S01")
            run_git(root, "add", ".")
            run_git(root, "commit", "-qm", "accepted")
            product = root / "07_app/product.txt"
            product.write_text("owner hotfix\n", encoding="utf-8")
            run_git(root, "add", "07_app/product.txt")
            run_git(root, "commit", "-qm", "owner hotfix")
            cli("check")
            events = ledger.read(root / "05_governance/ledger.jsonl")
            rm = roadmap.load(root)
            current = ledger.fold(events, rm)["slices"]["M001-S01"]
            _integrity.require_active(root, current, events)
            holistic = save_report(
                root, "holistic", PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic")
            )
            cli("record", holistic["report"], "--milestone", "M001")
            cli("close", "M001")
            product.write_text("uncommitted drift\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "product differs"):
                _integrity.require_active(root, current, events, extra=[holistic["report"]])

    def test_history_reports_parse_once_per_command_and_revalidate_after_mutation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rm = roadmap.load(ROOT)
            events = [
                save_report(
                    root, f"r{number}", report_row(f"F{number}", "P3", "carried", round_no=number)
                )
                for number in range(1, 31)
            ]
            with mock.patch.object(
                _evidence, "parse_review", wraps=_evidence.parse_review
            ) as parse:
                with (
                    c.command_scope(),
                    mock.patch.object(ledger, "fold", side_effect=AssertionError),
                ):
                    self.assertEqual(_integrity.errors(root, events, rm), [])
                    findings.project(root, events)
                    self.assertEqual(parse.call_count, 30)
                with c.command_scope():
                    findings.project(root, events)
                self.assertEqual(parse.call_count, 60)
            with c.command_scope():
                findings.project(root, events)
                path = root / events[0]["report"]
                path.write_text(path.read_text().replace("Recorded finding", "Modified finding"))
                with self.assertRaisesRegex(ValueError, "source drift"):
                    findings.project(root, events)
            with c.command_scope(), self.assertRaisesRegex(ValueError, "source drift"):
                findings.project(root, events)

    def test_closure_reads_only_indexed_open_findings_and_cache_returns_independent_values(self):
        class IndexedOnly(dict):
            def items(self):
                raise AssertionError("closure scanned all historical findings")

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            projection = findings.Projection(root)
            for number in range(1, 31):
                event = save_report(root, f"p3-{number}", report_row(f"P{number}", "P3", "carried"))
                projection.add((event["report"], event["sha"]), event)
            event = save_report(
                root, "holistic", report_row("M001-S01-F1", scope="M001", round_no="holistic")
            )
            projection.add((event["report"], event["sha"]), event)
            projection.findings = IndexedOnly(projection.findings)
            with self.assertRaisesRegex(ValueError, "M001-S01-F1"):
                projection.require_closure(_evidence.parse_review(PASS_REPORT))
            with c.command_scope():
                ref = {"path": event["report"], "sha": event["sha"]}
                _, first = findings.read_report(root, ref)
                first["findings"][0]["disposition"] = "closed_by_review"
                _, second = findings.read_report(root, ref)
                self.assertEqual(second["findings"][0]["disposition"], "open")
            with (
                c.command_scope(),
                mock.patch.object(c, "MEMO_LIMIT", 1),
                mock.patch.object(_evidence, "parse_review", wraps=_evidence.parse_review) as parse,
            ):
                findings.read_report(root, ref)
                findings.read_report(root, ref)
                self.assertEqual(parse.call_count, 2)


if __name__ == "__main__":
    unittest.main()
