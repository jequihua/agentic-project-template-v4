"""Raw workspace witnesses and the standalone project Python convention."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import sys
import tomllib
from pathlib import Path

import _common as c
import _git as g


def snapshot_digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _identity(root, rel):
    path = root / rel
    # Do not follow a replaced ancestor into an ignored store or outside the project.
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            return {"kind": "symlink-parent", "sha": snapshot_digest(os.readlink(parent))}
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"kind": "missing"}
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        return {"kind": "symlink", "mode": mode, "sha": snapshot_digest(os.readlink(path))}
    if stat.S_ISREG(info.st_mode):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)
        return {"kind": "file", "mode": mode, "sha": digest.hexdigest()}
    return {"kind": "directory" if stat.S_ISDIR(info.st_mode) else "special", "mode": mode}


def snapshot(root: Path):
    """Witness Git-owned paths, raw contents, types/modes, HEAD and index entries.

    Git applies its explicit ignore rules while listing untracked paths. No cache,
    dependency or run-store walk is performed by this helper. Ignored files and
    submodule-internal contents are outside this witness.
    """
    root = Path(root).resolve()
    names = g.run(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
    files = {}
    for name in sorted(set(names.split(b"\0")) - {b""}):
        rel = os.fsdecode(name)
        c.safe_rel(rel)
        files[rel] = _identity(root, rel)
    return {
        "head": g.run(root, "rev-parse", "HEAD", limit=1024).stdout.decode().strip(),
        "index": hashlib.sha256(g.run(root, "ls-files", "--stage", "-v", "-z").stdout).hexdigest(),
        "files": files,
    }


def runtime_argv(argv, executable):
    """Only the portable literal `python` names the declared project interpreter."""
    return [
        executable if number == 0 and value == "python" else value
        for number, value in enumerate(argv)
    ]


def resolve_runtime(root: Path, rm=None):
    """Return executable and path-free identity; local resolution is never tracked."""
    root = Path(root).resolve()
    local = root / "project.local.toml"
    executable = sys.executable
    source = "invoking_python"
    if local.exists():
        if (
            # check-ignore accepts literal names but rejects pathspec magic.
            g.run(
                root,
                "--no-literal-pathspecs",
                "check-ignore",
                "-q",
                "project.local.toml",
                check=False,
            ).returncode
            or g.run(
                root, "ls-files", "--error-unmatch", "project.local.toml", check=False
            ).returncode
            == 0
        ):
            raise ValueError("project.local.toml must be ignored and untracked")
        data = tomllib.loads(local.read_text(encoding="utf-8"))
        if set(data) != {"schema", "python"} or data.get("schema") != "template.local/1":
            raise ValueError("project.local.toml requires schema template.local/1 and python")
        value = data["python"]
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError("project.local.toml python must name an existing absolute executable")
        executable = str(Path(value).resolve())
        source = "project.local"
    if Path(executable).resolve() == Path(sys.executable).resolve():
        identity = {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
        }
    else:
        import _process

        result = _process.run(
            [
                executable,
                "-I",
                "-S",
                "-c",
                (
                    "import json,platform;print(json.dumps({"
                    "'python':platform.python_version(),"
                    "'implementation':platform.python_implementation()}))"
                ),
            ],
            cwd=root,
            timeout=10,
        )
        if result.returncode != 0 or result.timed_out:
            raise ValueError("selected project Python could not report its runtime identity")
        try:
            identity = json.loads(result.stdout)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(
                "selected project Python returned an invalid runtime identity"
            ) from exc
        if (
            not isinstance(identity, dict)
            or set(identity) != {"python", "implementation"}
            or not all(isinstance(value, str) and value for value in identity.values())
        ):
            raise ValueError("selected project Python returned an invalid runtime identity")
    expected = (rm or {}).get("runtime", {}).get("python")
    if expected and not (
        identity["python"] == expected or identity["python"].startswith(expected + ".")
    ):
        raise ValueError(
            f"project Python {expected} required; selected runtime is {identity['python']}"
        )
    identity["source"] = source
    identity["sha"] = snapshot_digest(
        {"runtime": identity, "declaration": (rm or {}).get("runtime")}
    )
    return executable, identity
