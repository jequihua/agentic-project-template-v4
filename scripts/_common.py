"""Small shared primitives for the v4 manual-loop scripts."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
HASH_CHUNK = 64 * 1024


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
    return git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
