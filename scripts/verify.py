"""Run a slice's authoritative verification and record a receipt."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import _common as c
import ledger
import roadmap


def _tail(value: bytes) -> str:
    return value[-4096:].decode("utf-8", "replace")


def _scrub(value: bytes, root: Path, env: dict[str, str]) -> str:
    text = _tail(value)
    for form in {str(root.resolve()), root.resolve().as_posix()}:
        text = text.replace(form, "<repo>").replace(form.lower(), "<repo>")
    for key, secret in env.items():
        if secret and len(secret) >= 4 and any(word in key.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            text = text.replace(secret, "<redacted>")
    return re.sub(r"(?i)(?<![\w])(?:[a-z]:[\\/]|/)(?:[^\s<>\"']+[\\/])*[^\s<>\"']+", "<absolute-path>", text)


def _public_argv(argv, root):
    out = []
    for value in argv:
        try:
            path = Path(value)
            if path.is_absolute():
                try: value = path.resolve().relative_to(root.resolve()).as_posix()
                except ValueError: value = "<outside-repo>"
        except (OSError, ValueError): pass
        out.append(re.sub(r"(?i)(?<![\w])(?:[a-z]:[\\/]|/)[^\s]+", "<outside-repo>", value))
    return out


def run(root: Path, sid: str, timeout: float = 1800):
    rm, events = roadmap.load(root), ledger.read(root / "05_governance/ledger.jsonl")
    state = ledger.fold(events, rm); s = state["slices"].get(sid)
    if not s or s["step"] != "verifying": raise ValueError(f"{sid} is not awaiting verification")
    _, item = roadmap.slice_by_id(rm, sid); argv = item.get("verification", rm["verification"]["full"])
    before = c.status_bytes(root); started = time.monotonic(); env = os.environ.copy(); env["PYTHONDONTWRITEBYTECODE"] = "1"
    exit_code, timed_out, stdout, stderr = None, False, b"", b""
    try:
        result = subprocess.run(argv, cwd=root, env=env, capture_output=True, timeout=timeout, shell=False)
        exit_code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out, stdout, stderr = True, exc.stdout or b"", exc.stderr or b""
        stderr += b"\nverification timed out"
    except OSError as exc:
        stderr = f"{type(exc).__name__}: {exc}".encode("utf-8", "replace")
    secs = round(time.monotonic() - started, 3); after = c.status_bytes(root)
    receipt = {
        "schema": "frutlups.receipt/1", "slice": sid, "round": s["round"], "t": c.now(),
        "base_commit": c.git(root, "rev-parse", "HEAD", text=True).stdout.strip(),
        "tree_dirty_before": bool(before),
        "commands": [{"label": "full", "argv": _public_argv(argv, root), "exit": exit_code,
                      "secs": secs, "stdout_tail": _scrub(stdout, root, env), "stderr_tail": _scrub(stderr, root, env),
                      "timed_out": timed_out}],
        "changed_files": s["changed"], "tree_clean_after": not bool(after),
        "ok": exit_code == 0 and not timed_out and before == after,
    }
    folder = root / "05_governance/reviews" / sid.split("-")[0].lower()
    path = folder / f"{sid}_r{s['round']}_verification.json"; c.atomic_json(path, receipt)
    rel = path.relative_to(root).as_posix()
    ledger.append(root / "05_governance/ledger.jsonl", {"ev": "verified", "by": "architect", "slice": sid,
                  "round": s["round"], "receipt": rel, "sha": c.sha(path), "ok": receipt["ok"]})
    return receipt, rel


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("slice"); parser.add_argument("--root", type=Path, default=c.ROOT); parser.add_argument("--timeout", type=float, default=1800); args = parser.parse_args(argv)
    try:
        receipt, rel = run(args.root.resolve(), args.slice, args.timeout)
        print(f"{args.slice} r{receipt['round']} verify {'ok' if receipt['ok'] else 'failed'} -> {rel}")
        return 0 if receipt["ok"] else 1
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as exc: print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
