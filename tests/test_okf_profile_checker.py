"""Tests for the PyYAML-backed ``--profile`` checker.

The runtime checker follows each fixture's ``full_parser`` oracle. YAML syntax and
representation come from a pure-Python ``yaml.SafeLoader`` adapter; project code
owns bounded input, framing, resource limits, semantic duplicate-key rejection, and
producer-profile policy. Tests that need parsing are skipped when PyYAML is not
installed; the acceptance run installs the declared dependency first.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIX_ROOT = ROOT / "tests" / "fixtures" / "okf_profile"
MANIFEST = FIX_ROOT / "manifest.json"
SCRIPTS = ROOT / "scripts"

try:
    import yaml  # noqa: F401
    _PYYAML = True
except ImportError:
    _PYYAML = False


def _preflight():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("artifact_integrity_preflight")


def _run(argv):
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        rc = _preflight().main(argv)
    return rc, buf.getvalue(), err.getvalue()


class DependencyAndSourcePolicyTests(unittest.TestCase):
    """These do not require PyYAML to be importable."""

    def test_package_metadata_declares_pyyaml(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("PyYAML>=6.0.3,<7", text)

    def test_pyproject_disables_package_discovery(self) -> None:
        # Guards the editable-install fix: removing the empty package selection or
        # the dependency range must fail this source-only test.
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[tool.setuptools]", text)
        self.assertRegex(text, r"packages\s*=\s*\[\s*\]")
        self.assertIn("PyYAML>=6.0.3,<7", text)

    def test_adapter_uses_only_pure_python_safeloader(self) -> None:
        src = (SCRIPTS / "okf_yaml_profile.py").read_text(encoding="utf-8")
        self.assertIn("SafeLoader", src)
        for forbidden in ("CSafeLoader", "CLoader", "yaml.Loader", "FullLoader",
                          "UnsafeLoader", "yaml.load(", "yaml.load_all(",
                          "setrecursionlimit", "add_constructor", "add_representer"):
            self.assertNotIn(forbidden, src, f"adapter must not use {forbidden}")
        # Representation-level APIs are used (not a bare safe_load + dict check).
        self.assertIn("get_single_node", src)
        self.assertIn("yaml.scan", src)

    def test_preflight_does_not_import_yaml_directly(self) -> None:
        src = (SCRIPTS / "artifact_integrity_preflight.py").read_text(encoding="utf-8")
        self.assertNotIn("import yaml", src)

    def test_missing_dependency_fails_cleanly_without_fallback(self) -> None:
        pf = _preflight()
        saved_yaml = sys.modules.get("yaml", "___absent___")
        saved_adapter = sys.modules.pop("okf_yaml_profile", None)
        sys.modules["yaml"] = None  # force ImportError on 'import yaml'
        try:
            buf, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                rc = pf.main(["--root", str(ROOT), "--profile", "--json",
                              "tests/fixtures/okf_profile/accepted_minimal.md"])
            self.assertEqual(rc, 2)
            self.assertIn("requires PyYAML", err.getvalue())
            self.assertEqual(buf.getvalue(), "")
        finally:
            if saved_yaml == "___absent___":
                sys.modules.pop("yaml", None)
            else:
                sys.modules["yaml"] = saved_yaml
            if saved_adapter is not None:
                sys.modules["okf_yaml_profile"] = saved_adapter
            else:
                sys.modules.pop("okf_yaml_profile", None)

    def test_default_behavior_unchanged_without_profile(self) -> None:
        target = "tests/fixtures/okf_profile/accepted_minimal.md"
        _, js, _ = _run(["--root", str(ROOT), "--json", target])
        self.assertEqual(set(json.loads(js).keys()), {"errors", "warnings", "findings"})
        _, txt, _ = _run(["--root", str(ROOT), target])
        self.assertNotIn("Profile check", txt)

    def test_default_mode_has_no_total_input_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.md"
            big.write_text("# H\n" + ("x " * 600_000) + "\n", encoding="utf-8")
            rc, js, _ = _run(["--root", tmp, "--json", "big.md"])
            self.assertEqual(set(json.loads(js).keys()), {"errors", "warnings", "findings"})
            self.assertEqual(rc, 0)


@unittest.skipUnless(_PYYAML, "PyYAML not installed")
class InstalledMetadataTests(unittest.TestCase):
    def test_installed_distribution_declares_pyyaml_range(self) -> None:
        import importlib.metadata as md
        try:
            dist = md.distribution("artifact-first-project-template")
        except md.PackageNotFoundError:
            self.skipTest("project distribution is not installed (run 'pip install -e .')")
        self.assertEqual(dist.metadata["Name"], "artifact-first-project-template")
        self.assertTrue(any("PyYAML" in r and "6.0.3" in r for r in (dist.requires or [])),
                        f"installed requirements missing PyYAML range: {dist.requires}")


@unittest.skipUnless(_PYYAML, "PyYAML not installed")
class ProfileCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.fixtures = cls.manifest["fixtures"]

    def _rec(self, text: str) -> tuple[dict, int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text(text, encoding="utf-8")
            rc, out, err = _run(["--root", tmp, "--profile", "--json", "a.md"])
            return json.loads(out)["artifacts"][0], rc, err

    def _raw_twice(self, text: str) -> tuple[tuple[int, str, str], tuple[int, str, str]]:
        """Invoke the public CLI twice against one contained artifact using the same
        root, file path, file bytes, and argument order, returning both complete
        ``(exit, stdout, stderr)`` tuples. Retaining raw stdout (unlike ``_rec``,
        which parses and discards it) lets hostile-limit tests assert output byte
        bounds, run-to-run determinism, and absence of input echo. Both runs share
        one temporary path so this checks deterministic behavior, not path
        randomness."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text(text, encoding="utf-8")
            argv = ["--root", tmp, "--profile", "--json", "a.md"]
            return _run(argv), _run(argv)

    def _assert(self, text, okf_result, okf_reason, prof_result, prof_reason, *, exit_code=None):
        rec, rc, err = self._rec(text)
        self.assertEqual(rec["okf_concept"], {"result": okf_result, "reason": okf_reason})
        self.assertEqual(rec["framework_profile"], {"result": prof_result, "reason": prof_reason})
        self.assertEqual(rec["execution_eligibility"], "not_evaluated")
        self.assertNotIn("Traceback", err)
        if exit_code is not None:
            self.assertEqual(rc, exit_code)

    def test_schema_is_v2(self) -> None:
        _, out, _ = _run(["--root", str(ROOT), "--profile", "--json",
                          "tests/fixtures/okf_profile/accepted_minimal.md"])
        self.assertEqual(json.loads(out)["schema_version"], "template.okf_profile_check.v2")

    def test_every_fixture_matches_full_parser_oracle(self) -> None:
        paths = [f["path"] for f in self.fixtures]
        rc, out, _ = _run(["--root", str(ROOT), "--profile", "--json", *paths])
        records = {a["path"]: a for a in json.loads(out)["artifacts"]}
        for f in self.fixtures:
            full = f["expected"]["full_parser"]
            got = records[f["path"]]
            self.assertEqual(got["okf_concept"], full["okf_concept"], f"{f['id']} okf")
            self.assertEqual(got["framework_profile"], full["framework_profile"], f"{f['id']} profile")
        self.assertEqual(rc, 1)

    # ----- syntax vs profile (Review 008/009 matrix) -----

    def test_malformed_yaml_is_okf_invalid(self) -> None:
        for extra in ('title: "bad" junk"\n', 'x: a: b\n', 'x:\ty\n'):
            self._assert('---\ntype: analysis\n' + extra + 'framework_profile: "0.1-rc.1"\n---\n',
                         "fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")

    def test_valid_yaml_out_of_profile(self) -> None:
        for extra in ('x: 1e3\n', 'x: 1_000\n', 'x: 1:20\n', 'x: Null\n', "x: 'single'\n",
                      'tags: [a, b]\n', 'x: 010\n', 'x: 2026-05-28\n'):
            self._assert('---\ntype: analysis\n' + extra + 'framework_profile: "0.1-rc.1"\n---\n',
                         "pass", None, "fail", "PROFILE_YAML_OUT_OF_SUBSET")

    def test_valid_unicode_escape_and_comments_pass(self) -> None:
        self._assert('---\ntype: analysis\nx: "\\u0041"\nframework_profile: "0.1-rc.1"\n---\n',
                     "pass", None, "pass", None)
        self._assert('---\ntype: analysis  # c\nframework_profile: "0.1-rc.1"  # v\n---\n',
                     "pass", None, "pass", None)

    def test_multiple_documents_is_okf_invalid(self) -> None:
        self._assert('---\ntype: analysis\n...\ntype: other\n---\n',
                     "fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")

    def test_exact_delimiters_and_crlf(self) -> None:
        self._assert('  ---\ntype: analysis\nframework_profile: "0.1-rc.1"\n  ---\n',
                     "not_evaluated", None, "not_applicable", None)
        self._assert('---\ntype: analysis\nframework_profile: "0.1-rc.1"\n  ---\n',
                     "fail", "OKF_FRONTMATTER_MISSING", "not_applicable", None)
        self._assert('---\r\ntype: analysis\r\nframework_profile: "0.1-rc.1"\r\n---\r\n',
                     "pass", None, "pass", None)

    # ----- semantic duplicate keys and producer keys (finding D) -----

    def test_semantic_duplicate_keys_are_okf_invalid(self) -> None:
        for a, b in (("1", "01"), ("60", "1:0"), ("yes", "true"), ("on", "true"), ("null", "~")):
            self._assert(f'---\ntype: analysis\n{a}: x\n{b}: y\n---\n',
                         "fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        # plain vs double-quoted string with the same value
        self._assert('---\ntype: analysis\na: 1\n"a": 2\n---\n',
                     "fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        # duplicate inside a nested tool mapping (spelling and semantic)
        self._assert('---\ntype: analysis\nframework_profile: "0.1-rc.1"\nllloom:\n  a: "1"\n  a: "2"\n---\n',
                     "fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")

    def test_non_string_and_complex_keys_are_profile_fail(self) -> None:
        # unique numeric key: OKF pass, profile fail (not profile pass, not OKF error)
        self._assert('---\ntype: analysis\n1: a\nframework_profile: "0.1-rc.1"\n---\n',
                     "pass", None, "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        # int 1 and str "1" are NOT semantic duplicates, but the int key still fails L2
        self._assert('---\ntype: analysis\n1: a\n"1": b\nframework_profile: "0.1-rc.1"\n---\n',
                     "pass", None, "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        # complex (non-scalar) key
        self._assert('---\ntype: analysis\n? [a, b]\n: v\nframework_profile: "0.1-rc.1"\n---\n',
                     "pass", None, "fail", "PROFILE_YAML_OUT_OF_SUBSET")

    def test_unknown_string_namespace_passes(self) -> None:
        self._assert('---\ntype: analysis\nframework_profile: "0.1-rc.1"\nnewtool:\n  k: "v"\n---\n',
                     "pass", None, "pass", None)

    # ----- bounded input, encoding, and resource limits (findings B, C) -----

    def test_total_input_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            head = b"---\ntype: analysis\nframework_profile: \"0.1-rc.1\"\n---\n"
            at = Path(tmp) / "at.md"
            at.write_bytes(head + b"x" * (1_048_576 - len(head)))  # exactly at the limit
            rc, out, err = _run(["--root", tmp, "--profile", "--json", "at.md"])
            self.assertEqual(json.loads(out)["artifacts"][0]["okf_concept"]["result"], "pass")
            self.assertNotIn("Traceback", err)
            over = Path(tmp) / "over.md"
            over.write_bytes(head + b"x" * 1_048_577)  # one region over the limit
            rc, out, err = _run(["--root", tmp, "--profile", "--json", "over.md"])
            r = json.loads(out)["artifacts"][0]
            self.assertEqual(r["okf_concept"], {"result": "unverified", "reason": "OKF_PARSE_LIMIT_EXCEEDED"})
            self.assertEqual(r["framework_profile"]["result"], "fail")
            self.assertEqual(rc, 1)
            self.assertNotIn("Traceback", err)

    def test_oversized_body_after_small_frontmatter(self) -> None:
        # A small valid frontmatter followed by an over-limit body -> total-input refusal.
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "b.md"
            f.write_bytes(b"---\ntype: analysis\n---\n" + b"y" * 1_048_600)
            rc, out, err = _run(["--root", tmp, "--profile", "--json", "b.md"])
            self.assertEqual(json.loads(out)["artifacts"][0]["okf_concept"]["reason"], "OKF_PARSE_LIMIT_EXCEEDED")
            self.assertNotIn("Traceback", err)

    def test_malformed_utf8_before_and_inside_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in (("pre.md", b"\xff\xfe# not utf8\n"),
                               ("inside.md", b"---\ntype: \xff\xfe x\n---\n")):
                (Path(tmp) / name).write_bytes(data)
                rc, out, err = _run(["--root", tmp, "--profile", "--json", name])
                d = json.loads(out)
                r = d["artifacts"][0]
                self.assertEqual(r["okf_concept"]["result"], "not_evaluated")
                self.assertEqual(r["framework_profile"]["result"], "not_applicable")
                self.assertGreaterEqual(d["errors"], 1)
                self.assertEqual(rc, 1)
                self.assertNotIn("Traceback", err)

    def test_deep_nesting_traceback_reproducer_is_bounded(self) -> None:
        # The exact Review 010 case: 1,000 nested flow sequences.
        text = "---\ntype: analysis\nx: " + "[" * 1000 + "]" * 1000 + "\n---\n"
        rec, rc, err = self._rec(text)
        self.assertEqual(rec["okf_concept"], {"result": "unverified", "reason": "OKF_PARSE_LIMIT_EXCEEDED"})
        self.assertEqual(rec["framework_profile"]["result"], "fail")
        self.assertEqual(rc, 1)
        self.assertEqual(err, "")  # empty routine stderr, no traceback

    def test_merge_keys(self) -> None:
        # A single merge key is valid YAML/OKF but out of the producer subset.
        self._assert('---\ntype: analysis\nframework_profile: "0.1-rc.1"\n'
                     'base: &b {x: 1}\nm:\n  <<: *b\n  y: 2\n---\n',
                     "pass", None, "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        # Two merge keys at one mapping are a duplicate key (top-level and nested).
        self._assert('---\ntype: analysis\n<<: {a: 1}\n<<: {b: 2}\n---\n',
                     "fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        self._assert('---\ntype: analysis\nframework_profile: "0.1-rc.1"\n'
                     'b1: &b {x: 1}\nm:\n  <<: *b\n  <<: *b\n---\n',
                     "fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        # A quoted string key "<<" is distinct from a resolved merge key: not a duplicate.
        self._assert('---\ntype: analysis\nframework_profile: "0.1-rc.1"\n'
                     'b1: &b {x: 1}\nm:\n  "<<": 9\n  <<: *b\n---\n',
                     "pass", None, "fail", "PROFILE_YAML_OUT_OF_SUBSET")

    def test_additional_named_resource_limits(self) -> None:
        """Direct public-CLI coverage for the six configured limits not exercised by
        ``test_named_resource_limits``. Each input is crafted so an earlier bound in
        the pipeline does not shadow the limit under test, carries a unique untrusted
        marker in a normal frontmatter scalar, and is run twice so the public JSON is
        proven bounded, run-to-run deterministic, and free of input echo."""
        def mark(case: str) -> str:
            return f"HOSTILE_LIMIT_PROBE_{case.upper()}_DO_NOT_ECHO"

        def fm(case: str, body: str) -> str:
            # A normal frontmatter scalar carries the case marker without changing
            # which limiter the body reaches.
            return f"---\ntype: analysis\nprobe: {mark(case)}\n{body}\n---\n"

        cases = {
            # frontmatter bytes over 64 KiB while staying <=500 lines and <=8192/line.
            "frontmatter_bytes": "---\ntype: analysis\nprobe: " + mark("frontmatter_bytes")
                + "\n" + "".join(f"k{i}: {'x' * 700}\n" for i in range(100)) + "---\n",
            # scanner tokens over 10,000, past framing bounds, before composition.
            "tokens": fm("tokens",
                "x: [" + ",\n ".join(",".join("a" for _ in range(1500)) for _ in range(4)) + "]"),
            # >2,000 unique composed nodes (700 two-item inner sequences), each
            # collection at or below its own ceiling.
            "unique_nodes": fm("unique_nodes",
                "x: [" + ",\n ".join(",".join("[a,a]" for _ in range(28)) for _ in range(25)) + "]"),
            # a constructed scalar over 16,384 chars with no physical line over 8,192.
            "scalar_length": '---\ntype: analysis\nprobe: ' + mark("scalar_length")
                + '\nx: "' + "A" * 6000 + "\n " + "A" * 6000 + "\n " + "A" * 6000 + '"\n---\n',
            # 501 mapping items (flow) without hitting token/node/line bounds first.
            "mapping_items": fm("mapping_items",
                "x: {" + ", ".join(f"k{i}: {i}" for i in range(501)) + "}"),
            # 1,001 sequence items (flow).
            "sequence_items": fm("sequence_items",
                "x: [" + ", ".join(str(i) for i in range(1001)) + "]"),
        }
        for label, text in cases.items():
            with self.subTest(limit=label):
                marker = mark(label)
                (rc1, out1, err1), (rc2, out2, err2) = self._raw_twice(text)
                # 1. Byte-identical complete tuples across two same-path runs.
                self.assertEqual((rc1, out1, err1), (rc2, out2, err2))
                # 2. Bounded public stdout (test safety ceiling; ~680 bytes observed).
                self.assertLessEqual(len(out1.encode("utf-8")), 4096)
                # 3. The untrusted marker is never echoed to stdout or stderr.
                for stream in (out1, err1, out2, err2):
                    self.assertNotIn(marker, stream)
                # 4. Schema v2 and the exact per-layer refusal outcomes are retained.
                doc = json.loads(out1)
                self.assertEqual(doc["schema_version"], "template.okf_profile_check.v2")
                rec = doc["artifacts"][0]
                self.assertEqual(
                    rec["okf_concept"], {"result": "unverified", "reason": "OKF_PARSE_LIMIT_EXCEEDED"})
                self.assertEqual(
                    rec["framework_profile"], {"result": "fail", "reason": "PROFILE_YAML_OUT_OF_SUBSET"})
                self.assertEqual(rec["execution_eligibility"], "not_evaluated")
                # 5. Exit 1 and exactly empty routine stderr (also rules out a traceback).
                self.assertEqual(rc1, 1)
                self.assertEqual(err1, "")
        # At-ceiling non-refusals: exactly 500 mapping items and 1,000 sequence
        # items compose without a resource refusal (kept without a marker to
        # preserve the prior at-ceiling constructions exactly).
        plain = "---\ntype: analysis\n{}\n---\n"
        for label, text in (
            ("mapping_500", plain.format("x: {" + ", ".join(f"k{i}: {i}" for i in range(500)) + "}")),
            ("sequence_1000", plain.format("x: [" + ", ".join(str(i) for i in range(1000)) + "]")),
        ):
            with self.subTest(at_ceiling=label):
                rec, _, err = self._rec(text)
                self.assertNotEqual(rec["okf_concept"]["reason"], "OKF_PARSE_LIMIT_EXCEEDED")
                self.assertEqual(err, "")

    def test_named_resource_limits(self) -> None:
        limit = "unverified", "OKF_PARSE_LIMIT_EXCEEDED", "fail", "PROFILE_YAML_OUT_OF_SUBSET"
        # nesting depth (33 nested block mappings)
        deep = "".join("  " * i + f"k{i}:\n" for i in range(33))
        self._assert("---\ntype: analysis\n" + deep + "---\n", *limit)
        # alias fan-out over the alias-count ceiling
        aliases = "base: &b x\n" + "".join(f"k{i}: *b\n" for i in range(60))
        self._assert("---\ntype: analysis\n" + aliases + "---\n", *limit)
        # self-referential alias cycle
        self._assert("---\ntype: analysis\na: &x [*x]\n---\n", *limit)
        # oversized single line
        self._assert("---\ntype: analysis\nx: " + "a" * 9000 + "\n---\n", *limit)
        # too many frontmatter lines
        self._assert("---\n" + "".join(f"k{i}: v{i}\n" for i in range(600)) + "---\n", *limit)

    # ----- determinism / non-mutation / containment / order -----

    def test_determinism_and_non_mutation(self) -> None:
        paths = [str(p) for p in FIX_ROOT.rglob("*.md")]
        before = {p: Path(p).read_bytes() for p in paths}
        a = _run(["--root", str(ROOT), "--profile", "--json", *paths])[1]
        b = _run(["--root", str(ROOT), "--profile", "--json", *paths])[1]
        after = {p: Path(p).read_bytes() for p in paths}
        self.assertEqual(a, b)
        self.assertEqual(before, after)

    def test_input_order_and_containment(self) -> None:
        order = ["tests/fixtures/okf_profile/version_unknown.md",
                 "tests/fixtures/okf_profile/accepted_minimal.md",
                 "tests/fixtures/okf_profile/legacy_no_frontmatter.md"]
        _, out, _ = _run(["--root", str(ROOT), "--profile", "--json", *order])
        self.assertEqual([a["path"] for a in json.loads(out)["artifacts"]], order)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "proj").mkdir()
            (tmp / "secret.md").write_text("---\ntype: analysis\n---\n", encoding="utf-8")
            rc, out, _ = _run(["--root", str(tmp / "proj"), "--profile", "--json", "../secret.md"])
            self.assertEqual(json.loads(out)["artifacts"][0]["okf_concept"]["result"], "not_evaluated")
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
