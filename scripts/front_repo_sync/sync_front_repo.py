"""Ongoing one-way sync from the development repo into a front-facing git repo.

Direction is one-way: development repo -> front-facing repo. The front-facing
repo is a curated projection of the development repo (per the manifest), not a
full mirror, and lives OUTSIDE the development repo.

Usage::

    python scripts/front_repo_sync/sync_front_repo.py --check --target-repo PATH
    python scripts/front_repo_sync/sync_front_repo.py --apply --target-repo PATH
    python scripts/front_repo_sync/sync_front_repo.py --apply --target-repo PATH --allow-dirty-target

Safety: the target must exist, contain `.git`, and (for --apply) be clean unless
overridden. The target must not nest with the development repo. The tool never
commits, pushes, opens PRs, or calls frutlups. Stdlib-only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _front_repo_common as core  # noqa: E402

SCRIPT_PATH = Path(__file__).resolve()
DEV_REPO_ROOT = SCRIPT_PATH.parents[2]
MANIFEST_PATH = SCRIPT_PATH.parent / "front_repo_sync_manifest.example.toml"


def validate_target_repo(target: Path) -> None:
    if not target.exists() or not target.is_dir():
        raise SystemExit(f"target repo does not exist or is not a directory: {target}")
    if not (target / ".git").exists():
        raise SystemExit(
            f"target repo has no .git directory: {target}\n"
            "Bootstrap a new front repo first with bootstrap_front_repo.py, then git init it."
        )


def require_clean_target(target: Path) -> None:
    """Enforced before --apply: refuse a dirty target working tree."""
    try:
        result = subprocess.run(
            ["git", "-C", str(target), "status", "--porcelain"],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"could not check target git status ({exc}); re-run with --allow-dirty-target if intended.")
    if result.stdout.strip():
        raise SystemExit(
            "target repo has uncommitted changes. Refusing to apply.\n"
            "Re-run with --allow-dirty-target to override.\n"
            f"git status:\n{result.stdout}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Print the plan; write nothing.")
    mode.add_argument("--apply", action="store_true", help="Apply the plan to the target repo.")
    parser.add_argument("--target-repo", type=Path, default=None,
                        help="Front-facing git repo (must exist, contain .git, be outside the dev repo).")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH,
                        help=f"Manifest path (default: {MANIFEST_PATH}).")
    parser.add_argument("--allow-dirty-target", action="store_true",
                        help="Allow --apply against a target repo with uncommitted changes.")
    parser.add_argument("--dev-root", type=Path, default=DEV_REPO_ROOT,
                        help="Advanced/testing: override the development repo root.")
    args = parser.parse_args(argv)

    dev_root = args.dev_root.resolve()
    manifest = core.load_manifest(args.manifest)
    target_raw = args.target_repo or (Path(manifest.default_target)
                                      if manifest.default_target else None)
    if target_raw is None:
        raise SystemExit("no target repo: pass --target-repo or set default_target.")
    target_root = Path(target_raw).resolve()

    print(f"Development repo: {dev_root}")
    print(f"Front-facing repo: {target_root}")
    print(f"Manifest: {args.manifest}")

    core.validate_separation(dev_root, target_root, "target repo")
    validate_target_repo(target_root)

    plan = core.build_plan(manifest, dev_root, target_root)
    core.report_plan(plan, dev_root, target_root)

    if plan.missing():
        print("\nERROR: missing source files for the following manifest entries:")
        for e in plan.missing():
            print(f"  {e.source}")
        return 2

    writes = plan.writes()
    if not writes:
        print("\nNo changes needed. Target is already in sync.")
        return 0
    if args.check:
        print(f"\nCheck mode: {len(writes)} change(s) would be applied. Nothing written.")
        return 0

    if not args.allow_dirty_target:
        require_clean_target(target_root)
    core.apply_plan(plan, target_root)
    print(f"\nApplied {len(writes)} change(s) to {target_root}")
    print("Commits and PRs in the front-facing repo remain governed by the human/project workflow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
