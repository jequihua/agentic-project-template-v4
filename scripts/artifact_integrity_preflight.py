"""Read-only integrity preflight for explicitly named Markdown artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"`([^`\r\n]+)`")
TEST_RE = re.compile(r"\b(test_[A-Za-z0-9_]+)\b")
FRONTMATTER_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]+$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")
# Machine-absolute paths are rejected before any repository-relative check.
# Windows drive-absolute (either separator) and UNC (\\host\share) forms plus the
# common POSIX home roots are all treated as machine-local, not repository paths.
MACHINE_PATH_RES = (
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/][^\s`)<>|]*"),  # Windows drive-absolute
    re.compile(r"\\\\[^\s`)<>|]+"),                              # UNC \\host\share
    re.compile(r"(?:/Users/|/home/)[^\s`)<>|]*"),               # POSIX home roots
)
VOLATILE_RES = (
    re.compile(r"\bcurrent next move\b", re.IGNORECASE),
    re.compile(r"\bcurrently holds\b", re.IGNORECASE),
    re.compile(r"\bonly (?:a|[0-9]+) (?:row|rows|entry|entries)\b", re.IGNORECASE),
    re.compile(r"\b(?:active|latest) (?:review )?prompt (?:is )?`?0[0-9]{2}\b", re.IGNORECASE),
)
# Dispatch-readiness rules: a ready artifact (frontmatter status, or the workflow
# metadata block's status) may carry no unresolved sentinel and no residue of an
# optional section that should have been removed (slice prompt contract v1).
READY_SENTINELS = ("TBD", "<value>", "<path>", "<one move>")
READY_RESIDUE_PHRASES = ("delete this section", "conditional: rendered only", "fills or deletes")
WORKFLOW_STATUS_RE = re.compile(r"^status:(.*)$")
STATUS_WORD_RE = re.compile(r"^(['\"]?)([A-Za-z_-]+)\1$")
TYPED_ENTRY_HEADING = "## Typed Entry"
HISTORICAL_WORDS = (
    "historical",
    "nonexistent",
    "removed",
    "replaced",
    "deleted",
    "old value",
    "no longer",
    "prior finding",
    "round-",
)


@dataclass(frozen=True)
class Finding:
    severity: str
    check_id: str
    artifact: str
    line: int
    evidence: str
    message: str


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _frontmatter(text: str) -> tuple[dict[str, str] | None, str | None]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "missing opening frontmatter delimiter"
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return None, "missing closing frontmatter delimiter"
    fields: dict[str, str] = {}
    for number, line in enumerate(lines[1:end], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = FRONTMATTER_FIELD_RE.match(line)
        if not match:
            return None, f"unsupported or malformed frontmatter at line {number}"
        fields[match.group(1)] = match.group(2).strip().strip('"\'')
    return fields, None


def _test_names(root: Path, supplied_roots: Sequence[str]) -> set[str]:
    names: set[str] = set()
    for supplied in supplied_roots or ("tests",):
        tests = (root / supplied).resolve()
        if not _within(tests, root) or not tests.is_dir():
            continue
        for path in tests.rglob("*.py"):
            try:
                names.update(TEST_RE.findall(path.read_text(encoding="utf-8")))
            except (OSError, UnicodeError):
                continue
    return names


def _normalize_citation(raw: str) -> str | None:
    """Reduce a link target or backticked token to a forward-slash path token.

    Returns ``None`` for empty tokens, URLs, anchors, and mail links. Backslashes
    are normalized to forward slashes so Windows and POSIX citations validate
    identically regardless of host platform.
    """
    raw = raw.strip()
    if not raw:
        return None
    raw = raw.split()[0].strip("<>").rstrip(".,;:")
    if not raw or "://" in raw or raw.startswith(("#", "mailto:")):
        return None
    raw = raw.split("#", 1)[0]
    return raw.replace("\\", "/") or None


def _is_machine_absolute(norm: str) -> bool:
    """True if a normalized citation is a machine-absolute (non-repository) path."""
    if norm.startswith("//"):  # UNC \\host\share after slash normalization
        return True
    if WINDOWS_DRIVE_RE.match(norm):  # Windows drive letter, e.g. C:/...
        return True
    return norm.startswith(("/Users/", "/home/"))


def _looks_like_path(norm: str, root: Path) -> bool:
    """Decide whether a backticked token is an unambiguous repository-path citation.

    A token counts as a path when it contains a separator and either its final
    component carries a file extension (for example ``outputs/report.md``) or its
    top-level component already exists in the repository. This flags a missing
    path whose top-level directory is absent while still ignoring slash-separated
    prose such as ``data/analysis/delivery`` whose components are ordinary words.
    """
    if "/" not in norm or any(mark in norm for mark in ("*", "{", "}", "…")):
        return False
    last = norm.rstrip("/").rsplit("/", 1)[-1]
    if EXTENSION_RE.search(last):
        return True
    first = norm.lstrip("/").split("/", 1)[0]
    return bool(first) and (root / first).exists()


def _path_finding(
    norm: str,
    *,
    root: Path,
    base: Path,
    rel: str,
    number: int,
    token: str,
    allowed_missing: set[str],
    context: str,
) -> Finding | None:
    """Validate one normalized path citation for containment and existence.

    Machine-absolute citations are left to the line-level machine-path scan.
    Repository escapes are hard errors regardless of existence; missing contained
    paths are hard errors unless explicitly allowed (warning) or in historical
    context (warning).
    """
    if _is_machine_absolute(norm):
        return None
    target = (root / norm.lstrip("/")) if norm.startswith("/") else (base / norm)
    try:
        resolved = target.resolve()
    except OSError:
        resolved = target
    root_resolved = root.resolve()
    if not _within(resolved, root_resolved):
        return Finding("error", "path_escape", rel, number, token, "cited path escapes the repository root")
    if resolved.exists():
        return None
    key = resolved.relative_to(root_resolved).as_posix()
    if key in allowed_missing:
        return Finding(
            "warning", "planned_path", rel, number, token,
            "missing path explicitly allowed as a planned artifact",
        )
    historical = any(word in context for word in HISTORICAL_WORDS)
    return Finding(
        "warning" if historical else "error", "repository_path", rel, number, token,
        "repository path does not exist" + (" (historical context)" if historical else ""),
    )


def _safe_allowed_missing(root: Path, values: Sequence[str]) -> set[str]:
    """Canonicalize ``--allow-missing`` values, dropping escapes and absolute paths.

    An allow-missing value may only downgrade a safe repository-relative future
    path; a repository escape or machine-absolute value is never authorized.
    """
    root_resolved = root.resolve()
    safe: set[str] = set()
    for value in values:
        norm = value.replace("\\", "/").strip().lstrip("/")
        if not norm or _is_machine_absolute(value.replace("\\", "/").strip()):
            continue
        try:
            resolved = (root / norm).resolve()
        except OSError:
            continue
        if _within(resolved, root_resolved):
            safe.add(resolved.relative_to(root_resolved).as_posix())
    return safe


# --- Optional framework-profile check (opt-in via --profile) ---
#
# All OKF/profile semantic parsing lives in the mandatory PyYAML adapter
# ``scripts/okf_yaml_profile.py``. It is imported lazily so the default
# (non-profile) path stays byte-identical and a missing dependency surfaces as a
# clean CLI error only when ``--profile`` is used. There is no custom-parser
# fallback.


class _MissingProfileDependency(Exception):
    """The declared PyYAML dependency is not importable for the --profile check."""


def _load_profile_adapter():
    try:
        import okf_yaml_profile  # lazy import keeps the default path PyYAML-free
    except ImportError as exc:
        raise _MissingProfileDependency(
            "the --profile checker requires PyYAML; install the project into its "
            "environment with 'python -m pip install -e .' (see ENVIRONMENT.md)"
        ) from exc
    return okf_yaml_profile


def _safe_profile_record() -> dict:
    return {
        "okf_concept": {"result": "not_evaluated", "reason": None},
        "framework_profile": {"result": "not_applicable", "reason": None},
        "execution_eligibility": "not_evaluated",
    }


def _profile_summary(records: list[dict]) -> dict:
    layers = {"okf_concept": {}, "framework_profile": {}, "execution_eligibility": {}}
    for rec in records:
        for layer in layers:
            value = rec[layer]
            result = value["result"] if isinstance(value, dict) else value
            layers[layer][result] = layers[layer].get(result, 0) + 1
    return {layer: dict(sorted(counts.items())) for layer, counts in layers.items()}


def _workflow_status(lines: list[str]) -> tuple[str, str]:
    """(status, problem): the workflow status declared by line-start `status:`
    lines anywhere in the artifact - a total line rule, no fence or YAML parsing.
    A value is one bare word, optionally in matching quotes (normalized away);
    any other spelling is unrecognized. Every line must agree, and a contract-v1
    prompt (one carrying a line-start `## Typed Entry` heading) declares it at
    least twice: the workflow metadata and the typed entry. Any violation is a
    problem and the caller fails closed (the artifact is treated as ready). A
    value carrying a sentinel (`status: TBD:status` in a scaffold) is an
    unresolved slot: never a value, so never ready, and never in disagreement
    unless a real value is also declared."""
    values: list[str] = []
    slots = 0
    problems: list[str] = []
    for line in lines:
        match = WORKFLOW_STATUS_RE.match(line)
        if not match:
            continue
        remainder = match.group(1).strip()
        word = STATUS_WORD_RE.match(remainder)
        if word:
            values.append(word.group(2))
        elif any(sentinel in remainder for sentinel in READY_SENTINELS):
            slots += 1
        else:
            problems.append(f"unrecognized status spelling {line[:40]!r}")
    if len(set(values)) > 1:
        problems.append("status lines disagree: " + ", ".join(sorted(set(values))))
    if values and slots:
        problems.append("a status value coexists with an unresolved status slot")
    if values and any(line.startswith(TYPED_ENTRY_HEADING) for line in lines):
        total = sum(1 for line in lines if WORKFLOW_STATUS_RE.match(line))
        if total < 2:
            problems.append(f"a contract prompt declares its status in the workflow metadata and in the typed entry; found {total}")
    if problems:
        return "ready", "; ".join(problems)
    if not values:
        return "", ""
    return values[0], ""


def check_artifact(
    artifact: Path,
    *,
    root: Path,
    known_tests: set[str],
    require_frontmatter: bool,
    check_volatile: bool,
    allowed_missing: set[str],
    text: str | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    rel = artifact.relative_to(root).as_posix()
    # ``text`` is the caller's already-decoded snapshot (profile mode); otherwise
    # the default path reads the file itself (unbounded, byte-compatible default).
    if text is None:
        text = artifact.read_text(encoding="utf-8")
    lines = text.splitlines()

    fields, frontmatter_error = _frontmatter(text)
    if require_frontmatter and frontmatter_error:
        findings.append(Finding("error", "frontmatter", rel, 1, "", frontmatter_error))
    workflow_status, status_problem = _workflow_status(lines)
    status = (fields or {}).get("status", "") or workflow_status
    if status_problem:
        status = "ready"
        findings.append(
            Finding("error", "status_ambiguous", rel, 1, "status:",
                    status_problem + "; the artifact is treated as ready and fails closed")
        )
    if status.lower() == "ready":
        for sentinel in READY_SENTINELS:
            if sentinel in text:
                findings.append(
                    Finding("error", "ready_tbd", rel, 1, "status: ready",
                            f"ready artifact contains unresolved sentinel {sentinel!r}")
                )
                break
        lowered = text.lower()
        for phrase in READY_RESIDUE_PHRASES:
            if phrase in lowered:
                findings.append(
                    Finding("error", "ready_optional_section_residue", rel, 1, "status: ready",
                            f"ready artifact carries deleted-section residue {phrase!r}")
                )
                break

    for number, line in enumerate(lines, 1):
        context = " ".join(lines[max(0, number - 4) : min(len(lines), number + 3)]).lower()
        for pattern in MACHINE_PATH_RES:
            machine = pattern.search(line)
            if machine:
                findings.append(
                    Finding("error", "machine_path", rel, number, machine.group(0), "machine-local path")
                )
                break

        if check_volatile:
            for pattern in VOLATILE_RES:
                match = pattern.search(line)
                if match:
                    findings.append(
                        Finding(
                            "warning",
                            "volatile_state",
                            rel,
                            number,
                            match.group(0),
                            "verify this is a dated/historical observation or replace it with a state/index link",
                        )
                    )

        for target in LINK_RE.findall(line):
            norm = _normalize_citation(target)
            if norm is None:
                continue
            finding = _path_finding(
                norm, root=root, base=artifact.parent, rel=rel, number=number,
                token=target.strip(), allowed_missing=allowed_missing, context=context,
            )
            if finding is not None:
                findings.append(finding)

        for token in BACKTICK_RE.findall(line):
            norm = _normalize_citation(token)
            if norm is not None and _looks_like_path(norm, root):
                finding = _path_finding(
                    norm, root=root, base=root, rel=rel, number=number,
                    token=token, allowed_missing=allowed_missing, context=context,
                )
                if finding is not None:
                    findings.append(finding)
                continue

            match = TEST_RE.fullmatch(token.strip())
            if match and match.group(1) not in known_tests:
                historical = any(word in context for word in HISTORICAL_WORDS)
                findings.append(
                    Finding(
                        "warning" if historical else "error",
                        "test_identifier",
                        rel,
                        number,
                        match.group(1),
                        "test identifier not found" + (" (historical context)" if historical else ""),
                    )
                )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path, help="Markdown artifacts to check")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--require-frontmatter", action="store_true")
    parser.add_argument("--check-volatile", action="store_true")
    parser.add_argument(
        "--profile",
        action="store_true",
        help="also report the read-only house-subset framework-profile check (opt-in)",
    )
    parser.add_argument(
        "--allow-missing",
        action="append",
        default=[],
        metavar="REPO_PATH",
        help="explicit repository-relative planned artifact allowed to be absent",
    )
    parser.add_argument(
        "--tests-root",
        action="append",
        default=[],
        metavar="REPO_DIR",
        help="repository-relative test tree to search for cited test identifiers; repeatable",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    adapter = None
    if args.profile:
        try:
            adapter = _load_profile_adapter()
        except _MissingProfileDependency as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    known_tests = _test_names(root, args.tests_root)
    allowed_missing = _safe_allowed_missing(root, args.allow_missing)
    findings: list[Finding] = []
    profile_records: list[dict] = []
    for supplied in args.artifacts:
        artifact = supplied if supplied.is_absolute() else root / supplied
        artifact = artifact.resolve()
        display = artifact.relative_to(root).as_posix() if _within(artifact, root) else str(supplied)
        profile_record = _safe_profile_record()
        if not _within(artifact, root):
            findings.append(Finding("error", "scope", str(supplied), 0, "", "artifact escapes root"))
        elif not artifact.is_file():
            findings.append(Finding("error", "artifact", str(supplied), 0, "", "artifact does not exist"))
        elif args.profile:
            # Profile mode: one contained, bounded byte read + single UTF-8 decode
            # snapshot, reused for both the ordinary integrity scan and the
            # OKF/profile evaluation. Oversized input is refused before decode or
            # any generic full-file scan.
            try:
                text, read_error = adapter.read_bounded(artifact)
            except OSError as exc:
                findings.append(Finding("error", "read", str(supplied), 0, "", str(exc)))
                text, read_error = None, "read"
            if read_error == "oversize":
                profile_record = adapter.limit_exceeded_record()
            elif read_error == "decode":
                findings.append(Finding("error", "read", str(supplied), 0, "", "input is not valid UTF-8"))
                profile_record = adapter.not_evaluated_record()
            elif read_error is None:
                findings.extend(
                    check_artifact(
                        artifact,
                        root=root,
                        known_tests=known_tests,
                        require_frontmatter=args.require_frontmatter,
                        check_volatile=args.check_volatile,
                        allowed_missing=allowed_missing,
                        text=text,
                    )
                )
                profile_record = adapter.evaluate_profile(text)
            profile_records.append({"path": display, **profile_record})
            continue
        else:
            try:
                findings.extend(
                    check_artifact(
                        artifact,
                        root=root,
                        known_tests=known_tests,
                        require_frontmatter=args.require_frontmatter,
                        check_volatile=args.check_volatile,
                        allowed_missing=allowed_missing,
                    )
                )
            except (OSError, UnicodeError) as exc:
                findings.append(Finding("error", "read", str(supplied), 0, "", str(exc)))
        if args.profile:
            profile_records.append({"path": display, **profile_record})

    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)

    if args.profile:
        # A conclusive OKF fail, a framework-profile fail, or an OKF unverified
        # resource refusal all produce a nonzero profile-mode exit so refusal
        # cannot be mistaken for success.
        profile_fail = any(
            rec["okf_concept"]["result"] in ("fail", "unverified")
            or rec["framework_profile"]["result"] == "fail"
            for rec in profile_records
        )
        if args.json:
            print(json.dumps({
                "schema_version": adapter.PROFILE_SCHEMA_VERSION,
                "errors": errors,
                "warnings": warnings,
                "findings": [asdict(f) for f in findings],
                "profile_summary": _profile_summary(profile_records),
                "artifacts": profile_records,
            }, indent=2))
        else:
            print("Artifact integrity preflight (read-only)")
            for item in findings:
                where = f"{item.artifact}:{item.line}" if item.line else item.artifact
                print(f"{item.severity.upper()} {item.check_id} {where}: {item.message} [{item.evidence}]")
            print(f"Summary: {errors} error(s), {warnings} warning(s)")
            print(f"Profile check (schema {adapter.PROFILE_SCHEMA_VERSION}):")
            for rec in profile_records:
                okf = rec["okf_concept"]
                prof = rec["framework_profile"]
                print(
                    f"{rec['path']}: okf_concept={okf['result']}({okf['reason']}) "
                    f"framework_profile={prof['result']}({prof['reason']}) "
                    f"execution_eligibility={rec['execution_eligibility']}"
                )
        return 1 if (errors or profile_fail) else 0

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        print("Artifact integrity preflight (read-only)")
        for item in findings:
            where = f"{item.artifact}:{item.line}" if item.line else item.artifact
            print(f"{item.severity.upper()} {item.check_id} {where}: {item.message} [{item.evidence}]")
        print(f"Summary: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
