"""Bounded diagnostics and timeout cleanup of only an invocation's process tree."""

from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool
    stdout_bytes: int
    stderr_bytes: int


class _Tail:
    def __init__(self, limit, keep="tail"):
        self.limit = limit
        self.keep = keep
        self.data = bytearray()
        self.total = 0

    def read(self, stream):
        try:
            while chunk := stream.read(8192):
                self.total += len(chunk)
                self.data.extend(
                    chunk[: max(0, self.limit - len(self.data))] if self.keep == "head" else chunk
                )
                if len(self.data) > self.limit:
                    del self.data[: -self.limit]
        finally:
            stream.close()

    def value(self):
        data = bytes(self.data)
        if self.total > self.limit and self.keep == "tail":
            # A cut token could be the suffix of a secret or a path. Retain only
            # complete lines, including when an unbounded single line was emitted.
            _, separator, data = data.partition(b"\n")
            if not separator:
                data = b""
        return data


class _WindowsJob:
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", Basic),
                ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(
            self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)
        ):
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def assign(self, process):
        import ctypes

        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def run(argv, *, cwd, env=None, timeout=600, tail_limit=16384, keep="tail", input=None):
    """Capture fixed-size tails; no shell, host PID search, or unowned termination.

    Windows uses a gated bootstrap: it cannot launch the command until assigned
    to our kill-on-close Job. POSIX commands start in their own process session.
    Descendants that deliberately escape ownership are outside this guarantee.
    """
    if timeout <= 0 or tail_limit < 1 or keep not in {"head", "tail"}:
        raise ValueError("process timeout and tail limit must be positive")
    job = _WindowsJob() if os.name == "nt" else None
    command = (
        [sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--child"] if job else argv
    )
    process = None
    started = time.monotonic()
    out, err = _Tail(tail_limit, keep), _Tail(tail_limit, keep)
    readers = []
    timed_out = False
    code = None
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE if job or input is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=not bool(job),
        )
        if job:
            job.assign(process)
        for tail, stream in ((out, process.stdout), (err, process.stderr)):
            reader = threading.Thread(target=tail.read, args=(stream,), daemon=True)
            reader.start()
            readers.append(reader)
        if job or input is not None:
            payload = (
                json.dumps(
                    {
                        "argv": argv,
                        "input": base64.b64encode(input).decode("ascii")
                        if input is not None
                        else None,
                    }
                ).encode("utf-8")
                if job
                else input
            )

            def feed():
                try:
                    process.stdin.write(payload)
                except BrokenPipeError:
                    pass
                finally:
                    process.stdin.close()

            writer = threading.Thread(target=feed, daemon=True)
            writer.start()
            readers.append(writer)
        try:
            code = process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        if job:
            job.close()
        elif process:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process:
            if process.poll() is None:
                process.kill()  # Also handles bootstrap failure before Job assignment.
            process.wait()
        for reader in readers:
            reader.join(timeout=5)
        if any(reader.is_alive() for reader in readers):
            raise OSError("owned verification output pipes did not close")
    stdout, stderr = out.value(), err.value()
    if code == 254 and stderr.startswith(b"verification launch failed: "):
        code = None
    return Result(code, stdout, stderr, timed_out, out.total, err.total)


if __name__ == "__main__":
    # The parent sends argv only after assigning this process to its Windows Job.
    command = json.loads(sys.stdin.buffer.read())
    try:
        supplied = command["input"]
        result = subprocess.run(
            command["argv"],
            shell=False,
            check=False,
            input=base64.b64decode(supplied) if supplied is not None else None,
            **({"stdin": subprocess.DEVNULL} if supplied is None else {}),
        )
        raise SystemExit(result.returncode)
    except OSError as exc:
        print(f"verification launch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(254)
