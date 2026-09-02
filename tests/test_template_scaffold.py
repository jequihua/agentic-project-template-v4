"""Doc invariant checks for the v2 scaffold.

These tests are intentionally small. They verify that the scaffold exposes the
core loop surfaces without requiring optional tools such as llloom or frutlups.
"""

from __future__ import annotations

import fnmatch
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Clone-only integrity checks: they protect the template as shipped and are
# scoped by the scaffold's own Status line, so a populated project reports them
# as skipped, never as failures.
SCAFFOLD_STATUS = "initialized template scaffold"


def _is_fresh_scaffold(state_path: Path = ROOT / "PROJECT_STATE.md") -> bool:
    """True only while PROJECT_STATE.md still carries the shipped Status."""
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Status:"):
            return line.split(":", 1)[1].strip() == SCAFFOLD_STATUS
    return False


_CLONE_ONLY = unittest.skipUnless(
    _is_fresh_scaffold(),
    "clone-only integrity check: PROJECT_STATE.md Status is no longer the shipped scaffold",
)

# The development release-projection manifest's exact `[ignore].globs`, matched by the
# same `fnmatch.fnmatch` primitive the projection engine uses (IgnoreRules.should_skip),
# so platform case normalization is identical on every OS (case-insensitive on Windows).
_RELEASE_IGNORE_GLOBS = ("*.egg-info", ".codex_tmp*", "*.log", ".coverage", "test-results*")
# Other bounded categories the clean `.gitignore` and projection also omit (exact
# directory names, plus the `.venv*` and `*_work` families and bytecode suffixes) that do
# not come from `[ignore].globs`. `test-results`/`.coverage`/`*.log`/`*.egg-info` are not
# repeated here: they are covered exactly by the glob tuple above.
_RELEASE_IGNORE_DIR_NAMES = frozenset({
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "venv", "env", "node_modules", "local_state", ".local", ".frutlups_drive", "build", "dist",
    "htmlcov", ".idea", ".vscode", "tmp", "temp",
    "llloom_memory", "memory_root", ".ipynb_checkpoints",
})
_RELEASE_IGNORE_SUFFIXES = (".pyc", ".pyo")
# Governed local surfaces: never distributable, skipped by every purity scan,
# identical to the drive's internally ignored set (frutlups.layout.yaml local_state).
_GOVERNED_LOCAL_SURFACES = ("local_state", ".frutlups_drive")
_MACHINE_FRAGMENTS = (
    "C:" + "\\Users\\dev",
    "repos" + "_dev",
    "agentic-project-template" + "-v2" + "-dev",
)


def _template_owned_paths(root: Path) -> list[Path]:
    """Template-owned surfaces declared under ``template_owned_surfaces`` in
    ``frutlups.layout.yaml`` (raw-text read; the tests never import a YAML
    parser). These are the surfaces a project refreshes from the template and
    the only surfaces the purity scans walk."""
    text = (root / "frutlups.layout.yaml").read_text(encoding="utf-8")
    block = text.split("\ntemplate_owned_surfaces:\n", 1)[1].split("\nlocal_state:\n", 1)[0]
    paths: list[Path] = []
    for line in block.splitlines():
        match = re.match(r'^\s+-\s+"([^"]+)"$', line)
        if match:
            paths.append(root / match.group(1))
    return paths


def _owned_files(root: Path, surfaces: list[Path]):
    """Regular files under the given surfaces, minus governed local surfaces and
    release-ignored residue."""
    for base in surfaces:
        if base.is_file():
            candidates = [base]
        elif base.is_dir():
            candidates = base.rglob("*")
        else:
            continue
        for p in candidates:
            if p.is_symlink() or not p.is_file():
                continue
            rel = p.relative_to(root)
            if any(part in _GOVERNED_LOCAL_SURFACES for part in rel.parts):
                continue
            if _is_release_ignored(rel):
                continue
            yield p


def _machine_path_offenders(root: Path, surfaces: list[Path]) -> list[str]:
    """Template-owned text files carrying this development machine's paths."""
    offenders: list[str] = []
    for p in _owned_files(root, surfaces):
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(fragment in text for fragment in _MACHINE_FRAGMENTS):
            offenders.append(p.relative_to(root).as_posix())
    return sorted(offenders)


def _is_release_ignored(rel: Path) -> bool:
    """True if a repo-relative path is omitted by the release projection's ignore rules.

    The five manifest globs are matched with the operative `fnmatch.fnmatch` on each
    directory and file basename, so this predicate is exactly `fnmatch`-equivalent to the
    engine on the current platform (including Windows case-insensitivity). The remaining
    bounded categories are exact directory names, the `.venv*`/`*_work` families, and
    bytecode suffixes.
    """
    for part in rel.parts:
        if part in _RELEASE_IGNORE_DIR_NAMES:
            return True
        if part.startswith(".venv") or part.endswith("_work"):
            return True
        if any(fnmatch.fnmatch(part, pat) for pat in _RELEASE_IGNORE_GLOBS):
            return True
    return rel.suffix in _RELEASE_IGNORE_SUFFIXES


def _distributable_text_crlf(root: Path, surfaces: list[Path] | None = None) -> list[str]:
    """Sorted relative POSIX paths of shipped UTF-8 text files under ``root`` that carry
    CRLF. Does not follow symlinked files or escape ``root``; skips release-ignored
    metadata; and treats a file as text only when it is strict UTF-8 with no NUL byte, so
    a binary payload containing ``\\r\\n`` is never reported as distributable text.
    With ``surfaces`` the walk is restricted to those template-owned paths and skips the
    governed local surfaces, so the check runs unchanged inside a populated project."""
    root = root.resolve()
    offenders: list[str] = []
    if surfaces is not None:
        files = _owned_files(root, [s.resolve() for s in surfaces])
    else:
        files = root.rglob("*")
    for p in files:
        if p.is_symlink() or not p.is_file():
            continue
        rel = p.relative_to(root)
        if _is_release_ignored(rel):
            continue
        if not p.resolve().is_relative_to(root):  # defensive containment
            continue
        data = p.read_bytes()
        if b"\x00" in data:                       # binary marker -> not text
            continue
        try:
            data.decode("utf-8")                  # strict UTF-8 -> text
        except UnicodeDecodeError:
            continue
        if b"\r\n" in data:
            offenders.append(rel.as_posix())
    return sorted(offenders)


class TemplateScaffoldTests(unittest.TestCase):
    def _is_ignored_local_path(self, path: Path) -> bool:
        """Honor simple exact directory rules from .gitignore during broad scans.

        Scaffold invariants apply to distributable template files, not ignored
        venvs, copied reference repositories, memory roots, local bootstrap
        evidence, or other local-only inputs. Complex glob semantics are
        unnecessary here; broad scans only need the explicit directory rules
        ending in ``/``.
        """
        rel_parts = path.relative_to(ROOT).parts
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for raw in gitignore.splitlines():
            rule = raw.strip()
            if not rule or rule.startswith(("#", "!")) or not rule.endswith("/"):
                continue
            rule = rule.rstrip("/")
            if any(mark in rule for mark in ("*", "?", "[")):
                continue
            parts = Path(rule).parts
            if rel_parts[: len(parts)] == parts:
                return True
        return False

    def _assert_no_test_imports(self, module: str) -> None:
        """Fail if any scaffold test imports the named optional tool.

        Matches real line-anchored ``import``/``from`` statements so the guard
        never flags its own assertion text or a method name.
        """
        pattern = re.compile(rf"^\s*(?:import|from)\s+{module}\b", re.MULTILINE)
        for test_file in (ROOT / "tests").glob("test_*.py"):
            text = test_file.read_text(encoding="utf-8")
            self.assertIsNone(
                pattern.search(text),
                f"{test_file} imports {module}; scaffold tests must not require it",
            )

    def _mode_value(self, state_text: str, label: str) -> str | None:
        """Return the bullet value under a ``Label:`` line in PROJECT_STATE.md."""
        lines = state_text.splitlines()
        for index, line in enumerate(lines):
            if line.strip().lower() == f"{label.lower()}:":
                for follow in lines[index + 1:]:
                    stripped = follow.strip()
                    if stripped:
                        return stripped.lstrip("- ").strip().lower()
        return None

    def test_root_control_files_exist(self) -> None:
        for name in (
            "README.md",
            "CLAUDE.md",
            "PROJECT_STATE.md",
            "ENVIRONMENT.md",
            "LOCAL_STATE_NOT_COMMITTED.md",
            "MILESTONES.md",
        ):
            self.assertTrue((ROOT / name).is_file(), f"missing {name}")

    def test_all_initialization_prompts_exist(self) -> None:
        init = ROOT / "initialization"
        expected = (
            "001_architect_reviewer_framework_initialization.md",
            "002_coder_framework_initialization.md",
            "003_architect_reviewer_llloom_initialization.md",
            "004_coder_llloom_initialization.md",
            "005_architect_reviewer_frutlups_initialization.md",
            "006_coder_frutlups_initialization.md",
            "007_architect_reviewer_project_intake_questionnaire.md",
        )
        for name in expected:
            self.assertTrue((init / name).is_file(), f"missing {name}")

    def test_project_state_names_optional_modes(self) -> None:
        text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8").lower()
        self.assertIn("memory mode", text)
        self.assertIn("frutlups mode", text)
        self.assertIn("active workspaces", text)
        self.assertIn("validation command", text)

    def test_llloom_is_optional_and_read_only_by_default(self) -> None:
        text = (
            ROOT / "initialization" / "004_coder_llloom_initialization.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("only when", text)
        self.assertIn("read-only", text)
        self.assertIn("do not mutate", text)

    def test_frutlups_is_optional(self) -> None:
        text = (
            ROOT / "initialization" / "005_architect_reviewer_frutlups_initialization.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("optional", text)
        self.assertIn("manual", text)
        self.assertIn("semi-manual", text)
        self.assertIn("automated driver", text)

    def test_prompt_template_contains_non_goals_and_done(self) -> None:
        text = (ROOT / "prompts" / "templates" / "coding_prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Non-Goals", text)
        self.assertIn("## Definition Of Done", text)

    def test_project_intake_questionnaire_names_outputs(self) -> None:
        """The architect intake prompt must preserve answers and populate rails."""
        text = (
            ROOT
            / "initialization"
            / "007_architect_reviewer_project_intake_questionnaire.md"
        ).read_text(encoding="utf-8")
        for fragment in (
            "00_brief/project_intake_answers.md",
            "00_brief/glossary.md",
            "PROJECT_STATE.md",
            "first roadmap",
            "first coding prompt",
        ):
            self.assertIn(fragment, text)

    def test_glossary_surface_exists(self) -> None:
        glossary = ROOT / "00_brief" / "glossary.md"
        self.assertTrue(glossary.is_file(), "missing 00_brief/glossary.md")
        text = glossary.read_text(encoding="utf-8").lower()
        self.assertIn("canonical terms", text)
        self.assertIn("open terminology questions", text)

    def test_frutlups_layout_config_declares_rails(self) -> None:
        """The v2 frutlups layout config (a template artifact) must declare the
        core rails and stay honest that no runner exists.

        Only the in-template config is checked; the legacy/root config and the
        usage doc live outside the template and would not ship with a clone.
        """
        config = ROOT / "frutlups.layout.yaml"
        self.assertTrue(config.is_file(), "missing frutlups.layout.yaml")
        text = config.read_text(encoding="utf-8")
        for fragment in (
            "PROJECT_STATE.md",
            "prompts/for_coding_agent",
            "prompts/for_review_agent",
            "_self_report.md",
            "_review_report.md",
            "_verdict_record.md",
            "runner_implemented: false",
        ):
            self.assertIn(fragment, text, f"layout config omits '{fragment}'")

    def test_layout_config_is_portable(self) -> None:
        """The shipped v2 config must be machine-portable: no Windows absolute
        paths, null external install sources, and the root-relative convention."""
        text = (ROOT / "frutlups.layout.yaml").read_text(encoding="utf-8")
        self.assertNotIn("C:" + "\\", text, "shipped YAML must not contain machine-local paths")
        self.assertIn("frutlups_source: null", text)
        self.assertIn("install_source: null", text)
        self.assertIn("install_source_note", text)
        self.assertIn('template_root: "."', text)
        self.assertNotIn("redesign" + " repo", text.lower())

    def test_layout_config_has_prompt_section_roles(self) -> None:
        """The config must expose prompt semantic roles and front-matter metadata
        so a loader reads section names and metadata as data, not assumptions."""
        text = (ROOT / "frutlups.layout.yaml").read_text(encoding="utf-8")
        self.assertIn("section_roles", text)
        for role in (
            'required_reading: "Read First"',
            'self_report: "Self-Report"',
            'non_goals: "Non-Goals"',
            'task: "Task"',
            'verification: "Verification"',
        ):
            self.assertIn(role, text, f"section_roles omits '{role}'")
        self.assertIn("parse_front_matter: true", text)
        for field in ('milestone_field: "milestone"', 'slice_field: "slice"', 'title_field: "title"'):
            self.assertIn(field, text, f"metadata omits '{field}'")

    def test_method_names_commit_discipline(self) -> None:
        """The canonical commit rule lives in method.md and names the boundary."""
        text = (
            ROOT / "docs" / "template_framework" / "method.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("commit discipline", text)
        self.assertIn("accepted", text)
        self.assertIn("milestone", text)

    def test_git_policy_is_automation_safe(self) -> None:
        """The v2 layout config must expose a git policy where automation cannot
        commit by default but may report commit-ready."""
        text = (ROOT / "frutlups.layout.yaml").read_text(encoding="utf-8")
        self.assertIn("git_policy", text)
        self.assertIn("runner_may_commit: false", text)
        self.assertIn("runner_may_report_commit_ready: true", text)

    def test_method_distinguishes_commit_and_pr_ready(self) -> None:
        """The canonical git guidance must separate commit-ready from PR-ready."""
        text = (
            ROOT / "docs" / "template_framework" / "method.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("commit-ready", text)
        self.assertIn("pull-request-ready", text)

    def test_pull_request_policy_is_human_controlled(self) -> None:
        """The v2 layout config must keep PR timing human-controlled: a runner may
        report PR-ready but must not open PRs by default."""
        text = (ROOT / "frutlups.layout.yaml").read_text(encoding="utf-8")
        self.assertIn("pull_request_policy", text)
        self.assertIn("runner_may_open_pull_request: false", text)
        self.assertIn("human_may_request_any_time: true", text)

    def test_gitignore_covers_commit_safety_baseline(self) -> None:
        """The template .gitignore must exclude common junk, local state, secrets,
        test output, build output, and editor noise before any milestone commit."""
        gitignore = ROOT / ".gitignore"
        self.assertTrue(gitignore.is_file(), "missing .gitignore")
        # Match exact non-comment lines so a broader pattern (e.g. `.env.*`) does
        # not mask a missing exact entry (e.g. `.env`).
        lines = {
            line.strip()
            for line in gitignore.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        for pattern in (
            "__pycache__/",
            ".pytest_cache/",
            ".coverage",
            ".env",
            "node_modules/",
            "local_state/",
            "dist/",
            "build/",
            ".ipynb_checkpoints/",
            ".DS_Store",
        ):
            self.assertIn(pattern, lines, f".gitignore omits exact line '{pattern}'")

    def test_method_names_commit_closure(self) -> None:
        """The canonical closure checklist must name the inspection commands."""
        text = (
            ROOT / "docs" / "template_framework" / "method.md"
        ).read_text(encoding="utf-8")
        for fragment in ("git status --short", ".gitignore", "git diff --cached --stat"):
            self.assertIn(fragment, text, f"method.md omits '{fragment}'")

    def test_git_policy_before_commit_requires(self) -> None:
        """The v2 layout config must require closure checks before a commit."""
        text = (ROOT / "frutlups.layout.yaml").read_text(encoding="utf-8")
        self.assertIn("before_commit_requires", text)
        self.assertIn("git status reviewed", text)
        self.assertIn("staged diff reviewed", text)
        self.assertIn(".gitignore checked", text)

    def test_method_names_default_committer(self) -> None:
        """The architect/reviewer is the canonical default milestone committer."""
        text = (
            ROOT / "docs" / "template_framework" / "method.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("architect/reviewer", text)
        self.assertIn("default committer", text)

    def test_git_policy_default_committer(self) -> None:
        """The v2 layout config must encode the default committer policy: the
        architect/reviewer commits at the boundary, the coder does not by default,
        and a runner commits only when explicitly authorized."""
        text = (ROOT / "frutlups.layout.yaml").read_text(encoding="utf-8")
        self.assertIn('default_committer_role: "architect_reviewer"', text)
        self.assertIn("architect_reviewer_may_commit_at_boundary: true", text)
        self.assertIn("coder_may_commit_by_default: false", text)
        self.assertIn("runner_may_commit: false", text)
        self.assertIn("runner_may_commit_when_explicitly_authorized: true", text)

    def test_intake_links_profile_selection(self) -> None:
        """Intake must route project type into the profile model, not invent its
        own workspace-selection rules."""
        text = (
            ROOT
            / "initialization"
            / "007_architect_reviewer_project_intake_questionnaire.md"
        ).read_text(encoding="utf-8")
        self.assertIn("project_profiles.md", text)

    def test_glossary_lists_status_options(self) -> None:
        """The glossary surface must document its controlled status vocabulary."""
        text = (ROOT / "00_brief" / "glossary.md").read_text(encoding="utf-8").lower()
        for status in ("accepted", "tentative", "needs human clarification"):
            self.assertIn(status, text, f"glossary omits status '{status}'")

    def test_self_report_schema_single_source(self) -> None:
        """The self-report schema has one canonical source; other surfaces
        reference it and must not silently drift from it.

        This guards against the frutlups failure mode where a prompt's friendly
        heading list disagreed with the validator's required headings, forcing
        repeated repair loops.
        """
        canonical_text = (
            ROOT / "prompts" / "templates" / "self_report.md"
        ).read_text(encoding="utf-8")
        fields = []
        for raw in canonical_text.splitlines():
            line = raw.strip()
            if line.endswith(":") and not line.startswith("#"):
                fields.append(line[:-1].strip())
        self.assertGreaterEqual(
            len(fields), 10, "canonical self-report schema looks too small"
        )
        self.assertIn("Intent", fields)

        # The coder initialization prompt restates the skeleton for onboarding;
        # it must carry every canonical field verbatim.
        init_text = (
            ROOT / "initialization" / "002_coder_framework_initialization.md"
        ).read_text(encoding="utf-8")
        for field in fields:
            self.assertIn(
                f"{field}:", init_text, f"init skeleton missing '{field}'"
            )

        # The coding-prompt template must point at the canonical schema file,
        # not restate headings or redirect to an onboarding prompt.
        coding_prompt_text = (
            ROOT / "prompts" / "templates" / "coding_prompt.md"
        ).read_text(encoding="utf-8")
        self.assertIn("prompts/templates/self_report.md", coding_prompt_text)

    def test_minimal_implementation_discipline_semantics(self) -> None:
        """M011, harmonized 2026-08-03 by owner decision: `CLAUDE.md` Minimal
        Implementation Discipline is the single canonical YAGNI copy. The
        coding template carries only a pointer plus a compressed summary (no
        full paraphrase, which had drifted), and the review template keeps its
        reviewer-specific accretion checks. Anchors guard load-bearing meaning
        rather than freezing paragraphs."""
        def read(rel: str) -> str:
            return (ROOT / rel).read_text(encoding="utf-8")

        claude = read("CLAUDE.md")
        coding = read("prompts/templates/coding_prompt.md")
        review = read("prompts/templates/review_prompt.md")
        report = read("prompts/templates/self_report.md")
        method = read("docs/template_framework/method.md")

        surfaces = {
            "canonical-claude": (claude, (
                "smallest correct useful change (YAGNI), not mechanically the",
                "structure earned by current evidence",
                "repeated concrete duplication",
                "usually by the third occurrence",
                "invariant that must change together is not speculative",
                "reduces total complexity and preserves local",
                "Small corrections must not silently accrete complexity",
                "evidence-backed simplification candidate without expanding the slice",
                "candidate is not authorized work",
                "prefer table-driven cases or",
                "assert exact contract values individually",
                "correctness, security, trust-boundary validation, data-loss prevention",
                "accessibility, explicit human requirements, or needed tests",
            )),
            "coding-template": (coding, (
                "CLAUDE.md` Minimal Implementation Discipline",
                "not restated here",
                "mechanically the smallest diff",
                "prefer table-driven tests or",
                "assert exact contract values individually",
            )),
            "review-template": (review, (
                "silent complexity accretion",
                "smallest-diff corrections",
                "bounded in-scope simplification",
                "recording a candidate does not authorize it",
                "unauthorized refactor or roadmap expansion",
            )),
            "self-report-template": (report, (
                "material out-of-scope complexity accretion",
                "treat it explicitly as unapproved",
                "follow-up, not authorized work",
            )),
            "method": (method, (
                "speculative architecture or a",
                "keeping structure earned by present evidence",
            )),
        }
        for name, (text, anchors) in surfaces.items():
            with self.subTest(surface=name):
                for anchor in anchors:
                    self.assertIn(anchor, text, f"{name} lost YAGNI anchor: {anchor!r}")

        # The self-report accretion guidance stays under the existing
        # "Known Limits / Follow-Up:" surface and adds no new schema heading.
        with self.subTest(surface="self-report-placement"):
            known = report.index("Known Limits / Follow-Up:")
            nxt = report.index("Recommended Next Move:")
            accretion = report.index("material out-of-scope complexity accretion")
            self.assertLess(known, accretion)
            self.assertLess(accretion, nxt)

    def test_project_state_contract_matches_state_file(self) -> None:
        """The PROJECT_STATE field contract and PROJECT_STATE.md must not drift:
        every field the contract marks required must exist in the file."""
        contract_path = (
            ROOT / "docs" / "template_framework" / "project_state_contract.md"
        )
        self.assertTrue(contract_path.is_file(), "missing project_state_contract.md")
        contract = contract_path.read_text(encoding="utf-8")

        # Read the required fields from the "## Required Fields" section only.
        required = []
        in_section = False
        for raw in contract.splitlines():
            line = raw.strip()
            if line.startswith("## "):
                in_section = line.lower().startswith("## required fields")
                continue
            if in_section:
                match = re.match(r"^-\s+`([^`]+)`", line)
                if match:
                    required.append(match.group(1))
        self.assertGreaterEqual(
            len(required), 10, "contract lists too few required fields"
        )

        state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        for field in required:
            self.assertIn(
                f"{field}:", state, f"PROJECT_STATE.md missing required field '{field}'"
            )

    def test_fast_close_template_has_guardrails(self) -> None:
        """Fast-close must stay append-only and forbidden for behavior changes."""
        text = (
            ROOT / "prompts" / "templates" / "fast_close_correction.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("append-only", text)
        self.assertIn("behavior", text)

    def test_memory_posture_names_install_source_and_update_slice(self) -> None:
        """The memory posture surface must carry the load-bearing llloom facts:
        where a project records llloom install details, and that mutation is a
        dedicated slice."""
        text = (
            ROOT / "05_governance" / "current" / "memory_posture.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("install source", text)
        self.assertIn("memory-update slice", text)

    def test_no_scaffold_test_requires_llloom(self) -> None:
        """The suite must run without llloom installed (downstream-safe)."""
        self._assert_no_test_imports("llloom")

    def test_frutlups_posture_names_source_and_guide(self) -> None:
        """The frutlups posture surface must provide clean fields for the source
        reference and integration guide when a project enables the tool."""
        text = (
            ROOT / "05_governance" / "current" / "frutlups_posture.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("install/source reference", text)
        self.assertIn("guide", text)

    def test_template_has_no_machine_local_paths(self) -> None:
        """Template-owned surfaces must not carry this development machine's
        local paths or repository names - in the template and in every project
        that refreshes them. Governed local surfaces (run stores, local state)
        are never scanned, so the check stays green in a populated project and
        still fails on the same defect in distributable source."""
        offenders = _machine_path_offenders(ROOT, _template_owned_paths(ROOT))
        self.assertEqual(offenders, [], f"machine-local content in template-owned surfaces: {offenders[:3]}")

    def test_purity_scans_skip_governed_surfaces_but_catch_owned_defects(self) -> None:
        """Both directions of the purity property: a CRLF/machine-path defect in a
        governed local surface must not fail; the same defect in a template-owned
        surface must fail."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frutlups.layout.yaml").write_text(
                "x: 1\n\ntemplate_owned_surfaces:\n  directories:\n"
                "    - \"docs/template_framework\"\n  files:\n"
                "    - \"frutlups.layout.yaml\"\n\nlocal_state:\n  root: \"local_state/\"\n",
                encoding="utf-8", newline="\n",
            )
            owned = root / "docs" / "template_framework"
            owned.mkdir(parents=True)
            governed = root / ".frutlups_drive" / "runs" / "run_001"
            governed.mkdir(parents=True)
            (root / "local_state").mkdir()
            defect = b"line\r\nPath " + _MACHINE_FRAGMENTS[0].encode() + b"\\x\n"
            (governed / "adapter.md").write_bytes(defect)
            (root / "local_state" / "note.md").write_bytes(defect)
            surfaces = _template_owned_paths(root)
            self.assertEqual(_distributable_text_crlf(root, surfaces), [])
            self.assertEqual(_machine_path_offenders(root, surfaces), [])
            (owned / "guide.md").write_bytes(defect)
            self.assertEqual(_distributable_text_crlf(root, surfaces), ["docs/template_framework/guide.md"])
            self.assertEqual(_machine_path_offenders(root, surfaces), ["docs/template_framework/guide.md"])

    def test_layout_names_every_shipped_scaffold_test_module(self) -> None:
        """The template-owned surface list is the refresh contract; every shipped
        test module must be named there (and nothing that does not exist)."""
        listed = {p.name for p in _template_owned_paths(ROOT) if p.suffix == ".py"}
        on_disk = {p.name for p in (ROOT / "tests").glob("test_*.py")}
        self.assertEqual(listed, on_disk)

    def test_clone_only_scope_follows_project_state_status(self) -> None:
        """Clone-only integrity checks run while PROJECT_STATE.md still carries
        the shipped Status and skip (never fail) once a project replaces it."""
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "PROJECT_STATE.md"
            state.write_text(
                f"# Project State\n\nStatus: {SCAFFOLD_STATUS}\n", encoding="utf-8"
            )
            self.assertTrue(_is_fresh_scaffold(state))
            state.write_text(
                "# Project State\n\nStatus: campaign running\n", encoding="utf-8"
            )
            self.assertFalse(_is_fresh_scaffold(state))
            state.write_text("# Project State\n\nTemplate version: v3\n", encoding="utf-8")
            self.assertFalse(_is_fresh_scaffold(state))

    def test_frutlups_driver_boundary_is_spec_only(self) -> None:
        """The driver boundary must stay a specification, not an implementation."""
        path = ROOT / "docs" / "template_framework" / "frutlups_driver_boundary.md"
        self.assertTrue(path.is_file(), "missing frutlups_driver_boundary.md")
        text = path.read_text(encoding="utf-8").lower()
        self.assertIn("no runner is implemented", text)

    @staticmethod
    def _section_outside_fences(text: str, heading: str) -> str:
        """Body of a Markdown section, up to the next same-or-higher heading.

        Headings inside fenced examples are skipped, so a doc may show the
        literal roadmap headings it defines without truncating its own section.
        """
        level = len(heading) - len(heading.lstrip("#"))
        out, capturing, fenced = [], False, False
        for line in text.splitlines():
            if line.startswith("```"):
                fenced = not fenced
            elif not fenced and line.strip() == heading:
                capturing = True
                continue
            elif capturing and not fenced and line.startswith("#"):
                if len(line) - len(line.lstrip("#")) <= level:
                    break
            if capturing:
                out.append(line)
        return "\n".join(out)

    @staticmethod
    def _bullets(section: str) -> list[str]:
        """Top-level ``- `` bullets, each joined with its continuation lines."""
        bullets: list[str] = []
        for line in section.splitlines():
            if line.startswith("- "):
                bullets.append(line[2:].strip())
            elif bullets and line.startswith("  ") and line.strip():
                bullets[-1] += " " + line.strip()
        return bullets

    def test_roadmap_uncertainty_and_exclusion_semantics(self) -> None:
        """M013: the two optional roadmap registers keep their load-bearing
        meaning, lifecycle, and authority across the method, the question
        policy, and the specification-only driver boundary.

        Anchored on the distinctions and control-flow words that decide
        behavior, not on whole paragraphs, so ordinary rewording stays free.
        The template ships no parser or runner, so nothing here claims
        downstream behavior this repository cannot execute.
        """
        framework = ROOT / "docs" / "template_framework"
        method = (framework / "method.md").read_text(encoding="utf-8")
        boundary = (framework / "frutlups_driver_boundary.md").read_text(
            encoding="utf-8"
        )
        policy = (
            ROOT / "05_governance" / "current" / "question_policy.md"
        ).read_text(encoding="utf-8")

        doctrine = self._section_outside_fences(
            method, "## Roadmap Uncertainty And Project Exclusions"
        )
        self.assertTrue(doctrine.strip(), "method.md has no roadmap-uncertainty section")

        # The four-way admission decision, the four distinct lanes, optional and
        # manual-first operation, the lifecycle cadence, and human authority.
        for label, anchor in (
            ("exact fog heading", "`## Not Yet Specified`"),
            ("exact exclusion heading", "`## Ruled Out`"),
            ("sharp work becomes a slice", "sharp and actionable: write a narrow slice"),
            ("blocked work stays sharp", "a known blocker is never hidden as fog"),
            ("dim in-scope work becomes fog", "record a `Not Yet Specified` entry"),
            ("outside work becomes an exclusion", "record a `Ruled Out` entry"),
            ("exclusion is project-level", "project-level terminal register"),
            ("non-goals stay slice-local", "slice-local fences that expire"),
            ("no automatic promotion", "never promoted into `Ruled Out` automatically"),
            ("optional and manual-first", "optional and manual-first"),
            ("no new machinery", "neither adds a workspace, artifact type, dependency,"),
            ("ordinary bullets", "ordinary top-level Markdown bullets"),
            ("neither is executable work",
             "is an executable slice, and neither enters the frontier"),
            ("bounded reconsideration cadence",
             "at an accepted slice or pass boundary"),
            ("not every loop action", "not on every loop action"),
            ("human approval to narrow scope", "needs human approval"),
            ("level 4 removal or resurrection", "Level 4, human-aware scope change"),
            ("empty frontier is not completion",
             "An empty frontier is not completion evidence"),
            ("only accepted closure completes",
             "explicit accepted closure evidence does"),
        ):
            with self.subTest(method=label):
                self.assertIn(anchor, doctrine, f"method doctrine lost: {label}")

        # The question lane routes a precise externally owned question separately
        # from a dim in-scope concern, and never absorbs sharp blocked work.
        for label, anchor in (
            ("precise external question", "`questions/open/`"),
            ("dim in-scope concern", "`Not Yet Specified`"),
            ("blocked work stays sharp", "stays sharp and blocked"),
        ):
            with self.subTest(question_policy=label):
                self.assertIn(anchor, policy, f"question policy lost: {label}")

        # The driver boundary stays specification-only: no schema, no JSON
        # object, no parser — only the typed outcomes and their behavior.
        low = boundary.lower()
        self.assertIn("no runner is implemented", low)
        for forbidden in ("contract_version", "```json", "next_actor", "reason_code"):
            self.assertNotIn(
                forbidden, low, f"driver boundary must stay spec-only: {forbidden}"
            )

        outcomes = self._section_outside_fences(boundary, "## Planning-Frontier Outcomes")
        self.assertTrue(outcomes.strip(), "driver boundary has no typed-outcome section")
        mapped = {
            bullet.split("`")[1]: bullet
            for bullet in self._bullets(outcomes)
            if bullet.startswith("`")
        }
        for state, behavior in (
            ("ready", "continue the normal declared loop"),
            ("needs_specification", "dispatch one bounded architect planning turn"),
            ("blocked", "stop and report the cited block"),
            ("complete", "stop successfully only with explicit accepted completion"),
            ("invalid", "stop fail-closed with diagnostics"),
        ):
            with self.subTest(outcome=state):
                self.assertIn(state, mapped, f"driver boundary omits `{state}`")
                self.assertIn(
                    behavior, mapped[state],
                    f"`{state}` is not bound to its required runner behavior",
                )

        # Nothing may be documented as a successful completion by default:
        # not an empty frontier, not an unsupported version, not retry exhaustion.
        for label, anchor in (
            ("empty frontier", "the absence of a ready slice never proves completion"),
            ("unsupported version",
             "refuses any contract version it does not implement"),
            ("no roadmap interpretation", "does not parse roadmap prose"),
            ("typed actor only", "only when the typed state names that actor"),
            ("retry exhaustion", "no durable progress is a stopped run, never"),
            ("existing gates intact", "all existing human gates"),
        ):
            with self.subTest(driver_boundary=label):
                self.assertIn(anchor, outcomes, f"driver boundary lost: {label}")
        self.assertIn(
            "an `invalid` or unknown planning-frontier state",
            boundary,
            "the generic 'no frontier' stop rule must be typed",
        )

        # No new required PROJECT_STATE.md field, workspace, mode, OKF type, or
        # dependency: the registers stay ordinary optional roadmap Markdown.
        for label, text in (
            ("project-state contract",
             (framework / "project_state_contract.md").read_text(encoding="utf-8")),
            ("frutlups modes",
             (framework / "frutlups_modes.md").read_text(encoding="utf-8")),
            ("okf profile",
             (ROOT / "docs" / "template_framework" / "okf_pkg" / "okf_profile_v0_1.md"
              ).read_text(encoding="utf-8")),
        ):
            with self.subTest(unchanged_contract=label):
                for register in ("Not Yet Specified", "Ruled Out"):
                    self.assertNotIn(
                        register, text,
                        f"{label} must not turn '{register}' into a contract value",
                    )
        deps = (
            (ROOT / "pyproject.toml")
            .read_text(encoding="utf-8")
            .split("dependencies = [", 1)[1]
            .split("]", 1)[0]
        )
        self.assertEqual(
            [line.strip().strip('",') for line in deps.strip().splitlines()],
            ["PyYAML>=6.0.3,<7"],
            "the roadmap registers must not add a dependency",
        )

    def test_operator_guidance_for_optional_roadmap_registers(self) -> None:
        """M014: the shipped README and human manual make the optional roadmap
        registers discoverable and safe to use, and the automated-driver guidance
        stays contract-accurate rather than promising a generic stop rule.

        Bounded section extraction is used wherever the same phrase appears
        elsewhere in a long document, and only semantic anchors are asserted, so
        the guard survives ordinary rewording of the surrounding prose.
        """
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        manual = (
            ROOT / "docs" / "template_framework" / "human_user_manual.md"
        ).read_text(encoding="utf-8")

        # The README entry point names both exact registers, their correct use,
        # human authority, and the canonical contract; and it warns autonomous
        # operators that an empty frontier is not completion evidence.
        entry = self._section_outside_fences(readme, "## Optional Roadmap Registers")
        self.assertTrue(entry.strip(), "README has no optional-roadmap-register section")
        for label, anchor in (
            ("exact fog heading", "`## Not Yet Specified`"),
            ("exact exclusion heading", "`## Ruled Out`"),
            ("fog is in scope but not sharp", "not yet sharp"),
            ("exclusion is project-level", "project-level exclusion"),
            ("not a slice-local non-goal", "slice-local `Non-Goals`"),
            ("neither is required", "Neither is required"),
            ("neither is executable work", "part of the ready frontier"),
            ("blocked work stays in the question lane", "question/block lane"),
            ("human approval for scope change", "needs human approval"),
            ("canonical method link", "docs/template_framework/method.md"),
            ("empty frontier is not completion",
             "An empty frontier is never proof of completion"),
            ("only accepted evidence completes",
             "explicit accepted completion evidence"),
            ("driver boundary link",
             "docs/template_framework/frutlups_driver_boundary.md"),
            ("no runner is shipped", "runner ships with this template"),
        ):
            with self.subTest(readme=label):
                self.assertIn(anchor, entry, f"README guidance lost: {label}")

        # The manual keeps all four destinations distinct, refuses automatic
        # execution, bounds reconsideration, and preserves human scope authority.
        guidance = self._section_outside_fences(
            manual, "### Optional Roadmap Uncertainty And Project Exclusions"
        )
        self.assertTrue(guidance.strip(), "manual has no optional-roadmap subsection")
        for label, anchor in (
            ("slice destination", "write a normal slice"),
            ("question/block destination", "keep it as a question or block"),
            ("blocked work stays sharp", "it stays sharp"),
            ("fog destination", "`## Not Yet Specified` bullet"),
            ("exclusion destination", "`## Ruled Out` bullet"),
            ("optional, not required", "neither is required"),
            ("no automatic execution", "Neither list feeds execution"),
            ("bounded reconsideration", "not on every action"),
            ("human approval to narrow", "narrow the project"),
            ("human approval to resurrect", "ruled-out work is resurrected"),
            ("canonical method link", "docs/template_framework/method.md"),
        ):
            with self.subTest(manual=label):
                self.assertIn(anchor, guidance, f"manual guidance lost: {label}")

        # The automated-driver section keeps the boundary specification-only
        # and runner-neutral (a conforming external runner may exist, but the
        # template ships none and depends on none), binds the five accepted
        # outcomes to the right behavior, and no longer offers a generic
        # "no frontier" as a sufficient stop or completion contract.
        driver = self._section_outside_fences(manual, "### Automated Driver Mode")
        self.assertTrue(driver.strip(), "manual has no automated-driver section")
        self.assertNotIn(
            "no frontier", driver.lower(),
            "the generic no-frontier stop rule must be replaced by typed outcomes",
        )
        for state, behavior in (
            ("ready", "continue the declared loop"),
            ("needs_specification", "run one bounded architect planning turn"),
            ("blocked", "stop and report the cited block"),
            ("complete", "succeed only when explicit accepted completion evidence"),
            ("invalid", "stop fail-closed with diagnostics"),
        ):
            with self.subTest(outcome=state):
                bullet = next(
                    (b for b in self._bullets(driver) if b.startswith(f"`{state}`")), None
                )
                self.assertIsNotNone(bullet, f"manual omits the `{state}` outcome")
                self.assertIn(
                    behavior, bullet,
                    f"`{state}` is not bound to its accepted operator behavior",
                )
        for label, anchor in (
            ("specification-only", "specification-only and runner-neutral"),
            ("template ships no runner",
             "No runner ships with this template"),
            ("boundary conformance named",
             "any runner honoring the normative boundary"),
            ("empty frontier and retries", "never imply completion"),
            ("versioned state, not prose", "instead of parsing roadmap prose"),
            ("no fog graduation", "must not graduate `Not Yet Specified`"),
            ("no scope decision", "or decide project scope"),
            ("human gates intact", "human approval gates remain intact"),
            ("no commit or PR by default",
             "must not commit or open pull requests by default"),
            ("normative boundary link",
             "docs/template_framework/frutlups_driver_boundary.md"),
        ):
            with self.subTest(driver=label):
                self.assertIn(anchor, driver, f"automated-driver guidance lost: {label}")

        # The new guidance stays advisory: both surfaces state optionality, and
        # the runner-neutral section ships no runner commands — those live in
        # a runner's own operator manual, outside this template.
        self.assertIn("Neither is required", entry)
        self.assertIn("neither is required", guidance)
        self.assertNotIn(
            "```", driver, "the driver section must not ship runner commands"
        )

    def test_no_scaffold_test_requires_frutlups(self) -> None:
        """The suite must run without frutlups installed (downstream-safe)."""
        self._assert_no_test_imports("frutlups")

    def test_mode_values_are_controlled(self) -> None:
        """`Memory mode` and `Frutlups mode` must use controlled values.

        Asserts membership in the allowed set (not a fixed value), so a project
        that legitimately enables a lane still passes.
        """
        state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        memory = self._mode_value(state, "Memory mode")
        frutlups = self._mode_value(state, "Frutlups mode")
        self.assertIn(
            memory, {"none", "lightweight", "llloom"},
            f"Memory mode '{memory}' is not a controlled value",
        )
        self.assertIn(
            frutlups, {"manual", "semi-manual", "automated driver"},
            f"Frutlups mode '{frutlups}' is not a controlled value",
        )

    def test_optional_lane_pattern_linked(self) -> None:
        """The optional-lane pattern doc exists and is linked from both lanes."""
        framework = ROOT / "docs" / "template_framework"
        self.assertTrue(
            (framework / "optional_lanes.md").is_file(), "missing optional_lanes.md"
        )
        for lane in ("memory_modes.md", "frutlups_modes.md"):
            text = (framework / lane).read_text(encoding="utf-8")
            self.assertIn(
                "optional_lanes.md", text, f"{lane} does not link optional_lanes.md"
            )

    def test_project_profiles_doc_exists(self) -> None:
        self.assertTrue(
            (ROOT / "docs" / "template_framework" / "project_profiles.md").is_file(),
            "missing project_profiles.md",
        )

    def test_migration_guide_exists_and_linked(self) -> None:
        """The migration/adoption guide exists and is discoverable."""
        framework = ROOT / "docs" / "template_framework"
        self.assertTrue(
            (framework / "migration_and_adoption.md").is_file(),
            "missing migration_and_adoption.md",
        )
        linked = any(
            "migration_and_adoption.md"
            in (ROOT / surface).read_text(encoding="utf-8")
            for surface in ("README.md", "docs/template_framework/method.md")
        )
        self.assertTrue(
            linked, "migration guide not linked from README or method.md"
        )

    def test_migration_guide_is_additive_and_nondestructive(self) -> None:
        """The migration guide must keep adoption additive and non-destructive."""
        text = (
            ROOT / "docs" / "template_framework" / "migration_and_adoption.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("additive", text)
        self.assertIn("destructive prune", text)

    # ----- front-facing repo bootstrap and sync lane -----

    _FRONT = "scripts/front_repo_sync"

    def test_front_repo_sync_lane_exists(self) -> None:
        base = ROOT / "scripts" / "front_repo_sync"
        for name in (
            "_front_repo_common.py",
            "bootstrap_front_repo.py",
            "sync_front_repo.py",
            "front_repo_sync_manifest.example.toml",
            "front_repo_gitignore",
            "README.md",
        ):
            self.assertTrue((base / name).is_file(), f"missing {self._FRONT}/{name}")
        self.assertTrue(
            (ROOT / "docs" / "template_framework" / "front_repo_sync.md").is_file(),
            "missing front_repo_sync.md",
        )

    def test_front_repo_cli_flags_and_safety(self) -> None:
        base = ROOT / "scripts" / "front_repo_sync"
        sync = (base / "sync_front_repo.py").read_text(encoding="utf-8")
        for flag in ("--check", "--apply", "--target-repo", "--allow-dirty-target"):
            self.assertIn(flag, sync, f"sync script omits {flag}")
        boot = (base / "bootstrap_front_repo.py").read_text(encoding="utf-8")
        for flag in ("--check", "--apply", "--output-dir"):
            self.assertIn(flag, boot, f"bootstrap script omits {flag}")
        # Bootstrap must not be able to run git (no subprocess import).
        self.assertNotIn("import subprocess", boot,
                         "bootstrap must not run git/subprocess")
        # The separation guard is the load-bearing no-nested-repo rule.
        common = (base / "_front_repo_common.py").read_text(encoding="utf-8")
        self.assertIn("validate_separation", common)
        self.assertIn("nested", common)

    def test_front_repo_manifest_is_portable(self) -> None:
        text = (
            ROOT / "scripts" / "front_repo_sync"
            / "front_repo_sync_manifest.example.toml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("C:" + "\\", text, "example manifest must not hardcode a machine-local path")

    def test_front_repo_docs_forbid_nested_repos(self) -> None:
        text = (
            ROOT / "docs" / "template_framework" / "front_repo_sync.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("nested", text)
        self.assertIn("separate", text)

    def _front_repo_modules(self):
        import importlib
        scripts_dir = ROOT / "scripts" / "front_repo_sync"
        import sys
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        return (
            importlib.import_module("bootstrap_front_repo"),
            importlib.import_module("sync_front_repo"),
        )

    @staticmethod
    def _tiny_dev_and_manifest(dev: Path) -> Path:
        (dev / "pkg").mkdir(parents=True, exist_ok=True)
        (dev / "pkg" / "a.py").write_text("x\n", encoding="utf-8")
        (dev / "pkg" / "README.md").write_text("# r\n", encoding="utf-8")
        manifest = dev / "m.toml"
        manifest.write_text(
            '[settings]\ndefault_target = ""\ndefault_bootstrap_output = ""\n'
            '[ignore]\nnames = []\nsuffixes = []\nglobs = []\n'
            '[[files]]\nsource = "pkg/README.md"\ntarget = "README.md"\n'
            '[[directories]]\nsource = "pkg"\ntarget = "src"\n',
            encoding="utf-8",
        )
        return manifest

    def test_bootstrap_functional(self) -> None:
        import io, contextlib, tempfile
        boot, _ = self._front_repo_modules()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dev, out = tmp / "dev", tmp / "out"
            manifest = self._tiny_dev_and_manifest(dev)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc_check = boot.main(["--check", "--output-dir", str(out),
                                      "--manifest", str(manifest), "--dev-root", str(dev)])
                rc_apply = boot.main(["--apply", "--output-dir", str(out),
                                      "--manifest", str(manifest), "--dev-root", str(dev)])
            self.assertEqual(rc_check, 0)
            self.assertFalse(out.exists() and any(out.iterdir()) and rc_check != 0)
            self.assertEqual(rc_apply, 0)
            self.assertTrue((out / "README.md").is_file())
            self.assertTrue((out / "src" / "a.py").is_file())
            self.assertFalse((out / ".git").exists(), "bootstrap must not create .git")
            # Refuses an output dir nested inside the dev repo.
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    boot.main(["--check", "--output-dir", str(dev / "nested"),
                               "--manifest", str(manifest), "--dev-root", str(dev)])

    def test_sync_functional(self) -> None:
        import io, contextlib, tempfile
        _, sync = self._front_repo_modules()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dev, tgt = tmp / "dev", tmp / "tgt"
            manifest = self._tiny_dev_and_manifest(dev)
            (tgt / ".git").mkdir(parents=True)  # fake repo marker; no real git needed
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc_check = sync.main(["--check", "--target-repo", str(tgt),
                                      "--manifest", str(manifest), "--dev-root", str(dev)])
                rc_apply = sync.main(["--apply", "--target-repo", str(tgt), "--allow-dirty-target",
                                      "--manifest", str(manifest), "--dev-root", str(dev)])
            self.assertEqual(rc_check, 0)
            self.assertEqual(rc_apply, 0)
            self.assertTrue((tgt / "README.md").is_file())
            self.assertTrue((tgt / "src" / "a.py").is_file())
            # Missing source -> nonzero exit.
            bad = dev / "bad.toml"
            bad.write_text(
                '[settings]\ndefault_target = ""\ndefault_bootstrap_output = ""\n'
                '[ignore]\nnames = []\nsuffixes = []\nglobs = []\n'
                '[[files]]\nsource = "pkg/NOPE.md"\ntarget = "NOPE.md"\n',
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                rc_missing = sync.main(["--check", "--target-repo", str(tgt),
                                        "--manifest", str(bad), "--dev-root", str(dev)])
            self.assertEqual(rc_missing, 2)
            # Refuses a target nested inside the dev repo.
            (dev / "innerrepo" / ".git").mkdir(parents=True)
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    sync.main(["--check", "--target-repo", str(dev / "innerrepo"),
                               "--manifest", str(manifest), "--dev-root", str(dev)])

    def test_front_repo_source_and_target_containment(self) -> None:
        import io, contextlib, tempfile
        boot, sync = self._front_repo_modules()

        def quiet():
            return contextlib.redirect_stdout(io.StringIO())

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dev, out, tgt = tmp / "dev", tmp / "out", tmp / "tgt"
            (dev / "pkg").mkdir(parents=True)
            (dev / "pkg" / "README.md").write_text("# r\n", encoding="utf-8")
            (tmp / "secret.txt").write_text("SECRET\n", encoding="utf-8")
            (tgt / ".git").mkdir(parents=True)
            head = (
                '[settings]\ndefault_target = ""\ndefault_bootstrap_output = ""\n'
                '[ignore]\nnames = []\nsuffixes = []\nglobs = []\n'
            )

            def manifest(name: str, body: str) -> Path:
                p = dev / name
                p.write_text(head + body, encoding="utf-8")
                return p

            file_escape = manifest("file_escape.toml", '[[files]]\nsource = "../secret.txt"\ntarget = "leak.txt"\n')
            dir_escape = manifest("dir_escape.toml", '[[directories]]\nsource = ".."\ntarget = "x"\n')
            target_escape = manifest("target_escape.toml", '[[files]]\nsource = "pkg/README.md"\ntarget = "../escape.txt"\n')
            missing_inside = manifest("missing.toml", '[[files]]\nsource = "pkg/NOPE.md"\ntarget = "NOPE.md"\n')

            def boot_check(m: Path) -> int:
                return boot.main(["--check", "--manifest", str(m), "--dev-root", str(dev), "--output-dir", str(out)])

            def sync_check(m: Path) -> int:
                return sync.main(["--check", "--manifest", str(m), "--dev-root", str(dev), "--target-repo", str(tgt)])

            # A file source outside dev_root is rejected by BOTH tools.
            for fn in (boot_check, sync_check):
                with quiet(), self.assertRaises(SystemExit):
                    fn(file_escape)
            # A directory source outside dev_root is rejected.
            with quiet(), self.assertRaises(SystemExit):
                boot_check(dir_escape)
            # Target traversal is still rejected by destination containment.
            with quiet(), self.assertRaises(SystemExit):
                boot_check(target_escape)
            # No outside file leaked into the destination or beyond it.
            self.assertFalse((out / "leak.txt").exists())
            self.assertFalse((tgt / "leak.txt").exists())
            self.assertFalse((tmp / "escape.txt").exists())
            # A missing source INSIDE dev_root is NOT a containment error: still 2.
            with quiet():
                self.assertEqual(boot_check(missing_inside), 2)

    def _front_repo_core(self):
        import importlib, sys
        scripts_dir = ROOT / "scripts" / "front_repo_sync"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        return importlib.import_module("_front_repo_common")

    def test_front_repo_rejects_symlinked_source_live(self) -> None:
        """If symlink creation is available, a symlink inside a mirrored source
        directory pointing outside dev_root is rejected and nothing is written."""
        import io, contextlib, tempfile
        boot, _ = self._front_repo_modules()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dev, out = tmp / "dev", tmp / "out"
            (dev / "pkg").mkdir(parents=True)
            (dev / "pkg" / "ok.py").write_text("x\n", encoding="utf-8")
            secret = tmp / "secret.txt"
            secret.write_text("SECRET\n", encoding="utf-8")
            try:
                (dev / "pkg" / "link.txt").symlink_to(secret)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation not available (privilege/platform)")
            manifest = dev / "m.toml"
            manifest.write_text(
                '[settings]\ndefault_target = ""\ndefault_bootstrap_output = ""\n'
                '[ignore]\nnames = []\nsuffixes = []\nglobs = []\n'
                '[[directories]]\nsource = "pkg"\ntarget = "src"\n',
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                boot.main(["--check", "--manifest", str(manifest),
                           "--dev-root", str(dev), "--output-dir", str(out)])
            self.assertFalse((out / "src" / "link.txt").exists())
            self.assertFalse(out.exists() and any(out.iterdir()))

    def test_front_repo_symlink_rejection_branches(self) -> None:
        """OS-independent coverage of the symlink-rejection branches: force
        is_symlink() True for a file and for a subdir and confirm each is
        rejected during the source walk (no real symlink privilege needed)."""
        import tempfile
        from unittest import mock
        core = self._front_repo_core()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dev = tmp / "dev"
            (dev / "pkg" / "sub").mkdir(parents=True)
            (dev / "pkg" / "a.py").write_text("x\n", encoding="utf-8")
            (dev / "pkg" / "sub" / "inner.py").write_text("y\n", encoding="utf-8")
            real = Path.is_symlink

            def fake_file(self):
                return self.name == "a.py" or real(self)

            def fake_dir(self):
                return self.name == "sub" or real(self)

            with mock.patch.object(Path, "is_symlink", fake_file):
                with self.assertRaises(SystemExit):
                    core.iter_source_files(dev / "pkg", core.IgnoreRules(), dev)
            with mock.patch.object(Path, "is_symlink", fake_dir):
                with self.assertRaises(SystemExit):
                    core.iter_source_files(dev / "pkg", core.IgnoreRules(), dev)
            # Without any (faked) symlink, a normal walk yields the regular files.
            files = core.iter_source_files(dev / "pkg", core.IgnoreRules(), dev)
            names = sorted(p.name for p in files)
            self.assertEqual(names, ["a.py", "inner.py"])

    # ----- local-state audit and cleanup lane -----

    def _local_state_modules(self):
        import importlib, sys
        scripts_dir = ROOT / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        return (
            importlib.import_module("local_state_audit"),
            importlib.import_module("local_cleanup"),
        )

    @staticmethod
    def _seed_local_tree(root: Path) -> None:
        """A tree with rebuildable residue at safe locations AND protected paths
        (workspaces, venv, .git, a nested repo) whose contents must survive."""
        def w(p: Path, text: str = "x\n") -> None:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

        # rebuildable residue that --apply should remove
        w(root / "pkg" / "__pycache__" / "m.cpython-3.pyc")
        w(root / ".pytest_cache" / "v.json", "{}\n")
        w(root / "build" / "out.o")
        w(root / "pkg.egg-info" / "PKG-INFO")
        w(root / ".coverage")
        # real source that must be preserved
        w(root / "pkg" / "real.py", "print(1)\n")
        # protected paths: contents (including caches inside them) must survive
        w(root / ".git" / "HEAD", "ref: refs/heads/main\n")
        w(root / ".venv" / "Lib" / "site.py")
        w(root / ".venv" / "__pycache__" / "c.pyc")
        w(root / "01_data" / "raw.csv", "a,b\n")
        w(root / "05_governance" / "__pycache__" / "g.pyc")
        # a nested repo (its own .git) and a cache inside it must survive
        w(root / "vendor" / ".git" / "HEAD", "ref: refs/heads/main\n")
        w(root / "vendor" / "__pycache__" / "n.pyc")

    def test_local_state_scripts_exist(self) -> None:
        base = ROOT / "scripts"
        for name in ("local_state_audit.py", "local_cleanup.py", "_local_state_common.py"):
            self.assertTrue((base / name).is_file(), f"missing scripts/{name}")

    def test_local_cleanup_dry_run_by_default(self) -> None:
        import io, contextlib, tempfile
        _, cleanup = self._local_state_modules()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            self._seed_local_tree(root)
            before = sorted(str(p) for p in root.rglob("*"))
            # no mode flag, then explicit --check: both must delete nothing
            for argv in (["--root", str(root)], ["--check", "--root", str(root)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(cleanup.main(argv), 0)
            after = sorted(str(p) for p in root.rglob("*"))
            self.assertEqual(before, after, "dry-run cleanup deleted something")

    def test_local_cleanup_apply_removes_only_rebuildable(self) -> None:
        import io, contextlib, tempfile
        _, cleanup = self._local_state_modules()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            self._seed_local_tree(root)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cleanup.main(["--apply", "--root", str(root)]), 0)
            # rebuildable residue at safe locations is gone
            for gone in (
                root / "pkg" / "__pycache__", root / ".pytest_cache",
                root / "build", root / "pkg.egg-info", root / ".coverage",
            ):
                self.assertFalse(gone.exists(), f"should have removed {gone}")
            # real source preserved
            self.assertTrue((root / "pkg" / "real.py").is_file())
            # protected paths preserved, INCLUDING caches nested inside them
            for keep in (
                root / ".git" / "HEAD",
                root / ".venv" / "Lib" / "site.py",
                root / ".venv" / "__pycache__" / "c.pyc",
                root / "01_data" / "raw.csv",
                root / "05_governance" / "__pycache__" / "g.pyc",
                root / "vendor" / ".git" / "HEAD",
                root / "vendor" / "__pycache__" / "n.pyc",
            ):
                self.assertTrue(keep.is_file(), f"must have preserved {keep}")

    def test_local_cleanup_never_escapes_root(self) -> None:
        import io, contextlib, tempfile
        _, cleanup = self._local_state_modules()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "proj"
            root.mkdir()
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "a.pyc").write_text("x\n", encoding="utf-8")
            outside = tmp / "__pycache__"
            outside.mkdir()
            (outside / "b.pyc").write_text("x\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                cleanup.main(["--apply", "--root", str(root)])
            self.assertFalse((root / "__pycache__").exists())
            self.assertTrue(outside.exists(), "cleanup escaped --root")

    def test_local_cleanup_skips_symlinked_candidate(self) -> None:
        import io, contextlib, tempfile
        _, cleanup = self._local_state_modules()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "proj"
            root.mkdir()
            external = tmp / "real_cache"
            external.mkdir()
            (external / "keep.pyc").write_text("x\n", encoding="utf-8")
            try:
                (root / "__pycache__").symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation not available (privilege/platform)")
            with contextlib.redirect_stdout(io.StringIO()):
                cleanup.main(["--apply", "--root", str(root)])
            # the symlink target (outside root) is untouched
            self.assertTrue((external / "keep.pyc").is_file())

    def test_local_cleanup_guard_rejects_symlink_before_resolve(self) -> None:
        """The final deletion guard must check the ORIGINAL candidate for symlink
        status before `resolve()`. Resolving first follows the link to its target,
        which never reports as a symlink, so resolving-then-checking silently
        defeats the guard.

        Privilege-independent: this forces ``is_symlink()`` to report True only for
        the original candidate object. ``resolve()`` returns a different Path
        instance, so a resolve-first implementation checks the wrong object and
        wrongly returns True (the assertion then fails); the fixed guard checks the
        original object first and returns False.
        """
        import tempfile
        from unittest import mock
        _, cleanup = self._local_state_modules()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            cand = root / "__pycache__"
            cand.mkdir(parents=True)
            (cand / "m.pyc").write_text("x\n", encoding="utf-8")
            real_is_symlink = Path.is_symlink

            def fake(self):
                return self is cand or real_is_symlink(self)

            with mock.patch.object(Path, "is_symlink", fake):
                self.assertFalse(
                    cleanup._safe_to_delete(cand, root),
                    "guard must reject a symlink candidate before resolving it",
                )

    def test_local_state_audit_is_read_only_and_flags(self) -> None:
        import io, contextlib, tempfile
        audit, _ = self._local_state_modules()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            self._seed_local_tree(root)
            before = {
                str(p): (p.stat().st_size if p.is_file() else None)
                for p in root.rglob("*")
            }
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(audit.main(["--root", str(root)]), 0)
            after = {
                str(p): (p.stat().st_size if p.is_file() else None)
                for p in root.rglob("*")
            }
            self.assertEqual(before, after, "audit modified the tree (must be read-only)")
            out = buf.getvalue().lower()
            self.assertIn(".venv", out, "audit did not flag the virtual environment")
            self.assertIn("read-only", out, "audit omitted its read-only banner")

    # ----- artifact-integrity preflight and process safeguards -----

    def _artifact_preflight_module(self):
        import importlib, sys
        scripts_dir = ROOT / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        return importlib.import_module("artifact_integrity_preflight")

    def test_ignore_boundary_helper_honors_directory_rules(self) -> None:
        """Broad scans must skip explicit local-only directory rules (e.g.
        ``.local/`` bootstrap evidence) while keeping template files in scope."""
        self.assertTrue(self._is_ignored_local_path(ROOT / ".local" / "paths.md"))
        self.assertTrue(self._is_ignored_local_path(ROOT / "local_state" / "x.md"))
        self.assertFalse(self._is_ignored_local_path(ROOT / "CLAUDE.md"))
        self.assertFalse(
            self._is_ignored_local_path(ROOT / "prompts" / "templates" / "coding_prompt.md")
        )

    def test_artifact_preflight_is_targeted_read_only_and_detects_errors(self) -> None:
        import contextlib, io, tempfile

        preflight = self._artifact_preflight_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "test_sample.py").write_text(
                "def test_real_name():\n    pass\n", encoding="utf-8"
            )
            (root / "reference_tests").mkdir()
            (root / "reference_tests" / "test_external.py").write_text(
                "def test_external_name():\n    pass\n", encoding="utf-8"
            )
            good = root / "good.md"
            good.write_text(
                "# Good\n\nSee `tests/test_sample.py` and `test_real_name`.\n",
                encoding="utf-8",
            )
            good_two = root / "good_two.md"
            good_two.write_text(
                "# Good Two\n\nAlso `tests/test_sample.py`.\n", encoding="utf-8"
            )
            bad = root / "bad.md"
            bad.write_text(
                "# Bad\n\nSee `tests/missing.py` and `test_missing_name`.\n",
                encoding="utf-8",
            )
            external = root / "external.md"
            external.write_text("# External\n\nSee `test_external_name`.\n", encoding="utf-8")
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with contextlib.redirect_stdout(io.StringIO()):
                # Multiple explicit artifacts in one call, all clean -> exit 0.
                self.assertEqual(
                    preflight.main(["--root", str(root), "good.md", "good_two.md"]), 0
                )
                # A missing cited repository path and a nonexistent test id are hard errors.
                self.assertEqual(preflight.main(["--root", str(root), "bad.md"]), 1)
                # A cited identifier resolved against a supplied non-default test root passes.
                self.assertEqual(
                    preflight.main(
                        ["--root", str(root), "--tests-root", "reference_tests", "external.md"]
                    ),
                    0,
                )
                # Allowing one planned path must not hide the bad test identifier.
                self.assertEqual(
                    preflight.main(
                        ["--root", str(root), "--allow-missing", "tests/missing.py", "bad.md"]
                    ),
                    1,
                )
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after, "artifact preflight modified its input tree")

    def test_artifact_preflight_allows_explicit_future_path(self) -> None:
        """A missing cited path under an existing root dir is a hard error unless
        it is explicitly allowed as a planned artifact, which downgrades it to an
        advisory warning."""
        import contextlib, io, tempfile

        preflight = self._artifact_preflight_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            planned = root / "planned.md"
            planned.write_text("# Planned\n\nFuture `tests/future_report.md`.\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(preflight.main(["--root", str(root), "planned.md"]), 1)
                self.assertEqual(
                    preflight.main(
                        ["--root", str(root), "--allow-missing", "tests/future_report.md", "planned.md"]
                    ),
                    0,
                )
            self.assertIn("WARNING planned_path", out.getvalue())

    def test_artifact_preflight_historical_and_volatile_are_advisory(self) -> None:
        """Historical identifiers and volatile-language phrases warn but do not
        force a hard-failure exit on their own."""
        import contextlib, io, tempfile

        preflight = self._artifact_preflight_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            note = root / "history.md"
            note.write_text(
                "# History\n\nHistorical finding: removed nonexistent `test_old_name`.\n",
                encoding="utf-8",
            )
            volatile = root / "volatile.md"
            volatile.write_text("# V\n\nThe active prompt is `001`.\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(preflight.main(["--root", str(root), "history.md"]), 0)
                self.assertEqual(
                    preflight.main(["--root", str(root), "--check-volatile", "volatile.md"]), 0
                )
            printed = out.getvalue()
            self.assertIn("WARNING test_identifier", printed)
            self.assertIn("WARNING volatile_state", printed)

    def test_artifact_preflight_handles_windows_and_posix_citations(self) -> None:
        """Repository-relative citations must be handled safely in both POSIX and
        Windows separator forms, independent of the host platform."""
        import contextlib, io, tempfile

        preflight = self._artifact_preflight_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "test_sample.py").write_text("def test_real():\n    pass\n", encoding="utf-8")
            both = root / "both.md"
            both.write_text(
                "# Both\n\nPOSIX `tests/test_sample.py` and Windows `tests\\test_sample.py`.\n",
                encoding="utf-8",
            )
            missing_win = root / "missing_win.md"
            missing_win.write_text("# Missing\n\nWindows `tests\\gone.py`.\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(preflight.main(["--root", str(root), "both.md"]), 0)
                self.assertEqual(preflight.main(["--root", str(root), "missing_win.md"]), 1)

    def test_artifact_preflight_json_output_is_deterministic(self) -> None:
        """Structured output is stable byte-for-byte across identical runs so it
        can feed later automation without becoming a live-state source."""
        import contextlib, io, tempfile

        preflight = self._artifact_preflight_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            bad = root / "bad.md"
            bad.write_text("# Bad\n\nSee `tests/missing.py` and `test_absent`.\n", encoding="utf-8")

            def run() -> str:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    preflight.main(["--root", str(root), "--json", "bad.md"])
                return buf.getvalue()

            self.assertEqual(run(), run())

    def test_artifact_preflight_distinguishes_illustrative_planned_and_broken_paths(self) -> None:
        """Three-way M009 contract: `example://...` is illustrative notation and
        never a citation; a real planned repository path stays a visible warning
        under `--allow-missing`; broken repository citations and machine-local
        absolute paths remain hard errors."""
        import contextlib, io, tempfile

        preflight = self._artifact_preflight_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "illustrative.md").write_text(
                "# I\n\nPreview lands at `example://temp/report.html`.\n",
                encoding="utf-8",
            )
            (root / "planned.md").write_text(
                "# P\n\nFuture `tests/planned_report.md`.\n", encoding="utf-8"
            )
            (root / "broken.md").write_text(
                "# B\n\nSee `tests/does_not_exist.md`.\n", encoding="utf-8"
            )
            (root / "machine.md").write_text(
                "# M\n\nSee `C:\\Users\\someone\\report.md`.\n", encoding="utf-8"
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    preflight.main(["--root", str(root), "illustrative.md"]), 0
                )
                self.assertEqual(
                    preflight.main(
                        [
                            "--root",
                            str(root),
                            "--allow-missing",
                            "tests/planned_report.md",
                            "planned.md",
                        ]
                    ),
                    0,
                )
                self.assertEqual(preflight.main(["--root", str(root), "broken.md"]), 1)
                self.assertEqual(preflight.main(["--root", str(root), "machine.md"]), 1)
            printed = out.getvalue()
            self.assertNotIn(
                "illustrative.md:",
                printed,
                "illustrative example:// notation must produce no finding",
            )
            self.assertIn("WARNING planned_path", printed)
            self.assertIn("ERROR repository_path", printed)
            self.assertIn("ERROR machine_path", printed)

    def test_closure_routing_ownership_is_single_sourced_and_review_log_pointer_only(self) -> None:
        """The canonical method owns one closure ownership/cadence contract; the
        review log is a pointer-only compatibility surface that does not invite
        duplicate routine rows (M009). No volatile row counts are frozen."""
        method = (ROOT / "docs" / "template_framework" / "method.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("### Closure Routing Ownership And Cadence", method)
        for surface in (
            "`PROJECT_STATE.md`",
            "`prompts/INDEX.md`",
            "`05_governance/reviews/INDEX.md`",
            "`MILESTONES.md`",
            "`05_governance/review_log.md`",
        ):
            self.assertIn(surface, method)
        self.assertIn("not for every slice transition", method)
        log = (ROOT / "05_governance" / "review_log.md").read_text(encoding="utf-8")
        self.assertIn("reviews/INDEX.md", log)
        self.assertIn("pointer-only", log.lower())
        self.assertNotIn(
            "| Date |", log, "review log must not carry a routine-entry table"
        )

    def test_fresh_context_guidance_is_optional_and_handoff_bounded(self) -> None:
        """Fresh agent contexts are documented as an optional, controller/human-
        owned choice available only at durable artifact handoffs; the guidance
        adds no required project-state field and keeps persistent contexts valid
        (M009)."""
        manual = (
            ROOT / "docs" / "template_framework" / "human_user_manual.md"
        ).read_text(encoding="utf-8")
        heading = "### Optional Fresh Contexts At Durable Handoffs"
        self.assertIn(heading, manual)
        section = manual.split(heading, 1)[1].split("\n## ", 1)[0]
        self.assertIn("optional, controller/human-owned", section)
        self.assertIn("Persistent contexts remain fully valid", section)
        self.assertIn("accepted milestone closure", section)
        self.assertIn("complete artifact handoff", section)
        self.assertIn("Never refresh midway", section)
        contract = (
            ROOT / "docs" / "template_framework" / "project_state_contract.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "fresh context",
            contract.lower(),
            "fresh-context guidance must not add a project-state field",
        )

    def test_artifact_preflight_enforces_containment_and_machine_paths(self) -> None:
        """Repository escapes, machine-absolute paths, and unambiguous missing
        top-level paths are hard errors; a safe missing future path is downgraded
        only via a contained ``--allow-missing`` value. The input tree is never
        modified and JSON output stays deterministic."""
        import contextlib, io, tempfile

        preflight = self._artifact_preflight_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "proj"
            (root / "tests").mkdir(parents=True)
            (root / "tests" / "test_sample.py").write_text(
                "def test_real():\n    pass\n", encoding="utf-8"
            )
            # A real file OUTSIDE the repository root, used for escape cases.
            (tmp / "secret.md").write_text("SECRET\n", encoding="utf-8")

            def write(name: str, body: str) -> str:
                (root / name).write_text(body, encoding="utf-8")
                return name

            bt_escape = write("bt_escape.md", "# x\n\nSee `../secret.md`.\n")
            link_escape = write("link_escape.md", "# x\n\nSee [s](../secret.md).\n")
            missing_top = write("missing_top.md", "# x\n\nSee `absent_root/file.md`.\n")
            drive_bslash = write("drive_bslash.md", "# x\n\nSee `C:\\Windows\\a.md`.\n")
            drive_fslash = write("drive_fslash.md", "# x\n\nSee `C:/Windows/a.md`.\n")
            unc = write("unc.md", "# x\n\nSee `\\\\server\\share\\a.md`.\n")
            future = write("future.md", "# x\n\nFuture `future_dir/report.md`.\n")
            both = write(
                "both.md",
                "# x\n\n`tests/test_sample.py` and Windows `tests\\test_sample.py`.\n",
            )
            prose = write("prose.md", "# x\n\nThe `data/analysis/delivery` split.\n")

            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with contextlib.redirect_stdout(io.StringIO()):
                r = lambda *a: preflight.main(["--root", str(root), *a])
                # Repository escapes are hard errors for both citation forms,
                # even though the target exists outside the root.
                self.assertEqual(r(bt_escape), 1)
                self.assertEqual(r(link_escape), 1)
                # An unambiguous path-shaped citation with a missing top-level dir.
                self.assertEqual(r(missing_top), 1)
                # Machine-absolute forms: Windows drive (either separator) and UNC.
                self.assertEqual(r(drive_bslash), 1)
                self.assertEqual(r(drive_fslash), 1)
                self.assertEqual(r(unc), 1)
                # A missing future path is an error unless explicitly (and safely)
                # allowed; an escaping allow-missing value must not authorize it.
                self.assertEqual(r(future), 1)
                self.assertEqual(r("--allow-missing", "future_dir/report.md", future), 0)
                self.assertEqual(r("--allow-missing", "../secret.md", bt_escape), 1)
                self.assertEqual(r("--allow-missing", "C:\\x\\y.md", missing_top), 1)
                # Existing repository-relative citations pass in both separator forms;
                # slash-separated prose is not treated as a path.
                self.assertEqual(r(both), 0)
                self.assertEqual(r(prose), 0)

                def as_json() -> str:
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        preflight.main(["--root", str(root), "--json", missing_top])
                    return buf.getvalue()

                self.assertEqual(as_json(), as_json())
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after, "preflight modified its input tree")

    def test_template_documents_live_state_and_fast_close_safeguards(self) -> None:
        """The three safeguards must be coherently present in reusable contracts:
        stable-reference (volatile) language, the preflight, and proportional,
        exclusion-bound fast-close."""
        state_contract = (
            ROOT / "docs" / "template_framework" / "project_state_contract.md"
        ).read_text(encoding="utf-8")
        review_protocol = (
            ROOT / "05_governance" / "current" / "review_protocol.md"
        ).read_text(encoding="utf-8")
        strictness = (
            ROOT / "docs" / "template_framework" / "review_strictness_levels.md"
        ).read_text(encoding="utf-8")
        fast_close = (
            ROOT / "prompts" / "templates" / "fast_close_correction.md"
        ).read_text(encoding="utf-8")
        script_docs = (ROOT / "scripts" / "README.md").read_text(encoding="utf-8")

        self.assertIn("volatile", state_contract.lower())
        self.assertIn("artifact_integrity_preflight.py", script_docs)
        self.assertTrue((ROOT / "scripts" / "artifact_integrity_preflight.py").is_file())

        # Fast-close stays proportional and append-only without spawning a new loop.
        self.assertIn("Do not create a new full coding prompt", review_protocol)
        self.assertIn("If eligibility is uncertain, use Level 2.", review_protocol)
        self.assertIn("append-only", strictness.lower())
        # The complete fast-close exclusion set must be explicit and consistent on
        # BOTH canonical surfaces: the review protocol and the correction template.
        required_exclusions = (
            "behavior",
            "generated-output",
            "public contract",
            "api",
            "schema",
            "dependenc",
            "credential",
            "secret",
            "cost",
            "cloud",
            "security",
            "privacy",
            "data-handling",
            "substantive",
            "uncertain",
        )
        for surface_name, surface in (
            ("review protocol", review_protocol.lower()),
            ("fast-close template", fast_close.lower()),
        ):
            for excluded in required_exclusions:
                self.assertIn(
                    excluded, surface, f"{surface_name} omits '{excluded}' exclusion"
                )

    def test_default_surfaces_carry_stable_reference_guidance(self) -> None:
        """Canonical guidance and the default coding/self-report/review surfaces
        must direct authors to link volatile live state and run the preflight,
        rather than duplicating changing values."""
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8").lower()
        self.assertIn("volatile", claude)
        self.assertIn("preflight", claude)

        coding_prompt = (
            ROOT / "prompts" / "templates" / "coding_prompt.md"
        ).read_text(encoding="utf-8")
        self.assertIn("volatile", coding_prompt.lower())
        self.assertIn("artifact_integrity_preflight.py", coding_prompt)

        self_report = (
            ROOT / "prompts" / "templates" / "self_report.md"
        ).read_text(encoding="utf-8")
        self.assertIn("continuing truth", self_report)
        self.assertIn("PROJECT_STATE.md", self_report)

        review_prompt = (
            ROOT / "prompts" / "templates" / "review_prompt.md"
        ).read_text(encoding="utf-8")
        self.assertIn("artifact_integrity_preflight.py", review_prompt)

        style_guide = (
            ROOT / "docs" / "template_framework" / "prompt_style_guide.md"
        ).read_text(encoding="utf-8")
        self.assertIn("volatile", style_guide.lower())

    def test_workspace_contexts_mark_status(self) -> None:
        for context in ROOT.glob("**/CONTEXT.md"):
            if self._is_ignored_local_path(context):
                continue
            text = context.read_text(encoding="utf-8").lower()
            self.assertIn("status:", text, f"{context} has no status marker")
            # Activation must be explicit: every workspace is either active or
            # inactive, never ambiguous.
            self.assertTrue(
                "status: active" in text or "status: inactive" in text,
                f"{context} status is neither active nor inactive",
            )

    def test_standalone_gitattributes_enforces_binary_safe_lf(self) -> None:
        # When this template becomes the root of its own Git repository, its .gitattributes
        # must enforce a binary-safe LF checkout for the whole tree so the release bytes are
        # deterministic regardless of the checkout machine's core.autocrlf.
        ga = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        lines = [l.strip() for l in ga.splitlines()]
        self.assertIn("* text=auto eol=lf", lines,
                      "standalone template must carry a binary-safe blanket LF rule")
        # `text=auto` (not unconditional `text`) so a future binary asset is not corrupted.
        self.assertNotIn("* text eol=lf", lines)
        # No shipped distributable UTF-8 text file carries CRLF. Release-ignored metadata
        # (e.g. an editable-install `*.egg-info/`) and binary payloads are not scanned.
        crlf = _distributable_text_crlf(ROOT, _template_owned_paths(ROOT))
        self.assertEqual(crlf, [], f"template-owned text files contain CRLF: {crlf[:3]}")

    def test_release_ignore_excludes_editable_install_egg_info(self) -> None:
        # An ignored editable-install `.egg-info/PKG-INFO` with CRLF must not be scanned.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            egg = root / "artifact_first_project_template.egg-info"
            egg.mkdir()
            (egg / "PKG-INFO").write_bytes(b"Metadata-Version: 2.1\r\nName: x\r\n")
            self.assertEqual(_distributable_text_crlf(root), [])

    def test_binary_payload_with_crlf_is_not_distributable_text(self) -> None:
        # A non-ignored binary payload containing a NUL and CRLF is not text -> excluded.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "asset.bin").write_bytes(b"\x89PNG\x00\r\n\x1a\n\x00\xff")
            self.assertEqual(_distributable_text_crlf(root), [])

    def test_distributable_utf8_text_crlf_is_caught(self) -> None:
        # Load-bearing negative: a real shipped UTF-8 text file with CRLF is reported and
        # makes the guard's assertion fail.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.md").write_bytes(b"# Title\r\nBody line.\r\n")
            self.assertEqual(_distributable_text_crlf(root), ["note.md"])

    def test_release_glob_families_exclude_dir_and_file_forms(self) -> None:
        # The two trailing-asterisk projection globs (.codex_tmp*, test-results*) exclude
        # both directory and filename forms, in every path position; a nearby non-matching
        # UTF-8 CRLF path is still detected, so the predicate is not overbroad and the
        # scanner cannot pass by returning an empty list.
        cases = {
            ".codex_tmp-review/trace.txt": True,     # .codex_tmp* directory form
            ".codex_tmp_probe.md": True,             # .codex_tmp* filename form
            "test-results-review/result.txt": True,  # test-results* directory form
            "test-results.json": True,               # test-results* filename (glob, not .xml)
            "kept/ordinary.md": False,               # nearby non-match: still an offender
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relpath in cases:
                p = root / relpath
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"line one\r\nline two\r\n")
            offenders = set(_distributable_text_crlf(root))
            for relpath, ignored in cases.items():
                with self.subTest(path=relpath):
                    if ignored:
                        self.assertNotIn(relpath, offenders, f"{relpath} must be release-ignored")
                    else:
                        self.assertIn(relpath, offenders, f"{relpath} must be a detected offender")
            self.assertEqual(offenders, {"kept/ordinary.md"})

    def test_predicate_equals_fnmatch_engine_for_all_five_globs(self) -> None:
        # For every declared manifest glob family — including lower-case, case-variant, and
        # near-miss basenames — the predicate must equal the operative fnmatch.fnmatch
        # result on the current platform (case-insensitive on Windows, case-sensitive
        # elsewhere), so the guard tracks the release engine exactly and portably.
        names = [
            ".codex_tmp_run", ".CODEX_TMP_run", "codex_tmp_run",   # .codex_tmp* + near miss
            "test-results-x", "TEST-RESULTS-X", "test-result",     # test-results* + near miss
            "pkg.egg-info", "PKG.EGG-INFO", "egg-info",            # *.egg-info + near miss
            "run.log", "RUN.LOG", "log",                          # *.log + near miss
            ".coverage", ".COVERAGE", "coverage",                 # .coverage + near miss
            "ordinary.md",                                        # plain non-match
        ]
        for name in names:
            with self.subTest(name=name):
                engine = any(fnmatch.fnmatch(name, pat) for pat in _RELEASE_IGNORE_GLOBS)
                self.assertEqual(
                    _is_release_ignored(Path(name)), engine,
                    f"{name}: predicate must equal the fnmatch engine on this platform")

    def test_case_variant_glob_dirs_track_engine_in_crlf_scan(self) -> None:
        # A real CRLF scan over case-variant glob directory/file names follows the engine:
        # on a case-insensitive platform they are excluded; otherwise they remain offenders.
        # A nearby ordinary UTF-8 CRLF path is always an offender (load-bearing).
        variants = {
            ".CODEX_TMP-x/trace.txt": ".CODEX_TMP-x",
            "TEST-RESULTS-X/result.txt": "TEST-RESULTS-X",
            "PKG.EGG-INFO/meta.txt": "PKG.EGG-INFO",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in [*variants, "kept/ordinary.md"]:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"line one\r\nline two\r\n")
            offenders = set(_distributable_text_crlf(root))
            expected = {"kept/ordinary.md"}
            for rel, component in variants.items():
                if not any(fnmatch.fnmatch(component, pat) for pat in _RELEASE_IGNORE_GLOBS):
                    expected.add(rel)
            self.assertEqual(offenders, expected)


if __name__ == "__main__":
    unittest.main()
