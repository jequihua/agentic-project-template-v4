"""Project-owned hermetic verification entry point; configure COMMANDS first."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Replace this with the project's real argv lists or {"argv": [...], "cwd": "subdir"}.
COMMANDS: list[object] = []


def _command(value, project_root):
    if isinstance(value, list):
        argv = value
        cwd_value = "."
    elif isinstance(value, dict) and set(value) <= {"argv", "cwd"} and "argv" in value:
        argv = value["argv"]
        cwd_value = value.get("cwd", ".")
    else:
        raise ValueError("verification command must be an argv list or an argv/cwd mapping")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
    ):
        raise ValueError("invalid verification argv list")
    if cwd_value == ".":
        return argv, project_root
    if (
        not isinstance(cwd_value, str)
        or not cwd_value
        or "\x00" in cwd_value
        or "\\" in cwd_value
        or cwd_value.startswith("/")
        or ":" in cwd_value.split("/", 1)[0]
        or any(part in ("", ".", "..") for part in cwd_value.split("/"))
    ):
        raise ValueError(f"unsafe verification cwd: {cwd_value!r}")
    cwd = (project_root / cwd_value).resolve()
    try:
        cwd.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"verification cwd escapes the project: {cwd_value!r}") from exc
    if not cwd.is_dir():
        raise ValueError(f"verification cwd is not a directory: {cwd_value!r}")
    return argv, cwd


def run(commands=COMMANDS, project_root=ROOT):
    if not commands:
        print(
            "hermetic verification is not configured; "
            "add project argv lists or mappings to COMMANDS",
            file=sys.stderr,
        )
        return 2
    project_root = Path(project_root).resolve()
    try:
        prepared = [_command(command, project_root) for command in commands]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="project-verification-") as name:
        workspace = Path(name).resolve()
        try:
            workspace.relative_to(project_root)
        except ValueError:
            pass
        else:
            print("refusing a verification workspace inside the project", file=sys.stderr)
            return 2
        env = os.environ.copy()
        env.update(
            {
                "TEMP": str(workspace),
                "TMP": str(workspace),
                "VERIFICATION_SCRATCH": str(workspace),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PROJECT_ROOT": str(project_root),
            }
        )
        for number, (command, cwd) in enumerate(prepared, 1):
            try:
                result = subprocess.run(command, cwd=cwd, env=env, shell=False)
            except OSError as exc:
                print(
                    f"verification command {number} could not start: argv={command!r} "
                    f"cwd={cwd}: {exc}",
                    file=sys.stderr,
                )
                return 2
            if result.returncode:
                print(
                    f"verification command {number} failed: argv={command!r} "
                    f"cwd={cwd} exit={result.returncode}",
                    file=sys.stderr,
                )
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
