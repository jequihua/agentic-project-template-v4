"""Real Git, literal selections and process-restart commit witness regressions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _commit as commit  # noqa: E402
import _git as git  # noqa: E402


class CommitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="template-commit-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "project"
        self.root.mkdir()
        self.rm = {"schema": "frutlups.roadmap/2", "verification": {}}
        self.events = []
        self.command("init", "-q")
        self.command("config", "user.name", "Template Test")
        self.command("config", "user.email", "template@example.invalid")
        self.command("config", "core.autocrlf", "false")
        self.write(".gitattributes", b"* text=auto\n")
        self.write("product.txt", b"before\n")
        self.write(commit.LEDGER, b"")
        self.command("add", "--all")
        self.command("commit", "-qm", "baseline")

    def command(self, *args, cwd=None, input=None, env=None):
        result = subprocess.run(
            ["git", "-C", str(cwd or self.root), *args],
            input=input,
            capture_output=True,
            check=True,
            env=env,
        )
        return result.stdout

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def append(self, event):
        self.events.append(event)
        with (self.root / commit.LEDGER).open("ab") as stream:
            stream.write((json.dumps(event) + "\n").encode())

    def intent(self, paths=("product.txt",), scope="M001-S01"):
        value = commit.request_intent(
            self.root,
            paths,
            scope,
            "Accept " + scope,
            self.rm,
            "05_governance/reviews",
        )
        event = {
            "schema": "frutlups.ledger/2",
            "t": "2026-09-12T00:00:00Z",
            "ev": "accepted" if "-S" in scope else "milestone_done",
            "by": "architect",
            "commit_intent": value,
        }
        event.update({"slice": scope, "round": 1} if "-S" in scope else {"milestone": scope})
        self.append(event)
        return value

    def fresh(self, *, crash=False):
        source = (
            "import json,os,sys;from pathlib import Path;"
            "sys.path.insert(0,sys.argv[1]);import _commit as c;import _git as g;"
            "root=Path(sys.argv[2]);"
            "events=[json.loads(s) for s in (root/c.LEDGER).read_text().splitlines() if s];"
            "rm={'schema':'frutlups.roadmap/2','verification':{}};"
        )
        if crash:
            source += (
                "original=g.run\n"
                "def fail_after_git(root,*args,**kwargs):\n"
                " result=original(root,*args,**kwargs)\n"
                " if args and args[0]=='commit':os._exit(17)\n"
                " return result\n"
                "g.run=fail_after_git\n"
            )
        source += "print(json.dumps(c.recover(root,events,rm,execute=True)))"
        return subprocess.run(
            [sys.executable, "-B", "-c", source, str(ROOT / "scripts"), str(self.root)],
            capture_output=True,
            timeout=180,
        )

    def test_large_literal_stage_and_bounded_diff(self):
        paths = []
        for number in range(700):
            rel = "bulk/" + f"{number:04d}-" + "long-name-" * 5 + "[literal]-é.txt"
            self.write(rel, b"a short artifact\n")
            paths.append(rel)
        literals = ["--leading.txt", "space name.txt", "unicode-界.txt"]
        if os.name != "nt":
            literals += ["literal*.txt", "literal?.txt"]
        for rel in literals:
            self.write(rel, b"literal path only\n")
            paths.append(rel)
        self.assertGreater(sum(len(path) + 1 for path in paths), 40_000)
        self.write("bulk/literal-must-remain.txt", b"unrelated\n")
        git.stage_exact(self.root, paths)
        self.assertEqual(git.staged_paths(self.root), set(paths))
        self.assertIn("?? bulk/literal-must-remain.txt", self.command("status", "--short").decode())
        rendered = git.bounded_diff(self.root, "HEAD", paths, limit=2048)
        self.assertLessEqual(len(rendered.encode()), 2048)
        self.assertIn("diff truncated", rendered)
        self.assertEqual(git.bounded_diff(self.root, "HEAD", [], 2048), "")

    def test_unrelated_index_is_preserved(self):
        self.write("unrelated.txt", b"staged user content\n")
        self.command("add", "unrelated.txt")
        self.write("product.txt", b"approved\n")
        before = self.command("ls-files", "--stage", "-z")
        with self.assertRaisesRegex(ValueError, "unrelated staged"):
            git.stage_exact(self.root, ["product.txt"])
        self.assertEqual(self.command("ls-files", "--stage", "-z"), before)
        with self.assertRaisesRegex(ValueError, "unrelated staged"):
            git.stage_exact(self.root, [])

    def test_rename_origins_and_range_diff(self):
        self.command("mv", "product.txt", "[renamed].txt")
        selected = git.approved_paths(self.root, [{"path": "[renamed].txt", "kind": "renamed"}])
        self.assertEqual(selected, ["[renamed].txt", "product.txt"])
        self.intent(selected)
        rows = commit.recover(self.root, self.events, self.rm, execute=True)
        self.assertEqual(rows[0]["state"], "completed")
        text = git.bounded_diff(self.root, "HEAD~1..HEAD", selected, 2048)
        self.assertIn("[renamed].txt", text)

    def test_recovery_before_stage_is_read_only_then_fresh_process(self):
        self.write("product.txt", b"approved\n")
        self.intent()
        before = self.command("status", "--porcelain=v1", "-z")
        diagnosed = commit.recover(self.root, self.events, self.rm, execute=False)
        self.assertEqual(diagnosed[0]["state"], "pending")
        self.assertEqual(self.command("status", "--porcelain=v1", "-z"), before)
        result = self.fresh()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout)[0]["state"], "completed")
        self.assertEqual(self.command("rev-list", "--count", "HEAD").strip(), b"2")
        self.assertEqual(self.command("status", "--porcelain=v1"), b"")

    def test_recovery_after_stage_and_after_unobserved_git_success(self):
        self.write("product.txt", b"approved\n")
        intent = self.intent()
        git.stage_exact(self.root, ["product.txt", commit.LEDGER, intent["manifest"]["path"]])
        result = self.fresh(crash=True)
        self.assertEqual(result.returncode, 17, result.stderr.decode())
        self.assertTrue(commit._marker(self.root).exists())
        result = self.fresh()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout)[0]["state"], "completed")
        self.assertEqual(self.command("rev-list", "--count", "HEAD").strip(), b"2")

    def test_two_approvals_and_later_descendants_preserve_historical_witnesses(self):
        self.write("product.txt", b"first\n")
        first = self.intent()
        commit.recover(self.root, self.events, self.rm, execute=True)
        self.write("product.txt", b"second\n")
        self.intent(scope="M001-S02")
        commit.recover(self.root, self.events, self.rm, execute=True)
        self.write("product.txt", b"later legitimate descendant\n")
        self.command("add", "product.txt")
        self.command("commit", "-qm", "later work")
        self.write(first["manifest"]["path"], b"current worktree drift\n")
        rows = commit.status(self.root, self.events, self.rm)
        self.assertEqual([r["state"] for r in rows], ["completed", "completed"])

    def test_pending_index_and_head_drift_refuse(self):
        self.write("product.txt", b"approved\n")
        self.intent()
        self.write("product.txt", b"unapproved staged content\n")
        self.command("add", "product.txt")
        self.write("product.txt", b"approved\n")
        before = self.command("ls-files", "--stage", "-z")
        with self.assertRaises(ValueError):
            commit.recover(self.root, self.events, self.rm, execute=True)
        self.assertEqual(self.command("ls-files", "--stage", "-z"), before)
        self.command("commit", "-qm", "unexplained movement")
        with self.assertRaisesRegex(ValueError, "HEAD movement"):
            commit.recover(self.root, self.events, self.rm, execute=True)

    def test_raw_storage_survives_git_and_clean_clone(self):
        self.write(".gitattributes", b"* text=auto\nraw/** -text\n")
        payload = {
            "raw/lf.csv": b"x,y\n1,2\n",
            "raw/crlf.json": b'{"x":1}\r\n',
            "raw/binary.bin": bytes(range(256)),
        }
        for rel, value in payload.items():
            self.write(rel, value)
        self.intent([".gitattributes", *payload])
        commit.recover(self.root, self.events, self.rm, execute=True)
        checkout = Path(self.directory.name) / "materialized"
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", str(self.root), str(checkout)],
            check=True,
            capture_output=True,
        )
        for rel, value in payload.items():
            with self.subTest(path=rel):
                self.assertEqual(self.command("show", "HEAD:" + rel), value)
                self.assertEqual((checkout / rel).read_bytes(), value)
                self.assertEqual(
                    hashlib.sha256((checkout / rel).read_bytes()).digest(),
                    hashlib.sha256(value).digest(),
                )

    def test_wrong_attributes_fail_before_completion_and_can_cancel(self):
        self.write(".gitattributes", b"* text=auto\nraw/** -text\n")
        self.command("add", ".gitattributes")
        self.command("commit", "-qm", "raw policy")
        self.write("raw/crlf.csv", b"x,y\r\n1,2\r\n")
        intent = self.intent(["raw/crlf.csv"])
        self.write(".gitattributes", b"* text=auto\nraw/** text eol=lf\n")
        with self.assertRaisesRegex(ValueError, "Git blob content differs"):
            commit.recover(self.root, self.events, self.rm, execute=True)
        self.assertEqual(self.command("rev-list", "--count", "HEAD").strip(), b"2")
        before = self.command("ls-files", "--stage", "-z")
        commit.cancel_check(self.root, self.events, self.rm, intent["id"])
        self.append(
            {
                "schema": "frutlups.ledger/2",
                "ev": "commit_cancelled",
                "by": "architect",
                "t": "2026-09-12T00:00:00Z",
                "operation": intent["id"],
                "reason": "storage policy needs a new review",
                "retain_acceptance": False,
            }
        )
        state = commit.status(self.root, self.events, self.rm)[0]["state"]
        self.assertEqual(state, "cancelled")
        self.assertEqual(self.command("ls-files", "--stage", "-z"), before)

    def test_declared_hook_binds_candidate_and_rejects_mutation(self):
        self.write("product.txt", b"approved\n")
        self.rm["verification"]["git_boundary"] = [
            "python",
            "-c",
            "import os;assert len(os.environ['TEMPLATE_CANDIDATE_TREE'])>=40",
        ]
        self.intent()
        commit.recover(self.root, self.events, self.rm, execute=True)
        self.write("product.txt", b"second\n")
        self.rm["verification"]["git_boundary"] = [
            "python",
            "-c",
            "from pathlib import Path;Path('product.txt').write_text('drift')",
        ]
        self.intent(scope="M001-S02")
        with self.assertRaisesRegex(ValueError, "mutated approved"):
            commit.recover(self.root, self.events, self.rm, execute=True)
        self.assertEqual((self.root / "product.txt").read_text(), "drift")

    def test_boundary_policy_cannot_be_removed_or_changed_after_approval(self):
        self.write("product.txt", b"approved\n")
        self.rm["verification"]["git_boundary"] = ["python", "-c", "pass"]
        self.intent()
        before = self.command("ls-files", "--stage", "-z")
        changed = [
            {"schema": "frutlups.roadmap/2", "verification": {}},
            {**self.rm, "verification": {**self.rm["verification"], "timeout_seconds": 5}},
            {**self.rm, "runtime": {"python": "3.14"}},
        ]
        for rm in changed:
            with self.subTest(policy=rm), self.assertRaisesRegex(ValueError, "policy changed"):
                commit.recover(self.root, self.events, rm, execute=True)
        self.assertEqual(self.command("rev-list", "--count", "HEAD").strip(), b"1")
        self.assertEqual(self.command("ls-files", "--stage", "-z"), before)

    def test_milestone_close_and_unresolved_dispatch(self):
        intent = self.intent([], scope="M001")
        marker = commit._marker(self.root)
        marker.write_text(json.dumps({"operation": intent["id"], "parent": intent["parent"]}))
        with self.assertRaisesRegex(ValueError, "unresolved"):
            commit.recover(self.root, self.events, self.rm, execute=True)
        with self.assertRaisesRegex(ValueError, "unresolved"):
            commit.cancel_check(self.root, self.events, self.rm, intent["id"])
        commit.resolve_inflight(self.root, intent["id"], "fixture Git process exited", "architect")
        self.assertTrue(marker.with_name("template-commit-resolved-" + intent["id"]).exists())
        self.assertEqual(
            commit.recover(self.root, self.events, self.rm, execute=True)[0]["state"], "completed"
        )

    def test_cancel_preserves_invalid_commit_and_does_not_fabricate_completion(self):
        self.write("product.txt", b"approved\n")
        intent = self.intent()
        self.write("product.txt", b"unapproved hook output\n")
        git.stage_exact(self.root, ["product.txt", commit.LEDGER, intent["manifest"]["path"]])
        message = intent["message"] + "\n\nTemplate-Operation: " + intent["id"]
        self.command("commit", "-qm", message)
        before = self.command("rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "Git blob content differs"):
            commit.status(self.root, self.events, self.rm)
        commit.cancel_check(self.root, self.events, self.rm, intent["id"])
        self.append(
            {
                "schema": "frutlups.ledger/2",
                "ev": "commit_cancelled",
                "by": "architect",
                "t": "2026-09-12T00:00:00Z",
                "operation": intent["id"],
                "reason": "invalid commit retained for inspection",
                "retain_acceptance": False,
            }
        )
        self.assertEqual(commit.status(self.root, self.events, self.rm)[0]["state"], "cancelled")
        self.assertEqual(self.command("rev-parse", "HEAD"), before)
        self.assertEqual((self.root / "product.txt").read_bytes(), b"unapproved hook output\n")

    def test_duplicate_witnesses_refuse_and_never_cancel_valid_approval(self):
        self.write("product.txt", b"approved\n")
        intent = self.intent()
        commit.recover(self.root, self.events, self.rm, execute=True)
        with self.assertRaisesRegex(ValueError, "cannot be cancelled"):
            commit.cancel_check(self.root, self.events, self.rm, intent["id"])
        tree = self.command("rev-parse", "HEAD^{tree}").decode().strip()
        message = intent["message"] + "\n\nTemplate-Operation: " + intent["id"]
        env = dict(os.environ, GIT_COMMITTER_DATE="2001-01-01T00:00:00Z")
        other = self.command("commit-tree", tree, "-p", intent["parent"], "-m", message, env=env)
        self.command("update-ref", "refs/heads/duplicate-witness", other.decode().strip())
        with self.assertRaisesRegex(ValueError, "duplicate commit witnesses"):
            commit.status(self.root, self.events, self.rm)
        with self.assertRaisesRegex(ValueError, "cannot be cancelled"):
            commit.cancel_check(self.root, self.events, self.rm, intent["id"])

    def test_absent_prior_untracked_tombstone_has_no_commit_delta(self):
        intent = self.intent(["never-tracked.txt"])
        manifest = json.loads((self.root / intent["manifest"]["path"]).read_text())
        self.assertEqual(manifest["entries"], [])
        rows = commit.recover(self.root, self.events, self.rm, execute=True)
        self.assertEqual(rows[0]["state"], "completed")
        changed = self.command("diff", "--name-only", "HEAD~1", "HEAD")
        self.assertNotIn(b"never-tracked.txt", changed)


if __name__ == "__main__":
    unittest.main()
