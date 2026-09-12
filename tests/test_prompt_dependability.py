"""Independent review regressions for prompt completeness and bounded recovery."""

import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_prompts_v2 import c, evidence, fixture, ledger, prompt, roadmap, verify
from test_scaffold import PASS_REPORT, quiet_call

SID = "M001-S01"


class DependablePromptTests(unittest.TestCase):
    def _envelope(self, root):
        rm = roadmap.load(root)
        _, item = roadmap.slice_by_id(rm, SID)
        return prompt._envelope(root, rm, item, ledger.fold([], rm)["slices"][SID])

    def _verified(self, root, notes=False):
        prompt.coding(root, SID)
        (root / "07_app/source.py").write_text("answer = 1\n", encoding="utf-8")
        args = ["--root", str(root), "coded", SID]
        if notes:
            rel = "05_governance/reviews/m001/notes.md"
            (root / rel).write_text("Coder explanation.\n", encoding="utf-8")
            args += ["--notes", rel]
        self.assertEqual(quiet_call(ledger.main, args), 0)
        self.assertTrue(verify.run(root, SID, 10)[0]["ok"])

    def _accepted(self, root):
        self._verified(root)
        rel = "05_governance/reviews/m001/accepted.md"
        (root / rel).write_text(PASS_REPORT, encoding="utf-8")
        self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "record", rel]), 0)
        self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "accept", SID]), 0)

    def _snapshot(self, root):
        snapshot = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }
        snapshot[".git/index"] = (root / ".git/index").read_bytes()
        return snapshot

    def _check_pages(self, root, text):
        refs = re.findall(r"`([^`\n]+)` \(sha256 `([a-f0-9]{64})`", text)
        self.assertTrue(refs)
        for rel, digest in refs:
            self.assertTrue((root / rel).is_file(), rel)
            self.assertEqual(c.sha(root / rel), digest, rel)

    def test_custom_review_appends_protocol_and_every_evidence_section(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            path = root / "prompts/templates/review_prompt.md"
            path.write_text("# Project review\n\n{{objective}}\n", encoding="utf-8")
            values = prompt._review_values(self._envelope(root), "reviews/result.md")
            for key in ("diff_manifest", "diff_evidence", "coder_notes", "receipt"):
                values[key] = "BOUND " + key
            values["prior_findings"] = "BOUND prior_findings"
            with contextlib.redirect_stderr(io.StringIO()) as err:
                text = prompt._render_review(root, values, True)
            for value in ("reviews/result.md", "## Finding updates", "## Closure Decision"):
                self.assertIn(value, text)
            for key in ("diff_manifest", "diff_evidence", "coder_notes", "receipt"):
                self.assertIn("BOUND " + key, text)
                self.assertIn("omitted " + key, err.getvalue())
            self.assertIn("BOUND prior_findings", text)
            self.assertIn("omitted report_path", err.getvalue())

    def test_root_acceptance_reference_is_diagnosed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            envelope = self._envelope(root)
            envelope["acceptance"] = ["Update `README.md`."]
            self.assertTrue(any("README.md" in row for row in prompt._diagnostics(root, envelope)))
            envelope["acceptance"] = ["Produce `07_app/future.py`."]
            self.assertFalse(prompt._diagnostics(root, envelope))

    def test_empty_known_field_and_legacy_omission_are_diagnosed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root / "custom.md"
            path.write_text("{{objective}}\n{{receipt}}\n", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                prompt._render(path, {"objective": "task", "receipt": "", "notes": "advice"})
            self.assertIn("empty receipt", err.getvalue())
            self.assertIn("omitted notes", err.getvalue())

    def test_empty_optional_inline_field_is_diagnosed_only_when_rendered(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root / "custom.md"
            optional = (
                ("Findings to resolve", "open_findings"),
                ("Memory", "memory"),
                ("Advisory notes", "notes"),
                ("Autonomous outcome", "outcome_contract"),
            )
            values = {"objective": "Implement scope", "memory": ""}
            for body, expect_warning in (
                ("{{objective}}\nMemory: {{memory}}\n", True),
                ("{{objective}}\n\n## Memory\n\n{{memory}}\n", False),
            ):
                with self.subTest(body=body):
                    path.write_text(body, encoding="utf-8")
                    with contextlib.redirect_stderr(io.StringIO()) as err:
                        prompt._render(path, values, optional)
                    self.assertEqual("empty memory" in err.getvalue(), expect_warning)

    def test_omitted_autonomous_outcome_contract_is_appended_and_diagnosed(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "custom.md"
            path.write_text("{{objective}}\n", encoding="utf-8")
            values = {"objective": "Implement scope", "outcome_contract": "Return typed outcome."}
            with contextlib.redirect_stderr(io.StringIO()) as err:
                text = prompt._render(path, values, complete=True)
            self.assertIn("## Autonomous outcome\n\nReturn typed outcome.", text)
            self.assertIn("omitted outcome_contract; appended its full section", err.getvalue())

    def test_coding_template_size_error_uses_coding_cap(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            (root / "prompts/templates/coding_prompt.md").write_text("x" * 50000)
            with self.assertRaisesRegex(ValueError, "16384"):
                prompt.coding(root, SID, preview=True)

    def test_preview_does_not_refresh_git_index_after_timestamp_only_change(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            path = root / "README.md"
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
            before = self._snapshot(root)
            prompt.coding(root, SID, preview=True)
            self.assertEqual(before, self._snapshot(root))

    def test_blocked_report_resume_is_bounded_and_preview_exact(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            self._verified(root)
            rel = "05_governance/reviews/m001/blocked.md"
            report = PASS_REPORT.replace(
                "| --- | --- | --- | --- |",
                "| --- | --- | --- | --- |\n| M001-S01-F1 | P1 | open | Owner input missing |",
            ).replace("## Closure Decision", "detail " * 2200 + "\n\n## Closure Decision")
            (root / rel).write_text(report.replace("Verdict: pass", "Verdict: blocked"))
            self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "record", rel]), 0)
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "resolve",
                        SID,
                        "--reason",
                        "Input recorded",
                        "--authority",
                        "00_brief/decisions.md",
                    ],
                ),
                0,
            )
            before = self._snapshot(root)
            preview = prompt.coding(root, SID, preview=True)
            self.assertEqual(before, self._snapshot(root))
            self.assertLessEqual(len(preview.encode()), prompt.CODING_LIMIT)
            self.assertIn(rel, preview)
            self.assertIn(c.sha(root / rel), preview)
            issued = prompt.coding(root, SID)
            self.assertEqual(preview, (root / issued).read_text(encoding="utf-8"))
            self._check_pages(root, preview)

    def test_large_finding_context_externalizes_without_mutating_preview(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            context = "Original immutable source and findings\n" + "finding detail " * 5000
            before = self._snapshot(root)
            with mock.patch.object(evidence, "findings_context", return_value=context):
                preview = prompt.coding(root, SID, preview=True)
                self.assertEqual(before, self._snapshot(root))
                issued = prompt.coding(root, SID)
            self.assertEqual(preview, (root / issued).read_text(encoding="utf-8"))
            self._check_pages(root, preview)
            pages = list((root / "05_governance/reviews/m001").glob("*context.md"))
            self.assertTrue(
                any(path.read_text(encoding="utf-8").strip() == context.strip() for path in pages)
            )

    def test_corrective_findings_stay_inline_when_whole_coding_prompt_fits(self):
        for backend in ("manual", "autonomous"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                fixture(root)
                self._verified(root)
                rows = [
                    f"| {SID}-F{index} | P2 | open | " + "Check café result. " * 10 + " |"
                    for index in range(12)
                ]
                report = PASS_REPORT.replace(
                    "| --- | --- | --- | --- |",
                    "| --- | --- | --- | --- |\n" + "\n".join(rows),
                ).replace("Verdict: pass", "Verdict: needs_work")
                report = report.replace(
                    "Objective status: achieved", "Objective status: not_achieved"
                )
                rel = "05_governance/reviews/m001/corrective.md"
                (root / rel).write_text(report, encoding="utf-8")
                self.assertEqual(quiet_call(ledger.main, ["--root", str(root), "record", rel]), 0)
                rm, events, state = prompt._load(root)
                context = evidence.findings_context(root, state["slices"][SID], events, SID)
                self.assertGreater(len(context.encode("utf-8")), 2048)
                before = self._snapshot(root)
                preview = prompt.coding(root, SID, preview=True, backend=backend)
                self.assertEqual(before, self._snapshot(root))
                self.assertLessEqual(len(preview.encode("utf-8")), prompt.CODING_LIMIT)
                self.assertIn(context, preview)
                issued = prompt.coding(root, SID, backend=backend)
                self.assertEqual(preview, (root / issued).read_text(encoding="utf-8"))
                self._check_pages(root, preview)
                self.assertFalse(list((root / "05_governance/reviews/m001").glob("*context.md")))
                events = ledger.read(root / "05_governance/ledger.jsonl")
                envelope = events[-1]["envelope"]
                frozen = json.loads((root / envelope["path"]).read_text(encoding="utf-8"))
                self.assertEqual(frozen["findings"], context)
                self.assertEqual(ledger.fold(events, rm)["slices"][SID]["round"], 2)

    def test_legacy_review_suppresses_only_inapplicable_finding_update_diagnostic(self):
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                fixture(root, schema=f"frutlups.roadmap/{version}")
                values = prompt._review_values(self._envelope(root), "reviews/result.md")
                values.update(diff_manifest="No changes", diff_evidence="No diff", receipt="")
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    text = prompt._render_review(root, values, version == 2)
                self.assertNotIn("empty finding_updates", err.getvalue())
                self.assertIn("empty receipt", err.getvalue())
                self.assertEqual("## Finding updates" in text, version == 2)
                path = root / "custom.md"
                path.write_text("{{finding_updates}}\n", encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    prompt._render(path, {"finding_updates": ""}, complete=True)
                self.assertIn("empty finding_updates", err.getvalue())

    def test_near_cap_blocked_outcome_resumes_with_complete_reference(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            prompt.coding(root, SID)
            (root / "07_app/source.py").write_text("retained = True\n", encoding="utf-8")
            rel = "05_governance/reviews/m001/outcome.json"
            outcome = {
                "schema": "frutlups.outcome/2",
                "slice": SID,
                "round": 1,
                "invocation": "manual-probe",
                "outcome": "blocked_authority",
                "requirement": "Owner input",
                "reason": "Missing approved source",
                "actor": "owner",
                "action": "Record approved source",
                "remaining": ["supporting detail " * 880],
                "evidence": [],
                "authority": [],
            }
            raw = json.dumps(outcome, ensure_ascii=False)
            self.assertGreater(len(raw.encode()), 15800)
            self.assertLess(len(raw.encode()), 16384)
            (root / rel).write_text(raw, encoding="utf-8")
            self.assertEqual(
                quiet_call(ledger.main, ["--root", str(root), "blocked", SID, "--outcome", rel]), 0
            )
            self.assertEqual(
                quiet_call(
                    ledger.main,
                    [
                        "--root",
                        str(root),
                        "resolve",
                        SID,
                        "--reason",
                        "Source approved",
                        "--authority",
                        "00_brief/decisions.md",
                    ],
                ),
                0,
            )
            before = self._snapshot(root)
            preview = prompt.coding(root, SID, preview=True)
            self.assertEqual(before, self._snapshot(root))
            issued = prompt.coding(root, SID)
            self.assertEqual(preview, (root / issued).read_text(encoding="utf-8"))
            self._check_pages(root, preview)
            self.assertIn(rel, preview)
            self.assertIn(c.sha(root / rel), preview)

    def test_stock_review_memory_is_inline_without_custom_warning(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            values = prompt._review_values(self._envelope(root), "reviews/result.md")
            values.update(
                memory="Read project memory with the granted tools.",
                diff_manifest="No changes",
                diff_evidence="No diff",
                receipt="Passed",
            )
            with contextlib.redirect_stderr(io.StringIO()) as err:
                text = prompt._render_review(root, values, True)
            self.assertIn("## Memory\n\nRead project memory", text)
            self.assertNotIn("memory", err.getvalue())

    def test_coding_externalizes_even_small_context_when_authority_nears_cap(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            envelope = self._envelope(root)
            envelope["acceptance"] = ["mandatory " * 1400]
            envelope["findings"] = "support context " * 100
            with mock.patch.object(prompt, "_envelope", return_value=envelope):
                text = prompt.coding(root, SID, preview=True)
            self.assertLessEqual(len(text.encode()), prompt.CODING_LIMIT)
            self.assertIn(envelope["acceptance"][0], text)
            self.assertIn("context.md", text)

    def test_source_priority_includes_c_headers_sql_and_numbered_data(self):
        bulk = [{"path": f"01_data/{number:04d}.csv"} for number in range(700)]
        sources = ["07_app/main.c", "07_app/api.h", "08_pkg/schema.sql", "01_data/load.py"]
        selected = evidence.selected_changes(bulk + [{"path": rel} for rel in sources])
        self.assertEqual({row["path"] for row in selected[:4]}, set(sources))

    def test_holistic_source_precedes_bulk_owned_by_an_earlier_slice(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            bulk = [f"01_data/{number:02d}.csv" for number in range(64)]
            for rel in bulk:
                (root / rel).write_text("bulk,1\n" * 1000, encoding="utf-8")
            source = "07_app/query.sql"
            (root / source).write_text("SELECT dependable_result;\n", encoding="utf-8")
            text = evidence.holistic_diff(
                root, "HEAD", {SID: bulk, "M001-S02": [source]}, limit=4096
            )
            self.assertIn("SELECT dependable_result", text)
            self.assertLessEqual(len(text.encode()), 4116)

    def test_excerpt_truncation_names_full_artifact_hash(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "notes.md").write_text("é" * 5000, encoding="utf-8")
            excerpt = evidence.read_excerpt(root, "notes.md", 1024)
            self.assertIn(c.sha(root / "notes.md"), excerpt)
            self.assertIn("notes.md", excerpt)

    def test_ledger_only_holistic_diff_pages_show_uncommitted_accepted_source(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            self._accepted(root)
            before = self._snapshot(root)
            preview = prompt.holistic(root, "M001", preview=True)
            self.assertEqual(before, self._snapshot(root))
            self.assertIn("answer = 1", preview)
            issued = prompt.holistic(root, "M001")
            self.assertEqual(preview, (root / issued).read_text(encoding="utf-8"))
            self._check_pages(root, preview)

    def test_holistic_prior_findings_externalize(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            self._accepted(root)
            frozen = prompt._frozen

            def large(*args):
                return {**frozen(*args), "findings": "historic context " * 5000}

            before = self._snapshot(root)
            with mock.patch.object(prompt, "_frozen", side_effect=large):
                preview = prompt.holistic(root, "M001", preview=True)
                self.assertEqual(before, self._snapshot(root))
                issued = prompt.holistic(root, "M001")
            self.assertEqual(preview, (root / issued).read_text(encoding="utf-8"))
            self._check_pages(root, preview)

    def test_review_refuses_tampered_notes_and_mandatory_overflow(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixture(root)
            self._verified(root, notes=True)
            rel = "05_governance/reviews/m001/notes.md"
            original = (root / rel).read_bytes()
            (root / rel).write_text("altered coder explanation\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "drift"):
                prompt.review(root, SID, preview=True)
            (root / rel).write_bytes(original)
            frozen = prompt._frozen
            with (
                mock.patch.object(
                    prompt,
                    "_frozen",
                    side_effect=lambda *args: {
                        **frozen(*args),
                        "acceptance": ["mandatory " * 6000],
                    },
                ),
                mock.patch.object(evidence, "review_diff") as diff,
            ):
                with self.assertRaisesRegex(ValueError, "49152"):
                    prompt.review(root, SID, preview=True)
                diff.assert_not_called()

    def test_sanitizer_preserves_relative_and_regex_but_scrubs_real_paths(self):
        root = Path("C:/repo")
        ordinary = "./scripts/x.py ../scripts/x.py r'^/api/(?P<id>\\d+)/$' / 1/2 2026/09/12"
        self.assertEqual(verify._scrub(ordinary.encode(), root, {}), ordinary)
        for value in (
            "/home/user/private/file.txt",
            r"C:\Users\Ada\private.txt",
            r"\\server\share\private.txt",
            "file:///home/user/private.txt",
        ):
            with self.subTest(value=value):
                self.assertIn("<absolute-path>", verify._scrub(value.encode(), root, {}))


if __name__ == "__main__":
    unittest.main()
