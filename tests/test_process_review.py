"""Transport status and workspace capture must not trust product diagnostics."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _git
import _process
import _workspace
from test_scaffold import git_init, run_git


class ProcessReviewTests(unittest.TestCase):
    def test_genuine_exit254_is_preserved_even_with_old_launch_error_text(self):
        command = (
            "import sys;print('verification launch failed: deliberate',file=sys.stderr);"
            "sys.exit(254)"
        )
        result = _process.run([sys.executable, "-c", command], cwd=Path.cwd())
        self.assertEqual(result.returncode, 254)
        self.assertFalse(result.timed_out)

    def test_workspace_metadata_limit_refuses_before_reading_any_product_files(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            git_init(root)
            (root / "baseline").write_text("original")
            run_git(root, "add", ".")
            run_git(root, "commit", "-qm", "baseline")
            for number in range(40):
                (root / (str(number) + "long-filename-" * 4 + ".txt")).write_text("content")
            original = _git.run

            def bounded(root, *args, **kwargs):
                kwargs.setdefault("limit", 256)
                return original(root, *args, **kwargs)

            with (
                mock.patch.object(_workspace.g, "run", side_effect=bounded),
                mock.patch.object(_workspace, "_identity") as identity,
            ):
                with self.assertRaisesRegex(ValueError, "bounded metadata allowance"):
                    _workspace.snapshot(root)
                identity.assert_not_called()


if __name__ == "__main__":
    unittest.main()
