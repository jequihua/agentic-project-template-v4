"""Reader parity, bounded admission and confirmed-refusal publication regressions."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_protocol_v2 import event, legacy_accepted
from test_prompts_v2 import fixture
from test_scaffold import PASS_REPORT

import _common as c
import _commit as commit
import _protocol as protocol
import ledger
import prompt
import roadmap
import verify


class ReaderParityTests(unittest.TestCase):
    def test_false_holistic_flag_refuses_direct_fold(self):
        rm = roadmap.load(ledger.c.ROOT)
        rm["milestones"][0]["holistic_review"] = False
        decision = event(
            "holistic_reviewed",
            milestone="M001",
            report="h.md",
            sha="d" * 64,
            verdict="pass",
            open=[],
        )
        ledger._validate(decision)
        with self.assertRaisesRegex(ValueError, "does not require holistic"):
            ledger.fold(legacy_accepted() + [decision], rm)

    def test_unblocked_refuses_validation_and_direct_fold(self):
        value = event("unblocked", slice="M001-S01", round=2, reason="Unbound authority")
        with self.assertRaisesRegex(ValueError, "authority-bound"):
            ledger._validate(value)
        prior = legacy_accepted()[:4]
        prior[-1].update(verdict="blocked")
        with self.assertRaisesRegex(ValueError, "authority-bound"):
            ledger.fold(prior + [value], roadmap.load(ledger.c.ROOT))

    def test_canonical_real_utc_timestamp_and_unknown_schema(self):
        for stamp in (
            "20260912T000000Z",
            "2026-09-12T00:00:00.000Z",
            "2026-09-12 00:00:00Z",
            "2026-02-30T00:00:00Z",
            "2026-09-12T25:00:00Z",
        ):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                ledger._validate(
                    event(
                        "resolved",
                        scope="M001-S01",
                        reason="Timestamp",
                        t=stamp,
                        authority=[{"path": "decision.md", "sha": "a" * 64}],
                    )
                )
        ledger._validate(event("note", text="canonical"))
        with self.assertRaises(ValueError):
            ledger._validate(event("note", text="future", schema="frutlups.ledger/3"))


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="template-review-protocol-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        fixture(self.root)

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = ledger.main(["--root", str(self.root), *args])
        return code, out.getvalue()

    def test_attempt_input_read_is_bounded_before_json(self):
        path = self.root / "local_state/oversized.json"
        path.write_bytes(b" " * (protocol.EVENT_LIMIT + 1))
        with mock.patch.object(ledger.json, "loads", wraps=json.loads) as loads:
            code, out = self.cli("attempt", "local_state/oversized.json")
        self.assertEqual(code, 2)
        self.assertIn("attempt event exceeds 2 MiB", out)
        self.assertFalse(
            any(len(call.args[0]) > protocol.EVENT_LIMIT for call in loads.call_args_list)
        )

    def test_v2_saved_prompt_registration_refuses_without_writes(self):
        before = (self.root / commit.LEDGER).read_bytes()
        code, out = self.cli("prompt", "M001-S01", "prompts/for_coding_agent/README.md")
        self.assertEqual(code, 2)
        self.assertIn("legacy /1 only; use prompt.py for /2", out)
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)

    def test_gate_reused_inside_command_revalidates_changed_ledger_and_next_command(self):
        rm = roadmap.load(self.root)
        path = self.root / commit.LEDGER
        with mock.patch.object(ledger, "fold", wraps=ledger.fold) as fold:
            with c.command_scope(), mock.patch.object(c, "file_key", return_value=("same",)):
                protocol.ensure_writable(self.root, rm)
                protocol.ensure_writable(self.root, rm)
                self.assertEqual(fold.call_count, 1)
                path.write_text(json.dumps(event("note", text="new event")) + "\n")
                protocol.ensure_writable(self.root, rm)
                self.assertEqual(fold.call_count, 2)
                path.write_text(json.dumps(event("note", text="old event")) + "\n")
                protocol.ensure_writable(self.root, rm)
                self.assertEqual(fold.call_count, 3)
            with c.command_scope():
                protocol.ensure_writable(self.root, rm)
            self.assertEqual(fold.call_count, 4)

    def test_immutable_json_cache_detects_tamper_and_does_not_share_mutable_results(self):
        path = self.root / "05_governance/reviews/data.json"
        path.write_text('{"items": [1]}\n')
        ref = {"path": "05_governance/reviews/data.json", "sha": c.sha(path)}
        with c.command_scope(), mock.patch.object(c, "file_key", return_value=("same",)):
            first = protocol.read_reference(self.root, ref)
            first["items"].append(2)
            self.assertEqual(protocol.read_reference(self.root, ref), {"items": [1]})
            with self.assertRaisesRegex(ValueError, "read bound"):
                protocol.read_reference(self.root, ref, 2)
            path.write_text('{"items": [2]}\n')
            with self.assertRaisesRegex(ValueError, "immutable evidence drift"):
                protocol.read_reference(self.root, ref)
        with c.command_scope(), self.assertRaisesRegex(ValueError, "immutable evidence drift"):
            protocol.read_reference(self.root, ref)

    def test_full_evidence_memo_budget_still_validates_without_caching(self):
        path = self.root / "05_governance/reviews/data.json"
        path.write_text('{"items": [1]}\n')
        ref = {"path": "05_governance/reviews/data.json", "sha": c.sha(path)}
        with (
            c.command_scope(),
            mock.patch.object(c, "MEMO_LIMIT", 1),
            mock.patch.object(protocol.json, "loads", wraps=json.loads) as loads,
        ):
            self.assertEqual(protocol.read_reference(self.root, ref), {"items": [1]})
            self.assertEqual(protocol.read_reference(self.root, ref), {"items": [1]})
            self.assertEqual(loads.call_count, 2)
            self.assertEqual(c.cache("json_evidence"), {})

    def test_refused_coded_and_intent_append_leave_no_new_json(self):
        prompt.coding(self.root, "M001-S01")
        path = self.root / "05_governance/reviews"
        before = set(path.rglob("*.json"))
        with mock.patch.object(ledger, "append", side_effect=ValueError("confirmed refusal")):
            self.assertEqual(self.cli("coded", "M001-S01")[0], 2)
        self.assertEqual(set(path.rglob("*.json")), before)
        self.assertEqual(self.cli("coded", "M001-S01")[0], 0)
        self.assertTrue(verify.run(self.root, "M001-S01", 10)[0]["ok"])
        (path / "pass.md").write_text(PASS_REPORT)
        self.assertEqual(self.cli("record", "05_governance/reviews/pass.md")[0], 0)
        before = set(path.rglob("*.json"))
        with mock.patch.object(ledger, "append", side_effect=ValueError("confirmed refusal")):
            self.assertEqual(self.cli("accept", "M001-S01", "--commit")[0], 2)
        self.assertEqual(set(path.rglob("*.json")), before)

    def test_artifact_rollback_preserves_existing_changed_and_uncertain_files(self):
        old = self.root / "05_governance/reviews/old.json"
        new = old.with_name("new.json")
        old.write_text("old\n")
        with self.assertRaises(ValueError), c.artifact_batch(self.root):
            c.artifact_text(old, "old\n")
            c.artifact_text(new, "new\n")
            new.write_text("owner changed it\n")
            raise ValueError("confirmed refusal")
        self.assertEqual(old.read_text(), "old\n")
        self.assertEqual(new.read_text(), "owner changed it\n")
        uncertain = old.with_name("uncertain.json")
        with self.assertRaises(ValueError), c.artifact_batch(self.root):
            c.artifact_text(uncertain, "evidence\n")
            with (self.root / commit.LEDGER).open("a") as stream:
                stream.write('{"partial":')
            raise ValueError("uncertain append")
        self.assertEqual(uncertain.read_text(), "evidence\n")

    def test_holistic_waiver_cli_requires_human_after_slice_acceptance(self):
        prompt.coding(self.root, "M001-S01")
        self.assertEqual(self.cli("coded", "M001-S01")[0], 0)
        self.assertTrue(verify.run(self.root, "M001-S01", 10)[0]["ok"])
        folder = self.root / "05_governance/reviews"
        (folder / "pass.md").write_text(PASS_REPORT)
        self.assertEqual(self.cli("record", "05_governance/reviews/pass.md")[0], 0)
        self.assertEqual(self.cli("accept", "M001-S01", "--commit")[0], 0)
        text = PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic")
        text = text.replace(
            "| --- | --- | --- | --- |",
            "| --- | --- | --- | --- |\n| M001-S01-F1 | P2 | waived_by_human | Waiver |",
        )
        (folder / "holistic.md").write_text(text)
        before = (self.root / commit.LEDGER).read_bytes()
        code, out = self.cli(
            "record",
            "05_governance/reviews/holistic.md",
            "--milestone",
            "M001",
            "--by",
            "architect",
        )
        self.assertEqual(code, 2)
        self.assertIn("requires --by human", out)
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
        code, out = self.cli(
            "record",
            "05_governance/reviews/holistic.md",
            "--milestone",
            "M001",
            "--by",
            "human",
        )
        self.assertEqual(code, 0, out)

    def test_pending_intent_freezes_all_ordinary_mutations(self):
        prompt.coding(self.root, "M001-S01")
        self.assertEqual(self.cli("coded", "M001-S01")[0], 0)
        self.assertTrue(verify.run(self.root, "M001-S01", 10)[0]["ok"])
        (self.root / "05_governance/reviews/pass.md").write_text(PASS_REPORT)
        self.assertEqual(self.cli("record", "05_governance/reviews/pass.md")[0], 0)
        with mock.patch.object(commit, "recover", side_effect=ValueError("interruption")):
            self.assertEqual(self.cli("accept", "M001-S01", "--commit")[0], 2)
        before = (self.root / commit.LEDGER).read_bytes()
        for args in (
            ("coded", "M001-S01"),
            ("accept", "M001-S01"),
            ("close", "M001"),
            ("record", "05_governance/reviews/pass.md"),
            ("reconcile",),
            ("reopen", "M001-S01", "--reason", "wait"),
            ("resolve", "M001-S01", "--reason", "wait", "--authority", "00_brief/decisions.md"),
            ("prompt", "M001-S01", "prompts/for_coding_agent/README.md"),
            ("index", "--output", "local_state/index.md"),
            ("attempt", "local_state/missing.json"),
            ("blocked", "M001-S01"),
            ("unblock", "M001-S01", "--reason", "wait"),
        ):
            with self.subTest(args=args):
                code, out = self.cli(*args)
                self.assertEqual(code, 2)
                self.assertIn("commit pending", out)
                self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
        with self.assertRaises(ValueError):
            prompt.coding(self.root, "M001-S01")
        with self.assertRaises(ValueError):
            verify.run(self.root, "M001-S01", 10)
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
