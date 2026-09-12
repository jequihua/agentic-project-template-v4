"""Standalone /2 lifecycle, authority and immutable evidence integration tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_prompts_v2 import fixture
from test_scaffold import PASS_REPORT


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _common as c  # noqa: E402
import _commit as commit  # noqa: E402
import _findings as findings  # noqa: E402
import _protocol as protocol  # noqa: E402
import ledger  # noqa: E402
import prompt  # noqa: E402
import roadmap  # noqa: E402
import verify  # noqa: E402


def event(kind, **values):
    return {
        "schema": protocol.SCHEMA,
        "t": "2026-09-12T00:00:00Z",
        "by": "architect",
        "ev": kind,
        **values,
    }


def legacy_accepted():
    common = {
        "schema": "frutlups.ledger/1",
        "t": "2026-09-12T00:00:00Z",
        "by": "architect",
        "slice": "M001-S01",
        "round": 1,
    }
    return [
        {**common, "ev": "prompt", "path": "p.md", "sha": "a" * 64},
        {**common, "ev": "coded", "changed": []},
        {**common, "ev": "verified", "receipt": "r.json", "sha": "b" * 64, "ok": True},
        {
            **common,
            "ev": "reviewed",
            "report": "v.md",
            "sha": "c" * 64,
            "verdict": "pass",
            "open": [],
        },
        {**common, "ev": "accepted"},
    ]


class GrammarTests(unittest.TestCase):
    def test_shared_conformance_corpus(self):
        data = json.loads((ROOT / "tests/fixtures/protocol_v2.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "template.conformance/2")
        rm = roadmap.load(ROOT)
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                rm = roadmap.load(ROOT)
                if "holistic_review" in case:
                    rm["milestones"][0]["holistic_review"] = case["holistic_review"]
                if not case["valid"]:
                    with self.assertRaises(ValueError):
                        for row in case["events"]:
                            ledger._validate(row)
                        ledger.fold(case["events"], rm)
                    continue
                for row in case["events"]:
                    ledger._validate(row)
                state = ledger.fold(case["events"], rm)
                expected = case["expected"]
                current = state["slices"]["M001-S01"]
                self.assertEqual(current["step"], expected["step"])
                self.assertEqual(current["round"], expected["round"])
                if "holistic" in expected:
                    self.assertEqual(state["holistic"]["M001"]["step"], expected["holistic"])
                if "done" in expected:
                    self.assertEqual("M001" in state["milestones_done"], expected["done"])
                for key in ("intents", "checkpoints"):
                    if key in expected:
                        self.assertEqual(len(state[key]), expected[key])
        sample = data["finding_update"]
        self.assertEqual(findings.updates(sample["text"]), sample["expected"])
        manifest = data["commit_manifest"]
        parsed = commit._manifest(manifest["text"].encode(), manifest["intent"], manifest["scope"])
        self.assertEqual(parsed, manifest["expected"])

    def test_version_order_unknown_fields_and_new_writer_declaration(self):
        rm = roadmap.load(ROOT)
        old = legacy_accepted()
        state = ledger.fold(old + [event("note", text="explicit upgraded suffix")], rm)
        self.assertEqual(state["slices"]["M001-S01"]["step"], "accepted")
        with self.assertRaises(ValueError):
            ledger.fold([event("note", text="new")], {**rm, "schema": "frutlups.roadmap/1"})
        with self.assertRaises(ValueError):
            ledger.fold([event("note", text="new"), old[0]], rm)
        for bad in (event("note", text="x", unknown=True), event("made_up", text="x")):
            with self.subTest(event=bad["ev"]), self.assertRaises(ValueError):
                ledger._validate(bad)
        with self.assertRaises(ValueError):
            ledger._validate(event("prompt", slice="M001-S01", round=1, path="p.md", sha="a" * 64))
        invalid = event(
            "accepted",
            slice="M001-S01",
            round=1,
            commit_intent={
                "id": "arbitrary-name",
                "parent": "a" * 40,
                "manifest": {"path": "m.json", "sha": "a" * 64},
                "message": "Accept",
            },
        )
        with self.assertRaises(ValueError):
            ledger._validate(invalid)

    def test_legacy_prefix_bytes_are_preserved_when_appending_v2(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            path = root / commit.LEDGER
            original = (
                json.dumps(
                    {
                        "schema": "frutlups.ledger/1",
                        "ev": "note",
                        "by": "architect",
                        "t": "2026-09-12T00:00:00Z",
                        "text": "Legacy evidence stays exact",
                    }
                )
                + "\r\n"
            ).encode()
            path.write_bytes(original)
            ledger.append(
                path, {"ev": "note", "by": "architect", "text": "Upgraded"}, roadmap.load(root)
            )
            self.assertTrue(path.read_bytes().startswith(original))
            self.assertEqual(
                [e["schema"] for e in ledger.read(path)], ["frutlups.ledger/1", "frutlups.ledger/2"]
            )

    def test_unknown_attempt_blocks_dispatch_and_usage_stays_unknown(self):
        rm = roadmap.load(ROOT)
        start = event(
            "attempt_started",
            invocation="review-1",
            scope="M001-S01",
            round=1,
            role="reviewer",
            contract="a" * 64,
            allowance_seconds=60,
            retry="initial",
        )
        with self.assertRaisesRegex(ValueError, "unresolved invocation"):
            ledger.fold([start, {**start, "invocation": "review-2"}], rm)
        finish = event(
            "attempt_finished",
            invocation="review-1",
            status="completed",
            usage={"completeness": "unknown"},
        )
        state = ledger.fold([start, finish], rm)
        self.assertEqual(
            state["attempts"]["review-1"]["finish"]["usage"], {"completeness": "unknown"}
        )
        checkpoint = event(
            "review_checkpoint",
            invocation="review-1",
            scope="M001-S01",
            round=1,
            contract="a" * 64,
            report="review.md",
            sha="b" * 64,
            seat="reviewer",
        )
        self.assertIn("review-1", ledger.fold([start, finish, checkpoint], rm)["checkpoints"])
        for change in ({"round": 2}, {"scope": "M001"}, {"contract": "c" * 64}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ledger.fold([start, finish, {**checkpoint, **change}], rm)
        retry = {**start, "invocation": "review-2", "retry": "transport", "parent": "review-1"}
        for change in ({"scope": "M001"}, {"contract": "b" * 64}, {"round": 2}):
            with self.subTest(retry=change), self.assertRaises(ValueError):
                ledger.fold([start, finish, {**retry, **change}], rm)

    def test_holistic_block_resolution_needswork_and_explicit_close(self):
        rm = roadmap.load(ROOT)
        accepted = legacy_accepted()
        decision = event(
            "holistic_reviewed",
            milestone="M001",
            report="holistic.md",
            sha="d" * 64,
            verdict="blocked",
            open=["M001-S01-P2"],
        )
        state = ledger.fold(accepted + [decision], rm)
        self.assertEqual(state["holistic"]["M001"]["step"], "blocked")
        self.assertEqual(state["slices"]["M001-S01"]["step"], "accepted")
        with self.assertRaises(ValueError):
            ledger.fold(accepted + [decision, {**decision, "verdict": "pass", "open": []}], rm)
        resolution = event(
            "resolved",
            scope="M001",
            reason="Authority now recorded",
            authority=[{"path": "decision.md", "sha": "e" * 64}],
        )
        passed = {**decision, "verdict": "pass", "open": []}
        state = ledger.fold(accepted + [decision, resolution, passed], rm)
        self.assertEqual(state["holistic"]["M001"]["step"], "close_pending")
        self.assertNotIn("M001", state["milestones_done"])
        close = event("milestone_done", milestone="M001", holistic_report="holistic.md")
        self.assertIn("M001", ledger.fold(accepted + [passed, close], rm)["milestones_done"])
        state = ledger.fold(accepted + [{**decision, "verdict": "needs_work"}], rm)
        self.assertEqual(state["slices"]["M001-S01"]["step"], "fix")
        self.assertEqual(state["slices"]["M001-S01"]["round"], 2)
        with self.assertRaises(ValueError):
            ledger.fold(accepted + [close], rm)


class ManualIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="template-protocol-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        fixture(self.root)

    def cli(self, *args):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.root / "scripts/ledger.py"),
                "--root",
                str(self.root),
                *args,
            ],
            capture_output=True,
            timeout=120,
        )

    def success(self, *args):
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result

    def state(self):
        return ledger.fold(ledger.read(self.root / commit.LEDGER), roadmap.load(self.root))

    def test_blocked_edits_resolution_and_notes_identity(self):
        prompt.coding(self.root, "M001-S01")
        (self.root / "07_app/partial.py").write_text("answer = 41\n")
        notes = self.root / "05_governance/reviews/coder.md"
        notes.write_text("Retained implementation awaits an explicit authority decision.\n")
        self.success(
            "blocked",
            "M001-S01",
            "--requirement",
            "acceptance 1",
            "--reason",
            "Experiment allowance absent",
            "--actor",
            "human",
            "--action",
            "Record allowance",
            "--notes",
            "05_governance/reviews/coder.md",
        )
        state = self.state()
        self.assertEqual(state["slices"]["M001-S01"]["step"], "blocked")
        events = ledger.read(self.root / commit.LEDGER)
        coded = next(e for e in events if e["ev"] == "coded")
        self.assertEqual(coded["result"], "blocked_authority")
        self.assertEqual(coded["notes_sha"], c.sha(notes))
        self.assertFalse(any(e["ev"] == "verified" for e in events))
        self.assertEqual((self.root / "07_app/partial.py").read_text(), "answer = 41\n")
        self.success(
            "resolve",
            "M001-S01",
            "--reason",
            "Allowance approved in decision register",
            "--authority",
            "00_brief/decisions.md",
            "--by",
            "architect",
        )
        self.assertEqual(self.state()["slices"]["M001-S01"]["step"], "fix")
        self.assertEqual(self.state()["slices"]["M001-S01"]["round"], 2)
        notes.write_text("Altered after recording\n")
        events = ledger.read(self.root / commit.LEDGER)
        errors = ledger.check(self.root, roadmap.load(self.root), events)
        self.assertTrue(any("drift" in message or "hash" in message for message in errors))

    def test_illegal_blocker_edits_are_preserved_and_not_recorded_as_valid(self):
        prompt.coding(self.root, "M001-S01")
        path = self.root / "00_brief/decisions.md"
        original = path.read_bytes()
        path.write_bytes(original + b"\nUnapproved coder authority change.\n")
        before = (self.root / commit.LEDGER).read_bytes()
        result = self.cli(
            "blocked",
            "M001-S01",
            "--requirement",
            "acceptance 1",
            "--reason",
            "Needs scope",
            "--actor",
            "architect",
            "--action",
            "Review boundary",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("boundary", result.stderr.decode())
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
        self.assertTrue(path.read_bytes().endswith(b"Unapproved coder authority change.\n"))

    def test_writer_lock_excludes_second_process_and_status_remains_readable(self):
        before = (self.root / commit.LEDGER).read_bytes()
        with c.writer_lock(self.root):
            blocked = self.cli("reconcile")
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("another writer", blocked.stderr.decode())
            self.success("status")
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
        # A leftover lock filename is not ownership after the OS lock releases.
        self.success("reconcile")

    def test_unresolved_attempt_refuses_clean_tree_coder_until_attribution(self):
        path = self.root / "local_state/attempt.json"
        start = event(
            "attempt_started",
            invocation="lost-coder",
            scope="M001-S01",
            round=1,
            role="coder",
            contract="a" * 64,
            allowance_seconds=60,
            retry="initial",
        )
        path.write_text(json.dumps(start))
        self.success("attempt", "local_state/attempt.json")
        before = (self.root / commit.LEDGER).read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.root / "scripts/prompt.py"),
                "M001-S01",
                "--root",
                str(self.root),
            ],
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unresolved invocation", result.stderr.decode())
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
        self.success("status")
        authority = self.root / "00_brief/decisions.md"
        finish = event(
            "attempt_finished",
            invocation="lost-coder",
            status="resolved",
            by="human",
            reason="Owned process exited; lost output remains unknown",
            usage={"completeness": "unknown"},
            evidence=[{"path": "00_brief/decisions.md", "sha": c.sha(authority)}],
        )
        path.write_text(json.dumps(finish))
        self.success("attempt", "local_state/attempt.json")
        self.assertEqual(
            self.state()["attempts"]["lost-coder"]["finish"]["usage"], {"completeness": "unknown"}
        )

    @unittest.skipUnless(
        os.environ.get("TEMPLATE_TEST_LEGACY_RUNNER"),
        "set TEMPLATE_TEST_LEGACY_RUNNER for optional paired legacy admission",
    )
    def test_installed_legacy_runner_refuses_upgrade_without_project_mutation(self):
        source = Path(os.environ["TEMPLATE_TEST_LEGACY_RUNNER"]) / "src"
        program = (
            "import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
            "from frutlups.roadmap import load;load(Path(sys.argv[2])/'roadmap.yaml')"
        )
        before = c.status_bytes(self.root), (self.root / commit.LEDGER).read_bytes()
        result = subprocess.run(
            [sys.executable, "-B", "-c", program, str(source), str(self.root)],
            capture_output=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema must be frutlups.roadmap/1", result.stderr.decode())
        after = c.status_bytes(self.root), (self.root / commit.LEDGER).read_bytes()
        self.assertEqual(after, before)

    def test_zero_change_manual_loop_and_pending_commit_freeze(self):
        prompt.coding(self.root, "M001-S01")
        self.success("coded", "M001-S01")
        self.assertEqual(self.state()["slices"]["M001-S01"]["changed"], [])
        self.assertTrue(verify.run(self.root, "M001-S01", 10)[0]["ok"])
        report = self.root / "05_governance/reviews/pass.md"
        report.write_text(PASS_REPORT)
        self.success("record", "05_governance/reviews/pass.md")
        # Fault before Git staging keeps one approval and the exact recoverable intent.
        real = commit.recover
        with mock.patch.object(commit, "recover", side_effect=ValueError("injected interruption")):
            result = ledger.main(["--root", str(self.root), "accept", "M001-S01", "--commit"])
            self.assertEqual(result, 2)
        events = ledger.read(self.root / commit.LEDGER)
        self.assertEqual(sum(e["ev"] == "accepted" for e in events), 1)
        before = (self.root / commit.LEDGER).read_bytes()
        result = self.cli("reopen", "M001-S01", "--reason", "must wait for commit")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
        self.assertIn("pending", self.success("status").stdout.decode())
        rows = real(self.root, events, roadmap.load(self.root), execute=True)
        self.assertEqual(rows[0]["state"], "completed")
        self.assertEqual((self.root / commit.LEDGER).read_bytes(), before)
        self.assertEqual(self.success("check").returncode, 0)

    def test_holistic_block_record_resolve_review_and_close_in_fresh_commands(self):
        prompt.coding(self.root, "M001-S01")
        self.success("coded", "M001-S01")
        self.assertTrue(verify.run(self.root, "M001-S01", 10)[0]["ok"])
        review = self.root / "05_governance/reviews/slice.md"
        review.write_text(PASS_REPORT)
        self.success("record", "05_governance/reviews/slice.md")
        self.success("accept", "M001-S01")
        base = PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic")
        blocked = base.replace(
            "| --- | --- | --- | --- |",
            "| --- | --- | --- | --- |\n| M001-S01-F1 | P2 | open | Human authority needed |",
        ).replace("Objective status: achieved", "Objective status: indeterminate")
        blocked = blocked.replace(
            "Verdict: pass - next: accept the slice",
            "Verdict: blocked - next: record missing authority",
        )
        path = self.root / "05_governance/reviews/holistic-blocked.md"
        path.write_text(blocked)
        self.success("record", "05_governance/reviews/holistic-blocked.md", "--milestone", "M001")
        self.assertEqual(self.state()["holistic"]["M001"]["step"], "blocked")
        self.assertEqual(self.state()["slices"]["M001-S01"]["step"], "accepted")
        self.success(
            "resolve",
            "M001",
            "--reason",
            "Human authority supplied",
            "--authority",
            "00_brief/decisions.md",
            "--by",
            "human",
        )
        updates = (
            "## Finding updates\n| source | sha | id | disposition | related |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"| 05_governance/reviews/holistic-blocked.md | {c.sha(path)} | M001-S01-F1 | "
            "closed_by_review | - |\n\n"
        )
        passed = self.root / "05_governance/reviews/holistic-pass.md"
        passed.write_text(base.replace("## Closure Decision", updates + "## Closure Decision"))
        self.success("record", "05_governance/reviews/holistic-pass.md", "--milestone", "M001")
        self.assertEqual(self.state()["holistic"]["M001"]["step"], "close_pending")
        self.assertNotIn("M001", self.state()["milestones_done"])
        self.success("close", "M001", "--commit")
        self.assertIn("M001", self.state()["milestones_done"])
        self.assertEqual(c.status_bytes(self.root), b"")
        self.success("check")


class FindingsTests(unittest.TestCase):
    def test_explicit_partial_closure_and_projection_preserve_architect_prose(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            directory = root / "05_governance/reviews"
            directory.mkdir(parents=True)
            backlog = root / "05_governance/backlog.md"
            backlog.write_text("# Architect backlog\n\nKeep this independent plan.\n")
            original = "Keep this independent plan."
            report = PASS_REPORT.replace(
                "| --- | --- | --- | --- |",
                "| --- | --- | --- | --- |\n| OLD-1 | P3 | carried | First retained item |\n"
                "| OLD-2 | P3 | carried | Second retained item |",
            )
            first = directory / "first.md"
            first.write_text(report)
            rel = first.relative_to(root).as_posix()
            events = [
                event(
                    "reviewed",
                    slice="M001-S01",
                    round=1,
                    report=rel,
                    sha=c.sha(first),
                    verdict="pass",
                    open=[],
                )
            ]
            second = directory / "second.md"
            second.write_text(PASS_REPORT)
            next_event = event(
                "reviewed",
                slice="M001-S02",
                round=1,
                report=second.relative_to(root).as_posix(),
                sha=c.sha(second),
                verdict="pass",
                open=[],
            )
            projected, _ = findings.project(root, events + [next_event])
            self.assertEqual({v["disposition"] for v in projected.values()}, {"carried"})
            updates = (
                "\n## Finding updates\n| source | sha | id | disposition | related |\n"
                "| --- | --- | --- | --- | --- |\n"
                f"| {rel} | {c.sha(first)} | OLD-1 | closed_by_review | OLD-2 |\n"
            )
            updated_report = PASS_REPORT.replace(
                "## Closure Decision", updates + "\n## Closure Decision"
            )
            second.write_text(updated_report)
            next_event["sha"] = c.sha(second)
            events.append(next_event)
            findings.reconcile(root, events)
            self.assertIn(original, backlog.read_text())
            generated = backlog.read_bytes()
            findings.reconcile(root, events)
            self.assertEqual(backlog.read_bytes(), generated)
            projected, _ = findings.project(root, events)
            self.assertEqual(
                {v["id"]: v["disposition"] for v in projected.values()},
                {"OLD-1": "closed_by_review", "OLD-2": "carried"},
            )
            waived = updated_report.replace("closed_by_review", "waived_by_human")
            second.write_text(waived)
            events[-1]["sha"] = c.sha(second)
            with self.assertRaisesRegex(ValueError, "waiver requires"):
                findings.project(root, events)
            events[-1]["by"] = "human"
            self.assertEqual(
                findings.project(root, events)[0][(rel, c.sha(first), "OLD-1")]["disposition"],
                "waived_by_human",
            )


if __name__ == "__main__":
    unittest.main()
