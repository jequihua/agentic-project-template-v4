"""Real Git and owned-process regressions for verification identity and capture."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import yaml
from test_scaffold import git_init, project_copy, quiet_call, run_git, set_full

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _process
import _workspace
import ledger
import prompt
import verify


def awaiting(root, command, *, v2=False):
    project_copy(root)
    set_full(root, command)
    if v2:
        plan = root / "roadmap.yaml"
        rm = yaml.safe_load(plan.read_text(encoding="utf-8"))
        rm["schema"] = "frutlups.roadmap/2"
        plan.write_text(yaml.safe_dump(rm, sort_keys=False), encoding="utf-8")
    git_init(root)
    run_git(root, "add", ".")
    run_git(root, "commit", "-qm", "baseline")
    prompt.coding(root, "M001-S01")
    (root / "07_app/product.txt").write_text("before\n", encoding="utf-8")
    if quiet_call(ledger.main, ["--root", str(root), "coded", "M001-S01"]):
        raise AssertionError("fixture could not record coding")


class VerificationIdentityTests(unittest.TestCase):
    def test_v2_verifier_uses_frozen_command_after_roadmap_edit(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            awaiting(root, "raise SystemExit(7)", v2=True)
            plan = root / "roadmap.yaml"
            rm = yaml.safe_load(plan.read_text(encoding="utf-8"))
            rm["verification"]["full"] = ["python", "-c", "print('replacement command')"]
            plan.write_text(yaml.safe_dump(rm, sort_keys=False), encoding="utf-8")
            receipt, _ = verify.run(root, "M001-S01", 10)
            self.assertEqual(receipt["schema"], "frutlups.receipt/2")
            self.assertFalse(receipt["ok"])
            self.assertEqual(receipt["commands"][0]["exit"], 7)
            self.assertEqual(receipt["commands"][0]["argv"][1:], ["-c", "raise SystemExit(7)"])
            self.assertTrue(receipt["witness"]["stable"])
            self.assertEqual(receipt["witness"]["before"], receipt["witness"]["after"])
            self.assertNotIn("changed_files", receipt)

    def test_dirty_content_index_head_and_new_file_are_witnessed(self):
        cases = [
            ("pass", True),
            ("from pathlib import Path;Path('07_app/product.txt').write_text('after\\n')", False),
            (
                "import subprocess;subprocess.run(['git','add','07_app/product.txt'],check=True)",
                False,
            ),
            ("from pathlib import Path;Path('new.txt').write_text('new')", False),
            (
                "import subprocess;"
                "subprocess.run(['git','commit','--allow-empty','-m','moved'],check=True)",
                False,
            ),
        ]
        for command, expected in cases:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                awaiting(root, command)
                before = verify.c.status_bytes(root)
                receipt, _ = verify.run(root, "M001-S01", 10)
                self.assertEqual(receipt["ok"], expected)
                self.assertTrue(receipt["tree_dirty_before"])
                self.assertFalse(receipt["tree_clean_after"])
                if "write_text('after" in command:
                    # Porcelain alone cannot distinguish this mutation.
                    after = verify.c.status_bytes(root)
                    self.assertIn(b"07_app/product.txt", before)
                    self.assertIn(b"07_app/product.txt", after)

    def test_snapshot_includes_raw_content_index_flags_and_excludes_ignored_stores(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            (root / ".gitignore").write_text("cache/\n")
            product = root / "product.txt"
            product.write_bytes(b"raw\r\n")
            run_git(root, "add", ".")
            run_git(root, "commit", "-qm", "baseline")
            before = _workspace.snapshot(root)
            (root / "cache").mkdir()
            (root / "cache/deep").mkdir()
            (root / "cache/deep/private.txt").write_text("ignored")
            self.assertEqual(before, _workspace.snapshot(root))
            product.write_bytes(b"raw\n")
            changed = _workspace.snapshot(root)
            self.assertNotEqual(before["files"], changed["files"])
            run_git(root, "update-index", "--assume-unchanged", "product.txt")
            self.assertNotEqual(changed["index"], _workspace.snapshot(root)["index"])

    def test_snapshot_records_symlink_without_reading_target(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            (root / "baseline").write_text("x")
            run_git(root, "add", ".")
            run_git(root, "commit", "-qm", "baseline")
            try:
                os.symlink("missing one", root / "link")
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            first = _workspace.snapshot(root)["files"]["link"]
            self.assertEqual(first["kind"], "symlink")
            (root / "link").unlink()
            os.symlink("missing two", root / "link")
            self.assertNotEqual(first, _workspace.snapshot(root)["files"]["link"])


class VerificationProcessTests(unittest.TestCase):
    def test_output_flood_retains_bounded_complete_failure_tails(self):
        code = (
            "import os;os.write(1,b'x'*2000000+b'\\nstdout end\\n');"
            "os.write(2,b'y'*2000000+b'\\nstderr end\\n')"
        )
        result = _process.run([sys.executable, "-c", code], cwd=Path.cwd(), timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.timed_out)
        self.assertEqual(result.stdout_bytes, 2000012)
        self.assertEqual(result.stderr_bytes, 2000012)
        self.assertEqual(result.stdout, b"stdout end\n")
        self.assertEqual(result.stderr, b"stderr end\n")
        head = _process.run(
            [sys.executable, "-c", code], cwd=Path.cwd(), timeout=10, tail_limit=32, keep="head"
        )
        self.assertEqual(head.stdout, b"x" * 32)
        self.assertEqual(head.stdout_bytes, 2000012)

    def test_timeout_removes_owned_grandchild_and_preserves_unrelated_process(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            marker, other = root / "child-marker", root / "other-marker"
            child = "import pathlib,sys,time;time.sleep(1.2);pathlib.Path(sys.argv[1]).touch()"
            unrelated = subprocess.Popen([sys.executable, "-c", child, str(other)])
            code = (
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]);time.sleep(30)"
            )
            try:
                result = _process.run(
                    [sys.executable, "-c", code, child, str(marker)], cwd=root, timeout=0.5
                )
                self.assertTrue(result.timed_out)
                self.assertIsNone(result.returncode)
                self.assertEqual(unrelated.wait(timeout=5), 0)
                time.sleep(0.2)
                self.assertTrue(other.exists())
                self.assertFalse(marker.exists())
            finally:
                if unrelated.poll() is None:
                    unrelated.kill()
                    unrelated.wait()

    def test_stdin_is_literal_and_missing_program_is_a_launch_failure(self):
        result = _process.run(
            [sys.executable, "-c", "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"],
            cwd=Path.cwd(),
            input=b"literal [*]\x00name\x00",
        )
        self.assertEqual(result.stdout, b"literal [*]\x00name\x00")
        try:
            missing = _process.run(["missing-template-verifier"], cwd=Path.cwd())
        except OSError:
            pass  # POSIX Popen reports launch failure before a child exists.
        else:
            self.assertIsNone(missing.returncode)


class VerificationPrivacyRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("TEMPLATE_TEST_OTHER_PYTHON"), "second Python not selected")
    def test_second_installed_runtime_is_used_and_wrong_minor_refuses(self):
        other = Path(os.environ["TEMPLATE_TEST_OTHER_PYTHON"]).resolve()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            (root / ".gitignore").write_text("project.local.toml\n")
            (root / "project.local.toml").write_text(
                "schema='template.local/1'\npython=" + json.dumps(str(other)) + "\n"
            )
            executable, identity = _workspace.resolve_runtime(root)
            self.assertEqual(Path(executable), other)
            self.assertEqual(identity["source"], "project.local")
            wanted = ".".join(identity["python"].split(".")[:2])
            agreed = _workspace.resolve_runtime(root, {"runtime": {"python": wanted}})[1]
            self.assertEqual(agreed["python"], identity["python"])
            self.assertNotEqual(agreed["sha"], identity["sha"])
            selected = _process.run(
                _workspace.runtime_argv(
                    ["python", "-c", "import sys;print(sys.version_info.minor)"], executable
                ),
                cwd=root,
            )
            self.assertEqual(selected.returncode, 0)
            self.assertEqual(int(selected.stdout), int(wanted.split(".")[1]))
            with self.assertRaisesRegex(ValueError, "required; selected runtime"):
                _workspace.resolve_runtime(root, {"runtime": {"python": "3.999"}})

    def test_sanitizer_preserves_markdown_slashes_urls_and_scrubs_spaced_paths(self):
        root = Path.cwd()
        ordinary = (
            "`/` read / write and pass / fail 1/2 [source](07_app/view.py) "
            "`07_app/view.py` https://example.test/a/b"
        )
        self.assertEqual(verify._scrub(ordinary.encode(), root, {}), ordinary)
        cases = [
            r'"C:\Users\Jane Doe\secret file.txt"',
            "'/home/Jane Doe/secret file.txt'",
            r"C:\Users\Jane Doe\secret.txt",
            "/home/Jane Doe/secret.txt",
            r"C:\Users\Jane Doe\secret file.txt",
            "/home/Jane Doe/secret file.txt",
            r"\\server\Jane Doe\secret file.txt",
            "file:///home/Jane Doe/secret file.txt",
        ]
        for value in cases:
            with self.subTest(value=value):
                cleaned = verify._scrub(value.encode(), root, {})
                self.assertNotIn("Jane", cleaned)
                self.assertNotIn("secret", cleaned)
                self.assertIn("<absolute-path>", cleaned)
        secret = "begin-" + "s" * 5000 + "-end"
        cleaned = verify._scrub(
            ("prefix\n" + secret + "\nlast line\n").encode(), root, {"SERVICE_TOKEN": secret}
        )
        self.assertIn("<redacted>", cleaned)
        self.assertNotIn("sss", cleaned)
        self.assertNotIn(
            "private line",
            verify._scrub(
                b"private line\nlast line\n", root, {"PRIVATE_KEY": "omitted prefix\nprivate line"}
            ),
        )

    def test_runtime_is_portable_and_wrong_version_fails_before_verification(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            executable, identity = _workspace.resolve_runtime(root)
            self.assertEqual(executable, sys.executable)
            self.assertNotIn(str(root), json.dumps(identity))
            self.assertNotIn(executable, json.dumps(identity))
            self.assertEqual(
                _workspace.runtime_argv(["python", "x.py"], executable), [executable, "x.py"]
            )
            self.assertEqual(
                _workspace.runtime_argv(["node", "x.js"], executable), ["node", "x.js"]
            )
            with self.assertRaisesRegex(ValueError, "required; selected runtime"):
                _workspace.resolve_runtime(root, {"runtime": {"python": "999.1"}})

    def test_runtime_mapping_must_be_ignored_and_schema_is_strict(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            local = root / "project.local.toml"
            local.write_text(
                "schema='template.local/1'\npython=" + json.dumps(sys.executable) + "\n"
            )
            with self.assertRaisesRegex(ValueError, "ignored and untracked"):
                _workspace.resolve_runtime(root)
            (root / ".gitignore").write_text("project.local.toml\n")
            self.assertEqual(_workspace.resolve_runtime(root)[1]["source"], "project.local")
            local.write_text(local.read_text() + "surprise=true\n")
            with self.assertRaisesRegex(ValueError, "requires schema"):
                _workspace.resolve_runtime(root)


if __name__ == "__main__":
    unittest.main()
