"""Rehashed semantic forgeries and active evidence drift must fail closed."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _common as c
import _integrity
import ledger
import prompt
import roadmap
import verify
from test_scaffold import PASS_REPORT, git_init, project_copy, quiet_call, run_git, set_full
from test_verification_v2 import awaiting


def verified(root):
    awaiting(root, "pass", v2=True)
    verify.run(root, "M001-S01", 10)
    events = ledger.read(root / "05_governance/ledger.jsonl")
    rm = roadmap.load(root)
    current = ledger.fold(events, rm)["slices"]["M001-S01"]
    return events, rm, current


def replace_ref(root, events, ev, key, mutate):
    forged = copy.deepcopy(events)
    event = next(item for item in reversed(forged) if item["ev"] == ev)
    ref = {"path": event[key], "sha": event["sha"]} if key == "receipt" else event[key]
    value = json.loads((root / ref["path"]).read_text(encoding="utf-8"))
    mutate(value)
    rel = f"05_governance/reviews/m001/forged_{ev}.json"
    c.atomic_text(root / rel, json.dumps(value))
    if key == "receipt":
        event.update(receipt=rel, sha=c.sha(root / rel))
    else:
        event[key] = {"path": rel, "sha": c.sha(root / rel)}
    return forged


class IntegrityTests(unittest.TestCase):
    def test_shared_accepted_path_closes_and_reopened_scope_reobserves_new_identity(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            set_full(root, "pass")
            plan = root / "roadmap.yaml"
            rm = yaml.safe_load(plan.read_text(encoding="utf-8"))
            rm["schema"] = "frutlups.roadmap/2"
            second = copy.deepcopy(rm["milestones"][0]["slices"][0])
            second["id"] = "M001-S02"
            rm["milestones"][0]["slices"].append(second)
            plan.write_text(yaml.safe_dump(rm, sort_keys=False), encoding="utf-8")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-qm", "baseline")

            def command(*args):
                self.assertEqual(quiet_call(ledger.main, ["--root", str(root), *args]), 0, args)

            def finish(sid, round_no, value):
                prompt.coding(root, sid)
                if value is not None:
                    (root / "07_app/shared.txt").write_text(value, encoding="utf-8")
                command("coded", sid)
                self.assertTrue(verify.run(root, sid, 10)[0]["ok"])
                prompt.review(root, sid)
                rel = f"05_governance/reviews/m001/{sid}_r{round_no}_review.md"
                c.atomic_text(
                    root / rel,
                    PASS_REPORT.replace("M001-S01", sid).replace("round 1", f"round {round_no}"),
                )
                command("record", rel)
                command("accept", sid)
                run_git(root, "add", ".")
                run_git(root, "commit", "-qm", "accepted " + sid)

            def close(number):
                rel = f"05_governance/reviews/m001/M001_h{number}_review.md"
                c.atomic_text(
                    root / rel, PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic")
                )
                command("record", rel, "--milestone", "M001")
                command("close", "M001")
                run_git(root, "add", ".")
                run_git(root, "commit", "-qm", "closed milestone")

            finish("M001-S01", 1, "first\n")
            finish("M001-S02", 1, "second\n")
            close(1)
            command("reopen", "M001-S01", "--reason", "observe integrated shared implementation")
            finish("M001-S01", 2, None)
            events = ledger.read(root / "05_governance/ledger.jsonl")
            latest = next(event for event in reversed(events) if event["ev"] == "coded")
            shared = next(row for row in latest["changed"] if row["path"] == "07_app/shared.txt")
            self.assertEqual(shared["sha"], c.sha(root / "07_app/shared.txt"))
            self.assertEqual((root / "07_app/shared.txt").read_text(), "second\n")
            close(2)
            self.assertEqual(
                _integrity.errors(root, ledger.read(root / "05_governance/ledger.jsonl"), rm), []
            )

    def test_all_review_records_validate_identity_decision_and_waiver_actor(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            events, rm, _ = verified(root)
            rel = "05_governance/reviews/m001/review.md"
            path = root / rel
            c.atomic_text(path, PASS_REPORT)
            base = {
                "schema": "frutlups.ledger/2",
                "t": c.now(),
                "ev": "reviewed",
                "by": "architect",
                "slice": "M001-S01",
                "round": 1,
                "report": rel,
                "sha": c.sha(path),
                "verdict": "pass",
                "open": [],
            }
            self.assertEqual(_integrity.errors(root, events + [base], rm), [])
            wrong = {**base, "verdict": "blocked"}
            self.assertIn(
                "verdict/open findings mismatch",
                "\n".join(_integrity.errors(root, events + [wrong], rm)),
            )
            wrong = {**base, "slice": "M001-S02"}
            self.assertIn(
                "review identity mismatch", "\n".join(_integrity.errors(root, events + [wrong], rm))
            )
            waived = PASS_REPORT.replace(
                "| --- | --- | --- | --- |",
                "| --- | --- | --- | --- |\n"
                "| M001-S01-F1 | P2 | waived_by_human | Explicit exception |",
            )
            c.atomic_text(path, waived)
            record = {**base, "sha": c.sha(path)}
            for actor in ("architect", "frutlups"):
                candidate = {**record, "by": actor}
                self.assertIn(
                    "waiver requires", "\n".join(_integrity.errors(root, events + [candidate], rm))
                )
                checkpoint = {
                    "schema": "frutlups.ledger/2",
                    "t": c.now(),
                    "ev": "review_checkpoint",
                    "by": actor,
                    "scope": "M001-S01",
                    "round": 1,
                    "report": rel,
                    "sha": c.sha(path),
                    "invocation": "reviewer-one",
                    "contract": "0" * 64,
                    "seat": "reviewer",
                }
                self.assertIn(
                    "waiver requires", "\n".join(_integrity.errors(root, events + [checkpoint], rm))
                )
            self.assertEqual(_integrity.errors(root, events + [{**record, "by": "human"}], rm), [])
            c.atomic_text(
                path,
                waived.replace("M001-S01 round 1", "M001 round holistic").replace(
                    "M001-S01-F1", "unscoped-F1"
                ),
            )
            holistic = {
                "schema": "frutlups.ledger/2",
                "t": c.now(),
                "ev": "holistic_reviewed",
                "by": "human",
                "milestone": "M001",
                "report": rel,
                "sha": c.sha(path),
                "verdict": "pass",
                "open": [],
            }
            self.assertIn(
                "affected slice", "\n".join(_integrity.errors(root, events + [holistic], rm))
            )

    def test_valid_receipt_and_exact_report_exception_allow_review(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            events, rm, current = verified(root)
            self.assertEqual(_integrity.errors(root, events, rm), [])
            _integrity.require_active(root, current, events)
            report = "05_governance/reviews/m001/new_review.md"
            (root / report).write_text("prospective report", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unrecorded product"):
                _integrity.require_active(root, current, events)
            _integrity.require_active(root, current, events, extra=[report])

    def test_rehashed_receipt_cannot_change_command_manifest_or_verdict(self):
        cases = [
            (lambda value: value["commands"][0].update(exit=9), "ok contradicts"),
            (
                lambda value: value["commands"][0].update(argv=["python", "other.py"]),
                "frozen verification",
            ),
            (lambda value: value["witness"].update(stable=False), "stability contradiction"),
            (lambda value: value["manifest"].update(sha="0" * 64), "manifest does not match"),
            (lambda value: value.update(observation="clean_checkout"), "observation differs"),
            (lambda value: value["runtime"].update(sha="0" * 64), "runtime identity hash"),
            (lambda value: value["commands"][0].update(secs=float("nan")), "duration"),
            (lambda value: value.update(extra_authority=True), "receipt fields"),
        ]
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            events, rm, _ = verified(root)
            for change, expected in cases:
                with self.subTest(expected=expected):
                    forged = replace_ref(root, events, "verified", "receipt", change)
                    self.assertIn(expected, "\n".join(_integrity.errors(root, forged, rm)))

    def test_rehashed_envelope_and_non_cumulative_manifest_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            events, rm, _ = verified(root)
            forged = replace_ref(
                root, events, "prompt", "envelope", lambda value: value.update(extra=True)
            )
            self.assertIn("invalid envelope fields", "\n".join(_integrity.errors(root, forged, rm)))
            forged = replace_ref(
                root, events, "coded", "manifest", lambda value: value.update(changed=[])
            )
            self.assertIn(
                "cumulative recorded change", "\n".join(_integrity.errors(root, forged, rm))
            )

    def test_nested_outcome_evidence_remains_immutable(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            events, rm, _ = verified(root)
            rel = "05_governance/reviews/m001/retained.txt"
            (root / rel).write_text("original evidence", encoding="utf-8")
            outcome = {
                "schema": "frutlups.outcome/2",
                "slice": "M001-S01",
                "round": 1,
                "invocation": "manual-observation",
                "outcome": "implemented",
                "requirement": "sample gate",
                "reason": "implementation observed",
                "actor": "",
                "action": "",
                "remaining": [],
                "evidence": [{"path": rel, "sha": c.sha(root / rel)}],
                "authority": [],
            }
            path = root / "05_governance/reviews/m001/outcome.json"
            c.atomic_text(path, json.dumps(outcome))
            changed = copy.deepcopy(events)
            coded = next(item for item in changed if item["ev"] == "coded")
            coded["outcome"] = {"path": path.relative_to(root).as_posix(), "sha": c.sha(path)}
            self.assertEqual(_integrity.errors(root, changed, rm), [])
            (root / rel).write_text("changed evidence", encoding="utf-8")
            self.assertIn(
                "retained evidence drift", "\n".join(_integrity.errors(root, changed, rm))
            )

    def test_raw_bytes_new_file_index_and_head_drift_refuse_before_acceptance(self):
        cases = [
            (
                lambda root: (root / "07_app/product.txt").write_bytes(
                    b"before\n"
                    if b"\r\n" in (root / "07_app/product.txt").read_bytes()
                    else b"before\r\n"
                ),
                "raw product",
            ),
            (lambda root: (root / "unrecorded.txt").write_text("extra"), "unrecorded product"),
            (lambda root: run_git(root, "add", "07_app/product.txt"), "index changed"),
            (
                lambda root: run_git(root, "commit", "--allow-empty", "-m", "unexpected"),
                "HEAD changed",
            ),
        ]
        for change, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                events, _, current = verified(root)
                change(root)
                with self.assertRaisesRegex(ValueError, expected):
                    _integrity.require_active(root, current, events)


if __name__ == "__main__":
    unittest.main()
