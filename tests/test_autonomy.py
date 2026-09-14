"""Optional run authority: shared folds and standalone durable recovery."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from test_prompts_v2 import fixture
from test_protocol_v2 import c, event, ledger, prompt, roadmap, verify
from test_scaffold import PASS_REPORT, run_git

ROOT = Path(__file__).resolve().parents[1]

PROFILE = {"schema": "frutlups.autonomy/1"}
LEDGER = "05_governance/ledger.jsonl"
UNITS = ("jobs", "transport_retries", "format_retries", "seconds")


def case_roadmap(case):
    rm = roadmap.load(ROOT)
    if case.get("declared", True):
        rm["autonomy"] = dict(PROFILE)
    options = case.get("roadmap", {})
    milestone = rm["milestones"][0]
    milestone["status"] = options.get("status", "active")
    milestone["holistic_review"] = options.get("holistic_review", True)
    original = milestone["slices"][0]
    milestone["slices"] = [
        {**copy.deepcopy(original), "id": sid} for sid in options.get("slices", ["M001-S01"])
    ]
    if options.get("second_milestone"):
        second = copy.deepcopy(milestone)
        second["id"] = "M002"
        second["status"] = "active"
        second["slices"] = [{**copy.deepcopy(original), "id": "M002-S01"}]
        rm["milestones"].append(second)
    return rm


class AutonomyCorpusTests(unittest.TestCase):
    def test_shared_profile_corpus(self):
        corpus = json.loads((ROOT / "tests/fixtures/autonomy_v1.json").read_text("utf-8"))
        self.assertEqual(corpus["schema"], "template.autonomy-conformance/1")
        names = [case["name"] for case in corpus["cases"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 30)
        for case in corpus["cases"]:
            with self.subTest(case=case["name"]):
                rm = case_roadmap(case)
                errors, _ = roadmap.validate(rm)
                self.assertEqual(errors, [])

                def fold(rows=case["events"], rm=rm):
                    for row in rows:
                        ledger._validate(row)
                    return ledger.fold(rows, rm)

                if not case["valid"]:
                    self.assertTrue(case["error"])
                    with self.assertRaises(ValueError) as failure:
                        fold()
                    self.assertIn(case["error"], str(failure.exception))
                    continue
                state = fold()
                for run_id, expected in case.get("expected", {}).items():
                    actual = state["runs"][run_id]
                    for key, value in expected.items():
                        self.assertEqual(actual[key], value, (case["name"], run_id, key))
                if "head" in case:
                    self.assertEqual(state["run_head"], case["head"])
                if "membership" in case:
                    self.assertEqual(state["run_membership"], case["membership"])

    def test_profile_declaration_is_exact_and_v2_only(self):
        for declaration, schema in (
            ({"schema": "frutlups.autonomy/2"}, "frutlups.roadmap/2"),
            ({**PROFILE, "reset": True}, "frutlups.roadmap/2"),
            ({}, "frutlups.roadmap/2"),
            (None, "frutlups.roadmap/2"),
            (PROFILE, "frutlups.roadmap/1"),
        ):
            with self.subTest(declaration=declaration, schema=schema):
                rm = roadmap.load(ROOT)
                rm.update(schema=schema, autonomy=declaration)
                self.assertTrue(roadmap.validate(rm)[0])
        self.assertNotIn("autonomy", roadmap.load(ROOT))


class AutonomyRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture(self.root)
        rm = roadmap.load(self.root)
        rm["autonomy"] = dict(PROFILE)
        (self.root / "roadmap.yaml").write_text(yaml.safe_dump(rm, sort_keys=False), "utf-8")
        self.approval = self.authority("admission", "Owner authorizes R1: four jobs, 100 seconds.")

    def authority(self, name, text):
        rel = f"05_governance/authority/{name}.md"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", "utf-8")
        return rel

    def cli(self, *args, env=None):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.root / "scripts/ledger.py"),
                "--root",
                str(self.root),
                *args,
            ],
            cwd=self.root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(env or {})},
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )

    def success(self, *args):
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def admit_args(self):
        return (
            "run",
            "admit",
            "M001",
            "--run-id",
            "R1",
            "--slice",
            "M001-S01",
            "--stop",
            "M001-S01",
            "--jobs",
            "4",
            "--seconds",
            "100",
            "--transport-retries",
            "1",
            "--format-retries",
            "1",
            "--max-corrective-rounds",
            "2",
            "--reason",
            "Owner admitted bounded work",
            "--authority",
            self.approval,
            "--by",
            "human",
        )

    def start(self, name="I1", **changes):
        value = event(
            "attempt_started",
            invocation=name,
            scope="M001-S01",
            round=1,
            role="probe",
            contract="b" * 64,
            allowance_seconds=40,
            retry="initial",
        )
        value.update(changes)
        self.attempt(value)
        return value

    def attempt(self, value):
        path = self.root / "local_state/attempt.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), "utf-8")
        return self.success("attempt", path.relative_to(self.root).as_posix())

    def state(self):
        # A genuinely new interpreter rebuilds all balances from durable bytes.
        code = (
            "import json,sys;from pathlib import Path;"
            "sys.path.insert(0,'scripts');import ledger,roadmap;"
            "s=ledger.fold(ledger.read(Path('05_governance/ledger.jsonl')),"
            "roadmap.load(Path('.')));"
            "fields=('revision','allowance','consumed','remaining','closed');"
            "print(json.dumps({k:{p:v[p] for p in fields}"
            "for k,v in s.get('runs',{}).items()}))"
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=self.root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_clean_tree_crash_config_edit_and_unknown_recovery(self):
        self.success(*self.admit_args())
        self.start()
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "-m", "Durable reservation before any launch")
        self.assertEqual(run_git(self.root, "status", "--porcelain").stdout.strip(), "")
        self.assertFalse((self.root / ".frutlups/runs").exists())
        before = (self.root / LEDGER).read_bytes()
        refusal = self.cli("coded", "M001-S01")
        self.assertNotEqual(refusal.returncode, 0)
        self.assertIn("unresolved invocation", refusal.stderr)
        self.assertEqual((self.root / LEDGER).read_bytes(), before)
        expected = dict(zip(UNITS, (3, 1, 1, 60)))
        self.assertEqual(self.state()["R1"]["remaining"], expected)
        (self.root / "frutlups.toml").write_text(
            "max_jobs = 999\nmax_wall_minutes = 999\n", "utf-8"
        )
        self.assertEqual(self.state()["R1"]["remaining"], expected)
        proof = self.authority("recovery", "Deterministic fixture: no child was launched.")
        self.attempt(
            event(
                "attempt_finished",
                invocation="I1",
                status="resolved",
                usage={"completeness": "unknown"},
                reason="Owner established safe child disposition",
                evidence=[{"path": proof, "sha": c.sha(self.root / proof)}],
                by="human",
            )
        )
        self.assertEqual(self.state()["R1"]["remaining"], expected)
        self.success("check")
        (self.root / proof).write_text("Changed disposition evidence\n", "utf-8")
        self.assertNotEqual(self.cli("check").returncode, 0)

    def test_stable_cli_grants_and_commit_authority_collection(self):
        self.success(*self.admit_args())
        prior = (self.root / LEDGER).read_bytes()
        self.assertNotEqual(self.cli(*self.admit_args()).returncode, 0)
        self.assertEqual((self.root / LEDGER).read_bytes(), prior)
        extra = self.authority("extension", "Owner adds two jobs and thirty seconds.")
        args = (
            "run",
            "extend",
            "R1",
            "--revision",
            "1",
            "--jobs",
            "2",
            "--seconds",
            "30",
            "--reason",
            "Explicit additional allowance",
            "--authority",
            extra,
            "--by",
            "human",
        )
        self.success(*args)
        after = (self.root / LEDGER).read_bytes()
        self.assertNotEqual(self.cli(*args).returncode, 0)
        self.assertEqual((self.root / LEDGER).read_bytes(), after)
        state = self.state()["R1"]
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["remaining"], dict(zip(UNITS, (6, 1, 1, 130))))
        events = ledger.read(self.root / LEDGER)
        paths = ledger._artifacts_for(self.root, events, "M001-S01")
        self.assertIn(self.approval, paths)
        self.assertIn(extra, paths)
        self.assertIn("R1", self.success("status").stdout)
        (self.root / extra).write_text("Altered authorization\n", "utf-8")
        self.assertNotEqual(self.cli("check").returncode, 0)

    def test_autonomous_seat_cannot_issue_grant_command(self):
        before = (self.root / LEDGER).read_bytes()
        result = self.cli(*self.admit_args(), env={"FRUTLUPS_SEAT": "coder"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / LEDGER).read_bytes(), before)

    def test_inactive_milestone_grant_refuses_without_writing(self):
        for status in ("planned", "done"):
            with self.subTest(status=status):
                rm = roadmap.load(self.root)
                rm["milestones"][0]["status"] = status
                if status == "planned":
                    second = copy.deepcopy(rm["milestones"][0])
                    second.update(id="M002", status="active")
                    second["slices"][0]["id"] = "M002-S01"
                    rm["milestones"].append(second)
                (self.root / "roadmap.yaml").write_text(yaml.safe_dump(rm), "utf-8")
                before = (self.root / LEDGER).read_bytes()
                result = self.cli(*self.admit_args())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("run admission requires active milestone", result.stderr)
                self.assertEqual((self.root / LEDGER).read_bytes(), before)

    def test_done_roadmap_replays_completed_history_but_cannot_admit(self):
        rm = roadmap.load(self.root)
        rm["milestones"][0]["holistic_review"] = False
        (self.root / "roadmap.yaml").write_text(yaml.safe_dump(rm), "utf-8")
        self.success(*self.admit_args())
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "-m", "Record active run before manual completion")
        prompt.coding(self.root, "M001-S01")
        self.success("coded", "M001-S01")
        self.assertTrue(verify.run(self.root, "M001-S01", 10)[0]["ok"])
        report = self.root / "05_governance/reviews/done-pass.md"
        report.write_text(PASS_REPORT, "utf-8")
        self.success("record", report.relative_to(self.root).as_posix())
        self.success("accept", "M001-S01")
        rm["milestones"][0]["status"] = "done"
        (self.root / "roadmap.yaml").write_text(yaml.safe_dump(rm), "utf-8")
        before = (self.root / LEDGER).read_bytes()
        self.success("check")
        self.success("status")
        args = ["R2" if value == "R1" else value for value in self.admit_args()]
        result = self.cli(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run admission requires active milestone", result.stderr)
        self.assertEqual((self.root / LEDGER).read_bytes(), before)

    def test_unfinished_verification_blocks_manual_verifier_and_recovers(self):
        self.success(*self.admit_args())
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "-m", "Record authority before verification")
        prompt.coding(self.root, "M001-S01")
        self.success("coded", "M001-S01")
        self.start("V1", role="verification", allowance_seconds=20)
        before = (self.root / LEDGER).read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.root / "scripts/verify.py"),
                "M001-S01",
                "--root",
                str(self.root),
            ],
            cwd=self.root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unresolved invocation", result.stderr)
        self.assertEqual((self.root / LEDGER).read_bytes(), before)
        self.assertFalse(
            (self.root / "05_governance/reviews/m001/M001-S01_r1_verification.json").exists()
        )
        proof = self.authority("verification-recovery", "Synthetic verifier was never launched.")
        self.attempt(
            event(
                "attempt_finished",
                invocation="V1",
                status="resolved",
                usage={"completeness": "unknown"},
                reason="Safe verifier disposition established",
                evidence=[{"path": proof, "sha": c.sha(self.root / proof)}],
                by="human",
            )
        )
        self.assertEqual(self.state()["R1"]["remaining"], dict(zip(UNITS, (4, 1, 1, 80))))
        self.success("check")

    def test_manual_handoff_reaches_stop_without_budget_operations(self):
        self.success(*self.admit_args())
        self.start()
        self.attempt(
            event(
                "attempt_finished",
                invocation="I1",
                status="completed",
                usage={"secs": 12, "completeness": "partial"},
            )
        )
        remaining = self.state()["R1"]["remaining"]
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "-m", "Record admitted authority before manual handoff")
        prompt.coding(self.root, "M001-S01")
        self.success("coded", "M001-S01")
        self.assertTrue(verify.run(self.root, "M001-S01", 10)[0]["ok"])
        report = self.root / "05_governance/reviews/manual-pass.md"
        report.write_text(PASS_REPORT, "utf-8")
        self.success("record", report.relative_to(self.root).as_posix())
        self.success("accept", "M001-S01")
        self.assertEqual(self.state()["R1"]["closed"], "boundary")
        self.assertEqual(self.state()["R1"]["remaining"], remaining)
        self.success("reopen", "M001-S01", "--reason", "New manually admitted scope")
        self.assertEqual(self.state()["R1"]["closed"], "boundary")
        self.success("check")


if __name__ == "__main__":
    unittest.main()
