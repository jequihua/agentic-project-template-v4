"""Focused tests for the deterministic OKF navigation-view generator.

Standard library only. Real-repository tests use the tracked manifest and view;
destructive, malformed, stale, and symlink scenarios use isolated temporary roots so
the tracked generated file is never altered by a negative test.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT_PATH = SCRIPTS / "generate_okf_navigation.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
gen = importlib.import_module("generate_okf_navigation")


def _symlinks_available() -> bool:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "t.txt"
            target.write_text("x", encoding="utf-8")
            link = Path(tmp) / "l.txt"
            os.symlink(target, link)
            return link.is_symlink()
    except (OSError, NotImplementedError, AttributeError):
        return False


_CAN_SYMLINK = _symlinks_available()

VALID_SOURCES = ["a.md", "sub/b.md", "sub/c.md"]


def _valid_manifest(paths=VALID_SOURCES):
    return {
        "manifest_schema": gen.MANIFEST_SCHEMA,
        "view_id": "t",
        "title": "Temp View",
        "output_path": gen.OUTPUT_REL,
        "groups": [
            {"group_id": "g1", "title": "First", "sources": [{"path": paths[0], "label": "A"}]},
            {"group_id": "g2", "title": "Second",
             "sources": [{"path": p, "label": f"L-{p}"} for p in paths[1:]]},
        ],
    }


def _make_repo(tmp, manifest_obj, source_paths=VALID_SOURCES):
    root = Path(tmp)
    (root / "08_pkg").mkdir(parents=True, exist_ok=True)
    (root / "08_pkg" / "okf_navigation_manifest.json").write_text(
        json.dumps(manifest_obj, indent=2), encoding="utf-8")
    for rel in source_paths:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# source {rel}\nbody of {rel}\n", encoding="utf-8")
    return root


class RealRepoViewTests(unittest.TestCase):
    """The tracked manifest and committed view on the real repository."""

    def test_committed_view_matches_fresh_render(self) -> None:
        data = gen.load_and_validate_manifest(ROOT)
        expected = gen.render(data)
        actual = (ROOT / gen.OUTPUT_REL).read_bytes()
        self.assertEqual(actual, expected)

    def test_check_reports_current_on_real_repo(self) -> None:
        self.assertEqual(gen.check(ROOT), "current")

    def test_view_has_marker_notice_paths_and_command(self) -> None:
        text = (ROOT / gen.OUTPUT_REL).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("<!-- GENERATED"))
        self.assertIn(gen.MANIFEST_REL, text)
        self.assertIn(gen.REGEN_COMMAND, text)
        for token in ("disposable", "not", "authoritative", "does **not reproduce live"):
            self.assertIn(token, text)
        self.assertIn("PROJECT_STATE.md", text)
        data = gen.load_and_validate_manifest(ROOT)
        for group in data["groups"]:
            for source in group["sources"]:
                self.assertIn(f"`{source['path']}`", text)
                self.assertIn(source["label"], text)

    def test_view_ends_with_single_trailing_newline_and_lf(self) -> None:
        raw = (ROOT / gen.OUTPUT_REL).read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"))
        self.assertNotIn(b"\r", raw)

    def test_view_does_not_copy_source_bodies_or_live_state(self) -> None:
        text = (ROOT / gen.OUTPUT_REL).read_text(encoding="utf-8")
        # Distinctive substrings owned by canonical sources must not be copied in.
        state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("Current objective", state)  # sanity: the source owns this
        for leaked in ("Current objective", "Next expected action", "Latest accepted review"):
            self.assertNotIn(leaked, text)
        arch = (ROOT / "docs" / "template_framework" / "okf_pkg" / "architecture_contract.md").read_text(encoding="utf-8")
        self.assertIn("Preserved Authorities", arch)
        self.assertNotIn("Preserved Authorities", text)

    def test_manifest_order_preserved_in_output(self) -> None:
        data = gen.load_and_validate_manifest(ROOT)
        manifest_order = [s["path"] for grp in data["groups"] for s in grp["sources"]]
        text = (ROOT / gen.OUTPUT_REL).read_text(encoding="utf-8")
        found_order = [line.split("`")[-2] for line in text.splitlines()
                       if line.startswith("- [")]
        self.assertEqual(found_order, manifest_order)

    def test_required_sources_are_all_routed(self) -> None:
        required = {
            "PROJECT_STATE.md",
            "docs/template_framework/okf_pkg/package_status.md",
            "docs/template_framework/okf_pkg/architecture_contract.md",
            "docs/template_framework/okf_pkg/okf_profile_v0_1.md",
            "docs/template_framework/okf_pkg/public_api_contract.md",
            "docs/template_framework/okf_pkg/testing_strategy.md",
            "tests/fixtures/okf_profile/manifest.json", "scripts/README.md",
            "MILESTONES.md",
        }
        data = gen.load_and_validate_manifest(ROOT)
        present = {s["path"] for grp in data["groups"] for s in grp["sources"]}
        self.assertTrue(required.issubset(present))

    def test_real_cli_from_outside_repo_targets_repo(self) -> None:
        # Resolve the repository root independently of the working directory.
        with tempfile.TemporaryDirectory() as outside:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--check"],
                cwd=outside, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("current", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)


class DeterminismTests(unittest.TestCase):
    def test_two_regenerations_produce_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            self.assertEqual(gen.generate(root), "written")
            first = (root / gen.OUTPUT_REL).read_bytes()
            self.assertEqual(gen.generate(root), "unchanged")
            second = (root / gen.OUTPUT_REL).read_bytes()
            self.assertEqual(first, second)
            data = gen.load_and_validate_manifest(root)
            self.assertEqual(first, gen.render(data))

    def test_delete_and_regenerate_restores_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            gen.generate(root)
            before = (root / gen.OUTPUT_REL).read_bytes()
            (root / gen.OUTPUT_REL).unlink()
            self.assertEqual(gen.check(root), "missing")
            self.assertEqual(gen.generate(root), "written")
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), before)

    def test_current_generation_does_not_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            gen.generate(root)
            with mock.patch.object(gen, "_atomic_write",
                                   side_effect=AssertionError("must not rewrite")):
                self.assertEqual(gen.generate(root), "unchanged")


class CheckModeTests(unittest.TestCase):
    def test_check_missing_stale_current_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            out = root / gen.OUTPUT_REL
            # missing: no write performed
            self.assertEqual(gen.check(root), "missing")
            self.assertFalse(out.exists())
            gen.generate(root)
            # stale: tamper, confirm check does not repair
            tampered = out.read_bytes() + b"tampered\n"
            out.write_bytes(tampered)
            self.assertEqual(gen.check(root), "stale")
            self.assertEqual(out.read_bytes(), tampered)
            # current after a fresh regeneration
            gen.generate(root)
            self.assertEqual(gen.check(root), "current")

    def test_cli_check_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            with mock.patch.object(gen, "repo_root", return_value=root):
                self.assertEqual(gen.main(["--check"]), 1)   # missing
                self.assertEqual(gen.main([]), 0)            # generate
                self.assertEqual(gen.main(["--check"]), 0)   # current

    def test_cli_rejects_bad_arguments(self) -> None:
        self.assertEqual(gen.main(["--bogus"]), 2)
        self.assertEqual(gen.main(["--check", "extra"]), 2)


class ManifestValidationTests(unittest.TestCase):
    def _fails(self, mutate, source_paths=VALID_SOURCES):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _valid_manifest()
            mutate(manifest)
            root = _make_repo(tmp, manifest, source_paths)
            with self.assertRaises(gen.NavError):
                gen.expected_bytes(root)

    def test_malformed_json_fails_without_touching_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            gen.generate(root)
            good = (root / gen.OUTPUT_REL).read_bytes()
            (root / "08_pkg" / "okf_navigation_manifest.json").write_text(
                "{ not valid json ", encoding="utf-8")
            with self.assertRaises(gen.NavError):
                gen.generate(root)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), good)

    def test_wrong_schema_version(self) -> None:
        self._fails(lambda m: m.update(manifest_schema="template.okf_navigation_manifest.v2"))

    def test_unknown_top_level_key(self) -> None:
        self._fails(lambda m: m.update(extra="x"))

    def test_unknown_group_key(self) -> None:
        self._fails(lambda m: m["groups"][0].update(color="red"))

    def test_unknown_source_key(self) -> None:
        self._fails(lambda m: m["groups"][0]["sources"][0].update(note="x"))

    def test_duplicate_group_id(self) -> None:
        self._fails(lambda m: m["groups"][1].update(group_id="g1"))

    def test_duplicate_source_path(self) -> None:
        self._fails(lambda m: m["groups"][1]["sources"].insert(
            0, {"path": VALID_SOURCES[0], "label": "dup"}))

    def test_type_errors(self) -> None:
        self._fails(lambda m: m.update(groups="notalist"))
        self._fails(lambda m: m["groups"][0].update(sources={}))
        self._fails(lambda m: m["groups"][0]["sources"][0].update(path=123))

    def test_empty_required_strings(self) -> None:
        self._fails(lambda m: m.update(title=""))
        self._fails(lambda m: m["groups"][0].update(title=""))
        self._fails(lambda m: m["groups"][0]["sources"][0].update(label=""))

    def test_wrong_output_path_rejected(self) -> None:
        self._fails(lambda m: m.update(output_path="08_pkg/generated/other.md"))

    def test_limits_enforced(self) -> None:
        with self.subTest("groups"):
            self._fails(lambda m: m.__setitem__("groups", [
                {"group_id": f"g{i}", "title": "T",
                 "sources": [{"path": "a.md", "label": "l"}]}
                for i in range(gen.MAX_GROUPS + 1)]))
        with self.subTest("path_len"):
            long_path = "sub/" + "x" * (gen.MAX_PATH_LEN + 1) + ".md"
            self._fails(lambda m: m["groups"][0]["sources"][0].update(path=long_path))
        with self.subTest("label_len"):
            self._fails(lambda m: m["groups"][0]["sources"][0].update(
                label="x" * (gen.MAX_LABEL_LEN + 1)))

    def test_manifest_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            path = root / "08_pkg" / "okf_navigation_manifest.json"
            padded = json.dumps(_valid_manifest()) + " " * (gen.MAX_MANIFEST_BYTES + 1)
            path.write_text(padded, encoding="utf-8")
            with self.assertRaises(gen.NavError):
                gen.expected_bytes(root)

    def test_missing_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Manifest names a source that is not created on disk.
            root = _make_repo(tmp, _valid_manifest(), source_paths=["a.md", "sub/b.md"])
            with self.assertRaises(gen.NavError):
                gen.expected_bytes(root)

    def test_non_regular_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _valid_manifest(["a.md", "sub/b.md", "adir"])
            root = _make_repo(tmp, manifest, source_paths=["a.md", "sub/b.md"])
            (root / "adir").mkdir()
            with self.assertRaises(gen.NavError):
                gen.expected_bytes(root)


class UnsafePathFormTests(unittest.TestCase):
    def _fails_path(self, bad_path):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _valid_manifest(["a.md", "sub/b.md", bad_path])
            root = _make_repo(tmp, manifest, source_paths=["a.md", "sub/b.md"])
            with self.assertRaises(gen.NavError):
                gen.expected_bytes(root)

    def test_absolute_path_rejected(self) -> None:
        self._fails_path("/etc/passwd")

    def test_parent_traversal_rejected(self) -> None:
        self._fails_path("../outside.md")

    def test_backslash_path_rejected(self) -> None:
        self._fails_path("sub\\evil.md")

    def test_drive_letter_path_rejected(self) -> None:
        self._fails_path("C:/Windows/win.ini")

    def test_dot_segment_rejected(self) -> None:
        self._fails_path("sub/./b.md")

    def test_output_as_input_rejected(self) -> None:
        self._fails_path(gen.OUTPUT_REL)


class OutputSafetyTests(unittest.TestCase):
    def test_generation_failure_preserves_output_and_leaves_no_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            gen.generate(root)
            good = (root / gen.OUTPUT_REL).read_bytes()
            # Corrupt the manifest so the next generation raises after output exists.
            (root / "08_pkg" / "okf_navigation_manifest.json").write_text(
                "not json", encoding="utf-8")
            with self.assertRaises(gen.NavError):
                gen.generate(root)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), good)
            residue = list((root / gen.GENERATED_DIR_REL).glob(".okfnav-*.tmp"))
            self.assertEqual(residue, [])

    def test_sources_and_manifest_unchanged_by_generate_and_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            tracked = ["08_pkg/okf_navigation_manifest.json", *VALID_SOURCES]
            before = {r: hashlib.sha256((root / r).read_bytes()).hexdigest() for r in tracked}
            gen.generate(root)
            gen.check(root)
            after = {r: hashlib.sha256((root / r).read_bytes()).hexdigest() for r in tracked}
            self.assertEqual(before, after)

    def test_containment_escape_branch_rejected_without_symlink_privilege(self) -> None:
        # Portable coverage for the escape-rejection branch the symlink tests exercise:
        # simulate a source whose real path resolves outside the repository root.
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            real_realpath = os.path.realpath
            escaped = os.path.join(tempfile.gettempdir(), "escaped_c.md")
            leaf = os.path.join("sub", "c.md")

            def fake_realpath(path):
                resolved = real_realpath(path)
                return escaped if resolved.endswith(leaf) else resolved

            with mock.patch("generate_okf_navigation.os.path.realpath",
                            side_effect=fake_realpath):
                with self.assertRaises(gen.NavError):
                    gen.expected_bytes(root)

    @unittest.skipUnless(_CAN_SYMLINK, "symlink creation not permitted on this platform")
    def test_symlinked_output_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            gen_dir = root / gen.GENERATED_DIR_REL
            gen_dir.mkdir(parents=True, exist_ok=True)
            external = root / "elsewhere.md"
            external.write_text("original\n", encoding="utf-8")
            os.symlink(external, root / gen.OUTPUT_REL)
            with self.assertRaises(gen.NavError):
                gen.generate(root)
            self.assertEqual(external.read_text(encoding="utf-8"), "original\n")

    @unittest.skipUnless(_CAN_SYMLINK, "symlink creation not permitted on this platform")
    def test_symlinked_source_escape_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / "secret.md"
            secret.write_text("secret\n", encoding="utf-8")
            manifest = _valid_manifest(["a.md", "sub/b.md", "sub/link.md"])
            root = _make_repo(tmp, manifest, source_paths=["a.md", "sub/b.md"])
            os.symlink(secret, root / "sub" / "link.md")
            with self.assertRaises(gen.NavError):
                gen.expected_bytes(root)

    @unittest.skipUnless(_CAN_SYMLINK, "symlink creation not permitted on this platform")
    def test_parent_symlink_generated_dir_escape_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = _make_repo(tmp, _valid_manifest())
            # Replace 08_pkg/generated with a symlink pointing outside the repo.
            os.symlink(outside, root / gen.GENERATED_DIR_REL, target_is_directory=True)
            with self.assertRaises(gen.NavError):
                gen.generate(root)


def _run_cli(root, args):
    """Invoke the public ``main`` boundary against ``root`` with ``repo_root``
    redirected, returning ``(exit, stdout, stderr)``."""
    err, out = io.StringIO(), io.StringIO()
    with mock.patch.object(gen, "repo_root", return_value=root):
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = gen.main(list(args))
    return rc, out.getvalue(), err.getvalue()


def _no_temp_residue(root) -> bool:
    return not list((root / gen.GENERATED_DIR_REL).glob(".okfnav-*.tmp"))


def _owning_boom_fdopen():
    """Return a replacement for ``os.fdopen`` that models a *post-ownership-transfer*
    write failure: the real ``os.fdopen`` takes ownership of the raw descriptor, the
    returned wrapper owns that real file object and closes it on context-manager exit,
    and ``write`` raises ``OSError``. Unlike a naive fake it never closes the raw
    descriptor itself, so it exercises the production ownership transition rather than
    substituting for it."""
    real_fdopen = os.fdopen

    class _OwningBoomWriter:
        def __init__(self, handle):
            self._handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self._handle.close()  # close the owned real file object (single close)
            return False

        def write(self, data):
            raise OSError(5, "io error")

    def fdopen(fd, mode):
        return _OwningBoomWriter(real_fdopen(fd, mode))

    return fdopen


class OutputFilesystemBoundaryTests(unittest.TestCase):
    """Finding A: non-regular and expected filesystem output failures become the
    documented concise exit 2 (no traceback, no mutation, no temp residue)."""

    def test_generator_is_standard_library_only(self) -> None:
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import yaml", src)
        self.assertNotIn("from yaml", src)

    def test_public_cli_remains_two_commands(self) -> None:
        self.assertEqual(gen.main(["--bogus"]), 2)
        self.assertEqual(gen.main(["--check", "x"]), 2)
        self.assertEqual(gen.main(["generate"]), 2)

    def test_directory_at_output_generate_and_check_exit_2(self) -> None:
        for args, label in (([], "generate"), (["--check"], "check")):
            with self.subTest(command=label), tempfile.TemporaryDirectory() as tmp:
                root = _make_repo(tmp, _valid_manifest())
                (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
                (root / gen.OUTPUT_REL).mkdir()  # a directory at the fixed output path
                rc, out, err = _run_cli(root, args)
                self.assertEqual(rc, 2)
                self.assertNotIn("Traceback", err)
                self.assertNotIn(str(root), err)  # no machine-local path disclosed
                self.assertIn(gen.OUTPUT_REL, err)
                self.assertTrue((root / gen.OUTPUT_REL).is_dir())  # unchanged, no write
                self.assertTrue(_no_temp_residue(root))

    def test_output_read_failure_is_translated_in_generate_and_check(self) -> None:
        real_read = Path.read_bytes

        def fail_output(self):
            if self.name == Path(gen.OUTPUT_REL).name:
                raise PermissionError(13, "denied")
            return real_read(self)

        for args, label in (([], "generate"), (["--check"], "check")):
            with self.subTest(command=label), tempfile.TemporaryDirectory() as tmp:
                root = _make_repo(tmp, _valid_manifest())
                gen.generate(root)
                good = (root / gen.OUTPUT_REL).read_bytes()
                with mock.patch.object(Path, "read_bytes", fail_output):
                    rc, out, err = _run_cli(root, args)
                self.assertEqual(rc, 2)
                self.assertNotIn("Traceback", err)
                self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), good)
                self.assertTrue(_no_temp_residue(root))

    def test_temp_create_failure_preserves_output_and_leaves_no_residue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
            (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")  # different from render
            with mock.patch.object(gen.tempfile, "mkstemp",
                                   side_effect=OSError(28, "no space")):
                rc, out, err = _run_cli(root, [])
            self.assertEqual(rc, 2)
            self.assertNotIn("Traceback", err)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
            self.assertTrue(_no_temp_residue(root))

    def test_temp_write_failure_preserves_output_and_leaves_no_residue(self) -> None:
        # Ownership-correct: the real os.fdopen takes the descriptor and the wrapper
        # owns that file object; the fake never closes the raw descriptor before
        # ownership transfers (unlike the earlier mechanic).
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
            (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
            with mock.patch.object(gen.os, "fdopen", _owning_boom_fdopen()):
                rc, out, err = _run_cli(root, [])
            self.assertEqual(rc, 2)
            self.assertNotIn("Traceback", err)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
            self.assertTrue(_no_temp_residue(root))

    def test_atomic_replace_failure_preserves_output_and_leaves_no_residue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
            (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
            with mock.patch.object(gen.os, "replace",
                                   side_effect=OSError(13, "denied")):
                rc, out, err = _run_cli(root, [])
            self.assertEqual(rc, 2)
            self.assertNotIn("Traceback", err)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
            self.assertTrue(_no_temp_residue(root))

    def test_check_stays_read_only_when_output_unreadable(self) -> None:
        # --check must never write, even when translating an output read failure.
        real_read = Path.read_bytes

        def fail_output(self):
            if self.name == Path(gen.OUTPUT_REL).name:
                raise PermissionError(13, "denied")
            return real_read(self)

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            gen.generate(root)
            before = (root / gen.OUTPUT_REL).read_bytes()
            with mock.patch.object(Path, "read_bytes", fail_output):
                rc, _, err = _run_cli(root, ["--check"])
            self.assertEqual(rc, 2)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), before)
            self.assertTrue(_no_temp_residue(root))

    # ----- Review 017 remaining branches: output-path resolution + fdopen ownership -

    @staticmethod
    def _realpath_raiser(suffix, errno=13):
        real = os.path.realpath

        def fake(path):
            if os.fspath(path).replace("\\", "/").endswith(suffix):
                raise PermissionError(errno, "denied")
            return real(path)

        return fake

    def test_generated_dir_realpath_failure_is_translated(self) -> None:
        # The exact Review 017 reproducer: only the generated directory's realpath
        # raises, while all manifest/source validation stays real.
        raiser = self._realpath_raiser("08_pkg/generated")
        for args, label in (([], "generate"), (["--check"], "check")):
            with self.subTest(command=label), tempfile.TemporaryDirectory() as tmp:
                root = _make_repo(tmp, _valid_manifest())
                (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
                (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
                with mock.patch.object(gen.os.path, "realpath", raiser):
                    rc, out, err = _run_cli(root, args)
                self.assertEqual(rc, 2)
                self.assertNotIn("Traceback", err)
                self.assertNotIn(str(root), err)  # no machine-local path
                self.assertIn(gen.OUTPUT_REL, err)
                self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
                self.assertTrue(_no_temp_residue(root))

    def test_output_parent_realpath_failure_is_translated(self) -> None:
        # With the generated directory absent, the surviving realpath call is the
        # output-parent resolution; it must translate to the same concise exit 2.
        raiser = self._realpath_raiser("08_pkg/generated")
        for args, label in (([], "generate"), (["--check"], "check")):
            with self.subTest(command=label), tempfile.TemporaryDirectory() as tmp:
                root = _make_repo(tmp, _valid_manifest())  # no generated/ directory
                with mock.patch.object(gen.os.path, "realpath", raiser):
                    rc, out, err = _run_cli(root, args)
                self.assertEqual(rc, 2)
                self.assertNotIn("Traceback", err)
                self.assertNotIn(str(root), err)
                self.assertIn(gen.OUTPUT_REL, err)
                self.assertFalse((root / gen.OUTPUT_REL).exists())  # no write
                self.assertTrue(_no_temp_residue(root))

    def test_output_stat_failure_is_translated_for_generate_and_check(self) -> None:
        # An adjacent fixed-output type/stat OSError is translated, not escaped, under
        # both commands. The selective mock fails only the fixed-output inspection;
        # manifest and source validation stay real.
        real_isfile = os.path.isfile

        def fail_isfile(path):
            if os.fspath(path).replace("\\", "/").endswith("okf_navigation.md"):
                raise PermissionError(13, "denied")
            return real_isfile(path)

        for args, label in (([], "generate"), (["--check"], "check")):
            with self.subTest(command=label), tempfile.TemporaryDirectory() as tmp:
                root = _make_repo(tmp, _valid_manifest())
                (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
                (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
                mkstemp_spy = mock.Mock(wraps=tempfile.mkstemp)
                replace_spy = mock.Mock(wraps=os.replace)
                with mock.patch.object(gen.os.path, "isfile", fail_isfile), \
                        mock.patch.object(gen.tempfile, "mkstemp", mkstemp_spy), \
                        mock.patch.object(gen.os, "replace", replace_spy):
                    rc, out, err = _run_cli(root, args)
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")  # no success result on stdout
                self.assertNotIn("Traceback", err)
                self.assertNotIn(str(root), err)  # no machine-local path
                self.assertIn(gen.OUTPUT_REL, err)
                self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
                self.assertTrue(_no_temp_residue(root))
                mkstemp_spy.assert_not_called()  # no temp/write operation
                replace_spy.assert_not_called()

    def test_fdopen_failure_closes_descriptor_and_leaves_no_residue(self) -> None:
        # os.fdopen raises AFTER a real mkstemp, before it can take descriptor
        # ownership. Production must close the raw descriptor and unlink the temp path.
        holder = {}
        real_mkstemp = tempfile.mkstemp

        def capturing_mkstemp(*a, **k):
            fd, path = real_mkstemp(*a, **k)
            holder["fd"], holder["path"] = fd, path
            return fd, path

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
            (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
            with mock.patch.object(gen.tempfile, "mkstemp", capturing_mkstemp), \
                 mock.patch.object(gen.os, "fdopen", side_effect=OSError(9, "bad fd")):
                rc, out, err = _run_cli(root, [])
            self.assertEqual(rc, 2)
            self.assertNotIn("Traceback", err)
            self.assertNotIn(str(root), err)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
            # The captured raw descriptor was closed by production code.
            with self.assertRaises(OSError):
                os.fstat(holder["fd"])
            self.assertFalse(Path(holder["path"]).exists())  # temp path unlinked
            self.assertTrue(_no_temp_residue(root))

    def _run_with_os_close_spy(self, root, *, fdopen=None, replace=None):
        """Run public generation while spying on the production module's ``os.close``;
        return ``(rc, out, err, close_calls)``."""
        real_close = os.close
        calls = []

        def counting_close(fd):
            calls.append(fd)
            return real_close(fd)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(gen.os, "close", counting_close))
            if fdopen is not None:
                stack.enter_context(mock.patch.object(gen.os, "fdopen", fdopen))
            if replace is not None:
                stack.enter_context(mock.patch.object(gen.os, "replace", replace))
            rc, out, err = _run_cli(root, [])
        return rc, out, err, calls

    def test_no_production_os_close_after_ownership_transfer(self) -> None:
        # After os.fdopen returns, the file object owns the descriptor and closes it;
        # production must never call os.close on the success, post-transfer write, or
        # post-close replace paths (a second close would be a double close). Only the
        # pre-transfer fdopen-failure path uses os.close.
        with self.subTest(path="success"), tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            rc, out, err, calls = self._run_with_os_close_spy(root)
            self.assertEqual(rc, 0)
            self.assertIn("written", out)
            self.assertEqual(calls, [])

        with self.subTest(path="write_failure"), tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
            (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
            rc, out, err, calls = self._run_with_os_close_spy(
                root, fdopen=_owning_boom_fdopen())
            self.assertEqual(rc, 2)
            self.assertNotIn("Traceback", err)
            self.assertNotIn(str(root), err)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
            self.assertTrue(_no_temp_residue(root))
            self.assertEqual(calls, [])

        with self.subTest(path="replace_failure"), tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
            (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
            rc, out, err, calls = self._run_with_os_close_spy(
                root, replace=mock.Mock(side_effect=OSError(13, "denied")))
            self.assertEqual(rc, 2)
            self.assertNotIn("Traceback", err)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
            self.assertTrue(_no_temp_residue(root))
            self.assertEqual(calls, [])

    def test_pre_transfer_non_oserror_propagates_after_descriptor_cleanup(self) -> None:
        # A non-OSError raised by os.fdopen before ownership transfers must propagate
        # unchanged (not become NavError/exit 2), while production still closes the raw
        # descriptor and removes the temporary path, emitting no user-facing diagnostic.
        real_mkstemp = tempfile.mkstemp
        cases = [
            ("keyboard_interrupt", KeyboardInterrupt()),
            ("system_exit", SystemExit(7)),
            ("assertion", AssertionError("boom")),
            ("value_error", ValueError("bad")),
        ]
        for label, exc in cases:
            with self.subTest(exc=label), tempfile.TemporaryDirectory() as tmp:
                holder = {}

                def capturing_mkstemp(*a, **k):
                    fd, path = real_mkstemp(*a, **k)
                    holder["fd"], holder["path"] = fd, path
                    return fd, path

                root = _make_repo(tmp, _valid_manifest())
                (root / gen.GENERATED_DIR_REL).mkdir(parents=True, exist_ok=True)
                (root / gen.OUTPUT_REL).write_bytes(b"OLD STALE\n")
                err, out = io.StringIO(), io.StringIO()
                with mock.patch.object(gen, "repo_root", return_value=root), \
                        mock.patch.object(gen.tempfile, "mkstemp", capturing_mkstemp), \
                        mock.patch.object(gen.os, "fdopen", side_effect=exc), \
                        contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                    with self.assertRaises(type(exc)) as ctx:
                        gen.main([])
                # The exact type propagated with its meaningful value/code preserved.
                if isinstance(exc, SystemExit):
                    self.assertEqual(ctx.exception.code, 7)
                elif isinstance(exc, (AssertionError, ValueError)):
                    self.assertEqual(str(ctx.exception), str(exc))
                # Production closed the raw descriptor and removed the temp path.
                with self.assertRaises(OSError):
                    os.fstat(holder["fd"])
                self.assertFalse(Path(holder["path"]).exists())
                self.assertTrue(_no_temp_residue(root))
                # Prior output preserved; no user-facing diagnostic or traceback.
                self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), b"OLD STALE\n")
                self.assertEqual(err.getvalue(), "")
                self.assertEqual(out.getvalue(), "")
                # Defensive cleanup only after the determining assertions above.
                try:
                    os.close(holder["fd"])
                except OSError:
                    pass


class ManifestTextPolicyTests(unittest.TestCase):
    """Finding B: schema-valid but Markdown-unsafe manifest text/paths are rejected
    before any write, so an existing output is preserved and nothing is injected."""

    def _reject(self, mutate, *, absent_in_output=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, _valid_manifest())
            gen.generate(root)
            good = (root / gen.OUTPUT_REL).read_bytes()
            manifest = _valid_manifest()
            mutate(manifest)
            (root / "08_pkg" / "okf_navigation_manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            rc, out, err = _run_cli(root, [])
            self.assertEqual(rc, 2, err)
            self.assertNotIn("Traceback", err)
            self.assertEqual((root / gen.OUTPUT_REL).read_bytes(), good)  # preserved
            if absent_in_output is not None:
                self.assertNotIn(absent_in_output,
                                 (root / gen.OUTPUT_REL).read_text(encoding="utf-8"))

    def test_review_012_injection_reproducer_is_rejected(self) -> None:
        payload = "Safe](https://example.invalid)\n\nINJECTED BODY"
        self._reject(lambda m: m["groups"][0]["sources"][0].__setitem__("label", payload),
                     absent_in_output="example.invalid")

    def test_whitespace_only_and_padded_title_and_label(self) -> None:
        for value in ("   ", " lead", "trail "):
            with self.subTest(title=repr(value)):
                self._reject(lambda m, v=value: m.__setitem__("title", v))
            with self.subTest(label=repr(value)):
                self._reject(lambda m, v=value: m["groups"][0]["sources"][0].__setitem__("label", v))

    def test_control_and_format_characters_rejected(self) -> None:
        for ch in ("\r", "\n", "\t", "\x00", "​"):
            with self.subTest(title=repr(ch)):
                self._reject(lambda m, c=ch: m.__setitem__("title", f"a{c}b"))
            with self.subTest(label=repr(ch)):
                self._reject(lambda m, c=ch: m["groups"][0]["sources"][0].__setitem__("label", f"a{c}b"))

    def test_forbidden_markdown_delimiters_rejected(self) -> None:
        for delim in ("\\", "`", "[", "]", "<", ">"):
            with self.subTest(title=delim):
                self._reject(lambda m, d=delim: m.__setitem__("title", f"a{d}b"))
            with self.subTest(group_title=delim):
                self._reject(lambda m, d=delim: m["groups"][0].__setitem__("title", f"a{d}b"))
            with self.subTest(label=delim):
                self._reject(lambda m, d=delim: m["groups"][0]["sources"][0].__setitem__("label", f"a{d}b"))

    def test_identifier_policy_rejects_unsafe_forms(self) -> None:
        for bad in ("bad id", "a\nb", "a!b", "_lead", "-lead", ".lead", "a.b"):
            with self.subTest(view_id=repr(bad)):
                self._reject(lambda m, b=bad: m.__setitem__("view_id", b))
            with self.subTest(group_id=repr(bad)):
                self._reject(lambda m, b=bad: m["groups"][0].__setitem__("group_id", b))

    def test_link_breaking_source_paths_rejected(self) -> None:
        for bad in ("a).md", "sub dir/x.md", "a#b.md", "a?b.md", "a%b.md",
                    "a:b.md", "a`b.md", "café.md", "-lead.md", "trail./x.md"):
            with self.subTest(path=repr(bad)):
                self._reject(
                    lambda m, p=bad: m["groups"][1]["sources"][0].__setitem__("path", p))

    def test_checked_in_manifest_and_view_remain_valid_and_stable(self) -> None:
        # The real manifest still validates under the stricter policy and renders to
        # the exact committed bytes.
        data = gen.load_and_validate_manifest(ROOT)
        self.assertEqual(gen.render(data), (ROOT / gen.OUTPUT_REL).read_bytes())


if __name__ == "__main__":
    unittest.main()
