"""Executable examples for project-owned user-path and coverage admission."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VIEWER = """import argparse,hashlib,json,pathlib,sys
parser=argparse.ArgumentParser()
parser.add_argument('action',choices=['prepare','serve'])
parser.add_argument('--output',required=True,type=pathlib.Path)
parser.add_argument('--once',action='store_true')
args=parser.parse_args()
identity={'code':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
          'input':hashlib.sha256(pathlib.Path('input.txt').read_bytes()).hexdigest()}
if args.action=='prepare':
    args.output.write_text(json.dumps({
        'identity':identity,'value':pathlib.Path('input.txt').read_text().upper()}))
else:
    saved=json.loads(args.output.read_text())
    if saved['identity']!=identity:
        sys.exit('stale output: run prepare with current code and inputs')
    print(saved['value'])
"""

REQUIRED = """import sys,unittest
suite=unittest.defaultTestLoader.discover('tests')
def ids(node):
    for item in node:
        if isinstance(item,unittest.TestSuite):
            yield from ids(item)
        else:
            yield item.id()
required={'test_product.ProductTests.test_user_path'}
if not required.issubset(set(ids(suite))):
    sys.exit('required test missing from discovery')
result=unittest.TextTestRunner().run(suite)
if any(test.id() in required for test,reason in result.skipped):
    sys.exit('required test skipped')
sys.exit(0 if result.wasSuccessful() else 1)
"""


def cli(root, *args):
    return subprocess.run(
        [sys.executable, "-B", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


class ProjectChecksTests(unittest.TestCase):
    def test_prepare_exit_serve_rejects_cache_only_design_and_code_drift(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "viewer.py"
            source.write_text(
                "import sys\ncache={}\nif sys.argv[1]=='prepare': cache['value']='READY'\n"
                "else: print(cache['value'])\n"
            )
            self.assertEqual(cli(root, "viewer.py", "prepare").returncode, 0)
            broken = cli(root, "viewer.py", "serve")
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn("KeyError", broken.stderr)
            source.write_text(VIEWER)
            (root / "input.txt").write_text("ready")
            self.assertEqual(
                cli(root, "viewer.py", "prepare", "--output", "current.json").returncode, 0
            )
            served = cli(root, "viewer.py", "serve", "--output", "current.json", "--once")
            self.assertEqual((served.returncode, served.stdout.strip()), (0, "READY"))
            historical = (root / "current.json").read_bytes()
            historical_sha = hashlib.sha256(historical).hexdigest()
            (root / "historical.json").write_bytes(historical)
            source.write_text(VIEWER + "\n# current implementation changed\n")
            stale = cli(root, "viewer.py", "serve", "--output", "current.json", "--once")
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("stale output", stale.stderr)
            self.assertEqual((root / "current.json").read_bytes(), historical)
            self.assertEqual(
                cli(root, "viewer.py", "prepare", "--output", "current.json").returncode, 0
            )
            self.assertEqual(
                cli(root, "viewer.py", "serve", "--output", "current.json", "--once").returncode, 0
            )
            self.assertEqual(
                hashlib.sha256((root / "historical.json").read_bytes()).hexdigest(), historical_sha
            )
            self.assertNotEqual(
                json.loads((root / "current.json").read_text()), json.loads(historical)
            )
            missing_flag = cli(root, "viewer.py", "prepare")
            self.assertEqual(missing_flag.returncode, 2)
            self.assertIn("--output", missing_flag.stderr)

    def test_required_discovery_and_skip_are_acceptance_failures(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "tests").mkdir()
            (root / "required.py").write_text(REQUIRED)
            missing = cli(root, "required.py")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("required test missing", missing.stderr)
            test = root / "tests/test_product.py"
            body = (
                "import unittest\nclass ProductTests(unittest.TestCase):\n"
                "    def test_user_path(self):\n        self.assertEqual(2+2,4)\n"
            )
            test.write_text(body)
            self.assertEqual(cli(root, "required.py").returncode, 0)
            test.write_text(
                body.replace(
                    "    def test_user_path",
                    "    @unittest.skip('unavailable product dependency')\n    def test_user_path",
                )
            )
            skipped = cli(root, "required.py")
            self.assertNotEqual(skipped.returncode, 0)
            self.assertIn("required test skipped", skipped.stderr)

    def test_unavailable_product_dependency_cannot_hide_behind_template_tooling(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "entry.py").write_text("import unavailable_product_dependency_fixture\n")
            result = cli(root, "entry.py")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unavailable_product_dependency_fixture", result.stderr)


if __name__ == "__main__":
    unittest.main()
