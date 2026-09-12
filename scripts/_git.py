"""Literal, bounded Git operations shared by evidence and manual acceptance."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

import _common as c

BLOB_LIMIT = 64 * 1024 * 1024
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})$")
ARGV_LIMIT = 12 * 1024
OUTPUT_LIMIT = 8 * 1024 * 1024
DIFF_NOTICE = "\n[diff truncated; complete manifest remains authoritative]\n"


def run(root, *args, input=None, limit=OUTPUT_LIMIT, truncate=False, check=True):
    """Drain bounded command output; Git metadata overflow always fails closed."""
    import _process

    argv = [
        "git",
        "--no-replace-objects",
        "--no-optional-locks",
        "--literal-pathspecs",
        "-C",
        str(root),
        *args,
    ]
    encoded = subprocess.list2cmdline(argv).encode("utf-16-le" if os.name == "nt" else "utf-8")
    if len(encoded) > ARGV_LIMIT:
        raise ValueError("Git command exceeds the bounded argument allowance")
    result = _process.run(
        argv,
        cwd=Path(root),
        timeout=120,
        tail_limit=limit,
        keep="head",
        input=input,
    )
    if result.timed_out:
        raise ValueError("Git operation timed out; inspect retained state")
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace")[-2048:]
        raise ValueError("Git operation failed: " + detail.strip())
    if not truncate and (result.stdout_bytes > limit or result.stderr_bytes > limit):
        raise ValueError("Git output exceeds the bounded metadata allowance")
    return result


def read_blobs(root, objects):
    """Yield complete blobs from size-checked batches, never aggregate the payload."""
    objects = list(dict.fromkeys(objects))
    if not objects:
        return
    if any(not OID.fullmatch(oid) for oid in objects):
        raise ValueError("invalid Git blob identity")
    framing = 1024
    metadata = run(
        root,
        "cat-file",
        "--batch-check",
        input="".join(o + "\n" for o in objects).encode(),
    ).stdout.splitlines()
    if len(metadata) != len(objects):
        raise ValueError("incomplete Git blob metadata")
    batches, batch, used = [], [], 0
    for oid, line in zip(objects, metadata):
        header = line.decode("ascii").split()
        if len(header) != 3 or header[0] != oid or header[1] != "blob":
            raise ValueError("commit content is not an available blob")
        size = int(header[2])
        if not 0 <= size <= BLOB_LIMIT:
            raise ValueError("Git blob exceeds the 64 MiB per-file allowance")
        cost = len(line) + size + 2
        if batch and used + cost > BLOB_LIMIT + framing:
            batches.append(batch)
            batch, used = [], 0
        batch.append((oid, size, line))
        used += cost
    if batch:
        batches.append(batch)
    for batch in batches:
        data = run(
            root,
            "cat-file",
            "--batch",
            input="".join(oid + "\n" for oid, _, _ in batch).encode(),
            limit=BLOB_LIMIT + framing,
        ).stdout
        offset = 0
        for oid, size, header in batch:
            start = offset + len(header) + 1
            end = start + size
            if data[offset:start] != header + b"\n" or data[end : end + 1] != b"\n":
                raise ValueError("incomplete Git blob evidence")
            yield oid, data[start:end]
            offset = end + 1
        if offset != len(data):
            raise ValueError("unexpected Git blob evidence")
        del data


def blob_hashes(root, objects):
    cache = c.cache("commit_blob_hashes")
    namespace = str(Path(root).resolve())
    objects = list(dict.fromkeys(objects))
    output = {
        oid: cache[namespace, oid]
        for oid in objects
        if cache is not None and (namespace, oid) in cache
    }
    for oid, data in read_blobs(root, [oid for oid in objects if oid not in output]):
        output[oid] = {
            "raw": hashlib.sha256(data).hexdigest(),
            "normalized": c.evidence_sha_bytes(data),
        }
        if cache is not None and len(cache) < 100_000:
            cache[namespace, oid] = output[oid]
        del data
    return output


def paths_checked(paths):
    output = list(dict.fromkeys(c.safe_rel(path) for path in paths))
    if len(output) > 100_000 or sum(len(p.encode("utf-8")) + 1 for p in output) > OUTPUT_LIMIT:
        raise ValueError("Git path manifest exceeds the bounded selection allowance")
    return output


def staged_paths(root):
    data = run(root, "diff", "--cached", "--name-only", "--no-renames", "-z").stdout
    return {c.safe_rel(p.decode("utf-8")) for p in data.split(b"\0") if p}


def guard_index(root, paths):
    extra = staged_paths(root) - set(paths)
    if extra:
        shown = ", ".join(sorted(extra)[:8])
        raise ValueError("unrelated staged paths; index preserved: " + shown)


def stage_exact(root, paths):
    """Stage literal file paths only, preserving all unrelated index/user work."""
    paths = paths_checked(paths)
    guard_index(root, paths)
    if not paths:
        return
    for path in paths:
        target = c.repo_path(Path(root), path)
        if target.is_dir():
            raise ValueError("exact Git selection cannot include a directory: " + path)
    indexed = {
        p.decode("utf-8") for p in run(root, "ls-files", "--cached", "-z").stdout.split(b"\0") if p
    }
    # An already staged deletion has no pathspec match. Its absence remains guarded.
    selected = [p for p in paths if p in indexed or c.repo_path(Path(root), p).exists()]
    if selected:
        selection = b"".join(p.encode("utf-8") + b"\0" for p in selected)
        run(root, "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul", input=selection)
    guard_index(root, paths)


def approved_paths(root, changed):
    """Recover rename origins from Git without changing legacy event grammar."""
    paths = {row["path"] if isinstance(row, dict) else str(row) for row in changed}
    data = run(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    fields = iter(data.split(b"\0"))
    for field in fields:
        if not field:
            continue
        code, path = field[:2], field[3:].decode("utf-8")
        if b"R" in code or b"C" in code:
            origin = next(fields, b"").decode("utf-8")
            if path in paths:
                paths.add(origin)
    return sorted(paths_checked(paths))


def _batches(root, base, paths, stat):
    framing = ["git", "--literal-pathspecs", "-C", str(root), "diff", base]
    framing += ["--stat"] if stat else ["--no-ext-diff", "--no-textconv"]
    encoding = "utf-16-le" if os.name == "nt" else "utf-8"
    batch = []
    for path in paths:
        candidate = framing + ["--", *batch, path]
        if len(subprocess.list2cmdline(candidate).encode(encoding)) > ARGV_LIMIT - 512:
            if not batch:
                raise ValueError("one Git path exceeds the argument allowance")
            yield batch
            batch = []
        batch.append(path)
    if batch:
        yield batch


def bounded_diff(root, base, paths, limit=24000, *, stat=False):
    """Render deterministic literal selections without oversized argv or capture."""
    paths = paths_checked(paths)
    if not paths or limit <= 0:
        return ""
    # A failed revision must not turn into an option or an unbounded default selection.
    revisions = base.split("..")
    if len(revisions) > 2 or any(not item or item.startswith("-") for item in revisions):
        raise ValueError("invalid bounded diff revision")
    resolved = [
        run(root, "rev-parse", "--verify", item + "^{commit}", limit=1024)
        .stdout.decode("ascii")
        .strip()
        for item in revisions
    ]
    revision = "..".join(resolved)
    notice = DIFF_NOTICE.encode("utf-8")
    allowance = max(0, limit - len(notice))
    chunks = []
    used = 0
    batches = list(_batches(root, revision, paths, stat))
    truncated = False
    for number, batch in enumerate(batches):
        remaining = allowance - used
        if remaining <= 0:
            truncated = True
            break
        flags = ("--stat",) if stat else ("--no-ext-diff", "--no-textconv")
        result = run(
            root,
            "diff",
            *flags,
            revision,
            "--",
            *batch,
            limit=remaining,
            truncate=True,
        )
        chunks.append(result.stdout)
        used += len(result.stdout)
        if result.stdout_bytes > remaining:
            truncated = True
            break
        if used >= allowance and number + 1 < len(batches):
            truncated = True
            break
    body = b"".join(chunks).decode("utf-8", "ignore")
    if truncated:
        body += DIFF_NOTICE
    return body.encode("utf-8")[:limit].decode("utf-8", "ignore")
