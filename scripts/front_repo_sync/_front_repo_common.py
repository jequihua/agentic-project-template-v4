"""Shared, stdlib-only core for the front-facing repo bootstrap and sync tools.

The development repository (a project made from this template) is the source of
truth. A *front-facing* repository is a separate, outside repo populated as a
curated projection of the development repo — never a nested child repo.

This module holds the manifest model, the plan model, path-safety checks, and
plan build/apply/report helpers shared by `bootstrap_front_repo.py` (first-copy
export into a new non-repo directory) and `sync_front_repo.py` (ongoing one-way
sync into an existing front-facing git repo).

No third-party dependencies. No git, network, or PR actions.
"""

from __future__ import annotations

import filecmp
import fnmatch
import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Manifest model
# ---------------------------------------------------------------------------


@dataclass
class IgnoreRules:
    names: set[str] = field(default_factory=set)
    suffixes: set[str] = field(default_factory=set)
    globs: list[str] = field(default_factory=list)

    def should_skip(self, name: str) -> bool:
        if name in self.names:
            return True
        if any(name.endswith(suffix) for suffix in self.suffixes):
            return True
        return any(fnmatch.fnmatch(name, pattern) for pattern in self.globs)


@dataclass
class Manifest:
    default_target: str
    default_bootstrap_output: str
    ignore: IgnoreRules
    files: list[tuple[str, str]]
    directories: list[tuple[str, str]]
    stale: list[tuple[str, str]]


def load_manifest(path: Path) -> Manifest:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    settings = data.get("settings", {})
    ignore_raw = data.get("ignore", {})
    ignore = IgnoreRules(
        names=set(ignore_raw.get("names", [])),
        suffixes=set(ignore_raw.get("suffixes", [])),
        globs=list(ignore_raw.get("globs", [])),
    )
    files = [(f["source"], f["target"]) for f in data.get("files", [])]
    directories = [(d["source"], d["target"]) for d in data.get("directories", [])]
    stale = [(s["target"], s.get("reason", "")) for s in data.get("stale", [])]
    return Manifest(
        default_target=settings.get("default_target", ""),
        default_bootstrap_output=settings.get("default_bootstrap_output", ""),
        ignore=ignore,
        files=files,
        directories=directories,
        stale=stale,
    )


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------


@dataclass
class PlanEntry:
    action: str  # copy-new | copy-update | same | delete | missing-source
    source: Path | None
    target: Path
    note: str = ""


@dataclass
class Plan:
    entries: list[PlanEntry] = field(default_factory=list)

    def add(self, entry: PlanEntry) -> None:
        self.entries.append(entry)

    def writes(self) -> list[PlanEntry]:
        return [e for e in self.entries if e.action in ("copy-new", "copy-update", "delete")]

    def missing(self) -> list[PlanEntry]:
        return [e for e in self.entries if e.action == "missing-source"]


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def is_within(path: Path, root: Path) -> bool:
    """True if `path` is `root` or a descendant of `root` (lexically resolved)."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def ensure_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not is_within(resolved, root):
        raise SystemExit(f"refusing to {label} outside the destination root: {resolved}")
    return resolved


def ensure_source_within(path: Path, dev_root: Path) -> Path:
    """Refuse a manifest source that resolves outside the development repo root.

    Manifest source paths are a curated projection from inside the development
    repo only. Resolved containment (not string prefixes) rejects `../` traversal
    and absolute paths that land outside `dev_root`, so the tool cannot read
    parent folders, secrets, or arbitrary machine paths into the export. A source
    that resolves *inside* `dev_root` but does not exist is left to the normal
    missing-source handling.
    """
    resolved = path.resolve()
    if not is_within(resolved, dev_root):
        raise SystemExit(
            f"refusing to read source outside the development repo root: {resolved}"
        )
    return resolved


def validate_separation(dev_root: Path, other_root: Path, other_label: str) -> None:
    """Refuse if the dev repo and the destination overlap or nest either way.

    This is the load-bearing guard against creating a nested repository or a
    recursive copy: the front-facing destination must be a separate, outside
    location.
    """
    dev = dev_root.resolve()
    other = other_root.resolve()
    if dev == other:
        raise SystemExit(f"refusing: {other_label} is the development repo itself: {other}")
    if is_within(other, dev):
        raise SystemExit(
            f"refusing: {other_label} is nested inside the development repo: {other}"
        )
    if is_within(dev, other):
        raise SystemExit(
            f"refusing: the development repo is nested inside {other_label}: {other}"
        )


# ---------------------------------------------------------------------------
# Plan construction
# ---------------------------------------------------------------------------


def files_equal(a: Path, b: Path) -> bool:
    if not (a.exists() and b.exists()):
        return False
    return filecmp.cmp(a, b, shallow=False)


def plan_file(source: Path, target: Path, plan: Plan) -> None:
    if not source.exists() or not source.is_file():
        plan.add(PlanEntry("missing-source", source, target))
        return
    if not target.exists():
        plan.add(PlanEntry("copy-new", source, target))
        return
    plan.add(PlanEntry("same" if files_equal(source, target) else "copy-update", source, target))


def iter_source_files(source_dir: Path, ignore: IgnoreRules, dev_root: Path) -> list[Path]:
    """Walk a mirrored source directory WITHOUT following symlinks.

    A front-facing projection must be boring and explicit: it must not read
    outside the development repo by accident. So a symlink encountered during the
    walk — a symlinked file or a symlinked subdirectory — is REJECTED, not
    silently skipped or followed. Every regular file is also revalidated to
    resolve inside `dev_root` before it is planned.
    """
    if not source_dir.exists():
        return []
    out: list[Path] = []
    # followlinks=False (the default) does not descend into symlinked dirs; we
    # additionally reject any symlink we encounter rather than just not following.
    for dirpath, dirnames, filenames in os.walk(source_dir, followlinks=False):
        here = Path(dirpath)
        kept_dirs: list[str] = []
        for name in dirnames:
            if ignore.should_skip(name):
                continue
            child = here / name
            if child.is_symlink():
                raise SystemExit(
                    "refusing a symlinked directory during the source walk "
                    f"(would risk reading outside the development repo root): {child}"
                )
            kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in filenames:
            if ignore.should_skip(name):
                continue
            f = here / name
            if f.is_symlink():
                raise SystemExit(
                    "refusing a symlink during the source walk "
                    f"(would risk reading outside the development repo root): {f}"
                )
            ensure_source_within(f, dev_root)
            if f.is_file():
                out.append(f)
    return out


def plan_directory(
    source_dir: Path, target_dir: Path, ignore: IgnoreRules,
    dev_root: Path, dest_root: Path, plan: Plan,
) -> None:
    if not source_dir.exists() or not source_dir.is_dir():
        plan.add(PlanEntry("missing-source", source_dir, target_dir))
        return

    expected: set[Path] = set()
    for src_file in iter_source_files(source_dir, ignore, dev_root):
        rel = src_file.relative_to(source_dir)
        tgt_file = ensure_within(target_dir / rel, dest_root, "write")
        expected.add(tgt_file)
        plan_file(src_file, tgt_file, plan)

    # Stale files inside the managed target directory get deleted.
    if target_dir.exists():
        for p in target_dir.rglob("*"):
            if any(ignore.should_skip(part) for part in p.relative_to(target_dir).parts):
                continue
            if p.is_file() and ensure_within(p, dest_root, "delete") not in expected:
                plan.add(PlanEntry("delete", None, p.resolve(), note="stale inside managed directory"))


def plan_stale(target: Path, dest_root: Path, reason: str, plan: Plan) -> None:
    resolved = ensure_within(target, dest_root, "delete")
    if resolved.exists():
        plan.add(PlanEntry("delete", None, resolved, note=f"explicit stale: {reason}"))


def build_plan(manifest: Manifest, dev_root: Path, dest_root: Path) -> Plan:
    plan = Plan()
    for src_rel, tgt_rel in manifest.files:
        src = ensure_source_within(dev_root / src_rel, dev_root)
        tgt = ensure_within(dest_root / tgt_rel, dest_root, "write")
        plan_file(src, tgt, plan)
    for src_rel, tgt_rel in manifest.directories:
        src = ensure_source_within(dev_root / src_rel, dev_root)
        tgt = (dest_root / tgt_rel).resolve()
        plan_directory(src, tgt, manifest.ignore, dev_root, dest_root, plan)
    for tgt_rel, reason in manifest.stale:
        plan_stale((dest_root / tgt_rel).resolve(), dest_root, reason, plan)
    return plan


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_entry(entry: PlanEntry, dest_root: Path) -> None:
    if entry.action in ("copy-new", "copy-update"):
        assert entry.source is not None
        ensure_within(entry.target, dest_root, "write")
        entry.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry.source, entry.target)
    elif entry.action == "delete":
        ensure_within(entry.target, dest_root, "delete")
        if entry.target.is_dir():
            shutil.rmtree(entry.target)
        elif entry.target.exists():
            entry.target.unlink()


def apply_plan(plan: Plan, dest_root: Path) -> None:
    for entry in plan.writes():
        apply_entry(entry, dest_root)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def fmt_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def report_plan(plan: Plan, dev_root: Path, dest_root: Path) -> None:
    by_action: dict[str, list[PlanEntry]] = {}
    for e in plan.entries:
        by_action.setdefault(e.action, []).append(e)
    for action in ("missing-source", "copy-new", "copy-update", "delete", "same"):
        entries = by_action.get(action, [])
        if not entries:
            continue
        print(f"\n[{action}] {len(entries)}")
        for e in entries:
            tgt_rel = fmt_rel(e.target, dest_root)
            if e.source is not None:
                print(f"  {fmt_rel(e.source, dev_root)}  ->  {tgt_rel}")
            else:
                print(f"  (target) {tgt_rel}")
            if e.note:
                print(f"    note: {e.note}")
