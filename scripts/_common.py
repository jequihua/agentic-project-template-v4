"""Small shared primitives for the v4 manual-loop scripts."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
HASH_CHUNK = 64 * 1024
MEMO_LIMIT = 16 * 1024 * 1024
_LOCKS = {}
_COMMAND = ContextVar("template_command", default=None)
_ARTIFACTS = ContextVar("template_artifacts", default=None)


@contextmanager
def command_scope():
    """Share immutable validation results only until the outer command returns."""
    if _COMMAND.get() is not None:
        yield
        return
    token = _COMMAND.set({})
    try:
        yield
    finally:
        _COMMAND.reset(token)


def cache(namespace):
    current = _COMMAND.get()
    return None if current is None else current.setdefault(namespace, {})


def remember(namespace, key, value, source_bytes):
    """Bound optional evidence memoization; overflow still validates without caching."""
    memo = cache(namespace)
    if memo is None or key in memo:
        return
    budget = cache("evidence_memo_budget")
    used, count = budget.get("bytes", 0), budget.get("entries", 0)
    if used + source_bytes <= MEMO_LIMIT and count < 10_000:
        memo[key] = value
        budget.update(bytes=used + source_bytes, entries=count + 1)


def file_key(path):
    path = Path(path).resolve()
    try:
        stat = path.stat()
    except FileNotFoundError:
        return (str(path), None)
    return (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@contextmanager
def artifact_batch(root):
    """Roll back solely owned artifacts on confirmed refusal, never uncertain append."""
    if _ARTIFACTS.get() is not None:
        yield
        return
    path = Path(root) / "05_governance/ledger.jsonl"
    before = path.read_bytes() if path.exists() else b""
    created = []
    token = _ARTIFACTS.set(created)
    try:
        yield
    except ValueError:
        after = path.read_bytes() if path.exists() else b""
        if before == after:
            for artifact, identity, digest in reversed(created):
                if file_key(artifact) == identity and sha(artifact) == digest:
                    artifact.unlink()
        raise
    finally:
        _ARTIFACTS.reset(token)


def artifact_text(path, text):
    """Publish immutable text; register only files created by this transaction."""
    digest = evidence_sha_bytes(text.encode("utf-8"))
    if path.exists():
        if sha(path) != digest:
            raise ValueError("immutable artifact collision")
        return
    atomic_text(path, text)
    created = _ARTIFACTS.get()
    if created is not None:
        created.append((path, file_key(path), digest))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def evidence_sha_bytes(data: bytes) -> str:
    """Hash normalized evidence bytes."""
    if b"\x00" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    """Stream a normalized evidence hash."""
    with path.open("rb") as stream:
        binary = any(b"\x00" in chunk for chunk in iter(lambda: stream.read(HASH_CHUNK), b""))
    digest = hashlib.sha256()
    pending = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(HASH_CHUNK), b""):
            if binary:
                digest.update(chunk)
                continue
            data = pending + chunk
            if data.endswith(b"\r"):
                data, pending = data[:-1], b"\r"
            else:
                pending = b""
            digest.update(data.replace(b"\r\n", b"\n"))
    digest.update(pending)
    return digest.hexdigest()


def safe_rel(value: object, *, directory: bool = False) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError(f"unsafe repository-relative path: {value!r}")
    raw = value[:-1] if directory and value.endswith("/") else value
    parts = raw.split("/")
    unsafe = (
        not raw
        or raw.startswith("/")
        or ":" in parts[0]
        or any(part in ("", ".", "..") for part in parts)
    )
    if unsafe:
        raise ValueError(f"unsafe repository-relative path: {value!r}")
    return raw + ("/" if directory else "")


def cli_rel(value: object, *, directory: bool = False) -> str:
    """Normalize a CLI path before strict storage validation."""
    if not isinstance(value, str) or re.match(r"^[A-Za-z]:[\\/]", value):
        raise ValueError(f"unsafe repository-relative path: {value!r}")
    normalized = value.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return safe_rel(normalized, directory=directory)


def repo_path(root: Path, rel: str) -> Path:
    root = root.resolve()
    lexical = root / rel
    path = lexical.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {rel}") from exc
    return lexical


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a YAML mapping")
    return data


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text.replace("\r\n", "\n"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def git(root: Path, *args: str, check: bool = True, text: bool = False):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=text,
    )


def status_bytes(root: Path) -> bytes:
    import _git

    return _git.run(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout


@contextmanager
def writer_lock(root):
    """One OS-owned byte lock, shared by manual writers and compatible runners."""
    result = git(root, "rev-parse", "--git-common-dir", text=True, check=False)
    if result.returncode:
        # Preserve the legacy standalone ledger/render API. A /2 writer always
        # needs a Git repository so it cannot bypass interoperable ownership.
        config = Path(root) / "roadmap.yaml"
        if config.is_file() and load_yaml(config).get("schema") == "frutlups.roadmap/1":
            yield
            return
        raise ValueError("initialize the project Git repository before mutating /2 state")
    common_dir = result.stdout.strip()
    folder = (Path(root) / common_dir).resolve()
    key = str(folder)
    if key in _LOCKS:
        yield
        return
    path = folder / "frutlups-writer.lock"
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError(
                "another writer owns the repository; status remains available"
            ) from exc
        _LOCKS[key] = stream
        try:
            yield
        finally:
            _LOCKS.pop(key, None)
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def mutation(root, rm=None):
    with command_scope(), writer_lock(root), artifact_batch(root):
        import _protocol

        _protocol.ensure_writable(root, rm)
        yield
