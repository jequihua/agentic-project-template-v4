"""Review regressions for bounded payloads and exact recovery witnesses."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _commit as commit
import _common as c
import test_commit_v2 as fixtures
import test_protocol_v2 as manual


class CommitReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CommitTests("test_large_literal_stage_and_bounded_diff")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_two_40mb_blobs_recover_in_fresh_process_and_remain_historical_witnesses(self):
        case = self.fixture
        case.write(".gitattributes", b"* text=auto\n*.bin -text\n")
        case.write("one.bin", b"A" * 40_000_000)
        case.write("two.bin", b"B" * 40_000_000)
        intent = case.intent([".gitattributes", "one.bin", "two.bin"])
        recovered = case.fresh()
        self.assertEqual(recovered.returncode, 0, recovered.stderr.decode())
        rows = json.loads(recovered.stdout)
        self.assertEqual((rows[0]["id"], rows[0]["state"]), (intent["id"], "completed"))
        witness = rows[0]["commit"]
        case.write("later.txt", b"legitimate descendant\n")
        case.command("add", "later.txt")
        case.command("commit", "-qm", "later change")
        historical = case.fresh()
        self.assertEqual(historical.returncode, 0, historical.stderr.decode())
        self.assertEqual(json.loads(historical.stdout)[0]["commit"], witness)
        self.assertEqual(case.command("status", "--porcelain"), b"")

    def test_quoted_trailer_and_invalid_matching_commit_are_not_duplicate_witnesses(self):
        case = self.fixture
        case.write("product.txt", b"approved\n")
        intent = case.intent()
        witness = commit.recover(case.root, case.events, case.rm, execute=True)[0]["commit"]
        case.command(
            "commit",
            "--allow-empty",
            "-qm",
            "Documentation\n\nTemplate-Operation: " + intent["id"] + "\n\nQuoted history.",
        )
        tree = case.command("rev-parse", intent["parent"] + "^{tree}").decode().strip()
        invalid = case.command(
            "commit-tree",
            tree,
            "-p",
            intent["parent"],
            input=(intent["message"] + "\n\nTemplate-Operation: " + intent["id"] + "\n").encode(),
        )
        case.command("update-ref", "refs/heads/invalid-quoted-witness", invalid.decode().strip())
        self.assertEqual(commit.status(case.root, case.events, case.rm)[0]["commit"], witness)
        with self.assertRaisesRegex(ValueError, "completed commit intent cannot be cancelled"):
            commit.cancel_check(case.root, case.events, case.rm, intent["id"])

    def test_inflight_resolution_requires_actor_and_reason_at_api_boundary(self):
        case = self.fixture
        case.write("product.txt", b"approved\n")
        intent = case.intent()
        marker = commit._marker(case.root)
        marker.write_text(json.dumps({"operation": intent["id"], "parent": intent["parent"]}))
        before = marker.read_bytes()
        with self.assertRaises(TypeError):
            commit.resolve_inflight(case.root, intent["id"])
        for reason, by in ((None, None), ("", "human"), ("finished", "frutlups")):
            with self.subTest(by=by), self.assertRaisesRegex(ValueError, "human/architect"):
                commit.resolve_inflight(case.root, intent["id"], reason, by)
            self.assertEqual(marker.read_bytes(), before)
        commit.resolve_inflight(case.root, intent["id"], "owned child was observed exited", "human")
        self.assertFalse(marker.exists())
        resolved = marker.with_name("template-commit-resolved-" + intent["id"])
        self.assertEqual(json.loads(resolved.read_text())["resolution"]["by"], "human")

    def test_exact_completed_witness_can_archive_its_stale_marker_only_on_execute(self):
        case = self.fixture
        case.write("product.txt", b"approved\n")
        intent = case.intent()
        crashed = case.fresh(crash=True)
        self.assertEqual(crashed.returncode, 17, crashed.stderr.decode())
        marker = commit._marker(case.root)
        self.assertTrue(marker.exists())
        read_only = commit.recover(case.root, case.events, case.rm)
        self.assertEqual(read_only[0]["state"], "completed")
        self.assertTrue(marker.exists())
        case.command("rev-parse", "HEAD")
        recovered = case.fresh()
        self.assertEqual(recovered.returncode, 0, recovered.stderr.decode())
        self.assertFalse(marker.exists())
        record = json.loads(
            marker.with_name("template-commit-resolved-" + intent["id"]).read_text()
        )
        self.assertEqual(record["completion"]["commit"], read_only[0]["commit"])

    def test_completed_witness_validates_once_per_command_and_ref_change_is_not_cached(self):
        case = self.fixture
        case.write("product.txt", b"approved\n")
        intent = case.intent()
        witness = commit.recover(case.root, case.events, case.rm, execute=True)[0]["commit"]
        with mock.patch.object(commit, "_candidate", wraps=commit._candidate) as validate:
            with c.command_scope():
                commit.status(case.root, case.events, case.rm)
                commit.status(case.root, case.events, case.rm)
                self.assertEqual(validate.call_count, 1)
                tree = case.command("rev-parse", witness + "^{tree}").decode().strip()
                env = dict(os.environ, GIT_COMMITTER_DATE="2030-01-01T00:00:00Z")
                other = case.command(
                    "commit-tree",
                    tree,
                    "-p",
                    intent["parent"],
                    env=env,
                    input=(
                        intent["message"] + "\n\nTemplate-Operation: " + intent["id"] + "\n"
                    ).encode(),
                )
                case.command("update-ref", "refs/heads/new-valid-witness", other.decode().strip())
                with self.assertRaisesRegex(ValueError, "duplicate commit witnesses"):
                    commit.status(case.root, case.events, case.rm)
                self.assertEqual(validate.call_count, 2)
            case.command("update-ref", "-d", "refs/heads/new-valid-witness")
            with c.command_scope():
                commit.status(case.root, case.events, case.rm)
            self.assertEqual(validate.call_count, 3)

    def test_batched_framework_blobs_still_reject_ledger_and_manifest_corruption(self):
        case = self.fixture
        case.write("product.txt", b"approved\n")
        intent = case.intent()
        _, manifest, prefix = commit._load(case.root, case.events[-1])
        paths = ["product.txt", commit.LEDGER, intent["manifest"]["path"]]
        commit.g.stage_exact(case.root, paths)
        parent = commit._tree(case.root, intent["parent"])

        def candidate():
            tree = case.command("write-tree").decode().strip()
            commit._candidate(
                case.root, commit._tree(case.root, tree), parent, manifest, intent, prefix
            )

        candidate()
        for path, refusal in (
            (commit.LEDGER, "ordered approval prefix"),
            (intent["manifest"]["path"], "manifest differs"),
        ):
            with self.subTest(path=path):
                original = (case.root / path).read_bytes()
                case.write(path, original + b"unapproved content\n")
                case.command("add", "--", path)
                with self.assertRaisesRegex(ValueError, refusal):
                    candidate()
                case.write(path, original)
                case.command("add", "--", path)

    def test_candidate_lookup_requires_an_available_commit_parent(self):
        case = self.fixture
        intent = case.intent()
        tree = case.command("rev-parse", "HEAD^{tree}").decode().strip()
        for parent in ("a" * 40, tree):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                commit._candidates(case.root, {**intent, "parent": parent})

    def test_replacement_refs_cannot_change_cached_or_fresh_canonical_witnesses(self):
        case = self.fixture
        case.write("product.txt", b"approved\n")
        intent = case.intent()
        witness = commit.recover(case.root, case.events, case.rm, execute=True)[0]["commit"]
        case.write("product.txt", b"unapproved replacement\n")
        case.command("add", "product.txt")
        tree = case.command("write-tree").decode().strip()
        message = intent["message"] + "\n\nTemplate-Operation: " + intent["id"] + "\n"
        replacement = (
            case.command("commit-tree", tree, "-p", intent["parent"], input=message.encode())
            .decode()
            .strip()
        )
        case.write("product.txt", b"approved\n")
        case.command("add", "product.txt")
        with c.command_scope():
            self.assertEqual(commit.status(case.root, case.events, case.rm)[0]["commit"], witness)
            case.command("replace", witness, replacement)
            self.assertEqual(
                case.command("show", witness + ":product.txt"), b"unapproved replacement\n"
            )
            self.assertEqual(commit.status(case.root, case.events, case.rm)[0]["commit"], witness)
        self.assertEqual(commit.status(case.root, case.events, case.rm)[0]["commit"], witness)
        self.assertEqual(
            commit.g.run(case.root, "show", witness + ":product.txt").stdout, b"approved\n"
        )
        self.assertEqual(
            case.command("rev-parse", "refs/replace/" + witness).decode().strip(), replacement
        )


class CommitCliReviewTests(unittest.TestCase):
    def pending(self):
        case = manual.ManualIntegrationTests(
            "test_zero_change_manual_loop_and_pending_commit_freeze"
        )
        case.setUp()
        self.addCleanup(case.doCleanups)
        manual.prompt.coding(case.root, "M001-S01")
        case.success("coded", "M001-S01")
        self.assertTrue(manual.verify.run(case.root, "M001-S01", 10)[0]["ok"])
        (case.root / "05_governance/reviews/pass.md").write_text(manual.PASS_REPORT)
        case.success("record", "05_governance/reviews/pass.md")
        with mock.patch.object(commit, "recover", side_effect=ValueError("before dispatch")):
            result = manual.ledger.main(
                ["--root", str(case.root), "accept", "M001-S01", "--commit"]
            )
        self.assertEqual(result, 2)
        events = manual.ledger.read(case.root / commit.LEDGER)
        intent = next(row["commit_intent"] for row in events if "commit_intent" in row)
        marker = commit._marker(case.root)
        marker.write_text(json.dumps({"operation": intent["id"], "parent": intent["parent"]}))
        return case, intent, marker

    def test_recover_cli_requires_reason_then_records_actor_and_can_complete(self):
        case, intent, marker = self.pending()
        before = marker.read_bytes()
        missing = case.cli("recover", "--git-resolved", intent["id"], "--by", "architect")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("requires --reason", missing.stderr.decode())
        self.assertEqual(marker.read_bytes(), before)
        reason = "The exact owned Git child was observed exited"
        result = case.success(
            "recover", "--git-resolved", intent["id"], "--reason", reason, "--by", "architect"
        )
        self.assertEqual(json.loads(result.stdout)[0]["state"], "pending")
        resolution = json.loads(
            marker.with_name("template-commit-resolved-" + intent["id"]).read_text()
        )
        self.assertEqual(resolution["resolution"], {"by": "architect", "reason": reason})
        self.assertFalse(marker.exists())
        result = case.success("recover", "--execute")
        self.assertEqual(json.loads(result.stdout)[0]["state"], "completed")

    def test_cancel_cli_records_explicit_exit_attribution_and_preserves_index(self):
        case, intent, marker = self.pending()
        before = fixtures.CommitTests.command(case, "ls-files", "--stage", "-z")
        reason = "Git exited; retained edits require another review"
        case.success("cancel", intent["id"], "--git-resolved", "--reason", reason, "--by", "human")
        resolution = json.loads(
            marker.with_name("template-commit-resolved-" + intent["id"]).read_text()
        )
        self.assertEqual(resolution["resolution"], {"by": "human", "reason": reason})
        self.assertFalse(marker.exists())
        self.assertEqual(fixtures.CommitTests.command(case, "ls-files", "--stage", "-z"), before)
        self.assertEqual(case.state()["slices"]["M001-S01"]["step"], "fix")

    def test_write_admission_refreshes_refs_after_immutable_validation_is_cached(self):
        case, intent, _ = self.pending()
        case.success(
            "recover", "--git-resolved", intent["id"], "--reason", "child exited", "--execute"
        )
        command = fixtures.CommitTests.command
        tree = command(case, "rev-parse", "HEAD^{tree}").decode().strip()
        rm = manual.roadmap.load(case.root)
        with c.command_scope():
            manual.protocol.ensure_writable(case.root, rm)
            message = intent["message"] + "\n\nTemplate-Operation: " + intent["id"] + "\n"
            other = command(
                case,
                "commit-tree",
                tree,
                "-p",
                intent["parent"],
                input=message.encode(),
                env=dict(os.environ, GIT_COMMITTER_DATE="2030-01-01T00:00:00Z"),
            )
            command(case, "update-ref", "refs/heads/new-valid-witness", other.decode().strip())
            with self.assertRaisesRegex(ValueError, "duplicate commit witnesses"):
                manual.protocol.ensure_writable(case.root, rm)


if __name__ == "__main__":
    unittest.main()
