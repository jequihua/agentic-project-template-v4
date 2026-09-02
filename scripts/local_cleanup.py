"""Dry-run-first cleanup of rebuildable local residue.

Removes only known, rebuildable, non-source local artifacts — the same
categories the template `.gitignore` already excludes: Python/test caches,
coverage output, build/dist output, packaging metadata, and temporary test
folders. It is **dry-run by default**: without `--apply` it only reports what it
would remove.

It NEVER touches protected paths: `.git`, virtual environments (`.venv`/`venv`/
`env`), `local_state/`, local memory roots, the evidence/governance workspaces
(`01_data`, `03_experiments`, `05_governance`, `90_legacy_review`, `memory`),
archives, copied source trees, or any nested repository. It never deletes outside
the resolved `--root` and never follows symlinks.

Usage::

    python scripts/local_cleanup.py --check --root .   # report only (default)
    python scripts/local_cleanup.py --apply --root .   # delete rebuildable residue

Stdlib-only. See `scripts/README.md` and
`docs/template_framework/security_and_local_state.md`.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _local_state_common as core  # noqa: E402

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]


def _safe_to_delete(path: Path, root: Path) -> bool:
    """Final guard before any deletion: the ORIGINAL candidate is not a symlink,
    and its resolved path is inside root, not the root itself, and not within a
    protected/nested-repo subtree.

    The symlink check runs on the original path *before* `resolve()`: a resolved
    path follows the link to its target and would never report as a symlink, so
    resolving first would silently defeat this independent guard. Candidate
    discovery already skips symlinks; this is the defense-in-depth re-check.
    """
    if path.is_symlink():
        return False
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved == root_resolved:
        return False
    if not core.is_within(resolved, root):
        return False
    rel_parts = resolved.relative_to(root_resolved).parts
    if any(core.is_protected_name(part) for part in rel_parts):
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--check", action="store_true",
                      help="Report candidates only; delete nothing (default).")
    mode.add_argument("--apply", action="store_true",
                      help="Delete the rebuildable residue listed by --check.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT,
                        help="Project root to clean (default: the template root).")
    args = parser.parse_args(argv)

    apply = args.apply  # dry-run unless --apply is explicitly given
    root = args.root.resolve()
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 2

    candidates = core.find_cleanup_candidates(root)
    mode_label = "APPLY" if apply else "CHECK (dry-run)"
    print(f"Local cleanup [{mode_label}]: {root}")

    if not candidates:
        print("  no rebuildable residue found.")
        return 0

    total_bytes = sum(c.bytes for c in candidates)
    total_files = sum(c.files for c in candidates)
    for c in candidates:
        rel = str(c.path.resolve().relative_to(root)).replace("\\", "/")
        suffix = "/" if c.kind == "dir" else ""
        print(f"  {core.human_bytes(c.bytes):>10}  {c.files:>6} files  {rel}{suffix}")
    print(f"  ---\n  {len(candidates)} item(s), ~{core.human_bytes(total_bytes)}, "
          f"{total_files} file(s)")

    if not apply:
        print("\nDry-run: nothing deleted. Re-run with --apply to remove these.")
        return 0

    removed = 0
    for c in candidates:
        if not _safe_to_delete(c.path, root):
            print(f"  skipped (guard): {c.path}")
            continue
        try:
            if c.kind == "dir":
                shutil.rmtree(c.path)
            else:
                c.path.unlink()
            removed += 1
        except OSError as exc:
            print(f"  could not remove {c.path}: {exc}")
    print(f"\nRemoved {removed} of {len(candidates)} item(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
