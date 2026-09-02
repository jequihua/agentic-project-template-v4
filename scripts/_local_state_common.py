"""Shared, stdlib-only core for the local-state audit and cleanup tools.

These tools give a project made from this template *visibility* into its local
disk/worktree footprint and a *conservative, dry-run-first* way to remove
rebuildable residue (caches, build output, coverage). They are support tooling,
not part of the artifact-first loop, and they never touch meaningful artifacts.

This module holds the shared classification sets, a symlink-safe directory walk
that prunes protected and nested-repo subtrees, size computation, the cleanup
candidate finder, and the read-only footprint audit. It is imported by
`local_state_audit.py` (read-only) and `local_cleanup.py` (dry-run default).

No third-party dependencies. No git, network, or PR actions. The audit never
writes; cleanup writes only under an explicit `--apply` and only inside the
resolved root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

# Directory names that are rebuildable residue: safe for `--apply` to delete.
# These mirror the non-source local artifacts the template `.gitignore` already
# excludes, so cleaning them never removes tracked or meaningful work.
REBUILDABLE_DIR_NAMES: frozenset[str] = frozenset({
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "test-results",
    "build",
    "dist",
})

# Directory name globs that are rebuildable (e.g. packaging metadata, temp test
# folders) and safe for `--apply` to delete.
REBUILDABLE_DIR_GLOBS: tuple[str, ...] = ("*.egg-info", ".tmp_pytest*", ".pytest_tmp*")

# File names that are rebuildable residue: safe for `--apply` to delete.
REBUILDABLE_FILE_NAMES: frozenset[str] = frozenset({".coverage", "coverage.xml"})

# Virtual-environment directory names. The audit FLAGS these; cleanup NEVER
# deletes them (deleting an environment mid-work is annoying and is a separate,
# explicit decision).
VENV_DIR_NAMES: frozenset[str] = frozenset({".venv", "venv", "env"})

# Cache directory names the audit flags as common local residue.
CACHE_DIR_NAMES: frozenset[str] = frozenset({
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
})

# Directory names cleanup must never enter or delete, at any depth. Workspace
# roots hold evidence and governance; venvs/local-state/memory are local roots;
# `.git` is repository metadata. A nested repository (a directory carrying its
# own `.git`) is additionally protected by `has_nested_git`.
PROTECTED_DIR_NAMES: frozenset[str] = frozenset({
    ".git",
    ".venv",
    "venv",
    "env",
    "local_state",
    "llloom_memory",
    "memory_root",
    "01_data",
    "03_experiments",
    "05_governance",
    "90_legacy_review",
    "memory",
})

# Default threshold (bytes) above which the audit flags an individual file.
LARGE_FILE_BYTES = 5 * 1024 * 1024


def is_rebuildable_dir(name: str) -> bool:
    return name in REBUILDABLE_DIR_NAMES or any(
        fnmatch(name, pattern) for pattern in REBUILDABLE_DIR_GLOBS
    )


def is_rebuildable_file(name: str) -> bool:
    return name in REBUILDABLE_FILE_NAMES


def is_protected_name(name: str) -> bool:
    return name in PROTECTED_DIR_NAMES


def has_nested_git(directory: Path, root: Path) -> bool:
    """True if `directory` is a nested repository: not the root, and it holds a
    `.git` entry. Cleanup prunes such subtrees entirely."""
    if directory.resolve() == root.resolve():
        return False
    return (directory / ".git").exists()


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


# ---------------------------------------------------------------------------
# Size
# ---------------------------------------------------------------------------


def dir_size(path: Path) -> tuple[int, int]:
    """Return (total_bytes, file_count) for `path`, never following symlinks.

    Symlinks are counted as zero-byte entries and not followed, so the walk
    cannot wander outside `path` or double-count link targets.
    """
    total = 0
    files = 0
    if path.is_symlink():
        return (0, 0)
    if path.is_file():
        try:
            return (path.stat().st_size, 1)
        except OSError:
            return (0, 1)
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        here = Path(dirpath)
        # Do not descend into symlinked subdirectories.
        dirnames[:] = [d for d in dirnames if not (here / d).is_symlink()]
        for name in filenames:
            f = here / name
            if f.is_symlink():
                continue
            files += 1
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return (total, files)


# ---------------------------------------------------------------------------
# Cleanup candidates
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    path: Path
    kind: str  # "dir" | "file"
    bytes: int
    files: int


def find_cleanup_candidates(root: Path) -> list[Candidate]:
    """Find rebuildable residue under `root`, skipping protected and nested-repo
    subtrees and never following symlinks.

    A rebuildable directory is recorded whole and not descended into. Protected
    directory names and nested repositories are pruned so cleanup can never reach
    evidence, governance, venvs, local state, memory roots, or another repo.
    """
    root = root.resolve()
    candidates: list[Candidate] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            child = here / name
            if child.is_symlink():
                continue  # never follow or delete symlinked dirs
            if is_protected_name(name) or has_nested_git(child, root):
                continue  # prune protected / nested-repo subtrees
            if is_rebuildable_dir(name):
                size, count = dir_size(child)
                candidates.append(Candidate(child, "dir", size, count))
                continue  # record whole; do not descend
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            f = here / name
            if f.is_symlink():
                continue
            if is_rebuildable_file(name):
                try:
                    size = f.stat().st_size
                except OSError:
                    size = 0
                candidates.append(Candidate(f, "file", size, 1))
    return candidates


# ---------------------------------------------------------------------------
# Read-only footprint audit
# ---------------------------------------------------------------------------


@dataclass
class Footprint:
    root: Path
    total_files: int = 0
    total_dirs: int = 0
    total_bytes: int = 0
    top_level: list[tuple[str, int, int]] = field(default_factory=list)  # (name, bytes, files)
    nested_git: list[str] = field(default_factory=list)
    venvs: list[str] = field(default_factory=list)
    caches: list[str] = field(default_factory=list)
    large_files: list[tuple[str, int]] = field(default_factory=list)  # (rel_path, bytes)


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def audit_footprint(root: Path, large_file_bytes: int = LARGE_FILE_BYTES) -> Footprint:
    """Compute a read-only footprint of `root`. Stats only — never writes.

    Counts all on-disk files/dirs/bytes (symlink-safe), measures each top-level
    directory, and flags nested `.git` directories, virtual environments, caches,
    and individually large files.
    """
    root = root.resolve()
    fp = Footprint(root=root)

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not (here / d).is_symlink()]
        for name in dirnames:
            child = here / name
            fp.total_dirs += 1
            if name in VENV_DIR_NAMES:
                fp.venvs.append(_rel(child, root))
            if name in CACHE_DIR_NAMES:
                fp.caches.append(_rel(child, root))
            if name == ".git" and child.resolve() != (root / ".git").resolve():
                fp.nested_git.append(_rel(child.parent, root))
        for name in filenames:
            f = here / name
            if f.is_symlink():
                continue
            fp.total_files += 1
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            fp.total_bytes += size
            if size >= large_file_bytes:
                fp.large_files.append((_rel(f, root), size))

    for child in sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()):
        size, files = dir_size(child)
        fp.top_level.append((child.name, size, files))
    fp.top_level.sort(key=lambda t: t[1], reverse=True)
    fp.large_files.sort(key=lambda t: t[1], reverse=True)
    return fp


def human_bytes(n: int) -> str:
    """Format a byte count for terminal display."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"
