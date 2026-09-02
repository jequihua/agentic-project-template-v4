"""Read-only local-state footprint audit for a project made from this template.

Makes hidden local disk/worktree state visible without forcing any policy: file
and directory counts, approximate bytes, the largest top-level directories, and
flags for nested `.git` repositories, virtual environments, caches, and large
files. Useful before milestone closure, a handoff, or deleting a local clone.

This tool is strictly READ-ONLY: it never deletes, moves, or modifies anything
(including `.gitignore`). It exits 0 even when a project is large — being large is
not a failure.

Usage::

    python scripts/local_state_audit.py --root .

Stdlib-only. See `scripts/README.md` and
`docs/template_framework/security_and_local_state.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _local_state_common as core  # noqa: E402

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]


# --- The drive's released oracle exclusion manifest grammar (frutlups-drive
# workspace._load_oracle_exclusions). The template does not define a second
# dialect: this reader accepts exactly what the drive accepts and refuses the
# rest, so a passing pre-launch check never disagrees with drive admission.
GOVERNED_TOP_LEVEL = (".git", ".frutlups_drive", "local_state")
REQUIRED_ORACLE_PATHS = ("05_governance/reviews/INDEX.md",)
MAX_MANIFEST_BYTES = 64 * 1024
MAX_MANIFEST_ENTRIES = 1_024


class ExclusionManifestInvalid(Exception):
    pass


def _canonical_relative(value) -> bool:
    """The drive's canonical repository-relative POSIX rule, applied to the
    unmodified declared string: no backslash, no absolute or drive-letter form,
    no empty, '.', or '..' segment, no trailing slash, no surrounding space."""
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if "\\" in value or value.startswith("/") or value.endswith("/"):
        return False
    if len(value) > 1 and value[1] == ":":
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _is_junction(path: Path) -> bool:
    return bool(getattr(path, "is_junction", lambda: False)())


def load_exclusion_manifest(root: Path, declared) -> tuple[set, tuple]:
    """Return (exact_paths, top_level_prefixes) or raise ExclusionManifestInvalid.

    ``declared is None`` means no declaration (nothing excluded). A declared
    reference is validated unmodified before any filesystem access, then resolved
    strictly under the strictly resolved root; a declared file that is missing,
    a link, or a junction refuses - exactly the drive's behavior."""
    if declared is None:
        return set(), ()
    rel_text = str(declared)
    if not _canonical_relative(rel_text):
        raise ExclusionManifestInvalid("the declared path is not canonical")
    if rel_text.split("/", 1)[0] in GOVERNED_TOP_LEVEL:
        raise ExclusionManifestInvalid("the declared file is outside the frozen surface")
    manifest_path = root / rel_text
    try:
        resolved_root = Path(root).resolve(strict=True)
        resolved = manifest_path.resolve(strict=True)
        resolved.relative_to(resolved_root)
        if manifest_path.is_symlink() or _is_junction(manifest_path) or not resolved.is_file():
            raise OSError
        with open(resolved, "rb") as stream:
            data = stream.read(MAX_MANIFEST_BYTES + 1)  # bounded, as the drive reads
    except (OSError, ValueError):
        raise ExclusionManifestInvalid("the declared file is unavailable") from None
    if len(data) > MAX_MANIFEST_BYTES:
        raise ExclusionManifestInvalid(f"the declared file exceeds {MAX_MANIFEST_BYTES} bytes")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ExclusionManifestInvalid("the declared file is not valid UTF-8 JSON") from None
    if (
        not isinstance(payload, dict)
        or set(payload) != {"contract_version", "exact_paths", "top_level_prefixes"}
        or payload.get("contract_version") != 1
        or not isinstance(payload.get("exact_paths"), list)
        or not isinstance(payload.get("top_level_prefixes"), list)
    ):
        raise ExclusionManifestInvalid("the manifest fields are malformed")
    exact = payload["exact_paths"]
    prefixes = payload["top_level_prefixes"]
    if len(exact) + len(prefixes) > MAX_MANIFEST_ENTRIES:
        raise ExclusionManifestInvalid(f"the manifest exceeds {MAX_MANIFEST_ENTRIES} entries")
    if any(not _canonical_relative(item) for item in exact) or len(set(exact)) != len(exact):
        raise ExclusionManifestInvalid("exact_paths must be unique canonical file paths")
    if any(item.split("/", 1)[0] in GOVERNED_TOP_LEVEL for item in exact):
        raise ExclusionManifestInvalid("exact_paths must remain inside the frozen surface")
    for item in exact:
        candidate = root / item
        if candidate.exists() and (candidate.is_dir() or _is_junction(candidate)):
            raise ExclusionManifestInvalid("exact_paths must name files, not directories")
    checked = []
    for item in prefixes:
        if not isinstance(item, str) or not item.endswith("/"):
            raise ExclusionManifestInvalid("top_level_prefixes must be unique top-level directories ending in '/'")
        directory = item[:-1]
        if not _canonical_relative(directory) or "/" in directory or directory in GOVERNED_TOP_LEVEL:
            raise ExclusionManifestInvalid("top_level_prefixes must be unique top-level directories ending in '/'")
        checked.append(item)
    if len(set(checked)) != len(checked):
        raise ExclusionManifestInvalid("top_level_prefixes must be unique top-level directories ending in '/'")
    if rel_text in exact or any(rel_text.startswith(prefix) for prefix in checked):
        raise ExclusionManifestInvalid("the manifest cannot exclude its own frozen bytes")
    if any(path.startswith(prefix) for path in exact for prefix in checked):
        raise ExclusionManifestInvalid("exact_paths cannot duplicate a declared top-level prefix")
    if any(req in exact or any(req.startswith(prefix) for prefix in checked) for req in REQUIRED_ORACLE_PATHS):
        raise ExclusionManifestInvalid("the manifest cannot exclude a required oracle input")
    return set(exact), tuple(sorted(checked))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT,
                        help="Project root to audit (default: the template root).")
    parser.add_argument("--large-file-mb", type=float, default=core.LARGE_FILE_BYTES / (1024 * 1024),
                        help="Flag individual files at or above this size in MB.")
    parser.add_argument("--limit-bytes", type=int, default=None,
                        help="Pre-launch check: list undeclared files at or above this size and exit 1 "
                             "when any exist (the drive's oracle content bound is 16777216).")
    parser.add_argument("--exclusions", type=str, default=None,
                        help="The drive's oracle exclusion manifest (strict JSON: contract_version, "
                             "exact_paths, top_level_prefixes); the same file the drive reads.")
    parser.add_argument("--top", type=int, default=10,
                        help="How many largest top-level directories / large files to show.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 2

    fp = core.audit_footprint(root, large_file_bytes=int(args.large_file_mb * 1024 * 1024))

    print(f"Local-state audit (read-only): {root}")
    print(f"  files: {fp.total_files}   directories: {fp.total_dirs}   "
          f"size: {core.human_bytes(fp.total_bytes)}")

    if fp.top_level:
        print("\nLargest top-level directories:")
        for name, size, files in fp.top_level[: args.top]:
            print(f"  {core.human_bytes(size):>10}  {files:>7} files  {name}/")

    if fp.venvs:
        print(f"\nVirtual environments ({len(fp.venvs)}) - not deleted by cleanup; "
              "remove manually when idle:")
        for rel in fp.venvs:
            print(f"  {rel}/")

    if fp.nested_git:
        print(f"\nNested .git repositories ({len(fp.nested_git)}) - review; the template "
              "discourages nested repos:")
        for rel in fp.nested_git:
            print(f"  {rel}/")

    if fp.caches:
        print(f"\nRebuildable caches ({len(fp.caches)}) - clean with "
              "`python scripts/local_cleanup.py --apply`:")
        for rel in fp.caches[: args.top]:
            print(f"  {rel}/")
        if len(fp.caches) > args.top:
            print(f"  ... and {len(fp.caches) - args.top} more")

    if fp.large_files:
        print(f"\nLarge files (>= {args.large_file_mb:g} MB):")
        for rel, size in fp.large_files[: args.top]:
            print(f"  {core.human_bytes(size):>10}  {rel}")

    print("\nRead-only: nothing was changed.")
    if args.limit_bytes is not None:
        try:
            exact, prefixes = load_exclusion_manifest(root, args.exclusions)
        except ExclusionManifestInvalid as exc:
            print(f"\nPre-launch size check: exclusion manifest invalid; {exc}; nothing was excluded")
            return 1
        bound = core.audit_footprint(root, large_file_bytes=args.limit_bytes)
        offenders = [
            (rel, size) for rel, size in bound.large_files
            if rel not in exact
            and not rel.startswith(prefixes)
            and rel.split("/")[0] not in GOVERNED_TOP_LEVEL
        ]
        declared = "none declared" if args.exclusions is None else \
            f"{len(exact)} exact exclusions, {len(prefixes)} prefix exclusions from {args.exclusions}"
        print(f"\nPre-launch size check (bound {args.limit_bytes} bytes; {declared}):")
        if offenders:
            for rel, size in sorted(offenders):
                print(f"  ABOVE BOUND  {rel}  {size} bytes")
            print("Declare each in the exclusion manifest or move it under local_state/.")
            return 1
        print("  no undeclared file at or above the bound")
    return 0


if __name__ == "__main__":
    sys.exit(main())
