"""Safely project selected development-repository files into a front repository."""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
STATE = ".front_repo_sync.json"
SENSITIVE = (".env*", "*.pem", "*.key", "credentials*", "secrets*")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_rel(value):
    if not isinstance(value, str) or not value or "\\" in value or ("\x00" in value):
        raise ValueError(f"unsafe relative path: {value!r}")
    p = PurePosixPath(value)
    if p.is_absolute() or ":" in p.parts[0] or any((x in ("", ".", "..") for x in p.parts)):
        raise ValueError(f"unsafe relative path: {value!r}")
    return p.as_posix()


def inside(root, rel, action):
    root, path = (root.resolve(), (root / safe_rel(rel)).resolve())
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"refusing to {action} outside root: {rel}") from exc
    return path


def reject_symlinks(root, rel, label):
    cursor = root.resolve()
    for part in PurePosixPath(safe_rel(rel)).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"refusing {label} symlink: {rel}")


def separated(source, target):
    a, b = (source.resolve(), target.resolve())
    try:
        b.relative_to(a)
        raise ValueError(f"destination is inside development repository: {b}")
    except ValueError as exc:
        if str(exc).startswith("destination"):
            raise
    try:
        a.relative_to(b)
        raise ValueError(f"development repository is inside destination: {b}")
    except ValueError as exc:
        if str(exc).startswith("development"):
            raise


def load_manifest(path):
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot load manifest: {exc}") from exc
    allowed = {"settings", "ignore", "files", "directories"}
    if set(data) - allowed:
        raise ValueError(f"unknown manifest keys: {sorted(set(data) - allowed)}")
    settings, ignore = (data.get("settings", {}), data.get("ignore", {}))
    if not isinstance(settings, dict) or not isinstance(ignore, dict):
        raise ValueError("settings and ignore must be tables")
    if set(settings) - {"target"} or set(ignore) - {"names", "suffixes", "globs"}:
        raise ValueError("unknown settings/ignore key")
    files, directories = (data.get("files", []), data.get("directories", []))
    if not isinstance(files, list) or not isinstance(directories, list):
        raise ValueError("files and directories must be arrays of tables")
    if "target" in settings and (not isinstance(settings["target"], str)):
        raise ValueError("settings.target must be a string")
    if not files and not directories:
        raise ValueError(
            "front_repo.toml has no active [[files]] or [[directories]] mappings; "
            "add one before use"
        )
    for n, row in enumerate(files):
        if not isinstance(row, dict) or set(row) != {"source", "target"}:
            raise ValueError(f"files[{n}] requires source and target")
        safe_rel(row["source"])
        safe_rel(row["target"])
    for n, row in enumerate(directories):
        valid = isinstance(row, dict) and not set(row) - {"source", "target", "exclude"}
        valid = valid and {"source", "target"} <= set(row)
        if not valid:
            raise ValueError(f"directories[{n}] is invalid")
        safe_rel(row["source"])
        safe_rel(row["target"])
        patterns = row.get("exclude", [])
        invalid = not isinstance(patterns, list) or any(
            not isinstance(x, str)
            or "\\" in x
            or x.startswith("/")
            or ".." in PurePosixPath(x).parts
            for x in patterns
        )
        if invalid:
            raise ValueError(f"directories[{n}].exclude is invalid")
    for key in ("names", "suffixes", "globs"):
        values = ignore.get(key, [])
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
            raise ValueError(f"ignore.{key} must be strings")
    return {"settings": settings, "ignore": ignore, "files": files, "directories": directories}


def git_exe(root):
    local = root / "frutlups.local.toml"
    if not local.exists():
        return "git"
    try:
        data = tomllib.loads(local.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot load frutlups.local.toml: {exc}") from exc
    known = {"schema", "pi", "claude", "git", "llloom", "path_dirs", "env_passthrough"}
    if data.get("schema") != "frutlups.local/1" or set(data) - known:
        raise ValueError("frutlups.local.toml has an invalid schema or key")
    value = data.get("git", "git")
    if value != "git" and (not isinstance(value, str) or not Path(value).is_absolute()):
        raise ValueError("frutlups.local.toml git must be absolute")
    return value


def git(root, exe, *args):
    try:
        return subprocess.run(
            [exe, "-C", str(root), *args], check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"git {' '.join(args)} failed: {exc}") from exc


def git_state(root, exe):
    commit = git(root, exe, "rev-parse", "HEAD").stdout.strip()
    status = git(root, exe, "status", "--porcelain").stdout
    return commit, status


def is_sensitive(rel):
    low, parts = (rel.lower(), PurePosixPath(rel.lower()).parts)
    if parts and parts[0] in (".git", "local_state"):
        return True
    if low == "frutlups.local.toml":
        return True
    return any((fnmatch.fnmatch(part, pattern) for part in parts for pattern in SENSITIVE))


def ignored(name, rules):
    return (
        name in rules.get("names", [])
        or any(name.endswith(x) for x in rules.get("suffixes", []))
        or any(fnmatch.fnmatch(name, x) for x in rules.get("globs", []))
    )


def excluded(rel, patterns):
    return any(
        fnmatch.fnmatch(rel, pattern)
        or pattern.endswith("/**")
        and (rel == pattern[:-3] or rel.startswith(pattern[:-2]))
        for pattern in patterns
    )


def source_file(root, rel, allow_sensitive):
    reject_symlinks(root, rel, "source")
    path = inside(root, rel, "read")
    if is_sensitive(rel) and (not allow_sensitive):
        raise ValueError(f"refusing sensitive source: {rel}")
    if not path.is_file():
        raise ValueError(f"missing source file: {rel}")
    return path


def walk_source(root, rel, rules, patterns, allow_sensitive):
    reject_symlinks(root, rel, "source")
    base = inside(root, rel, "read")
    if base.is_symlink() or not base.is_dir():
        raise ValueError(f"missing or symlinked source directory: {rel}")
    out = []
    for here, dirs, files in os.walk(base, followlinks=False):
        hp = Path(here)
        kept = []
        for name in dirs:
            child, sub = (hp / name, (hp / name).relative_to(base).as_posix())
            if ignored(name, rules) or excluded(sub, patterns):
                continue
            if child.is_symlink():
                raise ValueError(f"refusing symlink source directory: {rel}/{sub}")
            kept.append(name)
        dirs[:] = kept
        for name in files:
            sub = (hp / name).relative_to(base).as_posix()
            if ignored(name, rules) or excluded(sub, patterns):
                continue
            full_rel = f"{rel.rstrip('/')}/{sub}"
            out.append((sub, source_file(root, full_rel, allow_sensitive)))
    return out


def target_file(root, rel, action):
    reject_symlinks(root, rel, "target")
    return inside(root, rel, action)


def plan(manifest, source, target, allow_sensitive=False):
    entries, expected, managed, rules = ([], set(), [], manifest["ignore"])

    def add(src, rel):
        if rel == STATE or rel in expected:
            raise ValueError(f"duplicate/reserved target: {rel}")
        dst = target_file(target, rel, "write")
        expected.add(rel)
        if not dst.exists():
            action = "copy-new"
        elif dst.is_file() and digest(src) == digest(dst):
            action = "same"
        else:
            action = "copy-update"
        entries.append({"action": action, "source": src, "target": dst, "rel": rel})

    for row in manifest["files"]:
        add(source_file(source, row["source"], allow_sensitive), row["target"])
    for row in manifest["directories"]:
        base = row["target"].rstrip("/")
        managed.append(base)
        walked = walk_source(source, row["source"], rules, row.get("exclude", []), allow_sensitive)
        for sub, src in walked:
            add(src, f"{base}/{sub}")
    for base in managed:
        folder = target_file(target, base, "inspect")
        if not folder.exists():
            continue
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError(f"managed target is not a directory: {base}")
        for here, dirs, files in os.walk(folder, followlinks=False):
            hp = Path(here)
            for name in dirs:
                if (hp / name).is_symlink():
                    rel = (hp / name).relative_to(target).as_posix()
                    raise ValueError(f"refusing target symlink: {rel}")
            for name in files:
                path = hp / name
                rel = path.relative_to(target).as_posix()
                if path.is_symlink():
                    raise ValueError(f"refusing target symlink: {rel}")
                if rel not in expected and rel != STATE:
                    entries.append({"action": "delete", "source": None, "target": path, "rel": rel})
    return (entries, expected)


def load_state(target):
    path = target / STATE
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError("invalid sync state file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid sync state: {exc}") from exc
    fields = {"schema", "source_commit", "source_dirty", "manifest_sha256", "files"}
    valid = (
        isinstance(data, dict)
        and set(data) == fields
        and data.get("schema") == "front_repo.sync/1"
        and isinstance(data.get("files"), dict)
        and type(data.get("source_dirty")) is bool
    )
    if not valid:
        raise ValueError("invalid sync state schema")
    commit_ok = re.fullmatch("[0-9a-f]{7,64}", str(data.get("source_commit", "")))
    manifest_ok = re.fullmatch("[0-9a-f]{64}", str(data.get("manifest_sha256", "")))
    if not commit_ok or not manifest_ok:
        raise ValueError("invalid sync state hashes")
    for rel in data["files"]:
        safe_rel(rel)
    if any((not re.fullmatch("[0-9a-f]{64}", str(value)) for value in data["files"].values())):
        raise ValueError("invalid projected-file hash")
    return data


def divergences(entries, state):
    recorded, out = (state.get("files", {}) if state else {}, [])
    for entry in entries:
        rel, path = (entry["rel"], entry["target"])
        if rel in recorded:
            if not path.is_file() or path.is_symlink() or digest(path) != recorded[rel]:
                out.append(rel)
        elif entry["action"] in ("copy-update", "delete"):
            out.append(rel)
    for rel, old in recorded.items():
        if not any((x["rel"] == rel for x in entries)):
            if entries:
                depth = len(PurePosixPath(entries[0]["rel"]).parts) - 1
                path = entries[0]["target"].parents[depth] / rel
            else:
                path = None
            changed = (
                path
                and path.exists()
                and (not path.is_file() or path.is_symlink() or digest(path) != old)
            )
            if changed:
                out.append(rel)
    return sorted(set(out))


def write_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{dst.name}.", dir=dst.parent)
    os.close(fd)
    try:
        shutil.copy2(src, name)
        os.replace(name, dst)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply(entries):
    for entry in entries:
        if entry["action"] in ("copy-new", "copy-update"):
            write_copy(entry["source"], entry["target"])
        elif entry["action"] == "delete" and entry["target"].exists():
            entry["target"].unlink()


def state_value(source, source_commit, dirty, manifest_path, entries):
    files = {
        entry["rel"]: digest(entry["source"])
        for entry in sorted(entries, key=lambda item: item["rel"])
        if entry["action"] != "delete"
    }
    return {
        "schema": "front_repo.sync/1",
        "source_commit": source_commit,
        "source_dirty": bool(dirty),
        "manifest_sha256": digest(manifest_path),
        "files": files,
    }


def write_state(target, value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    path = target / STATE
    fd, name = tempfile.mkstemp(prefix=".front-state.", dir=target)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def report(entries, diverged):
    for action in ("copy-new", "copy-update", "delete", "same"):
        rows = [x["rel"] for x in entries if x["action"] == action]
        if rows:
            print(f"{action}: {len(rows)}")
            [print(f"  {x}") for x in rows]
    if diverged:
        print(f"diverged: {len(diverged)}")
        [print(f"  {x}") for x in diverged]


def add_common(parser):
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--dev-root", type=Path, default=ROOT)
    parser.add_argument("--allow-dirty-source", action="store_true")
    parser.add_argument("--allow-sensitive", action="store_true")


def main(argv=None):
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    boot = subs.add_parser("bootstrap")
    add_common(boot)
    boot.add_argument("--output-dir", type=Path, required=True)
    boot.add_argument("--allow-non-empty-output", action="store_true")
    for name in ("check", "apply", "status"):
        p = subs.add_parser(name)
        add_common(p)
        p.add_argument("--target-repo", type=Path)
        p.add_argument("--allow-dirty-target", action="store_true")
        p.add_argument("--overwrite-diverged", action="store_true")
    args = parser.parse_args(argv)
    try:
        source = args.dev_root.resolve()
        manifest_path = (args.manifest or source / "front_repo.toml").resolve()
        manifest = load_manifest(manifest_path)
        exe = git_exe(source)
        commit, dirty = git_state(source, exe)
        if dirty and (not args.allow_dirty_source) and (args.command != "status"):
            raise ValueError("development repository is dirty; use --allow-dirty-source")
        if args.command == "bootstrap":
            if os.environ.get("FRUTLUPS_SEAT"):
                raise ValueError("agent seats may not bootstrap a front repository")
            target = args.output_dir.resolve()
            separated(source, target)
            if (target / ".git").exists():
                raise ValueError("bootstrap output already contains .git")
            if target.exists() and any(target.iterdir()) and (not args.allow_non_empty_output):
                raise ValueError("bootstrap output is not empty")
            target.mkdir(parents=True, exist_ok=True)
            entries, _ = plan(manifest, source, target, args.allow_sensitive)
            div = divergences(entries, load_state(target))
            report(entries, div)
            if div:
                raise ValueError("bootstrap would overwrite diverged/unmanaged files")
            apply(entries)
            write_state(target, state_value(source, commit, dirty, manifest_path, entries))
            print(f"bootstrapped {target}")
            return 0
        target_raw = args.target_repo or manifest["settings"].get("target")
        if not target_raw:
            raise ValueError("pass --target-repo or set settings.target")
        target = Path(target_raw).resolve()
        separated(source, target)
        git(target, exe, "rev-parse", "--git-dir")
        target_dirty = git(target, exe, "status", "--porcelain").stdout
        entries, _ = plan(manifest, source, target, args.allow_sensitive)
        state = load_state(target)
        div = divergences(entries, state)
        report(entries, div)
        if args.command == "status":
            print(f"recorded source: {(state.get('source_commit', 'none') if state else 'none')}")
            print(f"current source: {commit}")
            print(f"source dirty: {bool(dirty)}")
            print(f"target dirty: {bool(target_dirty)}")
            print(f"pending changes: {sum((x['action'] != 'same' for x in entries))}")
            print(f"divergence count: {len(div)}")
            changed = not state or state.get("manifest_sha256") != digest(manifest_path)
            print(f"manifest changed: {changed}")
            return 0
        if args.command == "check":
            return 0
        if os.environ.get("FRUTLUPS_SEAT"):
            raise ValueError("agent seats may not apply a front repository projection")
        if target_dirty and (not args.allow_dirty_target):
            raise ValueError("front repository is dirty; use --allow-dirty-target")
        if div and (not args.overwrite_diverged):
            raise ValueError("front repository has diverged files; use --overwrite-diverged")
        apply(entries)
        write_state(target, state_value(source, commit, dirty, manifest_path, entries))
        print(f"applied {sum((x['action'] != 'same' for x in entries))} change(s)")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
