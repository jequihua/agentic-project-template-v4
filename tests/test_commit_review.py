"""Review regressions for bounded payloads and exact recovery witnesses."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _commit as commit
import _common as c
import _evidence as evidence
import test_commit_v2 as fixtures
import test_protocol_v2 as manual


class CommitReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CommitTests("test_large_literal_stage_and_bounded_diff")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def assert_deleted_batch(self, count):
        case = self.fixture
        expected = []
        for number in range(count):
            rel = f"product/file-{number:04d}.txt"
            data = f"original {number}\n".encode()
            case.write(rel, data)
            expected.append(
                {"path": rel, "sha": hashlib.sha256(data).hexdigest(), "kind": "deleted"}
            )
        case.command("add", ".")
        case.command("commit", "-qm", "deletion baseline")
        for row in expected:
            (case.root / row["path"]).unlink()
        with c.command_scope(), mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
            self.assertEqual(evidence.changed_files(case.root), expected)
        self.assertEqual(len(calls.call_args_list), 5)
        self.assertEqual(
            [call.args[1] for call in calls.call_args_list],
            ["status", "rev-parse", "ls-tree", "cat-file", "cat-file"],
        )

    def test_fifty_deletions_use_one_head_lookup(self):
        self.assert_deleted_batch(50)

    def test_seven_hundred_deletions_use_one_head_lookup(self):
        self.assert_deleted_batch(700)

    def test_head_lookup_empty_absent_deduplicated_and_cached(self):
        case = self.fixture
        with c.command_scope(), mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
            self.assertEqual(evidence.head_shas(case.root, []), {})
            with self.assertRaises(ValueError):
                evidence.head_shas(case.root, ["../escape"])
            self.assertEqual(calls.call_count, 0)
            expected = {"product.txt": hashlib.sha256(b"before\n").hexdigest()}
            self.assertEqual(evidence.head_shas(case.root, ["product.txt"] * 2), expected)
            self.assertEqual(calls.call_count, 4)
            calls.reset_mock()
            self.assertEqual(evidence.head_shas(case.root, ["product.txt"]), expected)
            self.assertEqual(calls.call_count, 1)
            calls.reset_mock()
            absent = [f"absent/{n}.txt" for n in range(700)]
            self.assertEqual(evidence.head_shas(case.root, absent), dict.fromkeys(absent))
            self.assertEqual(calls.call_count, 1)
        with c.command_scope(), mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
            self.assertEqual(evidence.head_shas(case.root, absent), dict.fromkeys(absent))
            self.assertEqual(calls.call_count, 2)
        with mock.patch.object(commit.g, "run", side_effect=AssertionError("unexpected Git")):
            self.assertTrue(evidence.matches_head(case.root, "absent", heads={"absent": None}))
            with self.assertRaises(KeyError):
                evidence.matches_head(case.root, "product.txt", heads={})

    def test_dirty_baseline_batches_only_unexplained_paths(self):
        case = self.fixture
        rm = {"milestones": [{"slices": [{"id": "M001-S01"}]}]}
        paths = [f"product/{n:03d}.txt" for n in range(50)]
        for rel in paths:
            case.write(rel, (rel + " original\n").encode())
        case.command("add", ".")
        case.command("commit", "-qm", "before dirty edits")
        for rel in paths:
            case.write(rel, (rel + " changed\n").encode())
        with c.command_scope(), mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
            rows = evidence.prompt_baseline(case.root, rm, [], "M001-S01", True)
        self.assertEqual([row["path"] for row in rows], paths)
        self.assertEqual(calls.call_count, 5)
        self.assertTrue(all(row["sha"] == c.sha(case.root / row["path"]) for row in rows))
        with self.assertRaisesRegex(ValueError, "unknown dirty paths"):
            evidence.prompt_baseline(case.root, rm, [], "M001-S01")
        for events, prospective in (
            ([], paths),
            ([{"ev": "coded", "slice": "M001-S01", "changed": rows}], ()),
        ):
            with c.command_scope(), mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
                self.assertEqual(
                    evidence.prompt_baseline(
                        case.root, rm, events, "M001-S01", prospective=prospective
                    ),
                    rows,
                )
            self.assertEqual([call.args[1] for call in calls.call_args_list], ["status"])

    def test_directory_replaced_by_file_needs_explicit_dirty_admission(self):
        case = self.fixture
        case.write("folder/nested.txt", b"nested\n")
        case.command("add", ".")
        case.command("commit", "-qm", "directory in HEAD")
        self.assertIsNone(evidence.head_sha(case.root, "folder"))
        (case.root / "folder/nested.txt").unlink()
        (case.root / "folder").rmdir()
        case.write("folder", b"now a regular file\n")
        rm = {"milestones": [{"slices": [{"id": "M001-S01"}]}]}
        with self.assertRaisesRegex(ValueError, "unknown dirty paths"):
            evidence.prompt_baseline(case.root, rm, [], "M001-S01")
        rows = evidence.prompt_baseline(case.root, rm, [], "M001-S01", True)
        self.assertEqual(
            {row["path"]: row["kind"] for row in rows},
            {"folder": "added", "folder/nested.txt": "deleted"},
        )

    def test_head_lookup_rechecks_head_and_worktree_inside_one_scope(self):
        case = self.fixture
        with c.command_scope():
            original = evidence.head_shas(case.root, ["product.txt"])
            stat = (case.root / "product.txt").stat()
            case.write("product.txt", b"tamper\n")
            os.utime(case.root / "product.txt", ns=(stat.st_atime_ns, stat.st_mtime_ns))
            self.assertFalse(evidence.matches_head(case.root, "product.txt", heads=original))
            case.command("add", ".")
            case.command("commit", "-qm", "owner hotfix")
            self.assertNotEqual(evidence.head_shas(case.root, ["product.txt"]), original)
            self.assertTrue(evidence.matches_head(case.root, "product.txt"))

    def test_head_lookup_cache_exhaustion_and_unscoped_reads_remain_valid(self):
        case = self.fixture
        expected = {"product.txt": hashlib.sha256(b"before\n").hexdigest()}
        with c.command_scope():
            c.cache("commit_trees")[None] = commit.g.OUTPUT_LIMIT
            for _ in range(2):
                with mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
                    self.assertEqual(evidence.head_shas(case.root, ["product.txt"]), expected)
                self.assertEqual(sum(call.args[1] == "ls-tree" for call in calls.call_args_list), 1)
            self.assertEqual(c.cache("commit_trees"), {None: commit.g.OUTPUT_LIMIT})
        for _ in range(2):
            with mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
                self.assertEqual(evidence.head_shas(case.root, ["product.txt"]), expected)
            self.assertEqual(calls.call_count, 4)

    def test_head_lookup_unborn_and_broken_refs_are_distinct(self):
        case = self.fixture
        head = case.command("rev-parse", "HEAD").decode().strip()
        tree = case.command("rev-parse", "HEAD^{tree}").decode().strip()
        saved = (case.root / ".git/HEAD").read_bytes()
        for name, content, absent in (
            ("unborn", None, True),
            ("malformed", "broken\n", False),
            ("unavailable", "a" * 40 + "\n", False),
            ("tree", tree + "\n", False),
        ):
            with self.subTest(name=name):
                if content is not None:
                    case.write(".git/refs/heads/" + name, content.encode())
                case.write(".git/HEAD", f"ref: refs/heads/{name}\n".encode())
                if absent:
                    self.assertEqual(
                        evidence.head_shas(case.root, ["product.txt"]), {"product.txt": None}
                    )
                else:
                    with self.assertRaises(ValueError):
                        evidence.head_sha(case.root, "product.txt")
        for content in ("b" * 40 + "\n", "ref: refs/tags/absent\n"):
            with self.subTest(head=content), self.assertRaises(ValueError):
                case.write(".git/HEAD", content.encode())
                evidence.head_sha(case.root, "product.txt")
        case.write(".git/HEAD", (head + "\n").encode())
        self.assertEqual(
            evidence.head_sha(case.root, "product.txt"), hashlib.sha256(b"before\n").hexdigest()
        )
        case.write(".git/HEAD", saved)
        with self.assertRaises(ValueError):
            evidence.head_sha(case.root.parent, "product.txt")

    def test_head_lookup_missing_tree_or_blob_does_not_become_absence(self):
        case = self.fixture
        for revision in ("HEAD^{tree}", "HEAD:product.txt"):
            oid = case.command("rev-parse", revision).decode().strip()
            path = case.root / ".git/objects" / oid[:2] / oid[2:]
            saved = path.read_bytes()
            mode = path.stat().st_mode
            path.chmod(mode | 0o200)
            path.unlink()
            try:
                with (
                    self.subTest(revision=revision),
                    c.command_scope(),
                    self.assertRaises(ValueError),
                ):
                    evidence.head_sha(case.root, "product.txt")
            finally:
                path.write_bytes(saved)
                path.chmod(mode)

    def test_head_lookup_keeps_hash_storage_types_and_replacement_policy(self):
        case = self.fixture
        values = {
            "crlf.txt": b"a\r\nb\r\n",
            "binary.bin": b"a\0\r\nb",
            "-literal[1].txt": b"literal\n",
        }
        case.write(".gitattributes", b"* -text\n")
        for rel, data in values.items():
            case.write(rel, data)
        case.command("add", ".")
        case.command("commit", "-qm", "raw bytes")
        expected = {rel: c.evidence_sha_bytes(data) for rel, data in values.items()}
        self.assertEqual(evidence.head_shas(case.root, values), expected)
        original = case.command("rev-parse", "HEAD:crlf.txt").decode().strip()
        replacement = (
            case.command("hash-object", "-w", "--stdin", input=b"replacement\n").decode().strip()
        )
        case.command("replace", original, replacement)
        self.assertEqual(evidence.head_shas(case.root, values), expected)
        case.command("update-index", "--add", "--cacheinfo", "160000," + original + ",gitlink")
        case.command("commit", "-qm", "gitlink metadata pointing at a blob")
        with self.assertRaisesRegex(ValueError, "not an available blob"):
            evidence.head_sha(case.root, "gitlink")

    def test_head_lookup_full_tree_overflow_refuses_even_an_absent_selection(self):
        case = self.fixture
        original = commit.g.run

        def bounded(root, *args, **kwargs):
            if args[0] == "ls-tree":
                kwargs["limit"] = 16
            return original(root, *args, **kwargs)

        with mock.patch.object(commit.g, "run", side_effect=bounded):
            with self.assertRaisesRegex(ValueError, "bounded metadata"):
                evidence.head_shas(case.root, ["absent"])

    def test_head_lookup_rejects_an_unrelated_non_utf8_tree_entry(self):
        case = self.fixture
        oid = case.command("rev-parse", "HEAD:product.txt").strip()
        tree = (
            case.command(
                "mktree",
                "-z",
                input=b"".join(
                    b"100644 blob " + oid + b"\t" + name + b"\0"
                    for name in (b"product.txt", b"unrelated-\xff")
                ),
            )
            .decode()
            .strip()
        )
        head = case.command("commit-tree", tree, "-m", "invalid unrelated path").decode().strip()
        case.command("update-ref", "HEAD", head)
        for name, lookup in (
            ("commit tree", lambda: commit._tree(case.root, head)),
            ("HEAD fallback", lambda: evidence.head_sha(case.root, "product.txt")),
        ):
            with self.subTest(reader=name):
                with self.assertRaises(ValueError) as caught:
                    lookup()
                self.assertEqual(
                    str(caught.exception), "Git tree path is not valid UTF-8: b'unrelated-\\xff'"
                )
                self.assertIsInstance(caught.exception.__cause__, UnicodeDecodeError)

    def test_head_lookup_caches_do_not_cross_repository_boundaries(self):
        case = self.fixture
        other = case.root.parent / "other"
        shutil.copytree(case.root, other)
        oid = case.command("rev-parse", "HEAD:product.txt").decode().strip()
        path = other / ".git/objects" / oid[:2] / oid[2:]
        path.chmod(path.stat().st_mode | 0o200)
        path.unlink()
        with c.command_scope():
            self.assertIsNotNone(evidence.head_sha(case.root, "product.txt"))
            with self.assertRaises(ValueError):
                evidence.head_sha(other, "product.txt")

    def test_head_symlink_is_a_blob_but_current_symlink_never_matches(self):
        case = self.fixture
        oid = case.command("rev-parse", "HEAD:product.txt").decode().strip()
        case.command("update-index", "--cacheinfo", "120000," + oid + ",product.txt")
        case.command("commit", "-qm", "symlink metadata without a host symlink")
        self.assertEqual(
            evidence.head_sha(case.root, "product.txt"), hashlib.sha256(b"before\n").hexdigest()
        )
        with (
            mock.patch.object(Path, "is_symlink", return_value=True),
            mock.patch.object(commit.g, "run", side_effect=AssertionError("unexpected Git")),
        ):
            self.assertFalse(evidence.matches_head(case.root, "product.txt"))
            self.assertFalse(evidence.matches_head(case.root, "product.txt", heads={}))

    def test_head_lookup_two_large_blobs_share_metadata_but_not_payload_batch(self):
        case = self.fixture
        size = 40 * 1024 * 1024
        for rel, byte in (("one.bin", b"A"), ("two.bin", b"B")):
            case.write(rel, byte * size)
        case.command("add", ".")
        case.command("commit", "-qm", "large lookup")
        with c.command_scope(), mock.patch.object(commit.g, "run", wraps=commit.g.run) as calls:
            result = evidence.head_shas(case.root, ["one.bin", "two.bin"])
        self.assertEqual(
            result,
            {
                "one.bin": hashlib.sha256(b"A" * size).hexdigest(),
                "two.bin": hashlib.sha256(b"B" * size).hexdigest(),
            },
        )
        self.assertEqual(
            [call.args[1:3] for call in calls.call_args_list],
            [
                ("rev-parse", "--verify"),
                ("ls-tree", "-r"),
                ("cat-file", "--batch-check"),
                ("cat-file", "--batch"),
                ("cat-file", "--batch"),
            ],
        )

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
