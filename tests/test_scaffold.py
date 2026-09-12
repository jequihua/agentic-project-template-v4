from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import front_repo  # noqa: E402
import ledger  # noqa: E402
import prompt  # noqa: E402
import roadmap  # noqa: E402
import verify  # noqa: E402

EXPECTED = {
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "ENVIRONMENT.md",
    "README.md",
    "front_repo.toml",
    "frutlups.toml",
    "pyproject.toml",
    "roadmap.yaml",
    "00_brief/CONTEXT.md",
    "00_brief/constraints.md",
    "00_brief/decisions.md",
    "00_brief/intake.md",
    "01_data/CONTEXT.md",
    "02_analysis/CONTEXT.md",
    "03_experiments/CONTEXT.md",
    "04_delivery/CONTEXT.md",
    "05_governance/CONTEXT.md",
    "05_governance/backlog.md",
    "05_governance/ledger.jsonl",
    "05_governance/human_owner_notes/README.md",
    "05_governance/reviews/README.md",
    "06_infra/CONTEXT.md",
    "07_app/CONTEXT.md",
    "08_pkg/CONTEXT.md",
    "09_ops/CONTEXT.md",
    "docs/front_repo.md",
    "docs/ledger.md",
    "docs/memory.md",
    "docs/method.md",
    "docs/operating.md",
    "docs/roadmap.md",
    "initialization/architect.md",
    "initialization/coder.md",
    "initialization/memory_llloom.md",
    "initialization/reviewer.md",
    "local_state/README.md",
    "prompts/for_coding_agent/README.md",
    "prompts/for_review_agent/README.md",
    "prompts/templates/coding_prompt.md",
    "prompts/templates/review_prompt.md",
    "questions/README.md",
    "questions/answered/README.md",
    "questions/open/README.md",
    "questions/template_question.md",
    "scripts/_common.py",
    "scripts/_evidence.py",
    "scripts/front_repo.py",
    "scripts/hermetic_verification.py",
    "scripts/ledger.py",
    "scripts/prompt.py",
    "scripts/roadmap.py",
    "scripts/verify.py",
    "scripts/_protocol.py",
    "scripts/_git.py",
    "scripts/_commit.py",
    "scripts/_process.py",
    "scripts/_workspace.py",
    "scripts/_integrity.py",
    "scripts/_findings.py",
    "docs/contracts.md",
    "docs/project_checks.md",
    "docs/upgrading.md",
}
LIMITS = {
    "AGENTS.md": 8_192,
    "README.md": 3_072,
    "ENVIRONMENT.md": 3_072,
    "docs/method.md": 15_360,
    "docs/operating.md": 12_288,
    "docs/ledger.md": 6_144,
    "docs/front_repo.md": 5_120,
    "docs/memory.md": 5_120,
    "docs/contracts.md": 12 * 1024,
    "docs/project_checks.md": 7 * 1024,
    "docs/upgrading.md": 8 * 1024,
    "prompts/templates/coding_prompt.md": 3_072,
    "prompts/templates/review_prompt.md": 3_072,
}


def project_files() -> set[str]:
    # Git applies ignore rules before enumeration, avoiding cache/run-store walks.
    top = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if top.returncode == 0 and Path(top.stdout.strip()).resolve() == ROOT.resolve():
        result = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            check=True,
        )
        paths = {os.fsdecode(value) for value in result.stdout.split(b"\0") if value}
        return {path for path in paths if not path.startswith("tests/")}
    # A real archive has no Git metadata; inspect only its explicitly admitted roots.
    files = {path.name for path in ROOT.iterdir() if path.is_file()}
    for folder in {Path(rel).parts[0] for rel in EXPECTED if "/" in rel} - {"local_state"}:
        for here, dirs, names in os.walk(ROOT / folder):
            dirs[:] = [
                name
                for name in dirs
                if name
                not in {
                    "__pycache__",
                    ".git",
                    ".venv",
                    "venv",
                    "node_modules",
                    ".cache",
                    ".pytest_cache",
                    ".ruff_cache",
                    "local_state",
                }
            ]
            files.update(
                (Path(here) / name).relative_to(ROOT).as_posix()
                for name in names
                if not name.endswith((".pyc", ".pyo"))
            )
    files.add("local_state/README.md")
    return files


class ScaffoldContractTests(unittest.TestCase):
    def test_exact_distributable_tree(self) -> None:
        self.assertEqual(project_files(), EXPECTED)

    def test_inventory_does_not_borrow_an_ancestor_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            parent = Path(name)
            git_init(parent)
            (parent / ".gitignore").write_text("export/\n", encoding="utf-8")
            export = parent / "export"
            project_copy(export)
            cache = export / "scripts/__pycache__"
            cache.mkdir()
            (cache / "ignored.pyc").write_bytes(b"cache")
            with mock.patch.object(sys.modules[__name__], "ROOT", export):
                self.assertEqual(project_files(), EXPECTED)

    def test_control_files_and_budgets(self) -> None:
        self.assertEqual((ROOT / "CLAUDE.md").read_bytes(), b"@AGENTS.md\n")
        editorconfig = (ROOT / ".editorconfig").read_text(encoding="utf-8")
        self.assertIn("root = true", editorconfig)
        self.assertIn("[*.{bat,cmd}]\nend_of_line = crlf", editorconfig)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.bat text eol=crlf", attributes)
        self.assertIn("*.cmd text eol=crlf", attributes)
        for rel, limit in LIMITS.items():
            self.assertLessEqual((ROOT / rel).stat().st_size, limit, rel)
        for n in (
            "01_data",
            "02_analysis",
            "03_experiments",
            "04_delivery",
            "06_infra",
            "07_app",
            "08_pkg",
            "09_ops",
        ):
            lines = (ROOT / n / "CONTEXT.md").read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 10, n)
            self.assertEqual(
                len(re.findall(r"^Status: (active|inactive)$", "\n".join(lines), re.M)), 1, n
            )

        # /2 adds coherent integrity/recovery boundaries and complete prompt preview.
        # Keep a small alarm per module; do not split the public ledger command just
        # to disguise its size, or compress readable validation syntax to pass.
        byte_limits = {
            "_common.py": 6 * 1024,
            "_evidence.py": 18 * 1024,
            "roadmap.py": 18 * 1024,
            "ledger.py": 48 * 1024,
            "verify.py": 9 * 1024,
            "prompt.py": 30 * 1024,
            "front_repo.py": 28 * 1024,
            "hermetic_verification.py": 6 * 1024,
            "_protocol.py": 20 * 1024,
            "_commit.py": 25 * 1024,  # Includes the frozen candidate-storage policy.
            "_findings.py": 8 * 1024,  # Original-owner and non-P3 waiver guards.
            "_git.py": 7 * 1024,
            "_workspace.py": 6 * 1024,
            "_process.py": 9 * 1024,
            "_integrity.py": 16 * 1024,
        }
        for name, limit in byte_limits.items():
            path = ROOT / "scripts" / name
            self.assertLessEqual(
                path.stat().st_size,
                limit,
                f"{name} exceeded its design alarm; discuss module design instead of "
                "compressing syntax",
            )
        python_files = sorted((ROOT / "scripts").glob("*.py"))
        python_files += sorted((ROOT / "tests").glob("*.py"))
        for path in python_files:
            name = path.relative_to(ROOT).as_posix()
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
            self.assertLessEqual(max(map(len, source.splitlines()), default=0), 100, name)
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            self.assertNotIn(";", (token.string for token in tokens), name)

    def test_default_optional_and_removed_surfaces(self) -> None:
        self.assertFalse(any((ROOT / "memory").rglob("*")))
        text = "\n".join(
            (ROOT / rel).read_text(encoding="utf-8", errors="strict")
            for rel in EXPECTED
            if (ROOT / rel).suffix in {".md", ".toml", ".yaml"}
        )
        for old in (
            "PROJECT_STATE.md",
            "MILESTONES.md",
            "frutlups.layout.yaml",
            "prompts/INDEX.md",
            "reviews/INDEX.md",
            "self_report",
        ):
            self.assertNotIn(old, text)

    def test_templates_have_known_placeholders(self) -> None:
        known = {
            "slice_id",
            "title",
            "round",
            "objective",
            "acceptance",
            "non_goals",
            "read_first",
            "allowed_prefixes",
            "forbidden",
            "focused",
            "full",
            "open_findings",
            "memory",
            "diff_manifest",
            "coder_notes",
            "receipt",
            "diff_evidence",
            "prior_findings",
            "report_path",
            "finding_id_rule",
            "finding_updates",
            "notes",
            "outcome_contract",
        }
        for rel in ("prompts/templates/coding_prompt.md", "prompts/templates/review_prompt.md"):
            found = set(re.findall(r"{{([a-z_]+)}}", (ROOT / rel).read_text(encoding="utf-8")))
            self.assertTrue(found)
            self.assertLessEqual(found, known)

    def test_distributable_size(self) -> None:
        # The measured /2 export is about 296 KiB: seven bounded stdlib helpers,
        # dual lifecycle readers, recoverable Git, immutable prompts and three
        # contract/upgrade guides replace the old 170 KiB scaffold allowance.
        self.assertLess(sum((ROOT / rel).stat().st_size for rel in EXPECTED), 312 * 1024)

    def test_archive_excludes_template_tests(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source, archive = Path(td) / "source", Path(td) / "project.zip"
            tests = {p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("test_*.py")}
            for rel in EXPECTED | tests:
                target = source / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, target)
            git_init(source)
            run_git(source, "add", ".")
            run_git(source, "commit", "-m", "template")
            run_git(source, "archive", "--format=zip", f"--output={archive}", "HEAD")
            with zipfile.ZipFile(archive) as zf:
                members = {x for x in zf.namelist() if not x.endswith("/")}
            self.assertEqual(members, EXPECTED)


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )


def git_init(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    run_git(root, "init", "-q")
    run_git(root, "config", "user.email", "test@example.invalid")
    run_git(root, "config", "user.name", "Template Test")


def project_copy(root: Path) -> None:
    for rel in EXPECTED:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    # Existing cases qualify legacy /1 behavior; new protocol cases explicitly opt in.
    path = root / "roadmap.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["schema"] = "frutlups.roadmap/1"
    data.pop("runtime", None)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n")


def set_full(root: Path, code: str) -> None:
    data = yaml.safe_load((root / "roadmap.yaml").read_text(encoding="utf-8"))
    data["project"] = "qualification"
    data["verification"]["full"] = [sys.executable, "-c", code]
    (root / "roadmap.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n"
    )


def quiet_call(fn, argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(argv)


PASS_REPORT = """# Review: M001-S01 round 1

## Findings
| id | severity | disposition | summary |
| --- | --- | --- | --- |

## Closure Decision
Objective status: achieved
Objective evidence: The receipt passed and the expected file exists.

## Verdict
Verdict: pass - next: accept the slice
"""


class RoadmapLedgerTests(unittest.TestCase):
    def test_milestone_statuses_and_active_frontier(self) -> None:
        rm = roadmap.load(ROOT)
        second = json.loads(json.dumps(rm["milestones"][0]))
        second["id"] = "M002"
        second["slices"][0]["id"] = "M002-S01"
        rm["milestones"].append(second)
        for statuses, valid in (
            (("active", "active"), True),
            (("done", "done"), True),
            (("done", "active"), True),
            (("done", "planned"), False),
            (("planned", "planned"), False),
        ):
            with self.subTest(statuses=statuses):
                for milestone, status in zip(rm["milestones"], statuses):
                    milestone["status"] = status
                errors, _ = roadmap.validate(rm)
                self.assertEqual(not errors, valid, errors)
                if not valid:
                    self.assertIn(
                        "at least one milestone must be active unless all milestones are done",
                        errors,
                    )
                self.assertIn(f"Status: {statuses[0]}", roadmap.render_markdown(rm))

        for milestone in rm["milestones"]:
            milestone["status"] = "active"
        state = ledger.fold([], rm)
        self.assertEqual(ledger.next_slice(rm, state), "M001-S01")
        state["slices"]["M001-S01"]["step"] = "accepted"
        for status, expected in (("active", "M002-S01"), ("planned", None), ("done", None)):
            with self.subTest(next_milestone_status=status):
                second["status"] = status
                self.assertEqual(ledger.next_slice(rm, state), expected)
        second["status"] = "active"
        state["milestones_done"].add("M001")
        self.assertEqual(ledger.next_slice(rm, state), "M002-S01")
        state["slices"]["M002-S01"]["step"] = "accepted"
        self.assertIsNone(ledger.next_slice(rm, state))
        # A reopened slice retains priority, regardless of its milestone's status.
        state["slices"]["M002-S01"].update(step="fix", reopened=True)
        state["slices"]["M001-S01"]["step"] = "coding"
        second["status"] = "done"
        self.assertEqual(ledger.next_slice(rm, state), "M002-S01")

    def test_example_and_render_are_current(self) -> None:
        data = roadmap.load(ROOT)
        self.assertEqual(roadmap.validate(data)[0], [])
        self.assertEqual(
            (ROOT / "docs/roadmap.md").read_text(encoding="utf-8"), roadmap.render_markdown(data)
        )

    def test_roadmap_validation_rules(self) -> None:
        data = roadmap.load(ROOT)
        cases = []
        bad = json.loads(json.dumps(data))
        bad["schema"] = "wrong"
        cases.append((bad, "schema"))
        bad = json.loads(json.dumps(data))
        bad["milestones"][0]["id"] = "M1"
        cases.append((bad, "Mnnn"))
        bad = json.loads(json.dumps(data))
        bad["verification"]["full"] = "python"
        cases.append((bad, "argv"))
        bad = json.loads(json.dumps(data))
        bad["allowed_prefixes"] = ["../escape/"]
        cases.append((bad, "unsafe"))
        bad = json.loads(json.dumps(data))
        bad["milestones"][0]["status"] = "paused"
        cases.append((bad, "planned, active, or done"))
        bad = json.loads(json.dumps(data))
        bad["milestones"][0]["slices"][0]["memory_pages"] = ["x.md"]
        cases.append((bad, "memory block"))
        for value, message in cases:
            with self.subTest(message=message):
                self.assertIn(message, "\n".join(roadmap.validate(value)[0]))

    def test_fold_every_transition_and_reopen(self) -> None:
        rm = roadmap.load(ROOT)
        sha = "a" * 64
        base = {
            "schema": ledger.SCHEMA,
            "t": "2026-09-02T12:00:00Z",
            "by": "architect",
            "slice": "M001-S01",
            "round": 1,
        }
        seq = [
            {**base, "ev": "prompt", "path": "p.md", "sha": sha},
            {**base, "ev": "coded", "changed": []},
            {**base, "ev": "verified", "receipt": "r.json", "sha": sha, "ok": True},
            {**base, "ev": "reviewed", "report": "v.md", "sha": sha, "verdict": "pass", "open": []},
            {**base, "ev": "accepted"},
        ]
        expected = ["coding", "verifying", "reviewing", "accept_pending", "accepted"]
        for n, step in enumerate(expected, 1):
            self.assertEqual(ledger.fold(seq[:n], rm)["slices"]["M001-S01"]["step"], step)
        reopened = {**base, "ev": "reopened", "round": 2, "by": "human", "reason": "defect"}
        milestone = {"ev": "milestone_done", "milestone": "M001"}
        state = ledger.fold(seq + [milestone], rm)
        self.assertEqual(state["milestones_done"], {"M001"})
        state = ledger.fold(seq + [milestone, reopened], rm)
        self.assertEqual(
            (
                state["slices"]["M001-S01"]["step"],
                state["slices"]["M001-S01"]["round"],
                state["milestones_done"],
            ),
            ("fix", 2, set()),
        )
        with self.assertRaisesRegex(ValueError, "out of order"):
            ledger.fold(seq + [reopened, reopened], rm)

    def test_failed_verification_and_needs_work_advance_round(self) -> None:
        rm = roadmap.load(ROOT)
        sha = "b" * 64
        base = {
            "schema": ledger.SCHEMA,
            "t": "2026-09-02T12:00:00Z",
            "by": "architect",
            "slice": "M001-S01",
            "round": 1,
        }
        first = [
            {**base, "ev": "prompt", "path": "p", "sha": sha},
            {**base, "ev": "coded", "changed": []},
        ]
        failed = first + [{**base, "ev": "verified", "receipt": "r", "sha": sha, "ok": False}]
        self.assertEqual(ledger.fold(failed, rm)["slices"]["M001-S01"]["round"], 2)
        reviewed = first + [
            {**base, "ev": "verified", "receipt": "r", "sha": sha, "ok": True},
            {
                **base,
                "ev": "reviewed",
                "report": "v",
                "sha": sha,
                "verdict": "needs_work",
                "open": ["F1"],
            },
        ]
        state = ledger.fold(reviewed, rm)["slices"]["M001-S01"]
        self.assertEqual((state["step"], state["round"], state["open"]), ("fix", 2, ["F1"]))

    def test_review_parser(self) -> None:
        parsed = ledger.parse_review(PASS_REPORT)
        self.assertEqual(
            (parsed["verdict"], parsed["objective_status"], parsed["open"]),
            ("pass", "achieved", []),
        )
        bad = PASS_REPORT.replace(
            "| --- | --- | --- | --- |", "| --- | --- | --- | --- |\n| F1 | P1 | open | broken |"
        )
        with self.assertRaisesRegex(ValueError, "cannot have open"):
            ledger.parse_review(bad)
        fenced = "```markdown\n## Verdict\nVerdict: blocked - next: fake\n```\n" + PASS_REPORT
        self.assertEqual(ledger.parse_review(fenced)["verdict"], "pass")

    def test_review_summary_accepts_literal_and_escaped_pipes(self) -> None:
        for summary, expected in (
            ("Run `a | b` before accepting", "Run `a | b` before accepting"),
            (r"Compare a \| b", "Compare a | b"),
            (r"Run `a \| b | c`", "Run `a | b | c`"),
            (r"Ends with \|", "Ends with |"),
        ):
            with self.subTest(summary=summary):
                row = f"| F1 | P3 | carried | {summary} |"
                report = PASS_REPORT.replace(
                    "| --- | --- | --- | --- |", "| --- | --- | --- | --- |\n" + row
                )
                parsed = ledger.parse_review(report)
                self.assertEqual(
                    parsed["findings"],
                    [
                        {
                            "id": "F1",
                            "severity": "P3",
                            "disposition": "carried",
                            "summary": expected,
                        }
                    ],
                )
        compact = PASS_REPORT.replace(
            "| --- | --- | --- | --- |", "| --- | --- | --- | --- |\n|F1|P3|carried|end\\||"
        )
        self.assertEqual(ledger.parse_review(compact)["findings"][0]["summary"], "end|")
        for row in ("| F1 | P3 | carried |", "| F1 | P3 | carried |   |"):
            with self.subTest(invalid_row=row):
                report = PASS_REPORT.replace(
                    "| --- | --- | --- | --- |", "| --- | --- | --- | --- |\n" + row
                )
                with self.assertRaisesRegex(ValueError, "invalid findings row"):
                    ledger.parse_review(report)

    def test_strict_ledger_read(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ledger.jsonl"
            path.write_text('{"bad":\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 1"):
                ledger.read(path)


class ManualLoopTests(unittest.TestCase):
    def test_render_preserves_braces_in_substituted_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "template.md"
            path.write_text("{{coder_notes}}\n{{diff_evidence}}\n", encoding="utf-8")
            notes = "Literal {{ and }}; Jinja {{diff}}; known {{diff_evidence}}."
            diff = "Nested {key: {item for item in items}}; known {{coder_notes}}."
            rendered = prompt._render(path, {"coder_notes": notes, "diff_evidence": diff})
            self.assertEqual(rendered, notes + "\n" + diff + "\n")

    def test_render_rejects_malformed_template_braces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "template.md"
            for text in ("{{ diff }}", "}}", "{{", "{{coder_notes}}}}"):
                with self.subTest(template=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError) as error:
                        prompt._render(path, {"coder_notes": "notes"})
                    self.assertEqual(str(error.exception), "unresolved placeholder")

    def test_render_rejects_unknown_template_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "template.md"
            path.write_text("{{unknown}}\n", encoding="utf-8")
            with self.assertRaises(ValueError) as error:
                prompt._render(path, {"unknown": "value"})
            self.assertEqual(str(error.exception), "unknown placeholders: ['unknown']")

    def test_complete_manual_loop_and_hash_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project_copy(root)
            set_full(root, "raise SystemExit(0)")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            coding = prompt.coding(root, "M001-S01")
            self.assertTrue((root / coding).is_file())
            feature = root / "07_app/feature.txt"
            feature.write_text("done\n", encoding="utf-8")
            notes = root / "05_governance/reviews/m001/M001-S01_r1_coder.md"
            notes.parent.mkdir(parents=True)
            notes.write_text("changed feature.txt\n", encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "coded",
                        "M001-S01",
                        "--notes",
                        notes.relative_to(root).as_posix(),
                    ],
                ),
                0,
            )
            receipt, receipt_rel = verify.run(root, "M001-S01", 10)
            self.assertTrue(receipt["ok"])
            self.assertTrue(receipt["tree_dirty_before"])
            self.assertFalse(receipt["tree_clean_after"])
            self.assertNotIn(str(root), (root / receipt_rel).read_text(encoding="utf-8"))
            review_prompt = prompt.review(root, "M001-S01")
            self.assertTrue((root / review_prompt).is_file())
            report = root / "05_governance/reviews/m001/M001-S01_r1_review.md"
            report.write_text(PASS_REPORT, encoding="utf-8")
            needs = PASS_REPORT.replace(
                "| --- | --- | --- | --- |",
                "| --- | --- | --- | --- |\n| M001-S01-R1-F1 | P1 | open | tighten behavior |",
            ).replace(
                "Verdict: pass - next: accept the slice",
                "Verdict: needs_work - next: fix F1 and re-verify",
            )
            report.write_text(needs, encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    ["--root", str(root), "record", report.relative_to(root).as_posix()],
                ),
                0,
            )
            corrective = (root / prompt.coding(root, "M001-S01")).read_text(encoding="utf-8")
            self.assertIn("M001-S01-R1-F1", corrective)
            feature.write_text("done better\n", encoding="utf-8")
            self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 0)
            self.assertTrue(verify.run(root, "M001-S01", 10)[0]["ok"])
            prompt.review(root, "M001-S01")
            report2 = root / "05_governance/reviews/m001/M001-S01_r2_review.md"
            report2.write_text(PASS_REPORT.replace("round 1", "round 2"), encoding="utf-8")
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    ["--root", str(root), "record", report2.relative_to(root).as_posix()],
                ),
                0,
            )
            self.assertEqual(
                quiet_call(ledger.main, ["--root", str(root), "accept", "M001-S01", "--commit"]), 0
            )
            events = ledger.read(root / "05_governance/ledger.jsonl")
            state = ledger.fold(events, roadmap.load(root))
            self.assertEqual(
                (state["slices"]["M001-S01"]["step"], state["slices"]["M001-S01"]["round"]),
                ("accepted", 2),
            )
            self.assertEqual(ledger.check(root, roadmap.load(root), events), [])
            self.assertEqual(run_git(root, "status", "--porcelain").stdout, "")

    def test_verification_detects_tree_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project_copy(root)
            set_full(root, "open('stray.txt','w').write('x')")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            prompt.coding(root, "M001-S01")
            (root / "07_app/feature.txt").write_text("x\n", encoding="utf-8")
            self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 0)
            receipt, _ = verify.run(root, "M001-S01", 10)
            self.assertFalse(receipt["ok"])
            state = ledger.fold(
                ledger.read(root / "05_governance/ledger.jsonl"), roadmap.load(root)
            )["slices"]["M001-S01"]
            self.assertEqual((state["step"], state["round"]), ("fix", 2))

    def test_verification_failure_modes_and_redaction(self) -> None:
        cases = [
            ([sys.executable, "-c", "raise SystemExit(7)"], 10, 7, False),
            (["missing-v4-command"], 10, None, False),
            ([sys.executable, "-c", "import time; time.sleep(2)"], 0.05, None, True),
        ]
        for command, timeout, exit_code, timed_out in cases:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                project_copy(root)
                data = yaml.safe_load((root / "roadmap.yaml").read_text(encoding="utf-8"))
                data["verification"]["full"] = command
                (root / "roadmap.yaml").write_text(
                    yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n"
                )
                git_init(root)
                run_git(root, "add", ".")
                run_git(root, "commit", "-m", "start")
                prompt.coding(root, "M001-S01")
                (root / "07_app/x").write_text("x")
                self.assertEqual(
                    quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 0
                )
                receipt, _ = verify.run(root, "M001-S01", timeout)
                self.assertFalse(receipt["ok"])
                self.assertEqual(
                    (receipt["commands"][0]["exit"], receipt["commands"][0]["timed_out"]),
                    (exit_code, timed_out),
                )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project_copy(root)
            secret = "v4-secret-value"
            set_full(root, "import os; print(os.getcwd()); print(os.environ['V4_TEST_SECRET'])")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            prompt.coding(root, "M001-S01")
            (root / "07_app/x").write_text("x")
            quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"])
            old = os.environ.get("V4_TEST_SECRET")
            os.environ["V4_TEST_SECRET"] = secret
            try:
                text = json.dumps(verify.run(root, "M001-S01", 10)[0])
                self.assertNotIn(secret, text)
                self.assertNotIn(str(root), text)
            finally:
                os.environ.pop("V4_TEST_SECRET", None) if old is None else os.environ.__setitem__(
                    "V4_TEST_SECRET", old
                )

    def test_changed_files_handles_deleted_and_unicode_rename(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            git_init(root)
            (root / "gone.txt").write_text("gone")
            (root / "old name.txt").write_text("move")
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            (root / "gone.txt").unlink()
            (root / "old name.txt").rename(root / "néw name.txt")
            run_git(root, "add", "-A")
            changed = {x["path"]: x["kind"] for x in ledger.changed_files(root)}
            self.assertEqual((changed["gone.txt"], changed["néw name.txt"]), ("deleted", "renamed"))

    def test_coded_refuses_out_of_boundary_without_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project_copy(root)
            set_full(root, "raise SystemExit(0)")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            prompt.coding(root, "M001-S01")
            (root / "README.md").write_text("unauthorized\n", encoding="utf-8")
            before = len(ledger.read(root / "05_governance/ledger.jsonl"))
            self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]), 2)
            self.assertEqual(len(ledger.read(root / "05_governance/ledger.jsonl")), before)

    def test_memory_section_is_conditional(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project_copy(root)
            set_full(root, "raise SystemExit(0)")
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            text = (root / prompt.coding(root, "M001-S01")).read_text(encoding="utf-8")
            self.assertNotIn("## Memory", text)

    def test_memory_section_and_prefix_rules_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project_copy(root)
            set_full(root, "raise SystemExit(0)")
            data = yaml.safe_load((root / "roadmap.yaml").read_text(encoding="utf-8"))
            data["memory"] = {
                "kind": "llloom",
                "root": "memory/llloom",
                "manual": "docs/memory.md",
                "read_verbs": ["search", "show"],
                "read_first_pages": ["memory/llloom/pages/start.md"],
            }
            (root / "roadmap.yaml").write_text(
                yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n"
            )
            self.assertEqual(roadmap.validate(data)[0], [])
            bad = json.loads(json.dumps(data))
            bad["milestones"][0]["slices"][0]["kind"] = "memory_update"
            self.assertIn("memory root", "\n".join(roadmap.validate(bad)[0]))
            bad["milestones"][0]["slices"][0]["allowed_prefixes"] = ["memory/llloom/"]
            self.assertEqual(roadmap.validate(bad)[0], [])
            git_init(root)
            run_git(root, "add", ".")
            run_git(root, "commit", "-m", "start")
            text = (root / prompt.coding(root, "M001-S01")).read_text(encoding="utf-8")
            self.assertIn("## Memory", text)
            self.assertIn("llloom --root memory/llloom search", text)


class FrontRepoTests(unittest.TestCase):
    def make_source(self, root: Path) -> Path:
        (root / "pkg").mkdir(parents=True)
        (root / "pkg/a.txt").write_text("one\n", encoding="utf-8")
        (root / "front_repo.toml").write_text(
            """[settings]
target = ""
[ignore]
names = []
suffixes = []
globs = []
[[directories]]
source = "pkg"
target = "src"
exclude = ["excluded/**"]
""",
            encoding="utf-8",
        )
        git_init(root)
        run_git(root, "add", ".")
        run_git(root, "commit", "-m", "source")
        return root / "front_repo.toml"

    def test_bootstrap_state_and_diverged_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source, target = base / "source", base / "target"
            manifest = self.make_source(source)
            args = [
                "bootstrap",
                "--dev-root",
                str(source),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(target),
            ]
            self.assertEqual(quiet_call(front_repo.main, args), 0)
            state = json.loads((target / front_repo.STATE).read_text(encoding="utf-8"))
            self.assertEqual(
                (state["schema"], state["source_commit"]),
                ("front_repo.sync/1", run_git(source, "rev-parse", "HEAD").stdout.strip()),
            )
            git_init(target)
            run_git(target, "add", ".")
            run_git(target, "commit", "-m", "front")
            (target / "adjacent.tmp").write_text("dirty\n", encoding="utf-8")
            apply_args = [
                "apply",
                "--dev-root",
                str(source),
                "--manifest",
                str(manifest),
                "--target-repo",
                str(target),
            ]
            self.assertEqual(quiet_call(front_repo.main, apply_args), 2)
            (target / "adjacent.tmp").unlink()
            (target / "src/a.txt").write_text("human\n", encoding="utf-8")
            run_git(target, "add", ".")
            run_git(target, "commit", "-m", "human")
            (source / "pkg/a.txt").write_text("two\n", encoding="utf-8")
            run_git(source, "add", ".")
            run_git(source, "commit", "-m", "two")
            state_before = (target / front_repo.STATE).read_bytes()
            self.assertEqual(quiet_call(front_repo.main, ["check", *apply_args[1:]]), 0)
            self.assertEqual(
                (
                    (target / "src/a.txt").read_text(encoding="utf-8"),
                    (target / front_repo.STATE).read_bytes(),
                ),
                ("human\n", state_before),
            )
            self.assertEqual(quiet_call(front_repo.main, apply_args), 2)
            self.assertEqual((target / "src/a.txt").read_text(encoding="utf-8"), "human\n")
            self.assertEqual(quiet_call(front_repo.main, apply_args + ["--overwrite-diverged"]), 0)
            self.assertEqual((target / "src/a.txt").read_text(encoding="utf-8"), "two\n")
            run_git(target, "add", ".")
            run_git(target, "commit", "-m", "sync")
            (target / "src/stale.txt").write_text("stale\n", encoding="utf-8")
            (target / "adjacent.txt").write_text("keep\n", encoding="utf-8")
            run_git(target, "add", ".")
            run_git(target, "commit", "-m", "extra")
            self.assertEqual(quiet_call(front_repo.main, apply_args + ["--overwrite-diverged"]), 0)
            self.assertFalse((target / "src/stale.txt").exists())
            self.assertTrue((target / "adjacent.txt").exists())

    def test_sensitive_exclude_and_separation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, target = root / "source", root / "target"
            manifest = self.make_source(source)
            target.mkdir()
            data = front_repo.load_manifest(manifest)
            (source / "pkg/.env.prod").write_text("secret\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sensitive"):
                front_repo.plan(data, source, target)
            self.assertIn(
                "src/.env.prod", [x["rel"] for x in front_repo.plan(data, source, target, True)[0]]
            )
            (source / "pkg/.env.prod").unlink()
            (source / "pkg/excluded").mkdir()
            (source / "pkg/excluded/x.txt").write_text("x", encoding="utf-8")
            entries, _ = front_repo.plan(data, source, target)
            self.assertNotIn("src/excluded/x.txt", [x["rel"] for x in entries])
            with self.assertRaisesRegex(ValueError, "inside"):
                front_repo.separated(source, source / "nested")
            with self.assertRaisesRegex(ValueError, "inside"):
                front_repo.separated(source / "nested", source)
            for bad in ("../escape", "C:/absolute", "/absolute"):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    front_repo.safe_rel(bad)

    def test_source_symlinks_are_refused_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, target = root / "source", root / "target"
            manifest = self.make_source(source)
            target.mkdir()
            try:
                os.symlink(source / "pkg/a.txt", source / "pkg/link.txt")
            except OSError:
                self.skipTest("symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "symlink"):
                front_repo.plan(front_repo.load_manifest(manifest), source, target)

    def test_seat_cannot_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source, target = base / "source", base / "target"
            manifest = self.make_source(source)
            old = os.environ.get("FRUTLUPS_SEAT")
            os.environ["FRUTLUPS_SEAT"] = "coder"
            try:
                self.assertEqual(
                    quiet_call(
                        front_repo.main,
                        [
                            "bootstrap",
                            "--dev-root",
                            str(source),
                            "--manifest",
                            str(manifest),
                            "--output-dir",
                            str(target),
                        ],
                    ),
                    2,
                )
            finally:
                if old is None:
                    os.environ.pop("FRUTLUPS_SEAT", None)
                else:
                    os.environ["FRUTLUPS_SEAT"] = old


if __name__ == "__main__":
    unittest.main()
