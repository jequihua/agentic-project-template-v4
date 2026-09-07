from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from test_scaffold import PASS_REPORT, git_init, project_copy, quiet_call, run_git, set_full


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _common as common  # noqa: E402
import _evidence as evidence  # noqa: E402
import front_repo  # noqa: E402
import hermetic_verification as hermetic  # noqa: E402
import ledger  # noqa: E402
import prompt  # noqa: E402
import roadmap  # noqa: E402
import verify  # noqa: E402


SHA = "a" * 64
BLOCKED_REPORT = """# Review: M001-S01 round 1

## Findings
| id | severity | disposition | summary |
| --- | --- | --- | --- |
| M001-S01-R1-F1 | P1 | open | external decision required |

## Closure Decision
Objective status: indeterminate
Objective evidence: The owner must resolve the named decision.

## Verdict
Verdict: blocked - next: ask the owner
"""


def needs_report(round_no: int) -> str:
    return (
        PASS_REPORT.replace("round 1", f"round {round_no}")
        .replace(
            "| --- | --- | --- | --- |",
            "| --- | --- | --- | --- |\n"
            f"| M001-S01-R{round_no}-F1 | P1 | open | correct round {round_no} |",
        )
        .replace(
            "Verdict: pass - next: accept the slice",
            "Verdict: needs_work - next: correct the finding",
        )
    )


def append_accepted(root: Path, sid: str) -> None:
    rm = roadmap.load(root)
    path = root / "05_governance/ledger.jsonl"
    base = {"by": "architect", "slice": sid, "round": 1}
    events = [
        {**base, "ev": "prompt", "path": f"prompts/{sid}.md", "sha": SHA},
        {**base, "ev": "coded", "changed": []},
        {**base, "ev": "verified", "receipt": f"reviews/{sid}.json", "sha": SHA, "ok": True},
        {
            **base,
            "ev": "reviewed",
            "report": f"reviews/{sid}.md",
            "sha": SHA,
            "verdict": "pass",
            "open": [],
        },
        {**base, "ev": "accepted"},
    ]
    for event in events:
        ledger.append(path, event, rm)


def add_second_slice(root: Path) -> None:
    path = root / "roadmap.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    second = json.loads(json.dumps(data["milestones"][0]["slices"][0]))
    second.update({"id": "M001-S02", "title": "Second slice"})
    data["milestones"][0]["slices"].append(second)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n")


def prepare_real_loop(root: Path) -> None:
    project_copy(root)
    set_full(root, "raise SystemExit(0)")
    git_init(root)
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "start")


class EvidenceHashTests(unittest.TestCase):
    def test_text_line_endings_are_normalized_but_binary_bytes_are_raw(self) -> None:
        self.assertEqual(
            common.evidence_sha_bytes(b"first\nsecond\n"),
            common.evidence_sha_bytes(b"first\r\nsecond\r\n"),
        )
        self.assertNotEqual(
            common.evidence_sha_bytes(b"first\rsecond\n"),
            common.evidence_sha_bytes(b"first\nsecond\n"),
        )
        self.assertNotEqual(
            common.evidence_sha_bytes(b"\x00first\r\n"), common.evidence_sha_bytes(b"\x00first\n")
        )

    def test_file_and_git_blob_share_normalized_evidence_identity(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            path = root / "evidence.md"
            path.write_bytes(b"first\nsecond\n")
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "seed")
            path.write_bytes(b"first\r\nsecond\r\n")
            blob = common.git(root, "show", "HEAD:evidence.md").stdout
            self.assertEqual(common.sha(path), common.evidence_sha_bytes(blob))

    def test_streaming_hash_normalizes_crlf_across_a_chunk_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "boundary.txt"
            data = b"x" * (common.HASH_CHUNK - 1) + b"\r\nlast\r"
            path.write_bytes(data)
            self.assertEqual(common.sha(path), common.evidence_sha_bytes(data))

    def test_crlf_evidence_survives_acceptance_and_a_fresh_clone(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            source = base / "source"
            clone = base / "clone"
            project_copy(source)
            add_second_slice(source)
            set_full(source, "raise SystemExit(0)")
            git_init(source)
            run_git(source, "config", "core.autocrlf", "true")
            run_git(source, "add", ".")
            run_git(source, "commit", "-m", "start")

            prompt.coding(source, "M001-S01")
            (source / "07_app/feature.txt").write_bytes(b"done\r\n")
            self.assertEqual(
                quiet_call(ledger.main, ["--root", str(source), "coded", "M001-S01"]),
                0,
            )
            self.assertTrue(verify.run(source, "M001-S01", 10)[0]["ok"])
            prompt.review(source, "M001-S01")
            report = source / "05_governance/reviews/m001/M001-S01_r1_review.md"
            report.write_bytes(PASS_REPORT.replace("\n", "\r\n").encode())
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    ["--root", str(source), "record", report.relative_to(source).as_posix()],
                ),
                0,
            )
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    ["--root", str(source), "accept", "M001-S01", "--commit"],
                ),
                0,
            )

            subprocess.run(
                ["git", "-c", "core.autocrlf=false", "clone", "-q", str(source), str(clone)],
                check=True,
                capture_output=True,
            )
            events = ledger.read(clone / "05_governance/ledger.jsonl")
            self.assertEqual(ledger.check(clone, roadmap.load(clone), events), [])
            self.assertTrue((clone / prompt.coding(clone, "M001-S02")).is_file())


class LedgerRemediationTests(unittest.TestCase):
    def test_holistic_carried_p3_reaches_backlog_once(self) -> None:
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                project_copy(root)
                append_accepted(root, "M001-S01")
                backlog = root / "05_governance/backlog.md"
                line = "- M001-H1-P3: polish later"
                if existing:
                    backlog.write_text(backlog.read_text(encoding="utf-8") + line + "\n")
                report = root / "05_governance/reviews/m001/M001_holistic_review.md"
                report.parent.mkdir(parents=True, exist_ok=True)
                text = PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic").replace(
                    "| --- | --- | --- | --- |",
                    "| --- | --- | --- | --- |\n| M001-H1-P3 | P3 | carried | polish later |",
                )
                report.write_text(text, encoding="utf-8")
                args = [
                    "--root",
                    str(root),
                    "record",
                    report.relative_to(root).as_posix(),
                    "--milestone",
                    "M001",
                ]
                self.assertEqual(quiet_call(ledger.main, args), 0)
                self.assertEqual(backlog.read_text(encoding="utf-8").splitlines().count(line), 1)
                before = backlog.read_bytes()
                # A completed milestone cannot be recorded twice; refusal adds nothing.
                self.assertEqual(quiet_call(ledger.main, args), 2)
                self.assertEqual(backlog.read_bytes(), before)

    def test_holistic_backlog_is_unchanged_when_append_fails(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            append_accepted(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001_holistic_review.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            text = PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic").replace(
                "| --- | --- | --- | --- |",
                "| --- | --- | --- | --- |\n| M001-H1-P3 | P3 | carried | polish later |",
            )
            report.write_text(text, encoding="utf-8")
            backlog = root / "05_governance/backlog.md"
            before = backlog.read_bytes()
            with mock.patch.object(ledger, "append", side_effect=ValueError("refused")):
                self.assertEqual(
                    quiet_call(
                        ledger.main,
                        [
                            "--root",
                            str(root),
                            "record",
                            report.relative_to(root).as_posix(),
                            "--milestone",
                            "M001",
                        ],
                    ),
                    2,
                )
            self.assertEqual(backlog.read_bytes(), before)

    def test_review_prompt_artifact_is_neutral_validated_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            prompt.coding(root, "M001-S01")
            (root / "07_app/feature.txt").write_text("done\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            verify.run(root, "M001-S01", 10)
            rel = prompt.review(root, "M001-S01")
            events = ledger.read(root / "05_governance/ledger.jsonl")
            artifact = events[-1]
            self.assertEqual(
                (artifact["ev"], artifact["scope"], artifact["round"], artifact["role"]),
                ("artifact", "M001-S01", 1, "review_prompt"),
            )
            state = ledger.fold(events, roadmap.load(root))["slices"]["M001-S01"]
            self.assertEqual((state["step"], state["round"]), ("reviewing", 1))
            (root / rel).write_text("tampered\n", encoding="utf-8")
            self.assertIn(f"drift: {rel}", ledger.artifact_errors(root, events))

        base = {
            "schema": ledger.SCHEMA,
            "t": "2026-09-02T12:00:00Z",
            "ev": "artifact",
            "by": "architect",
            "scope": "M001-S01",
            "round": 1,
            "role": "review_prompt",
            "path": "prompts/for_review_agent/review.md",
            "sha": SHA,
        }
        for changes in (
            {"by": "human"},
            {"scope": "M001", "round": 1},
            {"role": "holistic_prompt"},
            {"round": 0},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaisesRegex(ValueError, "artifact|round"),
            ):
                ledger._validate({**base, **changes})

    def test_out_of_order_artifact_does_not_change_the_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            path = root / "05_governance/ledger.jsonl"
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "out of order"):
                ledger.append(
                    path,
                    {
                        "ev": "artifact",
                        "by": "architect",
                        "scope": "M001-S01",
                        "round": 1,
                        "role": "review_prompt",
                        "path": "prompts/for_review_agent/review.md",
                        "sha": SHA,
                    },
                    roadmap.load(root),
                )
            self.assertEqual(path.read_bytes(), before)

    def test_append_folds_candidate_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            rm = roadmap.load(root)
            path = root / "05_governance/ledger.jsonl"
            before = path.read_bytes()
            invalid = {
                "ev": "coded",
                "by": "architect",
                "slice": "M001-S01",
                "round": 1,
                "changed": [],
            }
            with self.assertRaisesRegex(ValueError, "out of order"):
                ledger.append(path, invalid, rm)
            self.assertEqual(path.read_bytes(), before)

    def test_blocked_slice_can_be_unblocked_with_preserved_context(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            prompt.coding(root, "M001-S01")
            (root / "07_app/feature.txt").write_text("done\n", encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "coded",
                        "M001-S01",
                    ],
                ),
                0,
            )
            self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
            prompt.review(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001-S01_r1_review.md"
            report.write_text(BLOCKED_REPORT, encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "record",
                        report.relative_to(root).as_posix(),
                    ],
                ),
                0,
            )
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "unblock",
                        "M001-S01",
                        "--reason",
                        "owner supplied the decision",
                        "--by",
                        "architect",
                    ],
                ),
                0,
            )
            state = ledger.fold(
                ledger.read(root / "05_governance/ledger.jsonl"), roadmap.load(root)
            )["slices"]["M001-S01"]
            self.assertEqual((state["step"], state["round"]), ("fix", 2))
            self.assertEqual(state["open"], ["M001-S01-R1-F1"])
            text = (root / prompt.coding(root, "M001-S01")).read_text(encoding="utf-8")
            self.assertIn("Unblock reason: owner supplied the decision", text)
            self.assertIn("M001-S01-R1-F1", text)

    def test_unblocked_schema_rejects_runner_actor_and_wrong_state(self) -> None:
        rm = roadmap.load(ROOT)
        event = {
            "schema": ledger.SCHEMA,
            "t": "2026-09-02T12:00:00Z",
            "ev": "unblocked",
            "by": "frutlups",
            "slice": "M001-S01",
            "round": 2,
            "reason": "x",
        }
        with self.assertRaisesRegex(ValueError, "actor"):
            ledger._validate(event)
        event["by"] = "human"
        with self.assertRaisesRegex(ValueError, "out of order"):
            ledger.fold([event], rm)

    def test_holistic_findings_are_grouped_once_per_slice(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            add_second_slice(root)
            append_accepted(root, "M001-S01")
            append_accepted(root, "M001-S02")
            report = root / "05_governance/reviews/m001/M001_holistic_review.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(
                """# Review: M001 round holistic

## Findings
| id | severity | disposition | summary |
| --- | --- | --- | --- |
| M001-S01-H1-F1 | P1 | open | first issue |
| M001-S01-H1-F2 | P2 | open | second issue |
| M001-S02-H1-F1 | P1 | open | third issue |

## Closure Decision
Objective status: not_achieved
Objective evidence: Three findings remain open.

## Verdict
Verdict: needs_work - next: reopen affected slices
""",
                encoding="utf-8",
            )
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "record",
                        report.relative_to(root).as_posix(),
                        "--milestone",
                        "M001",
                    ],
                ),
                0,
            )
            reopened = [
                event
                for event in ledger.read(root / "05_governance/ledger.jsonl")
                if event["ev"] == "reopened"
            ]
            self.assertEqual(
                [event["slice"] for event in reopened],
                [
                    "M001-S01",
                    "M001-S02",
                ],
            )
            self.assertIn("M001-S01-H1-F1, M001-S01-H1-F2", reopened[0]["reason"])

    def test_holistic_pass_records_milestone_done_and_ids_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            append_accepted(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001_holistic_review.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(
                PASS_REPORT.replace("M001-S01 round 1", "M001 round holistic"),
                encoding="utf-8",
            )
            args = [
                "--root",
                str(root),
                "record",
                report.relative_to(root).as_posix(),
                "--milestone",
                "M001",
            ]
            self.assertEqual(quiet_call(ledger.main, args), 0)
            state = ledger.fold(
                ledger.read(root / "05_governance/ledger.jsonl"), roadmap.load(root)
            )
            self.assertEqual(state["milestones_done"], {"M001"})

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            append_accepted(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001_holistic_review.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            bad = BLOCKED_REPORT.replace("M001-S01 round 1", "M001 round holistic")
            bad = bad.replace("M001-S01-R1-F1", "H1-F1")
            report.write_text(bad, encoding="utf-8")
            args = [
                "--root",
                str(root),
                "record",
                report.relative_to(root).as_posix(),
                "--milestone",
                "M001",
            ]
            self.assertEqual(quiet_call(ledger.main, args), 2)
            self.assertFalse(
                any(
                    event["ev"] == "reopened"
                    for event in ledger.read(root / "05_governance/ledger.jsonl")
                )
            )

    def test_reopen_cli_advances_an_accepted_slice(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            append_accepted(root, "M001-S01")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "reopen",
                        "M001-S01",
                        "--reason",
                        "regression",
                        "--by",
                        "architect",
                    ],
                ),
                0,
            )
            state = ledger.fold(
                ledger.read(root / "05_governance/ledger.jsonl"), roadmap.load(root)
            )["slices"]["M001-S01"]
            self.assertEqual((state["step"], state["round"]), ("fix", 2))

    def test_backlog_is_unchanged_when_review_append_fails(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            rm = roadmap.load(root)
            path = root / "05_governance/ledger.jsonl"
            base = {"by": "architect", "slice": "M001-S01", "round": 1}
            for event in (
                {**base, "ev": "prompt", "path": "p.md", "sha": SHA},
                {**base, "ev": "coded", "changed": []},
                {**base, "ev": "verified", "receipt": "r.json", "sha": SHA, "ok": True},
            ):
                ledger.append(path, event, rm)
            report = root / "05_governance/reviews/m001/M001-S01_r1_review.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            text = PASS_REPORT.replace(
                "| --- | --- | --- | --- |",
                "| --- | --- | --- | --- |\n| M001-S01-R1-P3 | P3 | carried | polish later |",
            )
            report.write_text(text, encoding="utf-8")
            backlog = root / "05_governance/backlog.md"
            before = backlog.read_bytes()
            with mock.patch.object(ledger, "append", side_effect=ValueError("refused")):
                result = quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "record",
                        report.relative_to(root).as_posix(),
                    ],
                )
            self.assertEqual(result, 2)
            self.assertEqual(backlog.read_bytes(), before)

    def test_check_accepts_product_paths_returned_to_head(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            set_full(root, "raise SystemExit(0)")
            originals = {
                "07_app/modified.txt": "original modified\n",
                "07_app/deleted.txt": "original deleted\n",
                "07_app/old.txt": "original rename\n",
            }
            for rel, text in originals.items():
                (root / rel).write_text(text, encoding="utf-8")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            prompt.coding(root, "M001-S01")
            (root / "07_app/modified.txt").write_text("changed\n", encoding="utf-8")
            (root / "07_app/added.txt").write_text("added\n", encoding="utf-8")
            (root / "07_app/deleted.txt").unlink()
            (root / "07_app/old.txt").rename(root / "07_app/new.txt")
            run_git(root, "add", "-A")
            self.assertEqual(
                quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]),
                0,
            )

            (root / "07_app/modified.txt").write_text(originals["07_app/modified.txt"])
            (root / "07_app/added.txt").unlink()
            (root / "07_app/deleted.txt").write_text(originals["07_app/deleted.txt"])
            (root / "07_app/new.txt").rename(root / "07_app/old.txt")
            run_git(root, "add", "-A")
            events = ledger.read(root / "05_governance/ledger.jsonl")
            self.assertEqual(ledger.check(root, roadmap.load(root), events), [])
            (root / "07_app/modified.txt").write_text("actual drift\n", encoding="utf-8")
            self.assertIn(
                "drift: 07_app/modified.txt", ledger.check(root, roadmap.load(root), events)
            )


class AttributionAndPromptTests(unittest.TestCase):
    def test_holistic_report_paths_are_reserved_across_prompts_and_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)

            def accept_round(round_no):
                prompt.coding(root, "M001-S01")
                (root / "07_app/feature.txt").write_text(f"round {round_no}\n", encoding="utf-8")
                self.assertEqual(
                    quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 0
                )
                self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
                report = f"05_governance/reviews/m001/M001-S01_r{round_no}_review.md"
                (root / report).write_text(
                    PASS_REPORT.replace("round 1", f"round {round_no}"), encoding="utf-8"
                )
                self.assertEqual(
                    quiet_call(ledger.main, ["--root", str(root), "record", report]), 0
                )
                self.assertEqual(
                    quiet_call(
                        ledger.main, ["--root", str(root), "accept", "M001-S01", "--commit"]
                    ),
                    0,
                )

            accept_round(1)
            first = "05_governance/reviews/m001/M001_holistic_review.md"
            second = "05_governance/reviews/m001/M001_holistic_2_review.md"
            for expected in (first, second):
                text = (root / prompt.holistic(root, "M001")).read_text(encoding="utf-8")
                self.assertIn(f"write only `{expected}`", text)
            report_text = needs_report(1).replace("M001-S01 round 1", "M001 round holistic")
            (root / first).write_text(report_text, encoding="utf-8")
            original = (root / first).read_bytes()
            self.assertEqual(
                quiet_call(
                    ledger.main, ["--root", str(root), "record", first, "--milestone", "M001"]
                ),
                0,
            )
            accept_round(2)
            # An existing, unrecorded file also occupies its report name.
            occupied = root / "05_governance/reviews/m001/M001_holistic_3_review.md"
            occupied.write_text("operator draft\n", encoding="utf-8")
            text = (root / prompt.holistic(root, "M001")).read_text(encoding="utf-8")
            self.assertIn("write only `05_governance/reviews/m001/M001_holistic_4_review.md`", text)
            self.assertEqual((root / first).read_bytes(), original)
            self.assertEqual(occupied.read_text(encoding="utf-8"), "operator draft\n")
            events = ledger.read(root / "05_governance/ledger.jsonl")
            self.assertEqual(ledger.check(root, roadmap.load(root), events), [])

    def test_failed_verification_baselines_known_state_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            set_full(root, "raise SystemExit(3)")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            prompt.coding(root, "M001-S01")
            (root / "07_app/feature.txt").write_text("round one\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            self.assertFalse(verify.run(root, "M001-S01", 10)[0]["ok"])
            prompt.coding(root, "M001-S01")
            latest = ledger.read(root / "05_governance/ledger.jsonl")[-1]
            baseline_paths = {item["path"] for item in latest["baseline"]}
            self.assertIn("07_app/feature.txt", baseline_paths)
            self.assertTrue(any(path.endswith("_verification.json") for path in baseline_paths))

    def test_holistic_reopen_baselines_prompt_and_report_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            prompt.coding(root, "M001-S01")
            (root / "07_app/feature.txt").write_text("done\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
            prompt.review(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001-S01_r1_review.md"
            report.write_text(PASS_REPORT, encoding="utf-8")
            quiet_call(
                ledger.main,
                ["--root", str(root), "record", report.relative_to(root).as_posix()],
            )
            quiet_call(ledger.main, ["--root", str(root), "accept", "M001-S01", "--commit"])
            holistic_prompt = prompt.holistic(root, "M001")
            holistic_report = root / "05_governance/reviews/m001/M001_holistic_review.md"
            text = BLOCKED_REPORT.replace("M001-S01 round 1", "M001 round holistic")
            holistic_report.write_text(text, encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "record",
                        holistic_report.relative_to(root).as_posix(),
                        "--milestone",
                        "M001",
                    ],
                ),
                0,
            )
            prompt.coding(root, "M001-S01")
            baseline = ledger.read(root / "05_governance/ledger.jsonl")[-1]["baseline"]
            paths = {item["path"] for item in baseline}
            self.assertIn(holistic_prompt, paths)
            self.assertIn(holistic_report.relative_to(root).as_posix(), paths)

    def test_dirty_prompt_refusal_and_exact_baseline_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            readme = root / "README.md"
            readme.write_text("architect edit\n", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                prompt.coding(root, "M001-S01")
            self.assertIn("README.md", str(caught.exception))
            self.assertIn("committed or stashed", str(caught.exception))
            prompt.coding(root, "M001-S01", True)
            (root / "07_app/x.txt").write_text("coder\n", encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "coded",
                        "M001-S01",
                    ],
                ),
                0,
            )
            coded = ledger.read(root / "05_governance/ledger.jsonl")[-1]
            self.assertEqual([item["path"] for item in coded["changed"]], ["07_app/x.txt"])

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            readme = root / "README.md"
            readme.write_text("architect edit\n", encoding="utf-8")
            prompt.coding(root, "M001-S01", True)
            readme.write_text("changed after prompt\n", encoding="utf-8")
            before = len(ledger.read(root / "05_governance/ledger.jsonl"))
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "coded",
                        "M001-S01",
                    ],
                ),
                2,
            )
            self.assertEqual(len(ledger.read(root / "05_governance/ledger.jsonl")), before)

    def test_injected_historical_prompt_is_not_owned(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            injected = root / "prompts/for_coding_agent/999_injected.md"
            injected.write_text("not a tool artifact\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown dirty paths"):
                prompt.coding(root, "M001-S01")

    def test_foreign_slice_artifacts_are_not_auto_baselined(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            add_second_slice(root)
            set_full(root, "raise SystemExit(0)")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            prompt.coding(root, "M001-S02")
            (root / "07_app/foreign.txt").write_text("foreign\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S02"])
            self.assertTrue(verify.run(root, "M001-S02", 10)[0]["ok"])
            foreign_prompt = prompt.review(root, "M001-S02")
            with self.assertRaisesRegex(ValueError, "unknown dirty paths") as caught:
                prompt.coding(root, "M001-S01")
            self.assertIn(foreign_prompt, str(caught.exception))

    def test_changed_prior_report_is_not_hidden_by_dirty_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            prompt.coding(root, "M001-S01")
            feature = root / "07_app/feature.txt"
            feature.write_text("round one\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            verify.run(root, "M001-S01", 10)
            prompt.review(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001-S01_r1_review.md"
            needs = PASS_REPORT.replace(
                "| --- | --- | --- | --- |",
                "| --- | --- | --- | --- |\n| M001-S01-R1-F1 | P1 | open | correct the behavior |",
            ).replace(
                "Verdict: pass - next: accept the slice",
                "Verdict: needs_work - next: fix the finding",
            )
            report.write_text(needs, encoding="utf-8")
            quiet_call(
                ledger.main,
                [
                    "--root",
                    str(root),
                    "record",
                    report.relative_to(root).as_posix(),
                ],
            )
            report.write_text(needs + "\ntampered before prompt\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "immutable evidence drift"):
                prompt.coding(root, "M001-S01")
            report.write_text(needs, encoding="utf-8")
            prompt.coding(root, "M001-S01")
            report.write_text(needs + "\ntampered after prompt\n", encoding="utf-8")
            before = len(ledger.read(root / "05_governance/ledger.jsonl"))
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "coded",
                        "M001-S01",
                    ],
                ),
                2,
            )
            self.assertEqual(len(ledger.read(root / "05_governance/ledger.jsonl")), before)

    def test_dirty_baseline_collects_every_git_change_kind(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            for rel in ("modified.txt", "deleted.txt", "old.txt"):
                (root / rel).write_text(rel, encoding="utf-8")
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "seed")
            (root / "modified.txt").write_text("changed", encoding="utf-8")
            (root / "deleted.txt").unlink()
            (root / "old.txt").rename(root / "renamed.txt")
            (root / "added.txt").write_text("new", encoding="utf-8")
            run_git(root, "add", "-A")
            baseline = evidence.prompt_baseline(root, roadmap.load(ROOT), [], "M001-S01", True)
            kinds = {item["path"]: item["kind"] for item in baseline}
            self.assertEqual(kinds["modified.txt"], "modified")
            self.assertEqual(kinds["deleted.txt"], "deleted")
            self.assertEqual(kinds["renamed.txt"], "renamed")
            self.assertEqual(kinds["added.txt"], "added")

    def test_review_prompt_embeds_added_file_and_bounded_diff(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            prompt.coding(root, "M001-S01")
            feature = root / "07_app/feature.txt"
            feature.write_text("visible source\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
            text = (root / prompt.review(root, "M001-S01")).read_text(encoding="utf-8")
            self.assertIn("## Code diff", text)
            self.assertIn("Added file: 07_app/feature.txt", text)
            self.assertIn("visible source", text)
            self.assertIn("Start every finding ID with `M001-S01-`", text)

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "seed")
            path = root / "large.txt"
            path.write_text("x" * 40_000, encoding="utf-8")
            block = evidence.review_diff(root, evidence.changed_files(root))
            self.assertIn("Diff truncated at 32 KB", block)
            self.assertTrue(block.endswith("\n```"))
            self.assertLessEqual(len(block.encode("utf-8")), 33 * 1024)

    def test_later_review_manifest_is_cumulative_but_diff_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            for round_no, rel in ((1, "first.txt"), (2, "second.txt")):
                prompt.coding(root, "M001-S01")
                (root / "07_app" / rel).write_text(f"round {round_no}\n", encoding="utf-8")
                quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
                self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
                prompt.review(root, "M001-S01")
                report = root / f"05_governance/reviews/m001/M001-S01_r{round_no}_review.md"
                report.write_text(needs_report(round_no), encoding="utf-8")
                quiet_call(
                    ledger.main,
                    ["--root", str(root), "record", report.relative_to(root).as_posix()],
                )
            prompt.coding(root, "M001-S01")
            (root / "07_app/first.txt").unlink()
            (root / "07_app/third.txt").write_text("round 3\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
            text = (root / prompt.review(root, "M001-S01")).read_text(encoding="utf-8")
            manifest, diff = text.split("## Code diff", 1)
            self.assertIn("`07_app/first.txt`", manifest)
            self.assertIn("`07_app/second.txt`", manifest)
            self.assertIn("`07_app/third.txt`", manifest)
            self.assertGreaterEqual(manifest.count("earlier round"), 2)
            self.assertIn("current round", manifest)
            self.assertIn("third.txt", diff)
            self.assertNotIn("second.txt", diff)

    def test_holistic_diff_uses_and_enforces_bounded_per_slice_detail(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "seed")
            base = run_git(root, "rev-parse", "HEAD").stdout.strip()
            paths = []
            for number in range(65):
                rel = f"07_app/file_{number:02d}.txt"
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x\n", encoding="utf-8")
                paths.append(rel)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "many")
            bounded = evidence.holistic_diff(root, base, {"M001-S01": paths})
            self.assertIn("omitted by the bounded evidence gate", bounded)
            self.assertNotIn("### M001-S01", bounded)

            detailed = evidence.holistic_diff(root, base, {"M001-S01": paths[:1]})
            self.assertIn("### M001-S01", detailed)
            self.assertLessEqual(len(detailed.encode("utf-8")), evidence.DIFF_LIMIT + 20)

    def test_review_diff_represents_delete_rename_and_binary_changes(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            (root / "gone.txt").write_text("gone\n", encoding="utf-8")
            (root / "old.txt").write_text("renamed\n", encoding="utf-8")
            (root / "binary.dat").write_bytes(b"\x00old")
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "seed")
            (root / "gone.txt").unlink()
            (root / "old.txt").rename(root / "new.txt")
            (root / "binary.dat").write_bytes(b"\x00new")
            run_git(root, "add", "-A")
            block = evidence.review_diff(root, evidence.changed_files(root))
            self.assertIn("gone.txt", block)
            self.assertIn("new.txt", block)
            self.assertIn("Binary files", block)

    def test_holistic_prompt_contains_accepted_range_stat_and_id_rule(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            prompt.coding(root, "M001-S01")
            (root / "07_app/feature.txt").write_text("done\n", encoding="utf-8")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            receipt, _ = verify.run(root, "M001-S01", 10)
            prompt.review(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001-S01_r1_review.md"
            report.write_text(PASS_REPORT, encoding="utf-8")
            quiet_call(
                ledger.main,
                [
                    "--root",
                    str(root),
                    "record",
                    report.relative_to(root).as_posix(),
                ],
            )
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "accept",
                        "M001-S01",
                        "--commit",
                    ],
                ),
                0,
            )
            text = (root / prompt.holistic(root, "M001")).read_text(encoding="utf-8")
            self.assertIn(f"git diff {receipt['base_commit']}..HEAD --stat", text)
            self.assertIn("### M001-S01", text)
            self.assertIn("Every P0-P2 finding ID must start with the affected slice ID", text)
            artifact = ledger.read(root / "05_governance/ledger.jsonl")[-1]
            self.assertEqual(
                (artifact["ev"], artifact["scope"], artifact["round"], artifact["role"]),
                ("artifact", "M001", "holistic", "holistic_prompt"),
            )


class CompatibilityAndSafetyTests(unittest.TestCase):
    def test_front_repo_projection_digest_remains_raw(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "projection.txt"
            path.write_bytes(b"first\r\nsecond\r\n")
            self.assertNotEqual(front_repo.digest(path), common.sha(path))

    def test_cli_paths_accept_backslashes_and_store_posix(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare_real_loop(root)
            manual = root / "prompts/for_coding_agent/manual.md"
            manual.write_text("manual\n", encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "prompt",
                        "M001-S01",
                        r".\prompts\for_coding_agent\manual.md",
                    ],
                ),
                0,
            )
            notes = root / "05_governance/reviews/m001/coder.md"
            notes.parent.mkdir(parents=True, exist_ok=True)
            notes.write_text("notes\n", encoding="utf-8")
            (root / "07_app/x.txt").write_text("x\n", encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "coded",
                        "M001-S01",
                        "--notes",
                        r"05_governance\reviews\m001\coder.md",
                    ],
                ),
                0,
            )
            verify.run(root, "M001-S01", 10)
            prompt.review(root, "M001-S01")
            report = root / "05_governance/reviews/m001/M001-S01_r1_review.md"
            report.write_text(PASS_REPORT, encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "record",
                        r".\05_governance\reviews\m001\M001-S01_r1_review.md",
                    ],
                ),
                0,
            )
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "index",
                        "--output",
                        r"05_governance\reviews\INDEX.md",
                    ],
                ),
                0,
            )
            events = ledger.read(root / "05_governance/ledger.jsonl")
            self.assertEqual(events[0]["path"], "prompts/for_coding_agent/manual.md")
            self.assertEqual(events[1]["notes_path"], "05_governance/reviews/m001/coder.md")
            self.assertTrue((root / "05_governance/reviews/INDEX.md").is_file())
            self.assertEqual(quiet_call(roadmap.main, ["next", "--root", str(root)]), 0)

    def test_cli_path_normalization_keeps_containment_strict(self) -> None:
        self.assertEqual(common.cli_rel(r"folder\file.md"), "folder/file.md")
        self.assertEqual(common.cli_rel(r".\folder\file.md"), "folder/file.md")
        self.assertEqual(common.cli_rel("./folder/file.md"), "folder/file.md")
        for value in (
            r"..\escape.md",
            r".\..\escape.md",
            "././escape.md",
            r"C:\absolute.md",
            r"\\server\share\x.md",
            "/absolute.md",
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "unsafe"):
                common.cli_rel(value)

    def test_git_identity_is_checked_before_accept_event(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project_copy(root)
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            append_accepted_events = [
                {"ev": "prompt", "path": "p.md", "sha": SHA},
                {"ev": "coded", "changed": []},
                {"ev": "verified", "receipt": "r.json", "sha": SHA, "ok": True},
                {"ev": "reviewed", "report": "v.md", "sha": SHA, "verdict": "pass", "open": []},
            ]
            rm = roadmap.load(root)
            ledger_path = root / "05_governance/ledger.jsonl"
            for value in append_accepted_events:
                ledger.append(
                    ledger_path,
                    {
                        **value,
                        "by": "architect",
                        "slice": "M001-S01",
                        "round": 1,
                    },
                    rm,
                )
            run_git(root, "config", "user.email", "")
            run_git(root, "config", "user.name", "")
            before = ledger_path.read_bytes()
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "accept",
                        "M001-S01",
                        "--commit",
                    ],
                ),
                2,
            )
            self.assertEqual(ledger_path.read_bytes(), before)

    def test_scrubber_preserves_urls_and_removes_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            value = b"https://example.test/a http://other.test C:\\secret\\x /tmp/private"
            scrubbed = verify._scrub(value, root, {})
            self.assertIn("https://example.test/a", scrubbed)
            self.assertIn("http://other.test", scrubbed)
            self.assertNotIn("C:\\secret", scrubbed)
            self.assertNotIn("/tmp/private", scrubbed)

    def test_empty_front_repo_manifest_has_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "front_repo.toml"
            path.write_text("[settings]\n[ignore]\n", encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, r"front_repo\.toml.*\[\[files\]\].*\[\[directories\]\].*add one"
            ):
                front_repo.load_manifest(path)

    def test_hermetic_verifier_fails_closed_and_stops_on_failure(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(hermetic.run([]), 2)
        self.assertIn("not configured", stderr.getvalue())
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            project = base / "project"
            project.mkdir()
            (project / "pkg").mkdir()
            observed = base / "observed.json"
            code = (
                "import json,os,pathlib,sys; "
                "pathlib.Path(sys.argv[1]).write_text(json.dumps({"
                "'cwd':os.getcwd(),'TEMP':os.environ['TEMP'],'TMP':os.environ['TMP'],"
                "'scratch':os.environ['VERIFICATION_SCRATCH'],"
                "'root':os.environ['PROJECT_ROOT'],"
                "'py':os.environ['PYTHONDONTWRITEBYTECODE']}))"
            )
            self.assertEqual(
                hermetic.run([[sys.executable, "-c", code, str(observed)]], project),
                0,
            )
            data = json.loads(observed.read_text(encoding="utf-8"))
            self.assertEqual(Path(data["cwd"]), project.resolve())
            self.assertEqual(data["TEMP"], data["TMP"])
            self.assertEqual(data["TEMP"], data["scratch"])
            self.assertEqual(Path(data["root"]), project.resolve())
            self.assertEqual(data["py"], "1")
            self.assertFalse(Path(data["TEMP"]).is_relative_to(project))
            self.assertEqual(
                hermetic.run(
                    [{"argv": [sys.executable, "-c", code, str(observed)], "cwd": "pkg"}],
                    project,
                ),
                0,
            )
            self.assertEqual(Path(json.loads(observed.read_text())["cwd"]), project / "pkg")
            for value in ("missing", "../escape", "/absolute", "./pkg", None):
                with self.subTest(cwd=value), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(
                        hermetic.run(
                            [{"argv": [sys.executable, "-c", "pass"], "cwd": value}], project
                        ),
                        2,
                    )
            marker = base / "should-not-exist"
            commands = [
                [sys.executable, "-c", "raise SystemExit(7)"],
                [
                    sys.executable,
                    "-c",
                    "import pathlib,sys;pathlib.Path(sys.argv[1]).touch()",
                    str(marker),
                ],
            ]
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(hermetic.run(commands, project), 7)
            self.assertIn("command 1 failed", stderr.getvalue())
            self.assertIn("exit=7", stderr.getvalue())
            self.assertIn(str(project.resolve()), stderr.getvalue())
            self.assertFalse(marker.exists())
            self.assertEqual([path.name for path in project.iterdir()], ["pkg"])

    def test_doctrine_and_intake_contracts_are_present(self) -> None:
        coding = (ROOT / "prompts/templates/coding_prompt.md").read_text(encoding="utf-8")
        self.assertIn("one short paragraph", coding)
        self.assertIn("exactly four lists", coding)
        review = (ROOT / "prompts/templates/review_prompt.md").read_text(encoding="utf-8")
        self.assertIn("## Code diff", review)
        self.assertIn("{{finding_id_rule}}", review)
        intake = (ROOT / "00_brief/intake.md").read_text(encoding="utf-8")
        for phrase in (
            "Project horizon",
            "Admitted milestones",
            "Current run boundary",
            "Disposable exact-toolchain slice",
            "user-path smoke test",
            "Operational budgets",
        ):
            self.assertIn(phrase, intake)
        doctrine = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("one short paragraph", doctrine)
        self.assertIn("ledger.py unblock", doctrine)
        operating = (ROOT / "docs/operating.md").read_text(encoding="utf-8")
        self.assertIn("--allow-dirty", operating)
        self.assertIn("fails with exit 2", operating)


if __name__ == "__main__":
    unittest.main()
