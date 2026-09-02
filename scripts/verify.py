"""Run a slice's authoritative verification and record a receipt."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import _common as c
import ledger
import roadmap


ABSOLUTE_PATH = re.compile(r"(?i)(?<![\w:/])(?:[a-z]:[\\/]|/)(?:[^\s<>\"']+[\\/])*[^\s<>\"']+")


def _tail(value: bytes) -> str:
    return value[-4096:].decode("utf-8", "replace")


def _scrub(value: bytes, root: Path, env: dict[str, str]) -> str:
    text = _tail(value)
    for form in {str(root.resolve()), root.resolve().as_posix()}:
        text = text.replace(form, "<repo>").replace(form.lower(), "<repo>")
    secret_words = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    for key, secret in env.items():
        if secret and len(secret) >= 4 and any(word in key.upper() for word in secret_words):
            text = text.replace(secret, "<redacted>")
    return ABSOLUTE_PATH.sub("<absolute-path>", text)


def _public_argv(argv, root):
    output = []
    for value in argv:
        try:
            path = Path(value)
            if path.is_absolute():
                try:
                    value = path.resolve().relative_to(root.resolve()).as_posix()
                except ValueError:
                    value = "<outside-repo>"
        except (OSError, ValueError):
            pass
        output.append(ABSOLUTE_PATH.sub("<outside-repo>", value))
    return output


def run(root: Path, sid: str, timeout: float = 1800):
    rm = roadmap.load(root)
    events = ledger.read(root / "05_governance/ledger.jsonl")
    state = ledger.fold(events, rm)
    current = state["slices"].get(sid)
    if not current or current["step"] != "verifying":
        raise ValueError(f"{sid} is not awaiting verification")
    _, item = roadmap.slice_by_id(rm, sid)
    argv = item.get("verification", rm["verification"]["full"])
    before = c.status_bytes(root)
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    exit_code = None
    timed_out = False
    stdout = b""
    stderr = b""
    try:
        result = subprocess.run(
            argv, cwd=root, env=env, capture_output=True, timeout=timeout, shell=False
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = (exc.stderr or b"") + b"\nverification timed out"
    except OSError as exc:
        stderr = f"{type(exc).__name__}: {exc}".encode("utf-8", "replace")
    seconds = round(time.monotonic() - started, 3)
    after = c.status_bytes(root)
    receipt = {
        "schema": "frutlups.receipt/1",
        "slice": sid,
        "round": current["round"],
        "t": c.now(),
        "base_commit": c.git(root, "rev-parse", "HEAD", text=True).stdout.strip(),
        "tree_dirty_before": bool(before),
        "commands": [
            {
                "label": "full",
                "argv": _public_argv(argv, root),
                "exit": exit_code,
                "secs": seconds,
                "stdout_tail": _scrub(stdout, root, env),
                "stderr_tail": _scrub(stderr, root, env),
                "timed_out": timed_out,
            }
        ],
        "changed_files": current["changed"],
        "tree_clean_after": not bool(after),
        "ok": exit_code == 0 and not timed_out and before == after,
    }
    folder = root / "05_governance/reviews" / sid.split("-")[0].lower()
    path = folder / f"{sid}_r{current['round']}_verification.json"
    c.atomic_text(path, json.dumps(receipt, ensure_ascii=False, separators=(",", ":")) + "\n")
    rel = path.relative_to(root).as_posix()
    ledger.append(
        root / "05_governance/ledger.jsonl",
        {
            "ev": "verified",
            "by": "architect",
            "slice": sid,
            "round": current["round"],
            "receipt": rel,
            "sha": c.sha(path),
            "ok": receipt["ok"],
        },
        rm,
    )
    return receipt, rel


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("slice")
    parser.add_argument("--root", type=Path, default=c.ROOT)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args(argv)
    try:
        receipt, rel = run(args.root.resolve(), args.slice, args.timeout)
        result = "ok" if receipt["ok"] else "failed"
        print(f"{args.slice} r{receipt['round']} verify {result} -> {rel}")
        return 0 if receipt["ok"] else 1
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
