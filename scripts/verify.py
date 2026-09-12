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
import _integrity
import _process
import _workspace
import ledger
import roadmap

_LAST_COMPONENT = r"(?:[^\\/\r\n<>\"'`]*?\.[a-z0-9]{1,12}(?=\s|[):,;]|$)|[^\s<>\"'`\\/]+)"
ABSOLUTE_PATH = re.compile(
    r"(?i)(?<![\w:/.])(?:"
    r"[a-z]:[\\/](?:[^\\/\r\n<>\"'`]+[\\/])*"
    r"|\\\\(?:[^\\/\r\n<>\"'`]+[\\/])+"
    r"|/(?!/)(?=[a-z0-9_.~])(?:[^\\/\r\n<>\"'`]+[\\/])+"
    r")" + _LAST_COMPONENT
)
QUOTED_PATH = re.compile(r"([\"'`])((?:[a-zA-Z]:[\\/]|/(?!/)|\\\\|file://)[^\r\n]*?)\1")
FILE_URL = re.compile(r"\bfile://[^\r\n<>\"'`]+", re.IGNORECASE)
PROTECTED = re.compile(r"https?://[^\s<>\"'`]+|(?<!\w)r?([\"'])\^[^\r\n]*?\$\1")


def _tail(value: bytes) -> str:
    if len(value) > 4096:
        # Never retain a cut path/secret suffix or split a Markdown construct.
        value = value[-4096:].partition(b"\n")[2]
    return value.decode("utf-8", "replace")


def _scrub(value: bytes, root: Path, env: dict[str, str]) -> str:
    text = value.decode("utf-8", "replace")
    for form in {str(root.resolve()), root.resolve().as_posix()}:
        text = re.sub(re.escape(form), "<repo>", text, flags=re.IGNORECASE)
    secret_words = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    for key, secret in env.items():
        if secret and len(secret) >= 4 and any(word in key.upper() for word in secret_words):
            text = text.replace(secret, "<redacted>")
            for line in secret.splitlines():
                if len(line) >= 4:
                    text = text.replace(line, "<redacted>")
    # URLs and relative Markdown references remain readable. Quoting lets us
    # recognize paths containing spaces without treating a standalone slash as one.
    protected = []

    def protect(match):
        protected.append(match[0])
        return f"\x00protected{len(protected) - 1}\x00"

    text = PROTECTED.sub(protect, text)
    text = QUOTED_PATH.sub(
        lambda match: (match[1] + "<absolute-path>" + match[1]) if len(match[2]) > 1 else match[0],
        text,
    )
    text = FILE_URL.sub("<absolute-path>", text)
    text = ABSOLUTE_PATH.sub("<absolute-path>", text)
    for number, original in enumerate(protected):
        text = text.replace(f"\x00protected{number}\x00", original)
    return _tail(text.encode("utf-8"))


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
        output.append(_scrub(value.encode("utf-8"), root, os.environ))
    return output


def run(root: Path, sid: str, timeout: float | None = None):
    rm = roadmap.load(root)
    events = ledger.read(root / "05_governance/ledger.jsonl")
    ledger.require_artifacts(root, events)
    state = ledger.fold(events, rm)
    current = state["slices"].get(sid)
    if not current or current["step"] != "verifying":
        raise ValueError(f"{sid} is not awaiting verification")
    _, item = roadmap.slice_by_id(rm, sid)
    declared_argv = item.get("verification", rm["verification"]["full"])
    runtime_plan = rm
    policy = rm["verification"]
    if rm["schema"] == "frutlups.roadmap/2":
        ledger.require_product(root, current)
        _integrity.require_active(root, current, events)
        envelope = _integrity.envelope(root, current["envelope"], sid, current["round"])
        declared_argv = envelope["full"]
        if (
            not isinstance(declared_argv, list)
            or not declared_argv
            or not all(isinstance(value, str) and value for value in declared_argv)
        ):
            raise ValueError("invalid frozen verification command")
        runtime_plan = {"runtime": envelope["runtime"]}
        policy = {key: envelope[key] for key in ("timeout_seconds", "observation")}
    executable, runtime = _workspace.resolve_runtime(root, runtime_plan)
    argv = _workspace.runtime_argv(declared_argv, executable)
    if timeout is None:
        timeout = policy.get("timeout_seconds", 600 if rm["schema"].endswith("/2") else 1800)
    before = c.status_bytes(root)
    witness_before = _workspace.snapshot(root)
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    exit_code = None
    timed_out = False
    stdout = b""
    stderr = b""
    try:
        result = _process.run(argv, cwd=root, env=env, timeout=timeout)
        exit_code = result.returncode
        timed_out = result.timed_out
        stdout = result.stdout
        stderr = result.stderr
        if timed_out:
            stderr += b"\nverification timed out"
    except OSError as exc:
        stderr = f"{type(exc).__name__}: {exc}".encode("utf-8", "replace")
    seconds = round(time.monotonic() - started, 3)
    after = c.status_bytes(root)
    witness_after = _workspace.snapshot(root)
    stable = witness_before == witness_after
    receipt = {
        "schema": "frutlups.receipt/1",
        "slice": sid,
        "round": current["round"],
        "t": c.now(),
        "base_commit": witness_before["head"],
        "tree_dirty_before": bool(before),
        "commands": [
            {
                "label": "full",
                "argv": _public_argv(declared_argv, root),
                "exit": exit_code,
                "secs": seconds,
                "stdout_tail": _scrub(stdout, root, env),
                "stderr_tail": _scrub(stderr, root, env),
                "timed_out": timed_out,
            }
        ],
        "changed_files": current["changed"],
        "tree_clean_after": not bool(after),
        "ok": exit_code == 0 and not timed_out and stable,
    }
    if rm["schema"] == "frutlups.roadmap/2":
        receipt["schema"] = "frutlups.receipt/2"
        del receipt["changed_files"]
        receipt.update(
            {
                "manifest": current["manifest"],
                "witness": {
                    "before": _workspace.snapshot_digest(witness_before),
                    "after": _workspace.snapshot_digest(witness_after),
                    "stable": stable,
                    "head": witness_before["head"],
                    "index": witness_before["index"],
                    "product": _integrity.product_digest(root, witness_before, events),
                },
                "runtime": runtime,
                "observation": policy.get("observation", "process"),
            }
        )
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
    parser.add_argument("--timeout", type=float)
    args = parser.parse_args(argv)
    try:
        with c.mutation(args.root.resolve()):
            receipt, rel = run(args.root.resolve(), args.slice, args.timeout)
        result = "ok" if receipt["ok"] else "failed"
        print(f"{args.slice} r{receipt['round']} verify {result} -> {rel}")
        return 0 if receipt["ok"] else 1
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
