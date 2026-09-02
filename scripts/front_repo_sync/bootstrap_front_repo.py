"""First-copy export of a front-facing repository from the development repo.

Use this once, before a front-facing repo exists, to produce a clean exported
tree in a new directory. It NEVER initializes git, commits, pushes, or opens a
PR — the human owner inspects the output, then runs `git init`, the first commit,
adds a remote, and pushes. Afterwards, use `sync_front_repo.py` for updates.

Usage::

    python scripts/front_repo_sync/bootstrap_front_repo.py --check --output-dir PATH
    python scripts/front_repo_sync/bootstrap_front_repo.py --apply --output-dir PATH

Stdlib-only. See `README.md` and the manifest example.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _front_repo_common as core  # noqa: E402

SCRIPT_PATH = Path(__file__).resolve()
DEV_REPO_ROOT = SCRIPT_PATH.parents[2]
MANIFEST_PATH = SCRIPT_PATH.parent / "front_repo_sync_manifest.example.toml"


def validate_output_dir(output: Path, allow_non_empty: bool) -> None:
    if (output / ".git").exists():
        raise SystemExit(
            f"refusing: output directory already contains .git: {output}\n"
            "Bootstrap targets a NON-repo directory. Use sync_front_repo.py for an "
            "existing front-facing repo."
        )
    if output.exists() and any(output.iterdir()) and not allow_non_empty:
        raise SystemExit(
            f"refusing: output directory is not empty: {output}\n"
            "Re-run with --allow-non-empty-output to override (writes stay inside output)."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Print the first-copy plan; write nothing.")
    mode.add_argument("--apply", action="store_true", help="Create the first-copy tree.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Destination directory (must be outside the dev repo).")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH,
                        help=f"Manifest path (default: {MANIFEST_PATH}).")
    parser.add_argument("--allow-non-empty-output", action="store_true",
                        help="Allow exporting into a non-empty output directory.")
    parser.add_argument("--dev-root", type=Path, default=DEV_REPO_ROOT,
                        help="Advanced/testing: override the development repo root.")
    args = parser.parse_args(argv)

    dev_root = args.dev_root.resolve()
    manifest = core.load_manifest(args.manifest)
    output_raw = args.output_dir or (Path(manifest.default_bootstrap_output)
                                     if manifest.default_bootstrap_output else None)
    if output_raw is None:
        raise SystemExit("no output directory: pass --output-dir or set default_bootstrap_output.")
    output_root = Path(output_raw).resolve()

    print(f"Development repo: {dev_root}")
    print(f"Bootstrap output: {output_root}")
    print(f"Manifest: {args.manifest}")

    core.validate_separation(dev_root, output_root, "output directory")
    validate_output_dir(output_root, args.allow_non_empty_output)

    plan = core.build_plan(manifest, dev_root, output_root)
    core.report_plan(plan, dev_root, output_root)

    if plan.missing():
        print("\nERROR: missing source files for the following manifest entries:")
        for e in plan.missing():
            print(f"  {e.source}")
        return 2

    writes = plan.writes()
    if not writes:
        print("\nNothing to export.")
        return 0
    if args.check:
        print(f"\nCheck mode: {len(writes)} change(s) would be written. Nothing written.")
        return 0

    output_root.mkdir(parents=True, exist_ok=True)
    core.apply_plan(plan, output_root)
    print(f"\nExported {len(writes)} change(s) to {output_root}")
    print("This is NOT a git repo. Next, the human owner inspects it, then runs:")
    print("  git init  ->  first commit  ->  add remote  ->  push")
    print("Future updates use sync_front_repo.py. PRs remain human-requested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
