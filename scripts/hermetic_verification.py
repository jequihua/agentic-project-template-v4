"""Project-owned hermetic verification entry point; configure COMMANDS first."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Replace this with the project's real verification argv lists.
COMMANDS: list[list[str]] = []


def run(commands=COMMANDS, project_root=ROOT):
    if not commands:
        print(
            "hermetic verification is not configured; add project argv lists to COMMANDS",
            file=sys.stderr,
        )
        return 2
    with tempfile.TemporaryDirectory(prefix="project-verification-") as name:
        workspace = Path(name).resolve()
        try:
            workspace.relative_to(project_root.resolve())
        except ValueError:
            pass
        else:
            print("refusing a verification workspace inside the project", file=sys.stderr)
            return 2
        env = os.environ.copy()
        env.update({
            "TEMP": str(workspace),
            "TMP": str(workspace),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PROJECT_ROOT": str(project_root.resolve()),
        })
        for command in commands:
            if not command or not all(isinstance(value, str) and value for value in command):
                print("invalid verification argv list", file=sys.stderr)
                return 2
            result = subprocess.run(command, cwd=workspace, env=env, shell=False)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
